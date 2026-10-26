from gestock_server.db.database import db_pool
from gestock_server.db.driver import DBError
from gestock_server.schemas.familia import FamiliasGetResponse

import logging
logger = logging.getLogger(__name__)


def get_familias() -> FamiliasGetResponse:
    """
    Devuelve la lista de familias distintas del catálogo (tabla productes).

    Raises:
        ConnectionError: si ocurre un error con la base de datos.
    """
    try:
        with db_pool.get_connection() as conn:
            with conn.cursor() as cursor:
                # Usa el índice IX_productes_familia (familia, subfamilia)
                cursor.execute("""
                    SELECT DISTINCT familia
                    FROM productes
                    WHERE familia IS NOT NULL AND familia <> ''
                    ORDER BY familia
                """)
                results = cursor.fetchall()

        familias = [str(row[0]).strip() for row in results]

        return FamiliasGetResponse(familias=familias)

    except DBError as e:
        logger.critical(f"ERROR SQL: {e}")
        raise ConnectionError("Error de la base de dades")
