from gestock_server.db.database import db_pool
from gestock_server.schemas.stock import (
    StockAddRequest, 
    StockDeleteRequest, 
    StockMoveRequest, 
    StockGetResponse, 
    StockInfo, 
    StockExportRequest,
    StockExportResponse,
    MessageResponse
)

import logging
import pymssql

def get_stock_caja(almacen: int, palet: int, caja: int) -> StockGetResponse:
    """
    Obtiene el stock de productos en una caja específica, identificada por su almacen, palet y caja.

    La función consulta la base de datos para obtener el stock asociado a un producto en particular
    dentro de una caja, palet y almacen específicos. Si encuentra coincidencias, las agrupa por EAN,
    sumando la cantidad de cada producto dentro de la caja.

    Args:
        almacen (int): El código del almacen donde se encuentra el stock.
        palet (int): El código del palet donde se encuentra la caja.
        caja (int): El código de la caja que contiene el stock.

    Returns:
        JSONResponse: Un objeto JSON con el stock y la cantidad total de productos en la caja.

    Raises:
        HTTPException: Si ocurre un error al consultar la base de datos.
    """
    data = {}

    try:

        with db_pool.get_connection() as conn:
            # Se realiza la consulta SQL a la base de datos para obtener el stock de la caja especificada
            with conn.cursor() as cursor:
                cursor.execute(
                    """
                        SELECT s.id, p.ean, p.nombre, p.color, p.talla, p.temporada
                        FROM stock s 
                        JOIN productos p ON s.ean = p.ean 
                        WHERE s.almacen = %s AND s.palet = %s AND s.caja = %s
                        ORDER BY s.ean
                    """,
                    (almacen, palet, caja,)
                )

                stock = cursor.fetchall()

                # Si no hay productos en la caja, se devuelve un JSON con stock vacío y cantidad total 0
                if not stock:
                    return StockGetResponse(stock=data, total=0)

                # Procesamiento de los resultados obtenidos
                for row_stock in stock:
                    id_producto, ean, nombre, color, talla, temporada = row_stock

                    # Verificar si el EAN ya existe en el diccionario 'data' y agregar la cantidad
                    if ean in data.keys():
                        data[ean]["cantidad"] += 1
                        data[ean]["id"].append(id_producto)

                    else:
                        # Si es un EAN nuevo, se agrega una entrada en el diccionario
                        data[str(ean)] = StockInfo(
                            id=id_producto,
                            nombre=nombre,
                            color=color,
                            talla=talla,
                            temporada=temporada,
                            cantidad=1
                        )
                        

                # Se devuelve el stock y la cantidad total de productos en la caja
                return StockGetResponse(stock=data, total=len(stock))

    except pymssql.Error as e:
        logging.critical(f"ERROR SQL: {e}")
        raise ConnectionError("Error de la base de dades")

def add_stock(body: StockAddRequest) -> MessageResponse:
    """
    Agrega múltiples productos al stock en la base de datos.
    
    Recibe una lista de EANs y agrega los productos correspondientes a la base de datos 
    en la caja, palet y almacén especificados.

    Args:
        request (AddStockRequest): Datos de entrada con el almacén, palet, caja, y la lista de EANs.

    Returns:
        dict: Respuesta indicando la cantidad de productos añadidos con éxito.
    
    Raises:
        HTTPException: Si la lista de EANs está vacía o ocurre un error con la base de datos.
    """

    # Validar que la lista de EANs no esté vacía
    if not isinstance(body.eans, list) or len(body.eans) == 0:
        raise ValueError("La lista de productes (EANs) no pot estar buida.")

    try:

        # Conexión a la base de datos
        with db_pool.get_connection() as conn:
            with conn.cursor() as cursor:

                # Preparamos los datos para la inserción masiva
                stock_data = [(ean, body.caja, body.palet, body.almacen) for ean in body.eans]

                # Consulta SQL para insertar los productos
                insert_query = """
                    INSERT INTO stock (ean, caja, palet, almacen) VALUES (%s, %s, %s, %s)
                """
                
                # Ejecutamos la inserción masiva
                cursor.executemany(insert_query, stock_data)

                insertados = cursor.rowcount
                
                # Confirmamos la transacción
                conn.commit()

                return MessageResponse(message=f"Insertados {insertados} productos con éxito.")

    except pymssql.Error as e:
        logging.critical(f"ERROR SQL: {e}")
        raise ConnectionError("Error de la base de dades")

def delete_stock(body: StockDeleteRequest) -> MessageResponse:
    """
    Elimina múltiples productos del stock en la base de datos.

    Recibe una lista de IDs de productos y los elimina de la base de datos en la caja, palet y almacén especificados.

    Args:
        request (DeleteStockRequest): Datos de entrada con el almacén, palet, caja, y la lista de IDs de los productos.

    Returns:
        dict: Respuesta indicando la cantidad de productos eliminados con éxito.
    
    Raises:
        HTTPException: Si la lista de IDs está vacía o ocurre un error con la base de datos.
    """

    # Validar que la lista de IDs no esté vacía
    if not isinstance(body.ids, list) or len(body.ids) == 0:
        raise ValueError("La lista de productes (EANs) no pot estar buida.")

    # Conexión a la base de datos
    try:

        with db_pool.get_connection() as conn:
            with conn.cursor() as cursor:
                # Preparamos los datos para la eliminación masiva
                stock_data = [(id,) for id in body.ids]

                # Consulta SQL para eliminar los productos
                cursor.executemany("DELETE FROM stock WHERE id = %s", stock_data)

                # Obtenemos la cantidad de productos eliminados
                eliminados = cursor.rowcount

                # Confirmamos la transacción
                conn.commit()

                # Log para indicar éxito en la operación
                return MessageResponse(message=f"Eliminados {eliminados} productos con éxito.")

    except pymssql.Error as e:
        logging.critical(f"ERROR SQL: {e}")
        raise ConnectionError("Error de la base de dades")

def move_stock(body: StockMoveRequest) -> MessageResponse:
    """
    Mueve productos dentro del stock de una caja/palet a otra.

    Recibe una lista de IDs de productos y los mueve dentro del almacén, palet y caja especificados.

    Args:
        request (MoveStockRequest): Datos de entrada con el almacén, palet, caja, y la lista de IDs de los productos.

    Returns:
        dict: Respuesta indicando la cantidad de productos movidos con éxito.
    
    Raises:
        HTTPException: Si la lista de IDs está vacía, la caja destino no existe, o si ocurre un error con la base de datos.
    """

    # Validar que la lista de productos no esté vacía
    if not body.ids:
        raise ValueError("La lista de productes no pot estar buida.")

    try:

        # Conexión a la base de datos
        with db_pool.get_connection() as conn:
            with conn.cursor() as cursor:
                # Verificar si la caja destino existe en la base de datos
                cursor.execute(
                    "SELECT 1 FROM cajas WHERE caja = %s AND palet = %s AND almacen = %s",
                    (body.caja, body.palet, body.almacen)
                )

                # Construir los datos para la actualización del movimiento de stock
                stock_data = [(body.palet, body.caja, id) for id in body.ids]

                # Consulta SQL para mover los productos
                update_query = "UPDATE stock SET palet = %s, caja = %s WHERE id = %s"
                cursor.executemany(update_query, stock_data)

                # Obtener el número de productos movidos
                moved_count = cursor.rowcount

                # Confirmar la transacción
                conn.commit()

                # Log para indicar éxito en la operación
                return MessageResponse(message=f"Movidos {moved_count} productos con éxito.")

    except pymssql.Error as e:
        logging.critical(f"ERROR SQL: {e}")
        raise ConnectionError("Error de la base de dades")
    

def filtered_search(
    data: StockExportRequest
) -> StockExportResponse:

    """
    Realiza una búsqueda filtrada de productos en un almacén específico. Los filtros incluyen 
    EAN, talla, nombre, familia, color y temporada.

    Args:
        almacen (int): El código del almacén donde se realizará la búsqueda.
        ean (str, opcional): EAN del producto para filtrar.
        talla (str, opcional): Talla del producto para filtrar.
        nombre (str, opcional): Nombre del producto para filtrar.
        familia (str, opcional): Familia del producto para filtrar.
        color (str, opcional): Color del producto para filtrar.
        temporada (str, opcional): Temporada del producto para filtrar.

    Returns:
        JSONResponse: Lista de productos que coinciden con los filtros aplicados.

    Raises:
        HTTPException: Si ocurre un error en la base de datos durante la consulta.
    """
    
    try:
        # Establecer conexión a la base de datos
        with db_pool.get_connection() as conn:
            with conn.cursor() as cursor:
                # Consulta base para obtener productos con los campos relevantes
                query = """
                    SELECT 
                        s.ean, s.palet, s.caja, c.descripcion  AS desc_caja, c.temporada  AS temp_caja, s.almacen, 
                        p.talla, p.nombre, p.familia, p.subfamilia, 
                        p.color, p.temporada, 
                        CAST(p.pvp AS FLOAT) AS pvp, 
                        CAST(p.prmp AS FLOAT) AS prmp, 
                        p.marca
                    FROM stock s
                    JOIN productos p ON s.ean = p.ean
                    JOIN cajas c ON s.caja = c.caja AND s.palet = c.palet AND s.almacen = c.almacen
                    WHERE s.almacen = %s
                """
                
                # Lista para almacenar los parámetros de consulta
                query_params = [data.almacen]

                # Filtrar por EAN si se proporciona
                if data.ean:
                    query += " AND p.ean = %s"
                    query_params.append(data.ean)

                # Filtrar por nombre si se proporciona
                if data.nombre:
                    query += " AND LOWER(p.nombre) LIKE %s"
                    query_params.append(f"%{data.nombre.lower()}%")

                # Filtrar por talla si se proporciona
                if data.talla:
                    query += " AND LOWER(p.talla) LIKE %s"
                    query_params.append(f"%{data.talla.lower()}%")

                # Filtrar por familia si se proporciona (se permite lista separada por comas)
                if data.familia:
                    for fam in data.familia.split(","):
                        if fam.strip():  # Evitar filtros vacíos
                            query += " AND LTRIM(RTRIM(p.familia)) LIKE %s"
                            query_params.append(f"%{fam.strip().lower()}%")

                # Filtrar por color si se proporciona
                if data.color:
                    query += " AND LOWER(p.color) LIKE %s"
                    query_params.append(f"%{data.color.lower()}%")

                # Filtrar por temporada si se proporciona
                if data.temporada:
                    query += " AND LTRIM(RTRIM(p.temporada)) LIKE LOWER(%s)"
                    query_params.append(f"%{data.temporada.lower()}%")

                # Ordenar los resultados por EAN
                query += " ORDER BY p.ean"

                # Ejecutar la consulta con los parámetros dinámicos
                cursor.execute(query, tuple(query_params))

                # Obtener los nombres de las columnas de la consulta
                columns = [col[0] for col in cursor.description]

                results = [
                    dict(zip(columns, row))
                    for row in cursor.fetchall()
                ]

                return StockExportResponse(
                    items=results
                )


    except pymssql.Error as e:
        logging.critical(f"ERROR SQL: {e}")
        raise ConnectionError("Error de la base de dades")