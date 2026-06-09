from app.core.database import SessionLocal
from app.models.sync_status import SyncStatus

db = SessionLocal()

try:
    success = (
        db.query(SyncStatus)
        .filter(SyncStatus.status == "success")
        .count()
    )

    failed = (
        db.query(SyncStatus)
        .filter(SyncStatus.status == "failed")
        .count()
    )

    total = db.query(SyncStatus).count()

    print(f"Total   : {total}")
    print(f"Success : {success}")
    print(f"Failed  : {failed}")

finally:
    db.close()