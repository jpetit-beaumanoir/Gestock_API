from dataclasses import dataclass

@dataclass
class Producto:
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