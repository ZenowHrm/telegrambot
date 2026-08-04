import re
import urllib.parse
from bs4 import BeautifulSoup
import requests
import telebot

# 1. Coloca aquí el token que te dio @BotFather
TOKEN = "8931648780:AAHeLvlk6HJQA2OkXFeZxSISKDv4fH_FSZ0"
bot = telebot.TeleBot(TOKEN)

# Dominio activo actual de Anna's Archive (puedes cambiarlo si migran a .se, .li, etc.)
BASE_URL = "https://annas-archive.gl"


def buscar_annas_archive(query, max_resultados=3):
    query_param = urllib.parse.quote(query)
    url_busqueda = f"{BASE_URL}/search?q={query_param}"

    headers = {
        "User-Agent": (
            "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"
            " (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
        )
    }

    try:
        # Petición directa SIN parámetro proxies
        response = requests.get(url_busqueda, headers=headers, timeout=15)
        if response.status_code != 200:
            return None

        md5_matches = re.findall(r"/md5/([a-fA-F0-9]{32})", response.text)
        md5_unicos = list(dict.fromkeys(md5_matches))

        enlaces = [
            f"{BASE_URL}/md5/{md5}" for md5 in md5_unicos[:max_resultados]
        ]
        return enlaces

    except Exception as e:
        print(f"Error en la búsqueda: {e}")
        return None


@bot.message_handler(commands=["start", "help"])
def send_welcome(message):
    texto = (
        "¡Hola! 📚 Puedes buscar libros escribiendo:\n\n"
        "`/libro <título y/o autor>`\n\n"
        "**Ejemplo:**\n"
        "`/libro El Principito Antoine de Saint-Exupéry`"
    )
    bot.reply_to(message, texto, parse_mode="Markdown")


@bot.message_handler(commands=["libro"])
def comando_libro(message):
    # Extraemos el texto que viene después de "/libro "
    texto_usuario = message.text.split(maxsplit=1)

    if len(texto_usuario) < 2:
        bot.reply_to(
            message,
            "⚠️ Debes indicar un título o autor.\nEjemplo: `/libro El Principito`",
            parse_mode="Markdown",
        )
        return

    query = texto_usuario[1]

    # Mensaje temporal de espera
    msg_espera = bot.reply_to(
        message, "🔍 *Buscando en Anna's Archive...*", parse_mode="Markdown"
    )

    enlaces = buscar_annas_archive(query)

    if not enlaces:
        bot.edit_message_text(
            "❌ No se encontraron resultados o el servidor tardó en responder.",
            chat_id=message.chat.id,
            message_id=msg_espera.message_id,
        )
        return

    # Formateamos la respuesta con los mejores enlaces
    respuesta = f"📖 **Resultados para:** _{query}_\n\n"
    for i, link in enumerate(enlaces, 1):
        respuesta += f"**Opción {i}:**\n🔗 {link}\n\n"

    respuesta += (
        "💡 _Abre cualquier enlace en tu navegador para ver las opciones de"
        " descarga gratuita._"
    )

    # Reemplazamos el mensaje de "Buscando..." por la respuesta final
    bot.edit_message_text(
        respuesta,
        chat_id=message.chat.id,
        message_id=msg_espera.message_id,
        parse_mode="Markdown",
        disable_web_page_preview=True,  # Evita que se llene de vistas previas gigantes
    )


if __name__ == "__main__":
    print("🤖 Bot iniciado y escuchando comandos...")
    # interval=3 evita saturación y non_stop=True hace que no se detenga si hay un corte de red leve
    bot.infinity_polling(interval=1, timeout=20)