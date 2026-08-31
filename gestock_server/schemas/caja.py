from pydantic import BaseModel

class CajaExistsDB(BaseModel):
    caja: int
    palet: int
    almacen: int
    temporada: str
    descripcion: str
    cantidad: int

class CajaInfo(BaseModel):
    cantidad: int
    descripcion: str
    temporada: str

class CajasGetResponse(BaseModel):
    cajas: dict[str, CajaInfo]


class CajaCreateRequest(BaseModel):
    almacen: int
    palet: int

class MessageResponse(BaseModel):
    message: str

class CajaGetDescTempResponse(BaseModel):
    descripcion: str
    temporada: str

class CajaUpdateDescTempRequest(BaseModel):
    almacen: int
    palet: int
    caja: int
    descripcion: str|None
    temporada: str|None

class CajaUpdateCantidadRequest(BaseModel):
    almacen: int
    palet: int
    caja: int