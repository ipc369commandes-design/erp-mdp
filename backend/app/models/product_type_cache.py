# app/models/product_type_cache.py

from sqlalchemy import Column, Integer, String

from app.core.database import Base


class ProductTypeCache(Base):

    __tablename__ = "product_type_cache"

    code = Column(String, primary_key=True, index=True)

    type_produit = Column(String, nullable=True)