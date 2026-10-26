from pydantic import BaseModel, Field

# almacen = gestock_caixes.codi_centre (texto). descripcio y temporada: VARCHAR(20)


class CajaExistsDB(BaseModel):
    caja: int
    palet: int
    almacen: str
    temporada: str | None = None
    descripcion: str | None = None
    cantidad: int

class CajaInfo(BaseModel):
    cantidad: int
    descripcion: str
    temporada: str

class CajasGetResponse(BaseModel):
    cajas: dict[str, CajaInfo]


class CajaCreateRequest(BaseModel):
    almacen: str
    palet: int

class MessageResponse(BaseModel):
    message: str

class CajaGetDescTempResponse(BaseModel):
    descripcion: str | None = None
    temporada: str | None = None

class CajaUpdateDescTempRequest(BaseModel):
    almacen: str
    palet: int
    caja: int
    descripcion: str | None = Field(default=None, max_length=20)
    temporada: str | None = Field(default=None, max_length=20)

class CajaUpdateCantidadRequest(BaseModel):
    almacen: str
    palet: int
    caja: int
