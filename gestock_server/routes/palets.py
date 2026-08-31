from fastapi import APIRouter, Depends, Request, HTTPException, status
from gestock_server.services import palets_service
from gestock_server.schemas.palet import (
    PaletsGetResponse,
    PaletCreateRequest,
    MessageResponse
)
from gestock_server.security.permissions import require_role

import logging

router = APIRouter(
    prefix="/gestock/palets",
    tags=["Palets"],
    dependencies=[
        Depends(require_role("usuari"))
    ]
)

@router.get("",response_model=PaletsGetResponse)
async def get_palets(
    request:Request,
    almacen = int
):   

    try:
        result = palets_service.get_palets(
            almacen
        )
        
        logging.info(f"{request.state.user} HA LLISTAT {result.total} PALETS DEL MAGATZEM {almacen} ({request.client.host})")

        return result

    except ConnectionError:
        logging.error(
            f"ERROR DE BD OBTENINT ELS PALETS DEL MAGATZEM {almacen} ({request.client.host})"
        )

        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Error de conexió amb la base de dades"
        )

@router.post("/create",response_model=MessageResponse)
async def create_palet(
    request: Request,
    data: PaletCreateRequest
):
    try:
    
        result = palets_service.create_palet(
            data.almacen
        )

        logging.info(
            f"{request.state.user} HA CREAT EL PALET {data.almacen} ({request.client.host})"
        )

        return result

    except ValueError as e:

        logging.warning(
            f"{request.state.user} S'HA INTENTAT CREAR UN PALET DUPLICAT AL MAGATZEM {data.almacen} ({request.client.host})"
        )

        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail= setattr(e)
        )

    except ConnectionError:

        logging.error(
            f"ERROR DE BD CREANT EL PALET"
        )

        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Error de conexió amb la base de dades"
        )

@router.delete("/delete",response_model=MessageResponse)
async def delete_palet(
    request: Request,
    almacen: int,
    palet: int
):
    
    try:
        
        result = palets_service.delete_palet(almacen,palet)

        logging.info(
            f"{request.state.user} HA ELIMINAT EL PALET {palet} DEL MAGATZEM {almacen} ({request.client.host})"
        )

        return result
    
    except ValueError:

        logging.warning(f"{request.state.user} HA INTENTAT ELIMINAR EL  PALET {palet} DEL MAGATZEM {almacen} AMB CAIXES A DINTRE ({request.client.host})")

        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=f"Buida el palet abans d'eliminar-lo"
        )

    except ConnectionError:

        logging.error(
            f"ERROR DE BD ELIMINANT EL PALET {palet} DEL MAGATZEM {almacen}"
        )

        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Error de conexió amb la base de dades"
        )