from dataclasses import dataclass

@dataclass
class Stock:
    id: int
    ean: str
    palet: int
    caja: int
    almacen: int
