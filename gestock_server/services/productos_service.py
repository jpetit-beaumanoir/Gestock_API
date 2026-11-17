"""
Catálogo de productos: tabla `productes`.

Columnas usadas: ean (VARCHAR(13), texto: no perder ceros iniciales), nom, color, talla,
familia, subfamilia, temporada, marca (CHAR(3), obligatoria) y pvp (obligatorio).
La BDD ya no tiene prmp: la API lo devuelve siempre como 0.0 por compatibilidad con la app.
La BDD trabaja en modo estricto: los textos se recortan a la longitud de cada columna.
"""
from gestock_server.db.database import db_pool
from gestock_server.db.driver import DBError, IntegrityError
from gestock_server.schemas.producto import ProductosGetResponse, MessageResponse
from gestock_server.config import (
    APIKEY_EXTERNAL,
    EXTERNAL_API_CONNECT_TIMEOUT,
    EXTERNAL_API_READ_TIMEOUT,
)

import time
from concurrent.futures import ThreadPoolExecutor

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


def _row_to_response(ean: str, row) -> ProductosGetResponse:
    nombre, familia, subfamilia, color, talla, pvp, temporada, marca = row

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


def _producto_no_encontrado() -> ProductosGetResponse:
    return ProductosGetResponse(
        ean="??", nombre="??", familia="??", subfamilia="??", color="??",
        talla="??", pvp=0.00, prmp=0.00, temporada="??", marca="??"
    )


def get_products_values(ean: str, codemag: str) -> ProductosGetResponse:
    """
    Devuelve los datos de un producto. Si no está en productes, lo busca en la API externa
    (marcas CCH, MGN, CRL) y, si lo encuentra, lo guarda en productes.

    La conexión a la BDD NO se mantiene abierta mientras se espera a la API externa
    (si no, unas cuantas búsquedas lentas dejaban el pool sin conexiones para el resto de la app).

    Raises:
        ConnectionError: error de base de datos o de la API externa (503).
    """
    ean = ean.strip()

    # 1) Buscar en la BDD (y liberar la conexión enseguida)
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
                row = cursor.fetchone()

    except DBError as e:
        logger.critical(f"ERROR SQL: {e}")
        raise ConnectionError("Error de la base de dades")

    if row:
        return _row_to_response(ean, row)

    # 2) No está: API externa (sin conexión a la BDD abierta)
    logger.info(f"NO S'HA TROBAT EL PRODUCTE {ean} A LA BASE DE DADES: ES CONSULTA LA API EXTERNA")

    product_values = get_product_external_API(ean, codemag)

    if not product_values:
        logger.info(f"NO S'HA TROBAT EL PRODUCTE {ean} A LA API EXTERNA")
        return _producto_no_encontrado()

    # 3) Guardar en productes (si falla el guardado, el producto se devuelve igualmente)
    if len(ean) > MAX_LEN["ean"]:
        logger.warning(f"EAN {ean} MASSA LLARG ({len(ean)} > 13): NO ES GUARDA A PRODUCTES")
        return product_values

    try:
        with db_pool.get_connection() as conn:
            with conn.cursor() as cursor:
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

    except IntegrityError:
        # Otro usuario lo ha guardado a la vez: no es un error
        logger.info(f"EL PRODUCTE {ean} JA S'HAVIA GUARDAT (petició simultània)")

    except Exception as e:
        logger.error(f"NO S'HA POGUT GUARDAR EL PRODUCTE {ean} DE LA API EXTERNA: {e}")

    return product_values


# ---------------------------------------------------------------------------
# API externa de partners (Korben)
# ---------------------------------------------------------------------------
EXTERNAL_API_URL = "https://api.partners.korben.com/API/SPN/services/infosProduitsSPN/getInfosProduit"
EXTERNAL_API_BRANDS = ["CCH", "MGN", "CRL"]   # orden de prioridad si el EAN existe en varias


def _parse_producto(ean: str, brand: str, data_object: dict) -> ProductosGetResponse:
    libelle = (data_object.get("libelle") or "").strip()
    pvp = str(data_object.get("pveuro") or 0)
    temporada = data_object.get("saison") or "??"

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

    try:
        pvp_value = round(float(pvp.replace(",", ".")), 2)
    except ValueError:
        pvp_value = 0.0

    return ProductosGetResponse(
        ean=ean,
        nombre=nombre,
        familia=familia,
        subfamilia=subfamilia,
        color=color,
        talla=talla,
        pvp=pvp_value,
        prmp=0.0,
        temporada=temporada,
        marca=brand
    )


def _consultar_marca(ean: str, codigo_almacen: str, brand: str):
    """
    Consulta una marca en la API externa.

    Returns:
        ("ok", ProductosGetResponse) | ("no", None) si no existe en esa marca | ("error", motivo)
    """
    t0 = time.monotonic()
    try:
        response = requests.get(
            EXTERNAL_API_URL,
            params={"brand": brand, "ean": ean, "codemag": codigo_almacen},
            headers={"Content-Type": "application/json", "KeyId": APIKEY_EXTERNAL},
            timeout=(EXTERNAL_API_CONNECT_TIMEOUT, EXTERNAL_API_READ_TIMEOUT),
        )
        ms = int((time.monotonic() - t0) * 1000)

        if response.status_code == 404:
            logger.info(f"API EXTERNA {brand} EAN {ean}: 404 (no existeix) en {ms} ms")
            return "no", None

        if response.status_code >= 400:
            logger.warning(f"API EXTERNA {brand} EAN {ean}: HTTP {response.status_code} en {ms} ms")
            return "error", f"HTTP {response.status_code}"

        data = response.json()
        data_array = (data.get("getInfosProduit") or {}).get("data") or []

        if data_array:
            logger.info(f"API EXTERNA {brand} EAN {ean}: TROBAT en {ms} ms")
            return "ok", _parse_producto(ean, brand, data_array[0])

        logger.info(f"API EXTERNA {brand} EAN {ean}: sense dades en {ms} ms")
        return "no", None

    except requests.exceptions.ConnectTimeout:
        motivo = f"timeout connectant (> {EXTERNAL_API_CONNECT_TIMEOUT}s)"
    except requests.exceptions.ReadTimeout:
        motivo = f"timeout esperant resposta (> {EXTERNAL_API_READ_TIMEOUT}s)"
    except requests.exceptions.ProxyError as e:
        motivo = f"error de proxy: {e}"
    except requests.exceptions.SSLError as e:
        motivo = f"error SSL: {e}"
    except requests.exceptions.ConnectionError as e:
        motivo = f"error de connexió: {e}"
    except ValueError as e:
        motivo = f"resposta no és JSON: {e}"
    except Exception as e:
        motivo = f"{type(e).__name__}: {e}"

    ms = int((time.monotonic() - t0) * 1000)
    logger.error(f"API EXTERNA {brand} EAN {ean}: ERROR en {ms} ms -> {motivo}")
    return "error", motivo


def get_product_external_API(ean: str, codigo_almacen: str):
    """
    Busca un producto en la API externa de partners en las marcas CCH, MGN y CRL.

    Las tres marcas se consultan EN PARALELO y con timeout, así que la búsqueda tarda como
    máximo lo que la consulta más lenta (connect + read timeout) y nunca se queda colgada.

    Returns:
        ProductosGetResponse con los datos del producto (prioridad CCH > MGN > CRL),
        o None si no existe en ninguna marca.

    Raises:
        ConnectionError: si no se ha encontrado y alguna marca ha fallado (timeout, red, HTTP 5xx...),
                         porque entonces no se puede asegurar que el producto no exista.
    """
    if not APIKEY_EXTERNAL:
        logger.error("APIKEY_EXTERNAL NO ESTÀ DEFINIDA AL gestock.env")
        raise ConnectionError("API externa no configurada")

    t0 = time.monotonic()
    logger.info(f"API EXTERNA: INICI CERCA EAN {ean} (codemag {codigo_almacen})")

    with ThreadPoolExecutor(max_workers=len(EXTERNAL_API_BRANDS)) as pool:
        futures = {
            brand: pool.submit(_consultar_marca, ean, codigo_almacen, brand)
            for brand in EXTERNAL_API_BRANDS
        }
        results = {brand: future.result() for brand, future in futures.items()}

    ms = int((time.monotonic() - t0) * 1000)

    for brand in EXTERNAL_API_BRANDS:
        estado, valor = results[brand]
        if estado == "ok":
            logger.info(f"API EXTERNA: EAN {ean} TROBAT A {brand} (total {ms} ms)")
            return valor

    errores = {brand: valor for brand, (estado, valor) in results.items() if estado == "error"}

    if errores:
        logger.error(f"API EXTERNA: EAN {ean} NO TROBAT I AMB ERRORS (total {ms} ms): {errores}")
        raise ConnectionError("Error con la comunicación de la API externa")

    logger.info(f"API EXTERNA: EAN {ean} NO EXISTEIX A CAP MARCA (total {ms} ms)")
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
