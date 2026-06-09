from fastapi import FastAPI

from app.api.products import router as products_router
from app.core.database import Base, engine
from app.api import school_lists


# Importer les modèles pour enregistrer les tables
from app.models.product import Product
from app.models.sync_status import SyncStatus
from app.models.product_type_cache import ProductTypeCache
from app.models.school import School
from app.models.school_year import SchoolYear
from app.models.school_list import SchoolList
from app.models.school_list_item import SchoolListItem
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse
from app.api import products
from fastapi.middleware.cors import CORSMiddleware
from app.api import sync
from app.api import school_lists_pdf
from app.api import public_school_lists
from app.api.shopping_list_pdf import router as shopping_pdf_router

import asyncio
import sys

if sys.platform == "win32":
    asyncio.set_event_loop_policy(
        asyncio.WindowsProactorEventLoopPolicy()
    )

app = FastAPI(title="ERP MDP")

# CORS pour frontend
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

Base.metadata.create_all(bind=engine)

# Servir les fichiers statiques
app.mount("/static", StaticFiles(directory="app/static"), name="static")

# Routes API
app.include_router(products.router)
app.include_router(sync.router)
app.include_router(school_lists.router)
app.include_router(school_lists_pdf.router)
app.include_router(public_school_lists.router)
app.include_router(shopping_pdf_router)

@app.get("/")
async def root():
    return FileResponse("app/static/index.html")