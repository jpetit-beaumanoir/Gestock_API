from fastapi import APIRouter, Depends, Request, HTTPException, status

from gestock_server.services import almacenes_service
from gestock_server.schemas.almacen import (
    AlmacenResponse, 
    AlmacenLoginResponse, 
    AlmacenCreateRequest,
    MessageResponse
)
from gestock_server.security.permissions import require_role

import logging
logger = logging.getLogger(__name__)

router = APIRouter(
    prefix="/gestock/almacenes",
    tags=["Almacenes"],
    dependencies=[
        Depends(require_role("usuari"))
    ]
)

@router.get("",response_model=AlmacenResponse)
async def get_almacenes(request: Request):

    try:

        result = almacenes_service.get_almacenes()

        logger.info(f"{request.state.user} HA CONSULTAT ELS MAGATZEMS EXISTENTS ({request.client.host})")

        return result

    except ConnectionError:
        logger.error(
            f"ERROR DE BD OBTENINT ELS MAGATZEMS"
        )

        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Error de conexió amb la base de dades"
        )


@router.get("/login",response_model=AlmacenLoginResponse)
async def login_almacen(
    request: Request, 
    codigo: int
):

    try:
        result = almacenes_service.login_almacen(codigo)
        logger.info(f"{request.state.user} HA ACCEDIT AL MAGATZEM {codigo} ({request.client.host})")

        return result
        
    except ValueError:
        logger.warning(f"{request.state.user} INTENT D'ACCEDIR A UN MAGATZEM INNEXISTENT {codigo} ({request.client.host})")

        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"No existeix un magatzem amb codi {codigo}"
        )

    except ConnectionError:
        logger.error(
            f"ERROR DE BD FENT LOGIN AL MAGATZEM {codigo}"
        )

        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Error de conexió amb la base de dades"
        )
    

@router.post("/create", response_model=MessageResponse)
async def crear_almacen(
    request: Request,
    data: AlmacenCreateRequest
):
    try:

        result = almacenes_service.create_almacen(
            nombre=data.nombre,
            codigo=data.codigo
        )

        logger.info(
            f"{request.state.user} HA CREAT EL MAGATZEM {data.codigo} ({request.client.host})"
        )

        return result

    except ValueError:

        logger.warning(
            f"{request.state.user} HA INTENTAT CREAR UN MAGATZEM DUPLICAT {data.codigo} ({request.client.host})"
        )

        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=f"Ja existeix un magatzem amb codi {data.codigo}"
        )

    except ConnectionError:

        logger.error(
            f"ERROR DE BD CREANT EL MAGATZEM {data.codigo}"
        )

        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Error de conexió amb la base de dades"
        )
     
@router.delete("/delete", response_model=MessageResponse)
async def delete_almacen(
    request: Request, 
    codigo: int
):
    try:
    
        result = almacenes_service.delete_almacen(codigo)

        logger.info(
            f"{request.state.user} HA ELIMINAT EL MAGATZEM {codigo} ({request.client.host})"
        )

        return result
    
    except ValueError:

        logger.warning(f"{request.state.user} HA INTENTAT ELIMINAR UN MAGATZEM AMB ELEMENTS A DINTRE {codigo} ({request.client.host})")

        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=f"Buida el magatzem abans d'eliminar-lo"
        )

    except ConnectionError:

        logger.error(
            f"ERROR DE BD ELIMINANT EL MAGATZEM {codigo}"
        )

        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Error de conexió amb la base de dades"
        )