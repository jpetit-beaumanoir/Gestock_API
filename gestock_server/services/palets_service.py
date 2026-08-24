from gestock_server.db.database import db_pool
from gestock_server.schemas.palet import (
    PaletInfo,
    PaletsGetResponse,
    MessageResponse
)

from fastapi import status, HTTPException

import logging
import pymssql

def get_palets(almacen: int) -> PaletsGetResponse:
    """
    Obtiene la información de los palets en un almacén específico.

    Este endpoint consulta la base de datos para obtener los palets de un almacén determinado 
    y la cantidad de cajas y productos en cada palet. Si la consulta es exitosa, devuelve un 
    objeto con la información de cada palet, incluyendo el número de cajas y la cantidad total de productos.
    
    Args:
        almacen (int): El código del almacén para obtener los palets asociados.

    Returns:
        PaletResponse: Un diccionario con la información de los palets, incluyendo la cantidad de cajas 
                       y productos en cada palet, así como el número total de palets.

    Raises:
        HTTPException: Lanza 404 si no encuentra palets en el almacén especificado.
        HTTPException: Lanza un error personalizado si ocurre un problema con la base de datos.
    """
    try:

        # Obtiene una conexión al pool de base de datos
        with db_pool.get_connection() as conn:
            with conn.cursor() as cursor:
                # Ejecuta la consulta para obtener los palets del almacén especificado
                cursor.execute("SELECT palet FROM palets WHERE almacen = %s", (almacen,))
                palets = cursor.fetchall()

                if not palets:
                    return PaletsGetResponse(
                        palets={},
                        total=0
                    )

                data = {}
                
                # Para cada palet obtenido, obtenemos la cantidad de cajas y productos
                for palet_row in palets:
                    palet_id = palet_row[0]  # Extrae el ID del palet

                    # Ejecuta una consulta para obtener la cantidad de cajas y la cantidad total de productos del palet
                    cursor.execute(
                        """SELECT 
                                COUNT(DISTINCT c.caja), 
                                COUNT(s.ean) 
                            FROM cajas c
                            LEFT JOIN stock s 
                                ON c.caja = s.caja 
                                AND c.palet = s.palet 
                                AND c.almacen = s.almacen 
                            WHERE c.almacen = %s 
                                AND c.palet = %s""",
                        (almacen, palet_id)
                    )
                    cajas, cantidad = cursor.fetchone()
                    
                    # Almacena la información del palet en el diccionario de respuesta
                    data[str(palet_id)] = PaletInfo(
                        cajas=cajas,
                        cantidad=cantidad or 0
                    )

            return PaletsGetResponse(
                palets=data,
                total=len(palets)
            )

    except pymssql.Error as e:
        # Si ocurre un error en la base de datos, se maneja de manera consistente
        logging.critical(f"ERROR SQL: {e}")
        raise ConnectionError("Error de la base de dades")
  
def create_palet(almacen: int) -> MessageResponse:
    """
    Crea un nuevo palet en un almacén específico.

    Este endpoint crea un palet nuevo en un almacén dado. Si no hay palets existentes, el primer palet 
    se creará con el ID 1. Si ya existen palets, se seleccionará el menor ID faltante. Si el ID propuesto 
    ya existe, se generará un error de conflicto.

    Args:
        almacen (int): El código del almacén en el que se desea crear el palet.

    Returns:
        MessageResponse: Un mensaje que confirma la creación del palet con su ID y almacén.

    Raises:
        HTTPException: Lanza un error si ya existe un palet con el ID seleccionado o si ocurre un error 
                        con la base de datos durante la creación del palet.
    """
    try:

        # Obtiene una conexión al pool de base de datos
        with db_pool.get_connection() as conn:
            with conn.cursor() as cursor:
                # Ejecuta una consulta para encontrar el menor ID faltante para el palet
                cursor.execute(""" 
                    SELECT MIN(palet)
                    FROM (
                        SELECT palet + 1 AS palet 
                        FROM palets 
                        WHERE almacen = %s      
                        UNION      
                        SELECT 1 AS palet
                    ) AS posibles_id 
                    WHERE palet NOT IN (
                        SELECT palet 
                        FROM palets 
                        WHERE almacen = %s
                    )
                """, (almacen,almacen,))
                result = cursor.fetchone()
                next_id = result[0] if result else None

                # Si no hay palets en la tabla, comenzamos desde el ID 1
                if next_id is None:
                    next_id = 1

                # Verificar si el palet con el siguiente ID ya existe en el almacén
                cursor.execute("SELECT COUNT(*) FROM palets WHERE palet = %s AND almacen = %s", (next_id, almacen))
                if cursor.fetchone()[0] > 0:
                    # Si ya existe, se lanza un error de conflicto
                    raise HTTPException(
                        status_code=status.HTTP_409_CONFLICT,
                        detail=f"Ya existe un palet con el código {next_id} en el almacén {almacen}"
                    )

                # Inserta el nuevo palet en la base de datos
                cursor.execute("INSERT INTO palets (palet, almacen) VALUES (%s, %s)", (next_id, almacen))
                conn.commit()

            
                logging.info(f"CREADO PALET {next_id} EN EL ALMACÉN {almacen}")
                return MessageResponse(
                    message=f"Palet {next_id} creado"
                )
                
    except pymssql.IntegrityError:
        # Maneja errores de integridad como cuando ya existe un almacén con el mismo código
        raise ValueError(f"Ja existeix un palet amb codi {next_id}")
        
    except pymssql.Error as e:
        # Si ocurre un error en la base de datos, se maneja de manera consistente
        logging.critical(f"ERROR SQL: {e}")
        raise ConnectionError("Error de base de dades")

def delete_palet(almacen: int, palet: int) -> MessageResponse:
    """
    Elimina un palet específico de un almacén.
    
    Este endpoint verifica si el palet tiene cajas asociadas antes de permitir su eliminación. Si el palet 
    tiene cajas, se lanzará un error. Si el palet no existe o no se encuentra en el almacén, se genera un 
    error 404.

    Args:
        almacen (int): El código del almacén donde se encuentra el palet.
        palet (int): El ID del palet que se desea eliminar.

    Returns:
        MessageResponse: Un mensaje confirmando la eliminación del palet.

    Raises:
        HTTPException: Lanza un error 409 si el palet tiene cajas asociadas, 
                        un error 404 si el palet no se encuentra, 
                        o un error 500 si hay un problema con la base de datos.
    """
    try:

        # Obtiene una conexión al pool de base de datos
        with db_pool.get_connection() as conn:
            with conn.cursor() as cursor:
                # Verifica si el palet tiene cajas asociadas en el almacén
                cursor.execute("SELECT COUNT(*) FROM cajas WHERE palet = %s AND almacen = %s", (palet, almacen))
                cajas_count = cursor.fetchone()[0]
                
                # Si el palet tiene cajas, no se puede eliminar
                if cajas_count > 0:
                    raise ValueError(f"No se puede eliminar el palet {palet} porque tiene {cajas_count} cajas asociadas.")
                
                # Si no tiene cajas asociadas, proceder a eliminar el palet
                cursor.execute("DELETE FROM palets WHERE palet = %s AND almacen = %s", (palet, almacen))
                conn.commit()

                # Si la eliminación fue exitosa, devolver un mensaje de éxito
                return MessageResponse(message=f"Palet {palet} eliminado")

    except pymssql.Error as e:
        # Si ocurre un error en la base de datos, se maneja de manera consistente
        logging.critical(f"ERROR SQL: {e}")
        raise ConnectionError("Error de la base de dades")