import math
import os
import re
import sys
import urllib.parse
import uuid
import cloudscraper
import telebot
from telebot import types

# 1. Configuración del Token
TOKEN = os.getenv("TELEGRAM_TOKEN", "TU_TOKEN_DE_BOTFATHER_AQUI")
bot = telebot.TeleBot(TOKEN)

# 2. Lista de espejos oficiales de Anna's Archive (rota si alguno falla o está bloqueado)
DOMINIOS_ANNAS = [
    "https://annas-archive.gl",
    "https://annas-archive.pk",
    "https://annas-archive.gd",
]

# 3. Configuración de exclusividad del Grupo/Tema
GRUPO_PERMITIDO = "LosConsejosDeHomeroGrupo"
TEMA_PERMITIDO = 65512

# Caché temporal en memoria
cache_busquedas = {}


def log(mensaje):
    """Imprime en la consola de Railway instantáneamente sin buffering."""
    print(mensaje, flush=True)


def buscar_annas_archive(query, max_resultados=48):
    """Busca en Anna's Archive probando espejos y saltando Cloudflare con cloudscraper."""
    query_param = urllib.parse.quote(query)

    # Creamos el scraper simulando un navegador Chrome real en Windows
    scraper = cloudscraper.create_scraper(
        browser={"browser": "chrome", "platform": "windows", "mobile": False}
    )

    for base_url in DOMINIOS_ANNAS:
        url_busqueda = f"{base_url}/search?q={query_param}"
        log(f"🔎 Probando búsqueda en espejo: {base_url} ...")

        try:
            # timeout corto por espejo para no hacer esperar al usuario si uno está caído
            response = scraper.get(url_busqueda, timeout=10)

            if response.status_code == 200:
                md5_matches = re.findall(r"/md5/([a-fA-F0-9]{32})", response.text)
                md5_unicos = list(dict.fromkeys(md5_matches))

                if md5_unicos:
                    log(f"✅ ¡Éxito en {base_url}! Se encontraron {len(md5_unicos)} resultados.")
                    enlaces = [
                        f"{base_url}/md5/{md5}"
                        for md5 in md5_unicos[:max_resultados]
                    ]
                    return enlaces
                else:
                    log(f"⚠️ El espejo {base_url} respondió, pero no encontró libros.")
            else:
                log(f"⚠️ El espejo {base_url} devolvió código HTTP {response.status_code}.")

        except Exception as e:
            log(f"❌ Falló el espejo {base_url}: {e}")
            continue  # Pasa automáticamente al siguiente dominio de la lista

    log("❌ Todos los espejos de Anna's Archive fallaron o no arrojaron resultados.")
    return None


def generar_texto_pagina(query, enlaces, pagina_actual):
    """Genera el texto formateado de 3 en 3 resultados según la página."""
    total_paginas = math.ceil(len(enlaces) / 3)
    inicio = pagina_actual * 3
    fin = inicio + 3
    enlaces_pagina = enlaces[inicio:fin]

    texto = f"📖 **Resultados para:** _{query}_\n\n"
    texto += (
        f"📄 **Página {pagina_actual + 1} de {total_paginas}**\n\n"
    )

    for i, link in enumerate(enlaces_pagina, start=inicio + 1):
        texto += f"**Opción {i}:**\n🔗 {link}\n\n"

    texto += "💡 _Abre cualquier enlace en tu navegador para descargar gratis._"
    return texto


def generar_teclado_paginacion(search_id, pagina_actual, total_paginas):
    """Crea botones Inline en 2 filas: arriba el indicador de página, abajo la navegación."""
    if total_paginas <= 1:
        return None

    markup = types.InlineKeyboardMarkup()

    # --- FILA 1 (ARRIBA): Botón ancho con el número de página ---
    boton_pagina = types.InlineKeyboardButton(
        f"📄 {pagina_actual + 1} / {total_paginas}",
        web_app=types.WebAppInfo(url="https://portfoliosantimy.up.railway.app"),
    )
    markup.row(boton_pagina)

    # --- FILA 2 (ABAJO): Botón Anterior y/o Siguiente ---
    botones_nav = []

    if pagina_actual > 0:
        botones_nav.append(
            types.InlineKeyboardButton(
                "⬅️ Anterior",
                callback_data=f"pag_{search_id}_{pagina_actual - 1}",
            )
        )

    if pagina_actual < total_paginas - 1:
        botones_nav.append(
            types.InlineKeyboardButton(
                "Siguiente ➡️",
                callback_data=f"pag_{search_id}_{pagina_actual + 1}",
            )
        )

    if botones_nav:
        markup.row(*botones_nav)

    return markup


@bot.message_handler(commands=["libro"])
def comando_libro(message):
    chat_username = message.chat.username or ""
    if (
        chat_username.lower() != GRUPO_PERMITIDO.lower()
        or message.message_thread_id != TEMA_PERMITIDO
    ):
        return

    texto_usuario = message.text.split(maxsplit=1)
    if len(texto_usuario) < 2:
        bot.reply_to(
            message,
            "⚠️ Debes indicar un título o autor.\nEjemplo: `/libro El Principito`",
            parse_mode="Markdown",
        )
        return

    query = texto_usuario[1]
    msg_espera = bot.reply_to(
        message, "🔍 *Buscando en Anna's Archive...*", parse_mode="Markdown"
    )

    # Envolvemos todo en try...except para que NUNCA se quede colgado en "Buscando..."
    try:
        enlaces = buscar_annas_archive(query, max_resultados=48)

        if not enlaces:
            bot.edit_message_text(
                "❌ **No se encontraron resultados** o los servidores de Anna's"
                " Archive están temporalmente bloqueados/caídos. Inténtalo de nuevo"
                " en unos minutos.",
                chat_id=message.chat.id,
                message_id=msg_espera.message_id,
                parse_mode="Markdown",
            )
            return

        search_id = str(uuid.uuid4())[:8]
        cache_busquedas[search_id] = {
            "query": query,
            "user_id": message.from_user.id,
            "enlaces": enlaces,
        }

        texto_inicial = generar_texto_pagina(query, enlaces, pagina_actual=0)
        total_paginas = math.ceil(len(enlaces) / 3)
        teclado = generar_teclado_paginacion(
            search_id, pagina_actual=0, total_paginas=total_paginas
        )

        bot.edit_message_text(
            texto_inicial,
            chat_id=message.chat.id,
            message_id=msg_espera.message_id,
            parse_mode="Markdown",
            disable_web_page_preview=True,
            reply_markup=teclado,
        )

    except Exception as error_general:
        log(f"❌ Error crítico en comando_libro: {error_general}")
        bot.edit_message_text(
            "⚠️ Ocurrió un error inesperado al procesar la búsqueda. Por favor,"
            " intenta nuevamente.",
            chat_id=message.chat.id,
            message_id=msg_espera.message_id,
        )


@bot.callback_query_handler(func=lambda call: call.data.startswith("pag_"))
def manejar_paginacion(call):
    _, search_id, str_pagina = call.data.split("_")
    nueva_pagina = int(str_pagina)

    if search_id not in cache_busquedas:
        bot.answer_callback_query(
            call.id,
            "⚠️ Esta búsqueda ya expiró. Escribe /libro nuevamente.",
            show_alert=True,
        )
        return

    datos = cache_busquedas[search_id]

    if call.from_user.id != datos["user_id"]:
        bot.answer_callback_query(
            call.id,
            "❌ No eres tú quien hizo esta búsqueda. ¡Escribe /libro para buscar el tuyo!",
            show_alert=True,
        )
        return

    total_paginas = math.ceil(len(datos["enlaces"]) / 3)
    nuevo_texto = generar_texto_pagina(
        datos["query"], datos["enlaces"], nueva_pagina
    )
    nuevo_teclado = generar_teclado_paginacion(
        search_id, nueva_pagina, total_paginas
    )

    bot.edit_message_text(
        nuevo_texto,
        chat_id=call.message.chat.id,
        message_id=call.message.message_id,
        parse_mode="Markdown",
        disable_web_page_preview=True,
        reply_markup=nuevo_teclado,
    )
    bot.answer_callback_query(call.id)


@bot.callback_query_handler(func=lambda call: call.data == "ignorar")
def boton_decorativo(call):
    bot.answer_callback_query(call.id)


if __name__ == "__main__":
    log("🤖 Bot iniciado y escuchando comandos (con espejos y cloudscraper)...")
    bot.infinity_polling(interval=1, timeout=20)