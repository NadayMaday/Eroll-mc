import os
import json
import random
import shutil
from datetime import datetime, timedelta

from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup, InputMediaPhoto, InputMediaAnimation, BotCommand
from telegram.ext import Application, CommandHandler, CallbackQueryHandler, ContextTypes

# ------------------- КОНФИГУРАЦИЯ -------------------
TOKEN = os.environ.get('BOT_TOKEN')
if not TOKEN:
    raise ValueError("Токен не найден! Добавьте переменную BOT_TOKEN.")

# Railway Volume
DATA_DIR = os.environ.get('DATA_PATH', '/data')
os.makedirs(DATA_DIR, exist_ok=True)

DATA_FILE = os.path.join(DATA_DIR, 'gacha_data.json')
IMAGES_DIR = 'images'
COOLDOWN_SECONDS = 30 * 60  # 30 минут

CATEGORY_CONFIG = {
    'common': {'prefix': 'common_', 'weight': 50, 'emoji': '💙', 'text': 'неплохо'},
    'rare':   {'prefix': 'rare_',   'weight': 25, 'emoji': '💜', 'text': 'тебе сегодня везет'},
    'epic':   {'prefix': 'epic_',   'weight': 19, 'emoji': '❤️', 'text': 'тебе повезло'},
    'legend': {'prefix': 'legend_', 'weight': 5,  'emoji': '💖', 'text': 'это твой день, дорогуша'},
    'porn':   {'prefix': 'Porn_',   'weight': 1,  'emoji': '🖤', 'text': 'ого! вот это удача'}
}

IMAGE_CACHE = {}

# ------------------- СКАНИРОВАНИЕ КАРТИНОК -------------------
def scan_images():
    categories = {cat: [] for cat in CATEGORY_CONFIG}
    if not os.path.exists(IMAGES_DIR):
        return categories
    for filename in os.listdir(IMAGES_DIR):
        if not filename.lower().endswith(('.png', '.jpg', '.jpeg', '.gif')):
            continue
        base = os.path.splitext(filename)[0]
        for cat, config in CATEGORY_CONFIG.items():
            if base.startswith(config['prefix']):
                categories[cat].append(base)
                break
    return categories

def refresh_cache():
    global IMAGE_CACHE
    IMAGE_CACHE = scan_images()
    print("📂 Кеш обновлён:")
    for cat, files in IMAGE_CACHE.items():
        print(f"  {cat}: {len(files)} файлов")

refresh_cache()

# ------------------- РАБОТА С ДАННЫМИ -------------------
def load_data():
    if os.path.exists(DATA_FILE):
        try:
            with open(DATA_FILE, 'r', encoding='utf-8') as f:
                return json.load(f)
        except Exception as e:
            print(f"❌ Ошибка чтения: {e}")
            create_backup("corrupted")
            return {}
    return {}

def save_data(data):
    try:
        create_backup()
        with open(DATA_FILE, 'w', encoding='utf-8') as f:
            json.dump(data, f, ensure_ascii=False, indent=2)
        print(f"✅ Данные сохранены")
    except Exception as e:
        print(f"❌ Ошибка сохранения: {e}")

def create_backup(prefix="backup"):
    if not os.path.exists(DATA_FILE):
        return None
    timestamp = datetime.now().strftime("%Y-%m-%d_%H-%M-%S")
    backup_name = os.path.join(DATA_DIR, f'gacha_data_{prefix}_{timestamp}.json')
    try:
        shutil.copy2(DATA_FILE, backup_name)
        print(f"✅ Бэкап создан: {os.path.basename(backup_name)}")
        return backup_name
    except Exception as e:
        print(f"❌ Ошибка бэкапа: {e}")
        return None

# ------------------- ВСПОМОГАТЕЛЬНЫЕ ФУНКЦИИ -------------------
def find_image_file(name):
    if not os.path.exists(IMAGES_DIR):
        return None
    for filename in os.listdir(IMAGES_DIR):
        if os.path.splitext(filename)[0].lower() == name.lower():
            return os.path.join(IMAGES_DIR, filename)
    return None

def get_random_card(user_id=None):
    available_cats = [(cat, config['weight']) for cat, config in CATEGORY_CONFIG.items() if IMAGE_CACHE.get(cat)]
    if not available_cats:
        return None

    total_weight = sum(w for _, w in available_cats)
    rand = random.randint(1, total_weight)
    cumulative = 0
    for cat, weight in available_cats:
        cumulative += weight
        if rand <= cumulative:
            chosen_cat = cat
            break

    files = IMAGE_CACHE[chosen_cat]
    file_name = random.choice(files)

    if user_id and len(files) > 1:
        data = load_data()
        last_card = data.get(user_id, {}).get('last_card')
        if last_card and last_card in files:
            filtered = [f for f in files if f != last_card]
            if filtered:
                file_name = random.choice(filtered)

    config = CATEGORY_CONFIG[chosen_cat]
    return {'category': chosen_cat, 'file_name': file_name, 'emoji': config['emoji'], 'text': config['text']}

# ------------------- КОМАНДЫ -------------------
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("🎲 Привет! Команды: /pull, /pack, /status, /refresh")

async def status(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = str(update.effective_user.id)
    data = load_data()
    if user_id not in data or 'last_pull' not in data[user_id]:
        return await update.message.reply_text("Ещё не тянули. Используй /pull")
    # ... (остальной код status можно оставить как раньше)

# set_commands — исправленная функция
async def set_commands(app):
    commands = [
        BotCommand("start", "Приветствие"),
        BotCommand("pull", "Вытянуть карточку"),
        BotCommand("pack", "Показать коллекцию"),
        BotCommand("status", "Оставшееся время"),
        BotCommand("refresh", "Обновить картинки"),
        BotCommand("backup", "Создать бэкап (только админ)"),
    ]
    await app.bot.set_my_commands(commands)

# ------------------- ЗАПУСК -------------------
def main():
    app = Application.builder().token(TOKEN).post_init(set_commands).build()

    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("pull", pull))
    app.add_handler(CommandHandler("pack", pack))
    app.add_handler(CommandHandler("status", status))
    app.add_handler(CommandHandler("refresh", refresh))
    app.add_handler(CommandHandler("backup", backup))
    app.add_handler(CallbackQueryHandler(pack_callback, pattern="^pack_"))

    create_backup("startup")
    print("🚀 Бот запущен...")
    app.run_polling()

if __name__ == '__main__':
    main()