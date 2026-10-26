from pydantic import BaseModel, ConfigDict

class PaletInfo(BaseModel):
    cajas: int
    cantidad: int

class PaletsGetResponse(BaseModel):
    palets: dict[str, PaletInfo]
    total: int


class PaletCreateRequest(BaseModel):
    # Acepta el código de almacén como número o como texto (9999 o "9999"):
    # la app puede seguir enviando números mientras se adapta a codi_centre (texto)
    model_config = ConfigDict(coerce_numbers_to_str=True)

    almacen: str      # gestock_palets.codi_centre

class MessageResponse(BaseModel):
    message: str
