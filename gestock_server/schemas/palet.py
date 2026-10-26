from pydantic import BaseModel

class PaletInfo(BaseModel):
    cajas: int
    cantidad: int

class PaletsGetResponse(BaseModel):
    palets: dict[str, PaletInfo]
    total: int


class PaletCreateRequest(BaseModel):
    almacen: str      # gestock_palets.codi_centre

class MessageResponse(BaseModel):
    message: str
