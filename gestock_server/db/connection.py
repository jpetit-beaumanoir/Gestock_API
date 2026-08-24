import pymssql

class ConnectionWrapper:
    """
    Envuelve una conexión a la base de datos para facilitar su manejo
    dentro de un contexto (usando el patrón de contexto `with`).
    
    Este objeto asegura que las conexiones sean devueltas al pool de conexiones
    automáticamente cuando se cierran o se eliminan.
    """

    def __init__(self, pool, connection):
        """
        Inicializa el wrapper de la conexión.
        
        Este wrapper gestiona la conexión a la base de datos y asegura que
        sea devuelta al pool una vez se haya terminado su uso.

        Args:
            pool (ConnectionPool): Instancia del pool de conexiones que gestionará la conexión.
            connection (pymssql.Connection): Objeto de conexión a la base de datos que será envuelto.
        """
        self.pool = pool  # El pool de conexiones al que esta conexión pertenece
        self.connection = connection  # La conexión a la base de datos
        self.closed = False  # Bandera para saber si la conexión ya ha sido cerrada

    def __enter__(self) -> pymssql.Connection:
        """Inicia el contexto de la conexión, devolviendo la conexión.
        
        Este método es utilizado al entrar en un bloque `with` para obtener
        la conexión y usarla dentro del contexto.
        
        Returns:
            connection: Devuelve la conexión envuelta para ser utilizada en el bloque `with`.
        """
        return self.connection
    
    def __exit__(self, exc_type, exc_val, exc_tb):
        """Cierra la conexión al salir del contexto.
        
        Este método es ejecutado automáticamente cuando el bloque `with` termina.
        Se asegura de que la conexión se devuelva al pool.
        
        Args:
            exc_type: El tipo de excepción que ocurrió (si la hubo).
            exc_val: El valor de la excepción (si la hubo).
            exc_tb: El traceback de la excepción (si la hubo).
        """
        self.close()  # Llama al método close para devolver la conexión al pool
    
    def close(self):
        """Devuelve la conexión al pool de conexiones si no está cerrada.
        
        Si la conexión aún no ha sido cerrada, se devuelve al pool para su reutilización.
        Una vez cerrada, se marca como `closed` para evitar cerrarla varias veces.
        """
        if not self.closed:
            self.pool.return_connection(self.connection)  # Devuelve la conexión al pool
            self.closed = True  # Marca la conexión como cerrada para evitar futuras devoluciones
    
    def __del__(self):
        """Llama al método close cuando el objeto es destruido.
        
        Si el objeto es destruido (por ejemplo, cuando se elimina del sistema o va fuera de alcance),
        este método asegura que la conexión sea cerrada y devuelta al pool.
        """
        self.close()  # Llama al método close para devolver la conexión cuando el objeto es destruido
