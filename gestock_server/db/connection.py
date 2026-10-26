class ConnectionWrapper:
    """
    Envuelve una conexión del pool para usarla con `with`:

        with db_pool.get_connection() as conn:
            with conn.cursor() as cursor:
                ...
                conn.commit()

    Al salir del bloque la conexión vuelve al pool. Si dentro del bloque hubo una
    excepción, la transacción se deshace antes de devolverla.
    """

    def __init__(self, pool, connection):
        self.pool = pool                # Pool al que pertenece la conexión
        self.connection = connection    # Conexión PyMySQL
        self.closed = False             # Evita devolverla dos veces

    def __enter__(self):
        return self.connection

    def __exit__(self, exc_type, exc_val, exc_tb):
        if exc_type is not None:
            try:
                self.connection.rollback()
            except Exception:
                pass
        self.close()

    def close(self):
        """Devuelve la conexión al pool (una sola vez)."""
        if not self.closed:
            self.closed = True
            self.pool.return_connection(self.connection)

    def __del__(self):
        self.close()
