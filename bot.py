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

# Поддержка Railway Volume
DATA_DIR = os.environ.get('DATA_PATH', '/data')
os.makedirs(DATA_DIR, exist_ok=True)

DATA_FILE = os.path.join(DATA_DIR, 'gacha_data.json')
IMAGES_DIR = 'images'
COOLDOWN_SECONDS = 30 * 60  # 30 минут

# Конфигурация категорий
CATEGORY_CONFIG = {
    'common': {'prefix': 'common_', 'weight': 50, 'emoji': '💙', 'text': 'неплохо'},
    'rare':   {'prefix': 'rare_',   'weight': 25, 'emoji': '💜', 'text': 'тебе сегодня везет'},
    'epic':   {'prefix': 'epic_',   'weight': 19, 'emoji': '❤️', 'text': 'тебе повезло'},
    'legend': {'prefix': 'legend_', 'weight': 5,  'emoji': '💖', 'text': 'это твой день, дорогуша'},
    'porn':   {'prefix': 'Porn_',   'weight': 1,  'emoji': '🖤', 'text': 'ого! вот это удача'}
}

# Глобальный кеш картинок
IMAGE_CACHE = {}

# ------------------- ФУНКЦИИ СКАНИРОВАНИЯ -------------------
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
        except (json.JSONDecodeError, OSError) as e:
            print(f"❌ Ошибка чтения данных: {e}")
            # Создаём бэкап повреждённого файла
            create_backup("corrupted")
            return {}
    return {}

def save_data(data):
    try:
        # Создаём бэкап перед сохранением
        create_backup()
        with open(DATA_FILE, 'w', encoding='utf-8') as f:
            json.dump(data, f, ensure_ascii=False, indent=2)
        print(f"✅ Данные сохранены ({len(data)} пользователей)")
    except Exception as e:
        print(f"❌ Ошибка сохранения данных: {e}")

def create_backup(prefix="backup"):
    """Создаёт бэкап с датой"""
    if not os.path.exists(DATA_FILE):
        return None
    timestamp = datetime.now().strftime("%Y-%m-%d_%H-%M-%S")
    backup_name = os.path.join(DATA_DIR, f'gacha_data_{prefix}_{timestamp}.json')
    try:
        shutil.copy2(DATA_FILE, backup_name)
        print(f"✅ Создан бэкап: {backup_name}")
        return backup_name
    except Exception as e:
        print(f"❌ Не удалось создать бэкап: {e}")
        return None

# ------------------- ВСПОМОГАТЕЛЬНЫЕ ФУНКЦИИ -------------------
def find_image_file(name):
    if not os.path.exists(IMAGES_DIR):
        return None
    for filename in os.listdir(IMAGES_DIR):
        base = os.path.splitext(filename)[0]
        if base.lower() == name.lower():
            return os.path.join(IMAGES_DIR, filename)
    return None

def get_random_card(user_id=None):
    available_cats = [(cat, config['weight']) for cat, config in CATEGORY_CONFIG.items() if IMAGE_CACHE.get(cat)]
    if not available_cats:
        return None

    total_weight = sum(w for _, w in available_cats)
    rand = random.randint(1, total_weight)
    cumulative = 0
    chosen_cat = None
    for cat, weight in available_cats:
        cumulative += weight
        if rand <= cumulative:
            chosen_cat = cat
            break

    files = IMAGE_CACHE[chosen_cat]
    file_name = random.choice(files)

    # Защита от повтора
    if user_id and len(files) > 1:
        data = load_data()
        last_card = data.get(user_id, {}).get('last_card')
        if last_card and last_card in files:
            filtered = [f for f in files if f != last_card]
            if filtered:
                file_name = random.choice(filtered)

    config = CATEGORY_CONFIG[chosen_cat]
    return {
        'category': chosen_cat,
        'file_name': file_name,
        'emoji': config['emoji'],
        'text': config['text']
    }

# ------------------- ОБРАБОТЧИКИ -------------------
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        "🎲 Привет! Я гача-бот.\n\n"
        "Команды:\n"
        "/pull — вытянуть карточку (раз в 30 минут)\n"
        "/pack — посмотреть коллекцию\n"
        "/status — время до следующей попытки\n"
        "/refresh — обновить список картинок"
    )

async def status(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = str(update.effective_user.id)
    data = load_data()
    if user_id not in data or 'last_pull' not in data[user_id]:
        await update.message.reply_text("Вы ещё ни разу не тянули! Используйте /pull.")
        return

    last_ts = data[user_id]['last_pull']
    last_time = datetime.fromtimestamp(last_ts)
    next_time = last_time + timedelta(seconds=COOLDOWN_SECONDS)
    now = datetime.now()

    if now >= next_time:
        await update.message.reply_text("✅ Уже можно тянуть! Используйте /pull.")
    else:
        remain = (next_time - now).seconds
        hours = remain // 3600
        minutes = (remain % 3600) // 60
        await update.message.reply_text(f"⏳ Осталось {hours} ч {minutes} мин.")

async def refresh(update: Update, context: ContextTypes.DEFAULT_TYPE):
    refresh_cache()
    await update.message.reply_text("✅ Список картинок обновлён!")

async def pull(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = str(update.effective_user.id)
    now = datetime.now()
    data = load_data()

    if user_id not in data:
        data[user_id] = {'last_pull': 0, 'collection': {}, 'last_card': None}

    # Проверка кулдауна
    last_ts = data[user_id].get('last_pull', 0)
    if last_ts:
        last_time = datetime.fromtimestamp(last_ts)
        if now < last_time + timedelta(seconds=COOLDOWN_SECONDS):
            remain = int((last_time + timedelta(seconds=COOLDOWN_SECONDS) - now).total_seconds())
            hours = remain // 3600
            minutes = (remain % 3600) // 60
            await update.message.reply_text(f"❌ Подожди {hours} ч {minutes} мин!")
            return

    card = get_random_card(user_id)
    if not card:
        await update.message.reply_text("❌ Нет картинок в папке images.")
        return

    file_path = find_image_file(card['file_name'])
    if not file_path:
        await update.message.reply_text(f"❌ Файл {card['file_name']} не найден.")
        return

    # Обновляем данные
    data[user_id]['last_pull'] = now.timestamp()
    collection = data[user_id].get('collection', {})
    collection[card['file_name']] = collection.get(card['file_name'], 0) + 1
    data[user_id]['collection'] = collection
    data[user_id]['last_card'] = card['file_name']

    save_data(data)

    caption = f"{card['emoji']} {card['text']}"
    try:
        with open(file_path, 'rb') as photo:
            await update.message.reply_photo(photo=photo, caption=caption, has_spoiler=True)
    except Exception as e:
        await update.message.reply_text(f"❌ Ошибка отправки: {e}")

async def pack(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = str(update.effective_user.id)
    data = load_data()
    if user_id not in data or not data[user_id].get('collection'):
        await update.message.reply_text("📭 Коллекция пуста. Тяните /pull!")
        return
    await show_card(update, context, user_id, 0)

# ... (остальные функции pack, show_card, pack_callback, backup — оставил без изменений, они работают)

async def backup(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = str(update.effective_user.id)
    if user_id != '5698800851':  # ← Замени на свой ID!
        await update.message.reply_text("❌ Нет прав.")
        return
    backup_file = create_backup("manual")
    if backup_file:
        await update.message.reply_text(f"✅ Бэкап создан: {os.path.basename(backup_file)}")
    else:
        await update.message.reply_text("❌ Не удалось создать бэкап.")

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

    create_backup("startup")  # бэкап при старте
    print("🚀 Бот запущен...")
    app.run_polling()

if __name__ == '__main__':
    main()