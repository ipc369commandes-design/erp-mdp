import asyncio
from playwright.async_api import async_playwright


class PlaywrightManager:

    _playwright = None
    _browser = None
    _lock = asyncio.Lock()

    @classmethod
    async def init(cls, headless: bool = False):

        async with cls._lock:

            if cls._browser:
                return cls._browser

            cls._playwright = await async_playwright().start()

            # ✅ FIX : Ajout de '--disable-http2' dans les arguments pour éliminer ERR_HTTP2_PROTOCOL_ERROR
            cls._browser = await cls._playwright.chromium.launch(
                headless=headless,
                args=["--disable-http2"]
            )

            return cls._browser

    # ==========================================
    # GET BROWSER
    # ==========================================
    @classmethod
    async def get_browser(cls):

        if cls._browser is None:
            await cls.init()

        if cls._browser is None:
            raise Exception("Browser non initialisé")

        return cls._browser

    # ==========================================
    # CLOSE SAFE
    # ==========================================
    @classmethod
    async def close(cls):

        if cls._browser:
            try:
                await cls._browser.close()
            except Exception as e:
                print("browser close error:", e)
            finally:
                cls._browser = None

        if cls._playwright:
            try:
                await cls._playwright.stop()
            except Exception as e:
                print("playwright stop error:", e)
            finally:
                cls._playwright = None