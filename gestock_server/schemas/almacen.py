from pydantic import BaseModel, Field

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
    nombre: str = Field(..., min_length=1, max_length=50)     # centres.nom_centre
    codigo: str = Field(..., min_length=1, max_length=10)     # centres.codi_centre

class MessageResponse(BaseModel):
    message: str
