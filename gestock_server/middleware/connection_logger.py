from starlette.middleware.base import BaseHTTPMiddleware
from fastapi import Request, HTTPException, status

import logging


class ConnectionResetLoggerMiddleware(BaseHTTPMiddleware):
    """
    Middleware que intercepta errores de conexión reiniciada por el cliente,
    y evita que se impriman trazas largas en los logs.
    """

    async def dispatch(self, request: Request, call_next):
        try:
            return await call_next(request)
        except ConnectionResetError:
            client_ip = request.client.host
            logging.warning(f"Conexión perdida con el cliente ({client_ip}) antes de enviar respuesta")
            raise HTTPException(
                status_code=status.HTTP_406_NOT_ACCEPTABLE
            )
            
        except Exception as e:
            raise e