import os
import csv
import sqlite3

# Détection automatique du fichier CSV source
CSV_FILENAME = "contacts.csv"
if not os.path.exists(CSV_FILENAME):
    if os.path.exists("contacts (1).csv"):
        CSV_FILENAME = "contacts (1).csv"

# Détection de la base de données ERP active
ERP_DB_PATH = "data/erp.db"

print("🔍 Recherche des fichiers...")
print(f"   ➡️ Fichier source CSV : {os.path.abspath(CSV_FILENAME)}")
print(f"   ➡️ Base de données ERP : {os.path.abspath(ERP_DB_PATH)}")

if not os.path.exists(CSV_FILENAME):
    print("❌ Erreur : Le fichier de contacts CSV est introuvable dans le dossier actuel.")
    exit(1)

if not os.path.exists(ERP_DB_PATH):
    print("❌ Erreur : La base de données 'erp.db' est introuvable. Veuillez lancer uvicorn au moins une fois.")
    exit(1)

def format_gabon_number(number: str) -> str:
    """Nettoie et formate le numéro selon la norme ARCEP Gabon"""
    num_clean = "".join(filter(str.isdigit, number))
    if not num_clean:
        return ""
    if number.startswith("+241"):
        return number.replace("+", "")
    elif number.startswith("0"):
        return "241" + num_clean[1:]
    elif not num_clean.startswith("241"):
        return "241" + num_clean
    return num_clean

try:
    # Connexion à la base de données ERP
    conn = sqlite3.connect(ERP_DB_PATH)
    cursor = conn.cursor()

    # Créer la table si elle n'existe pas
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS contacts (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            Nom TEXT NOT NULL,
            Contacts TEXT NOT NULL UNIQUE
        )
    """)
    conn.commit()

    added_count = 0
    duplicate_count = 0
    invalid_count = 0

    # Lecture du fichier CSV avec détection de l'encodage (utf-8-sig gère le BOM excel)
    with open(CSV_FILENAME, mode='r', encoding='utf-8-sig', errors='ignore') as f:
        reader = csv.reader(f)
        headers = next(reader, None)
        
        # Vérification s'il s'agit d'un export Google brut ou d'un fichier simple
        is_google_format = headers and "First Name" in headers
        
        first_name_idx, middle_name_idx, last_name_idx = -1, -1, -1
        phone_cols_indices = []

        if is_google_format:
            print("📋 Format Google Contacts détecté. Analyse des colonnes...")
            # Trouver les index des colonnes de nom
            if "First Name" in headers: first_name_idx = headers.index("First Name")
            if "Middle Name" in headers: middle_name_idx = headers.index("Middle Name")
            if "Last Name" in headers: last_name_idx = headers.index("Last Name")
            
            # Identifier toutes les colonnes contenant des numéros de téléphone
            for idx, header in enumerate(headers):
                if "Phone" in header and "Value" in header:
                    phone_cols_indices.append(idx)
        else:
            print("📋 Format CSV simple (2 colonnes) détecté.")

        # Traitement des lignes
        for row_idx, row in enumerate(reader, start=2):
            if not row:
                continue

            nom = "Inconnu"
            raw_phone_entries = []

            if is_google_format:
                # Reconstruire le nom complet
                parts = []
                if first_name_idx < len(row) and row[first_name_idx].strip():
                    parts.append(row[first_name_idx].strip())
                if middle_name_idx < len(row) and row[middle_name_idx].strip():
                    parts.append(row[middle_name_idx].strip())
                if last_name_idx < len(row) and row[last_name_idx].strip():
                    parts.append(row[last_name_idx].strip())
                
                if parts:
                    nom = " ".join(parts)
                
                # Extraire les numéros de téléphone de toutes les colonnes détectées
                for col_idx in phone_cols_indices:
                    if col_idx < len(row) and row[col_idx].strip():
                        raw_phone_entries.append(row[col_idx].strip())
            else:
                # Format simple (colonne 0 = nom, colonne 1 = numéro)
                if len(row) >= 2:
                    nom = row[0].strip() or "Inconnu"
                    raw_phone_entries.append(row[1].strip())

            # Traitement et nettoyage de chaque entrée téléphonique trouvée sur la ligne
            for raw_phone in raw_phone_entries:
                # Gestion des cas de numéros multiples séparés par ':::'
                sub_numbers = [n.strip() for n in raw_phone.split(":::")]
                for sub_num in sub_numbers:
                    if not sub_num:
                        continue
                        
                    formatted = format_gabon_number(sub_num)
                    
                    # Validation du format (11 ou 12 chiffres commençant par 241)
                    if len(formatted) in (11, 12) and formatted.startswith("241"):
                        # Vérification stricte des doublons au niveau du NUMÉRO (pas du nom)
                        cursor.execute("SELECT id FROM contacts WHERE Contacts = ?", (formatted,))
                        if cursor.fetchone():
                            duplicate_count += 1
                            continue # Le numéro existe déjà, on l'ignore silencieusement
                        
                        # Insertion du nouveau numéro unique
                        cursor.execute("INSERT INTO contacts (Nom, Contacts) VALUES (?, ?)", (nom, formatted))
                        added_count += 1
                    else:
                        invalid_count += 1

    # Appliquer les modifications
    conn.commit()
    
    # Forcer la fusion SQLite du cache WAL vers le fichier principal erp.db
    cursor.execute("PRAGMA wal_checkpoint(TRUNCATE);")
    conn.commit()

    print("\n✅ Importation et nettoyage terminés avec succès !")
    print(f"   ➡️ {added_count} nouveau(x) numéro(s) unique(s) importé(s).")
    print(f"   ➡️ {duplicate_count} doublon(s) de numéro ignoré(s).")
    print(f"   ➡️ {invalid_count} ligne(s) sans numéro ou au format invalide ignorée(s).")

except Exception as e:
    print(f"\n❌ Erreur pendant l'importation : {e}")

finally:
    if 'conn' in locals():
        conn.close()