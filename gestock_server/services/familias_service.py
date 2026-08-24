from gestock_server.db.database import db_pool
from gestock_server.schemas.familia import FamiliasGetResponse

import logging
import pymssql


def get_familias() -> FamiliasGetResponse:
    """
    Obtiene la lista de todas las familias de productos disponibles en la base de datos.

    Este endpoint consulta la base de datos para obtener todas las familias de productos almacenadas 
    en la tabla `productos`. Si no se encuentran familias devuelve 404. En caso de cualquier otro error, 
    se lanza un error 500.

    Returns:
        JSONResponse: Una lista de diccionarios con el nombre de cada familia, o una respuesta vacía 
                       si no se encuentran familias.

    Raises:
        HTTPException: Lanza un error personalizado si ocurre un problema con la base de datos.
    """
    try:

        # Obtiene una conexión al pool de base de datos
        with db_pool.get_connection() as conn:
            with conn.cursor() as cursor:
                # Ejecuta la consulta para obtener todas las familias de productos
                cursor.execute("""
                    SELECT DISTINCT familia 
                    FROM productos
                    WHERE familia IS NOT NULL AND familia <> ''
                    ORDER BY familia
                """)
                results = cursor.fetchall()

            # Si no hay resultados (sin familias), se retorna una lista vacía
            if not results:
                return FamiliasGetResponse(familias=[])

            # Extrae las familias de los resultados y las formatea como una lista de diccionarios
            familias = [str(row[0]).strip() for row in results]

            # Devuelve la lista de familias en formato JSON
            return FamiliasGetResponse(familias=familias)

    except pymssql.Error as e:
        logging.critical(f"ERROR SQL: {e}")
        raise ConnectionError("Error de la base de dades")