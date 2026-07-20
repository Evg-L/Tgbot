import os
import sys
import asyncio
import logging
from datetime import datetime

from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import (
    Application,
    CommandHandler,
    CallbackQueryHandler,
    MessageHandler,
    filters,
    ContextTypes,
)

from config import Config
from database import Database

# Настройка логирования
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# Проверка конфигурации
try:
    Config.validate()
except ValueError as e:
    logger.error(f"Ошибка конфигурации: {e}")
    sys.exit(1)

# Инициализация базы данных
db = Database(Config.DB_NAME)

# Создание папки для видео
if not os.path.exists(Config.VIDEO_FOLDER):
    os.makedirs(Config.VIDEO_FOLDER)


# ===================== ОСНОВНЫЕ КОМАНДЫ =====================

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Приветствие и главное меню"""
    user = update.effective_user
    user_id = user.id

    # Проверяем реферальную ссылку
    referrer_id = None
    if context.args:
        try:
            referrer_id = int(context.args[0])
        except ValueError:
            pass

    # Регистрируем пользователя
    is_new = db.add_user(user_id, user.username or "без_username", user.first_name or "Пользователь")

    if is_new and referrer_id:
        db.set_referrer(user_id, referrer_id)

    # Главное меню
    keyboard = [
        [InlineKeyboardButton("🎬 Видео", callback_data="videos")],
        [InlineKeyboardButton("⭐ Проверить звезды", callback_data="check_stars")],
        [InlineKeyboardButton("🔗 Пополнить звезды", callback_data="refill")]
    ]

    await update.message.reply_text(
        f"👋 Привет, {user.first_name or 'Пользователь'}!\n\n"
        f"Добро пожаловать в магазин видео!\n"
        f"У тебя уже есть 2 ⭐ для старта!\n\n"
        f"Используй кнопки ниже:",
        reply_markup=InlineKeyboardMarkup(keyboard)
    )


# ===================== ОБРАБОТЧИКИ КНОПОК =====================

async def button_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Обработка всех кнопок"""
    query = update.callback_query
    await query.answer()

    user_id = query.from_user.id
    data = query.data

    # ===== КНОПКА "Видео" =====
    if data == "videos":
        keyboard = []
        for video_id, name in Config.NAMES.items():
            price = Config.PRICES[video_id]
            keyboard.append([
                InlineKeyboardButton(
                    f"{name} - {price} ⭐",
                    callback_data=f"buy_{video_id}"
                )
            ])
        keyboard.append([
            InlineKeyboardButton("⬅️ Назад", callback_data="back_to_menu")
        ])

        await query.edit_message_text(
            "📹 <b>Выбери видео для покупки:</b>\n\n"
            "Цены указаны в звездах ⭐",
            reply_markup=InlineKeyboardMarkup(keyboard),
            parse_mode="HTML"
        )

    # ===== ПОКУПКА ВИДЕО =====
    elif data.startswith("buy_"):
        video_id = data.replace("buy_", "")
        price = Config.PRICES.get(video_id)
        name = Config.NAMES.get(video_id)

        if not price or not name:
            await query.edit_message_text("❌ Видео не найдено.")
            return

        # Проверяем баланс
        user_data = db.get_user(user_id)
        if not user_data:
            await query.edit_message_text("❌ Ошибка: пользователь не найден.")
            return

        if user_data['stars'] < price:
            await query.edit_message_text(
                f"❌ Недостаточно звезд!\n"
                f"Нужно: {price} ⭐\n"
                f"У тебя: {user_data['stars']} ⭐\n\n"
                f"Пополни баланс через реферальную ссылку!",
                reply_markup=InlineKeyboardMarkup([[
                    InlineKeyboardButton("🔗 Пополнить", callback_data="refill")
                ]])
            )
            return

        # Проверяем наличие видео
        video_file = Config.FILES.get(video_id)
        video_path = os.path.join(Config.VIDEO_FOLDER, video_file)

        if not os.path.exists(video_path):
            await query.edit_message_text(
                f"❌ Видео временно недоступно.\n"
                f"Пожалуйста, попробуй позже."
            )
            return

        # Списываем звезды и записываем покупку
        db.remove_stars(user_id, price)
        db.add_purchase(user_id, video_id, video_path)

        # Отправляем видео
        try:
            with open(video_path, 'rb') as f:
                await context.bot.send_video(
                    chat_id=user_id,
                    video=f,
                    caption=f"✅ {name} куплено!\n"
                            f"💰 Остаток: {db.get_user(user_id)['stars']} ⭐"
                )

            # Возвращаем в меню
            keyboard = [
                [InlineKeyboardButton("🎬 Еще видео", callback_data="videos")],
                [InlineKeyboardButton("⭐ Проверить звезды", callback_data="check_stars")]
            ]
            await query.edit_message_text(
                "✅ Видео отправлено!\n"
                "Что дальше?",
                reply_markup=InlineKeyboardMarkup(keyboard)
            )
        except Exception as e:
            db.add_stars(user_id, price)
            logger.error(f"Ошибка отправки видео: {e}")
            await query.edit_message_text(
                "❌ Ошибка отправки видео.\n"
                "Звезды возвращены."
            )

    # ===== КНОПКА "Проверить звезды" =====
    elif data == "check_stars":
        user_data = db.get_user(user_id)
        if not user_data:
            await query.edit_message_text("❌ Ошибка: пользователь не найден.")
            return

        referrals = db.get_referral_count(user_id)
        purchases = db.get_purchased_videos(user_id)

        text = (
            f"⭐ <b>Твоя статистика</b>\n\n"
            f"🌟 Звезды: {user_data['stars']}\n"
            f"👥 Рефералов: {referrals}\n"
            f"📹 Куплено видео: {len(purchases)}\n"
        )

        if purchases:
            text += "\n📹 <b>Купленные видео:</b>\n"
            for video_id, _, date in purchases[:5]:
                name = Config.NAMES.get(video_id, video_id)
                text += f"• {name} - {date[:10]}\n"

        keyboard = [[InlineKeyboardButton("⬅️ Назад", callback_data="back_to_menu")]]
        await query.edit_message_text(
            text,
            reply_markup=InlineKeyboardMarkup(keyboard),
            parse_mode="HTML"
        )

    # ===== КНОПКА "Пополнить звезды" =====
    elif data == "refill":
        bot_username = context.bot.username
        ref_link = f"https://t.me/{bot_username}?start={user_id}"

        text = (
            "🔗 <b>Пополни звезды!</b>\n\n"
            "Приглашай друзей по ссылке и получай 2 ⭐ за каждого нового пользователя!\n\n"
            f"👤 Твоя ссылка:\n"
            f"<code>{ref_link}</code>\n\n"
            "📤 Отправь ее друзьям и получай звезды!"
        )

        keyboard = [
            [InlineKeyboardButton("📋 Скопировать ссылку", callback_data="copy_link")],
            [InlineKeyboardButton("⬅️ Назад", callback_data="back_to_menu")]
        ]
        await query.edit_message_text(
            text,
            reply_markup=InlineKeyboardMarkup(keyboard),
            parse_mode="HTML"
        )

    # ===== СКОПИРОВАТЬ ССЫЛКУ =====
    elif data == "copy_link":
        bot_username = context.bot.username
        await query.edit_message_text(
            f"🔗 Твоя ссылка:\n"
            f"<code>https://t.me/{bot_username}?start={user_id}</code>\n\n"
            f"Отправь ее друзьям!",
            parse_mode="HTML"
        )

    # ===== НАЗАД В ГЛАВНОЕ МЕНЮ =====
    elif data == "back_to_menu":
        keyboard = [
            [InlineKeyboardButton("🎬 Видео", callback_data="videos")],
            [InlineKeyboardButton("⭐ Проверить звезды", callback_data="check_stars")],
            [InlineKeyboardButton("🔗 Пополнить звезды", callback_data="refill")]
        ]
        await query.edit_message_text(
            "🏠 <b>Главное меню</b>\n\n"
            "Выбери действие:",
            reply_markup=InlineKeyboardMarkup(keyboard),
            parse_mode="HTML"
        )


# ===================== ЗАГРУЗКА ВИДЕО (АДМИН) =====================

async def admin_upload(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Команда для загрузки видео (только админ)"""
    user_id = update.effective_user.id
    if user_id not in Config.ADMIN_IDS:
        await update.message.reply_text("⛔ Доступ запрещен.")
        return

    if not context.args:
        await update.message.reply_text(
            "📤 <b>Загрузка видео</b>\n\n"
            "Использование: /upload ID_видео\n"
            "Доступные ID: test, kids, teens, young\n\n"
            "Пример: /upload test",
            parse_mode="HTML"
        )
        return

    video_id = context.args[0]
    if video_id not in Config.FILES:
        await update.message.reply_text(
            f"❌ Неверный ID.\n"
            f"Доступные: test, kids, teens, young"
        )
        return

    context.user_data["upload_video_id"] = video_id
    await update.message.reply_text(
        f"📤 Отправь видео для: <b>{Config.NAMES[video_id]}</b>\n"
        f"Имя файла: {Config.FILES[video_id]}",
        parse_mode="HTML"
    )


async def handle_video_upload(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Обработка загруженного видео"""
    user_id = update.effective_user.id
    if user_id not in Config.ADMIN_IDS:
        await update.message.reply_text("⛔ Доступ запрещен.")
        return

    if not context.user_data.get("upload_video_id"):
        await update.message.reply_text(
            "❌ Сначала используй /upload ID_видео"
        )
        return

    video_id = context.user_data["upload_video_id"]
    video_file = Config.FILES[video_id]
    video_path = os.path.join(Config.VIDEO_FOLDER, video_file)

    try:
        file = await update.message.video.get_file()
        await file.download_to_drive(video_path)
        await update.message.reply_text(
            f"✅ Видео <b>{Config.NAMES[video_id]}</b> загружено!\n"
            f"💰 Цена: {Config.PRICES[video_id]} ⭐",
            parse_mode="HTML"
        )
        context.user_data.pop("upload_video_id", None)
    except Exception as e:
        await update.message.reply_text(f"❌ Ошибка загрузки: {e}")


# ===================== ЗАПУСК =====================

async def run_bot():
    """Асинхронный запуск бота"""
    logger.info("🤖 Запуск бота...")
    logger.info(f"Категории видео: {len(Config.NAMES)}")
    logger.info(f"Администраторы: {Config.ADMIN_IDS}")

    # Создаем приложение
    application = Application.builder().token(Config.BOT_TOKEN).build()

    # Команды
    application.add_handler(CommandHandler("start", start))
    application.add_handler(CommandHandler("upload", admin_upload))

    # Кнопки
    application.add_handler(CallbackQueryHandler(button_handler))

    # Загрузка видео
    application.add_handler(MessageHandler(filters.VIDEO, handle_video_upload))

    # Запуск
    logger.info("🚀 Бот готов к работе!")

    # Запускаем polling
    await application.initialize()
    await application.start()
    await application.updater.start_polling()

    # Держим бота активным
    try:
        while True:
            await asyncio.sleep(3600)  # Спим час
    except KeyboardInterrupt:
        logger.info("🛑 Остановка бота...")
        await application.updater.stop()
        await application.stop()
        await application.shutdown()


def main():
    """Главная функция"""
    try:
        asyncio.run(run_bot())
    except KeyboardInterrupt:
        logger.info("🛑 Бот остановлен пользователем")
    except Exception as e:
        logger.error(f"❌ Критическая ошибка: {e}")


if __name__ == "__main__":
    main()