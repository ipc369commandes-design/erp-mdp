import asyncio

from app.services.sync_service import SyncService
from app.core.database import init_db


async def main():
    # 🔧 Initialiser les tables avant de lancer le sync
    init_db()
    
    sync = SyncService(
        excel_path="data/catalogue.xlsx"
    )

    # 🚀 Configuration CONSERVATIVE - Sans surcharger
    # - 5 articles par batch (petit)
    # - 2s entre les batches (respecte le serveur)
    # - 2 requêtes simultanées (Semaphore réduit)
    # - Temps estimé: ~35 heures
    await sync.run(batch_size=5, delay_between_batches=2.0)


if __name__ == "__main__":
    asyncio.run(main())