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
        
        # Callbacks d'interaction pour le serveur web et la console
        self.log_callback = log_callback or (lambda msg: print(msg))
        self.stop_checker = stop_checker or (lambda: False)
        self.product_tracker = product_tracker or (lambda title: None)

        self.semaphore = asyncio.Semaphore(1)
        self.type_detector = TypeDetector(self.client)
        self.type_cache = {}

    def log(self, message: str):
        self.log_callback(message)

    # ==========================================
    # UPSERT PRODUCT + SYNC_STATUS
    # ==========================================
    def upsert_with_status(self, db, data: dict, status: str, error_msg: Optional[str] = None):
        """Mettre à jour ou insérer un produit et son statut de synchronisation"""
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

    # ==========================================
    # SYNC ONE ITEM (avec retry intelligent)
    # ==========================================
    async def sync_one(self, item: dict, retry_count: int = 0):
        code = item["code"]
        prix_vente = item["prix_vente"]
        max_retries = 3

        async with self.semaphore:
            # ✅ FIX : Nous n'ouvrons plus la session DB ici pour éviter de bloquer la base de données 
            # pendant les longs appels réseau asynchrones de Playwright
            try:
                # 1. DETECTION TYPE PRODUIT (Appel réseau)
                type_produit = await self.get_type(code)
                if type_produit is None:
                    db = SessionLocal() # Ouverture au dernier moment pour l'écriture
                    try:
                        self.upsert_with_status(
                            db,
                            {"code": code, "type_produit": None, "titre": None, "prix_vente": prix_vente},
                            "failed",
                            "Type produit introuvable"
                        )
                    finally:
                        db.close()
                    self.log(f"❌ {code}: type_produit introuvable")
                    return

                # 2. APPEL API MDP (Appel réseau)
                response = await self.client.get_article(code=code, type_produit=type_produit)
                if response is None:
                    db = SessionLocal() # Ouverture au dernier moment pour l'écriture
                    try:
                        self.upsert_with_status(
                            db,
                            {"code": code, "type_produit": type_produit, "titre": None, "prix_vente": prix_vente},
                            "failed",
                            "Réponse vide"
                        )
                    finally:
                        db.close()
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

                # ✅ Étape d'écriture en base (Dure seulement quelques millisecondes)
                db = SessionLocal()
                try:
                    self.upsert_with_status(db, data, "success")
                    self.log(f"✔ {code} : {article.get('titre', '')[:30]}")
                finally:
                    db.close()

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
                    return await self.sync_one(item, retry_count + 1)

                db = SessionLocal()
                try:
                    self.upsert_with_status(
                        db,
                        {"code": code, "prix_vente": prix_vente},
                        "failed",
                        error_msg
                    )
                finally:
                    db.close()
                self.log(f"❌ {code}: {error_msg}")
                
    # ==========================================
    # SPINNER CONSOLE DYNAMIQUE
    # ==========================================
    async def spinner(self, stop_event):
        chars = ["|", "/", "-", "\\"]
        idx = 0

        while not stop_event.is_set():
            print(
                f"\r🔄 Synchronisation en cours {chars[idx % len(chars)]}",
                end="",
                flush=True
            )
            idx += 1
            await asyncio.sleep(0.2)

        print("\r✅ Synchronisation terminée          ")

    # ==========================================
    # GET PENDING PRODUCTS
    # ==========================================
    def get_pending_products(self):
        """Récupérer les produits qui n'ont pas encore été syncés"""
        db = SessionLocal()
        try:
            all_products = self.reader.load()
            synced_codes = db.query(SyncStatus.code).filter(
                SyncStatus.status == "success"
            ).all()
            synced_codes = [c[0] for c in synced_codes]
            return [p for p in all_products if p["code"] not in synced_codes]
        finally:
            db.close()

    # ==========================================
    # RUN FULL SYNC (Optimisé avec Concurrence)
    # ==========================================
    async def run(self, batch_size: int = 15, delay_between_batches: float = 1.0, concurrency: int = 3):
        """Lancer la synchronisation par lots de façon optimisée"""
        # Configuration dynamique du Sémaphore
        self.semaphore = asyncio.Semaphore(concurrency)
        
        stop_event = asyncio.Event()
        spinner_task = asyncio.create_task(self.spinner(stop_event))

        # Récupérer les produits restants
        products = self.get_pending_products()
        if not products:
            products = self.reader.load()

        self.log(f"📦 {len(products)} articles à traiter.")
        self.log(f"⚙️ Configuration de vitesse sûre :")
        self.log(f"   • Concurrence max : {concurrency} requêtes simultanées")
        self.log(f"   • Taille des batches : {batch_size} articles")
        self.log(f"   • Délai entre batches : {delay_between_batches}s")

        total_batches = (len(products) + batch_size - 1) // batch_size
        synced_count = 0

        for i in range(0, len(products), batch_size):
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
            
        stop_event.set()
        await spinner_task
        self.log("✅ SYNC TERMINÉ")

    # ==========================================
    # GET SYNC STATS
    # ==========================================
    def get_sync_stats(self):
        """Afficher les statistiques de synchronisation"""
        db = SessionLocal()
        try:
            total = db.query(SyncStatus).count()
            success = db.query(SyncStatus).filter(SyncStatus.status == "success").count()
            failed = db.query(SyncStatus).filter(SyncStatus.status == "failed").count()
            pending = db.query(SyncStatus).filter(SyncStatus.status == "pending").count()
            
            print(f"\n📊 Stats de synchronisation:")
            print(f"   Total: {total}")
            print(f"   ✅ Success: {success} ({(success/total*100):.1f}%)" if total > 0 else "   ✅ Success: 0")
            print(f"   ❌ Failed: {failed} ({(failed/total*100):.1f}%)" if total > 0 else "   ❌ Failed: 0")
            print(f"   ⏳ Pending: {pending} ({(pending/total*100):.1f}%)" if total > 0 else "   ⏳ Pending: 0")
        finally:
            db.close()