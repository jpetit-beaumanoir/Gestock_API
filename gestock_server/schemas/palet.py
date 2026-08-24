from pydantic import BaseModel

class PaletInfo(BaseModel):
    cajas: int
    cantidad: int


class PaletsGetRequest(BaseModel):
    almacen: int

class PaletsGetResponse(BaseModel):
    palets: dict[str, PaletInfo]
    total: int


class PaletCreateRequest(BaseModel):
    almacen: int

class PaletDeleteRequest(BaseModel):
    almacen: int
    palet: int

class MessageResponse(BaseModel):
    message: str