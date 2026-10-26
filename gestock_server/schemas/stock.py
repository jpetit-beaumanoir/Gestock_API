from pydantic import BaseModel, conlist

# almacen = codi_centre (texto)


class StockAddRequest(BaseModel):
    almacen: str
    palet: int
    caja: int
    eans: conlist(str)

class StockDeleteRequest(BaseModel):
    almacen: str
    palet: int
    caja: int
    ids: conlist(int)

class StockMoveRequest(BaseModel):
    almacen: str      # destino
    palet: int        # destino
    caja: int         # destino
    ids: conlist(int)

class StockInfo(BaseModel):
    ids: list[int]
    nombre: str
    color: str
    talla: str
    temporada: str
    cantidad: int

class StockGetResponse(BaseModel):
    stock: dict[str, StockInfo]
    total: int

class StockExportItem(BaseModel):
    ean: str
    palet: int
    caja: int

    desc_caja: str
    temp_caja: str

    almacen: str

    talla: str
    nombre: str

    familia: str
    subfamilia: str

    color: str
    temporada: str

    pvp: float
    prmp: float       # ya no existe en productes: siempre 0.0 (se mantiene por compatibilidad con la app)

    marca: str

class StockExportResponse(BaseModel):
    items: list[StockExportItem]


class MessageResponse(BaseModel):
    message: str
