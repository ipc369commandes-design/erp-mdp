from sqlalchemy import Column
from sqlalchemy import Integer
from sqlalchemy import String
from sqlalchemy import Float
from sqlalchemy import DateTime
from sqlalchemy import Text

from datetime import datetime

from app.core.database import Base


class Product(Base):
    __tablename__ = "products"

    id = Column(Integer, primary_key=True, index=True)

    code = Column(
        String,
        unique=True,
        nullable=False,
        index=True
    )

    type_produit = Column(Integer, nullable=False)

    titre = Column(String)

    auteurs = Column(String)

    editeur = Column(String)

    collection = Column(String)

    description = Column(Text)

    image_url = Column(String)

    pages = Column(Integer)

    poids = Column(Float)

    longueur = Column(Float)

    largeur = Column(Float)

    epaisseur = Column(Float)

    disponibilite = Column(Integer)

    prix_catalogue = Column(Float)

    prix_vente = Column(Float)

    synced_at = Column(
        DateTime,
        default=datetime.utcnow
    )