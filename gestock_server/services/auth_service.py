from gestock_server.schemas.auth import AuthUserResponse
from gestock_server.services.usuaris_service import validar_api_key


def validar_user(key: str) -> AuthUserResponse:
    """
    Comprueba la clave personal que introduce el usuario en la app (contra la tabla usuaris)
    y devuelve su nombre.

    Raises:
        ValueError: la clave no existe en usuaris o el usuario está desactivado (401).
        ConnectionError: no se puede consultar la BDD (503).
    """
    usuario = validar_api_key(key)

    if usuario is None:
        raise ValueError("CLAU INCORRECTA")

    return AuthUserResponse(user=usuario.nom)
