from fastapi import status, Request
from fastapi.responses import JSONResponse
from starlette.middleware.base import BaseHTTPMiddleware

import logging

from gestock_server.config import API_KEYS, HEADER_NAME, MAX_FAILED_ATTEMPTS, FAILED_ATTEMPTS, BLOCKED_IPS_FILE, BLOCKED_IPS, PUBLIC_ROUTES

class APIKeyMiddleware(BaseHTTPMiddleware):
    """
    Middleware para autenticar solicitudes mediante una API Key.

    Este middleware:
    - Verifica que la solicitud incluya una API Key válida en los headers.
    - Registra los intentos fallidos por IP.
    - Bloquea automáticamente las IPs que superen un número máximo de intentos fallidos.
    - Deniega el acceso a las IPs previamente bloqueadas.
    """

    async def dispatch(self, request: Request, call_next):
        """
        Intercepta cada solicitud HTTP antes de llegar a la ruta destino.

        Verifica:
        - Si la IP está bloqueada, retorna error 401.
        - Si la API Key es incorrecta, registra el intento fallido y bloquea la IP si excede el límite.
        - Si la API Key es correcta, permite que la solicitud continúe normalmente.

        Args:
            request (Request): La solicitud HTTP entrante.
            call_next (Callable): Función para pasar la solicitud al siguiente middleware o endpoint.

        Returns:
            Response: Respuesta HTTP, que puede ser un error o la respuesta normal del endpoint.
        """

        if request.url.path in PUBLIC_ROUTES:
            # Permitir acceso a rutas públicas sin necesidad de API Key
            return await call_next(request)

        # Obtener la IP del cliente, respetando posibles proxies
        client_ip = request.headers.get("X-Forwarded-For", request.client.host)

        # Extraer la API Key del encabezado
        api_key = request.headers.get(HEADER_NAME)

        # Verificar si la IP ya está bloqueada
        if client_ip in BLOCKED_IPS:
            
            logging.warning(f"Acceso bloqueado desde IP: {client_ip}, URL {request.url}")
            return JSONResponse(
                status_code=status.HTTP_401_UNAUTHORIZED,
                content={"detail": "IP bloqueada"}
            )

        

        # Verificar si la API Key es válida
        if api_key not in API_KEYS:
            
            # Registrar intento fallido
            logging.warning(f"Intento de acceso sin API Key válida: IP {client_ip}, URL {request.url}")

            # Incrementar el contador de intentos fallidos
            FAILED_ATTEMPTS[client_ip] = FAILED_ATTEMPTS.get(client_ip, 0) + 1

            # Si se superó el máximo de intentos, bloquear la IP
            if FAILED_ATTEMPTS[client_ip] >= MAX_FAILED_ATTEMPTS:
                BLOCKED_IPS.append(client_ip)
                with open(BLOCKED_IPS_FILE, 'a', encoding='utf-8') as archivo:
                    archivo.write(client_ip + '\n')
                logging.warning(f"Acceso bloqueado desde IP: {client_ip}, URL {request.url}")
                logging.warning(f"IP bloqueada automáticamente tras múltiples intentos: {client_ip}")
                return JSONResponse(
                    status_code=status.HTTP_401_UNAUTHORIZED,
                    content={"detail": "IP bloqueada tras múltiples intentos fallidos"}
                )

            # Si aún no supera el límite, denegar con advertencia
            return JSONResponse(
                status_code=403,
                content={"detail": "Acceso denegado: API Key incorrecta"}
            )

        # Si la API Key es válida, permitir la solicitud
        request.state.user = API_KEYS[api_key]["nom"]
        request.state.rol = API_KEYS[api_key]["rol"]
        return await call_next(request)