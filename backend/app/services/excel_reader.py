import os
import pandas as pd


class ExcelReader:

    def __init__(self, file_path: str):

        self.file_path = file_path

        if not os.path.exists(file_path):
            raise FileNotFoundError(
                f"Fichier introuvable : {file_path}"
            )

        file_size_mb = os.path.getsize(file_path) / 1024 / 1024

        print(f"📄 Fichier Excel : {file_path}")
        print(f"📦 Taille : {file_size_mb:.2f} MB")

    # ==================================================
    # LOAD PRODUCTS
    # ==================================================
    def load(self):

        print("⏳ Lecture du fichier Excel...")

        try:

            df = pd.read_excel(
                self.file_path,
                sheet_name=0,
                usecols=["code", "prix_vente"],
                dtype={
                    "code": str
                }
            )

            print(f"📊 {len(df)} lignes lues")

        except Exception as e:

            print(f"❌ Erreur lecture Excel : {e}")
            raise

        required_cols = {
            "code",
            "prix_vente"
        }

        missing = required_cols - set(df.columns)

        if missing:

            raise ValueError(
                f"Colonnes manquantes : {missing}"
            )

        df = df.fillna("")

        products = []
        skipped = 0

        for idx, row in df.iterrows():

            raw_code = str(
                row["code"]
            ).strip()

            # Excel transforme parfois les EAN en float
            if raw_code.endswith(".0"):
                raw_code = raw_code[:-2]

            code = raw_code

            if not code:
                skipped += 1
                continue

            try:
                prix_vente = float(
                    row["prix_vente"]
                ) if row["prix_vente"] != "" else 0.0

            except Exception:
                prix_vente = 0.0

            products.append({
                "code": code,
                "prix_vente": prix_vente
            })

            if (idx + 1) % 10000 == 0:

                print(
                    f"   ✅ {idx + 1} articles traités..."
                )

        print()
        print(f"✅ {len(products)} produits chargés")
        print(f"⚠️ {skipped} lignes ignorées")

        return products