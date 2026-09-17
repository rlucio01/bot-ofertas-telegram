"""Shopee: busca de ofertas e geração de link de afiliado via Open API oficial.

Credenciais (AppId/Secret) ficam no painel de afiliados > Open API
(https://affiliate.shopee.com.br). O offerLink retornado já é o seu link
de afiliado, com comissão atrelada.
"""
import hashlib
import json
import logging
import re
import time

import requests

from ..config import config
from ..models import Oferta
from ..utils import sessao

log = logging.getLogger("ofertas.shopee")

ENDPOINT = "https://open-api.affiliate.shopee.com.br/graphql"

# sortType do productOfferV2 (conferir docs no painel): 1=relevância, 2=mais vendidos,
# 3=preço crescente, 4=preço decrescente, 5=maior comissão
SORT_TYPE = 2


def e_link(url: str) -> bool:
    return any(d in url for d in ("shopee.com.br", "s.shopee.", "shp.ee/"))


def _chamar(query: str) -> dict:
    if not (config.shopee_app_id and config.shopee_app_secret):
        raise RuntimeError("Configure SHOPEE_APP_ID e SHOPEE_APP_SECRET no .env "
                           "(painel de afiliados > Open API)")
    payload = json.dumps({"query": query}, separators=(",", ":"))
    ts = str(int(time.time()))
    fator = config.shopee_app_id + ts + payload + config.shopee_app_secret
    assinatura = hashlib.sha256(fator.encode()).hexdigest()
    headers = {
        "Content-Type": "application/json",
        "Authorization": (f"SHA256 Credential={config.shopee_app_id}, "
                          f"Timestamp={ts}, Signature={assinatura}"),
    }
    r = requests.post(ENDPOINT, data=payload, headers=headers, timeout=30)
    r.raise_for_status()
    dados = r.json()
    if dados.get("errors"):
        raise RuntimeError(f"Shopee API: {dados['errors']}")
    return dados.get("data") or {}


_CAMPOS = ("itemId productName priceMin priceMax priceDiscountRate imageUrl "
           "offerLink productLink sales ratingStar shopName")


def _node_para_oferta(n: dict) -> Oferta:
    preco = float(n.get("priceMin") or 0) or None
    desconto = int(n.get("priceDiscountRate") or 0) or None
    preco_original = None
    if preco and desconto and desconto < 100:
        preco_original = round(preco / (1 - desconto / 100), 2)

    partes = []
    if n.get("ratingStar"):
        try:
            partes.append(f"⭐ {float(n['ratingStar']):.1f}")
        except (TypeError, ValueError):
            pass
    if n.get("sales"):
        partes.append(f"{n['sales']} vendidos")

    return Oferta(
        plataforma="shopee",
        id_produto=str(n.get("itemId")),
        titulo=n.get("productName") or "",
        url_afiliado=n.get("offerLink") or "",
        url_produto=n.get("productLink") or "",
        preco=preco,
        preco_original=preco_original,
        desconto_pct=desconto,
        imagem=n.get("imageUrl"),
        extra=" · ".join(partes) or None,
    )


def _buscar_keyword(termo: str, limite: int) -> list[Oferta]:
    query = (f'{{productOfferV2(keyword:"{termo}",sortType:{SORT_TYPE},page:1,limit:{limite})'
             f"{{nodes{{{_CAMPOS}}}}}}}")
    data = _chamar(query)
    nodes = (data.get("productOfferV2") or {}).get("nodes") or []
    return [_node_para_oferta(n) for n in nodes]


def buscar_ofertas(limite: int = 30) -> list[Oferta]:
    """Busca ofertas por palavras-chave tech (config.yaml: fontes.shopee.buscas).

    listType:1 do productOfferV2 vem SEMPRE vazio (verificado 2026-08-29); por isso
    usamos busca por keyword, que também mantém o foco tech do canal.
    """
    termos = config.fonte_shopee.get("buscas") or []
    if not termos:
        # sem termos configurados: cai na lista geral de destaque (listType:0)
        query = (f"{{productOfferV2(listType:0,sortType:{SORT_TYPE},page:1,limit:{limite})"
                 f"{{nodes{{{_CAMPOS}}}}}}}")
        nodes = (_chamar(query).get("productOfferV2") or {}).get("nodes") or []
        ofertas = [_node_para_oferta(n) for n in nodes]
        log.info("Shopee (destaque): %d ofertas", len(ofertas))
        return ofertas

    por_termo = max(5, limite // len(termos))
    ofertas: dict[str, Oferta] = {}
    for termo in termos:
        try:
            for o in _buscar_keyword(str(termo), por_termo):
                ofertas[o.id_produto] = o
        except Exception as e:
            log.error("Shopee '%s': %s", termo, e)
    log.info("Shopee: %d ofertas em %d termo(s)", len(ofertas), len(termos))
    return list(ofertas.values())


_RE_IDS = re.compile(r"-?i\.(\d+)\.(\d+)|/product/(\d+)/(\d+)")


def converter(url: str) -> Oferta:
    """Link de produto/short link -> Oferta com link de afiliado."""
    if "s.shopee." in url or "shp.ee/" in url:
        try:
            url = sessao().get(url, allow_redirects=True, timeout=20).url
        except Exception as e:
            log.warning("Não consegui expandir o link curto da Shopee: %s", e)

    m = _RE_IDS.search(url)
    item_id = (m.group(2) or m.group(4)) if m else None

    if item_id:
        data = _chamar(f"{{productOfferV2(itemId:{item_id}){{nodes{{{_CAMPOS}}}}}}}")
        nodes = (data.get("productOfferV2") or {}).get("nodes") or []
        if nodes:
            return _node_para_oferta(nodes[0])

    # produto fora do catálogo de ofertas: gera só o short link de afiliado
    origin = json.dumps(url.split("?")[0])
    data = _chamar(f'mutation{{generateShortLink(input:{{originUrl:{origin},'
                   f'subIds:["telegram"]}}){{shortLink}}}}')
    short = (data.get("generateShortLink") or {}).get("shortLink")
    if not short:
        raise RuntimeError("Shopee não retornou o short link")
    return Oferta(
        plataforma="shopee",
        id_produto=item_id or url.split("?")[0].rstrip("/").rsplit("/", 1)[-1][:60],
        titulo="Oferta Shopee",
        url_afiliado=short,
        url_produto=url,
    )
