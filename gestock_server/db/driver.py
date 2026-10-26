"""
Conexión con MariaDB (BDD ElBicho) mediante PyMySQL.

Las credenciales se leen del gestock.env (a través de config.py):

    DB_SERVER    host de MariaDB             (por defecto 127.0.0.1)
    DB_PORT      puerto                      (por defecto 3306)
    DB_SOCKET    socket de Linux (opcional)  p. ej. /run/mysqld/mysqld.sock
    DB_USER      usuario de aplicaciones     (obligatorio)
    DB_PASSWORD  contraseña                  (obligatorio)
    DB_DATABASE  nombre de la BDD            (obligatorio)
    DB_CONNECTION_TIMEOUT  segundos para conectar (por defecto 10)

Los servicios solo deben importar desde aquí:
    from gestock_server.db.driver import DBError, IntegrityError, dict_cursor
"""
import pymysql
import pymysql.cursors

from gestock_server.config import (
    DB_SERVER,
    DB_PORT,
    DB_SOCKET,
    DB_USER,
    DB_PASSWORD,
    DB_DATABASE,
    DB_CONNECTION_TIMEOUT,
)

# Excepciones del driver (todas heredan de DBError)
DBError = pymysql.err.Error
IntegrityError = pymysql.err.IntegrityError
OperationalError = pymysql.err.OperationalError


def check_config() -> None:
    """
    Comprueba que el .env tiene las credenciales obligatorias.

    Raises:
        RuntimeError: con la lista de variables que faltan.
    """
    missing = [
        name for name, value in (
            ("DB_USER", DB_USER),
            ("DB_PASSWORD", DB_PASSWORD),
            ("DB_DATABASE", DB_DATABASE),
        )
        if not value
    ]
    if missing:
        raise RuntimeError(
            f"Falten variables de connexió a la BDD al gestock.env: {', '.join(missing)}"
        )


def describe_target() -> str:
    """Destino de la conexión para los logs (sin contraseña)."""
    where = f"socket {DB_SOCKET}" if DB_SOCKET else f"{DB_SERVER}:{DB_PORT}"
    return f"{DB_USER}@{where}/{DB_DATABASE}"


def connect():
    """
    Abre una conexión nueva con MariaDB.

    - utf8mb4, igual que la BDD.
    - autocommit desactivado: los servicios confirman con commit().
    """
    kwargs = dict(
        user=DB_USER,
        password=DB_PASSWORD,
        database=DB_DATABASE,
        charset="utf8mb4",
        autocommit=False,
        connect_timeout=DB_CONNECTION_TIMEOUT,
        read_timeout=60,
        write_timeout=60,
    )

    if DB_SOCKET:
        kwargs["unix_socket"] = DB_SOCKET
    else:
        kwargs["host"] = DB_SERVER
        kwargs["port"] = DB_PORT

    return pymysql.connect(**kwargs)


def dict_cursor(conn):
    """Cursor que devuelve cada fila como diccionario {columna: valor}."""
    return conn.cursor(pymysql.cursors.DictCursor)


def explain_error(error: Exception) -> str:
    """Mensaje claro para los errores de conexión más habituales de MariaDB."""
    code = error.args[0] if getattr(error, "args", None) else None
    hints = {
        1045: "usuari o contrasenya incorrectes (o l'usuari no té permís des d'aquest host)",
        1044: "l'usuari no té permisos sobre la base de dades",
        1049: "la base de dades no existeix (revisa DB_DATABASE)",
        2003: "no es pot connectar amb el servidor (revisa DB_SERVER/DB_PORT, que MariaDB estigui en marxa i el bind-address)",
        2005: "host desconegut (revisa DB_SERVER)",
        2013: "s'ha perdut la connexió durant la connexió (timeout o xarxa)",
    }
    hint = hints.get(code)
    return f"{error} -> {hint}" if hint else str(error)
