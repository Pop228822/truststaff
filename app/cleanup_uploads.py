import time
from pathlib import Path

# Папка, где хранятся фото и pdf
UPLOAD_DIR = Path("static/uploads")
# Время жизни файла (1 дней)
LIFETIME_SECONDS = 60 * 60 * 24

now = time.time()

for file in UPLOAD_DIR.iterdir():
    if file.is_file():
        age = now - file.stat().st_mtime
        if age > LIFETIME_SECONDS:
            print(f"Удаляю: {file.name}")
            file.unlink()
