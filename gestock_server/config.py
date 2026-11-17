from pathlib import Path
from dotenv import load_dotenv
from os import getenv

# Ruta absoluta al .env (funciona en Windows y Linux, sin depender del directorio de arranque)
BASE_DIR = Path(__file__).resolve().parent
load_dotenv(BASE_DIR / "gestock.env")

# ---------------------------------------------------------------------------
# Base de datos MariaDB (BDD ElBicho)
# ---------------------------------------------------------------------------
def _env(name: str, default: str | None = None) -> str | None:
    """Lee una variable del .env sin espacios; vacía = no definida."""
    value = getenv(name)
    if value is None:
        return default
    value = value.strip()
    return value if value else default


DB_SERVER = _env("DB_SERVER", "127.0.0.1")
DB_PORT = int(_env("DB_PORT", "3306"))
# Opcional (Linux): ruta del socket de MariaDB, p. ej. /run/mysqld/mysqld.sock.
# Si se indica, se usa en lugar de DB_SERVER/DB_PORT (útil si la API corre en el mismo servidor).
DB_SOCKET = _env("DB_SOCKET")
DB_USER = _env("DB_USER")
DB_PASSWORD = getenv("DB_PASSWORD")          # sin strip: la contraseña se usa tal cual
DB_DATABASE = _env("DB_DATABASE")

DB_MAX_CONNECTIONS = int(_env("DB_MAX_CONNECTIONS", "5"))
DB_CONNECTION_TIMEOUT = int(_env("DB_CONNECTION_TIMEOUT", "10"))

LOG_PATH = getenv("LOG_PATH", "gestock.log")

HEADER_NAME = getenv(
    "HEADER_NAME",
    "X-API-Key"
)

MAX_FAILED_ATTEMPTS = int(
    getenv(
        "MAX_FAILED_ATTEMPTS",
        "5"
    )
)
BLOCKED_IPS_FILE = getenv("BLOCKED_IPS_FILE", "blocked_ips.txt")

# ---------------------------------------------------------------------------
# Autenticación: las API keys se validan contra la tabla usuaris de la BDD
# (usuaris.clau = SHA-256 de la clave, aplicacio = USUARIS_APLICACIO, actiu = 1).
# ---------------------------------------------------------------------------
# Segundos que se recuerda el resultado de validar una clave (evita una consulta por petición).
# Al desactivar un usuario (actiu = 0) o cambiar su rol, el cambio tarda como máximo esto.
AUTH_CACHE_SEGUNDOS = int(_env("AUTH_CACHE_SEGUNDOS", "60"))

# Longitud máxima aceptada para una API key: las más largas se rechazan sin consultar la BDD
API_KEY_MAX_LEN = int(_env("API_KEY_MAX_LEN", "256"))

APIKEY_EXTERNAL = getenv("APIKEY_EXTERNAL")

# Timeouts (segundos) de la API externa de partners. Las 3 marcas se consultan en paralelo,
# así que una búsqueda tarda como máximo CONNECT + READ. Debe ser menor que el timeout de la app
# (Retrofit: 10 s por defecto), para que la app reciba un error claro en vez de "ha tardado demasiado".
EXTERNAL_API_CONNECT_TIMEOUT = float(_env("EXTERNAL_API_CONNECT_TIMEOUT", "3"))
EXTERNAL_API_READ_TIMEOUT = float(_env("EXTERNAL_API_READ_TIMEOUT", "6"))

# Valor de usuaris.aplicacio de los usuarios de Gestock (la tabla usuaris es compartida entre aplicaciones)
USUARIS_APLICACIO = getenv("USUARIS_APLICACIO", "gestock")

# País (ISO de 2 letras) con el que se crean los almacenes nuevos en centres
DEFAULT_PAIS = getenv("DEFAULT_PAIS", "ES")

ROLES = {
    "limitat": 1,
    "usuari": 2,
    "admin": 3,
}

PUBLIC_ROUTES = {
    "/docs",
    "/openapi.json",
    "/redoc",
    "/health",
    "/favicon.ico"
}


def _load_blocked_ips(path: str) -> set[str]:
    """Carga las IPs bloqueadas guardadas en disco para que sobrevivan a un reinicio."""
    try:
        file = Path(path)
        if not file.exists():
            return set()
        return {
            line.strip()
            for line in file.read_text(encoding="utf-8", errors="ignore").splitlines()
            if line.strip()
        }
    except OSError:
        return set()


BLOCKED_IPS = _load_blocked_ips(BLOCKED_IPS_FILE)
FAILED_ATTEMPTS = {}
