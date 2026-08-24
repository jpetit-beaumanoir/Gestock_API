from gestock_server.config import API_KEYS
from gestock_server.schemas.auth import AuthUserResponse

from fastapi import status, HTTPException

def validar_user(key: str) -> AuthUserResponse:
    if key in API_KEYS.keys():        
        return AuthUserResponse(
            user=API_KEYS[key]["nom"]
        )

    else:
        return ValueError("CLAU INCORRECTA")