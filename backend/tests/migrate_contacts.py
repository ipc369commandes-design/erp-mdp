import sqlite3
import os

# Définition des chemins vers vos deux bases de données
CONTACTS_DB_PATH = "contacts.db"
ERP_DB_PATH = "data/erp.db"

print("🔍 Recherche des bases de données...")
print(f"   ➡️ Ancienne base (contacts.db) : {os.path.abspath(CONTACTS_DB_PATH)}")
print(f"   ➡️ Nouvelle base (erp.db) : {os.path.abspath(ERP_DB_PATH)}")

# Vérifications de sécurité
if not os.path.exists(CONTACTS_DB_PATH):
    print("❌ Erreur : Le fichier 'contacts.db' est introuvable. "
          "Veuillez le copier dans le dossier 'backend' avant de continuer.")
    exit(1)

if not os.path.exists(ERP_DB_PATH):
    print("❌ Erreur : La base de données 'erp.db' est introuvable. "
          "Veuillez démarrer votre serveur FastAPI (uvicorn main:app) au moins une fois pour la générer.")
    exit(1)

def format_gabon_number(number: str) -> str:
    """Conserve la logique stricte de nettoyage gabonais de votre script Tkinter"""
    num_clean = "".join(filter(str.isdigit, number))
    if number.startswith("+241"):
        return number.replace("+", "")
    elif number.startswith("0"):
        return "241" + num_clean[1:]
    elif not num_clean.startswith("241"):
        return "241" + num_clean
    return num_clean

try:
    # Établissement des connexions
    conn_old = sqlite3.connect(CONTACTS_DB_PATH)
    cursor_old = conn_old.cursor()

    conn_new = sqlite3.connect(ERP_DB_PATH)
    cursor_new = conn_new.cursor()

    # 1. S'assurer que la table contacts existe dans la nouvelle base de données
    cursor_new.execute("""
        CREATE TABLE IF NOT EXISTS contacts (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            Nom TEXT NOT NULL,
            Contacts TEXT NOT NULL UNIQUE
        )
    """)
    conn_new.commit()

    # 2. Récupérer les contacts de l'ancienne base
    cursor_old.execute("SELECT Nom, Contacts FROM contacts")
    old_contacts = cursor_old.fetchall()

    print(f"📝 {len(old_contacts)} contact(s) identifié(s) dans contacts.db.")

    inserted_count = 0
    ignored_count = 0

    # 3. Traiter et migrer chaque contact
    for nom, numero in old_contacts:
        if not nom or not numero:
            continue

        formatted_num = format_gabon_number(str(numero))

        # Validation du format gabonais final (+241 / 12 caractères)
        if len(formatted_num) in (11, 12) and formatted_num.startswith("241"):
            # Vérifier si le numéro existe déjà dans la base ERP pour éviter les doublons
            cursor_new.execute("SELECT id FROM contacts WHERE Contacts = ?", (formatted_num,))
            if cursor_new.fetchone():
                ignored_count += 1
                continue

            # Insertion
            cursor_new.execute(
                "INSERT INTO contacts (Nom, Contacts) VALUES (?, ?)", 
                (nom, formatted_num)
            )
            inserted_count += 1
        else:
            ignored_count += 1

    # Validation de la transaction
    conn_new.commit()

    print("\n✅ Migration terminée avec succès !")
    print(f"   ➡️ {inserted_count} contact(s) transféré(s) et nettoyé(s).")
    print(f"   ➡️ {ignored_count} contact(s) ignoré(s) (doublons ou formats invalides).")

except Exception as e:
    print(f"\n❌ Erreur pendant la migration : {e}")

finally:
    # Fermeture propre des connexions
    if 'conn_old' in locals():
        conn_old.close()
    if 'conn_new' in locals():
        conn_new.close()