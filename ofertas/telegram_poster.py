import logging

from telegram import Bot, InlineKeyboardButton, InlineKeyboardMarkup, Message
from telegram.constants import ParseMode

from .formatter import montar_caption
from .models import Oferta

log = logging.getLogger("ofertas.poster")


def teclado_oferta(o: Oferta) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup([[InlineKeyboardButton("🛒 Pegar oferta", url=o.url_afiliado)]])


async def postar_oferta(bot: Bot, oferta: Oferta, chat_id: str | int,
                        teclado: InlineKeyboardMarkup | None = None) -> Message:
    caption = montar_caption(oferta)
    markup = teclado or teclado_oferta(oferta)
    if oferta.imagem:
        try:
            return await bot.send_photo(chat_id, oferta.imagem, caption=caption,
                                        parse_mode=ParseMode.HTML, reply_markup=markup)
        except Exception as e:  # imagem recusada pelo Telegram -> cai para texto
            log.warning("send_photo falhou (%s), enviando como texto", e)
    return await bot.send_message(chat_id, caption, parse_mode=ParseMode.HTML,
                                  reply_markup=markup, disable_web_page_preview=True)
