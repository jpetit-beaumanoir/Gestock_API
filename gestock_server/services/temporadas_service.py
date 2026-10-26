from gestock_server.db.database import db_pool
from gestock_server.db.driver import DBError
from gestock_server.schemas.temporada import TemporadasGetResponse

import logging
logger = logging.getLogger(__name__)


def get_temporadas() -> TemporadasGetResponse:
    """
    Devuelve la lista de temporadas distintas del catálogo (tabla productes).

    Raises:
        ConnectionError: si ocurre un error con la base de datos.
    """
    try:
        with db_pool.get_connection() as conn:
            with conn.cursor() as cursor:
                cursor.execute("""
                    SELECT DISTINCT temporada
                    FROM productes
                    WHERE temporada IS NOT NULL AND temporada <> ''
                    ORDER BY temporada
                """)
                results = cursor.fetchall()

        temporadas = [str(row[0]).strip() for row in results]

        return TemporadasGetResponse(temporadas=temporadas)

    except DBError as e:
        logger.critical(f"ERROR SQL: {e}")
        raise ConnectionError("Error de la base de dades")
