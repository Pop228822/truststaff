"""
Обработчики событий приложения (startup/shutdown)
"""
from fastapi import FastAPI
from apscheduler.schedulers.background import BackgroundScheduler

from app.jobs.cleanup_PU import cleanup_pending_users


def setup_events(app: FastAPI) -> None:
    """Настройка обработчиков событий приложения"""
    scheduler = BackgroundScheduler()

    @app.on_event("startup")
    def startup_event():
        """Запуск фоновых задач при старте приложения"""
        scheduler.add_job(cleanup_pending_users, 'interval', minutes=10)
        scheduler.start()

    @app.on_event("shutdown")
    def shutdown_event():
        """Остановка фоновых задач при завершении приложения"""
        scheduler.shutdown()
