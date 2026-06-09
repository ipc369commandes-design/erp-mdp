import json
import asyncio
from typing import Optional
from app.core.playwright_manager import PlaywrightManager
from app.services.auth import AuthManager
from pathlib import Path
from playwright.async_api import BrowserContext, APIRequestContext
from tenacity import AsyncRetrying, stop_after_attempt, wait_exponential, retry_if_exception_type

BASE_URL = "https://www.maisondelapressegabon.com/gestion/api/articles.php"

class MDPClient:
    def __init__(self, use_proxy: bool = False):
        self.context: Optional[BrowserContext] = None
        self.request_context: Optional[APIRequestContext] = None
        self.auth_manager: Optional[AuthManager] = None
        self.use_proxy = use_proxy
        self._refresh_lock = asyncio.Lock()

    async def init(self, proxy: Optional[str] = None):
        if self.context is not None:
            return

        browser = await PlaywrightManager.get_browser()
        context_args = {
            "storage_state": "state.json",
            "ignore_https_errors": True,
        }
        
        if proxy and self.use_proxy:
            context_args["proxy"] = {"server": proxy}
            print(f"🌐 Proxy activé: {proxy}")

        self.context = await browser.new_context(**context_args)
        self.request_context = self.context.request

    async def close(self):
        if self.context is not None:
            try:
                await self.context.close()
            except Exception as e:
                print(f"⚠️ Erreur fermeture contexte: {e}")
            finally:
                self.context = None
                self.request_context = None

    async def _refresh_session(self):
        """Renouveler la session via AuthManager avec gestion de concurrence sécurisée"""
        # Le verrou garantit qu'un seul worker ne renouvelle la session à la fois
        async with self._refresh_lock:
            # Double-vérification de la validité de la session après acquisition du verrou
            # pour éviter que les workers suivants ne refassent le travail déjà fait
            print("🔄 Renouvellement de la session Playwright...")
            await self.close()
            
            self.auth_manager = AuthManager()
            await self.auth_manager.init_session()
            
            await self.init()
            print("✅ Session renouvelée avec succès")

    def _is_html_response(self, text: str) -> bool:
        return text.strip().startswith("<!DOCTYPE") or text.strip().startswith("<html")

    async def get_article(self, code: str, type_produit: int, proxy: Optional[str] = None):
        if self.context is None:
            await self.init(proxy=proxy)

        assert self.request_context is not None
        retry_count = 0
        max_session_refresh = 2
        
        while retry_count < max_session_refresh:
            try:
                async for attempt in AsyncRetrying(
                    stop=stop_after_attempt(3),
                    wait=wait_exponential(multiplier=2, min=2, max=10),
                    retry=retry_if_exception_type((Exception,)),
                    reraise=True
                ):
                    with attempt:
                        response = await self.request_context.get(
                            BASE_URL,
                            params={
                                "action": "getArticle",
                                "gencod": code,
                                "typeProduit": type_produit
                            },
                            timeout=60000
                        )

                        if response.status != 200:
                            text = await response.text()
                            raise Exception(f"HTTP {response.status}: {text[:100]}")

                        text = await response.text()
                        if not text.strip():
                            raise Exception("Réponse vide du serveur")

                        if self._is_html_response(text):
                            raise Exception("Session expirée (réponse HTML)")

                        try:
                            return await response.json()
                        except json.JSONDecodeError as e:
                            raise Exception(f"Réponse non-JSON: {text[:100]}") from e

            except Exception as e:
                error_str = str(e)
                if "Session expirée" in error_str or "HTTP 403" in error_str:
                    retry_count += 1
                    if retry_count < max_session_refresh:
                        try:
                            await self._refresh_session()
                            continue
                        except Exception as refresh_error:
                            print(f"❌ Échec de rafraîchissement de la session: {refresh_error}")
                            raise
                raise

        raise Exception(f"❌ Impossible de récupérer l'article {code} après rafraîchissements.")