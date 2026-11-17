"""
Validación de API keys contra la tabla `usuaris` de la BDD ElBicho.

Una API key es válida si existe un usuario con:
    aplicacio = USUARIS_APLICACIO ('gestock' por defecto)
    clau      = SHA-256 de la clave (lo mismo que SHA2('<clave>', 256) en MariaDB)
    actiu     = 1

La clave nunca se guarda ni se escribe en el log: solo se trabaja con su hash.

Para no hacer una consulta en cada petición, el resultado (válido o no) se recuerda durante
AUTH_CACHE_SEGUNDOS. Desactivar un usuario o cambiarle el rol tarda como máximo ese tiempo.
"""
import hashlib
import threading
import time
from dataclasses import dataclass

from gestock_server.config import (
    API_KEY_MAX_LEN,
    AUTH_CACHE_SEGUNDOS,
    ROLES,
    USUARIS_APLICACIO,
)
from gestock_server.db.database import db_pool
from gestock_server.db.driver import DBError

import logging
logger = logging.getLogger(__name__)

# Máximo de claves distintas en caché (evita que alguien llene la memoria probando claves)
_CACHE_MAX = 1000


@dataclass(frozen=True)
class Usuario:
    id_usuari: int
    nom: str
    rol: str


_cache: dict[str, tuple[float, Usuario | None]] = {}
_cache_lock = threading.Lock()


def hash_clau(key: str) -> str:
    """SHA-256 en hexadecimal (minúsculas), igual que SHA2(key, 256) de MariaDB."""
    return hashlib.sha256(key.encode("utf-8")).hexdigest()


def _cache_get(clau: str):
    with _cache_lock:
        entry = _cache.get(clau)
        if entry and entry[0] > time.monotonic():
            return True, entry[1]
        if entry:
            _cache.pop(clau, None)
    return False, None


def _cache_put(clau: str, usuario: Usuario | None) -> None:
    if AUTH_CACHE_SEGUNDOS <= 0:
        return
    with _cache_lock:
        if len(_cache) >= _CACHE_MAX:
            _cache.clear()
        _cache[clau] = (time.monotonic() + AUTH_CACHE_SEGUNDOS, usuario)


def clear_cache() -> None:
    """Vacía la caché (p. ej. tras dar de baja un usuario, para que se aplique al momento)."""
    with _cache_lock:
        _cache.clear()


def validar_api_key(key: str | None) -> Usuario | None:
    """
    Devuelve el usuario de la API key, o None si la clave no es válida
    (vacía, demasiado larga, inexistente, de otra aplicación o de un usuario desactivado).

    Raises:
        ConnectionError: si no se puede consultar la BDD. En ese caso NO se debe tratar como
                         clave incorrecta (no hay que contar el intento ni bloquear la IP).
    """
    if not key:
        return None

    key = key.strip()
    if not key or len(key) > API_KEY_MAX_LEN:
        return None

    clau = hash_clau(key)

    hit, usuario = _cache_get(clau)
    if hit:
        return usuario

    try:
        with db_pool.get_connection() as conn:
            with conn.cursor() as cursor:
                cursor.execute(
                    """
                    SELECT id_usuari, nom_usuari, rol
                    FROM usuaris
                    WHERE aplicacio = %s
                      AND clau = %s
                      AND actiu = 1
                    LIMIT 1
                    """,
                    (USUARIS_APLICACIO, clau)
                )
                row = cursor.fetchone()

    except DBError as e:
        logger.critical(f"ERROR SQL VALIDANT API KEY: {e}")
        raise ConnectionError("Error de la base de dades")

    except Exception as e:
        # Pool sin conexiones o BDD caída (HTTPException 500/503 del pool)
        logger.critical(f"NO S'HA POGUT VALIDAR L'API KEY (BDD NO DISPONIBLE): {e}")
        raise ConnectionError("Base de dades no disponible")

    if row is None:
        usuario = None
    elif row[2] not in ROLES:
        logger.error(f"L'USUARI {row[1]} (id {row[0]}) TÉ UN ROL DESCONEGUT: {row[2]!r}")
        usuario = None
    else:
        usuario = Usuario(id_usuari=int(row[0]), nom=row[1], rol=row[2])

    _cache_put(clau, usuario)
    return usuario
