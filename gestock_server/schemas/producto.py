from pydantic import BaseModel

class ProductoResponse(BaseModel):
    ean: str
    nombre: str
    familia: str
    subfamilia: str
    color: str
    talla: str
    pvp: float
    prmp: float
    temporada: str
    marca: str