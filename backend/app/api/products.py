
from pydantic import BaseModel
from typing import Optional, List, Any
from datetime import datetime
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib.units import cm
from reportlab.platypus import SimpleDocTemplate, Table, TableStyle, Paragraph, Spacer, Image as RLImage
from reportlab.lib import colors
from reportlab.lib.enums import TA_CENTER, TA_LEFT, TA_RIGHT
import io as io_module
import base64
import urllib.request
from fastapi.responses import StreamingResponse

from app.core.database import SessionLocal
from app.models.product import Product
from app.schemas.product import ProductResponse, ProductListResponse

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.models.school_list import SchoolList
from app.models.school_list_item import SchoolListItem

from app.models.school import School
from app.models.school_year import SchoolYear



class GeneratePDFRequest(BaseModel):
    list_id: int

router = APIRouter()

# ============= SCHEMAS =============
class ProductUpdate(BaseModel):
    code: Optional[str] = None
    titre: Optional[str] = None
    auteurs: Optional[str] = None
    editeur: Optional[str] = None
    collection: Optional[str] = None
    description: Optional[str] = None
    image_url: Optional[str] = None
    pages: Optional[int] = None
    poids: Optional[float] = None
    longueur: Optional[float] = None
    largeur: Optional[float] = None
    epaisseur: Optional[float] = None
    disponibilite: Optional[int] = None
    prix_catalogue: Optional[float] = None
    prix_vente: Optional[float] = None
    
    class Config:
        from_attributes = True

class ShoppingListItem(BaseModel):
    id: int
    code: str
    titre: str
    prix_vente: float
    qty: int
    image_url: Optional[str] = None

class ShoppingListRequest(BaseModel):
    items: List[ShoppingListItem]

# ============= ROUTES PRODUITS =============
@router.get("/products", response_model=ProductListResponse)
def get_products():
    """Récupérer tous les produits"""
    db = SessionLocal()
    try:
        products = db.query(Product).all()
        return {
            "items": products,
            "total": len(products)
        }
    finally:
        db.close()

@router.get("/products/{code}", response_model=ProductResponse)
def get_product(code: str):
    """Récupérer un produit par son code"""
    db = SessionLocal()
    try:
        product = db.query(Product).filter(
            Product.code == code
        ).first()

        if not product:
            raise HTTPException(
                status_code=404,
                detail="Produit introuvable"
            )

        return product
    finally:
        db.close()

@router.put("/products/{product_id}")
@router.post("/products/{product_id}")
def update_product(product_id: int, product_data: ProductUpdate):
    """Mettre à jour un produit par son ID"""
    db = SessionLocal()
    try:
        product = db.query(Product).filter(
            Product.id == product_id
        ).first()

        if not product:
            raise HTTPException(
                status_code=404,
                detail=f"Produit avec l'ID {product_id} introuvable"
            )

        for key, value in product_data.dict(exclude_unset=True).items():
            if value is not None and hasattr(product, key):
                setattr(product, key, value)

        db.commit()
        db.refresh(product)
        
        return {
            "success": True,
            "message": "Produit mis à jour avec succès",
            "product": product
        }

    except Exception as e:
        db.rollback()
        raise HTTPException(
            status_code=500,
            detail=f"Erreur lors de la mise à jour: {str(e)}"
        )
    finally:
        db.close()

