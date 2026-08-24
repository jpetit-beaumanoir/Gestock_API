from pydantic import BaseModel

class FilteredSearchRequest(BaseModel):
    ean: str | None = None
    familia: str | None = None
    subfamilia: str | None = None
    talla: str | None = None
    color: str | None = None
    marca: str | None = None
    temporada: str | None = None
    almacen: int | None = None
    palet: int | None = None
    caja: int | None = None