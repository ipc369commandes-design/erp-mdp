import asyncio

from app.services.mdp_client import MDPClient


async def main():

    client = MDPClient()

    try:
        data = await client.get_article(
            "9782075187541",
            1
        )

        if data is None:
            print("❌ Données vides")
            return

        article = data.get("article", {})

        if not article:
            print("❌ Article non trouvé")
            return

        titre = article.get("titre", "N/A")
        editeur = article.get("editeur", "N/A")

        print(f"✔ Titre: {titre}")
        print(f"✔ Éditeur: {editeur}")
        
    except Exception as e:
        print(f"❌ Erreur: {type(e).__name__}: {str(e)}")
    
    finally:
        # Fermer proprement le client
        await client.close()


if __name__ == "__main__":
    asyncio.run(main())
