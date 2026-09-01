from fastapi import APIRouter, Depends, Request, HTTPException, status
from gestock_server.services import familias_service
from gestock_server.schemas.familia import (
    FamiliasGetResponse
)
from gestock_server.security.permissions import require_role

import logging
logger = logging.getLogger(__name__)

router = APIRouter(
    prefix="/gestock/familias",
    tags=["Familias"],
    dependencies=[
        Depends(require_role("usuari"))
    ]
)

@router.get("",response_model=FamiliasGetResponse)
async def get_familias(
    request: Request
):
    try:
        result = familias_service.get_familias()
        
        logger.info(f"{request.state.user} HA CONSULTAT LES FAMILIAS DE PRODUCTES ({request.client.host})")

        return result

    except ConnectionError:
        logger.error(
            f"ERROR DE BD OBTENINT LES FAMILIAS DE PRODUCTES ({request.client.host})"
        )

        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Error de conexió amb la base de dades"
        )