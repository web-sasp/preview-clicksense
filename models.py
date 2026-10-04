from sqlalchemy import Column, String, DateTime
from datetime import datetime
from database import Base

class SancionDB(Base):
    __tablename__ = "sanciones"

    id = Column(String, primary_key=True, index=True)
    usuario = Column(String, index=True)
    discord_id = Column(String, index=True)
    motivo = Column(String)
    tipo = Column(String)
    pruebas = Column(String, nullable=True)
    status = Column(String, default="Activa")
    fecha_registro = Column(DateTime, default=datetime.utcnow)


class UsuarioDB(Base):
    __tablename__ = "usuarios"

    discord_id = Column(String, primary_key=True, index=True)
    username = Column(String)
    avatar = Column(String, nullable=True)
    fecha_registro = Column(DateTime, default=datetime.utcnow)
    ultimo_login = Column(DateTime, nullable=True)