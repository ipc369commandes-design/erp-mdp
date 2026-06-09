from datetime import datetime

from app.core.database import SessionLocal
from app.models.product import Product


class ProductService:

    def upsert_product(self, data: dict):
        db = SessionLocal()

        try:
            product = db.query(Product).filter(
                Product.code == data["code"]
            ).first()

            # ======================
            # UPDATE
            # ======================
            if product:

                for key, value in data.items():
                    if hasattr(product, key):
                        setattr(product, key, value)

                product.synced_at = datetime.utcnow()

            # ======================
            # INSERT
            # ======================
            else:

                product = Product(
                    code=data["code"],
                    type_produit=data["type_produit"],

                    titre=data.get("titre"),

                    auteur=data.get("auteur"),
                    editeur=data.get("editeur"),
                    collection=data.get("collection"),

                    description=data.get("description"),

                    image_url=data.get("image_url"),

                    pages=data.get("pages"),

                    poids=data.get("poids"),

                    longueur=data.get("longueur"),
                    largeur=data.get("largeur"),
                    epaisseur=data.get("epaisseur"),

                    disponibilite=data.get("disponibilite"),

                    prix_catalogue=data.get("prix_catalogue"),

                    prix_vente=data.get("prix_vente"),

                    synced_at=datetime.utcnow()
                )

                db.add(product)

            db.commit()

        except Exception as e:
            db.rollback()
            raise e

        finally:
            db.close()