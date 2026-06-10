import asyncio

from app.services.sync_service import SyncService
from app.core.database import init_db


async def main():
    # 🔧 Initialiser les tables avant de lancer le sync
    init_db()
    
    sync = SyncService(
        excel_path="data/catalogue.xlsx"
    )

    # 🚀 CONFIGURATION CALIBRÉE & SÉCURISÉE
    # - 15 articles par batch
    # - 1.0s de repos entre chaque batch
    # - 3 requêtes simultanées maximum (Sémaphore)
    # - Temps estimé pour 26 000 produits : ~3,5 à 4,5 heures (au lieu de 35 heures !)
    await sync.run(batch_size=15, delay_between_batches=1.0, concurrency=3)


if __name__ == "__main__":
    asyncio.run(main())