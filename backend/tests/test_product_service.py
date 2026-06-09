from app.services.product_service import ProductService
from app.core.database import SessionLocal
from app.models.product import Product


def main():
    service = ProductService()

    data = {
        "code": "9782075187541",
        "type_produit": 1,
        "prix_vente": 8500
    }

    print("=== TEST UPSERT ===")

    # Premier appel (INSERT)
    service.upsert_product(data)

    # Deuxième appel (UPDATE)
    service.upsert_product(data)

    db = SessionLocal()

    try:
        products = db.query(Product).filter(
            Product.code == "9782075187541"
        ).all()

        print(f"\nNombre de produits trouvés : {len(products)}")

        for product in products:
            print({
                "id": product.id,
                "code": product.code,
                "type_produit": product.type_produit,
                "titre": product.titre,
                "prix_vente": product.prix_vente,
                "synced_at": product.synced_at
            })

        if len(products) == 1:
            print("\n✅ PHASE 5 VALIDÉE")
            print("UPSERT fonctionne correctement.")
            print("Un seul produit existe en base après deux appels.")
        else:
            print("\n❌ PHASE 5 NON VALIDÉE")
            print(f"{len(products)} produits trouvés au lieu de 1.")

    finally:
        db.close()


if __name__ == "__main__":
    main()