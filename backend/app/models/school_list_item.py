from sqlalchemy import Column, Integer, String, Float

from app.core.database import Base


class SchoolListItem(Base):
    
    __tablename__ = "school_list_items"

    id = Column(Integer, primary_key=True, index=True)

    list_id = Column(Integer, nullable=False)

    product_id = Column(Integer, nullable=True)

    designation_libre = Column(String, nullable=True)

    quantite = Column(Integer, nullable=False, default=1)

    prix_force = Column(Float, nullable=True)