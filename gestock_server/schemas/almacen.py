from pydantic import BaseModel, Field, ConfigDict

# El código de almacén es centres.codi_centre (VARCHAR(10)), por eso es texto


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
    # Acepta el código de almacén como número o como texto (9999 o "9999"):
    # la app puede seguir enviando números mientras se adapta a codi_centre (texto)
    model_config = ConfigDict(coerce_numbers_to_str=True)

    nombre: str = Field(..., min_length=1, max_length=50)     # centres.nom_centre
    codigo: str = Field(..., min_length=1, max_length=10)     # centres.codi_centre

class MessageResponse(BaseModel):
    message: str
