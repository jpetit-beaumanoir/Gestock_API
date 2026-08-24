from fastapi import APIRouter, Depends, Request, HTTPException, status

from gestock_server.services import auth_service
from gestock_server.security.permissions import require_role
from gestock_server.schemas.auth import AuthUserResponse

import logging

router = APIRouter(
    prefix="/gestock",
    tags=["Auth"],
    dependencies=[
        Depends(require_role("limitat"))
    ]
)

@router.get("/user",response_model=AuthUserResponse)
async def validar_user(
    request: Request,
    key:str
):
    try:
        result = auth_service.validar_user(key=key)
        logging.info(f"USUARI {request.state.user} REGISTRAT DESDE {request.client.host}")

        return result

    except ValueError:
    
        logging.warning(f"INTENT DE REGISTRAR USUARI DESDE {request.client.host}")

        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="CLAU INCORRECTA")
    