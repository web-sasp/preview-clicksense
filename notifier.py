import os
import time
from datetime import datetime
from zoneinfo import ZoneInfo
requests_mod = __import__("requests")

load_dotenv_mod = __import__("dotenv")
load_dotenv_mod.load_dotenv()

BOT_INTERNAL_URL = os.getenv("BOT_INTERNAL_URL", "http://127.0.0.1:5005/notify")
BOT_INTERNAL_TOKEN = os.getenv("BOT_INTERNAL_TOKEN")

# Pausa entre mensajes para no saturar al bot ni el límite de Discord
PAUSA_ENTRE_DMS = 0.4


def obtener_hora_espanola() -> str:
    """Devuelve la fecha y hora actual en la España peninsular con el formato requerido."""
    try:
        now_madrid = datetime.now(ZoneInfo("Europe/Madrid"))
        hora_str = now_madrid.strftime("%H:%M")
        return f"hoy a las {hora_str}"
    except Exception:
        return datetime.now().strftime("hoy a las %H:%M")


def enviar_notificacion(discord_id: str, tipo: str, descripcion: str,
                        titulo: str = None, campos: list = None,
                        boton_texto: str = None, boton_url: str = None) -> bool:
    """
    Le pide al bot de Discord que mande un DM con embed a discord_id.
    Valida la respuesta del servidor interno del bot.
    """
    if not discord_id:
        return False

    footer_text = f"ClickSense RP • Sistema de notificaciones • {obtener_hora_espanola()}"

    payload = {
        "discord_id": str(discord_id),
        "tipo": tipo,
        "titulo": titulo,
        "descripcion": descripcion,
        "campos": campos or [],
        "thumbnail": "https://i.imgur.com/ibt9508.png",
        "footer_text": footer_text,
        "footer_icon": "https://i.imgur.com/ibt9508.png",
        "button_text": boton_texto or "Acceder al portal online",
        "button_url": boton_url or ""
    }
    headers = {"X-Internal-Token": BOT_INTERNAL_TOKEN or ""}

    try:
        respuesta = requests_mod.post(BOT_INTERNAL_URL, json=payload, headers=headers, timeout=4)
        if respuesta.status_code == 200:
            try:
                data = respuesta.json()
            except ValueError:
                print("[notifier] Respuesta del bot no válida (no es JSON).")
                return False
            return bool(data.get("success", False))
        else:
            print(f"[notifier] El bot rechazó la notificación (Status {respuesta.status_code}): {respuesta.text}")
            return False
    except requests_mod.RequestException as error:
        print(f"[notifier] No se pudo conectar con el servidor interno del bot en el puerto 5005: {error}")
        return False


def enviar_novedad(novedad: dict, discord_ids: list) -> dict:
    """
    Envía una novedad por DM (vía el bot) a cada discord_id de la lista.
    Pensada para ejecutarse en segundo plano (BackgroundTasks).
    Devuelve un resumen {"enviados": n, "fallidos": n}.
    """
    categoria = novedad.get("categoria") or "Comunicados"
    autor = novedad.get("autor") or "Staff"
    destacada = bool(novedad.get("destacada"))
    titulo_novedad = novedad.get("titulo", "")

    titulo = f"NUEVA NOVEDAD REGISTRADA - {titulo_novedad}"[:256]
    descripcion = (novedad.get("descripcion") or "")[:4000]

    campos = [
        {"name": "Categoría", "value": categoria, "inline": True},
        {"name": "Publicado por", "value": autor, "inline": True},
    ]
    if destacada:
        campos.append({"name": "Destacada", "value": "Sí", "inline": True})

    # Añadimos el bloque de texto de atención justo debajo de los campos de metadatos
    campos.append({
        "name": "\u200b",
        "value": "-# ¡ATENCIÓN! Esto es un mensaje automático procedente del sistema de notificaciones de ClickSense. Puedes desactivar esta notificación en cualquier momento pulsando en el botón adjunto.",
        "inline": False
    })

    enviados = 0
    fallidos = 0
    for discord_id in discord_ids:
        ok = enviar_notificacion(
            discord_id=discord_id,
            tipo="novedad",
            titulo=titulo,
            descripcion=descripcion,
            campos=campos,
        )
        if ok:
            enviados += 1
        else:
            fallidos += 1
        time.sleep(PAUSA_ENTRE_DMS)

    print(f"[notifier] Novedad '{titulo_novedad}': {enviados} enviados, {fallidos} fallidos.")
    return {"enviados": enviados, "fallidos": fallidos}