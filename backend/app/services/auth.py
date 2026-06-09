import os
import asyncio
from playwright.async_api import Browser, BrowserContext, Page
from app.core.playwright_manager import PlaywrightManager

BASE_URL = "https://www.maisondelapressegabon.com/gestion"
STATE_FILE = "state.json"

# Utilisation recommandée de variables d'environnement avec fallback
USERNAME = os.getenv("MDP_USERNAME", "ipc369@yahoo.fr")
PASSWORD = os.getenv("MDP_PASSWORD", "Libreville963@")

class AuthManager:
    def __init__(self):
        self.browser: Browser | None = None
        self.context: BrowserContext | None = None
        self.page: Page | None = None

    async def init(self):
        await PlaywrightManager.init(headless=True) # headles=True recommandé pour le serveur de prod
        self.browser = await PlaywrightManager.get_browser()

    async def _new_context(self, storage=None):
        if self.context:
            try:
                await self.context.close()
            except Exception as e:
                print("context close error:", e)

        assert self.browser is not None
        self.context = await self.browser.new_context(
            storage_state=storage if storage else None
        )
        self.page = await self.context.new_page()

    async def is_session_valid(self):
        if not os.path.exists(STATE_FILE):
            return False

        try:
            await self._new_context(storage=STATE_FILE)
            assert self.page is not None

            await self.page.goto(BASE_URL, wait_until="domcontentloaded")
            await self.page.wait_for_timeout(2000)

            url = self.page.url.lower()
            if "login" in url or "connexion" in url:
                return False

            login_field = await self.page.locator("input[name='login']").count()
            if login_field > 0:
                return False

            return True
        except Exception as e:
            print("Session check error:", e)
            return False

    async def login(self):
        print("Connexion automatique...")
        await self._new_context()
        assert self.page is not None

        await self.page.goto(BASE_URL, wait_until="domcontentloaded")
        await self.page.wait_for_timeout(3000)

        if "index_ventes" in self.page.url:
            print("Déjà connecté")
            return

        await self.page.wait_for_load_state("domcontentloaded")

        login_input = self.page.locator("input[name='login'], input[type='text']").first
        password_input = self.page.locator("input[type='password']").first

        if await login_input.count() == 0 or await password_input.count() == 0:
            print("❌ Champs login/password introuvables")
            await self.page.screenshot(path="debug_login.png", full_page=True)
            return

        print("Remplissage credentials...")
        await login_input.fill(USERNAME)
        await password_input.fill(PASSWORD)

        print("Envoi du formulaire...")
        await self.page.locator("button:has-text('Se connecter')").click()
        await self.page.wait_for_load_state("networkidle")
        await self.page.wait_for_timeout(3000)

        login_field = await self.page.locator("input[name='login']").count()
        if login_field == 0:
            assert self.context is not None
            await self.context.storage_state(path=STATE_FILE)
            print("SESSION SAUVEGARDEE AVEC SUCCES")
        else:
            print("❌ Login non validé")
            await self.page.screenshot(path="login_failed.png", full_page=True)

    async def init_session(self):
        await self.init()
        if await self.is_session_valid():
            print("Session valide")
        else:
            print("Session invalide ou expirée")
            await self.login()
        print("SESSION OK")

    async def close(self):
        if self.context:
            try:
                await self.context.close()
            except Exception as e:
                print("context close error:", e)
        self.context = None
        self.page = None