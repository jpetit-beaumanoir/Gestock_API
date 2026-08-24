from fastapi import FastAPI

import os

from gestock_server.routes.auth import router as auth_router
from gestock_server.routes.almacenes import router as almacenes_router
from gestock_server.routes.palets import router as palets_router
from gestock_server.routes.cajas import router as cajas_router
from gestock_server.routes.stock import router as stock_router
from gestock_server.routes.familias import router as familias_router
from gestock_server.routes.temporadas import router as temporadas_router

from gestock_server.middleware.apikey import APIKeyMiddleware
from gestock_server.middleware.connection_logger import (
    ConnectionResetLoggerMiddleware,
)

from gestock_server.middleware.ratelimit import limiter
from slowapi.middleware import SlowAPIMiddleware


app = FastAPI(
    title="Gestock API",
    version="1.0.0"
)


app.state.limiter = limiter

# Middleware
app.add_middleware(ConnectionResetLoggerMiddleware)
app.add_middleware(APIKeyMiddleware)
app.add_middleware(SlowAPIMiddleware)

# Routers
app.include_router(auth_router)
app.include_router(almacenes_router)
app.include_router(palets_router)
app.include_router(cajas_router)
app.include_router(stock_router)
app.include_router(familias_router)
app.include_router(temporadas_router)

os.system("cls")
print("APP GESTOCK CARGADA")

# En el cmd a la carpeta pare de gestock_server
#uvicorn gestock_server.app:app --reload