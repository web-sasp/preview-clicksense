from pydantic import BaseModel
from typing import Optional, List
from datetime import datetime

class SancionCreate(BaseModel):
    id: str
    usuario: str
    discord_id: str
    motivo: str
    tipo: str
    pruebas: Optional[str] = None
    status: Optional[str] = "Activa"

class SancionUpdate(BaseModel):
    usuario: Optional[str] = None
    discord_id: Optional[str] = None
    motivo: Optional[str] = None
    tipo: Optional[str] = None
    pruebas: Optional[str] = None
    status: Optional[str] = None

class SancionResponse(SancionCreate):
    fecha_registro: datetime

    class Config:
        from_attributes = True

class NotificacionCreate(BaseModel):
    discord_id: str
    tipo: str                 # "registro", "sancion", "evento", etc.
    titulo: Optional[str] = None
    descripcion: str
    campos: Optional[List[dict]] = None   # [{"name": "...", "value": "...", "inline": True}]

class LogoutRequest(BaseModel):
    discord_id: str