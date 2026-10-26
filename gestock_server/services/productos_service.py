"""
Catálogo de productos: tabla `productes`.

Columnas usadas: ean (VARCHAR(13), texto: no perder ceros iniciales), nom, color, talla,
familia, subfamilia, temporada, marca (CHAR(3), obligatoria) y pvp (obligatorio).
La BDD ya no tiene prmp: la API lo devuelve siempre como 0.0 por compatibilidad con la app.
La BDD trabaja en modo estricto: los textos se recortan a la longitud de cada columna.
"""
from gestock_server.db.database import db_pool
from gestock_server.db.driver import DBError
from gestock_server.schemas.producto import ProductosGetResponse, MessageResponse
from gestock_server.config import APIKEY_EXTERNAL

import requests
import pandas as pd
from io import StringIO

import logging
logger = logging.getLogger(__name__)

# Longitudes máximas de las columnas de productes (modo estricto: un texto más largo da error)
MAX_LEN = {
    "ean": 13,
    "nom": 50,
    "color": 30,
    "talla": 10,
    "familia": 40,
    "subfamilia": 40,
    "temporada": 20,
    "marca": 3,
}

# Columnas obligatorias del CSV de catálogo. PRMP ya no se usa (si viene, se ignora).
REQUIRED_COLUMNS = {
    "EAN",
    "Product_Name",
    "Department_Categories",
    "Family_Categories",
    "Color_Name_FR",
    "Sizes",
    "Retail_Price",
    "Saison"
}

# Correspondencia columna del CSV -> columna de productes
CSV_TO_DB = {
    "Product_Name": "nom",
    "Department_Categories": "familia",
    "Family_Categories": "subfamilia",
    "Color_Name_FR": "color",
    "Sizes": "talla",
    "Saison": "temporada",
}

INSERT_PRODUCTE = """
    INSERT INTO productes (
        ean, nom, familia, subfamilia, color, talla, temporada, marca, pvp
    )
    VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s)
"""

LOTE = 1000


def _txt(value, column: str):
    """Texto limpio y recortado a la longitud de la columna, o None si está vacío."""
    if value is None:
        return None
    try:
        if pd.isna(value):
            return None
    except (TypeError, ValueError):
        pass
    text = str(value).strip()
    if not text:
        return None
    return text[:MAX_LEN[column]]


def _placeholders(n: int) -> str:
    return ", ".join(["%s"] * n)


def get_products_values(ean: str, codemag: str) -> ProductosGetResponse:
    """
    Devuelve los datos de un producto. Si no está en productes, lo busca en la API externa
    (marcas CCH, MGN, CRL) y, si lo encuentra, lo guarda en productes.

    Raises:
        ConnectionError: error de base de datos o de la API externa.
    """
    ean = ean.strip()

    try:
        with db_pool.get_connection() as conn:
            with conn.cursor() as cursor:
                cursor.execute(
                    """
                    SELECT nom, familia, subfamilia, color, talla, pvp, temporada, marca
                    FROM productes
                    WHERE ean = %s
                    """,
                    (ean,)
                )
                product_values = cursor.fetchone()

                # Si no está en la BDD, se consulta la API externa
                if not product_values:

                    logger.info(f"NO S'HA TROBAT EL PRODUCTE {ean} A LA BASE DE DADES")

                    product_values = get_product_external_API(ean, codemag)

                    if product_values:

                        if len(ean) <= MAX_LEN["ean"]:
                            cursor.execute(
                                INSERT_PRODUCTE,
                                (
                                    ean,
                                    _txt(product_values.nombre, "nom"),
                                    _txt(product_values.familia, "familia"),
                                    _txt(product_values.subfamilia, "subfamilia"),
                                    _txt(product_values.color, "color"),
                                    _txt(product_values.talla, "talla"),
                                    _txt(product_values.temporada, "temporada"),
                                    _txt(product_values.marca, "marca"),
                                    product_values.pvp,
                                )
                            )
                            conn.commit()

                            logger.info(f"S'HA TROBAT EL PRODUCTE {ean} EN LA API EXTERNA I GUARDAT A LA BASE DE DADES")
                        else:
                            logger.warning(f"EAN {ean} MASSA LLARG ({len(ean)} > 13): NO ES GUARDA A PRODUCTES")

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

        nombre, familia, subfamilia, color, talla, pvp, temporada, marca = product_values

        color = color or "??"

        # Limitar la longitud del color a 9 caracteres y agregar un punto final si es largo
        if len(color) > 9:
            color = color[0:9] + "."

        return ProductosGetResponse(
            ean=ean,
            nombre=nombre or "??",
            familia=familia or "??",
            subfamilia=subfamilia or "??",
            color=color,
            talla=talla or "??",
            pvp=float(pvp or 0),
            prmp=0.0,
            temporada=temporada or "??",
            marca=marca or "??"
        )

    except DBError as e:
        logger.critical(f"ERROR SQL: {e}")
        raise ConnectionError("Error de la base de dades")


def get_product_external_API(ean: str, codigo_almacen: str):
    """
    Busca un producto en la API externa de partners (marcas CCH, MGN y CRL, en ese orden).

    Returns:
        ProductosGetResponse con los datos del producto, o None si no existe en ninguna marca.

    Raises:
        ConnectionError: si falla la comunicación con la API externa.
    """
    for brand in ["CCH", "MGN", "CRL"]:

        url = f"https://api.partners.korben.com/API/SPN/services/infosProduitsSPN/getInfosProduit?brand={brand}&ean={ean}&codemag={codigo_almacen}"

        headers = {
            "Content-Type": "application/json",
            "KeyId": APIKEY_EXTERNAL
        }

        try:
            response = requests.get(url, headers=headers)
            response.raise_for_status()
            data = response.json()

            if "getInfosProduit" in data and "data" in data["getInfosProduit"]:
                data_array = data["getInfosProduit"]["data"]

                if len(data_array) > 0:
                    data_object = data_array[0]

                    libelle = data_object.get("libelle", "").strip()
                    pvp = str(data_object.get("pveuro") or 0)
                    temporada = data_object.get("saison", "??")
                    marca = brand

                    nombre, familia, subfamilia, color, talla = "??", "??", "??", "??", "??"

                    # libelle: "NOMBRE COLOR TALLA" o "NOMBRE COLOR1 COLOR2 ... TALLA"
                    if libelle:
                        partes = libelle.split(" ")
                        nombre = partes[0] if len(partes) > 0 else "??"

                        if len(partes) == 3:
                            color = partes[1]
                            talla = partes[-1]
                        elif len(partes) > 3:
                            color = f"{partes[1]} {partes[2]}"
                            talla = partes[-1]

                    logger.info(f"OBTENIDOS LOS DATOS EL PRODUCTO {ean}")

                    return ProductosGetResponse(
                        ean=ean,
                        nombre=nombre,
                        familia=familia,
                        subfamilia=subfamilia,
                        color=color,
                        talla=talla,
                        pvp=round(float(pvp), 2),
                        prmp=0.0,
                        temporada=temporada,
                        marca=marca
                    )

        except Exception as e:
            logger.error(f"ERROR EN LA API EXTERNA: {e}")
            raise ConnectionError("Error con la comunicación de la API externa")

    return None


def upload_productos(
    content: bytes,
    filename: str,
    marca: str
) -> MessageResponse:
    """
    Importa un catálogo de productos desde un CSV (separador ';') a productes.

    Se ejecuta en un hilo (run_in_threadpool) desde la ruta, que ya ha leído el archivo.
    Solo inserta los EAN que todavía no existen en productes. Todo en una transacción.

    Raises:
        ValueError: CSV vacío, columnas que faltan o marca incorrecta (400).
        ConnectionError: error de base de datos (503).
    """
    marca = marca.strip().upper()

    logger.info(
        "INICIO IMPORTACIÓN CATÁLOGO | archivo=%s | marca=%s",
        filename,
        marca
    )

    try:
        if not marca or len(marca) > MAX_LEN["marca"]:
            raise ValueError("La marca ha de tenir com a màxim 3 caràcters (p. ex. CCH, MGN, CRL)")

        if not content:
            logger.warning(
                "CATÁLOGO VACÍO | archivo=%s | marca=%s",
                filename,
                marca
            )
            raise ValueError("El archivo CSV está vacío")

        # dtype=str: los EAN se leen como texto para no perder los ceros iniciales
        try:
            csv_df = pd.read_csv(
                StringIO(content.decode("utf-8-sig")),
                sep=";",
                dtype=str,
                keep_default_na=False
            )
            encoding = "utf-8"

        except UnicodeDecodeError:
            csv_df = pd.read_csv(
                StringIO(content.decode("ISO-8859-1")),
                sep=";",
                dtype=str,
                keep_default_na=False
            )
            encoding = "ISO-8859-1"

        logger.info(
            "CSV LEÍDO | archivo=%s | codificación=%s | filas=%d",
            filename,
            encoding,
            len(csv_df)
        )

        csv_df.columns = [str(c).strip() for c in csv_df.columns]

        missing_columns = REQUIRED_COLUMNS - set(csv_df.columns)

        if missing_columns:
            logger.error(
                "CSV INCORRECTO | archivo=%s | faltan columnas=%s | columnas=%s",
                filename,
                sorted(missing_columns),
                list(csv_df.columns)
            )
            raise ValueError(
                f"Al CSV li falten les columnes: {', '.join(sorted(missing_columns))}"
            )

        # Normaliza los EAN (texto, sin espacios)
        csv_df["EAN"] = csv_df["EAN"].astype(str).str.strip()

        # Filas sin EAN
        csv_df = csv_df[csv_df["EAN"] != ""].copy()

        # EAN más largos de 13 caracteres: no caben en productes
        too_long = csv_df.loc[csv_df["EAN"].str.len() > MAX_LEN["ean"], "EAN"].tolist()
        if too_long:
            logger.warning(
                "EAN DEMASIADO LARGOS (>13) IGNORADOS | cantidad=%d | eans=%s",
                len(too_long),
                too_long[:50]
            )
            csv_df = csv_df[csv_df["EAN"].str.len() <= MAX_LEN["ean"]].copy()

        duplicated_eans = csv_df.loc[csv_df["EAN"].duplicated(keep="first"), "EAN"].tolist()

        if duplicated_eans:
            logger.warning(
                "EAN DUPLICADOS EN CSV | cantidad=%d | eans=%s",
                len(duplicated_eans),
                duplicated_eans[:50]
            )

        csv_df = csv_df.drop_duplicates(subset=["EAN"], keep="first")

        csv_eans = csv_df["EAN"].tolist()

        logger.info("EAN VÁLIDOS EN CSV | cantidad=%d", len(csv_eans))

        inserted_count = 0

        with db_pool.get_connection() as conn:
            try:
                with conn.cursor() as cursor:

                    # EAN del CSV que ya existen (por lotes: productes tiene ~570.000 filas)
                    existing_eans = set()
                    for i in range(0, len(csv_eans), LOTE):
                        lote = csv_eans[i:i + LOTE]
                        cursor.execute(
                            f"SELECT ean FROM productes WHERE ean IN ({_placeholders(len(lote))})",
                            lote
                        )
                        existing_eans.update(str(row[0]) for row in cursor.fetchall())

                    new_df = csv_df[~csv_df["EAN"].isin(existing_eans)]

                    logger.info(
                        "COMPARACIÓN CATÁLOGO | csv=%d | existentes=%d | nuevos=%d",
                        len(csv_eans),
                        len(existing_eans),
                        len(new_df)
                    )

                    if new_df.empty:
                        logger.warning(
                            "SIN PRODUCTOS NUEVOS | archivo=%s | marca=%s",
                            filename,
                            marca
                        )

                        return MessageResponse(
                            message=(
                                "No hi ha productes nous per inserir "
                                f"al catàleg {marca}"
                            )
                        )

                    def _price(value) -> float:
                        text = str(value or "").strip().replace(",", ".")
                        try:
                            return round(float(text), 2) if text else 0.0
                        except ValueError:
                            return 0.0

                    insert_data = [
                        (
                            row["EAN"],
                            _txt(row["Product_Name"], "nom"),
                            _txt(row["Department_Categories"], "familia"),
                            _txt(row["Family_Categories"], "subfamilia"),
                            _txt(row["Color_Name_FR"], "color"),
                            _txt(row["Sizes"], "talla"),
                            _txt(row["Saison"], "temporada"),
                            marca,
                            _price(row["Retail_Price"]),
                        )
                        for _, row in new_df.iterrows()
                    ]

                    for i in range(0, len(insert_data), LOTE):
                        cursor.executemany(INSERT_PRODUCTE, insert_data[i:i + LOTE])
                        inserted_count += len(insert_data[i:i + LOTE])

                conn.commit()

                logger.info(
                    "IMPORTACIÓN COMPLETADA | archivo=%s | marca=%s | insertados=%d",
                    filename,
                    marca,
                    inserted_count
                )

            except Exception:
                conn.rollback()

                logger.exception(
                    "ROLLBACK IMPORTACIÓN | archivo=%s | marca=%s",
                    filename,
                    marca
                )

                raise

        return MessageResponse(
            message=(
                f"S'han inserit {inserted_count} productes "
                f"correctament al catàleg {marca}"
            )
        )

    except ValueError:
        raise

    except DBError as e:
        logger.critical(f"ERROR SQL IMPORTANDO CATÁLOGO: {e}")
        raise ConnectionError("Error de la base de dades")

    except Exception:
        logger.exception(
            "ERROR IMPORTANDO CATÁLOGO | archivo=%s | marca=%s",
            filename,
            marca
        )
        raise
