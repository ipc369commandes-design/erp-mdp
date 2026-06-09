from pydantic import BaseModel
from datetime import datetime
from typing import Optional


class ProductBase(BaseModel):
    """Schéma de base pour un produit"""
    code: str
    type_produit: int
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


class ProductCreate(ProductBase):
    """Schéma pour créer un produit"""
    pass


class ProductUpdate(ProductBase):
    """Schéma pour mettre à jour un produit"""
    pass


class ProductResponse(ProductBase):
    """Schéma pour la réponse API"""
    id: int
    synced_at: datetime

    class Config:
        from_attributes = True  # Pour convertir les modèles SQLAlchemy en dict


class ProductListResponse(BaseModel):
    """Schéma pour la liste des produits"""
    items: list[ProductResponse]
    total: int