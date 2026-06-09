from app.core.database import SessionLocal
from app.models.product_type_cache import ProductTypeCache

db = SessionLocal()

try:
    rows = db.query(ProductTypeCache).all()

    for row in rows:
        print(
            row.code,
            row.type_produit
        )

finally:
    db.close()