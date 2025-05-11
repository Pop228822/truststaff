from fastapi import APIRouter
from alembic.config import Config
from alembic import command

router = APIRouter()

@router.post("/__internal__/migrate")
def trigger_migration():
    alembic_cfg = Config("alembic.ini")
    command.upgrade(alembic_cfg, "head")
    return {"status": "migration applied"}
