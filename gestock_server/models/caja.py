from dataclasses import dataclass

@dataclass
class Caja:
    caja: int
    palet: int
    almacen: int
    temporada: str
    descripcion: str
    cantidad: int