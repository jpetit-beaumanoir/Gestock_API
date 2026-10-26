"""
Pool de conexiones a MariaDB.

- Reutiliza hasta `max_connections` conexiones abiertas.
- Comprueba con ping() que una conexión sigue viva antes de entregarla.
- Al devolver una conexión hace rollback(): así ninguna transacción queda abierta y la
  siguiente petición ve siempre los datos actuales (con InnoDB, un SELECT sin commit/rollback
  deja una "foto" antigua de los datos en esa conexión).
- Si todas están ocupadas, espera hasta `connection_timeout` segundos y luego responde 503.
"""
import logging
import queue
import threading
import time

from fastapi import HTTPException

from gestock_server.db.connection import ConnectionWrapper
from gestock_server.db.driver import connect, check_config, describe_target, explain_error, DBError

logger = logging.getLogger(__name__)


class ConnectionPool:
    """Pool de conexiones (singleton)."""

    _instance = None
    _instance_lock = threading.Lock()

    def __new__(cls, *args, **kwargs):
        with cls._instance_lock:
            if cls._instance is None:
                cls._instance = super().__new__(cls)
                cls._instance._initialized = False
            return cls._instance

    def __init__(self, max_connections: int = 5, connection_timeout: int = 10):
        if self._initialized:
            return

        check_config()

        self.max_connections = max_connections
        self.connection_timeout = connection_timeout
        self._idle = queue.LifoQueue(maxsize=max_connections)   # conexiones libres
        self._created = 0                                        # conexiones abiertas (libres + en uso)
        self._lock = threading.Lock()
        self._initialized = True

        logger.info(
            f"Pool de conexiones inicializado: {describe_target()} "
            f"(máx. {max_connections} conexiones, espera {connection_timeout}s)"
        )

    # ------------------------------------------------------------------
    # Conexiones físicas
    # ------------------------------------------------------------------
    def _open(self):
        """Abre una conexión nueva. Lanza HTTPException 500 si MariaDB no responde."""
        try:
            conn = connect()
            logger.info(f"Nueva conexión establecida con la base de datos ({describe_target()}).")
            return conn
        except DBError as e:
            logger.critical(f"Error al conectar con la base de datos {describe_target()}: {explain_error(e)}")
            raise HTTPException(
                status_code=500,
                detail="No se puede establecer conexión con la base de datos."
            )

    @staticmethod
    def _is_alive(conn) -> bool:
        """True si la conexión sigue abierta (ping sin reconectar)."""
        try:
            conn.ping(reconnect=False)
            return True
        except Exception:
            return False

    @staticmethod
    def _close_quietly(conn) -> None:
        try:
            conn.close()
        except Exception:
            pass

    def _discard(self, conn) -> None:
        """Cierra una conexión y libera su hueco en el pool."""
        self._close_quietly(conn)
        with self._lock:
            self._created = max(0, self._created - 1)

    # ------------------------------------------------------------------
    # API pública
    # ------------------------------------------------------------------
    def get_connection(self) -> ConnectionWrapper:
        """
        Devuelve una conexión lista para usar (con `with`).

        Raises:
            HTTPException 500: no se puede conectar con MariaDB.
            HTTPException 503: todas las conexiones están en uso durante `connection_timeout`.
        """
        deadline = time.monotonic() + self.connection_timeout

        while True:
            # 1) Conexión libre del pool
            try:
                conn = self._idle.get_nowait()
            except queue.Empty:
                conn = None

            if conn is not None:
                if self._is_alive(conn):
                    return ConnectionWrapper(self, conn)
                logger.warning("Conexión del pool caducada. Se descarta y se abre otra.")
                self._discard(conn)
                continue

            # 2) Hay hueco: abrir una nueva (fuera del lock, conectar puede tardar)
            with self._lock:
                can_open = self._created < self.max_connections
                if can_open:
                    self._created += 1

            if can_open:
                try:
                    return ConnectionWrapper(self, self._open())
                except Exception:
                    with self._lock:
                        self._created = max(0, self._created - 1)
                    raise

            # 3) Pool lleno: esperar a que se libere una
            remaining = deadline - time.monotonic()
            if remaining <= 0:
                logger.warning("Todas las conexiones están en uso: se responde 503.")
                raise HTTPException(
                    status_code=503,
                    detail="Todas las conexiones están en uso. Intente más tarde."
                )

            try:
                conn = self._idle.get(timeout=min(remaining, 0.5))
            except queue.Empty:
                continue

            if self._is_alive(conn):
                return ConnectionWrapper(self, conn)
            self._discard(conn)

    def return_connection(self, conn) -> None:
        """Devuelve una conexión al pool, sin transacciones abiertas."""
        if conn is None:
            return

        try:
            # Cierra cualquier transacción pendiente (SELECT sin commit, error a medias...)
            conn.rollback()
        except Exception:
            logger.warning("Conexión inválida al devolverla al pool. Se descarta.")
            self._discard(conn)
            return

        try:
            self._idle.put_nowait(conn)
        except queue.Full:
            self._discard(conn)

    def close_all(self) -> None:
        """Cierra todas las conexiones libres del pool."""
        closed = 0
        while True:
            try:
                conn = self._idle.get_nowait()
            except queue.Empty:
                break
            self._discard(conn)
            closed += 1
        logger.info(f"Pool cerrado. {closed} conexiones cerradas.")
