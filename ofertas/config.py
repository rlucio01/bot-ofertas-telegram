import os
from datetime import datetime
from pathlib import Path

import yaml
from dotenv import load_dotenv

BASE_DIR = Path(__file__).resolve().parent.parent
DATA_DIR = BASE_DIR / "data"
DATA_DIR.mkdir(exist_ok=True)

# Navegador do Playwright fica dentro do projeto: instalações no AppData podem
# não ser visíveis entre sessões diferentes (sandbox). Instale com:
# uv run python -m ofertas instalar-navegador
os.environ.setdefault("PLAYWRIGHT_BROWSERS_PATH", str(DATA_DIR / "pw-browsers"))
PW_BROWSERS_DIR = Path(os.environ["PLAYWRIGHT_BROWSERS_PATH"])

load_dotenv(BASE_DIR / ".env")


def _ler_yaml() -> dict:
    caminho = BASE_DIR / "config.yaml"
    if not caminho.exists():
        return {}
    with open(caminho, encoding="utf-8") as f:
        return yaml.safe_load(f) or {}


class Config:
    def __init__(self):
        y = _ler_yaml()
        geral = y.get("geral") or {}
        filtros = y.get("filtros") or {}

        # .env (segredos)
        self.bot_token: str = os.getenv("TELEGRAM_BOT_TOKEN", "").strip()
        self.chat_id: str = os.getenv("TELEGRAM_CHAT_ID", "").strip()
        self.owner_id: int = int(os.getenv("TELEGRAM_OWNER_ID", "0").strip() or 0)
        self.amazon_tag: str = os.getenv("AMAZON_TAG", "").strip()
        self.amazon_credential_id: str = os.getenv("AMAZON_CREDENTIAL_ID", "").strip()
        self.amazon_credential_secret: str = os.getenv("AMAZON_CREDENTIAL_SECRET", "").strip()
        self.ml_etiqueta: str = os.getenv("ML_ETIQUETA", "").strip()
        self.shopee_app_id: str = os.getenv("SHOPEE_APP_ID", "").strip()
        self.shopee_app_secret: str = os.getenv("SHOPEE_APP_SECRET", "").strip()

        # config.yaml
        self.intervalo_minutos: int = int(geral.get("intervalo_minutos", 45))
        self.max_posts_por_ciclo: int = int(geral.get("max_posts_por_ciclo", 3))
        self.espacamento_segundos: int = int(geral.get("espacamento_segundos", 120))
        self.nao_repetir_dias: int = int(geral.get("nao_repetir_dias", 7))
        self.horario_ativo: str = str(geral.get("horario_ativo") or "").strip()  # "08:00-23:00"; vazio = 24h

        self.desconto_minimo: int = int(filtros.get("desconto_minimo", 0))
        self.preco_minimo: float = float(filtros.get("preco_minimo", 0))
        self.preco_maximo: float = float(filtros.get("preco_maximo", 0))
        self.palavras_bloqueadas: list[str] = [
            str(p).lower() for p in (filtros.get("palavras_bloqueadas") or [])
        ]

        fontes = y.get("fontes") or {}
        self.fonte_ml: dict = fontes.get("mercadolivre") or {"ativa": False}
        self.fonte_shopee: dict = fontes.get("shopee") or {"ativa": False}
        self.fonte_amazon: dict = fontes.get("amazon") or {"ativa": False}

        # Seleção de nichos feita no painel (data/nichos.json). Se houver, ela
        # SUBSTITUI as categorias/departamentos/buscas do config.yaml.
        # Nenhum nicho selecionado = mantém o config.yaml (padrão: todas as categorias).
        self.nichos: list[str] = []
        try:
            from .nichos import expandir, ler_selecao
            self.nichos = ler_selecao()
            if self.nichos:
                exp = expandir(self.nichos)
                self.fonte_ml = {**self.fonte_ml, "categorias": exp["ml"]}
                self.fonte_amazon = {**self.fonte_amazon,
                                     "departamentos": exp["amazon_dep"],
                                     "buscas": exp["amazon_buscas"]}
                self.fonte_shopee = {**self.fonte_shopee, "buscas": exp["shopee"]}
        except Exception:
            pass


config = Config()


def dentro_do_horario(agora: datetime | None = None) -> bool:
    """True se agora está dentro de geral.horario_ativo (aceita janela virando a noite)."""
    if not config.horario_ativo:
        return True
    try:
        inicio, fim = config.horario_ativo.split("-")
        h1, m1 = (int(x) for x in inicio.strip().split(":"))
        h2, m2 = (int(x) for x in fim.strip().split(":"))
    except ValueError:
        return True  # formato inválido: não bloqueia
    agora = agora or datetime.now()
    t, a, b = agora.hour * 60 + agora.minute, h1 * 60 + m1, h2 * 60 + m2
    return a <= t < b if a <= b else (t >= a or t < b)


def verificar() -> list[str]:
    """Retorna a lista do que ainda falta configurar."""
    pendencias = []
    if not config.bot_token:
        pendencias.append("TELEGRAM_BOT_TOKEN (crie o bot no @BotFather)")
    if not config.chat_id:
        pendencias.append("TELEGRAM_CHAT_ID (canal/grupo onde o bot vai postar)")
    if not config.owner_id:
        pendencias.append("TELEGRAM_OWNER_ID (seu user id — mande /id para o bot)")
    if not config.amazon_tag:
        pendencias.append("AMAZON_TAG (tag/Store ID do Amazon Associates)")
    if config.fonte_amazon.get("ativa") and not (config.amazon_credential_id and config.amazon_credential_secret):
        pendencias.append("AMAZON_CREDENTIAL_ID / AMAZON_CREDENTIAL_SECRET (Creators API — busca automática)")
    if not (config.shopee_app_id and config.shopee_app_secret):
        pendencias.append("SHOPEE_APP_ID / SHOPEE_APP_SECRET (painel de afiliados > Open API)")
    if not config.ml_etiqueta:
        pendencias.append("ML_ETIQUETA (a 'Etiqueta em uso' do Linkbuilder do ML)")
    tem_navegador = (
        (PW_BROWSERS_DIR.exists() and bool(list(PW_BROWSERS_DIR.glob("chromium-*"))))
        or (Path("/ms-playwright").exists() and bool(list(Path("/ms-playwright").glob("chromium-*"))))
    )
    if not tem_navegador:
        pendencias.append("Chromium do Playwright (rode: uv run python -m ofertas instalar-navegador)")
    perfil_ml = DATA_DIR / "ml_profile"
    if not (perfil_ml.exists() and any(perfil_ml.iterdir())):
        pendencias.append("Sessão do Mercado Livre (rode: uv run python -m ofertas ml-login)")
    return pendencias
