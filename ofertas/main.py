import argparse
import asyncio
import logging
import sys


def _log():
    logging.basicConfig(level=logging.INFO,
                        format="%(asctime)s %(levelname)s %(name)s: %(message)s")
    logging.getLogger("httpx").setLevel(logging.WARNING)


def cmd_check(_):
    from .config import config, verificar
    pendencias = verificar()
    print("── Checagem da configuração ──")
    if config.bot_token:
        print("✅ Token do bot")
    if config.chat_id:
        print(f"✅ Canal/grupo: {config.chat_id}")
    if config.owner_id:
        print(f"✅ Owner id: {config.owner_id}")
    if config.amazon_tag:
        print(f"✅ Amazon tag: {config.amazon_tag}")
    if config.shopee_app_id and config.shopee_app_secret:
        print("✅ Credenciais Shopee")
    from .sources import mercadolivre
    if mercadolivre.tem_sessao():
        print("✅ Sessão do Mercado Livre")
    for p in pendencias:
        print(f"⚠️  Falta: {p}")
    if not pendencias:
        print("\n🎉 Tudo pronto! Rode: uv run python -m ofertas run")


def cmd_run(_):
    from .bot_interativo import rodar
    rodar()


def cmd_ciclo(_):
    from telegram import Bot
    from . import pipeline
    from .config import config
    if not (config.bot_token and config.chat_id):
        raise SystemExit("Configure TELEGRAM_BOT_TOKEN e TELEGRAM_CHAT_ID antes.")

    async def go():
        bot = Bot(config.bot_token)
        async with bot:
            await pipeline.executar_ciclo(bot)

    asyncio.run(go())


def _converter(url: str):
    from .sources import detectar_fonte
    fonte = detectar_fonte(url)
    if not fonte:
        raise SystemExit("Link não reconhecido (esperado: Mercado Livre, Shopee ou Amazon).")
    return fonte.converter(url)


def cmd_converter(args):
    o = _converter(args.url)
    print(f"Plataforma:  {o.plataforma}")
    print(f"Título:      {o.titulo}")
    print(f"Preço:       {o.preco}  (de {o.preco_original})  -{o.desconto or 0}%")
    print(f"Imagem:      {o.imagem}")
    print(f"Link afiliado: {o.url_afiliado}")


def cmd_postar(args):
    from telegram import Bot
    from . import db
    from .config import config
    from .telegram_poster import postar_oferta
    if not (config.bot_token and config.chat_id):
        raise SystemExit("Configure TELEGRAM_BOT_TOKEN e TELEGRAM_CHAT_ID antes.")
    o = _converter(args.url)

    async def go():
        bot = Bot(config.bot_token)
        async with bot:
            await postar_oferta(bot, o, config.chat_id)
        db.registrar(o)
        print(f"✅ Postada: {o.titulo[:60]}")

    asyncio.run(go())


def cmd_painel(_):
    from .painel import painel
    painel()


def cmd_instalar_navegador(_):
    import subprocess
    from . import config  # noqa: F401 — define PLAYWRIGHT_BROWSERS_PATH (data/pw-browsers)
    r = subprocess.run([sys.executable, "-m", "playwright", "install", "chromium"])
    if r.returncode == 0:
        print("✅ Chromium instalado em data\\pw-browsers")
    raise SystemExit(r.returncode)


def cmd_ml_login(_):
    from .sources import mercadolivre
    mercadolivre.ml_login()


def cmd_testar(args):
    if args.fonte == "ml":
        from .sources import mercadolivre
        ofertas = mercadolivre.buscar_ofertas()
    elif args.fonte == "shopee":
        from .sources import shopee
        ofertas = shopee.buscar_ofertas(10)
    elif args.fonte == "amazon":
        from .sources import amazon
        from .config import config
        if not config.amazon_tag:
            raise SystemExit("Preencha AMAZON_TAG no .env")
        ofertas = amazon.buscar_ofertas()
    else:
        raise SystemExit("Fontes testáveis: ml, shopee, amazon")
    ofertas.sort(key=lambda o: o.desconto or 0, reverse=True)
    for o in ofertas[:10]:
        print(f"[-{o.desconto or 0:>2}%] R$ {o.preco} (de {o.preco_original}) — "
              f"{o.titulo[:60]}")
        if o.extra:
            print(f"       {o.extra}")
    print(f"\nTotal: {len(ofertas)} ofertas")


def main():
    try:
        sys.stdout.reconfigure(encoding="utf-8")
    except Exception:
        pass
    _log()

    p = argparse.ArgumentParser(prog="ofertas",
                                description="Bot de ofertas para Telegram com links de afiliado")
    sub = p.add_subparsers(dest="cmd", required=True)

    sub.add_parser("painel", help="abre o painel de controle gráfico no navegador").set_defaults(fn=cmd_painel)
    sub.add_parser("check", help="mostra o que falta configurar").set_defaults(fn=cmd_check)
    sub.add_parser("run", help="roda o bot (conversor no privado + ciclos automáticos)").set_defaults(fn=cmd_run)
    sub.add_parser("ciclo", help="roda um único ciclo de busca e postagem").set_defaults(fn=cmd_ciclo)

    pc = sub.add_parser("converter", help="converte um link e mostra o resultado (não posta)")
    pc.add_argument("url")
    pc.set_defaults(fn=cmd_converter)

    pp = sub.add_parser("postar", help="converte um link e posta no canal")
    pp.add_argument("url")
    pp.set_defaults(fn=cmd_postar)

    sub.add_parser("instalar-navegador", help="baixa o Chromium usado pelo Linkbuilder (fica em data/)").set_defaults(fn=cmd_instalar_navegador)
    sub.add_parser("ml-login", help="login único no Mercado Livre (salva a sessão)").set_defaults(fn=cmd_ml_login)

    pt = sub.add_parser("testar", help="testa uma fonte sem postar nada")
    pt.add_argument("fonte", choices=["ml", "shopee", "amazon"])
    pt.set_defaults(fn=cmd_testar)

    args = p.parse_args()
    args.fn(args)
