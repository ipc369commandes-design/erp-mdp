from.playwright_manager import PlaywrightManager
import os


class BrowserManager:

    def __init__(self):

        self.browser = None
        self.context = None
        self.page = None
        self._closed = False

    # ==================================================
    # INIT
    # ==================================================
    async def init(self):

        if self._closed:
            self._closed = False

        self.browser = await PlaywrightManager.get_browser()

        if self.browser is None:
            raise Exception("BROWSER NON INITIALISÉ")

        # ==========================================
        # SAFE STORAGE STATE
        # ==========================================
        storage_state_path = "state.json" if os.path.exists("state.json") else None

        self.context = await self.browser.new_context(
            storage_state=storage_state_path
        )

        self.page = await self.context.new_page()

    # ==================================================
    # CLOSE SAFE (IDEMPOTENT)
    # ==================================================
    async def close(self):

        if self._closed:
            return

        self._closed = True

        # ==========================================
        # CLOSE PAGE
        # ==========================================
        if self.page is not None:
            try:
                await self.page.close()
            except Exception as e:
                print("Erreur fermeture page:", e)
            finally:
                self.page = None

        # ==========================================
        # CLOSE CONTEXT
        # ==========================================
        if self.context is not None:
            try:
                await self.context.close()
            except Exception as e:
                print("Erreur fermeture context:", e)
            finally:
                self.context = None

        # ==========================================
        # RESET BROWSER REF
        # ==========================================
        self.browser = None

    # ==================================================
    # SAFETY CHECK
    # ==================================================
    def is_ready(self) -> bool:
        return (
            self.browser is not None
            and self.context is not None
            and self.page is not None
            and not self._closed
        )