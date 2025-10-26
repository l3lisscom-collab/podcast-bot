import os
import logging
from telegram import Update
from telegram.ext import Application, CommandHandler, MessageHandler, filters, ContextTypes
import subprocess
from pathlib import Path
import asyncio

# Настройка логирования
logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.INFO
)
logger = logging.getLogger(__name__)

# ВСТАВЬТЕ СЮДА ВАШ ТОКЕН БОТА
BOT_TOKEN = "ВАШ_ТОКЕН_СЮДА"

# Папка для временных файлов
TEMP_DIR = Path("temp_audio")
TEMP_DIR.mkdir(exist_ok=True)

# Хранилище файлов пользователей
user_files = {}

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Команда /start"""
    await update.message.reply_text(
        "👋 Привет! Я бот для монтажа подкастов.\n\n"
        "📎 Отправьте мне 2-3 аудиофайла\n"
        "⚡️ Затем отправьте команду /process\n\n"
        "Я склею их, ускорю на 1.2x и отправлю готовый файл!"
    )

async def handle_audio(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Обработка полученных аудиофайлов"""
    user_id = update.effective_user.id
    
    # Инициализация списка файлов для пользователя
    if user_id not in user_files:
        user_files[user_id] = []
    
    # Получаем файл
    if update.message.audio:
        file = await update.message.audio.get_file()
        file_name = update.message.audio.file_name or f"audio_{len(user_files[user_id])}.mp3"
    elif update.message.voice:
        file = await update.message.voice.get_file()
        file_name = f"voice_{len(user_files[user_id])}.ogg"
    elif update.message.document and update.message.document.mime_type.startswith('audio'):
        file = await update.message.document.get_file()
        file_name = update.message.document.file_name
    else:
        await update.message.reply_text("❌ Пожалуйста, отправьте аудиофайл")
        return
    
    # Сохраняем файл
    file_path = TEMP_DIR / f"{user_id}_{len(user_files[user_id])}_{file_name}"
    await file.download_to_drive(file_path)
    
    user_files[user_id].append(str(file_path))
    
    await update.message.reply_text(
        f"✅ Файл {len(user_files[user_id])} получен!\n"
        f"📝 Всего файлов: {len(user_files[user_id])}\n\n"
        f"Отправьте еще файлы или используйте /process для обработки"
    )

async def process(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Обработка и склейка файлов"""
    user_id = update.effective_user.id
    
    if user_id not in user_files or len(user_files[user_id]) == 0:
        await update.message.reply_text("❌ Сначала отправьте аудиофайлы!")
        return
    
    if len(user_files[user_id]) < 2:
        await update.message.reply_text("❌ Нужно минимум 2 файла для склейки!")
        return
    
    await update.message.reply_text("⏳ Обрабатываю файлы... Это может занять минуту.")
    
    try:
        # Создаем список файлов для FFmpeg
        file_list_path = TEMP_DIR / f"{user_id}_filelist.txt"
        with open(file_list_path, 'w', encoding='utf-8') as f:
            for audio_file in user_files[user_id]:
                # FFmpeg требует формат: file 'path'
                f.write(f"file '{audio_file}'\n")
        
        # Выходной файл
        output_file = TEMP_DIR / f"{user_id}_output.mp3"
        
        # FFmpeg команда: склейка + ускорение на 1.2x
        command = [
            'ffmpeg',
            '-f', 'concat',
            '-safe', '0',
            '-i', str(file_list_path),
            '-filter:a', 'atempo=1.2',  # Ускорение на 1.2x
            '-codec:a', 'libmp3lame',
            '-b:a', '192k',
            '-y',  # Перезаписывать файл
            str(output_file)
        ]
        
        # Запускаем FFmpeg
        result = subprocess.run(
            command,
            capture_output=True,
            text=True,
            timeout=300  # 5 минут таймаут
        )
        
        if result.returncode != 0:
            logger.error(f"FFmpeg error: {result.stderr}")
            await update.message.reply_text(
                f"❌ Ошибка обработки:\n{result.stderr[:500]}"
            )
            return
        
        # Проверяем, что файл создан
        if not output_file.exists():
            await update.message.reply_text("❌ Файл не был создан. Попробуйте еще раз.")
            return
        
        # Отправляем файл
        await update.message.reply_text("📤 Отправляю готовый файл...")
        
        with open(output_file, 'rb') as audio:
            await update.message.reply_audio(
                audio=audio,
                filename=f"podcast_processed_{user_id}.mp3",
                caption="✅ Готово! Файлы склеены и ускорены на 1.2x"
            )
        
        # Очистка файлов пользователя
        cleanup_user_files(user_id)
        
        await update.message.reply_text(
            "🎉 Готово! Можете отправлять новые файлы.\n"
            "Используйте /clear чтобы очистить текущие файлы."
        )
        
    except subprocess.TimeoutExpired:
        await update.message.reply_text("❌ Таймаут обработки. Файлы слишком большие.")
    except Exception as e:
        logger.error(f"Processing error: {e}")
        await update.message.reply_text(f"❌ Ошибка: {str(e)}")
        cleanup_user_files(user_id)

async def clear(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Очистка файлов пользователя"""
    user_id = update.effective_user.id
    cleanup_user_files(user_id)
    await update.message.reply_text("🗑 Файлы очищены. Можете отправлять новые.")

def cleanup_user_files(user_id: int):
    """Удаление временных файлов пользователя"""
    if user_id in user_files:
        for file_path in user_files[user_id]:
            try:
                if os.path.exists(file_path):
                    os.remove(file_path)
            except Exception as e:
                logger.error(f"Error deleting file {file_path}: {e}")
        
        # Удаляем также файл списка и выходной файл
        try:
            file_list = TEMP_DIR / f"{user_id}_filelist.txt"
            if file_list.exists():
                os.remove(file_list)
            
            output_file = TEMP_DIR / f"{user_id}_output.mp3"
            if output_file.exists():
                os.remove(output_file)
        except Exception as e:
            logger.error(f"Error in cleanup: {e}")
        
        user_files[user_id] = []

async def help_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Команда /help"""
    await update.message.reply_text(
        "📖 Инструкция:\n\n"
        "1️⃣ Отправьте 2-3 аудиофайла\n"
        "2️⃣ Отправьте команду /process\n"
        "3️⃣ Получите готовый файл!\n\n"
        "🔧 Команды:\n"
        "/start - Начать работу\n"
        "/process - Обработать файлы\n"
        "/clear - Очистить текущие файлы\n"
        "/help - Эта справка"
    )

def main():
    """Запуск бота"""
    # Проверка токена
    if BOT_TOKEN == "ВАШ_ТОКЕН_СЮДА":
        print("❌ ОШИБКА: Вставьте токен бота в переменную BOT_TOKEN!")
        return
    
    # Проверка FFmpeg
    try:
        result = subprocess.run(['ffmpeg', '-version'], capture_output=True)
        if result.returncode != 0:
            print("❌ FFmpeg не установлен!")
            return
        print("✅ FFmpeg найден")
    except FileNotFoundError:
        print("❌ FFmpeg не найден! Установите его в Replit.")
        return
    
    # Создание приложения
    application = Application.builder().token(BOT_TOKEN).build()
    
    # Регистрация обработчиков
    application.add_handler(CommandHandler("start", start))
    application.add_handler(CommandHandler("help", help_command))
    application.add_handler(CommandHandler("process", process))
    application.add_handler(CommandHandler("clear", clear))
    
    # Обработчик аудио и голосовых сообщений
    application.add_handler(MessageHandler(
        filters.AUDIO | filters.VOICE | filters.Document.AUDIO,
        handle_audio
    ))
    
    print("🤖 Бот запущен!")
    
    # Запуск бота
    application.run_polling(allowed_updates=Update.ALL_TYPES)

if __name__ == '__main__':
    main()
