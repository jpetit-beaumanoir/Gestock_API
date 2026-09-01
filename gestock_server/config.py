from os import getenv

DB_SERVER = getenv("DB_SERVER")
DB_USER = getenv("DB_USER")
DB_PASSWORD = getenv("DB_PASSWORD")
DB_DATABASE = getenv("DB_DATABASE")

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
BLOCKED_IPS_FILE = getenv("BLOCKED_IP_FILE")

API_KEYS = {
    getenv("APIKEY_ANONIM"): {
        "nom": "anonim",
        "rol": "limitat"
    },
    getenv("APIKEY_CARLES"): {
        "nom": "Carles",
        "rol": "usuari"
    },
    getenv("APIKEY_SYLVAIN"): {
        "nom": "Sylvain",
        "rol": "usuari"
    },
    getenv("APIKEY_IT"): {
        "nom": "IT",
        "rol": "usuari"
    }
}

APIKEY_EXTERNAL = getenv("APIKEY_EXTERNAL")

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

BLOCKED_IPS = []
FAILED_ATTEMPTS = {}