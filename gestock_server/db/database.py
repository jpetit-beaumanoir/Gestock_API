from gestock_server.db.pool import ConnectionPool
from gestock_server.config import DB_MAX_CONNECTIONS, DB_CONNECTION_TIMEOUT

db_pool = ConnectionPool(
    max_connections=DB_MAX_CONNECTIONS,
    connection_timeout=DB_CONNECTION_TIMEOUT
)
