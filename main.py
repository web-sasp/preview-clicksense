import os
import re
import base64
import json
import secrets
import tempfile
import threading
import html as html_lib
from datetime import datetime, timezone
from fastapi import FastAPI, Depends, HTTPException, Request, Response, Cookie, BackgroundTasks
from fastapi.responses import HTMLResponse
from fastapi.staticfiles import StaticFiles
from sqlalchemy import Column, String, DateTime, Boolean
from sqlalchemy.orm import Session
from pydantic import BaseModel
import requests
from dotenv import load_dotenv

import models
import schemas
import notifier
from database import engine, get_db

load_dotenv()


# ==========================================
# 0. TABLAS EXTRA (perfil y preferencias de notificación)
# ==========================================
# Se definen aquí para no tener que modificar models.py.
# Deben declararse ANTES de create_all para que se creen las tablas.
class PerfilUsuarioDB(models.Base):
    __tablename__ = "perfiles_usuario"

    discord_id = Column(String, primary_key=True, index=True)
    steam = Column(String, nullable=True)
    nacionalidad = Column(String, nullable=True)
    fecha_nacimiento = Column(String, nullable=True)
    actualizado = Column(DateTime, default=datetime.utcnow)


class PreferenciaNotifDB(models.Base):
    """Usuarios que han pulsado la campanita de novedades en home.html."""
    __tablename__ = "preferencias_notificaciones"

    discord_id = Column(String, primary_key=True, index=True)
    activas = Column(Boolean, default=False)
    actualizado = Column(DateTime, default=datetime.utcnow)


models.Base.metadata.create_all(bind=engine)

app = FastAPI(title="ClickSense RP API", version="1.0")

# ---------- Test de whitelist (whitelist_api.py, en la misma carpeta que este archivo) ----------
# Se carga aquí arriba para que sus rutas /api/whitelist... tengan prioridad.
# Si el archivo falta o tiene un error, la web NO se cae: se avisa en la consola y
# simplemente el test de whitelist no estará disponible hasta que se arregle.
try:
    import whitelist_api
    app.include_router(whitelist_api.router)
    print("[whitelist] ✅ Test de whitelist cargado.")
except Exception as e:
    print("[whitelist] ❌ No se pudo cargar whitelist_api.py (¿está junto a main.py?):", repr(e))

STEAM_REGEX = re.compile(
    r"^https?://(www\.)?steamcommunity\.com/(id/[a-zA-Z0-9_-]+|profiles/\d+)/?$"
)
BIRTH_REGEX = re.compile(r"^\d{2}/\d{2}/\d{4}$")

PAISES_VALIDOS = {
    "España", "Francia", "Alemania", "Italia", "Reino Unido", "Portugal",
    "Países Bajos", "Suecia", "México", "Argentina", "Colombia", "Chile",
    "Perú", "Estados Unidos", "Uruguay", "Venezuela",
}

# IDs de Discord del staff que puede publicar novedades (en .env: STAFF_DISCORD_IDS=id1,id2)
# Si se deja vacío, basta con tener sesión iniciada.
STAFF_IDS = {i.strip() for i in os.getenv("STAFF_DISCORD_IDS", "").split(",") if i.strip()}

# ID de Discord con acceso total a la gestión de staff. Es el mismo MASTER_ADMIN_ID
# que hay en public/admin/staff.html. Se puede cambiar en .env: MASTER_ADMIN_ID=tu_id
MASTER_ADMIN_ID = os.getenv("MASTER_ADMIN_ID", "732650490588037160").strip()

# Carpeta de datos: siempre junto a main.py, sin depender de desde dónde se lance el servidor
DATA_DIR = os.path.join(os.path.dirname(__file__), "data")
NOVEDADES_FILE = os.path.join(DATA_DIR, "novedades.json")
PERFIL_FILE = os.path.join(DATA_DIR, "perfiles.json")
SUGERENCIAS_FILE = os.path.join(DATA_DIR, "sugerencias.json")
TICKETS_FILE = os.path.join(DATA_DIR, "tickets.json")
FOTOS_FILE = os.path.join(DATA_DIR, "fotografias.json")
STAFF_FILE = os.path.join(DATA_DIR, "staff.json")
TRANSCRIPTS_DIR = os.path.join(DATA_DIR, "transcripts")

# Fotografías que suben los usuarios desde perfil.html. Los archivos se guardan en
# data/fotos y se sirven en /fotos/<archivo>; la lista de cada usuario va en fotografias.json.
FOTOS_DIR = os.path.join(DATA_DIR, "fotos")
MAX_FOTOS_POR_USUARIO = 12
MAX_FOTO_BYTES = 4 * 1024 * 1024   # 4 MB por imagen (el navegador ya la reduce antes de enviarla)

# Dirección pública de la web (para los enlaces que se envían por Discord). En .env: PUBLIC_URL=https://tudominio.com
PUBLIC_URL = os.getenv("PUBLIC_URL", "http://localhost:8000").rstrip("/")

_file_lock = threading.Lock()


def leer_json(path: str, default):
    """Lee un JSON; si no existe o está roto devuelve el valor por defecto."""
    try:
        with open(path, "r", encoding="utf-8") as f:
            return json.load(f)
    except (FileNotFoundError, ValueError, OSError):
        return default


def escribir_json(path: str, data) -> None:
    """Escritura atómica: se escribe en un temporal y se reemplaza, así nunca queda un archivo a medias."""
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with _file_lock:
        fd, tmp = tempfile.mkstemp(dir=os.path.dirname(path), suffix=".tmp")
        try:
            with os.fdopen(fd, "w", encoding="utf-8") as f:
                json.dump(data, f, ensure_ascii=False)
            os.replace(tmp, path)
        finally:
            if os.path.exists(tmp):
                os.remove(tmp)


class NovedadIn(BaseModel):
    id: str
    titulo: str
    descripcion: str
    categoria: str = "Comunicados"
    destacada: bool = False
    autor: str = "Staff"
    avatarUrl: str | None = None
    fecha: str | None = None


def _require_staff(discord_id: str | None):
    if not discord_id:
        raise HTTPException(status_code=401, detail="No hay sesión activa")
    if STAFF_IDS and discord_id not in STAFF_IDS:
        raise HTTPException(status_code=403, detail="Solo el staff puede hacer esto")


def _encode_pending(data: dict) -> str:
    raw = json.dumps(data, ensure_ascii=False).encode("utf-8")
    return base64.urlsafe_b64encode(raw).decode("ascii")


def _decode_pending(value: str):
    try:
        raw = base64.urlsafe_b64decode(value.encode("ascii"))
        data = json.loads(raw.decode("utf-8"))
        return data if isinstance(data, dict) else None
    except Exception:
        return None


# ==========================================
# 1. AUTENTICACIÓN CON DISCORD
# ==========================================

@app.get("/auth/discord/callback", response_class=HTMLResponse)
def discord_auth_callback(
    code: str,
    pending_profile: str = Cookie(None),
    db: Session = Depends(get_db),
):
    token_url = "https://discord.com/api/oauth2/token"
    client_id = os.getenv("DISCORD_CLIENT_ID")
    client_secret = os.getenv("DISCORD_CLIENT_SECRET")

    # IMPORTANTE: Forzamos el callback exacto para que coincida con el botón y Discord Developer Portal
    redirect_uri = "http://localhost:8000/auth/discord/callback"

    data = {
        "client_id": client_id,
        "client_secret": client_secret,
        "grant_type": "authorization_code",
        "code": code,
        "redirect_uri": redirect_uri,
    }
    headers = {"Content-Type": "application/x-www-form-urlencoded"}

    response_discord = requests.post(token_url, data=data, headers=headers)

    if response_discord.status_code != 200:
        # Esto imprimirá el error real en tu terminal negra de Python para depuración
        print("❌ ERROR REAL DE DISCORD:", response_discord.json())
        raise HTTPException(status_code=400, detail=f"No se pudo autenticar con Discord: {response_discord.json().get('error_description', 'Error desconocido')}")

    access_token = response_discord.json().get("access_token")
    user_headers = {"Authorization": f"Bearer {access_token}"}
    user_response = requests.get("https://discord.com/api/users/@me", headers=user_headers)

    if user_response.status_code != 200:
        raise HTTPException(status_code=400, detail="No se pudo obtener el perfil de Discord")

    user_info = user_response.json()
    discord_id = user_info.get("id")
    username = user_info.get("username")
    avatar = user_info.get("avatar")

    avatar_url = f"https://cdn.discordapp.com/avatars/{discord_id}/{avatar}.png" if avatar else "https://cdn.discordapp.com/embed/avatars/0.png"

    usuario = db.query(models.UsuarioDB).filter(models.UsuarioDB.discord_id == discord_id).first()
    es_nuevo = usuario is None

    if es_nuevo:
        usuario = models.UsuarioDB(
            discord_id=discord_id,
            username=username,
            avatar=avatar,
        )
        db.add(usuario)
    else:
        usuario.username = username
        usuario.avatar = avatar
        usuario.ultimo_login = datetime.utcnow()

    # Guardamos los datos adjuntados en el login (Steam, nacionalidad, nacimiento)
    if pending_profile:
        pending = _decode_pending(pending_profile)
        if pending:
            perfil = db.query(PerfilUsuarioDB).filter(PerfilUsuarioDB.discord_id == discord_id).first()
            if not perfil:
                perfil = PerfilUsuarioDB(discord_id=discord_id)
                db.add(perfil)
            perfil.steam = pending.get("steam")
            perfil.nacionalidad = pending.get("country")
            perfil.fecha_nacimiento = pending.get("birth")
            perfil.actualizado = datetime.utcnow()

    db.commit()

    if es_nuevo:
        notifier.enviar_notificacion(
            discord_id=discord_id,
            tipo="registro",
            descripcion="Te acabas de registrar en la web de **ClickSense RP**. ¡Bienvenido a la ciudad!",
        )

    # Preparamos el objeto de usuario para el frontend
    discord_user_data = {
        "id": discord_id,
        "username": username,
        "displayName": user_info.get("global_name") or username,
        "avatarUrl": avatar_url
    }

    # HTML de transición que guarda los datos en localStorage y vuelve a login.html
    html_content = f"""
    <!DOCTYPE html>
    <html lang="es">
    <head>
        <meta charset="UTF-8">
        <title>Autenticando | ClickSense RP</title>
        <style>
            body {{ background: #06040c; color: #fff; font-family: 'Plus Jakarta Sans', sans-serif; display: flex; align-items: center; justify-content: center; height: 100vh; margin: 0; }}
            .loader-box {{ text-align: center; background: rgba(16, 12, 30, 0.9); padding: 40px; border-radius: 20px; border: 1px solid rgba(168, 85, 247, 0.3); box-shadow: 0 15px 35px rgba(0,0,0,0.8); }}
            h2 {{ color: #d8b4fe; margin-bottom: 10px; }}
            p {{ color: #94a3b8; font-size: 14px; }}
        </style>
    </head>
    <body>
        <div class="loader-box">
            <h2>¡Autenticación Exitosa!</h2>
            <p>Accediendo a ClickSense RP...</p>
        </div>
        <script>
            const userData = {json.dumps(discord_user_data)};
            localStorage.setItem('discord_user', JSON.stringify(userData));
            // login.html muestra la carga y decide: Home si ya está registrado, o el formulario si es la primera vez
            window.location.href = '/login.html?auth=1';
        </script>
    </body>
    </html>
    """

    # IMPORTANTE: las cookies se ponen sobre la respuesta que realmente se devuelve.
    # (Si se devuelve un HTMLResponse, las cookies del objeto Response inyectado se pierden.)
    html_response = HTMLResponse(content=html_content)
    html_response.set_cookie(key="discord_id", value=discord_id, httponly=True, max_age=60*60*24*7)
    html_response.delete_cookie(key="pending_profile")
    return html_response


@app.get("/api/auth/session")
async def get_session(discord_id: str = Cookie(None), db: Session = Depends(get_db)):
    if not discord_id:
        raise HTTPException(status_code=401, detail="No hay sesión activa")

    usuario = db.query(models.UsuarioDB).filter(models.UsuarioDB.discord_id == discord_id).first()
    if not usuario:
        raise HTTPException(status_code=401, detail="Usuario no encontrado")

    avatar_url = f"https://cdn.discordapp.com/avatars/{usuario.discord_id}/{usuario.avatar}.png" if usuario.avatar else "/src/assets/default-avatar.png"

    return {
        "id": usuario.discord_id,
        "username": usuario.username,
        "global_name": usuario.username,
        "avatar": usuario.avatar,
        "avatarUrl": avatar_url
    }

@app.post("/api/auth/logout")
def logout(response: Response):
    response.delete_cookie(key="discord_id")
    return {"success": True}


# ==========================================
# 1.B DATOS DE PERFIL ADJUNTADOS EN EL LOGIN
# ==========================================

@app.post("/api/user-profile-data")
async def guardar_datos_login(
    request: Request,
    response: Response,
    discord_id: str = Cookie(None),
    db: Session = Depends(get_db),
):
    """
    Guarda Steam, fecha de nacimiento y nacionalidad.
      - Con sesión iniciada (flujo actual: primero Discord, después los datos):
        se guardan directamente en la cuenta de Discord de la sesión.
      - Sin sesión (flujo antiguo): se guardan en una cookie temporal y se
        vuelcan a la base de datos en /auth/discord/callback.
    """
    try:
        data = await request.json()
    except Exception:
        raise HTTPException(status_code=400, detail="JSON inválido")
    if not isinstance(data, dict):
        raise HTTPException(status_code=400, detail="Formato no válido")

    steam = str(data.get("steam", "")).strip()
    birth = str(data.get("birth", "")).strip()
    country = str(data.get("country", "")).strip()

    if not STEAM_REGEX.match(steam):
        raise HTTPException(status_code=400, detail="Enlace de Steam no válido")
    if not BIRTH_REGEX.match(birth):
        raise HTTPException(status_code=400, detail="Fecha de nacimiento no válida")
    if country not in PAISES_VALIDOS:
        raise HTTPException(status_code=400, detail="Nacionalidad no válida")

    # --- Con sesión: se guarda ya en la cuenta (el usuario sale de la cookie, nunca del cuerpo) ---
    if discord_id:
        usuario = db.query(models.UsuarioDB).filter(models.UsuarioDB.discord_id == discord_id).first()
        if usuario:
            perfil = db.query(PerfilUsuarioDB).filter(PerfilUsuarioDB.discord_id == discord_id).first()
            if not perfil:
                perfil = PerfilUsuarioDB(discord_id=discord_id)
                db.add(perfil)
            perfil.steam = steam
            perfil.nacionalidad = country
            perfil.fecha_nacimiento = birth
            perfil.actualizado = datetime.utcnow()
            db.commit()
            return {"success": True, "saved": True}

    # --- Sin sesión: cookie temporal hasta completar el login con Discord ---
    pending = _encode_pending({"steam": steam, "birth": birth, "country": country})
    response.set_cookie(
        key="pending_profile",
        value=pending,
        httponly=True,
        max_age=60 * 30,  # 30 minutos para completar el login con Discord
        samesite="lax",
    )
    return {"success": True, "saved": False}

@app.get("/api/user-profile-data")
async def obtener_datos_perfil(
    userId: str = None,
    discord_id: str = Cookie(None),
    db: Session = Depends(get_db),
):
    """
    Devuelve los datos confidenciales SOLO al propio usuario con sesión iniciada.
    """
    if not discord_id:
        raise HTTPException(status_code=401, detail="No hay sesión activa")
    if userId and str(userId) != str(discord_id):
        raise HTTPException(status_code=403, detail="No autorizado")

    perfil = db.query(PerfilUsuarioDB).filter(PerfilUsuarioDB.discord_id == discord_id).first()
    if not perfil:
        return {"steam": None, "country": None, "birth": None}

    return {
        "steam": perfil.steam,
        "country": perfil.nacionalidad,
        "birth": perfil.fecha_nacimiento,
    }


# ==========================================
# 1.C PERFILES: privacidad, redes y qué se muestra
# ==========================================

def limpiar_redes(r) -> dict:
    out = {}
    if not isinstance(r, dict):
        return out
    for k in ("instagram", "youtube", "twitch", "kick"):
        v = str(r.get(k) or "").strip()
        if not v or len(v) > 200:
            continue
        # solo enlaces http/https o un simple nombre de usuario
        if ":" in v.split("/")[0] and not v.lower().startswith(("http://", "https://")):
            continue
        out[k] = v
    return out

def normalizar_perfil(d) -> dict:
    d = d if isinstance(d, dict) else {}
    m = d.get("mostrar") if isinstance(d.get("mostrar"), dict) else {}
    return {
        "redes": limpiar_redes(d.get("redes")),
        "publico": d.get("publico") is not False,
        "mostrar": {
            "redes": m.get("redes") is not False,
            "fotos": m.get("fotos") is not False,
            "sugerencias": m.get("sugerencias") is not False,
        },
    }

def _perfiles() -> dict:
    data = leer_json(PERFIL_FILE, {})
    return data if isinstance(data, dict) else {}

@app.get("/api/perfil-settings")
async def get_perfil_settings(userId: str = "", discord_id: str = Cookie(None)):
    p = normalizar_perfil(_perfiles().get(str(userId)))
    es_dueno = bool(discord_id) and str(discord_id) == str(userId)
    if not p["publico"] and not es_dueno:
        return {"publico": False}              # privado: nada más
    if not es_dueno and not p["mostrar"]["redes"]:
        p["redes"] = {}
    return p

@app.post("/api/perfil-settings")
async def save_perfil_settings(request: Request, discord_id: str = Cookie(None), db: Session = Depends(get_db)):
    if not discord_id:
        raise HTTPException(status_code=401, detail="No hay sesión activa")
    usuario = db.query(models.UsuarioDB).filter(models.UsuarioDB.discord_id == discord_id).first()
    if not usuario:
        raise HTTPException(status_code=401, detail="Usuario no encontrado")

    try:
        body = await request.json()
    except Exception:
        raise HTTPException(status_code=400, detail="JSON no válido")

    todos = _perfiles()
    todos[str(discord_id)] = normalizar_perfil(body)   # el usuario sale de la sesión, nunca del cuerpo
    escribir_json(PERFIL_FILE, todos)
    return {"ok": True}

@app.get("/api/perfiles-publicos")
async def get_perfiles_publicos():
    out = {}
    for uid, raw in _perfiles().items():
        p = normalizar_perfil(raw)
        if p["publico"]:
            out[uid] = {"publico": True, "redes": p["redes"] if p["mostrar"]["redes"] else {}}
    return out

# ---------- Fotografías del perfil (subir, listar y borrar) ----------

_FOTO_URL_RE = re.compile(r"^/fotos/[A-Za-z0-9_-]{1,80}\.(jpg|png|webp)$")


def _foto_valida(u) -> bool:
    """Solo enlaces http/https o archivos subidos a esta web (/fotos/...)."""
    return isinstance(u, str) and (
        u.lower().startswith(("http://", "https://")) or bool(_FOTO_URL_RE.match(u))
    )


def _fotos_todas() -> dict:
    data = leer_json(FOTOS_FILE, {})
    return data if isinstance(data, dict) else {}


def _fotos_de(todas: dict, user_id) -> list:
    lista = todas.get(str(user_id), [])
    return [u for u in lista if _foto_valida(u)] if isinstance(lista, list) else []


def _tipo_imagen(raw: bytes):
    """Tipo real del archivo según sus primeros bytes (no nos fiamos del nombre ni de lo que diga el navegador)."""
    if raw[:3] == b"\xff\xd8\xff":
        return "jpg"
    if raw[:8] == b"\x89PNG\r\n\x1a\n":
        return "png"
    if raw[:4] == b"RIFF" and raw[8:12] == b"WEBP":
        return "webp"
    return None


@app.get("/api/fotografias")
async def get_fotografias(userId: str = "", discord_id: str = Cookie(None)):
    """Lista de imágenes publicadas por un usuario (respeta su privacidad)."""
    p = normalizar_perfil(_perfiles().get(str(userId)))
    es_dueno = bool(discord_id) and str(discord_id) == str(userId)
    if not es_dueno and (not p["publico"] or not p["mostrar"]["fotos"]):
        return []
    return _fotos_de(_fotos_todas(), userId)


@app.post("/api/fotografias")
async def subir_fotografia(request: Request, discord_id: str = Cookie(None), db: Session = Depends(get_db)):
    """Sube una fotografía al perfil de quien tiene la sesión iniciada. Cuerpo: {"imagen": "data:image/...;base64,..."}"""
    if not discord_id:
        raise HTTPException(status_code=401, detail="No hay sesión activa")
    usuario = db.query(models.UsuarioDB).filter(models.UsuarioDB.discord_id == discord_id).first()
    if not usuario:
        raise HTTPException(status_code=401, detail="Usuario no encontrado")

    # Se corta antes de leer nada si la petición es exageradamente grande
    try:
        largo = int(request.headers.get("content-length") or 0)
    except ValueError:
        largo = 0
    if largo > MAX_FOTO_BYTES * 2:
        raise HTTPException(status_code=413, detail="La imagen es demasiado grande")

    try:
        body = await request.json()
    except Exception:
        raise HTTPException(status_code=400, detail="JSON no válido")

    dato = str(body.get("imagen") or "") if isinstance(body, dict) else ""
    if dato.startswith("data:") and "," in dato:
        dato = dato.split(",", 1)[1]
    try:
        raw = base64.b64decode(dato, validate=True)
    except Exception:
        raise HTTPException(status_code=400, detail="La imagen no es válida")

    if not raw:
        raise HTTPException(status_code=400, detail="No se ha recibido ninguna imagen")
    if len(raw) > MAX_FOTO_BYTES:
        raise HTTPException(status_code=413, detail="La imagen es demasiado grande (máximo 4 MB)")

    ext = _tipo_imagen(raw)
    if not ext:
        raise HTTPException(status_code=400, detail="Formato no admitido: solo JPG, PNG o WebP")

    todas = _fotos_todas()
    lista = _fotos_de(todas, discord_id)
    if len(lista) >= MAX_FOTOS_POR_USUARIO:
        raise HTTPException(status_code=400, detail=f"Has llegado al máximo de {MAX_FOTOS_POR_USUARIO} fotografías. Borra alguna para subir otra.")

    # Nombre aleatorio: no se puede adivinar ni pisar el archivo de otro usuario
    solo_digitos = re.sub(r"\D", "", str(discord_id))[:25] or "u"
    nombre = f"{solo_digitos}_{secrets.token_urlsafe(12)}.{ext}"
    try:
        os.makedirs(FOTOS_DIR, exist_ok=True)
        with open(os.path.join(FOTOS_DIR, nombre), "wb") as f:
            f.write(raw)
    except OSError as e:
        print("[fotos] ❌ No se pudo guardar la imagen:", e)
        raise HTTPException(status_code=500, detail="No se pudo guardar la imagen en el servidor")

    url = f"/fotos/{nombre}"
    lista.insert(0, url)   # la más reciente primero
    todas[str(discord_id)] = lista
    escribir_json(FOTOS_FILE, todas)
    return {"ok": True, "url": url, "fotos": lista}


@app.delete("/api/fotografias")
async def borrar_fotografia(url: str = "", discord_id: str = Cookie(None)):
    """Borra una fotografía del perfil de quien tiene la sesión iniciada."""
    if not discord_id:
        raise HTTPException(status_code=401, detail="No hay sesión activa")

    todas = _fotos_todas()
    lista = _fotos_de(todas, discord_id)
    if url not in lista:
        raise HTTPException(status_code=404, detail="Esa fotografía no está en tu perfil")

    lista = [u for u in lista if u != url]
    todas[str(discord_id)] = lista
    escribir_json(FOTOS_FILE, todas)

    if _FOTO_URL_RE.match(url):   # archivo subido a esta web: se borra también del disco
        try:
            os.remove(os.path.join(FOTOS_DIR, os.path.basename(url)))
        except OSError:
            pass
    return {"ok": True, "fotos": lista}


# ==========================================
# 2. GESTIÓN DE SANCIONES
# ==========================================

@app.get("/api/sanciones", response_model=list[schemas.SancionResponse])
def obtener_sanciones(userId: str = None, db: Session = Depends(get_db)):
    query = db.query(models.SancionDB)
    if userId:
        query = query.filter(models.SancionDB.discord_id == userId)
    return query.all()

@app.post("/api/sanciones", response_model=schemas.SancionResponse)
def crear_sancion(sancion: schemas.SancionCreate, db: Session = Depends(get_db)):
    db_sancion = models.SancionDB(**sancion.dict())
    db.add(db_sancion)
    db.commit()
    db.refresh(db_sancion)

    notifier.enviar_notificacion(
        discord_id=db_sancion.discord_id,
        tipo="sancion",
        descripcion=f"Se ha registrado una sanción a tu nombre: **{db_sancion.tipo}**.",
        campos=[
            {"name": "Motivo", "value": db_sancion.motivo, "inline": False},
            {"name": "Expediente", "value": db_sancion.id, "inline": True},
        ],
    )
    return db_sancion

@app.put("/api/sanciones/{sancion_id}", response_model=schemas.SancionResponse)
def actualizar_sancion(sancion_id: str, sancion_update: schemas.SancionUpdate, db: Session = Depends(get_db)):
    db_sancion = db.query(models.SancionDB).filter(models.SancionDB.id == sancion_id).first()
    if not db_sancion:
        raise HTTPException(status_code=404, detail="Sanción no encontrada")
    for key, value in sancion_update.dict(exclude_unset=True).items():
        setattr(db_sancion, key, value)
    db.commit()
    db.refresh(db_sancion)
    return db_sancion

@app.delete("/api/sanciones/{sancion_id}")
def eliminar_sancion(sancion_id: str, db: Session = Depends(get_db)):
    db_sancion = db.query(models.SancionDB).filter(models.SancionDB.id == sancion_id).first()
    if not db_sancion:
        raise HTTPException(status_code=404, detail="Sanción no encontrada")
    db.delete(db_sancion)
    db.commit()
    return {"message": "Sanción eliminada con éxito"}


# ==========================================
# 3. NOTIFICACIONES Y ENDPOINTS DE PERFIL
# ==========================================

@app.post("/api/notificar")
def notificar(payload: schemas.NotificacionCreate):
    ok = notifier.enviar_notificacion(
        discord_id=payload.discord_id,
        tipo=payload.tipo,
        titulo=payload.titulo,
        descripcion=payload.descripcion,
        campos=payload.campos,
    )
    if not ok:
        raise HTTPException(status_code=502, detail="No se pudo contactar con el bot de Discord")
    return {"success": True}


# ---------- 3.A NOVEDADES (publicación + aviso por MD) ----------

@app.get("/api/novedades")
def listar_novedades():
    data = leer_json(NOVEDADES_FILE, [])
    return data if isinstance(data, list) else []


@app.post("/api/novedades")
async def guardar_novedades(request: Request, discord_id: str = Cookie(None)):
    _require_staff(discord_id)
    try:
        data = await request.json()
    except Exception:
        raise HTTPException(status_code=400, detail="JSON inválido")
    if not isinstance(data, list):
        raise HTTPException(status_code=400, detail="Se esperaba una lista")

    escribir_json(NOVEDADES_FILE, data)
    return {"success": True}


@app.post("/api/novedades/notificar")
def notificar_novedad(
    novedad: NovedadIn,
    background: BackgroundTasks,
    discord_id: str = Cookie(None),
    db: Session = Depends(get_db),
):
    """
    Envía la novedad por MD (vía el bot) SOLO a los usuarios que han
    activado la campanita de notificaciones en home.html.
    """
    _require_staff(discord_id)

    activos = db.query(PreferenciaNotifDB).filter(PreferenciaNotifDB.activas == True).all()  # noqa: E712
    ids = [p.discord_id for p in activos if p.discord_id]

    # En segundo plano: con muchos usuarios el envío tarda (hay pausa entre MD)
    background.add_task(notifier.enviar_novedad, novedad.dict(), ids)
    return {"destinatarios": len(ids)}


# ---------- 3.B PREFERENCIA DE NOTIFICACIONES (campanita) ----------

@app.get("/api/notificaciones/preferencias")
def get_preferencias(discord_id: str = Cookie(None), db: Session = Depends(get_db)):
    if not discord_id:
        raise HTTPException(status_code=401, detail="No hay sesión activa")
    pref = db.query(PreferenciaNotifDB).filter(PreferenciaNotifDB.discord_id == discord_id).first()
    return {"activas": bool(pref.activas) if pref else False}


@app.post("/api/notificaciones/preferencias")
async def set_preferencias(request: Request, discord_id: str = Cookie(None), db: Session = Depends(get_db)):
    if not discord_id:
        raise HTTPException(status_code=401, detail="No hay sesión activa")
    try:
        data = await request.json()
    except Exception:
        raise HTTPException(status_code=400, detail="JSON inválido")

    pref = db.query(PreferenciaNotifDB).filter(PreferenciaNotifDB.discord_id == discord_id).first()
    if not pref:
        pref = PreferenciaNotifDB(discord_id=discord_id)
        db.add(pref)
    pref.activas = bool(data.get("activas", False))
    pref.actualizado = datetime.utcnow()
    db.commit()
    return {"success": True, "activas": pref.activas}


# ---------- 3.C SUGERENCIAS Y TICKETS (listas compartidas) ----------
# Las páginas leen la lista completa y la guardan completa (así funcionan sugerencias.html,
# tickets.html y home.html). Guardar requiere sesión iniciada.

MAX_ITEMS = 10000

async def _lista_desde_peticion(request: Request) -> list:
    try:
        data = await request.json()
    except Exception:
        raise HTTPException(status_code=400, detail="JSON inválido")
    if not isinstance(data, list):
        raise HTTPException(status_code=400, detail="Se esperaba una lista")
    if len(data) > MAX_ITEMS:
        raise HTTPException(status_code=413, detail="Demasiados elementos")
    if not all(isinstance(x, dict) for x in data):
        raise HTTPException(status_code=400, detail="Formato no válido")
    return data


@app.get("/api/sugerencias")
async def get_sugerencias(userId: str = None):
    data = leer_json(SUGERENCIAS_FILE, [])
    return data if isinstance(data, list) else []

@app.post("/api/sugerencias")
async def save_sugerencias(request: Request, discord_id: str = Cookie(None)):
    if not discord_id:
        raise HTTPException(status_code=401, detail="No hay sesión activa")
    escribir_json(SUGERENCIAS_FILE, await _lista_desde_peticion(request))
    return {"ok": True}


# ---------- Tickets: lista compartida + cierre (copia HTML y aviso por MD) ----------

_TAG_RE = re.compile(r"<[^>]+>")
_TID_RE = re.compile(r"^[A-Za-z0-9_-]{1,40}$")

_TICKET_CSS = """
*{box-sizing:border-box}body{margin:0;background:#0b0a14;color:#e2e8f0;font-family:'Inter','Segoe UI',sans-serif;line-height:1.55}
.wrap{max-width:860px;margin:0 auto;padding:32px 18px 60px}
.head{background:linear-gradient(135deg,#1a1230,#10101c);border:1px solid rgba(168,85,247,.35);border-radius:18px;padding:24px;margin-bottom:22px}
.brand{font-size:12px;font-weight:700;letter-spacing:1.5px;color:#c084fc;text-transform:uppercase}
h1{margin:8px 0 14px;font-size:24px;color:#fff}
.meta{display:grid;grid-template-columns:repeat(auto-fit,minmax(200px,1fr));gap:10px;font-size:13.5px;color:#94a3b8}
.meta b{display:block;font-size:11px;letter-spacing:.8px;text-transform:uppercase;color:#a78bfa;margin-bottom:2px}
.closed{display:inline-block;margin-left:8px;padding:3px 12px;border-radius:999px;background:rgba(239,68,68,.15);color:#f87171;font-size:12px;font-weight:700;vertical-align:middle}
.msg{margin:12px 0;padding:14px 16px;border-radius:14px;background:rgba(255,255,255,.04);border:1px solid rgba(255,255,255,.08)}
.msg.user{background:rgba(168,85,247,.1);border-color:rgba(168,85,247,.3)}
.msg.system{background:rgba(251,191,36,.06);border-color:rgba(251,191,36,.25);font-size:13.5px}
.top{display:flex;justify-content:space-between;gap:10px;font-size:12.5px;margin-bottom:6px;color:#94a3b8}
.top b{color:#fff;font-size:13.5px}
.msg img{max-width:100%;border-radius:10px;margin-top:10px;display:block}
.foot{margin-top:30px;text-align:center;font-size:12px;color:#64748b}
@media print{body{background:#fff;color:#000}.head,.msg{border-color:#ccc;background:#fff}h1,.top b,.meta b{color:#000}}
"""

def _limpio(s) -> str:
    """Quita etiquetas HTML y escapa el texto (nunca se inserta HTML de usuarios)."""
    return html_lib.escape(_TAG_RE.sub("", str(s or "")))

def _ticket_cerrado(t) -> bool:
    if not isinstance(t, dict):
        return False
    return str(t.get("status") or t.get("estado") or "").lower() == "closed"

def _span_fecha(iso, fallback="—") -> str:
    """Fecha que el navegador convierte a la hora local de quien abre el archivo."""
    if not iso:
        return html_lib.escape(str(fallback))
    s = html_lib.escape(str(iso), quote=True)
    return f'<span data-ts="{s}">{s}</span>'

def _render_ticket_html(t: dict) -> str:
    tid = _limpio(t.get("id"))
    titulo = _limpio(t.get("title") or t.get("asunto") or "Sin título")
    categoria = _limpio(t.get("category") or t.get("categoria") or "General")
    usuario = _limpio(t.get("usuario") or "—")

    burbujas = []
    for m in (t.get("messages") or []):
        if not isinstance(m, dict):
            continue
        sender = m.get("sender") if m.get("sender") in ("user", "staff", "system") else "staff"
        nombre = _limpio(m.get("name") or m.get("autor") or "")
        texto = _limpio(m.get("text") or m.get("texto") or "").replace("\n", "<br>")
        hora = _limpio(m.get("time") or "")
        img = ""
        src = str(m.get("image") or "")
        if src.startswith(("data:image/png", "data:image/jpeg", "data:image/gif", "data:image/webp", "https://", "http://")):
            img = f'<img src="{html_lib.escape(src, quote=True)}" alt="Imagen adjunta">'
        burbujas.append(
            f'<div class="msg {sender}"><div class="top"><b>{nombre}</b><span>{hora}</span></div>{texto}{img}</div>'
        )
    cuerpo = "".join(burbujas) or '<div class="msg system">Este ticket no tiene mensajes.</div>'

    script = (
        "<script>document.querySelectorAll('[data-ts]').forEach(function(e){"
        "var d=new Date(e.getAttribute('data-ts'));"
        "if(!isNaN(d))e.textContent=d.toLocaleString('es-ES');});</script>"
    )
    return (
        '<!DOCTYPE html><html lang="es"><head><meta charset="UTF-8">'
        '<meta name="viewport" content="width=device-width, initial-scale=1.0">'
        f"<title>Ticket {tid} | ClickSense RP</title><style>{_TICKET_CSS}</style></head><body><div class=\"wrap\">"
        f'<div class="head"><div class="brand">ClickSense RP · Archivo de ticket</div>'
        f'<h1>{titulo}<span class="closed">CERRADO</span></h1><div class="meta">'
        f"<div><b>Ticket</b>{tid}</div><div><b>Categoría</b>{categoria}</div><div><b>Usuario</b>{usuario}</div>"
        f"<div><b>Creado</b>{_span_fecha(t.get('fechaCreacion'), t.get('date') or '—')}</div>"
        f"<div><b>Cerrado</b>{_span_fecha(t.get('fechaCierre'))}</div></div></div>"
        f"{cuerpo}<div class=\"foot\">Copia generada automáticamente al cerrar el ticket.</div></div>{script}</body></html>"
    )

def _pagina_mensaje(titulo: str, texto: str, codigo: int) -> HTMLResponse:
    cuerpo = (
        '<!DOCTYPE html><html lang="es"><head><meta charset="UTF-8"><title>ClickSense RP</title>'
        f"<style>{_TICKET_CSS}</style></head><body><div class=\"wrap\"><div class=\"head\" style=\"text-align:center\">"
        f'<div class="brand">ClickSense RP</div><h1>{html_lib.escape(titulo)}</h1>'
        f'<p style="color:#94a3b8">{html_lib.escape(texto)}</p>'
        '<p><a href="/login.html" style="color:#c084fc">Iniciar sesión</a></p></div></div></body></html>'
    )
    return HTMLResponse(content=cuerpo, status_code=codigo, headers={"Cache-Control": "no-store"})

def _procesar_cierre_ticket(t: dict) -> None:
    """Guarda la copia HTML del ticket y avisa por MD de Discord a su dueño."""
    tid = str(t.get("id") or "")
    owner = str(t.get("discordId") or "")
    if not _TID_RE.match(tid) or not owner:
        print(f"[tickets] ⚠️ Cierre ignorado: ticket sin id válido o sin discordId ({tid!r}).")
        return

    # 1) Copia HTML (primero, para que el enlace del mensaje ya funcione)
    try:
        os.makedirs(TRANSCRIPTS_DIR, exist_ok=True)
        with open(os.path.join(TRANSCRIPTS_DIR, tid + ".html"), "w", encoding="utf-8") as f:
            f.write(_render_ticket_html(t))
    except Exception as e:
        print("[tickets] ❌ No se pudo guardar la copia HTML:", e)

    # 2) Aviso por MD con botón "Acceder al ticket"
    try:
        ts = int(datetime.fromisoformat(str(t.get("fechaCierre"))).timestamp())
    except Exception:
        ts = int(datetime.now(timezone.utc).timestamp())

    titulo = str(t.get("title") or t.get("asunto") or "Sin título")[:200]
    categoria = str(t.get("category") or t.get("categoria") or "General")[:100]
    url = f"{PUBLIC_URL}/ticket/{tid}.html"

    campos = [
        {
            "name": "**INFORMACIÓN**",
            "value": (
                f"- __**TICKET**__: {titulo}\n"
                f"- __**ID**__: `{tid}`\n"
                f"- __**CATEGORÍA**__: {categoria}\n"
                f"- __**FECHA DE CIERRE**__: <t:{ts}:F>"
            ),
            "inline": False,
        },
        {
            "name": "\u200b",
            "value": "-# ¡ATENCIÓN! Esto es un mensaje automático procedente del sistema de tickets de ClickSense.",
            "inline": False,
        },
    ]

    ok = notifier.enviar_notificacion(
        discord_id=owner,
        tipo="ticket",
        titulo="SISTEMA DE TICKETS",
        descripcion="¡Buenas!, se ha cerrado el siguiente ticket:",
        campos=campos,
        boton_texto="Acceder al ticket",
        boton_url=url,
    )
    if ok:
        print(f"[tickets] ✅ MD de cierre enviado para {tid}.")
    else:
        print(f"[tickets] ❌ No se pudo enviar el MD de {tid}. Mira los mensajes [notifier] / [bot] justo encima.")


@app.get("/api/tickets")
async def get_tickets():
    data = leer_json(TICKETS_FILE, [])
    return data if isinstance(data, list) else []


@app.post("/api/tickets")
async def save_tickets(request: Request, background: BackgroundTasks, discord_id: str = Cookie(None)):
    if not discord_id:
        raise HTTPException(status_code=401, detail="No hay sesión activa")
    nuevos = await _lista_desde_peticion(request)

    anteriores = leer_json(TICKETS_FILE, [])
    previos = {str(x.get("id")): x for x in anteriores if isinstance(x, dict)} if isinstance(anteriores, list) else {}

    ahora = datetime.now(timezone.utc)
    for t in nuevos:
        if not _ticket_cerrado(t) or t.get("cierreNotificado"):
            continue
        tid = str(t.get("id"))
        previo = previos.get(tid)

        if previo is None:
            print(f"[tickets] ⚠️ {tid} llega cerrado pero no estaba en el servidor: no se avisa.")
            continue
        if _ticket_cerrado(previo):
            continue   # ya estaba cerrado antes

        print(f"[tickets] Cierre detectado: {tid}")
        t["fechaCierre"] = ahora.isoformat()
        owner = str(t.get("discordId") or "")
        if owner and (str(discord_id) == owner or (STAFF_IDS and str(discord_id) in STAFF_IDS)):
            t["cierreNotificado"] = True
            background.add_task(_procesar_cierre_ticket, dict(t))
        else:
            print(f"[tickets] ⚠️ Cierre de {tid} ignorado: quien cierra ({discord_id}) no es el dueño ({owner}) ni está en STAFF_IDS.")

    escribir_json(TICKETS_FILE, nuevos)
    return {"ok": True}


@app.get("/ticket/{ticket_id}")
async def ver_ticket_cerrado(ticket_id: str, discord_id: str = Cookie(None)):
    """Copia en HTML de un ticket. Solo la ve su dueño o el staff."""
    tid = ticket_id[:-5] if ticket_id.lower().endswith(".html") else ticket_id
    if not _TID_RE.match(tid):
        return _pagina_mensaje("Ticket no encontrado", "El enlace no es válido.", 404)
    if not discord_id:
        return _pagina_mensaje("Inicia sesión", "Para ver este ticket tienes que iniciar sesión con Discord.", 401)

    lista = leer_json(TICKETS_FILE, [])
    t = next((x for x in lista if isinstance(x, dict) and str(x.get("id")) == tid), None) if isinstance(lista, list) else None
    if t is None:
        return _pagina_mensaje("Ticket no encontrado", "Este ticket no existe o ha sido eliminado.", 404)

    es_dueno = str(t.get("discordId") or "") == str(discord_id)
    if not es_dueno and not (STAFF_IDS and str(discord_id) in STAFF_IDS):
        return _pagina_mensaje("Sin acceso", "Este ticket pertenece a otro usuario.", 403)

    copia = os.path.join(TRANSCRIPTS_DIR, tid + ".html")
    try:
        with open(copia, "r", encoding="utf-8") as f:
            contenido = f.read()
    except OSError:
        contenido = _render_ticket_html(t)   # si aún no existe la copia, se genera al momento
    return HTMLResponse(content=contenido, headers={"Cache-Control": "no-store"})


# ---------- 3.D STAFF (admin/staff.html guarda, equipo.html lee) ----------
# La lista se guarda en data/staff.json.
#  - Leer: cualquiera recibe la versión pública (solo activos y sin las redes marcadas
#    como "Ocultar"). Quien puede gestionar el staff recibe la lista completa.
#  - Guardar: solo el MASTER_ADMIN_ID o un staff activo de la propia lista, y siempre
#    con sesión iniciada (el usuario sale de la cookie, nunca del cuerpo de la petición).

_REDES_STAFF = ("instagram", "youtube", "kick", "twitch")


def _staff() -> list:
    data = leer_json(STAFF_FILE, [])
    return [s for s in data if isinstance(s, dict)] if isinstance(data, list) else []


def _staff_activo(s: dict) -> bool:
    estado = str(s.get("status") or "Activo").strip().lower()
    return estado not in ("inactivo", "inactive", "0", "false")


def _puede_gestionar_staff(discord_id) -> bool:
    if not discord_id:
        return False
    did = str(discord_id).strip()
    if did == MASTER_ADMIN_ID:
        return True
    return any(
        _staff_activo(s) and str(s.get("discordId") or "").strip() == did
        for s in _staff()
    )


def _limpiar_staff(s: dict):
    """Deja solo los campos que usa la web, como texto y con un tamaño razonable."""
    sid = str(s.get("id") or "").strip()[:40]
    usuario = str(s.get("usuario") or "").strip()[:64]
    if not sid or not usuario:
        return None

    out = {
        "id": sid,
        "usuario": usuario,
        "discordId": re.sub(r"\D", "", str(s.get("discordId") or ""))[:25],
        "categoria": str(s.get("categoria") or "Moderación y Soporte").strip()[:60],
        "rango": str(s.get("rango") or "Moderador").strip()[:60],
        "especialidad": str(s.get("especialidad") or "Ninguna").strip()[:400],
        "status": "Activo" if _staff_activo(s) else "Inactivo",
        "fechaRegistro": str(s.get("fechaRegistro") or "").strip()[:40] or None,
    }
    for red in _REDES_STAFF:
        url = str(s.get(red) or "").strip()[:200]
        out[red] = url if url.lower().startswith(("http://", "https://")) else ""
        out["hide" + red.capitalize()] = bool(s.get("hide" + red.capitalize()))
    return out


@app.get("/api/staff")
async def get_staff(discord_id: str = Cookie(None)):
    lista = _staff()
    if _puede_gestionar_staff(discord_id):
        return lista   # el panel necesita la lista completa (inactivos y redes ocultas incluidas)

    publica = []
    for s in lista:
        if not _staff_activo(s):
            continue
        p = dict(s)
        for red in _REDES_STAFF:
            if p.get("hide" + red.capitalize()):
                p[red] = ""
        publica.append(p)
    return publica


@app.post("/api/staff")
async def save_staff(request: Request, discord_id: str = Cookie(None)):
    if not discord_id:
        raise HTTPException(status_code=401, detail="No hay sesión activa")
    if not _puede_gestionar_staff(discord_id):
        raise HTTPException(status_code=403, detail="No tienes permisos para gestionar el staff")

    lista = await _lista_desde_peticion(request)
    limpia = [x for x in (_limpiar_staff(s) for s in lista) if x]
    escribir_json(STAFF_FILE, limpia)
    print(f"[staff] ✅ Lista guardada por {discord_id}: {len(limpia)} miembros.")
    return {"ok": True, "total": len(limpia)}


# ---------- 3.E ENDPOINTS DE RELLENO ----------

@app.get("/api/clickpoints")
async def get_clickpoints(userId: str = None):
    return {"clickpoints": 0}

# Solo responde si whitelist_api.py no se ha podido cargar (si está cargado, manda el suyo)
@app.get("/api/whitelist")
async def get_whitelist(userId: str = None):
    return []

@app.get("/api/vip")
async def get_vip(userId: str = None):
    return {"isVip": False}

@app.get("/api/notificaciones")
async def get_notificaciones(userId: str = None):
    return []

@app.get("/api/propiedades")
async def get_propiedades(userId: str = None):
    return []

@app.post("/api/notificaciones/read")
async def mark_notification_read(request: Request):
    data = await request.json()
    notif_id = data.get("id")
    return {"success": True, "id": notif_id}


# ==========================================
# 4. ARCHIVOS ESTÁTICOS (SIEMPRE AL FINAL)
# ==========================================
public_path = os.path.join(os.path.dirname(__file__), "public")
os.makedirs(public_path, exist_ok=True)

src_path = os.path.join(public_path, "src")
os.makedirs(src_path, exist_ok=True)
app.mount("/src", StaticFiles(directory=src_path), name="src")

# Fotografías subidas por los usuarios (data/fotos -> /fotos/archivo.jpg)
os.makedirs(FOTOS_DIR, exist_ok=True)
app.mount("/fotos", StaticFiles(directory=FOTOS_DIR), name="fotos")

app.mount("/", StaticFiles(directory=public_path, html=True), name="public")