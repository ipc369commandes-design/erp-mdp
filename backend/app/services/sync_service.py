import asyncio
from datetime import datetime
from typing import Optional, Callable

from app.services.excel_reader import ExcelReader
from app.services.mdp_client import MDPClient
from app.core.database import SessionLocal
from app.models.product import Product
from app.models.sync_status import SyncStatus
from app.services.type_detector import TypeDetector

class SyncService:
    def __init__(
        self, 
        excel_path: str, 
        use_proxy: bool = False,
        log_callback: Optional[Callable[[str], None]] = None,
        stop_checker: Optional[Callable[[], bool]] = None,
        product_tracker: Optional[Callable[[str], None]] = None
    ):
        self.excel_path = excel_path
        self.reader = ExcelReader(excel_path)
        self.client = MDPClient(use_proxy=False)
        self.use_proxy = use_proxy
        
        # Callbacks pour interagir proprement avec l'API sans polluer le contexte global
        self.log_callback = log_callback or (lambda msg: print(msg))
        self.stop_checker = stop_checker or (lambda: False)
        self.product_tracker = product_tracker or (lambda title: None)

        self.semaphore = asyncio.Semaphore(1)
        self.type_detector = TypeDetector(self.client)
        self.type_cache = {}

    def log(self, message: str):
        self.log_callback(message)

    def upsert_with_status(self, db, data: dict, status: str, error_msg: Optional[str] = None):
        """Met à jour ou insère un produit et son statut de synchronisation"""
        product = db.query(Product).filter(Product.code == data["code"]).first()

        if product:
            for key, value in data.items():
                if hasattr(product, key):
                    setattr(product, key, value)
        else:
            valid_fields = {
                "code": data["code"],
                "type_produit": data.get("type_produit"),
                "titre": data.get("titre"),
                "auteurs": data.get("auteurs"),
                "editeur": data.get("editeur"),
                "collection": data.get("collection"),
                "description": data.get("description"),
                "image_url": data.get("image_url"),
                "pages": data.get("pages"),
                "poids": data.get("poids"),
                "longueur": data.get("longueur"),
                "largeur": data.get("largeur"),
                "epaisseur": data.get("epaisseur"),
                "disponibilite": data.get("disponibilite"),
                "prix_catalogue": data.get("prix_catalogue"),
                "prix_vente": data.get("prix_vente"),
                "synced_at": datetime.utcnow()
            }
            product = Product(**valid_fields)
            db.add(product)

        sync_status = db.query(SyncStatus).filter(SyncStatus.code == data["code"]).first()
        if sync_status:
            sync_status.status = status
            sync_status.last_sync = datetime.utcnow()
            sync_status.error_message = error_msg
        else:
            sync_status = SyncStatus(
                code=data["code"],
                status=status,
                last_sync=datetime.utcnow(),
                error_message=error_msg
            )
            db.add(sync_status)

        db.commit()

    async def get_type(self, code):
        if code in self.type_cache:
            return self.type_cache[code]
        type_ = await self.type_detector.detect(code)
        self.type_cache[code] = type_
        return type_

    async def sync_one(self, item: dict, retry_count: int = 0):
        """Synchroniser un produit unique (Gestion optimisée de la session de base de données)"""
        code = item["code"]
        prix_vente = item["prix_vente"]
        max_retries = 3

        async with self.semaphore:
            # Ouverture d'une SEULE et unique session de base de données par produit
            db = SessionLocal()
            try:
                # 1. Détection du type
                type_produit = await self.get_type(code)
                if type_produit is None:
                    self.upsert_with_status(
                        db,
                        {"code": code, "type_produit": None, "titre": None, "prix_vente": prix_vente},
                        "failed",
                        "Type produit introuvable"
                    )
                    self.log(f"❌ {code}: type_produit introuvable")
                    return

                # 2. Appel à la plateforme
                response = await self.client.get_article(code=code, type_produit=type_produit)
                if response is None:
                    self.upsert_with_status(
                        db,
                        {"code": code, "type_produit": type_produit, "titre": None, "prix_vente": prix_vente},
                        "failed",
                        "Réponse vide"
                    )
                    self.log(f"❌ {code}: Réponse vide de la plateforme")
                    return

                article = response.get("article", {})
                self.product_tracker(article.get("titre", code))

                auteurs = "; ".join(article["auteurs"]) if article.get("auteurs") else None

                data = {
                    "code": code,
                    "type_produit": type_produit,
                    "titre": article.get("titre"),
                    "auteurs": auteurs,
                    "editeur": article.get("editeur"),
                    "collection": article.get("collection"),
                    "description": article.get("presentation"),
                    "image_url": article.get("imageUrl"),
                    "pages": article.get("pages"),
                    "poids": article.get("poids"),
                    "longueur": article.get("longueur"),
                    "largeur": article.get("largeur"),
                    "epaisseur": article.get("epaisseur"),
                    "disponibilite": article.get("disponibilite"),
                    "prix_catalogue": article.get("prix"),
                    "prix_vente": prix_vente,
                    "synced_at": datetime.utcnow()
                }

                self.upsert_with_status(db, data, "success")
                self.log(f"✔ {code} : {article.get('titre', '')[:30]}")

            except Exception as e:
                error_str = str(e)
                error_msg = f"{type(e).__name__}: {error_str[:150]}"

                is_network_error = any([
                    "ETIMEDOUT" in error_str, "ECONNREFUSED" in error_str,
                    "ECONNRESET" in error_str, "ENOTFOUND" in error_str,
                    "socket" in error_str.lower(), "timeout" in error_str.lower(),
                    "disconnected" in error_str.lower(), "network" in error_str.lower()
                ])

                if is_network_error and retry_count < max_retries:
                    wait_time = 2 ** (retry_count + 1)
                    self.log(f"🔄 Retry {retry_count + 1}/{max_retries} pour {code} dans {wait_time}s...")
                    await asyncio.sleep(wait_time)
                    db.close() # Important : Fermer la session avant la récursion
                    return await self.sync_one(item, retry_count + 1)

                self.upsert_with_status(
                    db,
                    {"code": code, "prix_vente": prix_vente},
                    "failed",
                    error_msg
                )
                self.log(f"❌ {code}: {error_msg}")
            finally:
                db.close()

    def get_pending_products(self):
        """Récupérer les produits restants depuis le fichier Excel"""
        db = SessionLocal()
        try:
            all_products = self.reader.load()
            synced_codes = db.query(SyncStatus.code).filter(SyncStatus.status == "success").all()
            synced_codes = [c[0] for c in synced_codes]
            return [p for p in all_products if p["code"] not in synced_codes]
        finally:
            db.close()

    async def run(self, batch_size: int = 10, delay_between_batches: float = 1.5):
        """Lancer la synchronisation par batches, avec support de l'arrêt en cours de route"""
        self.semaphore = asyncio.Semaphore(1)
        products = self.get_pending_products()
        
        if not products:
            products = self.reader.load()

        self.log(f"📦 {len(products)} articles à traiter.")
        total_batches = (len(products) + batch_size - 1) // batch_size
        synced_count = 0

        for i in range(0, len(products), batch_size):
            # ✅ CHECK STOP : Permet l'arrêt immédiat entre deux batches
            if self.stop_checker():
                self.log("⛔ Synchronisation interrompue à la demande de l'utilisateur.")
                break

            batch = products[i:i+batch_size]
            batch_num = i // batch_size + 1
            
            self.log(f"📍 Batch {batch_num}/{total_batches} ({len(batch)} articles)")

            tasks = [self.sync_one(item) for item in batch]
            await asyncio.gather(*tasks, return_exceptions=True)
            
            synced_count += len(batch)
            await asyncio.sleep(delay_between_batches)
            
        self.log("🏁 Fin du processus de synchronisation")