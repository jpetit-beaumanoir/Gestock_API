from fastapi import APIRouter, Depends, Request, HTTPException, status
from gestock_server.services import temporadas_service
from gestock_server.schemas.temporada import (
    TemporadasGetResponse
)
from gestock_server.security.permissions import require_role

import logging

router = APIRouter(
    prefix="/gestock/temporadas",
    tags=["Temporadas"],
    dependencies=[
        Depends(require_role("usuari"))
    ]
)

@router.get("",response_model=TemporadasGetResponse)
async def get_temporadas(
    request: Request
):
    try:
        result = temporadas_service.get_temporadas()
        
        logging.info(f"{request.state.user} HA CONSULTAT LES TEMPORADES ({request.client.host})")

        return result

    except ConnectionError:
        logging.error(
            f"ERROR DE BD OBTENINT LES TEMPORADES ({request.client.host})"
        )

        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Error de conexió amb la base de dades"
        )