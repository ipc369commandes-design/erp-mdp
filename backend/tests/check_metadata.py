from app.core.database import Base

print("Avant import:", Base.metadata.tables.keys())

from app.models.product import Product

print("Après Product:", Base.metadata.tables.keys())

from app.models.sync_status import SyncStatus

print("Après SyncStatus:", Base.metadata.tables.keys())

from app.models.product_type_cache import ProductTypeCache

print("Après Cache:", Base.metadata.tables.keys())