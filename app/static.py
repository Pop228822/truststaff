"""
Настройка статических файлов
"""
from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles


def setup_static_files(app: FastAPI) -> None:
    """Настройка статических файлов"""
    app.mount("/static", StaticFiles(directory="static"), name="static")
