from fastapi import APIRouter, Depends, Request, HTTPException, status
from gestock_server.services import stock_service
from gestock_server.schemas.stock import (
    StockGetResponse, 
    MessageResponse, 
    StockAddRequest, 
    StockDeleteRequest, 
    StockMoveRequest,
    StockExportResponse
)
from gestock_server.security.permissions import require_role

import logging

router = APIRouter(
    prefix="/gestock/stock",
    tags=["Stock"],
    dependencies=[
        Depends(require_role("usuari"))
    ]
)

@router.get("",response_model=StockGetResponse)
async def get_stock_caja(
    request: Request,
    almacen: int,
    palet: int,
    caja: int
):
    try:
        result = stock_service.get_stock_caja(
            almacen=almacen,
            palet=palet,
            caja=caja
        )
        
        logging.info(f"{request.state.user} HA CONSULTAT EL STOCK DE LA CAIXA {caja} DEL PALET {palet} EN EL MAGATZEM {almacen} ({request.client.host})")

        return result

    except ConnectionError:
        logging.error(
            f"ERROR DE BD OBTENINT STOCK DE LA CAIXA {caja} DEL PALET {palet} EN EL MAGATZEM {almacen} ({request.client.host})"
        )

        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Error de conexió amb la base de dades"
        )

@router.post("/add",response_model=MessageResponse)
async def add_stock(
    request: Request,
    data: StockAddRequest
):
    try:
        result = await stock_service.add_stock(
            body=data
        )

        logging.info(
            f"{request.state.user} HA AFEGIT {len(data.eans)} PRODUCTES A LA CAIXA {data.caja} DEL PALET {data.palet} EN EL MAGATZEM {data.almacen} ({request.client.host})"
        )

        return result

    except ValueError as e:
        logging.warning(
            f"{request.state.user} HA INTENTAT AFEGIR STOCK SENSE EANS ({request.client.host})"
        )
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST, 
            detail=str(e)
        )

    except ConnectionError:
        logging.error(
            f"ERROR DE BD AFEGINT STOCK A LA CAIXA {data.caja} DEL PALET {data.palet} EN EL MAGATZEM {data.almacen} ({request.client.host})"
        )

        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Error de conexió amb la base de dades"
        )

@router.post("/delete",response_model=MessageResponse)
async def delete_stock(
    request: Request,
    data: StockDeleteRequest
):
    try:
        result = await stock_service.delete_stock(
            body=data
        )

        logging.info(
            f"{request.state.user} HA ELIMINAT {len(data.ids)} PRODUCTES DE LA CAIXA {data.caja} DEL PALET {data.palet} EN EL MAGATZEM {data.almacen} ({request.client.host})"
        )

        return result

    except ValueError as e:
        logging.warning(
            f"{request.state.user} HA INTENTAT ELIMINAR STOCK SENSE EANs ({request.client.host})"
        )
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST, 
            detail=str(e)
        )

    except ConnectionError:
        logging.error(
            f"ERROR DE BD ELIMINANT STOCK DE LA CAIXA {data.caja} DEL PALET {data.palet} EN EL MAGATZEM {data.almacen} ({request.client.host})"
        )

        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Error de conexió amb la base de dades"
        )

@router.post("/move",response_model=MessageResponse)
async def move_stock(
    request: Request,
    data: StockMoveRequest
):
    try:
        result = await stock_service.move_stock(
            body=data
        )

        logging.info(
            f"{request.state.user} HA MOGUT {len(data.ids)} PRODUCTES DE LA CAIXA {data} DEL PALET {data} EN EL MAGATZEM {data.almacen} ({request.client.host})"
        )

        return result

    except ValueError as e:
        logging.warning(
            f"{request.state.user} HA INTENTAT MOURE STOCK SENSE EANs ({request.client.host})"
        )
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST, 
            detail=str(e)
        )

    except ConnectionError:
        logging.error(
            f"ERROR DE BD MOVENT STOCK DE LA CAIXA {data.caja} DEL PALET {data.palet} EN EL MAGATZEM {data.almacen} ({request.client.host})"
        )

        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Error de conexió amb la base de dades"
        )

@router.get("/export",response_model=StockExportResponse)
async def export_stock(
    request: Request,
    almacen: int,
    ean: str | None = None,
    talla: str | None = None,
    nombre: str | None = None,
    familia: str | None = None,
    color: str | None = None,
    temporada: str | None = None
):
    try:
        result = stock_service.filtered_search(
            StockExportRequest(
                almacen = almacen,
                ean = ean,
                talla = talla,
                nombre = nombre,
                familia = familia,
                color = color,
                temporada = temporada
            )
        )
        
        logging.info(f"{request.state.user} HA EXPORTAT STOCK DEL MAGATZEM {almacen} ({request.client.host})")

        return result

    except ConnectionError:
        logging.error(
            f"ERROR DE BD EXPORTANT STOCK DEL MAGATZEM {almacen} ({request.client.host})"
        )

        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Error de conexió amb la base de dades"
        )
