from pydantic import BaseModel

class AuthUserResponse(BaseModel):
    user: str