from sqlmodel import SQLModel
from app.database import engine # или app.database, если внутри пакета

# Явный импорт всех моделей
from models import User, Employee, ReputationRecord, LoginAttempt, PendingUser, CheckLog, RateLimit

def init():
    SQLModel.metadata.create_all(engine)

if __name__ == "__main__":
    init()