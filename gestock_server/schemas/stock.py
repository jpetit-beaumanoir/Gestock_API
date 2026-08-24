from pydantic import BaseModel, conlist, Field

class StockGetRequest(BaseModel):
    almacen: int
    palet: int
    caja: int

class StockAddRequest(BaseModel):
    almacen: int
    palet: int
    caja: int
    eans: conlist(str)

class StockDeleteRequest(BaseModel):
    almacen: int
    palet: int
    caja: int
    ids: conlist(int)

class StockMoveRequest(BaseModel):
    almacen: int
    palet: int
    caja: int
    ids: conlist(int)

class StockInfo(BaseModel):
    id: int
    nombre: str
    color: str
    talla: str
    temporada: str
    cantidad: int

class StockGetResponse(BaseModel):
    stock: dict[str, StockInfo]
    total: int

class StockExportRequest(BaseModel):
    almacen: int
    ean: str | None = None
    talla: str | None = None
    nombre: str | None = None
    familia: str | None = None
    color: str | None = None
    temporada: str | None = None

class StockExportItem(BaseModel):
    ean: str
    palet: int
    caja: int

    desc_caja: str
    temp_caja: str

    almacen: int

    talla: str
    nombre: str

    familia: str
    subfamilia: str

    color: str
    temporada: str

    pvp: float
    prmp: float

    marca: str

class StockExportResponse(BaseModel):
    items: list[StockExportItem]


class MessageResponse(BaseModel):
    message: str