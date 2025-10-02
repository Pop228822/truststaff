"""
Главный файл приложения TrustStaff
"""
from dotenv import load_dotenv

from app.config import create_app
from app.routers import setup_routers
from app.events import setup_events
from app.static import setup_static_files
from app.error_handlers import setup_error_handlers

# Загружаем переменные окружения
load_dotenv()

# Создаем приложение
app = create_app()

# Настраиваем все компоненты
setup_routers(app)
setup_events(app)
setup_static_files(app)
setup_error_handlers(app)