from fastapi import APIRouter, Depends, Request, HTTPException, status
from gestock_server.services import productos_service
from gestock_server.schemas.producto import ProductosGetResponse
from gestock_server.security.permissions import require_role

import logging
logger = logging.getLogger(__name__)

router = APIRouter(
    prefix="/gestock/producto",
    tags=["Productos"],
    dependencies=[
        Depends(require_role("usuari"))
    ]
)

@router.get("",response_model=ProductosGetResponse)
async def get_product_values(
    request: Request,
    ean: str,
    codemag: int
):
    try:
        result = productos_service.get_products_values(
            eans = ean,
            codemag = codemag
        )
        
        logger.info(f"{request.state.user} HA OBTINGUT ELS VALORS DEL PRODUCTE {ean} ({request.client.host})")

        return result

    except ConnectionError:
        logger.error(
            f"ERROR DE BD OBTENINT INFORMACIÓ DE PRODUCTES"
        )

        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Error de conexió amb la base de dades"
        )