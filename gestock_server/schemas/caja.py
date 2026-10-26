from pydantic import BaseModel, Field, ConfigDict

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
    # Acepta el código de almacén como número o como texto (9999 o "9999"):
    # la app puede seguir enviando números mientras se adapta a codi_centre (texto)
    model_config = ConfigDict(coerce_numbers_to_str=True)

    almacen: str
    palet: int

class MessageResponse(BaseModel):
    message: str

class CajaGetDescTempResponse(BaseModel):
    descripcion: str | None = None
    temporada: str | None = None

class CajaUpdateDescTempRequest(BaseModel):
    # Acepta el código de almacén como número o como texto (9999 o "9999"):
    # la app puede seguir enviando números mientras se adapta a codi_centre (texto)
    model_config = ConfigDict(coerce_numbers_to_str=True)

    almacen: str
    palet: int
    caja: int
    descripcion: str | None = Field(default=None, max_length=20)
    temporada: str | None = Field(default=None, max_length=20)

class CajaUpdateCantidadRequest(BaseModel):
    # Acepta el código de almacén como número o como texto (9999 o "9999"):
    # la app puede seguir enviando números mientras se adapta a codi_centre (texto)
    model_config = ConfigDict(coerce_numbers_to_str=True)

    almacen: str
    palet: int
    caja: int
