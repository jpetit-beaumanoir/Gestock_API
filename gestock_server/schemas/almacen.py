from pydantic import BaseModel

class AlmacenInfo(BaseModel):
    nombre: str
    palets: int
    cajas: int
    productos: int

class AlmacenResponse(BaseModel):
    almacenes: dict[str, AlmacenInfo]

class AlmacenLoginResponse(BaseModel):
    nombre: str


class AlmacenCreateRequest(BaseModel):
    nombre: str
    codigo: int


class AlmacenDeleteRequest(BaseModel):
    codigo: int

class MessageResponse(BaseModel):
    message: str