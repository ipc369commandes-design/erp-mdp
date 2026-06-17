import os
from typing import Optional
from app.core.database import SessionLocal
from app.models.product_type_cache import ProductTypeCache


class TypeDetector:

    TYPES = [1, 5, 6]

    def __init__(self, client):
        self.client = client

    async def detect(self, code: str) -> Optional[int]:
        db = SessionLocal()

        try:
            # ==========================
            # CACHE
            # ==========================
            cached = db.get(ProductTypeCache, code)

            if cached:
                print(
                    f"✅ CACHE HIT : "
                    f"{code} -> {cached.type_produit}"
                )

                # ✅ FIX : Sécurisation si le type en base est vide ou marqué NOT_FOUND
                if not cached.type_produit or cached.type_produit == "NOT_FOUND":
                    return None

                try:
                    return int(cached.type_produit)
                except ValueError:
                    return None

            print(
                f"🔍 DETECTION MDP : "
                f"{code}"
            )

            # ==========================
            # DETECTION
            # ==========================
            for type_produit in self.TYPES:
                try:
                    print(
                        f"   Test type "
                        f"{type_produit}"
                    )

                    response = await self.client.get_article(
                        code=code,
                        type_produit=type_produit
                    )

                    # ✅ FIX : Vérification que la réponse n'est pas vide et est bien un dictionnaire valide
                    if not response or not isinstance(response, dict):
                        continue

                    article = response.get("article")

                    if article and article.get("titre"):
                        db.merge(
                            ProductTypeCache(
                                code=code,
                                type_produit=str(type_produit)
                            )
                        )
                        db.commit()

                        print(
                            f"💾 CACHE SAVE : "
                            f"{code} -> {type_produit}"
                        )

                        return type_produit

                except Exception as e:
                    print(
                        f"⚠️ Type "
                        f"{type_produit} : "
                        f"{e}"
                    )
                    continue

            # ==========================
            # NOT FOUND
            # ==========================
            db.merge(
                ProductTypeCache(
                    code=code,
                    type_produit="NOT_FOUND"
                )
            )
            db.commit()

            print(
                f"💾 CACHE SAVE : "
                f"{code} -> NOT_FOUND"
            )

            return None

        finally:
            db.close()