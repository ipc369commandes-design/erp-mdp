import asyncio
import json

from app.services.mdp_client import MDPClient


async def main():
    client = MDPClient()

    article = await client.get_article(
        code="9782075187541",
        type_produit=1
    )

    print(json.dumps(
        article,
        indent=2,
        ensure_ascii=False
    ))


asyncio.run(main())