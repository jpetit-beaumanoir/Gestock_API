"""
Cajas de Gestock: tabla `gestock_caixes` (codi_centre, palet, caixa, temporada, descripcio, quantitat).

`quantitat` la calcula la BDD con triggers (= número de filas de gestock_stock de la caja):
la API nunca la escribe.
"""
from gestock_server.db.database import db_pool
from gestock_server.db.driver import DBError, IntegrityError
from gestock_server.schemas.caja import (
    CajaExistsDB,
    CajasGetResponse,
    CajaInfo,
    MessageResponse,
    CajaGetDescTempResponse
)

import logging
logger = logging.getLogger(__name__)

DESCRIPCION_DEFECTO = "SIN DESCRIPCIÓN"
TEMPORADA_DEFECTO = "SIN TEMPORADA"


def check_caja_exists(
    almacen: str,
    palet: int,
    caja: int
) -> CajaExistsDB:
    """
    Devuelve los datos de una caja.

    Raises:
        ValueError: si la caja no existe (404).
        ConnectionError: si ocurre un error con la base de datos.
    """
    try:
        with db_pool.get_connection() as conn:
            with conn.cursor() as cursor:

                cursor.execute("""
                    SELECT
                        caixa,
                        palet,
                        codi_centre,
                        temporada,
                        descripcio,
                        quantitat
                    FROM gestock_caixes
                    WHERE codi_centre = %s
                      AND palet = %s
                      AND caixa = %s
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

    except DBError as e:
        logger.critical(f"ERROR SQL: {e}")
        raise ConnectionError("Error de la base de dades")


def get_cajas(almacen: str, palet: int) -> CajasGetResponse:
    """
    Devuelve las cajas de un palet con su cantidad, descripción y temporada.

    Raises:
        ConnectionError: si ocurre un error con la base de datos.
    """
    try:
        with db_pool.get_connection() as conn:
            with conn.cursor() as cursor:
                cursor.execute(
                    """
                    SELECT
                        caixa,
                        quantitat,
                        COALESCE(descripcio, %s),
                        COALESCE(temporada, %s)
                    FROM gestock_caixes
                    WHERE codi_centre = %s
                      AND palet = %s
                    ORDER BY caixa
                    """,
                    (DESCRIPCION_DEFECTO, TEMPORADA_DEFECTO, almacen, palet)
                )
                cajas = cursor.fetchall()

        data = {
            str(caja): CajaInfo(
                cantidad=cantidad,
                descripcion=descripcion,
                temporada=temporada
            )
            for caja, cantidad, descripcion, temporada in cajas
        }

        return CajasGetResponse(cajas=data)

    except DBError as e:
        logger.critical(f"ERROR SQL: {e}")
        raise ConnectionError("Error de la base de dades")


def create_caja(almacen: str, palet: int) -> MessageResponse:
    """
    Crea una caja nueva en un palet con el menor número libre y valores por defecto
    ('SIN DESCRIPCIÓN', 'SIN TEMPORADA'). La cantidad la pone el trigger.

    Raises:
        LookupError: si el palet no existe en el almacén (404).
        ValueError: si hay un conflicto de clave, p. ej. dos usuarios a la vez (409).
        ConnectionError: si ocurre un error con la base de datos.
    """
    try:
        with db_pool.get_connection() as conn:
            with conn.cursor() as cursor:

                # Comprueba que el palet existe en el almacén antes de crear la caja
                cursor.execute(
                    "SELECT COUNT(*) FROM gestock_palets WHERE codi_centre = %s AND palet = %s",
                    (almacen, palet)
                )
                if cursor.fetchone()[0] == 0:
                    raise LookupError(f"No existeix el palet {palet} al magatzem {almacen}")

                # Menor número de caja libre en el palet
                cursor.execute(
                    """
                    SELECT MIN(posibles.caixa)
                    FROM (
                        SELECT caixa + 1 AS caixa
                        FROM gestock_caixes
                        WHERE codi_centre = %s
                          AND palet = %s
                        UNION
                        SELECT 1 AS caixa
                    ) AS posibles
                    WHERE posibles.caixa NOT IN (
                        SELECT caixa
                        FROM gestock_caixes
                        WHERE codi_centre = %s
                          AND palet = %s
                    )
                    """,
                    (almacen, palet, almacen, palet)
                )
                result = cursor.fetchone()
                next_id = int(result[0]) if result and result[0] is not None else 1

                cursor.execute(
                    """
                    INSERT INTO gestock_caixes (codi_centre, palet, caixa, temporada, descripcio)
                    VALUES (%s, %s, %s, %s, %s)
                    """,
                    (almacen, palet, next_id, TEMPORADA_DEFECTO, DESCRIPCION_DEFECTO)
                )

                conn.commit()

                return MessageResponse(
                    message=f"HA CREAT LA CAIXA {next_id} EN EL PALET {palet} MAGATZEM {almacen}"
                )

    except IntegrityError as e:
        logger.warning(f"ERROR D'INTEGRITAT CREANT CAIXA AL PALET {palet} MAGATZEM {almacen}: {e}")
        raise ValueError(f"No s'ha pogut crear la caixa al palet {palet} del magatzem {almacen}. Torna-ho a provar")

    except DBError as e:
        logger.critical(f"ERROR SQL: {e}")
        raise ConnectionError("Error de la base de dades")


def delete_caja(almacen: str, palet: int, caja: int) -> MessageResponse:
    """
    Elimina una caja vacía (sin stock).

    Raises:
        ValueError: si la caja todavía tiene stock (409).
        ConnectionError: si ocurre un error con la base de datos.
    """
    try:
        with db_pool.get_connection() as conn:
            with conn.cursor() as cursor:
                cursor.execute(
                    "SELECT COUNT(*) FROM gestock_stock WHERE codi_centre = %s AND palet = %s AND caixa = %s",
                    (almacen, palet, caja)
                )
                productos_count = cursor.fetchone()[0]

                if productos_count > 0:
                    raise ValueError(f"No es pot eliminar la caixa {caja} perquè té {productos_count} productes.")

                cursor.execute(
                    "DELETE FROM gestock_caixes WHERE codi_centre = %s AND palet = %s AND caixa = %s",
                    (almacen, palet, caja)
                )
                conn.commit()

                return MessageResponse(message=f"Caja {caja} del palet {palet}, almacén {almacen} eliminada")

    except IntegrityError:
        # La BDD impide borrar una caja con stock (FK sin cascada)
        raise ValueError(f"No es pot eliminar la caixa {caja} perquè té productes.")

    except DBError as e:
        logger.critical(f"ERROR SQL: {e}")
        raise ConnectionError("Error de la base de dades")


def get_desc_temp_caja(almacen: str, palet: int, caja: int) -> CajaGetDescTempResponse:
    """
    Devuelve la descripción y temporada de una caja. Los valores por defecto se
    devuelven como 'DESCRIPCIÓN' / 'TEMP' (texto de ayuda para la app).

    Raises:
        ValueError: si la caja no existe (404).
        ConnectionError: si ocurre un error con la base de datos.
    """
    data = check_caja_exists(almacen, palet, caja)

    if not data.descripcion and not data.temporada:
        return CajaGetDescTempResponse(
            descripcion=None,
            temporada=None
        )

    descripcion = data.descripcion
    temporada = data.temporada

    if descripcion == DESCRIPCION_DEFECTO:
        descripcion = "DESCRIPCIÓN"

    if temporada == TEMPORADA_DEFECTO:
        temporada = "TEMP"

    return CajaGetDescTempResponse(
        descripcion=descripcion,
        temporada=temporada
    )


def update_desc_temp_caja(
        almacen: str,
        palet: int,
        caja: int,
        descripcion: str | None,
        temporada: str | None
    ) -> MessageResponse:
    """
    Actualiza la descripción y/o la temporada de una caja (máx. 20 caracteres cada una,
    lo valida el schema de la petición).

    Raises:
        ValueError: si la caja no existe (404).
        ConnectionError: si ocurre un error con la base de datos.
    """
    # Si no se envía ningún campo no hay nada que actualizar (evita un UPDATE sin SET)
    if descripcion is None and temporada is None:
        return MessageResponse(message=f"Sense canvis a la caixa {caja}, palet {palet}, magatzem {almacen}")

    check_caja_exists(almacen, palet, caja)

    try:
        with db_pool.get_connection() as conn:
            with conn.cursor() as cursor:

                sets = []
                params = []

                if descripcion is not None:
                    sets.append("descripcio = %s")
                    params.append(descripcion)

                if temporada is not None:
                    sets.append("temporada = %s")
                    params.append(temporada)

                params.extend([almacen, palet, caja])

                cursor.execute(
                    f"UPDATE gestock_caixes SET {', '.join(sets)} "
                    "WHERE codi_centre = %s AND palet = %s AND caixa = %s",
                    params
                )
                conn.commit()

                return MessageResponse(message=f"Descripción y temporada actualizadas de la caja {caja}, palet {palet}, almacen {almacen}")

    except IntegrityError as e:
        raise ValueError(f"Error de integridad al actualizar la caja {caja}: {e}")

    except DBError as e:
        logger.critical(f"ERROR SQL: {e}")
        raise ConnectionError("Error de la base de dades")


def update_cantidad_caja(almacen: str, palet: int, caja: int) -> MessageResponse:
    """
    Recalcula la cantidad de una caja.

    En la BDD ElBicho la cantidad la mantienen los triggers automáticamente, así que este
    endpoint ya no es necesario; se conserva por compatibilidad con la app. El UPDATE
    dispara el trigger BEFORE UPDATE, que vuelve a poner el valor real.

    Raises:
        ValueError: si la caja no existe (404).
        ConnectionError: si ocurre un error con la base de datos.
    """
    check_caja_exists(almacen, palet, caja)

    try:
        with db_pool.get_connection() as conn:
            with conn.cursor() as cursor:
                cursor.execute(
                    """
                    UPDATE gestock_caixes
                    SET quantitat = (
                        SELECT COUNT(*)
                        FROM gestock_stock
                        WHERE codi_centre = %s AND palet = %s AND caixa = %s
                    )
                    WHERE codi_centre = %s AND palet = %s AND caixa = %s
                    """,
                    (almacen, palet, caja, almacen, palet, caja)
                )
                conn.commit()

                return MessageResponse(message=f"Cambiada la cantidad de la caja {caja}, palet {palet}, almacen {almacen}")

    except DBError as e:
        logger.critical(f"ERROR SQL: {e}")
        raise ConnectionError("Error de la base de dades")
