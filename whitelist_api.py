"""
Test de whitelist de ClickSense RP.

Va junto a main.py. En main.py solo hay que añadir, justo debajo de `app = FastAPI(...)`:

    import whitelist_api
    app.include_router(whitelist_api.router)

Cómo funciona:
  - La web pide las preguntas (sin las respuestas correctas) y las opciones llegan barajadas.
  - El usuario envía sus respuestas y EL SERVIDOR las corrige: las respuestas correctas
    nunca salen de aquí, así que no se pueden ver ni falsear desde el navegador.
  - Cada intento se guarda completo en data/whitelist_intentos.json para el panel
    admin/whitelist.html.
"""
import os
import json
import math
import random
import secrets
import hashlib
import tempfile
import threading
from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException, Request, Cookie
from sqlalchemy.orm import Session
from dotenv import load_dotenv

import models
from database import get_db

load_dotenv()

router = APIRouter()

# ==========================================
# CONFIGURACIÓN
# ==========================================
PORCENTAJE_APROBADO = 60          # % mínimo de aciertos para aprobar
MAX_INTENTOS_GUARDADOS = 5000     # se conservan los más recientes

DATA_DIR = os.path.join(os.path.dirname(__file__), "data")
INTENTOS_FILE = os.path.join(DATA_DIR, "whitelist_intentos.json")
STAFF_FILE = os.path.join(DATA_DIR, "staff.json")

# El mismo ID maestro que usa la gestión de staff
MASTER_ADMIN_ID = os.getenv("MASTER_ADMIN_ID", "732650490588037160").strip()
# Sirve para generar los identificadores de las opciones (no hace falta tocarlo)
_SAL = os.getenv("WHITELIST_SALT", "clicksense-whitelist-test")

BLOQUES = {
    1: "Normativa general",
    2: "Normativa de actos delictivos",
    3: "Normativa de creadores de contenido",
    4: "Normativa de playmakers (PM)",
}

# ==========================================
# BANCO DE PREGUNTAS
# Para cambiar una pregunta, edítala aquí y reinicia el servidor.
# "correcta" es la letra de la opción buena.
# ==========================================
PREGUNTAS = [
    # ---------- BLOQUE 1: NORMATIVA GENERAL ----------
    {
        "n": 1, "bloque": 1, "tema": "1.3", "titulo": "Comportamiento de los usuarios",
        "enunciado": "Estás dentro del servidor de ClickSense RP y un jugador comienza a insultar gravemente a otro miembro de la comunidad y a faltarle el respeto al STAFF a través del chat de voz. Según la normativa, ¿cuál es la actitud correcta?",
        "opciones": {
            "A": "Responderle con los mismos insultos para defender al afectado.",
            "B": "Los jugadores deben mostrar respeto en todo momento hacia los demás miembros y el STAFF; la administración tomará acciones contra quienes incumplan la ética y el buen comportamiento.",
            "C": "Está permitido siempre y cuando sea parte de la interpretación de un personaje malhumorado.",
            "D": "Puedes ignorarlo y reportarlo directamente por el chat global OOC.",
        },
        "correcta": "B",
    },
    {
        "n": 2, "bloque": 1, "tema": "1.4", "titulo": "Creación del personaje",
        "enunciado": "Un nuevo usuario entra al servidor con el nombre \"Batman_Kriptonita\" y sin haber definido una historia de fondo para su personaje. ¿Qué dictamina la normativa al respecto?",
        "opciones": {
            "A": "Está permitido si el personaje viste de superhéroe.",
            "B": "Los nombres deben ser realistas, seguir el formato de Nombre y Apellido (sin significados \"troll\") y el personaje debe tener una historia de fondo coherente que seguir.",
            "C": "Solo se permite cambiar el nombre una vez alcanzado el nivel 2.",
            "D": "No importa el nombre mientras no insulte a nadie directamente.",
        },
        "correcta": "B",
    },
    {
        "n": 3, "bloque": 1, "tema": "1.5", "titulo": "Requisitos mínimos",
        "enunciado": "Un jugador de 16 años logra saltarse los filtros de acceso y entra a jugar en ClickSense RP fingiendo ser mayor de edad. Si la administración lo descubre, ¿qué ocurre?",
        "opciones": {
            "A": "Se le otorga una advertencia verbal y se le invita a volver cuando cumpla 18.",
            "B": "Debe pagar una tasa simbólica de moderación para regularizar su cuenta.",
            "C": "Los jugadores deben tener al menos 18 años para acceder; cualquier menor detectado podrá ser expulsado de la Comunidad por la Administración.",
            "D": "No hay problema siempre que mantenga un buen rol.",
        },
        "correcta": "C",
    },
    {
        "n": 4, "bloque": 1, "tema": "1.6", "titulo": "Reportar un rol",
        "enunciado": "Estás involucrado en una situación de rol compleja y consideras que la otra parte ha infringido la normativa. ¿Cuál de los siguientes pasos debes seguir obligatoriamente antes de abrir un ticket?",
        "opciones": {
            "A": "Abandonar el juego de inmediato (tirar de E) para no perder tiempo.",
            "B": "Finalizar siempre el rol con normalidad, hablar primero con la otra parte para aclarar las discrepancias y, si no hay entendimiento, abrir ticket adjuntando vídeo probatorio.",
            "C": "Publicar lo sucedido en el canal de streaming o redes sociales para buscar apoyo.",
            "D": "Sancionar al jugador utilizando el comando /report dentro del propio rol.",
        },
        "correcta": "B",
    },
    {
        "n": 5, "bloque": 1, "tema": "2.1", "titulo": "Character Kill (CK)",
        "enunciado": "Tu personaje ha sufrido un Character Kill (CK) debido a una serie de decisiones argumentales y a la autorización de la administración. ¿Qué implicaciones tiene esto?",
        "opciones": {
            "A": "Podrás reaparecer en el hospital tras 10 minutos de espera.",
            "B": "Tu personaje muere definitivamente y no podrás volver a interpretarlo dentro del servidor hasta el siguiente wipe (o dejarlo en standby si se aplica una marcha/Ley Rico).",
            "C": "Podrás recuperar el personaje pagando una fianza a la administración.",
            "D": "Se borrará tu inventario pero conservarás el nivel de las habilidades.",
        },
        "correcta": "B",
    },
    {
        "n": 6, "bloque": 1, "tema": "2.6", "titulo": "Player Kill (PK)",
        "enunciado": "Tu personaje cae en estado de coma durante un tiroteo y posteriormente es reanimado por un médico en el hospital. Al encontrarte con tus agresores en la calle poco después, ¿puedes reconocerlos y vengarte?",
        "opciones": {
            "A": "Sí, porque recuerdas perfectamente quién te disparó antes de quedar inconsciente.",
            "B": "No, al ser reanimado por un médico se debe interpretar pérdida de memoria respecto a quién generó la inconsciencia, pudiendo recordar el contexto pero nunca quién lo realizó a menos que alguien presente lo recuerde.",
            "C": "Sí, siempre y cuando avises por /msg que vas a iniciar rol de venganza.",
            "D": "No puedes interactuar con ellos bajo ninguna circunstancia durante 48 horas reales.",
        },
        "correcta": "B",
    },
    {
        "n": 7, "bloque": 1, "tema": "2.8 y 4.8", "titulo": "Evasión de rol / Desconexión",
        "enunciado": "Estás siendo detenido por la policía tras cometer un delito menor y, al ver que vas a perder tus armas ilegales, decides pulsar \"Alt+F4\" para desconectarte del servidor. ¿Cómo se califica esta acción?",
        "opciones": {
            "A": "Es una estrategia válida de escape si el juego va lento.",
            "B": "Evasión de rol, la cual está terminantemente prohibida bajo ninguna circunstancia.",
            "C": "Un fallo técnico justificado por las mecánicas del juego.",
            "D": "Un PK automático que evita que la policía te arreste.",
        },
        "correcta": "B",
    },
    {
        "n": 8, "bloque": 1, "tema": "3.3 y 3.4", "titulo": "Uso de comandos de entorno",
        "enunciado": "Te dispones a robar un vehículo aparcado en la calle para utilizarlo posteriormente en un atraco. ¿En qué momento exacto debes enviar el comando correspondiente a la policía?",
        "opciones": {
            "A": "Al terminar el atraco principal para avisar de los daños causados.",
            "B": "Mediante el comando /forzar justo en el momento en que te subes al vehículo.",
            "C": "No es necesario enviar ningún comando si el coche no tiene alarma.",
            "D": "Debes enviar un /report solicitando permiso a los administradores.",
        },
        "correcta": "B",
    },
    {
        "n": 9, "bloque": 1, "tema": "4.1", "titulo": "Abuso de tercera persona",
        "enunciado": "Durante un tiroteo en una calle estrecha, te refugias detrás de un muro alto y, utilizando la cámara en tercera persona de forma elevada, miras por encima del obstáculo para ver la posición exacta de tus enemigos sin exponerte. ¿Cómo se define esta acción?",
        "opciones": {
            "A": "Táctica defensiva avanzada permitida por el motor de GTA.",
            "B": "Abuso de tercera persona, ya que simula una visión irreal imposible en la vida real.",
            "C": "Uso de macros ilegales en la carpeta Citizen.",
            "D": "Un rol de entorno visual correcto.",
        },
        "correcta": "B",
    },
    {
        "n": 10, "bloque": 1, "tema": "4.16", "titulo": "Valoración de vida",
        "enunciado": "Tu personaje es interceptado por un grupo de secuestradores fuertemente armados que le apuntan directamente a la cabeza, exigiéndole que levante las manos y obedezca. Tú decides sacar una pistola rápidamente para dispararles. ¿Qué norma estás incumpliendo?",
        "opciones": {
            "A": "MetaGaming (MG).",
            "B": "Bad Driving (BD).",
            "C": "Nula valoración de vida, lo cual puede conllevar un CK solicitado por la otra parte.",
            "D": "Abuso de comandos /do.",
        },
        "correcta": "C",
    },

    # ---------- BLOQUE 2: NORMATIVA DE ACTOS DELICTIVOS ----------
    {
        "n": 11, "bloque": 2, "tema": "5.1.1", "titulo": "Accesorios y armamento prohibido",
        "enunciado": "Vas a realizar un asalto ilegal a una zona peligrosa y decides equiparte con un mosquete y un cuchillo de caza que tenías guardados. Según la normativa de actos delictivos, ¿es correcto?",
        "opciones": {
            "A": "Sí, siempre que participen un máximo de 2 personas.",
            "B": "No, el uso de mosquete y cuchillo de caza está prohibido en actividades ilícitas y reservado exclusivamente para la actividad de caza.",
            "C": "Sí, porque son armas blancas y de fuego permitidas para civiles.",
            "D": "Solo está prohibido si la policía está presente en la zona.",
        },
        "correcta": "B",
    },
    {
        "n": 12, "bloque": 2, "tema": "5.1.3", "titulo": "Bloqueos y persecuciones",
        "enunciado": "Un grupo de atracadores es perseguido por la policía e inmediatamente al iniciar la persecución, uno de sus compinches cruza un camión de manera brusca generando un choque frontal intencionado contra el coche patrulla. ¿Qué falta se está cometiendo?",
        "opciones": {
            "A": "Está permitido para asegurar la huida a toda costa.",
            "B": "No está permitido ir a un bloqueo inmediatamente al iniciar la persecución ni provocar un choque intencionado entre el vehículo de bloqueo y el coche de la policía.",
            "C": "Es una táctica de evasión de nivel 2 permitida para bandas.",
            "D": "Falta de interpretación de personaje (IDP).",
        },
        "correcta": "B",
    },
    {
        "n": 13, "bloque": 2, "tema": "5.1.6", "titulo": "Farmeo",
        "enunciado": "Acabas de finalizar con éxito un robo a un establecimiento comercial y obtienes el botín. A los 5 minutos, ves otro establecimiento cercano y decides atracarlo inmediatamente de nuevo. ¿Puedes hacerlo?",
        "opciones": {
            "A": "Sí, siempre que tengas munición suficiente.",
            "B": "No, está prohibido el farmeo constante; debes esperar un mínimo de 20 minutos hasta poder realizar el siguiente robo.",
            "C": "Sí, siempre y cuando cambies de vehículo.",
            "D": "Solo si la policía no ha acudido al primer aviso.",
        },
        "correcta": "B",
    },
    {
        "n": 14, "bloque": 2, "tema": "5.1.7", "titulo": "Periodo de gracia en reinicios",
        "enunciado": "El servidor anuncia un reinicio programado para dentro de 10 minutos. Un grupo de amigos decide aprovechar este momento para iniciar un robo rápido a una tienda local. ¿Es válido?",
        "opciones": {
            "A": "Sí, porque el servidor sigue abierto.",
            "B": "No, está prohibido realizar actos delictivos en los 20 minutos anteriores y posteriores a un reinicio programado.",
            "C": "Sí, siempre y cuando terminen antes de que aparezca el mensaje de cuenta atrás.",
            "D": "Solo si participan menos de 2 personas.",
        },
        "correcta": "B",
    },
    {
        "n": 15, "bloque": 2, "tema": "5.1.11", "titulo": "Robo a jugadores y facciones legales",
        "enunciado": "Te encuentras trabajando de taxista transportando a un ciudadano y, al llegar a un callejón oscuro, decides sacarle una pistola para robarle el dinero de la tarifa y las herramientas de trabajo. ¿Qué normativa se aplica?",
        "opciones": {
            "A": "Está permitido si el rol previo duró más de 5 minutos.",
            "B": "Está prohibido robar a jugadores que desempeñan roles en facciones legales y/o comercios (como taxistas, policías, sanitarios), así como sus herramientas u objetos de trabajo.",
            "C": "Es un acto delictivo de tipo civil autorizado.",
            "D": "Se permite únicamente si el taxista no ofrece resistencia.",
        },
        "correcta": "B",
    },
    {
        "n": 16, "bloque": 2, "tema": "5.1.13", "titulo": "Secuestros",
        "enunciado": "Secuestras a un jugador para resolver un conflicto personal y, tras iniciar la negociación, exiges como rescate 5 millones de dólares y un lanzacohetes militar. ¿Es correcta tu petición?",
        "opciones": {
            "A": "Sí, en los secuestros todo vale para conseguir la libertad del rehén.",
            "B": "No, no se puede solicitar dinero, armas u objetos desproporcionados como rescate o en negociaciones.",
            "C": "Sí, siempre que el tiempo del secuestro no supere los 30 minutos.",
            "D": "Solo si la administración da el visto bueno por privado.",
        },
        "correcta": "B",
    },
    {
        "n": 17, "bloque": 2, "tema": "5.1.15 y tabla 5.2.2", "titulo": "Robo a Fleeca",
        "enunciado": "Tu banda (nivel 2) va a planificar un asalto al banco Fleeca. Según la tabla de actos delictivos para bandas, ¿cuántos atracadores mínimos/máximos se requieren y qué tipo de arma está permitida?",
        "opciones": {
            "A": "Mín. 2 / Máx. 4 atracadores con arma blanca.",
            "B": "Mín. 4 / Máx. 6 atracadores con arma automática (permitiendo hasta 8 policías).",
            "C": "Libre de atracadores con armas de fuego cortas.",
            "D": "Mín. 6 / Máx. 8 atracadores con armamento pesado militar.",
        },
        "correcta": "B",
    },
    {
        "n": 18, "bloque": 2, "tema": "5.1.17", "titulo": "Matrículas",
        "enunciado": "Durante una huida policial en tu coche personal, decides bajarte rápidamente en un semáforo y rolear mediante /me que le quitas la matrícula al coche con las manos para despistar a la policía. ¿Estás actuando correctamente?",
        "opciones": {
            "A": "Sí, el /me valida cualquier modificación visual temporal.",
            "B": "No, no está permitido rolear la retirada u ocultación manual de la matrícula; para ello existe obligatoriamente el objeto de matrícula falsa.",
            "C": "Sí, siempre y cuando la policía no esté mirando directamente.",
            "D": "Solo si el vehículo es de alta gama.",
        },
        "correcta": "B",
    },
    {
        "n": 19, "bloque": 2, "tema": "5.2.1", "titulo": "Actos delictivos para civiles",
        "enunciado": "Dos civiles deciden organizarse para realizar un robo a una casa o a un badulaque. ¿Qué límite de civiles atracadores y de policías máximos establece la normativa para este tipo de robo pequeño?",
        "opciones": {
            "A": "Máximo 2 civiles / Máximo 4 policías (usando como máximo arma blanca y el tendero como único rehén).",
            "B": "Máximo 4 civiles / Máximo 6 policías con armas automáticas.",
            "C": "Libre de civiles / Máximo 10 policías.",
            "D": "Máximo 1 civil / Máximo 2 policías sin armas.",
        },
        "correcta": "A",
    },
    {
        "n": 20, "bloque": 2, "tema": "5.2.2", "titulo": "Funcionamiento del /MANDO en robos",
        "enunciado": "Tu grupo solicita con éxito el /mando para realizar un atraco a una joyería. Sin embargo, se entretienen hablando y deciden iniciar el robo transcurridos 12 minutos desde la aceptación. ¿Qué sucede?",
        "opciones": {
            "A": "Pueden continuar el robo con normalidad si hay policías conectados.",
            "B": "La prioridad y posibilidad de realizar el robo quedan completamente anuladas al superarse el plazo de 10 minutos.",
            "C": "Deben enviar un nuevo /mando duplicando la multa.",
            "D": "Se permite un margen de 20 minutos adicionales si no hay patrullas libres.",
        },
        "correcta": "B",
    },

    # ---------- BLOQUE 3: NORMATIVA DE CREADORES DE CONTENIDO ----------
    {
        "n": 21, "bloque": 3, "tema": "6.1", "titulo": "Requisitos previos para streamers",
        "enunciado": "Un jugador desea solicitar el rol oficial de Creador de Contenido en ClickSense RP, pero actualmente cuenta con una advertencia leve (sanción activa) en su historial. ¿Puede obtener el rol?",
        "opciones": {
            "A": "Sí, las advertencias leves no se tienen en cuenta para los creadores.",
            "B": "No, uno de los requisitos previos es no tener ninguna sanción activa dentro del servidor.",
            "C": "Sí, siempre que prometa borrar el directo al finalizar.",
            "D": "Depende del número de seguidores que tenga en su canal.",
        },
        "correcta": "B",
    },
    {
        "n": 22, "bloque": 3, "tema": "6.1", "titulo": "Configuración de directos",
        "enunciado": "Configuras tu plataforma de streaming para que los directos se borren de forma automática nada más terminar la emisión para ahorrar espacio. ¿Cumples con la normativa de creadores?",
        "opciones": {
            "A": "Sí, es una decisión personal del streamer.",
            "B": "No, los directos deben ser accesibles en todo momento y conservarse durante un mínimo de 15 días.",
            "C": "Sí, siempre que avises en el Discord del servidor.",
            "D": "Solo si no muestras información de facciones ilegales.",
        },
        "correcta": "B",
    },
    {
        "n": 23, "bloque": 3, "tema": "6.2", "titulo": "Elementos visuales obligatorios",
        "enunciado": "Al iniciar tu directo en Twitch interpretando en ClickSenseRP, decides colocar tu cámara web justo en la esquina superior derecha de la pantalla, ocultando el logo oficial del servidor. ¿Es correcto?",
        "opciones": {
            "A": "Sí, la webcam puede colocarse donde el streamer prefiera.",
            "B": "No, el logo del servidor ubicado en la parte superior derecha debe estar visible en todo momento y no puede ser ocultado por elementos como webcams o imágenes.",
            "C": "Sí, siempre que incluyas \"ClickSenseRP\" en el título del directo.",
            "D": "Está permitido si juegas con una resolución 16:9.",
        },
        "correcta": "B",
    },
    {
        "n": 24, "bloque": 3, "tema": "6.2 y 6.3", "titulo": "Moderación del chat",
        "enunciado": "Durante tu retransmisión en directo, los espectadores de tu chat comienzan a darte información privilegiada sobre dónde están escondidos tus enemigos en un tiroteo (MetaGaming), y tú actúas en consecuencia dentro del juego. ¿Qué implica esto?",
        "opciones": {
            "A": "Es una ventaja legítima por interactuar con la comunidad.",
            "B": "El creador debe asegurar un comportamiento saludable y evitar el MG a través de los comentarios del chat; incumplirlo conlleva sanciones y retirada del permiso.",
            "C": "La administración solo sanciona a los espectadores, nunca al streamer.",
            "D": "Está permitido si el chat está en modo lento.",
        },
        "correcta": "B",
    },
    {
        "n": 25, "bloque": 3, "tema": "6.3 y 6.4", "titulo": "Motivos de retirada del permiso",
        "enunciado": "Tras un mes de inactividad en la que no has transmitido ningún contenido del servidor de ClickSense RP, la administración revisa tu estado. ¿Qué medida se puede tomar sobre tu rol de creador?",
        "opciones": {
            "A": "Se te asciende automáticamente a creador VIP.",
            "B": "Se te puede retirar el permiso de Content Creator por baja actividad o por no transmitir contenido del servidor durante 15 días.",
            "C": "Se te exige un pago de renovación en el Discord oficial.",
            "D": "No ocurre nada mientras mantengas el título del directo actualizado.",
        },
        "correcta": "B",
    },

    # ---------- BLOQUE 4: NORMATIVA PLAYMAKERS (PM) ----------
    {
        "n": 26, "bloque": 4, "tema": "7.1", "titulo": "Definición de Playmaker",
        "enunciado": "Has obtenido el rol de Playmaker (PM) en el servidor y decides crear por tu cuenta una banda independiente para extorsionar a los negocios de la ciudad sin consultar a nadie. ¿Puedes hacerlo?",
        "opciones": {
            "A": "Sí, los PM tienen total libertad de movimientos creativos.",
            "B": "No, los playmakers participan como figurantes en roles solicitados/impulsados por la Administración, y en ningún caso su rol es independiente de las indicaciones administrativas.",
            "C": "Sí, siempre que utilices el segundo slot generado para ello.",
            "D": "Solo si los negocios aceptan participar voluntariamente.",
        },
        "correcta": "B",
    },
    {
        "n": 27, "bloque": 4, "tema": "7.2.1", "titulo": "Uso del segundo slot",
        "enunciado": "Utilizas el segundo slot de PM que te fue concedido para un evento puntual con el fin de interpretar a un civil corriente y farmear dinero en tus horas libres. ¿Está permitido?",
        "opciones": {
            "A": "Sí, el segundo slot sirve para tener un doble personaje libre.",
            "B": "No, el slot generado de PM no es para tener un doble rol y utilizarlo libremente para hacer roles de forma independiente.",
            "C": "Sí, siempre y cuando no realices actos delictivos.",
            "D": "Solo si pagas las tasas de transferencia de slot.",
        },
        "correcta": "B",
    },
    {
        "n": 28, "bloque": 4, "tema": "7.3", "titulo": "Restricciones de organizaciones",
        "enunciado": "Un grupo de jugadores con el rol de Playmakers decide agruparse formalmente para constituir una nueva organización criminal oficial que controle el tráfico de armas en el servidor. ¿Están autorizados?",
        "opciones": {
            "A": "Sí, siempre que avisen a los líderes de las otras mafias.",
            "B": "No, en ningún caso los PM podrán actuar como facción, organización criminal, organización legal o similares.",
            "C": "Sí, si obtienen la aprobación de los creadores de contenido.",
            "D": "Sí, siempre que sus acciones sean supervisadas por un moderador junior.",
        },
        "correcta": "B",
    },
    {
        "n": 29, "bloque": 4, "tema": "7.4.1", "titulo": "Incompatibilidad con facciones",
        "enunciado": "Eres un miembro activo de la facción legal de la policía (LSPD) dentro del servidor y solicitas unirte al grupo de Playmakers para participar en eventos especiales. ¿Se te permite?",
        "opciones": {
            "A": "Sí, los policías pueden ser PM en su tiempo libre.",
            "B": "No, los jugadores pertenecientes a facciones (legales o ilegales) no tienen prioridad ni pueden acceder como PM, ya que deben atender su rol principal activo y necesario.",
            "C": "Sí, siempre que no intervengas en investigaciones policiales.",
            "D": "Solo si pides una excedencia temporal en la comisaría.",
        },
        "correcta": "B",
    },
    {
        "n": 30, "bloque": 4, "tema": "7.6", "titulo": "Roles policiales de los PM",
        "enunciado": "Tu grupo de Playmakers planea realizar un rol de asalto sorpresa dirigido específicamente contra la comisaría y los agentes de la LSPD. ¿Qué requisito normativo es indispensable?",
        "opciones": {
            "A": "Realizarlo preferiblemente a altas horas de la madrugada sin avisar.",
            "B": "No pueden realizar roles dirigidos a la policía salvo que hayan sido solicitados mediante ticket y posteriormente aprobados por sus encargados.",
            "C": "Contar con al menos 10 playmakers conectados simultáneamente.",
            "D": "Está totalmente prohibido bajo cualquier circunstancia atacar a la policía siendo PM.",
        },
        "correcta": "B",
    },
]

_POR_NUMERO = {p["n"]: p for p in PREGUNTAS}

# ==========================================
# UTILIDADES
# ==========================================
_lock = threading.Lock()


def _leer(path: str, default):
    try:
        with open(path, "r", encoding="utf-8") as f:
            return json.load(f)
    except (FileNotFoundError, ValueError, OSError):
        return default


def _escribir(path: str, data) -> None:
    """Escritura atómica: nunca queda un archivo a medias."""
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with _lock:
        fd, tmp = tempfile.mkstemp(dir=os.path.dirname(path), suffix=".tmp")
        try:
            with os.fdopen(fd, "w", encoding="utf-8") as f:
                json.dump(data, f, ensure_ascii=False)
            os.replace(tmp, path)
        finally:
            if os.path.exists(tmp):
                os.remove(tmp)


def _intentos() -> list:
    data = _leer(INTENTOS_FILE, [])
    return [i for i in data if isinstance(i, dict)] if isinstance(data, list) else []


def _id_opcion(n: int, letra: str) -> str:
    """Identificador de una opción que no revela su letra (y por tanto tampoco cuál es la correcta)."""
    return hashlib.sha256(f"{_SAL}:{n}:{letra}".encode("utf-8")).hexdigest()[:10]


def _minimo_aciertos(total: int) -> int:
    return math.ceil(total * PORCENTAJE_APROBADO / 100)


def _staff_activo(s: dict) -> bool:
    estado = str(s.get("status") or "Activo").strip().lower()
    return estado not in ("inactivo", "inactive", "0", "false")


def _es_staff(discord_id) -> bool:
    """ID maestro o cualquier staff activo registrado en admin/staff.html."""
    if not discord_id:
        return False
    did = str(discord_id).strip()
    if did == MASTER_ADMIN_ID:
        return True
    lista = _leer(STAFF_FILE, [])
    if not isinstance(lista, list):
        return False
    return any(
        isinstance(s, dict) and _staff_activo(s) and str(s.get("discordId") or "").strip() == did
        for s in lista
    )


def _usuario_sesion(discord_id, db: Session):
    if not discord_id:
        raise HTTPException(status_code=401, detail="No hay sesión activa")
    usuario = db.query(models.UsuarioDB).filter(models.UsuarioDB.discord_id == discord_id).first()
    if not usuario:
        raise HTTPException(status_code=401, detail="Usuario no encontrado")
    return usuario


def _resumen(i: dict) -> dict:
    """El intento sin el detalle pregunta a pregunta."""
    return {k: v for k, v in i.items() if k != "respuestas"}


def _tiene_aprobada(lista: list, discord_id) -> bool:
    did = str(discord_id)
    return any(str(i.get("discordId")) == did and i.get("status") == "Aprobado" for i in lista)


def _nuevo_id(lista: list) -> str:
    usados = {str(i.get("id")) for i in lista}
    alfabeto = "ABCDEFGHJKLMNPQRSTUVWXYZ23456789"   # sin letras/números que se confunden
    while True:
        nuevo = "WL-" + "".join(secrets.choice(alfabeto) for _ in range(6))
        if nuevo not in usados:
            return nuevo


# ==========================================
# RUTAS PARA EL USUARIO
# ==========================================

@router.get("/api/whitelist/preguntas")
def preguntas_test(discord_id: str = Cookie(None), db: Session = Depends(get_db)):
    """Las preguntas del test, sin la respuesta correcta y con las opciones barajadas."""
    _usuario_sesion(discord_id, db)
    if _tiene_aprobada(_intentos(), discord_id):
        raise HTTPException(status_code=409, detail="Ya tienes la whitelist aprobada")

    salida = []
    for p in PREGUNTAS:
        opciones = [{"id": _id_opcion(p["n"], letra), "texto": texto} for letra, texto in p["opciones"].items()]
        random.shuffle(opciones)
        salida.append({
            "id": f"p{p['n']}",
            "n": p["n"],
            "bloque": p["bloque"],
            "bloqueNombre": BLOQUES.get(p["bloque"], ""),
            "tema": p["tema"],
            "titulo": p["titulo"],
            "enunciado": p["enunciado"],
            "opciones": opciones,
        })

    total = len(PREGUNTAS)
    return {
        "total": total,
        "minimoPorcentaje": PORCENTAJE_APROBADO,
        "minimoAciertos": _minimo_aciertos(total),
        "bloques": [
            {"id": b, "nombre": nombre, "preguntas": sum(1 for p in PREGUNTAS if p["bloque"] == b)}
            for b, nombre in BLOQUES.items()
        ],
        "preguntas": salida,
    }


@router.post("/api/whitelist/intento")
async def enviar_intento(request: Request, discord_id: str = Cookie(None), db: Session = Depends(get_db)):
    """Corrige el test en el servidor, guarda el intento completo y devuelve solo el resultado."""
    usuario = _usuario_sesion(discord_id, db)

    try:
        body = await request.json()
    except Exception:
        raise HTTPException(status_code=400, detail="JSON no válido")
    if not isinstance(body, dict):
        raise HTTPException(status_code=400, detail="Formato no válido")

    marcadas = body.get("respuestas")
    if not isinstance(marcadas, dict) or len(marcadas) > len(PREGUNTAS) * 2:
        raise HTTPException(status_code=400, detail="Faltan las respuestas")

    try:
        duracion = max(0, min(int(body.get("duracion") or 0), 86400))
    except (TypeError, ValueError):
        duracion = 0

    lista = _intentos()
    if _tiene_aprobada(lista, discord_id):
        raise HTTPException(status_code=409, detail="Ya tienes la whitelist aprobada")

    # ---- Corrección ----
    respuestas, aciertos, sin_responder = [], 0, 0
    por_bloque = {str(b): {"nombre": nombre, "aciertos": 0, "total": 0} for b, nombre in BLOQUES.items()}

    for p in PREGUNTAS:
        marcada = str(marcadas.get(f"p{p['n']}") or "")
        elegida = next((letra for letra in p["opciones"] if _id_opcion(p["n"], letra) == marcada), None)
        acierto = elegida == p["correcta"]

        aciertos += 1 if acierto else 0
        sin_responder += 1 if elegida is None else 0
        bloque = por_bloque.setdefault(str(p["bloque"]), {"nombre": "", "aciertos": 0, "total": 0})
        bloque["total"] += 1
        bloque["aciertos"] += 1 if acierto else 0

        respuestas.append({"n": p["n"], "elegida": elegida, "correcta": p["correcta"], "acierto": acierto})

    total = len(PREGUNTAS)
    aprobado = aciertos * 100 >= PORCENTAJE_APROBADO * total
    estado = "Aprobado" if aprobado else "Rechazado"

    intento = {
        "id": _nuevo_id(lista),
        "usuario": usuario.username or "Usuario",
        "discordId": str(discord_id),
        "status": estado,                 # 'Aprobado' / 'Rechazado' (lo que leen perfil.html y el panel)
        "statusAuto": estado,             # resultado de la corrección, aunque luego el staff lo cambie
        "aciertos": aciertos,
        "fallos": total - aciertos,
        "sinResponder": sin_responder,
        "total": total,
        "porcentaje": round(aciertos * 100 / total, 1) if total else 0,
        "minimoPorcentaje": PORCENTAJE_APROBADO,
        "minimoAciertos": _minimo_aciertos(total),
        "bloques": por_bloque,
        "duracionSeg": duracion,
        "numeroIntento": 1 + sum(1 for i in lista if str(i.get("discordId")) == str(discord_id)),
        "tipo": "Test de whitelist",
        "aprobador": "Corrección automática",
        "fechaRegistro": datetime.now(timezone.utc).isoformat(),
        "respuestas": respuestas,
    }

    lista.insert(0, intento)
    _escribir(INTENTOS_FILE, lista[:MAX_INTENTOS_GUARDADOS])
    print(f"[whitelist] {intento['id']} · {intento['usuario']} ({discord_id}): {aciertos}/{total} -> {estado}")

    # Al usuario solo se le devuelve el recuento, nunca qué preguntas ha fallado
    return {
        "id": intento["id"],
        "aprobado": aprobado,
        "aciertos": aciertos,
        "fallos": total - aciertos,
        "total": total,
        "porcentaje": intento["porcentaje"],
        "minimoPorcentaje": PORCENTAJE_APROBADO,
        "minimoAciertos": intento["minimoAciertos"],
    }


@router.get("/api/whitelist")
def listar_whitelist(userId: str = None, discord_id: str = Cookie(None)):
    """
    Staff: todos los intentos (o los de un usuario si se pasa userId).
    Usuario normal: solo sus propios intentos. Sin sesión: nada.
    Nunca incluye el detalle pregunta a pregunta (eso va en /api/whitelist/detalle).
    """
    if not discord_id:
        return []
    lista = _intentos()
    if _es_staff(discord_id):
        if userId:
            lista = [i for i in lista if str(i.get("discordId")) == str(userId)]
    else:
        lista = [i for i in lista if str(i.get("discordId")) == str(discord_id)]
    return [_resumen(i) for i in lista]


@router.post("/api/whitelist")
def guardar_whitelist_antiguo():
    """La versión anterior guardaba la lista entera desde el navegador. Ya no se admite."""
    raise HTTPException(status_code=410, detail="La whitelist ahora se corrige en el servidor: usa /api/whitelist/intento")


# ==========================================
# RUTAS PARA EL PANEL (admin/whitelist.html)
# ==========================================

@router.get("/api/whitelist/detalle")
def detalle_intento(id: str = "", discord_id: str = Cookie(None)):
    """Un intento completo, con cada pregunta, lo que respondió el usuario y la respuesta correcta."""
    if not discord_id:
        raise HTTPException(status_code=401, detail="No hay sesión activa")
    if not _es_staff(discord_id):
        raise HTTPException(status_code=403, detail="Solo el staff puede ver el detalle de un intento")

    intento = next((i for i in _intentos() if str(i.get("id")) == str(id)), None)
    if intento is None:
        raise HTTPException(status_code=404, detail="Intento no encontrado")

    detalle = []
    for r in intento.get("respuestas") or []:
        if not isinstance(r, dict):
            continue
        p = _POR_NUMERO.get(r.get("n"))
        detalle.append({
            "n": r.get("n"),
            "bloque": p["bloque"] if p else None,
            "bloqueNombre": BLOQUES.get(p["bloque"], "") if p else "",
            "tema": p["tema"] if p else "",
            "titulo": p["titulo"] if p else "",
            "enunciado": p["enunciado"] if p else "(Esta pregunta ya no está en el banco de preguntas)",
            "opciones": p["opciones"] if p else {},
            "elegida": r.get("elegida"),
            "correcta": r.get("correcta"),
            "acierto": bool(r.get("acierto")),
        })

    salida = _resumen(intento)
    salida["respuestas"] = detalle
    return salida


@router.post("/api/whitelist/estado")
async def cambiar_estado(request: Request, discord_id: str = Cookie(None), db: Session = Depends(get_db)):
    """El staff aprueba o rechaza a mano un intento (por encima de la corrección automática)."""
    revisor = _usuario_sesion(discord_id, db)
    if not _es_staff(discord_id):
        raise HTTPException(status_code=403, detail="Solo el staff puede cambiar el estado de una whitelist")

    try:
        body = await request.json()
    except Exception:
        raise HTTPException(status_code=400, detail="JSON no válido")
    if not isinstance(body, dict):
        raise HTTPException(status_code=400, detail="Formato no válido")

    nuevo = str(body.get("status") or "")
    if nuevo not in ("Aprobado", "Rechazado"):
        raise HTTPException(status_code=400, detail="Estado no válido")

    lista = _intentos()
    intento = next((i for i in lista if str(i.get("id")) == str(body.get("id"))), None)
    if intento is None:
        raise HTTPException(status_code=404, detail="Intento no encontrado")

    intento["status"] = nuevo
    intento["aprobador"] = revisor.username or "Staff"
    intento["revisadoPor"] = {"id": str(discord_id), "usuario": revisor.username or "Staff"}
    intento["fechaRevision"] = datetime.now(timezone.utc).isoformat()
    _escribir(INTENTOS_FILE, lista)
    print(f"[whitelist] {intento.get('id')} marcado como {nuevo} por {revisor.username} ({discord_id})")
    return _resumen(intento)