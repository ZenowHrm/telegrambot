import os
import re
import urllib.parse
import requests
import telebot

# 1. Configuración del Token (lo lee de Railway o usa el string de respaldo)
TOKEN = os.getenv("TELEGRAM_TOKEN")
bot = telebot.TeleBot(TOKEN)

# Dominio activo actual de Anna's Archive
BASE_URL = "https://annas-archive.pk"

# 2. Configuración de exclusividad (extraído de tu enlace)
GRUPO_PERMITIDO = "LosConsejosDeHomeroGrupo"
TEMA_PERMITIDO = 65512


def buscar_annas_archive(query, max_resultados=3):
    """Busca en Anna's Archive y devuelve una lista con los enlaces MD5."""
    query_param = urllib.parse.quote(query)
    url_busqueda = f"{BASE_URL}/search?q={query_param}"

    headers = {
        "User-Agent": (
            "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"
            " (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
        )
    }

    try:
        response = requests.get(url_busqueda, headers=headers, timeout=15)
        if response.status_code != 200:
            return None

        # Buscamos todas las coincidencias /md5/ en el HTML
        md5_matches = re.findall(r"/md5/([a-fA-F0-9]{32})", response.text)

        # Eliminamos duplicados manteniendo el orden de relevancia
        md5_unicos = list(dict.fromkeys(md5_matches))

        # Construimos los enlaces web directos
        enlaces = [
            f"{BASE_URL}/md5/{md5}" for md5 in md5_unicos[:max_resultados]
        ]
        return enlaces

    except Exception as e:
        print(f"Error en la búsqueda: {e}")
        return None


@bot.message_handler(commands=["libro"])
def comando_libro(message):
    # --- FILTRO DE SEGURIDAD ---
    # Comprobamos que sea el grupo correcto y el tema correcto (ID 65512)
    chat_username = message.chat.username or ""
    if (
        chat_username.lower() != GRUPO_PERMITIDO.lower()
        or message.message_thread_id != TEMA_PERMITIDO
    ):
        return  # Ignora en silencio si no es en el lugar autorizado
    # ---------------------------

    # Extraemos el texto que viene después de "/libro"
    texto_usuario = message.text.split(maxsplit=1)

    if len(texto_usuario) < 2:
        # Responde citando el mensaje del usuario si faltan datos
        bot.reply_to(
            message,
            "⚠️ Debes indicar un título o autor.\nEjemplo: `/libro El"
            " Principito`",
            parse_mode="Markdown",
        )
        return

    query = texto_usuario[1]

    # Mensaje temporal de espera (siempre citando el mensaje original)
    msg_espera = bot.reply_to(
        message, "🔍 *Buscando en Anna's Archive...*", parse_mode="Markdown"
    )

    enlaces = buscar_annas_archive(query)

    if not enlaces:
        # Usamos chat_id y message_id explícitos para editar el mensaje exacto
        bot.edit_message_text(
            "❌ No se encontraron resultados o el servidor tardó en responder.",
            chat_id=message.chat.id,
            message_id=msg_espera.message_id,
        )
        return

    # Formateamos la respuesta final
    respuesta = f"📖 **Resultados para:** _{query}_\n\n"
    for i, link in enumerate(enlaces, 1):
        respuesta += f"**Opción {i}:**\n🔗 {link}\n\n"

    respuesta += (
        "💡 _Abre cualquier enlace en tu navegador para ver las opciones de"
        " descarga gratuita._"
    )

    # Editamos el mensaje temporal usando chat_id y message_id explícitos
    bot.edit_message_text(
        respuesta,
        chat_id=message.chat.id,
        message_id=msg_espera.message_id,
        parse_mode="Markdown",
        disable_web_page_preview=True,
    )


if __name__ == "__main__":
    print("🤖 Bot iniciado y escuchando comandos...")
    bot.infinity_polling(interval=1, timeout=20)