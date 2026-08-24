from fastapi import Request, HTTPException

from gestock_server.config import ROLES


def require_role(required_role: str):

    def checker(request: Request):

        user_role = request.state.rol

        if ROLES[user_role] < ROLES[required_role]:
            raise HTTPException(
                403,
                detail="NO TIENES PERMISOS SUFICIENTES"
            )
        return True

    return checker