from fastapi import APIRouter, Depends, Request, HTTPException, status
from gestock_server.services import cajas_service
from gestock_server.schemas.caja import (
    CajasGetResponse,
    CajaCreateRequest,
    MessageResponse, 
    CajaGetDescTempResponse, 
    CajaUpdateDescTempRequest,
    CajaUpdateCantidadRequest
)
from gestock_server.security.permissions import require_role

import logging
logger = logging.getLogger(__name__)

router = APIRouter(
    prefix="/gestock/cajas",
    tags=["Cajas"],
    dependencies=[
        Depends(require_role("usuari"))
    ]
)

@router.get("",response_model=CajasGetResponse)
async def get_caixes(
    request:Request,
    almacen: int,
    palet: int
):   

    try:
        result = cajas_service.get_cajas(
            almacen=almacen,
            palet=palet
        )
        
        logger.info(f"{request.state.user} HA LLISTAT LES {len(result.cajas)} CAIXES DEL PALET {palet} MAGATZEM {almacen} ({request.client.host})")

        return result

    except ConnectionError:
        logger.error(
            f"ERROR DE BD OBTENINT LLISTA DE CAIXES DEL PALET {palet} MAGATZEM {almacen}"
        )

        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Error de conexió amb la base de dades"
        )

@router.post("/create",response_model=MessageResponse)
async def create_caixa(
    request: Request,
    data: CajaCreateRequest
):
    try:
    
        result = cajas_service.create_caja(
            almacen=data.almacen,
            palet=data.palet
        )

        logger.info(
            f"{request.state.user} {result.message} ({request.client.host})"
        )

        return MessageResponse(
            message="Caixa creada correctament"
        )

    except ConnectionError:

        logger.error(
            f"ERROR DE BD CREANT UNA NOVA CAIXA AL PALET {data.palet} ALMACÉN {data.almacen} ({request.client.host})"
        )

        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Error de conexió amb la base de dades"
        )

@router.delete("/delete",response_model=MessageResponse)
async def delete_caixa(
    request: Request,
    almacen: int,
    palet: int,
    caja: int
):
    
    try:
        
        result = cajas_service.delete_caja(
            almacen=almacen,
            palet=palet,
            caja=caja
        )

        logger.info(
            f"{request.state.user} HA ELIMINAT LA CAIXA {caja} DEL PALET {palet} DEL MAGATZEM {almacen} ({request.client.host})"
        )

        return result
    
    except ValueError:

        logger.warning(f"{request.state.user} HA INTENTAT ELIMINAR LA CAIXA {caja} DEL PALET {palet} DEL MAGATZEM {almacen} AMB PRODUCTES A DINTRE ({request.client.host})")

        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=f"Buida la caixa abans d'eliminar-la"
        )

    except ConnectionError:

        logger.error(
            f"ERROR DE BD ELIMINANT LA CAIXA {caja} DEL PALET {palet} DEL MAGATZEM {almacen} ({request.client.host})"
        )

        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Error de conexió amb la base de dades"
        )

@router.get("/get-desc-temp",response_model=CajaGetDescTempResponse)
async def get_desc_temp_caja(
    request: Request,
    almacen: int,
    palet: int,
    caja: int
):
    try:
    
        result = cajas_service.get_desc_temp_caja(
            almacen=almacen,
            palet=palet,
            caja=caja
        )

        logger.info(
            f"{request.state.user} HA OBTINGUT LA DESCRIPCIÓ I TEMPORADA DE LA CAIXA {caja} DEL PALET {palet} DEL MAGATZEM {almacen} ({request.client.host})"
        )

        return result

    except ValueError:

        logger.warning(f"{request.state.user} HA INTENTAT OBTENIR LA DESCRIPCIÓ I TEMPORADA DE LA CAIXA {caja} DEL PALET {palet} DEL MAGATZEM {almacen} QUE NO EXISTEIX ({request.client.host})")

        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"La caixa {caja} del palet {palet} del magatzem {almacen} no existeix"
        )

    except ConnectionError:

        logger.error(
            f"ERROR DE BD OBTENINT LA DESCRIPCIÓ I TEMPORADA DE LA CAIXA {caja} DEL PALET {palet} DEL MAGATZEM {almacen} ({request.client.host})"
        )

        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Error de conexió amb la base de dades"
        )

@router.post("/update-desc-temp",response_model=MessageResponse)
async def update_desc_temp_caja(
    request: Request,
    data: CajaUpdateDescTempRequest,
):
    try:
    
        result = cajas_service.update_desc_temp_caja(
            almacen=data.almacen,
            palet=data.palet,
            caja=data.caja,
            descripcion=data.descripcion,
            temporada=data.temporada
        )

        logger.info(
            f"{request.state.user} HA ACTUALITZAT LA DESCRIPCIÓ I TEMPORADA DE LA CAIXA {data.caja} DEL PALET {data.palet} DEL MAGATZEM {data.almacen} ({request.client.host})"
        )

        logger.info(f"Descripció: {data.descripcion}, Temporada: {data.temporada} -> {result.message}")

        return result

    except ValueError:
    
            logger.warning(f"{request.state.user} HA INTENTAT OBTENIR LA DESCRIPCIÓ I TEMPORADA DE LA CAIXA {data.caja} DEL PALET {data.palet} DEL MAGATZEM {data.almacen} QUE NO EXISTEIX ({request.client.host})")
    
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"La caixa {data.caja} del palet {data.palet} del magatzem {data.almacen} no existeix"
            )

    except ConnectionError:

        logger.error(
            f"ERROR DE BD ACTUALITZANT LA DESCRIPCIÓ I TEMPORADA DE LA CAIXA {data.caja} DEL PALET {data.palet} DEL MAGATZEM {data.almacen} ({request.client.host})"
        )

        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Error de conexió amb la base de dades"
        )

@router.post("/update-cantidad", response_model=MessageResponse)
async def update_cantidad_caja(
    request: Request,
    data: CajaUpdateCantidadRequest
):
    try:
    
        result = cajas_service.update_cantidad_caja(
            almacen=data.almacen,
            palet=data.palet,
            caja=data.caja
        )

        logger.info(
            f"{request.state.user} HA ACTUALITZAT LA CANTITAT DE LA CAIXA {data.caja} DEL PALET {data.palet} DEL MAGATZEM {data.almacen} ({request.client.host})"
        )

        return result

    except ConnectionError:

        logger.error(
            f"ERROR DE BD ACTUALITZANT LA CANTITAT DE LA CAIXA {data.caja} DEL PALET {data.palet} DEL MAGATZEM {data.almacen} ({request.client.host})"
        )

        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Error de conexió amb la base de dades"
        )