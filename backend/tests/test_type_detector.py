import asyncio

from app.services.mdp_client import MDPClient
from app.services.type_detector import TypeDetector
from app.core.playwright_manager import PlaywrightManager


async def main():

    try:

        client = MDPClient()

        detector = TypeDetector(client)

        result = await detector.detect(
            "9782075187541"
        )

        print("Type détecté :", result)

    except Exception as e:

        print(f"Erreur : {e}")

    finally:

        await PlaywrightManager.close()


if __name__ == "__main__":
    asyncio.run(main())