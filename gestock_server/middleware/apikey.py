from fastapi import status, Request
from fastapi.responses import JSONResponse
from starlette.concurrency import run_in_threadpool
from starlette.middleware.base import BaseHTTPMiddleware

import logging
logger = logging.getLogger(__name__)

from gestock_server.config import (
    HEADER_NAME,
    MAX_FAILED_ATTEMPTS,
    PUBLIC_ROUTES,
    FAILED_ATTEMPTS,
    BLOCKED_IPS,
    BLOCKED_IPS_FILE,
)
from gestock_server.services.usuaris_service import validar_api_key


def _client_ip(request: Request) -> str:
    """
    IP del cliente. Si hay un proxy delante (X-Forwarded-For), la primera IP de la lista
    es la del cliente original.
    """
    forwarded = request.headers.get("X-Forwarded-For")
    if forwarded:
        return forwarded.split(",")[0].strip()
    return request.client.host if request.client else "desconeguda"


class APIKeyMiddleware(BaseHTTPMiddleware):
    """
    Autentica cada petición con la API key de la cabecera HEADER_NAME, validándola contra
    la tabla usuaris de la BDD (ver services/usuaris_service.py).

    - Sin clave, o con una clave que no está en usuaris (o de un usuario desactivado): se deniega
      y se cuenta como intento fallido para esa IP.
    - Al llegar a MAX_FAILED_ATTEMPTS intentos fallidos, la IP queda bloqueada (también tras
      reiniciar, se guarda en BLOCKED_IPS_FILE).
    - Si la BDD no responde se devuelve 503 y NO se cuenta como intento fallido
      (no se bloquea a usuarios legítimos por una caída de la BDD).
    - Con una clave válida se guardan en request.state: user, rol e id_usuari.
    """

    async def dispatch(self, request: Request, call_next):

        if request.url.path in PUBLIC_ROUTES:
            return await call_next(request)

        client_ip = _client_ip(request)

        # IP bloqueada
        if client_ip in BLOCKED_IPS:
            logger.warning(f"Acceso bloqueado desde IP: {client_ip}, URL {request.url.path}")
            return JSONResponse(
                status_code=status.HTTP_401_UNAUTHORIZED,
                content={"detail": "IP bloqueada"}
            )

        api_key = request.headers.get(HEADER_NAME)

        # Sin API key: se deniega directamente
        if not api_key or not api_key.strip():
            logger.warning(f"Petición sin API Key: IP {client_ip}, URL {request.url.path}")
            return self._intento_fallido(client_ip, "Falta la API Key")

        # Validación contra la BDD (en un hilo: la consulta es síncrona)
        try:
            usuario = await run_in_threadpool(validar_api_key, api_key)

        except ConnectionError:
            logger.error(f"No se puede validar la API Key (BDD no disponible): IP {client_ip}")
            return JSONResponse(
                status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                content={"detail": "Servicio no disponible. Intente más tarde."}
            )

        # Clave que no está en usuaris (o usuario desactivado / de otra aplicación)
        if usuario is None:
            logger.warning(f"Intento de acceso con API Key no válida: IP {client_ip}, URL {request.url.path}")
            return self._intento_fallido(client_ip, "Acceso denegado: API Key incorrecta")

        # Clave válida: se reinicia el contador de fallos de la IP
        FAILED_ATTEMPTS.pop(client_ip, None)

        request.state.user = usuario.nom
        request.state.rol = usuario.rol
        request.state.id_usuari = usuario.id_usuari

        return await call_next(request)

    @staticmethod
    def _intento_fallido(client_ip: str, detalle: str) -> JSONResponse:
        """Cuenta un intento fallido y bloquea la IP si llega al máximo."""
        FAILED_ATTEMPTS[client_ip] = FAILED_ATTEMPTS.get(client_ip, 0) + 1

        if FAILED_ATTEMPTS[client_ip] >= MAX_FAILED_ATTEMPTS:
            BLOCKED_IPS.add(client_ip)
            try:
                with open(BLOCKED_IPS_FILE, 'a', encoding='utf-8') as archivo:
                    archivo.write(client_ip + '\n')
            except OSError as e:
                logger.error(f"No s'ha pogut guardar la IP bloquejada a {BLOCKED_IPS_FILE}: {e}")
            logger.warning(f"IP bloqueada automáticamente tras {FAILED_ATTEMPTS[client_ip]} intentos: {client_ip}")
            return JSONResponse(
                status_code=status.HTTP_401_UNAUTHORIZED,
                content={"detail": "IP bloqueada tras múltiples intentos fallidos"}
            )

        return JSONResponse(
            status_code=status.HTTP_403_FORBIDDEN,
            content={"detail": detalle}
        )
