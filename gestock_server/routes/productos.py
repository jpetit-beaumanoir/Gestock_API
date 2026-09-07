import logging

from fastapi import (
    APIRouter,
    Depends,
    File,
    Form,
    HTTPException,
    Request,
    UploadFile,
    status
)
from starlette.concurrency import run_in_threadpool

from gestock_server.schemas.producto import (
    MessageResponse,
    ProductosGetResponse
)
from gestock_server.security.permissions import require_role
from gestock_server.services import productos_service


logger = logging.getLogger(__name__)


router = APIRouter(
    prefix="/gestock/producto",
    tags=["Productos"],
    dependencies=[
        Depends(require_role("usuari"))
    ]
)


@router.get(
    "",
    response_model=ProductosGetResponse
)
async def get_product_values(
    request: Request,
    ean: str,
    codemag: int
):
    try:
        result = await run_in_threadpool(
            productos_service.get_products_values,
            ean,
            codemag
        )

        logger.info(
            "%s HA OBTINGUT ELS VALORS DEL PRODUCTE %s (%s)",
            request.state.user,
            ean,
            request.client.host if request.client else "desconegut"
        )

        return result

    except ConnectionError as exc:
        logger.exception(
            "ERROR DE BD OBTENINT INFORMACIÓ DEL PRODUCTE %s",
            ean
        )

        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Error de connexió amb la base de dades"
        ) from exc


@router.post(
    "/upload",
    response_model=MessageResponse
)
async def upload_productos_route(
    request: Request,
    csv_file: UploadFile = File(...),
    marca: str = Form(...)
):
    return await productos_service.upload_productos(
        csv_file=csv_file,
        marca=marca
    )