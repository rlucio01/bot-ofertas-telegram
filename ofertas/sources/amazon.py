"""Amazon: Creators API (busca de ofertas, dados do produto e link de afiliado).

Credenciais: Associates Central > Ferramentas > Creators API > Aplicativos
(Credential ID / Secret). A API exige conta com vendas recentes; enquanto ela
nega acesso (AssociateNotEligible), a busca automática usa scraping das páginas
de busca (SSR) — ofertas por departamento e termos livres — e o conversor usa
link com ?tag= + scraping leve do produto.
Docs: https://affiliate-program.amazon.com/creatorsapi/docs
"""
import logging
import re
import time

import requests
from bs4 import BeautifulSoup

from ..config import DATA_DIR, config
from ..models import Oferta
from ..utils import parse_preco_br, sessao

log = logging.getLogger("ofertas.amazon")

TOKEN_URL = "https://api.amazon.com/auth/o2/token"  # grupo NA (inclui amazon.com.br)
API_BASE = "https://creatorsapi.amazon/catalog/v1/"
MARKETPLACE = "www.amazon.com.br"
RESOURCES = [
    "itemInfo.title",
    "images.primary.large",
    "offersV2.listings.price",
    "offersV2.listings.dealDetails",
    "offersV2.listings.isBuyBoxWinner",
]
# searchIndex da Creators API por departamento (alias usado na busca do site)
SEARCH_INDEX = {"electronics": "Electronics", "computers": "Computers", "videogames": "VideoGames",
                "appliances": "Appliances", "amazon-devices": "AmazonDevices", "kitchen": "Kitchen",
                "office-products": "OfficeProducts", "hi": "HomeImprovement"}

_RE_ASIN = re.compile(r"/(?:dp|gp/product|gp/aw/d)/([A-Z0-9]{10})")
_token = {"valor": None, "expira": 0.0}


def e_link(url: str) -> bool:
    return any(d in url for d in ("amazon.com.br", "amazon.com/", "amzn.to/", "amzn.eu/"))


def tem_api() -> bool:
    return bool(config.amazon_credential_id and config.amazon_credential_secret and config.amazon_tag)


def _departamentos() -> dict[str, str]:
    """{alias: nome} a partir do config (aceita dict ou lista de aliases)."""
    deps = config.fonte_amazon.get("departamentos") or {}
    return dict(deps) if isinstance(deps, dict) else {str(d): str(d) for d in deps}


# ── Creators API ─────────────────────────────────────────────────────

def _access_token() -> str:
    if _token["valor"] and time.time() < _token["expira"] - 60:
        return _token["valor"]
    r = requests.post(TOKEN_URL, json={
        "grant_type": "client_credentials",
        "client_id": config.amazon_credential_id,
        "client_secret": config.amazon_credential_secret,
        "scope": "creatorsapi::default",
    }, timeout=30)
    if r.status_code != 200:
        raise RuntimeError(f"token da Creators API falhou (HTTP {r.status_code}): {r.text[:200]}")
    dados = r.json()
    _token["valor"] = dados["access_token"]
    _token["expira"] = time.time() + int(dados.get("expires_in", 3600))
    return _token["valor"]


def _chamar(operacao: str, corpo: dict) -> list[dict]:
    """POST na Creators API; retorna a lista de itens da resposta."""
    corpo = {"marketplace": MARKETPLACE, "partnerTag": config.amazon_tag,
             "resources": RESOURCES, **corpo}
    headers = {"Authorization": f"Bearer {_access_token()}",
               "Content-Type": "application/json", "x-marketplace": MARKETPLACE}
    r = requests.post(API_BASE + operacao, json=corpo, headers=headers, timeout=30)
    if r.status_code != 200:
        raise RuntimeError(f"Creators API {operacao} HTTP {r.status_code}: {r.text[:300]}")
    dados = r.json()
    if dados.get("errors"):
        log.warning("Creators API %s: %s", operacao, dados["errors"])
    resultado = dados.get("itemsResult") or dados.get("searchResult") or {}
    return resultado.get("items") or []


def _item_para_oferta(item: dict) -> Oferta | None:
    asin = item.get("asin")
    if not asin:
        return None
    titulo = ((item.get("itemInfo") or {}).get("title") or {}).get("displayValue")
    imagem = (((item.get("images") or {}).get("primary") or {}).get("large") or {}).get("url")

    listings = (item.get("offersV2") or {}).get("listings") or []
    listing = next((l for l in listings if l.get("isBuyBoxWinner")), listings[0] if listings else {})
    preco_info = listing.get("price") or {}
    preco = (preco_info.get("money") or {}).get("amount")
    preco_original = ((preco_info.get("savingBasis") or {}).get("money") or {}).get("amount")
    desconto = (preco_info.get("savings") or {}).get("percentage")
    extra = "⚡ Oferta por tempo limitado" if listing.get("dealDetails") else None

    url = item.get("detailPageURL") or f"https://www.amazon.com.br/dp/{asin}"
    if "tag=" not in url:
        url += ("&" if "?" in url else "?") + f"tag={config.amazon_tag}"

    return Oferta(
        plataforma="amazon",
        id_produto=asin,
        titulo=titulo or f"Oferta Amazon ({asin})",
        url_afiliado=url,
        url_produto=f"https://www.amazon.com.br/dp/{asin}",
        preco=float(preco) if preco is not None else None,
        preco_original=float(preco_original) if preco_original is not None else None,
        desconto_pct=int(desconto) if desconto else None,
        imagem=imagem,
        extra=extra,
    )


def _buscar_por_api() -> list[Oferta]:
    """SearchItems com desconto mínimo: termos livres e/ou um termo genérico por departamento."""
    paginas = int(config.fonte_amazon.get("paginas", 1))
    consultas = [(str(t), None) for t in (config.fonte_amazon.get("buscas") or [])]
    consultas += [(nome, SEARCH_INDEX.get(alias)) for alias, nome in _departamentos().items()]
    ofertas: dict[str, Oferta] = {}
    for termo, indice in consultas:
        for pagina in range(1, paginas + 1):
            corpo = {"keywords": termo, "itemCount": 10, "itemPage": pagina,
                     "condition": "New", "sortBy": "Featured"}
            if indice:
                corpo["searchIndex"] = indice
            if config.desconto_minimo:
                corpo["minSavingPercent"] = int(config.desconto_minimo)
            for item in _chamar("searchItems", corpo):
                o = _item_para_oferta(item)
                if o:
                    ofertas[o.id_produto] = o
    return list(ofertas.values())


# ── Scraping das páginas de busca (enquanto a Creators API não libera) ──

URL_BUSCA = "https://www.amazon.com.br/s"
# Refinamento "tipo de oferta" da busca da Amazon BR (ids vistos na página de departamento):
# filtra a listagem para itens em promoção. Sondagem 2026-08-22 (computers): os dois primeiros
# vieram 24/24 com desconto, o terceiro 17/24; 210771958011 veio fraco (9/24) e ficou de fora.
DEAL_TYPES = ["23565492011", "23565493011", "210771957011"]
_sessao_amz: requests.Session | None = None
_rodizio = 0


def _sessao() -> requests.Session:
    global _sessao_amz
    if _sessao_amz is None:
        _sessao_amz = sessao()  # cookies persistem entre ciclos: menos cara de robô
    return _sessao_amz


def _bloqueado(html: str) -> bool:
    inicio = html[:5000].lower()
    if any(s in inicio for s in ("captcha", "robot check", "api-services-support@amazon.com")):
        return True
    # página-interstício de bloqueio leve: título vazio (&nbsp;) e sem resultados
    m = re.search(r"<title>(.*?)</title>", html[:3000], re.S)
    titulo = re.sub(r"&nbsp;|\s", "", m.group(1)) if m else "x"
    return not titulo and 's-search-result' not in html[:60000]


def _imagem_grande(src: str | None) -> str | None:
    # ".../51MFNq3409L._AC_UL320_.jpg" -> ".../51MFNq3409L.jpg" (tamanho original)
    return re.sub(r"\._[^./]+_\.", ".", src) if src else None


def _card_para_oferta(card) -> Oferta | None:
    asin = card.get("data-asin")
    link = card.select_one("a.a-link-normal.s-no-outline, h2 a, a.s-line-clamp-2")
    if not asin or (link and "/sspa/" in (link.get("href") or "")):
        return None  # sem ASIN ou patrocinado
    h2 = card.select_one("h2")
    titulo = h2.get_text(" ", strip=True) if h2 else ""
    if not titulo:
        return None

    el = card.select_one(".a-price:not(.a-text-price) .a-offscreen")
    preco = parse_preco_br(el.get_text()) if el else None
    el = card.select_one('.a-price.a-text-price[data-a-strike="true"] .a-offscreen')
    preco_original = parse_preco_br(el.get_text()) if el else None
    if preco is None or (preco_original is not None and preco_original <= preco):
        preco_original = None  # sem preço atual, ou "riscado" que não é desconto de verdade

    partes = []
    el = card.select_one("span.a-icon-alt")
    if el:
        m = re.match(r"([\d,]+)", el.get_text(strip=True))
        if m:
            partes.append(f"⭐ {m.group(1)}")
    texto = card.get_text(" ", strip=True)
    if card.select_one("i.a-icon-prime"):
        partes.append("Prime")
    for rotulo, selo in (("Mais vendido", "🏆 Mais vendido"), ("Escolha da Amazon", "✔️ Escolha da Amazon"),
                         ("Oferta Relâmpago", "⚡ Oferta Relâmpago")):
        if rotulo in texto:
            partes.append(selo)
    m = re.search(r"Cupom de (R\$\s?[\d.,]+|\d+%)", texto)
    if m:
        partes.append(f"🎟 Cupom de {m.group(1)}")

    img = card.select_one("img.s-image")
    return Oferta(
        plataforma="amazon",
        id_produto=asin,
        titulo=titulo,
        url_afiliado=f"https://www.amazon.com.br/dp/{asin}?tag={config.amazon_tag}",
        url_produto=f"https://www.amazon.com.br/dp/{asin}",
        preco=preco,
        preco_original=preco_original,
        imagem=_imagem_grande(img.get("src")) if img else None,
        extra=" · ".join(partes) or None,
    )


def _parse_busca(html: str, rotulo: str) -> list[Oferta]:
    soup = BeautifulSoup(html, "lxml")
    cards = soup.select('div[data-component-type="s-search-result"]')
    ofertas = [o for o in (_card_para_oferta(c) for c in cards) if o]
    if not ofertas:
        # guarda a página para diagnóstico: o que a Amazon mandou em vez dos resultados?
        arq = DATA_DIR / "debug_amazon_busca.html"
        arq.write_text(html, encoding="utf-8")
        m = re.search(r"<title>(.*?)</title>", html, re.S)
        log.warning("Amazon %s: %d cards, 0 ofertas (título: %s) — HTML salvo em %s",
                    rotulo, len(cards), (m.group(1).strip()[:80] if m else "?"), arq.name)
    return ofertas


def _tarefas() -> list[dict]:
    """Uma tarefa = uma página de busca: ofertas por departamento e/ou termos livres.

    Sem departamentos nem termos configurados = ofertas de TODAS as categorias
    (i=aps, todos os produtos), que é o padrão do pacote distribuído.
    """
    tarefas = []
    for alias, nome in _departamentos().items():
        for n, deal in enumerate(DEAL_TYPES, 1):
            tarefas.append({"rotulo": f"ofertas de {nome} ({n}/{len(DEAL_TYPES)})",
                            "params": {"i": alias, "rh": f"p_n_deal_type:{deal}"}})
    for termo in (config.fonte_amazon.get("buscas") or []):
        tarefas.append({"rotulo": f"busca '{termo}'", "params": {"k": str(termo)}})
    if not tarefas:
        for n, deal in enumerate(DEAL_TYPES, 1):
            tarefas.append({"rotulo": f"ofertas gerais ({n}/{len(DEAL_TYPES)})",
                            "params": {"i": "aps", "rh": f"p_n_deal_type:{deal}"}})
    return tarefas


def _tarefas_do_ciclo() -> list[dict]:
    """Rodízio: só algumas páginas por ciclo, para não martelar a Amazon."""
    global _rodizio
    tarefas = _tarefas()
    por_ciclo = int(config.fonte_amazon.get("requisicoes_por_ciclo", 0)) or len(tarefas)
    if not tarefas or por_ciclo >= len(tarefas):
        return tarefas
    inicio = _rodizio % len(tarefas)
    _rodizio += por_ciclo
    return (tarefas + tarefas)[inicio:inicio + por_ciclo]


def _buscar_por_scraping(tarefas: list[dict]) -> list[Oferta]:
    paginas = int(config.fonte_amazon.get("paginas", 1))
    s = _sessao()
    ofertas: dict[str, Oferta] = {}
    for tarefa in tarefas:
        for pagina in range(1, paginas + 1):
            params = dict(tarefa["params"])
            if pagina > 1:
                params["page"] = pagina
            achadas: list[Oferta] = []
            for tentativa in (1, 2):
                try:
                    r = s.get(URL_BUSCA, params=params, timeout=30)
                except Exception as e:
                    log.error("Amazon %s: %s", tarefa["rotulo"], e)
                    return list(ofertas.values())
                if r.status_code != 200 or _bloqueado(r.text):
                    log.warning("Amazon bloqueou a busca (HTTP %s) — parando este ciclo", r.status_code)
                    return list(ofertas.values())
                achadas = _parse_busca(r.text, tarefa["rotulo"])
                if achadas or tentativa == 2:
                    break
                time.sleep(6)  # página veio sem resultados: respira e tenta mais uma vez
            for o in achadas:
                ofertas[o.id_produto] = o
            log.info("Amazon %s: %d itens", tarefa["rotulo"], len(achadas))
            time.sleep(3)  # educação com o servidor
    return list(ofertas.values())


_api_bloqueada_ate = 0.0


def buscar_ofertas() -> list[Oferta]:
    """Creators API quando disponível; senão scraping das buscas. Troca sozinho."""
    global _api_bloqueada_ate
    if tem_api() and time.time() >= _api_bloqueada_ate:
        try:
            ofertas = _buscar_por_api()
            log.info("Amazon (Creators API): %d ofertas", len(ofertas))
            return ofertas
        except Exception as e:
            if "AssociateNotEligible" in str(e):
                _api_bloqueada_ate = time.time() + 6 * 3600
                log.warning("Amazon: conta ainda não elegível para a Creators API — "
                            "usando scraping das buscas (tento a API de novo em 6h)")
            else:
                log.error("Amazon (Creators API): %s — usando scraping", e)
    tarefas = _tarefas_do_ciclo()
    ofertas = _buscar_por_scraping(tarefas)
    log.info("Amazon (scraping): %d ofertas em %d página(s): %s",
             len(ofertas), len(tarefas), ", ".join(t["rotulo"] for t in tarefas))
    return ofertas


# ── Conversor de link ────────────────────────────────────────────────

def _expandir(url: str) -> str:
    if "amzn.to/" in url or "amzn.eu/" in url:
        try:
            return sessao().get(url, allow_redirects=True, timeout=20).url
        except Exception as e:
            log.warning("Não consegui expandir o link curto: %s", e)
    return url


def converter(url: str) -> Oferta:
    """Link de produto -> Oferta com link de afiliado (Creators API; fallback ?tag=)."""
    if not config.amazon_tag:
        raise RuntimeError("AMAZON_TAG não configurada no .env")
    url = _expandir(url)
    m = _RE_ASIN.search(url)
    if not m:
        raise ValueError("Não encontrei o ASIN nesse link da Amazon")
    asin = m.group(1)

    if tem_api() and time.time() >= _api_bloqueada_ate:
        try:
            itens = _chamar("getItems", {"itemIds": [asin], "itemIdType": "ASIN"})
            oferta = _item_para_oferta(itens[0]) if itens else None
            if oferta:
                return oferta
            log.warning("Creators API não retornou o ASIN %s; usando fallback", asin)
        except Exception as e:
            motivo = "conta ainda não elegível" if "AssociateNotEligible" in str(e) else str(e)
            log.warning("Creators API indisponível (%s); usando link com tag", motivo)

    titulo, preco, preco_original, imagem = _detalhes(f"https://www.amazon.com.br/dp/{asin}")
    return Oferta(
        plataforma="amazon",
        id_produto=asin,
        titulo=titulo or f"Oferta Amazon ({asin})",
        url_afiliado=f"https://www.amazon.com.br/dp/{asin}?tag={config.amazon_tag}",
        url_produto=url,
        preco=preco,
        preco_original=preco_original,
        imagem=imagem,
    )


def _detalhes(url: str):
    """Scraping leve da página do produto; se a Amazon bloquear, segue sem os dados."""
    try:
        r = _sessao().get(url, timeout=25)
        if r.status_code != 200 or "captcha" in r.text[:3000].lower():
            log.warning("Amazon não liberou a página (%s) — postando sem título/preço", r.status_code)
            return None, None, None, None
        soup = BeautifulSoup(r.text, "lxml")

        el = soup.select_one("#productTitle")
        titulo = el.get_text(strip=True) if el else None

        el = soup.select_one("#corePriceDisplay_desktop_feature_div .a-price .a-offscreen, .a-price .a-offscreen")
        preco = parse_preco_br(el.get_text()) if el else None

        el = soup.select_one(".basisPrice .a-offscreen, span[data-a-strike='true'] .a-offscreen")
        preco_original = parse_preco_br(el.get_text()) if el else None

        el = soup.select_one("#landingImage")
        imagem = (el.get("data-old-hires") or el.get("src")) if el else None

        return titulo, preco, preco_original, imagem
    except Exception as e:
        log.warning("Falha ao ler detalhes na Amazon: %s", e)
        return None, None, None, None
