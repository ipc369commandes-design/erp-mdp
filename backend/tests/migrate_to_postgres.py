import os
import sys
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from app.core.database import Base, DB_PATH

# Importation de tous les modèles de l'application
from app.models.product import Product
from app.models.sync_status import SyncStatus
from app.models.product_type_cache import ProductTypeCache
from app.models.school import School
from app.models.school_year import SchoolYear
from app.models.school_list import SchoolList
from app.models.school_list_item import SchoolListItem

SQLITE_URL = f"sqlite:///{DB_PATH}"

print("==================================================")
print("🔄 SCRIPT DE MIGRATION SQLITE -> POSTGRESQL")
print("==================================================")

# Demander l'URL de connexion PostgreSQL
postgres_url = input("Veuillez coller la Connection String (URL) de votre base PostgreSQL Neon : ").strip()

if not postgres_url:
    print("❌ Erreur : L'URL de connexion est obligatoire.")
    sys.exit(1)

if postgres_url.startswith("postgres://"):
    postgres_url = postgres_url.replace("postgres://", "postgresql://", 1)

print("\n📡 Connexion aux bases de données...")
sqlite_engine = create_engine(SQLITE_URL)
postgres_engine = create_engine(postgres_url)

# Créer les structures de tables vides sur Postgres
print("🔨 Création des tables sur PostgreSQL si elles n'existent pas...")
Base.metadata.create_all(bind=postgres_engine)

SqliteSession = sessionmaker(bind=sqlite_engine)
PostgresSession = sessionmaker(bind=postgres_engine)

sqlite_db = SqliteSession()
postgres_db = PostgresSession()

# Ordre d'importation logique pour respecter les clés étrangères
tables_to_migrate = [
    (School, "schools"),
    (SchoolYear, "school_years"),
    (SchoolList, "school_lists"),
    (SchoolListItem, "school_list_items"),
    (Product, "products"),
    (SyncStatus, "sync_status"),
    (ProductTypeCache, "product_type_cache")
]

try:
    for model, name in tables_to_migrate:
        print(f"\n📦 Migration de la table '{name}'...")
        
        # Vider la table Postgres d'abord pour éviter les doublons en cas de relancement
        postgres_db.query(model).delete()
        postgres_db.commit()
        
        # Lire les données depuis SQLite
        rows = sqlite_db.query(model).all()
        print(f"   -> {len(rows)} lignes trouvées dans SQLite.")
        
        if not rows:
            print("   -> Ligne vide, étape sautée.")
            continue
            
        sqlite_db.expunge_all() # Détacher les objets de la session SQLite
        
        # Insertion optimisée par lots de 5 000 objets pour préserver la RAM
        batch_size = 5000
        for i in range(0, len(rows), batch_size):
            batch = rows[i:i+batch_size]
            new_objects = []
            
            for row in batch:
                # Extraire les données de la ligne SQLite pour l'injecter dans un nouvel objet Postgres
                attrs = {col.name: getattr(row, col.name) for col in model.__table__.columns}
                new_objects.append(model(**attrs))
                
            postgres_db.bulk_save_objects(new_objects)
            postgres_db.commit()
            print(f"   -> Écrit {min(i + batch_size, len(rows))}/{len(rows)} lignes...")
            
        print(f"   -> ✅ Table '{name}' migrée avec succès.")
        
    print("\n🎉 MIGRATION FINALE TERMINÉE AVEC SUCCÈS !")
    print("   Toutes vos données (produits, écoles, listes) sont désormais dans votre cloud PostgreSQL.")

except Exception as e:
    postgres_db.rollback()
    print(f"\n❌ Erreur critique pendant la migration : {e}")
finally:
    sqlite_db.close()
    postgres_db.close()