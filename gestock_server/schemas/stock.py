from pydantic import BaseModel, conlist, ConfigDict

# almacen = codi_centre (texto)


class StockAddRequest(BaseModel):
    # Acepta el código de almacén como número o como texto (9999 o "9999"):
    # la app puede seguir enviando números mientras se adapta a codi_centre (texto)
    model_config = ConfigDict(coerce_numbers_to_str=True)

    almacen: str
    palet: int
    caja: int
    eans: conlist(str)

class StockDeleteRequest(BaseModel):
    # Acepta el código de almacén como número o como texto (9999 o "9999"):
    # la app puede seguir enviando números mientras se adapta a codi_centre (texto)
    model_config = ConfigDict(coerce_numbers_to_str=True)

    almacen: str
    palet: int
    caja: int
    ids: conlist(int)

class StockMoveRequest(BaseModel):
    # Acepta el código de almacén como número o como texto (9999 o "9999"):
    # la app puede seguir enviando números mientras se adapta a codi_centre (texto)
    model_config = ConfigDict(coerce_numbers_to_str=True)

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
