"""
Palets de Gestock: tabla `gestock_palets` (codi_centre, palet).
"""
from gestock_server.db.database import db_pool
from gestock_server.db.driver import DBError, IntegrityError
from gestock_server.schemas.palet import (
    PaletInfo,
    PaletsGetResponse,
    MessageResponse
)

import logging
logger = logging.getLogger(__name__)

TIPUS_ALMACEN = "ALMACEN"


def get_palets(almacen: str) -> PaletsGetResponse:
    """
    Devuelve los palets de un almacén con su número de cajas y de unidades de stock.

    Raises:
        ConnectionError: si ocurre un error con la base de datos.
    """
    try:
        with db_pool.get_connection() as conn:
            with conn.cursor() as cursor:
                # Una sola consulta: palets + cajas + unidades (quantitat la mantienen los triggers)
                cursor.execute(
                    """
                    SELECT
                        p.palet,
                        COUNT(c.caixa)                 AS cajas,
                        COALESCE(SUM(c.quantitat), 0)  AS cantidad
                    FROM gestock_palets p
                    LEFT JOIN gestock_caixes c
                        ON c.codi_centre = p.codi_centre
                       AND c.palet = p.palet
                    WHERE p.codi_centre = %s
                    GROUP BY p.palet
                    ORDER BY p.palet
                    """,
                    (almacen,)
                )
                palets = cursor.fetchall()

        data = {
            str(palet): PaletInfo(cajas=int(cajas), cantidad=int(cantidad))
            for palet, cajas, cantidad in palets
        }

        return PaletsGetResponse(
            palets=data,
            total=len(palets)
        )

    except DBError as e:
        logger.critical(f"ERROR SQL: {e}")
        raise ConnectionError("Error de la base de dades")


def create_palet(almacen: str) -> MessageResponse:
    """
    Crea un palet nuevo en un almacén con el menor número libre (1, 2, 3...).

    Raises:
        LookupError: si el almacén no existe (404).
        ValueError: si hay un conflicto de clave, p. ej. dos usuarios a la vez (409).
        ConnectionError: si ocurre un error con la base de datos (500).
    """
    next_id = None

    try:
        with db_pool.get_connection() as conn:
            with conn.cursor() as cursor:
                # Comprueba que el almacén existe antes de crear el palet
                cursor.execute(
                    "SELECT COUNT(*) FROM centres WHERE codi_centre = %s AND tipus = %s",
                    (almacen, TIPUS_ALMACEN)
                )
                if cursor.fetchone()[0] == 0:
                    raise LookupError(f"No existeix el magatzem {almacen}")

                # Menor número de palet libre en el almacén
                cursor.execute(
                    """
                    SELECT MIN(posibles.palet)
                    FROM (
                        SELECT palet + 1 AS palet
                        FROM gestock_palets
                        WHERE codi_centre = %s
                        UNION
                        SELECT 1 AS palet
                    ) AS posibles
                    WHERE posibles.palet NOT IN (
                        SELECT palet
                        FROM gestock_palets
                        WHERE codi_centre = %s
                    )
                    """,
                    (almacen, almacen)
                )
                result = cursor.fetchone()
                next_id = int(result[0]) if result and result[0] is not None else 1

                cursor.execute(
                    "INSERT INTO gestock_palets (codi_centre, palet) VALUES (%s, %s)",
                    (almacen, next_id)
                )
                conn.commit()

                return MessageResponse(
                    message=f"HA CREAT EL PALET {next_id} EN EL MAGATZEM {almacen}"
                )

    except IntegrityError as e:
        logger.warning(f"ERROR D'INTEGRITAT CREANT PALET {next_id} AL MAGATZEM {almacen}: {e}")
        raise ValueError(f"No s'ha pogut crear el palet {next_id} al magatzem {almacen}. Torna-ho a provar")

    except DBError as e:
        logger.critical(f"ERROR SQL: {e}")
        raise ConnectionError("Error de base de dades")


def delete_palet(almacen: str, palet: int) -> MessageResponse:
    """
    Elimina un palet vacío (sin cajas).

    Raises:
        ValueError: si el palet todavía tiene cajas (409).
        ConnectionError: si ocurre un error con la base de datos.
    """
    try:
        with db_pool.get_connection() as conn:
            with conn.cursor() as cursor:
                cursor.execute(
                    "SELECT COUNT(*) FROM gestock_caixes WHERE codi_centre = %s AND palet = %s",
                    (almacen, palet)
                )
                cajas_count = cursor.fetchone()[0]

                if cajas_count > 0:
                    raise ValueError(f"No es pot eliminar el palet {palet} perquè té {cajas_count} caixes.")

                cursor.execute(
                    "DELETE FROM gestock_palets WHERE codi_centre = %s AND palet = %s",
                    (almacen, palet)
                )
                conn.commit()

                return MessageResponse(message=f"Palet {palet} eliminado")

    except IntegrityError:
        # La BDD impide borrar un palet con cajas (FK sin cascada)
        raise ValueError(f"No es pot eliminar el palet {palet} perquè té caixes.")

    except DBError as e:
        logger.critical(f"ERROR SQL: {e}")
        raise ConnectionError("Error de la base de dades")
