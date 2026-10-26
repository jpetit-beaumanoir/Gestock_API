"""
Stock de Gestock: tabla `gestock_stock`. Una fila = una unidad de producto dentro de una caja.

Columnas: id, ean, codi_centre, palet, caixa, data_alta (la pone la BDD) e id_usuari (obligatorio).
`gestock_caixes.quantitat` se actualiza sola con los triggers al insertar, mover o borrar stock.
"""
from gestock_server.db.database import db_pool
from gestock_server.db.driver import DBError, IntegrityError
from gestock_server.config import USUARIS_APLICACIO
from gestock_server.schemas.stock import (
    StockAddRequest,
    StockDeleteRequest,
    StockMoveRequest,
    StockGetResponse,
    StockInfo,
    StockExportResponse,
    MessageResponse
)

import logging
logger = logging.getLogger(__name__)


def _placeholders(n: int) -> str:
    """'%s, %s, ...' para usar en IN (...)."""
    return ", ".join(["%s"] * n)


def _get_id_usuari(cursor, nom_usuari: str) -> int:
    """
    Busca el id_usuari del usuario de la API (nombre asociado a la API key) en la tabla usuaris.

    Raises:
        PermissionError: si el usuario no existe en usuaris o está desactivado (403).
    """
    cursor.execute(
        """
        SELECT id_usuari
        FROM usuaris
        WHERE aplicacio = %s
          AND nom_usuari = %s
          AND actiu = 1
        """,
        (USUARIS_APLICACIO, nom_usuari)
    )
    row = cursor.fetchone()

    if row is None:
        raise PermissionError(
            f"L'usuari '{nom_usuari}' no existeix o no està actiu a la taula usuaris "
            f"(aplicacio = '{USUARIS_APLICACIO}')"
        )

    return int(row[0])


def _check_caixa(cursor, almacen: str, palet: int, caja: int) -> None:
    """
    Raises:
        LookupError: si la caja no existe (404).
    """
    cursor.execute(
        "SELECT 1 FROM gestock_caixes WHERE codi_centre = %s AND palet = %s AND caixa = %s",
        (almacen, palet, caja)
    )
    if cursor.fetchone() is None:
        raise LookupError(f"La caixa {caja} del palet {palet} del magatzem {almacen} no existeix")


def get_stock_caja(almacen: str, palet: int, caja: int) -> StockGetResponse:
    """
    Devuelve el stock de una caja agrupado por EAN (con los ids de cada unidad).

    Raises:
        ConnectionError: si ocurre un error con la base de datos.
    """
    data: dict[str, StockInfo] = {}

    try:
        with db_pool.get_connection() as conn:
            with conn.cursor() as cursor:
                cursor.execute(
                    """
                    SELECT s.id, s.ean, p.nom, p.color, p.talla, p.temporada
                    FROM gestock_stock s
                    LEFT JOIN productes p ON s.ean = p.ean
                    WHERE s.codi_centre = %s AND s.palet = %s AND s.caixa = %s
                    ORDER BY s.ean, s.id
                    """,
                    (almacen, palet, caja)
                )
                stock = cursor.fetchall()

        if not stock:
            return StockGetResponse(stock={}, total=0)

        for id_producto, ean, nombre, color, talla, temporada in stock:
            ean = str(ean).strip()

            if ean in data:
                data[ean].cantidad += 1
                data[ean].ids.append(id_producto)
            else:
                data[ean] = StockInfo(
                    ids=[id_producto],
                    nombre=nombre or "??",
                    color=color or "??",
                    talla=talla or "??",
                    temporada=temporada or "??",
                    cantidad=1
                )

                if nombre is None:
                    logger.warning(f"NO S'HA TROBAT INFORMACIÓ DEL PRODUCTE {ean} A LA TAULA PRODUCTES")

        return StockGetResponse(stock=data, total=len(stock))

    except DBError as e:
        logger.critical(f"ERROR SQL: {e}")
        raise ConnectionError("Error de la base de dades")


def add_stock(body: StockAddRequest, usuario: str) -> MessageResponse:
    """
    Añade unidades de producto a una caja. Cada EAN de la lista es una unidad.

    Args:
        body: almacén, palet, caja y lista de EAN.
        usuario: nombre del usuario de la API (request.state.user), se guarda su id_usuari.

    Raises:
        ValueError: lista vacía o EAN que no existen en productes (400).
        LookupError: la caja no existe (404).
        PermissionError: el usuario no existe en usuaris (403).
        ConnectionError: si ocurre un error con la base de datos.
    """
    eans = [str(ean).strip() for ean in body.eans if str(ean).strip()]

    if not eans:
        raise ValueError("La lista de productes (EANs) no pot estar buida.")

    try:
        with db_pool.get_connection() as conn:
            with conn.cursor() as cursor:

                _check_caixa(cursor, body.almacen, body.palet, body.caja)
                id_usuari = _get_id_usuari(cursor, usuario)

                # gestock_stock.ean tiene FK a productes: comprobar antes para dar un error claro
                unique_eans = sorted(set(eans))
                cursor.execute(
                    f"SELECT ean FROM productes WHERE ean IN ({_placeholders(len(unique_eans))})",
                    unique_eans
                )
                existentes = {row[0] for row in cursor.fetchall()}
                no_existen = [ean for ean in unique_eans if ean not in existentes]

                if no_existen:
                    raise ValueError(
                        "Aquests EAN no existeixen al catàleg (productes): " + ", ".join(no_existen)
                    )

                stock_data = [
                    (ean, body.almacen, body.palet, body.caja, id_usuari)
                    for ean in eans
                ]

                cursor.executemany(
                    """
                    INSERT INTO gestock_stock (ean, codi_centre, palet, caixa, id_usuari)
                    VALUES (%s, %s, %s, %s, %s)
                    """,
                    stock_data
                )
                insertados = cursor.rowcount

                conn.commit()

                return MessageResponse(message=f"Insertados {insertados} productos con éxito.")

    except IntegrityError as e:
        logger.warning(f"ERROR D'INTEGRITAT AFEGINT STOCK: {e}")
        raise ValueError("No s'ha pogut afegir l'estoc: la caixa, algun EAN o l'usuari no existeixen")

    except DBError as e:
        logger.critical(f"ERROR SQL: {e}")
        raise ConnectionError("Error de la base de dades")


def delete_stock(body: StockDeleteRequest) -> MessageResponse:
    """
    Elimina unidades de stock por id. Solo borra las que pertenecen a la caja indicada.

    Raises:
        ValueError: lista vacía (400).
        ConnectionError: si ocurre un error con la base de datos.
    """
    if not body.ids:
        raise ValueError("La lista de productes no pot estar buida.")

    try:
        with db_pool.get_connection() as conn:
            with conn.cursor() as cursor:
                cursor.execute(
                    f"""
                    DELETE FROM gestock_stock
                    WHERE id IN ({_placeholders(len(body.ids))})
                      AND codi_centre = %s
                      AND palet = %s
                      AND caixa = %s
                    """,
                    [*body.ids, body.almacen, body.palet, body.caja]
                )
                eliminados = cursor.rowcount

                conn.commit()

                if eliminados < len(set(body.ids)):
                    logger.warning(
                        f"S'HAN DEMANAT ELIMINAR {len(set(body.ids))} IDS PERÒ NOMÉS {eliminados} "
                        f"ERAN A LA CAIXA {body.caja} PALET {body.palet} MAGATZEM {body.almacen}"
                    )

                return MessageResponse(message=f"Eliminados {eliminados} productos con éxito.")

    except DBError as e:
        logger.critical(f"ERROR SQL: {e}")
        raise ConnectionError("Error de la base de dades")


def move_stock(body: StockMoveRequest) -> MessageResponse:
    """
    Mueve unidades de stock (por id) a la caja de destino indicada (almacén, palet, caja).
    Los triggers recalculan la cantidad de la caja de origen y de la de destino.

    Raises:
        ValueError: lista vacía (400).
        LookupError: la caja de destino no existe (404).
        ConnectionError: si ocurre un error con la base de datos.
    """
    if not body.ids:
        raise ValueError("La lista de productes no pot estar buida.")

    try:
        with db_pool.get_connection() as conn:
            with conn.cursor() as cursor:

                _check_caixa(cursor, body.almacen, body.palet, body.caja)

                cursor.execute(
                    f"""
                    UPDATE gestock_stock
                    SET codi_centre = %s, palet = %s, caixa = %s
                    WHERE id IN ({_placeholders(len(body.ids))})
                    """,
                    [body.almacen, body.palet, body.caja, *body.ids]
                )
                moved_count = cursor.rowcount

                conn.commit()

                return MessageResponse(message=f"Movidos {moved_count} productos con éxito.")

    except IntegrityError as e:
        logger.warning(f"ERROR D'INTEGRITAT MOVENT STOCK: {e}")
        raise ValueError("No s'ha pogut moure l'estoc a la caixa indicada")

    except DBError as e:
        logger.critical(f"ERROR SQL: {e}")
        raise ConnectionError("Error de la base de dades")


def filtered_search(
    almacen: str,
    ean: str | None = None,
    talla: str | None = None,
    nombre: str | None = None,
    familia: str | None = None,
    color: str | None = None,
    temporada: str | None = None
) -> StockExportResponse:
    """
    Búsqueda filtrada del stock de un almacén para exportar.
    Filtros opcionales: EAN, talla, nombre, familia (lista separada por comas), color y temporada.

    Raises:
        ConnectionError: si ocurre un error con la base de datos.
    """
    try:
        with db_pool.get_connection() as conn:
            with conn.cursor() as cursor:
                # Los campos de texto pueden ser NULL en la BDD nueva: COALESCE para no romper el schema
                query = """
                    SELECT
                        s.ean,
                        s.palet,
                        s.caixa                          AS caja,
                        COALESCE(c.descripcio, '')       AS desc_caja,
                        COALESCE(c.temporada, '')        AS temp_caja,
                        s.codi_centre                    AS almacen,
                        COALESCE(p.talla, '??')          AS talla,
                        COALESCE(p.nom, '??')            AS nombre,
                        COALESCE(p.familia, '??')        AS familia,
                        COALESCE(p.subfamilia, '??')     AS subfamilia,
                        COALESCE(p.color, '??')          AS color,
                        COALESCE(p.temporada, '??')      AS temporada,
                        p.pvp                            AS pvp,
                        0                                AS prmp,
                        p.marca                          AS marca
                    FROM gestock_stock s
                    JOIN productes p
                        ON s.ean = p.ean
                    JOIN gestock_caixes c
                        ON s.codi_centre = c.codi_centre
                       AND s.palet = c.palet
                       AND s.caixa = c.caixa
                    WHERE s.codi_centre = %s
                """

                query_params: list = [almacen]

                if ean:
                    query += " AND p.ean = %s"
                    query_params.append(ean)

                if nombre:
                    query += " AND LOWER(p.nom) LIKE %s"
                    query_params.append(f"%{nombre.lower()}%")

                if talla:
                    query += " AND LOWER(p.talla) LIKE %s"
                    query_params.append(f"%{talla.lower()}%")

                # Familia: se permite lista separada por comas
                if familia:
                    for fam in familia.split(","):
                        if fam.strip():
                            query += " AND LOWER(TRIM(p.familia)) LIKE %s"
                            query_params.append(f"%{fam.strip().lower()}%")

                if color:
                    query += " AND LOWER(p.color) LIKE %s"
                    query_params.append(f"%{color.lower()}%")

                if temporada:
                    query += " AND LOWER(TRIM(p.temporada)) LIKE %s"
                    query_params.append(f"%{temporada.lower()}%")

                query += " ORDER BY p.ean"

                cursor.execute(query, tuple(query_params))

                columns = [col[0] for col in cursor.description]

                results = [
                    dict(zip(columns, row))
                    for row in cursor.fetchall()
                ]

                return StockExportResponse(
                    items=results
                )

    except DBError as e:
        logger.critical(f"ERROR SQL: {e}")
        raise ConnectionError("Error de la base de dades")
