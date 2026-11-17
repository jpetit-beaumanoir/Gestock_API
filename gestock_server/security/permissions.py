from fastapi import Request, HTTPException

from gestock_server.config import ROLES


def require_role(required_role: str):
    """
    Dependencia de FastAPI: deja pasar solo a usuarios con un rol igual o superior al indicado.
    El rol lo pone el middleware de API key a partir de usuaris.rol.
    """

    def checker(request: Request):

        user_role = getattr(request.state, "rol", None)

        # Rol desconocido o ausente = sin permisos
        if ROLES.get(user_role, 0) < ROLES[required_role]:
            raise HTTPException(
                403,
                detail="NO TIENES PERMISOS SUFICIENTES"
            )
        return True

    return checker
