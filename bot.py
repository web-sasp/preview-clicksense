import os
from datetime import datetime

import discord
from aiohttp import web
from dotenv import load_dotenv

load_dotenv()

BOT_TOKEN = os.getenv("DISCORD_BOT_TOKEN")
TOKEN = BOT_TOKEN  # Alias obligatorio para que run.py importe el bot correctamente
INTERNAL_TOKEN = os.getenv("BOT_INTERNAL_TOKEN")
INTERNAL_PORT = int(os.getenv("BOT_INTERNAL_PORT", "5005"))

PLANTILLAS = {
    "registro": {"titulo": "¡Bienvenido a ClickSense RP!", "color": 0xA855F7, "icono": "🎉"},
    "sancion": {"titulo": "Nueva sanción registrada", "color": 0xEF4444, "icono": "⚠️"},
    "evento": {"titulo": "Nuevo evento en el servidor", "color": 0x38BDF8, "icono": "📅"},
    "ticket": {"titulo": "Ticket cerrado", "color": 0x10B981, "icono": "🎫"},
    "logout": {"titulo": "Sesión cerrada", "color": 0xF59E0B, "icono": "🔒"},
    "default": {"titulo": "Notificación de ClickSense RP", "color": 0x71717A, "icono": "🔔"},
}

intents = discord.Intents.default()
bot = discord.Client(intents=intents)


def construir_embed(tipo: str, titulo, descripcion: str, campos: list) -> discord.Embed:
    plantilla = PLANTILLAS.get(tipo, PLANTILLAS["default"])
    embed = discord.Embed(
        title=titulo or f"{plantilla['icono']} {plantilla['titulo']}",
        description=descripcion,
        color=plantilla["color"],
        timestamp=datetime.utcnow(),
    )

    for campo in campos:
        name = campo.get("name", "\u200b")
        value = campo.get("value", "\u200b")

        embed.add_field(
            name=name,
            value=value,
            inline=campo.get("inline", False),
        )

    # URL de miniatura fija arriba a la derecha
    embed.set_thumbnail(url="https://i.imgur.com/ibt9508.png")

    # Pie de página actualizado
    embed.set_footer(
        text="ClickSense RP • Sistema de notificaciones",
        icon_url="https://i.imgur.com/ibt9508.png"
    )
    return embed


async def manejar_notificacion(request: web.Request) -> web.Response:
    if request.headers.get("X-Internal-Token") != INTERNAL_TOKEN:
        return web.json_response({"error": "no autorizado"}, status=401)

    datos = await request.json()
    discord_id = datos.get("discord_id")
    if not discord_id:
        return web.json_response({"error": "falta discord_id"}, status=400)

    try:
        usuario = await bot.fetch_user(int(discord_id))
        embed = construir_embed(
            tipo=datos.get("tipo", "default"),
            titulo=datos.get("titulo"),
            descripcion=datos.get("descripcion", ""),
            campos=datos.get("campos") or [],
        )

        # Botón de enlace inferior (texto y URL configurables desde el notifier)
        boton_texto = str(datos.get("button_text") or "Acceder al panel online")[:80]
        boton_url = str(datos.get("button_url") or "http://localhost:8000/home.html")
        if not boton_url.lower().startswith(("http://", "https://")):
            boton_url = "http://localhost:8000/home.html"

        view = discord.ui.View()
        view.add_item(discord.ui.Button(
            style=discord.ButtonStyle.link,
            label=boton_texto,
            url=boton_url
        ))

        await usuario.send(embed=embed, view=view)
        return web.json_response({"success": True})

    except discord.Forbidden:
        print(f"[bot] Error 403: No se puede enviar DM a {discord_id}. DMs bloqueados o sin servidor común.")
        return web.json_response({"error": "dm_bloqueado", "success": False}, status=403)
    except (discord.NotFound, ValueError):
        print(f"[bot] Error 404: Usuario de Discord no encontrado ({discord_id}).")
        return web.json_response({"error": "usuario_no_encontrado", "success": False}, status=404)
    except Exception as error:
        print(f"[bot] Error interno enviando notificación: {error}")
        return web.json_response({"error": "error_interno", "success": False}, status=500)


async def iniciar_servidor_interno():
    app_web = web.Application()
    app_web.router.add_post("/notify", manejar_notificacion)
    runner = web.AppRunner(app_web)
    await runner.setup()
    site = web.TCPSite(runner, "127.0.0.1", INTERNAL_PORT)
    await site.start()
    print(f"[bot] Servidor interno escuchando en 127.0.0.1:{INTERNAL_PORT}")


_servidor_iniciado = False


@bot.event
async def on_ready():
    global _servidor_iniciado
    print(f"[bot] Conectado como {bot.user} (ID: {bot.user.id})")

    await bot.change_presence(
        status=discord.Status.online,
        activity=discord.Game(name="ClickSense RP")
    )

    # Solo se arranca una vez, aunque el bot se reconecte
    if not _servidor_iniciado:
        _servidor_iniciado = True
        await iniciar_servidor_interno()


if __name__ == "__main__":
    if not BOT_TOKEN:
        raise SystemExit("Falta DISCORD_BOT_TOKEN en el .env")
    if not INTERNAL_TOKEN:
        raise SystemExit("Falta BOT_INTERNAL_TOKEN en el .env")
    bot.run(BOT_TOKEN)