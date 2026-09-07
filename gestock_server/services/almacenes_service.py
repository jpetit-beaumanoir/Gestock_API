from gestock_server.db.database import db_pool
from gestock_server.schemas.almacen import (
    AlmacenInfo, 
    AlmacenResponse,
    AlmacenLoginResponse,
    MessageResponse
)
import pymssql

import logging
logger = logging.getLogger(__name__)

def get_almacenes() -> AlmacenResponse:
    """Ruta para obtener una lista de almacenes con información sobre palets, cajas y productos.

    Esta función consulta la base de datos para obtener un resumen de todos los almacenes, incluyendo:
    - Nombre del almacén
    - Código del almacén
    - Cantidad total de palets
    - Cantidad total de cajas
    - Total de productos (suma de la cantidad de productos en todas las cajas)

    Returns:
        JSONResponse: Un JSON con los datos de los almacenes, incluyendo el nombre, código, y los totales de palets, cajas y productos.
    
    Raises:
        HTTPException: Lanza un error 500 si ocurre un problema con la consulta a la base de datos.
    """
    try:        
        with db_pool.get_connection() as conn:
            with conn.cursor(as_dict=True) as cursor:

                # Consulta 1: cantidad de palets por almacen
                cursor.execute("""
                    SELECT almacen, COUNT(DISTINCT palet) AS cantidad_palets
                    FROM palets
                    GROUP BY almacen
                """)
                palets_data = {row["almacen"]: row["cantidad_palets"] for row in cursor.fetchall()}

                # Consulta 2: cantidad de cajas por almacen
                cursor.execute("""
                    SELECT almacen, COUNT(caja) AS cantidad_cajas
                    FROM cajas
                    GROUP BY almacen
                """)
                cajas_data = {row["almacen"]: row["cantidad_cajas"] for row in cursor.fetchall()}

                # Consulta 3: cantidad total de productos (distinct ean) por almacen desde stock
                cursor.execute("""
                    SELECT almacen, COUNT(ean) AS cantidad_productos
                    FROM stock
                    GROUP BY almacen
                """)
                productos_data = {row["almacen"]: row["cantidad_productos"] for row in cursor.fetchall()}

                # Consulta 4: almacenes con nombre y codigo
                cursor.execute("SELECT codigo, nombre FROM almacenes")
                almacenes_info = cursor.fetchall()

                # Combina todo en el diccionario final
                data = {}
                for almacen in almacenes_info:
                    codigo = almacen["codigo"]
                    
                    data[str(codigo)] = AlmacenInfo(
                        nombre=almacen["nombre"],
                        palets=palets_data.get(codigo, 0),
                        cajas=cajas_data.get(codigo, 0),
                        productos=productos_data.get(codigo, 0)
                    )

        return AlmacenResponse(almacenes=data)

    except pymssql.Error as e:
        logger.critical(f"ERROR SQL: {e}")
        raise ConnectionError("Error de base de dades")

def login_almacen(code: int) -> AlmacenLoginResponse:
    """Ruta para autenticar el acceso a un almacén utilizando su código.

    Esta función maneja la autenticación del almacén utilizando un código único.
    Se consulta la base de datos para verificar si existe un almacén con el código proporcionado.
    Si el almacén existe, se devuelve su nombre. Si no, se devuelve un error 204 indicando que no se encuentra.

    Args:
        code (int): El código único del almacén que se desea autenticar.

    Returns:
        dict: Un diccionario con el nombre del almacén si la autenticación es exitosa.

    Raises:
        HTTPException: Lanza una excepción HTTP 204 si no existe un almacén con el código proporcionado.
        HTTPException: Lanza una excepción HTTP 500 si ocurre un error en la base de datos.
    """
    try:

        # Obtiene una conexión al pool de base de datos y asegura que la conexión se maneje automáticamente
        with db_pool.get_connection() as conn:
            # Obtiene un cursor para ejecutar las consultas SQL
            with conn.cursor() as cursor:
                # Realiza una consulta SQL para buscar el almacén por su código
                cursor.execute("SELECT nombre FROM almacenes WHERE codigo = %s", (code,))
                # Recupera una fila del resultado de la consulta
                row = cursor.fetchone()
                
                # Si se encuentra el almacén, se devuelve el nombre
                if row:
                    return AlmacenLoginResponse(nombre= row[0])
                
                # Si no se encuentra el almacén, se rechaza la solicitud con un error 404
                raise ValueError(f"El magatzem {code} no existeix")
            
    except pymssql.Error as e:
        # Si ocurre un error al interactuar con la base de datos, se maneja de manera consistente
        logger.critical(f"ERROR SQL: {e}")
        raise ConnectionError("Error de base de dades")

def create_almacen(nombre: str, codigo: int) -> MessageResponse:
    """Ruta para crear un nuevo almacén en la base de datos.

    Esta función inserta un nuevo almacén con el nombre y código proporcionados en la base de datos.
    Si el almacén se crea correctamente, se devuelve un mensaje de éxito. Si ya existe un almacén con
    el mismo código, se lanza un error 409. En caso de cualquier otro error, se lanza un error 500.

    Args:
        name (str): El nombre del almacén a crear.
        code (int): El código único del almacén.

    Returns:
        dict: Un mensaje confirmando la creación exitosa del almacén.

    Raises:
        HTTPException: Lanza un error 400 si la creación falla, 409 si el código ya existe y 500 si ocurre un error en la base de datos.
    """
    
    try:

        # Obtiene una conexión al pool de base de datos
        with db_pool.get_connection() as conn:
            with conn.cursor() as cursor:
                # Ejecuta la consulta para insertar el nuevo almacén
                cursor.execute("INSERT INTO almacenes (nombre, codigo) VALUES (%s, %s)", (nombre, codigo))
                conn.commit()
            
                return MessageResponse(message = f"Magatzem '{nombre}' creat.")
                
    
    except pymssql.IntegrityError:
        # Maneja errores de integridad como cuando ya existe un almacén con el mismo código
        raise ValueError(f"Ja existeix un magatzem amb codi {codigo}")
    
    except pymssql.Error as e:
        # Si ocurre un error en la base de datos, se maneja de manera consistente
        logger.critical(f"ERROR SQL: {e}")
        raise ConnectionError("Error de base de dades")


def delete_almacen(codigo: int) -> MessageResponse:
    """
    Elimina un almacén de la base de datos por su código.
    
    Este endpoint permite eliminar un almacén basado en su código único. Si el almacén no existe, 
    devuelve un error 204. Si el almacén tiene elementos asignados (como palets o cajas), se lanza un 
    error 409, indicando que debe vaciarse antes de eliminarlo.

    Args:
        code (int): El código único del almacén a eliminar.

    Returns:
        dict: Un mensaje confirmando la eliminación exitosa del almacén o un mensaje de error si ocurre algún problema.

    Raises:
        HTTPException: Lanza un error 204 si no se encuentra el almacén con el código proporcionado. 
                        Lanza un error 409 si el almacén tiene elementos asignados y no se puede eliminar.
    """
    try:
        # Obtiene una conexión al pool de base de datos
        with db_pool.get_connection() as conn:
            with conn.cursor() as cursor:
                # Ejecuta la consulta para eliminar el almacén con el código proporcionado
                cursor.execute("DELETE FROM almacenes WHERE codigo = %s", (codigo,))
                conn.commit()
                    
                return MessageResponse(message=f"Magatzem '{codigo}' eliminat.")
                
    except pymssql.IntegrityError:
        # Si el almacén tiene elementos asignados, lanza un error 409 indicando que se debe vaciar antes de eliminarlo
        raise ValueError("S'ha intentat eliminar un magatzem amb elements a dintre")

    except pymssql.Error as e:
        # Si ocurre un error en la base de datos, se maneja de manera consistente
        logger.critical(f"ERROR SQL: {e}")
        raise ConnectionError("Error de la base de dades")

    