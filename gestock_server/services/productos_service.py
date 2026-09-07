from gestock_server.db.database import db_pool
from gestock_server.schemas.producto import ProductosGetResponse, MessageResponse
from gestock_server.config import APIKEY_EXTERNAL

from fastapi import UploadFile

import requests
import pymssql
import pandas as pd
from io import StringIO

import logging
logger = logging.getLogger(__name__)

REQUIRED_COLUMNS = {
    "EAN",
    "Product_Name",
    "Department_Categories",
    "Family_Categories",
    "Color_Name_FR",
    "Sizes",
    "Retail_Price",
    "PRMP",
    "Saison"
}


def get_products_values(ean: str, codemag: int):
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
                        SELECT p.nombre, p.familia, p.subfamilia, p.color, p.talla, p.pvp, p.prmp, p.temporada, p.marca
                        FROM productos p
                        WHERE p.ean = %s
                    """,
                    (ean,)  # Se pasa el EAN como parámetro para la consulta
                )

                # Obtener los resultados de la consulta
                product_values = cursor.fetchone()                

                # Si no se encuentra el producto en la base de datos, se consulta la API externa
                if not product_values:

                    logger.info(f"NO S'HA TROBAT EL PRODUCTE {ean} A LA BASE DE DADES")

                    product_values = get_product_external_API(ean, codemag)
                        
                    if product_values:

                        logger.info(f"S'HA TROBAT EL PRODUCTE {ean} EN LA API EXTERNA I GUARDA'T A LA BASE DE DADES")

                        cursor.execute("""
                        INSERT INTO productos (
                            ean, nombre, familia, subfamilia,
                            color, talla, pvp, prmp, temporada, marca
                        )
                        VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
                        """,
                        (
                            product_values.ean,
                            product_values.nombre,
                            product_values.familia,
                            product_values.subfamilia,
                            product_values.color,
                            product_values.talla,
                            product_values.pvp,
                            product_values.prmp,
                            product_values.temporada,
                            product_values.marca,
                        ))

                        conn.commit()

                        return product_values

                    logger.info(f"NO S'HA TROBAT EL PRODUCTE {ean} A LA API EXTERNA")

                    return ProductosGetResponse(
                        ean="??",
                        nombre="??",
                        familia="??",
                        subfamilia="??",
                        color="??",
                        talla="??",
                        pvp=0.00,
                        prmp=0.00,
                        temporada="??",
                        marca="??"
                    )
            
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
        logger.critical(f"ERROR SQL: {e}")
        raise ConnectionError("Error de la base de dades")

def get_product_external_API(ean: str, codigo_almacen: int):
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
            "KeyId": APIKEY_EXTERNAL  # ID de la clave API
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
                    nombre, familia, subfamilia, color, talla = "??", "??", "??", "??", "??"

                    # Si libelle tiene contenido, procesarlo para extraer nombre, color y talla
                    if libelle:
                        partes = libelle.split(" ")
                        nombre = partes[0] if len(partes) > 0 else "??"

                        # Si el nombre tiene tres partes, considerar la segunda como color y la tercera como talla
                        if len(partes) == 3:
                            color = partes[1] if len(partes) > 1 else "??"
                            talla = partes[-1] if len(partes) > 2 else "??"
                        # Si el nombre tiene más de tres partes, considerar las partes intermedias como color
                        elif len(partes) > 3:
                            color = f"{partes[1]} {partes[2]}" if len(partes) > 2 else "??"
                            talla = partes[-1] if len(partes) > 1 else "??"


                    # Log para registrar el éxito de la operación
                    logger.info(f"OBTENIDOS LOS DATOS EL PRODUCTO {ean}")


                    # Crear el objeto con los datos procesados
                    return ProductosGetResponse(
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

        except Exception as e:
            # En caso de error en la solicitud o conexión con la API
            logger.error(f"ERROR EN LA API EXTERNA: {e}")
            raise ConnectionError(f"Error con la comunicación de la API externa")
   
    return None

def upload_productos(
    csv_file: UploadFile,
    marca: str
) -> MessageResponse:

    marca = marca.strip().upper()

    logger.info(
        "INICIO IMPORTACIÓN CATÁLOGO | archivo=%s | marca=%s",
        csv_file.filename,
        marca
    )

    print("ENTRANDO EN upload_productos")

    try:
        content = csv_file.read()

        if not content:
            logger.warning(
                "CATÁLOGO VACÍO | archivo=%s | marca=%s",
                csv_file.filename,
                marca
            )
            raise ValueError("El archivo CSV está vacío")

        try:
            csv_df = pd.read_csv(
                StringIO(content.decode("utf-8")),
                sep=";",
                low_memory=False
            )

            encoding = "utf-8"

        except UnicodeDecodeError:
            csv_df = pd.read_csv(
                StringIO(content.decode("ISO-8859-1")),
                sep=";",
                low_memory=False
            )

            encoding = "ISO-8859-1"

        logger.info(
            "CSV LEÍDO | archivo=%s | codificación=%s | filas=%d",
            csv_file.filename,
            encoding,
            len(csv_df)
        )

        if "EAN" not in csv_df.columns:
            logger.error(
                "CSV INCORRECTO | archivo=%s | falta columna EAN | columnas=%s",
                csv_file.filename,
                list(csv_df.columns)
            )
            raise ValueError("El CSV no contiene la columna EAN")

        # Primero elimina filas completamente vacías.
        csv_df = csv_df.dropna(how="all").copy()

        # Normaliza los EAN.
        csv_df["EAN"] = (
            csv_df["EAN"]
            .astype("string")
            .str.strip()
            .str.replace(r"\.0$", "", regex=True)
        )

        # Elimina filas sin EAN y duplicados del propio CSV.
        csv_df = csv_df[
            csv_df["EAN"].notna() &
            csv_df["EAN"].ne("")
        ].copy()

        duplicated_eans = (
            csv_df.loc[
                csv_df["EAN"].duplicated(keep="first"),
                "EAN"
            ]
            .astype(str)
            .tolist()
        )

        if duplicated_eans:
            logger.warning(
                "EAN DUPLICADOS EN CSV | cantidad=%d | eans=%s",
                len(duplicated_eans),
                duplicated_eans
            )

        csv_df = csv_df.drop_duplicates(
            subset=["EAN"],
            keep="first"
        )

        csv_eans = set(
            csv_df["EAN"].astype(str).tolist()
        )

        logger.info(
            "EAN VÁLIDOS EN CSV | cantidad=%d",
            len(csv_eans)
        )

        # Para ver todos los EAN del CSV en el fichero de log.
        logger.debug(
            "LISTA EAN DEL CSV | eans=%s",
            sorted(csv_eans)
        )

        with db_pool.get_connection() as conn:
            try:
                with conn.cursor() as cursor:

                    cursor.execute("""
                        SELECT ean
                        FROM productos
                    """)

                    database_eans = {
                        str(row[0]).strip()
                        for row in cursor.fetchall()
                        if row[0] is not None
                    }

                    # EAN del CSV que ya están registrados.
                    existing_eans = csv_eans.intersection(
                        database_eans
                    )

                    # EAN del CSV que todavía no están registrados.
                    new_eans = csv_eans.difference(
                        database_eans
                    )

                    logger.info(
                        "COMPARACIÓN CATÁLOGO | csv=%d | existentes=%d | nuevos=%d",
                        len(csv_eans),
                        len(existing_eans),
                        len(new_eans)
                    )

                    logger.info(
                        "PRODUCTOS YA EXISTENTES | eans=%s",
                        sorted(existing_eans)
                    )

                    logger.info(
                        "PRODUCTOS NUEVOS | eans=%s",
                        sorted(new_eans)
                    )

                    csv_df = csv_df[
                        csv_df["EAN"].isin(new_eans)
                    ].copy()

                    if csv_df.empty:
                        logger.warning(
                            "SIN PRODUCTOS NUEVOS | archivo=%s | marca=%s",
                            csv_file.filename,
                            marca
                        )

                        raise ValueError(
                            "No hay productos nuevos para insertar "
                            "en el catálogo seleccionado"
                        )

                    csv_df["Retail_Price"] = (
                        csv_df["Retail_Price"]
                        .fillna(0)
                        .astype(str)
                        .str.replace(",", ".", regex=False)
                        .astype(float)
                    )

                    csv_df["PRMP"] = (
                        csv_df["PRMP"]
                        .fillna(0)
                        .astype(str)
                        .str.replace(",", ".", regex=False)
                        .astype(float)
                    )

                    insert_data = [
                        (
                            str(row["EAN"]),
                            row["Product_Name"]
                            if pd.notna(row["Product_Name"]) else "??",

                            row["Department_Categories"]
                            if pd.notna(row["Department_Categories"]) else "??",

                            row["Family_Categories"]
                            if pd.notna(row["Family_Categories"]) else "??",

                            row["Color_Name_FR"]
                            if pd.notna(row["Color_Name_FR"]) else "??",

                            row["Sizes"]
                            if pd.notna(row["Sizes"]) else "??",

                            float(row["Retail_Price"]),
                            float(row["PRMP"]),

                            row["Saison"]
                            if pd.notna(row["Saison"]) else "??",

                            marca
                        )
                        for _, row in csv_df.iterrows()
                    ]

                    insert_query = """
                        INSERT INTO productos (
                            ean,
                            nombre,
                            familia,
                            subfamilia,
                            color,
                            talla,
                            pvp,
                            prmp,
                            temporada,
                            marca
                        )
                        VALUES (
                            %s, %s, %s, %s, %s,
                            %s, %s, %s, %s, %s
                        )
                    """

                    inserted_count = 0

                    for data in insert_data:
                        ean = data[0]

                        try:
                            cursor.execute(
                                insert_query,
                                data
                            )

                            inserted_count += 1

                            logger.info(
                                "PRODUCTO INSERTADO | ean=%s | marca=%s",
                                ean,
                                marca
                            )

                        except pymssql.Error:
                            logger.exception(
                                "ERROR INSERTANDO PRODUCTO | ean=%s | marca=%s",
                                ean,
                                marca
                            )
                            raise

                conn.commit()

                logger.info(
                    "IMPORTACIÓN COMPLETADA | archivo=%s | marca=%s | insertados=%d",
                    csv_file.filename,
                    marca,
                    inserted_count
                )

            except Exception:
                conn.rollback()

                logger.exception(
                    "ROLLBACK IMPORTACIÓN | archivo=%s | marca=%s",
                    csv_file.filename,
                    marca
                )

                raise

        return MessageResponse(
            message=(
                f"S'han inserit {inserted_count} productes "
                f"correctament al catàleg {marca}"
            )
        )

    except Exception:
        logger.exception(
            "ERROR IMPORTANDO CATÁLOGO | archivo=%s | marca=%s",
            csv_file.filename,
            marca
        )
        raise

    finally:
        csv_file.close()