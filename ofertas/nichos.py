"""Catálogo de nichos para o seletor de categorias do painel.

Cada nicho mapeia, de uma vez, as categorias equivalentes nas três plataformas:
- Mercado Livre: IDs de categoria (ofertas?category=MLB...), validados ao vivo
- Amazon: aliases de departamento (s?i=<alias>) e/ou termos de busca
- Shopee: palavras-chave (a Open API busca por keyword)

A seleção do usuário fica em data/nichos.json (lista de chaves). Nenhum nicho
marcado = todas as categorias (comportamento padrão).
"""
import json

from .config import DATA_DIR

ARQ_SELECAO = DATA_DIR / "nichos.json"

# chave -> {emoji, nome, ml{id:nome}, amazon_dep{alias:nome}, amazon_buscas[], shopee[]}
NICHOS: dict[str, dict] = {
    "tecnologia": {
        "emoji": "💻", "nome": "Tecnologia e Eletrônicos",
        "ml": {"MLB1648": "Informática", "MLB1000": "Eletrônicos, Áudio e Vídeo"},
        "amazon_dep": {"electronics": "Eletrônicos", "computers": "Informática",
                       "amazon-devices": "Dispositivos Amazon"},
        "shopee": ["fone bluetooth", "smartwatch", "mouse gamer", "ssd", "carregador turbo"],
    },
    "celulares": {
        "emoji": "📱", "nome": "Celulares e Acessórios",
        "ml": {"MLB1051": "Celulares e Telefones"},
        "amazon_buscas": ["celular", "smartphone", "capa celular"],
        "shopee": ["capa celular", "power bank", "carregador", "película"],
    },
    "games": {
        "emoji": "🎮", "nome": "Games",
        "ml": {"MLB1144": "Games"},
        "amazon_dep": {"videogames": "Games"},
        "shopee": ["controle", "headset gamer", "teclado mecânico"],
    },
    "casa": {
        "emoji": "🏠", "nome": "Casa e Cozinha",
        "ml": {"MLB1574": "Casa, Móveis e Decoração"},
        "amazon_dep": {"home": "Casa", "kitchen": "Cozinha", "furniture": "Móveis"},
        "shopee": ["organizador", "panela", "utensílios de cozinha"],
    },
    "eletrodomesticos": {
        "emoji": "🔌", "nome": "Eletrodomésticos",
        "ml": {"MLB5726": "Eletrodomésticos"},
        "amazon_dep": {"appliances": "Eletrodomésticos"},
        "shopee": ["air fryer", "liquidificador", "aspirador de pó"],
    },
    "moda": {
        "emoji": "👗", "nome": "Moda e Acessórios",
        "ml": {"MLB1430": "Calçados, Roupas e Bolsas"},
        "amazon_dep": {"fashion": "Moda", "fashion-luggage": "Bolsas e Malas"},
        "shopee": ["tênis", "camiseta", "relógio", "mochila"],
    },
    "beleza": {
        "emoji": "💄", "nome": "Beleza e Cuidados",
        "ml": {"MLB1246": "Beleza e Cuidado Pessoal"},
        "amazon_dep": {"beauty": "Beleza", "luxury-beauty": "Beleza de Luxo"},
        "shopee": ["maquiagem", "perfume", "skincare"],
    },
    "esporte": {
        "emoji": "💪", "nome": "Esporte e Fitness",
        "ml": {"MLB1276": "Esportes e Fitness"},
        "amazon_dep": {"sporting": "Esportes"},
        "shopee": ["suplemento", "roupa academia", "garrafa térmica"],
    },
    "saude": {
        "emoji": "🩺", "nome": "Saúde e Bem-estar",
        "ml": {"MLB264586": "Saúde"},
        "amazon_buscas": ["vitamina", "suplemento"],
        "shopee": ["vitamina", "creatina", "massageador"],
    },
    "brinquedos": {
        "emoji": "🧸", "nome": "Brinquedos e Bebês",
        "ml": {"MLB1132": "Brinquedos e Hobbies"},
        "amazon_dep": {"toys": "Brinquedos", "baby": "Bebês"},
        "shopee": ["brinquedo", "lego", "fralda"],
    },
    "pet": {
        "emoji": "🐶", "nome": "Pet",
        "ml": {"MLB1071": "Animais"},
        "amazon_dep": {"pets": "Pet Shop"},
        "shopee": ["ração", "brinquedo pet", "coleira"],
    },
    "automotivo": {
        "emoji": "🚗", "nome": "Automotivo",
        "ml": {"MLB5672": "Acessórios para Veículos"},
        "amazon_dep": {"automotive": "Automotivo"},
        "shopee": ["acessório carro", "suporte veicular", "capacete"],
    },
    "livros": {
        "emoji": "📚", "nome": "Livros",
        "ml": {"MLB1196": "Livros, Revistas e Comics"},
        "amazon_dep": {"stripbooks": "Livros"},
        "shopee": ["livro"],
    },
}


def catalogo() -> list[dict]:
    """Lista para o painel: [{chave, emoji, nome}]."""
    return [{"chave": k, "emoji": v["emoji"], "nome": v["nome"]} for k, v in NICHOS.items()]


def ler_selecao() -> list[str]:
    """Chaves de nicho escolhidas no painel (data/nichos.json)."""
    if not ARQ_SELECAO.exists():
        return []
    try:
        dados = json.loads(ARQ_SELECAO.read_text(encoding="utf-8"))
        return [c for c in dados if c in NICHOS]
    except (ValueError, TypeError):
        return []


def salvar_selecao(chaves: list[str]) -> None:
    validas = [c for c in chaves if c in NICHOS]
    ARQ_SELECAO.write_text(json.dumps(validas), encoding="utf-8")


def expandir(chaves: list[str]) -> dict:
    """Junta os nichos escolhidos nas listas que cada fonte entende."""
    ml: dict[str, str] = {}
    amazon_dep: dict[str, str] = {}
    amazon_buscas: list[str] = []
    shopee: list[str] = []
    for k in chaves:
        n = NICHOS.get(k)
        if not n:
            continue
        ml.update(n.get("ml", {}))
        amazon_dep.update(n.get("amazon_dep", {}))
        for kw in n.get("amazon_buscas", []):
            if kw not in amazon_buscas:
                amazon_buscas.append(kw)
        for kw in n.get("shopee", []):
            if kw not in shopee:
                shopee.append(kw)
    return {"ml": ml, "amazon_dep": amazon_dep, "amazon_buscas": amazon_buscas, "shopee": shopee}
