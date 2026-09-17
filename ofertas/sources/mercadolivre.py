"""Mercado Livre: scraping da página de ofertas + link de afiliado via Linkbuilder.

O ML não tem API pública para afiliados, mas o Linkbuilder do painel usa uma API
interna simples (createLink), autenticada só pelos cookies da sessão. O bot chama
essa API de dentro de uma página logada (perfil persistente do Chrome em
data/ml_profile). Faça login uma única vez com:

    uv run python -m ofertas ml-login
"""
import json
import logging
import os
import re
import subprocess
import sys
import time
from pathlib import Path

from bs4 import BeautifulSoup

from ..config import DATA_DIR, config
from ..models import Oferta
from ..utils import USER_AGENT, parse_preco_br, sessao

log = logging.getLogger("ofertas.ml")

URL_OFERTAS = "https://www.mercadolivre.com.br/ofertas"
URL_LINKBUILDER = "https://www.mercadolivre.com.br/afiliados/linkbuilder"
API_CREATELINK = "https://www.mercadolivre.com.br/affiliate-program/api/v2/affiliates/createLink"
PERFIL_DIR = DATA_DIR / "ml_profile"
STATE_FILE = DATA_DIR / "ml_state.json"

_RE_ID = re.compile(r"(MLB-?\d{6,})")


def e_link(url: str) -> bool:
    return any(d in url for d in ("mercadolivre.com", "mercadolibre.com", "meli.la/"))


def tem_sessao() -> bool:
    if STATE_FILE.exists() and STATE_FILE.stat().st_size > 50:
        return True
    return PERFIL_DIR.exists() and any(PERFIL_DIR.iterdir())


# ── Busca de ofertas (scraping, sem login) ───────────────────────────

def _categorias() -> dict[str, str]:
    """{id: nome} das categorias do config (aceita dict ou lista de ids); vazio = todas."""
    cats = config.fonte_ml.get("categorias") or {}
    return dict(cats) if isinstance(cats, dict) else {str(c): str(c) for c in cats}


def buscar_ofertas() -> list[Oferta]:
    """Página de ofertas do ML, filtrada pelas categorias do config (ofertas?category=MLB...)."""
    paginas = max(1, int(config.fonte_ml.get("paginas", 1)))
    categorias = _categorias() or {"": "todas"}
    s = sessao()
    ofertas: dict[str, Oferta] = {}
    for cat_id, nome in categorias.items():
        for pagina in range(1, paginas + 1):
            params = {}
            if cat_id:
                params["category"] = cat_id
            if pagina > 1:
                params["page"] = pagina
            r = s.get(URL_OFERTAS, params=params or None, timeout=30)
            r.raise_for_status()
            achadas = _parse_pagina(r.text)
            for o in achadas:
                ofertas.setdefault(o.id_produto, o)
            log.info("Mercado Livre %s: %d ofertas", nome, len(achadas))
            time.sleep(1)
    log.info("Mercado Livre: %d ofertas coletadas", len(ofertas))
    return list(ofertas.values())


def _preco_de(card, seletor_base: str) -> float | None:
    fracao = card.select_one(f"{seletor_base} .andes-money-amount__fraction")
    if not fracao:
        return None
    centavos = card.select_one(f"{seletor_base} .andes-money-amount__cents")
    texto = fracao.get_text(strip=True) + ("," + centavos.get_text(strip=True) if centavos else "")
    return parse_preco_br(texto)


def _parse_card(card) -> Oferta | None:
    a = card.select_one("a.poly-component__title")
    if not (a and a.get("href")):
        return None
    titulo = a.get_text(strip=True)
    url = a["href"].split("#")[0].split("?")[0]

    m = _RE_ID.search(a["href"])
    id_produto = m.group(1).replace("-", "") if m else url.rstrip("/").rsplit("/", 1)[-1][:40]

    preco = _preco_de(card, ".poly-price__current")
    preco_original = _preco_de(card, "s.andes-money-amount--previous")

    desconto = None
    selo = card.select_one(".poly-price__discount-polylabel, .andes-money-amount__discount")
    if selo:
        m = re.search(r"(\d+)\s*%", selo.get_text())
        desconto = int(m.group(1)) if m else None

    img = card.select_one("img.poly-component__picture")
    imagem = (img.get("data-src") or img.get("src")) if img else None
    if imagem and imagem.startswith("data:"):
        imagem = None  # placeholder de lazy-load

    partes = []
    review = card.select_one(".poly-component__review-compacted")
    if review:
        partes.append("⭐ " + re.sub(r"\s*\|\s*", " · ", review.get_text(" ", strip=True)))
    if "Frete grátis" in card.get_text():
        partes.append("🚚 Frete grátis")
    pix = card.select_one(".poly-price__unit-description")
    if pix and "pix" in pix.get_text().lower():
        partes.append("💠 preço no Pix")

    return Oferta(
        plataforma="mercadolivre",
        id_produto=id_produto,
        titulo=titulo,
        url_afiliado="",  # preenchido depois pelo Linkbuilder
        url_produto=url,
        preco=preco,
        preco_original=preco_original,
        desconto_pct=desconto,
        imagem=imagem,
        extra=" · ".join(partes) or None,
    )


def _parse_pagina(html: str) -> list[Oferta]:
    soup = BeautifulSoup(html, "lxml")
    cards = soup.select("div.poly-card")
    ofertas = [o for o in (_parse_card(c) for c in cards) if o]
    if cards and not ofertas:
        log.warning("Página de ofertas do ML mudou de layout? %d cards, 0 parseados", len(cards))
    return ofertas


# ── Link de afiliado via Linkbuilder (Playwright + sessão logada) ────

def _abrir_contexto(pw, headless: bool):
    """Google Chrome instalado (build de produção) + perfil persistente do projeto.

    O ML recusa login no "Chrome for Testing" do Playwright, então usamos o
    Chrome real via channel="chrome" e removemos as marcas de automação.
    """
    args = [
        "--disable-blink-features=AutomationControlled",
        "--no-sandbox",
        "--disable-setuid-sandbox",
        "--disable-dev-shm-usage",
    ]
    kwargs = dict(
        channel="chrome",
        headless=headless,
        locale="pt-BR",
        args=args,
        ignore_default_args=["--enable-automation"],
    )
    if headless:
        kwargs["user_agent"] = USER_AGENT  # o headless real se anuncia como HeadlessChrome
    else:
        kwargs["no_viewport"] = True
    try:
        ctx = pw.chromium.launch_persistent_context(str(PERFIL_DIR), **kwargs)
    except Exception as e:
        msg = str(e).lower()
        if "chrome" not in msg and "executable" not in msg and "not found" not in msg:
            raise
        log.warning("Google Chrome não encontrado (%s); usando Chromium do projeto — "
                    "o login no ML pode ser recusado", type(e).__name__)
        kwargs.pop("channel", None)
        ctx = pw.chromium.launch_persistent_context(str(PERFIL_DIR), **kwargs)

    # Injeta cookies portáveis de ml_state.json (necessário no Linux/Docker onde DPAPI não existe)
    if STATE_FILE.exists():
        try:
            with open(STATE_FILE, encoding="utf-8") as f:
                dados = json.load(f)
                cookies = dados.get("cookies", [])
                if cookies:
                    ctx.add_cookies(cookies)
        except Exception as e:
            log.warning("Falha ao injetar cookies de %s: %s", STATE_FILE, e)

    return ctx


def _achar_chrome() -> str:
    """Caminho do Google Chrome instalado (Windows, macOS ou Linux)."""
    import shutil
    candidatos: list[str] = []

    if sys.platform == "win32":
        try:
            import winreg
            for hive in (winreg.HKEY_CURRENT_USER, winreg.HKEY_LOCAL_MACHINE):
                try:
                    chave = r"SOFTWARE\Microsoft\Windows\CurrentVersion\App Paths\chrome.exe"
                    with winreg.OpenKey(hive, chave) as k:
                        candidatos.append(winreg.QueryValueEx(k, None)[0])
                except OSError:
                    continue
        except ImportError:
            pass
        for base in (os.environ.get("ProgramFiles", r"C:\Program Files"),
                     os.environ.get("ProgramFiles(x86)", r"C:\Program Files (x86)"),
                     os.environ.get("LOCALAPPDATA", "")):
            if base:
                candidatos.append(str(Path(base) / "Google/Chrome/Application/chrome.exe"))
    elif sys.platform == "darwin":
        candidatos += [
            "/Applications/Google Chrome.app/Contents/MacOS/Google Chrome",
            str(Path.home() / "Applications/Google Chrome.app/Contents/MacOS/Google Chrome"),
            "/Applications/Chromium.app/Contents/MacOS/Chromium",
            "/Applications/Brave Browser.app/Contents/MacOS/Brave Browser",
            "/Applications/Microsoft Edge.app/Contents/MacOS/Microsoft Edge",
        ]
    else:  # Linux e afins
        for nome in ("google-chrome", "google-chrome-stable", "chromium", "chromium-browser",
                     "brave-browser", "microsoft-edge"):
            achado = shutil.which(nome)
            if achado:
                candidatos.append(achado)
        candidatos += ["/usr/bin/google-chrome", "/usr/bin/chromium",
                       "/snap/bin/chromium", "/usr/bin/chromium-browser"]

    for c in candidatos:
        if c and Path(c).exists():
            return c
    raise RuntimeError("Google Chrome não encontrado — instale o Google Chrome e tente de novo.")


def ml_login() -> None:
    """Abre um Chrome comum (SEM automação — indetectável porque não há o que
    detectar) no perfil do bot, para você logar no ML uma única vez."""
    chrome = _achar_chrome()
    PERFIL_DIR.mkdir(parents=True, exist_ok=True)
    print("\n➡️  Vai abrir um Chrome normal com o perfil do bot (separado do seu).")
    print("    1. Faça login no Mercado Livre (senha, 2FA etc.)")
    print("    2. Confira que o Linkbuilder carrega logado")
    print("    3. FECHE o navegador para terminar\n")
    proc = subprocess.Popen([chrome, f"--user-data-dir={PERFIL_DIR}", "--no-first-run",
                             "--no-default-browser-check", URL_LINKBUILDER])
    proc.wait()
    salvar_sessao_json()
    print(f"✅ Perfil salvo em {PERFIL_DIR} e exportado para {STATE_FILE} — o bot usa essa sessão sozinho daqui pra frente.")
    print('   Teste com: uv run python -m ofertas converter "<link de produto do ML>"')


def salvar_sessao_json() -> bool:
    """Extrai os cookies da sessão ativa em PERFIL_DIR e salva em ml_state.json (portável para Linux/Docker)."""
    from playwright.sync_api import sync_playwright
    try:
        with sync_playwright() as pw:
            ctx = _abrir_contexto(pw, headless=True)
            ctx.storage_state(path=str(STATE_FILE))
            ctx.close()
            log.info("Sessão do Mercado Livre exportada para %s", STATE_FILE)
            return True
    except Exception as e:
        log.warning("Não foi possível exportar storage_state do ML: %s", e)
        return False


def _criar_links_api(page, urls: list[str], etiqueta: str) -> list[str]:
    """Chama a API interna do Linkbuilder de dentro da página logada; retorna os short links.

    Payload/resposta observados em 2026-08-21:
    POST createLink {"urls": [...], "tag": "<etiqueta>"} ->
    {"status": 200, "urls": [{"id", "created", "short_url": "https://meli.la/...", ...}]}
    """
    r = page.evaluate(
        """async ({api, urls, tag}) => {
            const resp = await fetch(api, {
                method: 'POST',
                headers: {'content-type': 'application/json'},
                body: JSON.stringify({urls, tag}),
            });
            const corpo = await resp.text();
            try { return {http: resp.status, dados: JSON.parse(corpo)}; }
            catch (e) { return {http: resp.status, texto: corpo.slice(0, 300)}; }
        }""",
        {"api": API_CREATELINK, "urls": urls, "tag": etiqueta},
    )
    if r.get("http") != 200 or not r.get("dados"):
        raise RuntimeError(f"createLink respondeu HTTP {r.get('http')}: {r.get('texto', '')}")
    itens = (r["dados"].get("urls")) or []
    links = [i.get("short_url") or "" for i in itens]
    if len(links) != len(urls) or not all(links):
        raise RuntimeError(f"createLink devolveu {sum(1 for l in links if l)} links "
                           f"para {len(urls)} URLs: {r['dados']}")
    return links


def gerar_links_afiliado(ofertas: list[Oferta]) -> None:
    """Preenche oferta.url_afiliado via API do Linkbuilder (lotes de 10 URLs)."""
    from playwright.sync_api import sync_playwright

    if not tem_sessao():
        raise RuntimeError("Sessão do ML não encontrada — rode: uv run python -m ofertas ml-login")
    if not config.ml_etiqueta:
        raise RuntimeError("ML_ETIQUETA não configurada no .env "
                           "(é a 'Etiqueta em uso' do Linkbuilder no painel de afiliados)")
    pendentes = [o for o in ofertas if not o.url_afiliado and o.url_produto]
    if not pendentes:
        return

    with sync_playwright() as pw:
        ctx = _abrir_contexto(pw, headless=True)
        page = ctx.pages[0] if ctx.pages else ctx.new_page()
        try:
            page.goto(URL_LINKBUILDER, wait_until="domcontentloaded")
            if "login" in page.url or "registration" in page.url:
                raise RuntimeError("Sessão do ML expirou — rode de novo: "
                                   "uv run python -m ofertas ml-login")
            page.wait_for_timeout(1500)  # deixa os scripts de sessão da página rodarem
            for i in range(0, len(pendentes), 10):
                lote = pendentes[i:i + 10]
                links = _criar_links_api(page, [o.url_produto for o in lote], config.ml_etiqueta)
                for o, link in zip(lote, links):
                    o.url_afiliado = link
            log.info("Mercado Livre: %d links de afiliado gerados", len(pendentes))
            try:
                ctx.storage_state(path=str(STATE_FILE))
            except Exception as e:
                log.debug("Erro ao renovar ml_state.json: %s", e)
        finally:
            ctx.close()


def converter(url: str) -> Oferta:
    """Link de produto -> Oferta com dados da página + link de afiliado."""
    url = url.split("#")[0]
    if "meli.la/" in url:  # link de afiliado encurtado: expande até o produto
        try:
            url = sessao().get(url, allow_redirects=True, timeout=20).url.split("#")[0]
        except Exception as e:
            log.warning("Não consegui expandir o link meli.la: %s", e)
    titulo = preco = preco_original = imagem = None
    try:
        r = sessao().get(url, timeout=25)
        soup = BeautifulSoup(r.text, "lxml")
        el = soup.select_one("h1.ui-pdp-title")
        titulo = el.get_text(strip=True) if el else None
        el = soup.select_one('meta[property="og:image"]')
        imagem = el.get("content") if el else None
        el = soup.select_one('meta[itemprop="price"]')
        if el and el.get("content"):
            preco = float(el["content"])
        else:
            el = soup.select_one(".ui-pdp-price__second-line .andes-money-amount__fraction")
            preco = parse_preco_br(el.get_text()) if el else None
        el = soup.select_one("s.andes-money-amount--previous .andes-money-amount__fraction")
        preco_original = parse_preco_br(el.get_text()) if el else None
    except Exception as e:
        log.warning("Não consegui ler a página do produto: %s", e)

    m = _RE_ID.search(url)
    oferta = Oferta(
        plataforma="mercadolivre",
        id_produto=m.group(1).replace("-", "") if m else url.rstrip("/").rsplit("/", 1)[-1][:40],
        titulo=titulo or "Oferta Mercado Livre",
        url_afiliado="",
        url_produto=url.split("?")[0],
        preco=preco,
        preco_original=preco_original,
        imagem=imagem,
    )
    gerar_links_afiliado([oferta])
    if not oferta.url_afiliado:
        raise RuntimeError("Linkbuilder não devolveu o link de afiliado")
    return oferta
