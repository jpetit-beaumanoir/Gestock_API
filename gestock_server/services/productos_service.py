from gestock_server.db.database import db_pool
from gestock_server.schemas.producto import ProductosGetResponse
from fastapi import requests

import logging
import pymssql

async def get_products_values(ean: str, codemag: int):
    """
    Obtiene los valores de un producto desde la base de datos, o en su defecto, los obtiene desde una API externa.

    La función busca los detalles del producto (nombre, familia, color, talla, precio, etc.) en la base de datos 
    utilizando el EAN del producto. Si no se encuentran valores en la base de datos, realiza una consulta externa 
    a una API para obtener dicha información.

    Args:
        ean (str): El código EAN del producto que se busca.
        codemag (int): El código del almacén donde se encuentra el producto.

    Returns:
        JSONResponse: Un objeto JSON con los valores del producto.

    Raises:
        HTTPException: Si ocurre un error con la base de datos o la API externa.
    """
    try:

        with db_pool.get_connection() as conn:
            # Conexión a la base de datos y ejecución de consulta
            with conn.cursor() as cursor:

                
                cursor.execute(
                    """
                        SELECT s.id, p.nombre, p.familia, p.subfamilia, p.color, p.talla, p.pvp, p.prmp, p.temporada, p.marca
                        FROM productos p
                        LEFT JOIN stock s ON p.ean = s.ean
                        WHERE p.ean = %s
                        ORDER BY s.ean
                    """,
                    (ean,)  # Se pasa el EAN como parámetro para la consulta
                )

                # Obtener los resultados de la consulta
                product_values = cursor.fetchone()

                # Si no se encuentra el producto en la base de datos, se consulta la API externa
                if not product_values:

                    product_values = await get_product_external_API(ean, codemag)
                    
                    if product_values:
                        
                        cursor.execute("""INSERT INTO productos (ean, nombre, familia, subfamilia, color, talla, pvp, prmp, temporada, marca)
                        VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s)""",
                        (product_values['ean'],product_values['nombre'],product_values['familia'],product_values['subfamilia'],product_values['color'],
                        product_values['talla'],product_values['pvp'],product_values['prmp'],product_values['temporada'],product_values['marca'],))
                        
                        product_values.pop('ean')
                        
                        product_values = list(product_values.values())
            
                # Si el producto se encuentra en la base de datos, se extraen los valores
                nombre, familia, subfamilia, color, talla, pvp, prmp, temporada, marca = product_values

                # Limitar la longitud del color a 9 caracteres y agregar un punto final si es largo
                if len(color) > 9:
                    color = color[0:9] + "."

                # Retornar los datos en formato JSON
                return ProductosGetResponse(
                    ean = ean,
                    nombre = nombre,
                    familia = familia,
                    subfamilia = subfamilia,
                    color = color,
                    talla = talla,
                    pvp = float(pvp),
                    prmp = float(prmp),
                    temporada = temporada,
                    marca = marca
                )

    except pymssql.Error as e:
        logging.critical(f"ERROR SQL: {e}")
        raise ConnectionError("Error de la base de dades")

async def get_product_external_API(ean: str, codigo_almacen: int):
    """
    Obtiene la información de un producto desde una API externa utilizando su EAN y código de almacén.

    Este endpoint intenta obtener la información de un producto de tres marcas diferentes (CCH, MGN, CRL)
    desde una API externa. En caso de que el producto se encuentre en la respuesta de la API, se devuelve
    la información procesada del producto, como nombre, familia, subfamilia, color, talla, precios y temporada.

    Args:
        ean (str): El código EAN del producto que se busca.
        codigo_almacen (int): El código del almacén donde se encuentra el producto.

    Returns:
        JSONResponse: Un objeto JSON con los datos procesados del producto.
    
    Raises:
        HTTPException: Lanza un error 500 en caso de un fallo con la API externa,
                       o un error 404 si el producto no se encuentra en la API.
    """
    
    # Intentar obtener los datos de tres marcas diferentes
    for brand in ["CCH", "MGN", "CRL"]:
        
        # URL de la API externa, construida con el EAN y el código de almacén
        url = f"https://api.partners.korben.com/API/SPN/services/infosProduitsSPN/getInfosProduit?brand={brand}&ean={ean}&codemag={codigo_almacen}"
        
        # Encabezados para la solicitud HTTP
        headers = {
            "Content-Type": "application/json",
            "KeyId": "93510b58-06dc-4efb-b1ab-dbdc23478d0d"  # ID de la clave API
        }

        try:
            # Realizar la solicitud GET a la API externa
            response = requests.get(url, headers=headers)
            
            # Verificar que la respuesta sea exitosa
            response.raise_for_status()

            # Analizar la respuesta JSON
            data = response.json()

            # Verificar que la respuesta contenga los datos esperados
            if "getInfosProduit" in data and "data" in data["getInfosProduit"]:
                data_array = data["getInfosProduit"]["data"]

                # Si se encuentran datos, procesarlos
                if len(data_array) > 0:
                    data_object = data_array[0]

                    # Extraer datos del objeto con valores predeterminados si están vacíos
                    libelle = data_object.get("libelle", "").strip()  # Nombre del producto
                    pvp = str(data_object.get("pveuro", ""))  # Precio de venta
                    prmp = str(data_object.get("prmp", 0))  # Precio de referencia
                    temporada = data_object.get("saison", "??")  # Temporada
                    marca = brand

                    # Inicializar valores por defecto para otros campos
                    nombre, familia, subfamilia, color, talla = "", "??", "", "", ""

                    # Si libelle tiene contenido, procesarlo para extraer nombre, color y talla
                    if libelle:
                        partes = libelle.split(" ")
                        nombre = partes[0] if len(partes) > 0 else ""

                        # Si el nombre tiene tres partes, considerar la segunda como color y la tercera como talla
                        if len(partes) == 3:
                            color = partes[1] if len(partes) > 1 else ""
                            talla = partes[-1] if len(partes) > 2 else ""
                        # Si el nombre tiene más de tres partes, considerar las partes intermedias como color
                        elif len(partes) > 3:
                            color = f"{partes[1]} {partes[2]}" if len(partes) > 2 else ""
                            talla = partes[-1] if len(partes) > 1 else ""

                    # Crear el objeto con los datos procesados
                    product_data = ProductInfo(
                        ean = ean,
                        nombre = nombre,
                        familia = familia,
                        subfamilia = subfamilia,
                        color = color,
                        talla = talla,
                        pvp = round(float(pvp),2),
                        prmp = round(float(prmp),2),
                        temporada = temporada,
                        marca = marca
                    )
                    
                    
                    # Log para registrar el éxito de la operación
                    logging.info(f"OBTENIDOS LOS DATOS EL PRODUCTO {ean}")
                    
                    # Devolver los datos del producto en formato JSON
                    return product_data

        except Exception as e:
            # En caso de error en la solicitud o conexión con la API
            logging.error(f"ERROR EN LA API EXTERNA: {e}")
            raise ConnectionError(f"Error con la comunicación de la API externa")
   
    return None