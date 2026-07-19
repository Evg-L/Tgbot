import os
from dotenv import load_dotenv

load_dotenv()


class Config:
    BOT_TOKEN = os.getenv('BOT_TOKEN')
    ADMIN_IDS = [int(id.strip()) for id in os.getenv('ADMIN_IDS', '').split(',') if id.strip()]
    DB_NAME = os.getenv('DB_NAME', 'bot_database.db')
    VIDEO_FOLDER = os.getenv('VIDEO_FOLDER', 'videos')
    PORT = int(os.getenv('PORT', 5000))

    # Цены на видео
    PRICES = {
        "test": 4,
        "kids": 20,
        "teens": 15,
        "young": 10
    }

    # Названия для кнопок
    NAMES = {
        "test": "🎬 Тестовый пакет",
        "kids": "👶 Детишки",
        "teens": "🧑 Подростки",
        "young": "🍼 Малолетки"
    }

    # Файлы видео
    FILES = {
        "test": "test.mp4",
        "kids": "kids.mp4",
        "teens": "teens.mp4",
        "young": "young.mp4"
    }

    @classmethod
    def validate(cls):
        if not cls.BOT_TOKEN:
            raise ValueError("BOT_TOKEN не найден в .env файле!")
        if not cls.ADMIN_IDS:
            raise ValueError("ADMIN_IDS не найден в .env файле!")
        return True