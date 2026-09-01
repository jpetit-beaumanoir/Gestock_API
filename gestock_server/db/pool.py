from fastapi import HTTPException
from gestock_server.db.connection import ConnectionWrapper
from gestock_server.config import (
    DB_DATABASE,
    DB_PASSWORD,
    DB_SERVER,
    DB_USER
)

import logging
logger = logging.getLogger(__name__)

import threading
import queue
import pymssql
import time

class ConnectionPool:
    """Implementa un pool de conexiones a la base de datos.
    
    Un pool de conexiones es un conjunto de conexiones reutilizables a la base de datos, que mejora la eficiencia al
    evitar la necesidad de crear nuevas conexiones cada vez que se hace una solicitud.
    """
    
    _instance = None  # Instancia única de la clase (Singleton)
    _lock = threading.Lock()  # Lock para garantizar acceso seguro en entornos multihilo
    
    def __new__(cls):
        """Implementa un Singleton para el pool de conexiones.
        
        Garantiza que solo exista una instancia del pool de conexiones, independientemente de cuántas veces se
        intente crear un nuevo objeto de la clase.
        
        Args:
            max_connections (int): Número máximo de conexiones que el pool puede mantener.
            connection_timeout (int): Tiempo máximo en segundos para esperar por una conexión disponible.
        
        Returns:
            object: Instancia del pool de conexiones.
        """
        with cls._lock:
            if cls._instance is None:
                cls._instance = super(ConnectionPool, cls).__new__(cls)
                cls._instance._initialized = False
            return cls._instance
    
    def __init__(self, max_connections=3, connection_timeout=5):
        """Inicializa el pool de conexiones.
        
        Inicializa el pool y configura el número máximo de conexiones y el tiempo de espera para obtener una
        conexión. Esta función se ejecuta solo la primera vez que se crea el pool (debido al patrón Singleton).
        
        Args:
            max_connections (int): Número máximo de conexiones que el pool puede manejar.
            connection_timeout (int): Tiempo de espera máximo para obtener una conexión.
        """
        if not hasattr(self, '_initialized') or not self._initialized:
            self.max_connections = max_connections
            self.connection_timeout = connection_timeout
            self._pool = queue.Queue(maxsize=max_connections)  # Cola para gestionar las conexiones
            self._active_connections = 0  # Contador de conexiones activas
            self._initialized = True
            logger.info(f"Pool de conexiones inicializado con {max_connections} conexiones máximas.")
    
    def _create_connection(self):
        """Crea una nueva conexión a la base de datos.
        
        Intenta crear y devolver una nueva conexión a la base de datos.
        
        Returns:
            connection: Objeto de conexión a la base de datos si es exitosa, None en caso de error.
        """
        try:
            conn = pymssql.connect(
                server = DB_SERVER,
                user = DB_USER,
                password = DB_PASSWORD,
                database = DB_DATABASE
            )
            logger.info("Nueva conexión establecida con la base de datos.")
            return conn
        except pymssql.OperationalError as e:
            # Maneja errores específicos de la base de datos
            error_msg = str(e)
            if hasattr(e, 'split'):
                try:
                    error_msg = str(e).split(',')[2].split(r'\n')[1]
                except (IndexError, AttributeError):
                    pass
            logger.critical(f"Error al crear conexión: {error_msg}")
            return None
    
    def get_connection(self) -> ConnectionWrapper:
        """Obtiene una conexión del pool o crea una nueva si hay espacio disponible.
        
        Si el pool de conexiones tiene conexiones disponibles, obtiene una de ellas.
        Si no, crea una nueva conexión si el número máximo de conexiones no ha sido alcanzado.
        
        Returns:
            ConnectionWrapper: Un objeto que envuelve la conexión obtenida del pool.
        """
        try:
            # Intenta obtener una conexión del pool sin esperar
            conn = self._pool.get(block=False)
            logger.debug("Conexión obtenida del pool.")
            
            # Verifica que la conexión sea válida
            if self._test_connection(conn):
                return ConnectionWrapper(self, conn)
            else:
                # Si la conexión no es válida, se crea una nueva
                logger.warning("Conexión del pool inválida. Creando una nueva.")
                self._active_connections -= 1  # Decrementa las conexiones activas debido a la conexión inválida
                return self._get_new_connection()
                
        except queue.Empty:
            # Si el pool está vacío, crea una nueva conexión si hay espacio
            return self._get_new_connection()
    
    def _get_new_connection(self):
        """Crea una nueva conexión si no se ha alcanzado el límite del pool.
        
        Si el número de conexiones activas es menor que el máximo permitido, se crea una nueva conexión.
        Si no hay espacio, espera hasta que una conexión se libere.
        
        Returns:
            ConnectionWrapper: Un objeto que envuelve la nueva conexión.
        
        Raises:
            HTTPException: Si se alcanza el límite de conexiones y no hay espacio.
        """
        with self._lock:
            if self._active_connections < self.max_connections:
                # Hay espacio para una nueva conexión
                self._active_connections += 1
                conn = self._create_connection()
                if conn is not None:
                    return ConnectionWrapper(self, conn)
                else:
                    self._active_connections -= 1
                    raise HTTPException(status_code=500, detail="No se puede establecer conexión con la base de datos.")
            else:
                # Espera hasta que haya espacio en el pool
                logger.warning("Alcanzado límite de conexiones. Esperando...")
                try:
                    # Intentar obtener una conexión con un tiempo de espera
                    start_time = time.time()
                    while time.time() - start_time < self.connection_timeout:
                        try:
                            conn = self._pool.get(block=True, timeout=0.5)
                            if self._test_connection(conn):
                                return ConnectionWrapper(self, conn)
                            else:
                                # Si la conexión no es válida, intentamos nuevamente
                                logger.warning("Conexión del pool inválida.")
                                self._active_connections -= 1
                        except queue.Empty:
                            continue
                    
                    # Si agotamos el tiempo de espera
                    raise HTTPException(status_code=503, 
                                       detail="Todas las conexiones están en uso. Intente más tarde.")
                                       
                except Exception as e:
                    logger.error(f"Error al esperar conexión: {str(e)}")
                    raise HTTPException(status_code=500, 
                                       detail="Error al obtener conexión de la base de datos.")
    
    def _test_connection(self, conn):
        """Prueba si una conexión sigue siendo válida.
        
        Ejecuta una consulta simple para comprobar si la conexión a la base de datos sigue activa.
        
        Args:
            conn: La conexión que se va a probar.
        
        Returns:
            bool: True si la conexión es válida, False en caso contrario.
        """
        try:
            cursor = conn.cursor()
            cursor.execute("SELECT 1")
            cursor.close()
            return True
        except Exception:
            logger.warning("Conexión no válida durante la prueba.")
            try:
                conn.close()
            except:
                pass
            return False
    
    def return_connection(self, conn):
        """Devuelve una conexión al pool.
        
        Devuelve la conexión al pool de conexiones si es válida. Si el pool está lleno, cierra la conexión.
        
        Args:
            conn: La conexión que se va a devolver al pool.
        """
        if conn is not None:
            try:
                self._pool.put(conn, block=False)
                logger.debug("Conexión devuelta al pool.")
            except queue.Full:
                # Si el pool está lleno, cerramos la conexión
                logger.warning("Pool lleno. Cerrando conexión excedente.")
                try:
                    conn.close()
                except:
                    pass
                with self._lock:
                    self._active_connections -= 1
    
    def close_all(self):
        """Cierra todas las conexiones en el pool.
        
        Cierra todas las conexiones activas y vacía el pool de conexiones.
        """
        with self._lock:
            closed_count = 0
            try:
                while not self._pool.empty():
                    conn = self._pool.get(block=False)
                    try:
                        conn.close()
                        closed_count += 1
                    except:
                        pass
            except:
                pass
            
            self._active_connections = 0
            logger.info(f"Pool cerrado. {closed_count} conexiones cerradas.")
