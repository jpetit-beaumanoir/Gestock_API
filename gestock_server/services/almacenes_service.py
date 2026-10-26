"""
Almacenes de Gestock.

Desde la BDD ElBicho los almacenes son filas de la tabla `centres` con tipus = 'ALMACEN'.
El código del almacén es `centres.codi_centre` (VARCHAR(10)) y el nombre `centres.nom_centre`.
"""
from gestock_server.db.database import db_pool
from gestock_server.db.driver import DBError, IntegrityError, dict_cursor
from gestock_server.config import DEFAULT_PAIS
from gestock_server.schemas.almacen import (
    AlmacenInfo,
    AlmacenResponse,
    AlmacenLoginResponse,
    MessageResponse
)

import logging
logger = logging.getLogger(__name__)

TIPUS_ALMACEN = "ALMACEN"


def get_almacenes() -> AlmacenResponse:
    """
    Devuelve todos los almacenes (centres con tipus 'ALMACEN') con el número de palets,
    cajas y unidades de stock de cada uno.

    Raises:
        ConnectionError: si ocurre un error con la base de datos.
    """
    try:
        with db_pool.get_connection() as conn:
            with dict_cursor(conn) as cursor:

                # Palets por almacén
                cursor.execute("""
                    SELECT codi_centre, COUNT(*) AS cantidad_palets
                    FROM gestock_palets
                    GROUP BY codi_centre
                """)
                palets_data = {row["codi_centre"]: row["cantidad_palets"] for row in cursor.fetchall()}

                # Cajas por almacén
                cursor.execute("""
                    SELECT codi_centre, COUNT(*) AS cantidad_cajas
                    FROM gestock_caixes
                    GROUP BY codi_centre
                """)
                cajas_data = {row["codi_centre"]: row["cantidad_cajas"] for row in cursor.fetchall()}

                # Unidades de stock por almacén
                cursor.execute("""
                    SELECT codi_centre, COUNT(*) AS cantidad_productos
                    FROM gestock_stock
                    GROUP BY codi_centre
                """)
                productos_data = {row["codi_centre"]: row["cantidad_productos"] for row in cursor.fetchall()}

                # Almacenes
                cursor.execute(
                    """
                    SELECT codi_centre, nom_centre
                    FROM centres
                    WHERE tipus = %s
                    ORDER BY codi_centre
                    """,
                    (TIPUS_ALMACEN,)
                )
                almacenes_info = cursor.fetchall()

                data = {}
                for almacen in almacenes_info:
                    codigo = almacen["codi_centre"]

                    data[str(codigo)] = AlmacenInfo(
                        nombre=almacen["nom_centre"] or str(codigo),
                        palets=palets_data.get(codigo, 0),
                        cajas=cajas_data.get(codigo, 0),
                        productos=productos_data.get(codigo, 0)
                    )

        return AlmacenResponse(almacenes=data)

    except DBError as e:
        logger.critical(f"ERROR SQL: {e}")
        raise ConnectionError("Error de base de dades")


def login_almacen(code: str) -> AlmacenLoginResponse:
    """
    Comprueba que existe un almacén con el código indicado y devuelve su nombre.

    Raises:
        ValueError: si no existe un almacén (centre tipus 'ALMACEN') con ese código (404).
        ConnectionError: si ocurre un error con la base de datos.
    """
    try:
        with db_pool.get_connection() as conn:
            with conn.cursor() as cursor:
                cursor.execute(
                    "SELECT codi_centre, nom_centre FROM centres WHERE codi_centre = %s AND tipus = %s",
                    (code, TIPUS_ALMACEN)
                )
                row = cursor.fetchone()

                if row:
                    return AlmacenLoginResponse(nombre=row[1] or str(row[0]))

                raise ValueError(f"El magatzem {code} no existeix")

    except DBError as e:
        logger.critical(f"ERROR SQL: {e}")
        raise ConnectionError("Error de base de dades")


def create_almacen(nombre: str, codigo: str) -> MessageResponse:
    """
    Da de alta un almacén nuevo en `centres` (tipus 'ALMACEN', país DEFAULT_PAIS,
    fecha de apertura = hoy). marca y regió quedan vacías.

    Raises:
        ValueError: si ya existe un centro con ese código (409).
        ConnectionError: si ocurre un error con la base de datos.
    """
    try:
        with db_pool.get_connection() as conn:
            with conn.cursor() as cursor:
                cursor.execute(
                    """
                    INSERT INTO centres (codi_centre, nom_centre, pais, tipus, data_obertura)
                    VALUES (%s, %s, %s, %s, CURDATE())
                    """,
                    (codigo, nombre, DEFAULT_PAIS, TIPUS_ALMACEN)
                )
                conn.commit()

                return MessageResponse(message=f"Magatzem '{nombre}' creat.")

    except IntegrityError:
        # Clave primaria duplicada: ya existe un centro (almacén, tienda o corner) con ese código
        raise ValueError(f"Ja existeix un centre amb codi {codigo}")

    except DBError as e:
        logger.critical(f"ERROR SQL: {e}")
        raise ConnectionError("Error de base de dades")


def delete_almacen(code: str) -> MessageResponse:
    """
    Elimina un almacén de `centres`. Solo se permite con centros de tipus 'ALMACEN'
    y sin palets (las tiendas y corners no se pueden borrar desde Gestock).

    Raises:
        LookupError: si no existe un almacén con ese código (404).
        ValueError: si el almacén todavía tiene palets (409).
        ConnectionError: si ocurre un error con la base de datos.
    """
    try:
        with db_pool.get_connection() as conn:
            with conn.cursor() as cursor:
                cursor.execute(
                    "SELECT COUNT(*) FROM centres WHERE codi_centre = %s AND tipus = %s",
                    (code, TIPUS_ALMACEN)
                )
                if cursor.fetchone()[0] == 0:
                    raise LookupError(f"El magatzem {code} no existeix")

                cursor.execute("SELECT COUNT(*) FROM gestock_palets WHERE codi_centre = %s", (code,))
                if cursor.fetchone()[0] > 0:
                    raise ValueError(f"El magatzem {code} té palets a dintre")

                cursor.execute(
                    "DELETE FROM centres WHERE codi_centre = %s AND tipus = %s",
                    (code, TIPUS_ALMACEN)
                )
                conn.commit()

                return MessageResponse(message=f"Magatzem '{code}' eliminat.")

    except IntegrityError:
        # Otra tabla de la BDD ElBicho sigue haciendo referencia a este centro
        raise ValueError("S'ha intentat eliminar un magatzem amb elements associats")

    except DBError as e:
        logger.critical(f"ERROR SQL: {e}")
        raise ConnectionError("Error de la base de dades")
