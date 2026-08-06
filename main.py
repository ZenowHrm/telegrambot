import math
import os
import re
import urllib.parse
import uuid
import requests
import telebot
from telebot import types

# 1. Configuración del Token
TOKEN = os.getenv("TELEGRAM_TOKEN", "TU_TOKEN_DE_BOTFATHER_AQUI")
bot = telebot.TeleBot(TOKEN)

BASE_URL = "https://annas-archive.pk"

# 2. Configuración de exclusividad del Grupo/Tema
GRUPO_PERMITIDO = "LosConsejosDeHomeroGrupo"
TEMA_PERMITIDO = 65512

# 3. Caché en memoria para guardar las búsquedas temporalmente
# Estructura: { 'id_busqueda': {'query': '...', 'user_id': 123, 'enlaces': [...]} }
cache_busquedas = {}


def buscar_annas_archive(query, max_resultados=48):
    """Busca en Anna's Archive y devuelve hasta 48 enlaces MD5."""
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

        md5_matches = re.findall(r"/md5/([a-fA-F0-9]{32})", response.text)
        md5_unicos = list(dict.fromkeys(md5_matches))

        enlaces = [
            f"{BASE_URL}/md5/{md5}" for md5 in md5_unicos[:max_resultados]
        ]
        return enlaces
    except Exception as e:
        print(f"Error en la búsqueda: {e}")
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
        texto += f"**Opción {i}:**\n🔗 {link}\n"

    texto += "💡 _Abre cualquier enlace en tu navegador para descargar gratis._"
    return texto


def generar_teclado_paginacion(search_id, pagina_actual, total_paginas):
    """Crea los botones Inline en 2 filas: arriba la página, abajo la navegación."""
    # Si solo hay 1 página, no necesitamos botones
    if total_paginas <= 1:
        return None

    markup = types.InlineKeyboardMarkup()

    # --- FILA 1 (ARRIBA): Botón ancho con el número de página ---
    boton_pagina = types.InlineKeyboardButton(
        f"📄 {pagina_actual + 1} / {total_paginas}",
        web_app=types.WebAppInfo(url="https://portfoliosantimy.up.railway.app"),
    )
    markup.row(boton_pagina)  # Al estar solo en su fila, ocupa todo el ancho

    # --- FILA 2 (ABAJO): Botón de Anterior y/o Siguiente ---
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

    # Si hay botones de navegación disponibles, los agregamos en una segunda fila
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
            "⚠️ Debes indicar un título o autor.\nEjemplo: `/libro El"
            " Principito`",
            parse_mode="Markdown",
        )
        return

    query = texto_usuario[1]
    msg_espera = bot.reply_to(
        message, "🔍 *Buscando en Anna's Archive...*", parse_mode="Markdown"
    )

    enlaces = buscar_annas_archive(query, max_resultados=48)

    if not enlaces:
        bot.edit_message_text(
            "❌ No se encontraron resultados o el servidor tardó en responder.",
            chat_id=message.chat.id,
            message_id=msg_espera.message_id,
        )
        return

    # Creamos un ID único corto para esta búsqueda y la guardamos en memoria
    search_id = str(uuid.uuid4())[:8]
    cache_busquedas[search_id] = {
        "query": query,
        "user_id": message.from_user.id,
        "enlaces": enlaces,
    }

    # Generamos la primera página (índice 0)
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


# --- MANEJADOR DE LOS BOTONES INLINE ---
@bot.callback_query_handler(func=lambda call: call.data.startswith("pag_"))
def manejar_paginacion(call):
    # Desarmamos los datos del botón: "pag_IDBUSQUEDA_NUMPAGINA"
    _, search_id, str_pagina = call.data.split("_")
    nueva_pagina = int(str_pagina)

    # 1. Verificamos si la búsqueda aún existe en memoria
    if search_id not in cache_busquedas:
        bot.answer_callback_query(
            call.id,
            "⚠️ Esta búsqueda ya expiró. Escribe /libro nuevamente.",
            show_alert=True,
        )
        return

    datos = cache_busquedas[search_id]

    # 2. ALERTA DE SEGURIDAD (Como en tu foto):
    # Si quien tocó el botón no es quien escribió el comando /libro
    if call.from_user.id != datos["user_id"]:
        bot.answer_callback_query(
            call.id,
            "❌ No eres tú quien hizo esta búsqueda. ¡Escribe /libro para"
            " buscar el tuyo!",
            show_alert=True,  # Esto hace que salga el cuadro emergente estilo ventana
        )
        return

    # 3. Si es el dueño, actualizamos el texto y los botones
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

    # Respondemos al callback en silencio para que el relojito del botón desaparezca
    bot.answer_callback_query(call.id)


@bot.callback_query_handler(func=lambda call: call.data == "ignorar")
def boton_decorativo(call):
    # Si tocan el botón del centro (ej. "1/5"), no hace nada
    bot.answer_callback_query(call.id)


if __name__ == "__main__":
    print("🤖 Bot iniciado con paginación y protección de botones...")
    bot.infinity_polling(interval=1, timeout=20)