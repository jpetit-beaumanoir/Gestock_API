from gestock_server.db.database import db_pool
from gestock_server.schemas.caja import (
    CajaExistsDB, 
    CajasGetResponse, 
    CajaInfo, 
    MessageResponse, 
    CajaGetDescTempResponse
)
import pymssql

import logging
logger = logging.getLogger(__name__)

def check_caja_exists(
    almacen: int,
    palet: int,
    caja: int
) -> CajaExistsDB:

    try:
        with db_pool.get_connection() as conn:
            with conn.cursor() as cursor:

                cursor.execute("""
                    SELECT 
                        caja,
                        palet,
                        almacen,
                        temporada,
                        descripcion,
                        cantidad
                    FROM cajas
                    WHERE almacen = %s
                      AND palet = %s
                      AND caja = %s
                """, (almacen, palet, caja))

                row = cursor.fetchone()

                if row is None:
                    raise ValueError(
                        f"La caja {caja} del palet {palet} "
                        f"en el almacén {almacen} no existe"
                    )

                return CajaExistsDB(
                    caja=row[0],
                    palet=row[1],
                    almacen=row[2],
                    temporada=row[3],
                    descripcion=row[4],
                    cantidad=row[5]
                )

    except pymssql.Error as e:
        logger.critical(f"ERROR SQL: {e}")
        raise ConnectionError("Error de la base de dades")


def get_cajas(almacen: int, palet: int) -> CajasGetResponse:
    """
    Obtiene todas las cajas asociadas a un palet específico en un almacén dado.

    Este endpoint permite obtener los detalles de todas las cajas presentes en un palet
    dentro de un almacén. Si no se encuentran cajas asociadas, devuelve 204. Los datos devueltos incluyen la cantidad, descripción y temporada
    de cada caja.

    Args:
        almacen (int): El código del almacén donde se encuentra el palet.
        palet (int): El ID del palet cuyo contenido se desea consultar.

    Returns:
        dict: Un diccionario con las cajas asociadas al palet y su información.
        str: Mensaje informando si no se encontraron cajas asociadas al palet.

    Raises:
        HTTPException: Lanza un error 404 en caso de no encontrar cajas en la base de datos.
        HTTPException: Lanza un error 500 en caso de fallos con la base de datos.
    """
    data = {}

    try:   
            
        with db_pool.get_connection() as conn:
            with conn.cursor() as cursor:
                # Consulta para obtener las cajas asociadas al palet en el almacén
                cursor.execute("""
                               SELECT 
                                c.caja, 
                                COUNT(s.ean) AS cantidad, 
                                c.descripcion, 
                                c.temporada 
                               FROM cajas c
                               LEFT JOIN stock s
                                ON c.caja = s.caja 
                                AND c.palet = s.palet 
                                AND c.almacen = s.almacen
                               WHERE c.almacen = %s 
                               AND c.palet = %s
                               GROUP BY c.caja, c.descripcion, c.temporada
                               ORDER BY c.caja""", (almacen, palet,))
                cajas = cursor.fetchall()

                # Si no se encuentran cajas, devolver un mensaje
                if not cajas:
                    return CajasGetResponse(
                        cajas={}
                    )

                # Construir el diccionario de datos con la información de las cajas
                for row_caja in cajas:
                    caja, cantidad, descripcion, temporada = row_caja

                    data[str(caja)] = CajaInfo(
                        cantidad=cantidad,
                        descripcion=descripcion,
                        temporada=temporada
                    )
                    
                return CajasGetResponse(cajas=data)

    except pymssql.Error as e:
        logger.critical(f"ERROR SQL: {e}")
        raise ConnectionError("Error de la base de dades")

def create_caja(almacen: int, palet: int) -> MessageResponse:
    """
    Crea una nueva caja en un palet dentro de un almacén.

    Este endpoint permite crear una caja en un palet y almacén específicos. La caja será asignada 
    con un ID automáticamente generado. Si ya existe una caja con el mismo ID, se genera un error 
    de conflicto (409). La caja se creará con valores predeterminados para la temporada, descripción
    y cantidad (sin especificar).

    Args:
        almacen (int): El código del almacén donde se desea agregar la caja.
        palet (int): El ID del palet en el cual se agregará la caja.

    Returns:
        dict: Mensaje de éxito si la caja se crea correctamente.

    Raises:
        HTTPException: Lanza un error 400 si no se pudo crear la caja, 
                        o 409 si ya existe una caja con el mismo ID.
    """
    try:

        with db_pool.get_connection() as conn:
            with conn.cursor() as cursor:
                
                # Obtener el siguiente ID de caja disponible (el menor número que no esté usado)
                cursor.execute(""" 
                    SELECT MIN(caja)
                    FROM (
                        SELECT caja + 1 AS caja 
                        FROM cajas 
                        WHERE almacen = %s 
                        AND palet = %s 
                        UNION 
                        SELECT 1 AS caja
                    ) AS posibles 
                    WHERE caja NOT IN (
                        SELECT caja 
                        FROM cajas 
                        WHERE almacen = %s 
                        AND palet = %s
                    )
                """, (almacen, palet, almacen, palet,))
                
                next_id = int(cursor.fetchone()[0])

                existe_caja = True

                while existe_caja:
                    # Verificar si la caja con el ID generado ya existe
                    cursor.execute("SELECT COUNT(*) FROM cajas WHERE caja = %s AND palet = %s AND almacen = %s", (next_id, palet, almacen,))
                    count = cursor.fetchone()[0]
                
                    # Si ya existe una caja con el mismo ID, generar un error de conflicto
                    if count == 0:
                        existe_caja = False
                        break

                    next_id += 1  # Incrementar el ID para buscar el siguiente disponible
                    
                
                # Insertar la nueva caja con valores predeterminados
                cursor.execute(""" 
                    INSERT INTO cajas (caja, palet, almacen, temporada, descripcion, cantidad) 
                    VALUES (%s, %s, %s, 'SIN TEMPORADA', 'SIN DESCRIPCIÓN', %s)
                """, (next_id, palet, almacen, 0))  # Se inicia con cantidad 0 y valores predeterminados

                conn.commit()
   
                return MessageResponse(message=f"HA CREAT LA CAIXA {next_id} EN EL PALET {palet} MAGATZEM {almacen}")

    except pymssql.Error as e:
        logger.critical(f"ERROR SQL: {e}")
        raise ConnectionError("Error de la base de dades")  

def delete_caja(almacen: int, palet: int, caja: int) -> MessageResponse:
    """
    Elimina una caja específica de un palet en un almacén.

    Este endpoint permite eliminar una caja de un palet en un almacén dado. Antes de proceder con la 
    eliminación, se verifica si la caja tiene productos asociados. Si tiene productos, no se puede 
    eliminar la caja y se lanza un error 409. Si la caja no existe en el sistema, se genera un error 
    404. En caso de una eliminación exitosa, se devuelve un mensaje confirmando la eliminación.

    Args:
        almacen (int): El código del almacén donde se encuentra la caja.
        palet (int): El ID del palet que contiene la caja.
        caja (int): El ID de la caja que se desea eliminar.

    Returns:
        dict: Un mensaje confirmando la eliminación de la caja.

    Raises:
        HTTPException: Lanza un error 404 si no se encuentra la caja o un error 409 si la caja tiene productos asociados.
    """
    
    try:

        with db_pool.get_connection() as conn:
            with conn.cursor() as cursor:
                # Verificar si la caja tiene productos asociados
                cursor.execute("SELECT COUNT(*) FROM stock WHERE almacen = %s AND palet = %s AND caja = %s", (almacen, palet, caja,))
                productos_count = cursor.fetchone()[0]

                # Si la caja tiene productos, no permitir la eliminación
                if productos_count > 0:
                    raise ValueError(f"No se puede eliminar la caja {caja} porque tiene {productos_count} productos asociados.")
                
                # Eliminar la caja si no tiene productos asociados
                cursor.execute("DELETE FROM cajas WHERE caja = %s AND palet = %s AND almacen = %s", (caja, palet, almacen,))
                conn.commit()

                return MessageResponse(message=f"Caja {caja} del palet {palet}, almacén {almacen} eliminada")

    except pymssql.Error as e:
        logger.critical(f"ERROR SQL: {e}")
        raise ConnectionError("Error de la base de dades")  

def get_desc_temp_caja(almacen: int, palet: int, caja: int) -> CajaGetDescTempResponse:
    """
    Obtiene la descripción y la temporada de una caja en un palet de un almacén.

    Este endpoint permite obtener la descripción y temporada asociada a una caja específica dentro 
    de un palet en un almacén. Si la caja no existe, se genera un error 404. Si la descripción o 
    la temporada no están especificadas en la base de datos, se asignan valores predeterminados.

    Args:
        almacen (int): El código del almacén donde se encuentra la caja.
        palet (int): El ID del palet que contiene la caja.
        caja (int): El ID de la caja de la que se desea obtener la descripción y la temporada.

    Returns:
        dict: Un diccionario con la descripción y la temporada de la caja.

    Raises:
        HTTPException: Lanza un error 404 si la caja no existe o un error 500 en caso de fallos con la base de datos.
    """
    
    try:

        data = check_caja_exists(almacen, palet, caja)  # Verificar si la caja existe
                       
        if not data.descripcion and not data.temporada:
            return CajaGetDescTempResponse(
                descripcion= None,
                temporada= None
            )
        
        # Asignar valores predeterminados si la descripción o temporada son 'SIN DESCRIPCIÓN' o 'SIN TEMPORADA'
        if data.descripcion == 'SIN DESCRIPCIÓN':
            data.descripcion = "DESCRIPCIÓN"

        if data.temporada == 'SIN TEMPORADA':
            data.temporada = "TEMP"
                
        return CajaGetDescTempResponse(
            descripcion= data.descripcion,
            temporada= data.temporada
        )
            
    except pymssql.Error as e:
        logger.critical(f"ERROR SQL: {e}")
        raise ConnectionError("Error de la base de dades")

def update_desc_temp_caja(
        almacen: int,
        palet: int, 
        caja: int, 
        descripcion: str|None, 
        temporada: str|None
    ) -> MessageResponse:
    """
    Actualiza la descripción y temporada de una caja en un palet de un almacén.

    Este endpoint permite actualizar la descripción y la temporada de una caja en un almacén específico. 
    Si la descripción o temporada proporcionadas son diferentes de las actuales, se actualizan en la base de datos. 
    Si la caja no se encuentra, se genera un error 404. Si no se realiza ningún cambio, se informa de que no hubo cambios.

    Args:
        almacen (int): El código del almacén donde se encuentra la caja.
        palet (int): El ID del palet que contiene la caja.
        caja (int): El ID de la caja cuya descripción y temporada se desean actualizar.
        descripcion (str, opcional): La nueva descripción de la caja. Por defecto es "SIN DESCRIPCIÓN".
        temporada (str, opcional): La nueva temporada de la caja. Por defecto es "SIN TEMPORADA".

    Returns:
        dict: Un mensaje confirmando la actualización de la descripción y temporada de la caja.

    Raises:
        HTTPException: Lanza un error 404 si la caja no existe en la base de datos o un error 500 en caso de fallos con la base de datos.
    """
    
    try:

        data = check_caja_exists(almacen, palet, caja)

        with db_pool.get_connection() as conn:
            with conn.cursor() as cursor:

                query = "UPDATE CAJAS SET"
                params = []

                if descripcion is not None:
                    query += " descripcion = %s"
                    params.append(descripcion)

                if temporada is not None:
                    if descripcion is not None:
                        query += ","
                    query += " temporada = %s"
                    params.append(temporada)

                params.extend([almacen, palet, caja])

                query += " WHERE almacen = %s AND palet = %s AND caja = %s"
                
                cursor.execute(query, params)

                return MessageResponse(message=f"Descripción y temporada actualizadas de la caja {caja}, palet {palet}, almacen {almacen}")

    except pymssql.IntegrityError as e:
        raise ValueError(f"Error de integridad al actualizar la caja {caja}: {e}")

    except pymssql.Error as e:
        logger.critical(f"ERROR SQL: {e}")
        raise ConnectionError("Error de la base de dades")
    
def update_cantidad_caja(almacen: int, palet: int, caja: int) -> MessageResponse:
    """
    Actualiza la cantidad de productos en una caja según los productos asociados en el stock.

    Este endpoint permite actualizar la cantidad de productos en una caja específica dentro de un palet 
    y almacén. La cantidad se calcula automáticamente como el número de productos asociados a la caja en 
    el inventario. Si la caja no existe, se genera un error 404.

    Args:
        almacen (int): El código del almacén donde se encuentra la caja.
        palet (int): El ID del palet que contiene la caja.
        caja (int): El ID de la caja cuya cantidad de productos se desea actualizar.

    Returns:
        dict: Un mensaje confirmando la actualización de la cantidad de la caja.

    Raises:
        HTTPException: Lanza un error 404 si la caja no existe en la base de datos o un error 500 en caso de fallos con la base de datos.
    """
    
    try:

        data = check_caja_exists(almacen, palet, caja)

        with db_pool.get_connection() as conn:
            with conn.cursor() as cursor:
                # Actualizar la cantidad de productos en la caja según el stock asociado
                cursor.execute("""
                    UPDATE cajas 
                    SET cantidad = (
                        SELECT COUNT(*) AS cantidad 
                        FROM stock 
                        WHERE caja = %s AND palet = %s AND almacen = %s
                    ) 
                    WHERE caja = %s AND palet = %s AND almacen = %s
                """, (caja, palet, almacen, caja, palet, almacen,))


                cursor.execute("SELECT cantidad FROM cajas WHERE caja = %s AND palet = %s AND almacen = %s",(caja, palet, almacen,))

                conn.commit()

                return MessageResponse(message=f"Cambiada la cantidad de la caja {caja}, palet {palet}, almacen {almacen}")

    except pymssql.Error as e:
        logger.critical(f"ERROR SQL: {e}")
        raise ConnectionError("Error de la base de dades")
    