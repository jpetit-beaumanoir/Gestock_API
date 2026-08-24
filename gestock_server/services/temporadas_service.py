from gestock_server.db.database import db_pool
from gestock_server.schemas.temporada import TemporadasGetResponse

import logging
import pymssql


def get_temporadas() -> TemporadasGetResponse:
    """
    """
    try:

        # Obtiene una conexión al pool de base de datos
        with db_pool.get_connection() as conn:
            with conn.cursor() as cursor:
                # Ejecuta la consulta para obtener todas las temporadas de cajas
                cursor.execute("""
                    SELECT DISTINCT temporada 
                    FROM productos
                    WHERE temporada IS NOT NULL AND temporada <> ''
                    ORDER BY temporada
                """)
                results = cursor.fetchall()

            # Si no hay resultados (sin temporadas), se retorna una lista vacía
            if not results:
                return TemporadasGetResponse(temporadas=[])

            # Extrae las temporadas de los resultados y las formatea como una lista de diccionarios
            temporadas = [str(row[0]).strip() for row in results]

            # Devuelve la lista de temporadas
            return TemporadasGetResponse(temporadas=temporadas)

    except pymssql.Error as e:
        logging.critical(f"ERROR SQL: {e}")
        raise ConnectionError("Error de la base de dades")