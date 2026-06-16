from fastapi import APIRouter, BackgroundTasks, HTTPException
from fastapi.responses import JSONResponse
from app.services.sync_service import SyncService
from app.core.database import SessionLocal
from app.models.sync_status import SyncStatus
import os

router = APIRouter()

class LogCapture:
    def __init__(self):
        self.logs = []
        self.max_logs = 100
    
    def add(self, message: str):
        self.logs.append(message)
        if len(self.logs) > self.max_logs:
            self.logs = self.logs[-self.max_logs:]
    
    def get_logs(self):
        return self.logs

log_capture = LogCapture()

# État global centralisé de la synchronisation
sync_status = {
    "running": False,
    "progress": 0,
    "message": "",
    "should_stop": False,
    "stats": {
        "total": 0,
        "success": 0,
        "failed": 0,
        "pending": 0,
        "current_product": "",
        "current_batch": ""
    }
}

@router.get("/sync/status")
def get_sync_status():
    """Récupérer l'état actuel de la synchronisation"""
    db = SessionLocal()
    try:
        total = db.query(SyncStatus).count()
        success = db.query(SyncStatus).filter(SyncStatus.status == "success").count()
        failed = db.query(SyncStatus).filter(SyncStatus.status == "failed").count()
        pending = db.query(SyncStatus).filter(SyncStatus.status == "pending").count()
        
        progress = (success / total * 100) if total > 0 else 0
        
        return {
            "running": sync_status["running"],
            "progress": progress,
            "message": sync_status["message"],
            "stats": {
                "total": total,
                "success": success,
                "failed": failed,
                "pending": pending,
                "remaining": pending,
                "current_product": sync_status["stats"]["current_product"],
                "current_batch": sync_status["stats"]["current_batch"],
                "logs": log_capture.get_logs()
            }
        }
    finally:
        db.close()

@router.post("/sync/start")
async def start_sync(background_tasks: BackgroundTasks):
    """Lancer la synchronisation en tâche de fond native"""
    if sync_status["running"]:
        raise HTTPException(
            status_code=400,
            detail="Une synchronisation est déjà en cours"
        )
    
    log_capture.logs = []
    sync_status["running"] = True
    sync_status["should_stop"] = False
    sync_status["progress"] = 0
    sync_status["message"] = "🚀 Démarrage de la synchronisation..."
    
    # Lancement asynchrone sécurisé géré par FastAPI
    background_tasks.add_task(run_sync_task)
    
    return {
        "status": "started",
        "message": "La synchronisation a démarré"
    }

@router.post("/sync/stop")
def stop_sync():
    """Arrêter la synchronisation de manière coopérative"""
    if not sync_status["running"]:
        raise HTTPException(
            status_code=400,
            detail="Aucune synchronisation en cours"
        )
    
    sync_status["should_stop"] = True
    sync_status["message"] = "⛔ Arrêt de la synchronisation demandé..."
    log_capture.add("⛔ Arrêt demandé par l'utilisateur")
    
    return {
        "status": "stopping",
        "message": "La synchronisation est en train de s'arrêter"
    }

async def run_sync_task():
    """Tâche d'arrière-plan asynchrone, isolée et protégée en mémoire"""
    try:
        excel_path = os.path.join(
            os.path.dirname(os.path.dirname(os.path.dirname(__file__))),
            "data",
            "catalogue.xlsx"
        )
        
        log_capture.add(f"📄 Excel : {excel_path} (Existe: {os.path.exists(excel_path)})")
        sync_status["message"] = "⏳ Chargement du fichier Excel..."
        
        # Injection de callbacks pour éviter de rediriger stdout de manière globale
        def log_listener(msg: str):
            log_capture.add(msg)

        def check_stop_requested() -> bool:
            return sync_status["should_stop"]

        def update_current_product(product_title: str):
            sync_status["stats"]["current_product"] = product_title

        sync_service = SyncService(
            excel_path=excel_path,
            use_proxy=False,
            log_callback=log_listener,
            stop_checker=check_stop_requested,
            product_tracker=update_current_product
        )
        
        sync_status["message"] = "🔄 Synchronisation en cours..."
        
        # ✅ FIX : Calibrage dynamique selon l'environnement (Render vs Local)
        is_render = os.getenv("RENDER") is not None
        
        if is_render:
            # Sur Render (Limité à 512 Mo de RAM) : Configuration ultra-légère et sécurisée
            batch_size = 5
            delay = 2.0
            concurrency = 1
            log_capture.add("ℹ️ Mode économie de mémoire activé pour Render (Limite 512 Mo).")
        else:
            # En local (votre PC) : Mode vitesse maximale
            batch_size = 15
            delay = 1.0
            concurrency = 3
            log_capture.add("ℹ️ Mode performance maximale activé pour le développement local.")
            
        await sync_service.run(batch_size=batch_size, delay_between_batches=delay, concurrency=concurrency)
        
        if sync_status["should_stop"]:
            sync_status["message"] = "⛔ Synchronisation arrêtée par l'utilisateur"
            log_capture.add("⛔ Synchronisation arrêtée avec succès")
        else:
            db = SessionLocal()
            try:
                total = db.query(SyncStatus).count()
                success = db.query(SyncStatus).filter(SyncStatus.status == "success").count()
                
                sync_status["progress"] = 100
                sync_status["message"] = f"✅ Sync terminée! {success}/{total} produits synchronisés"
                log_capture.add(f"✅ Synchronisation terminée avec succès ({success}/{total} produits)")
            finally:
                db.close()
                
    except Exception as e:
        error_msg = f"❌ Erreur critique sync: {e}"
        log_capture.add(error_msg)
        sync_status["message"] = error_msg
        sync_status["progress"] = 0
    finally:
        sync_status["running"] = False
        sync_status["should_stop"] = False