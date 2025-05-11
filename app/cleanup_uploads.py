import time
from pathlib import Path

# Папка, где хранятся фото и pdf
UPLOAD_DIR = Path("static/uploads")
# Время жизни файла (7 дней)
LIFETIME_SECONDS = 20

now = time.time()

for file in UPLOAD_DIR.iterdir():
    if file.is_file():
        age = now - file.stat().st_mtime
        if age > LIFETIME_SECONDS:
            print(f"Удаляю: {file.name}")
            file.unlink()
