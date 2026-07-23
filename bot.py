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
COOLDOWN_SECONDS = 30 * 60

CATEGORY_CONFIG = {
    'common': {'prefix': 'common_', 'weight': 50, 'emoji': '💙', 'text': 'неплохо'},
    'rare':   {'prefix': 'rare_',   'weight': 25, 'emoji': '💜', 'text': 'тебе сегодня везет'},
    'epic':   {'prefix': 'epic_',   'weight': 19, 'emoji': '❤️', 'text': 'тебе повезло'},
    'legend': {'prefix': 'legend_', 'weight': 5,  'emoji': '💖', 'text': 'это твой день, дорогуша'},
    'porn':   {'prefix': 'Porn_',   'weight': 1,  'emoji': '🖤', 'text': 'ого! вот это удача'}
}

IMAGE_CACHE = {}

# ------------------- СКАНИРОВАНИЕ -------------------
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

# ------------------- ДАННЫЕ -------------------
def load_data():
    if os.path.exists(DATA_FILE):
        try:
            with open(DATA_FILE, 'r', encoding='utf-8') as f:
                return json.load(f)
        except Exception as e:
            print(f"❌ Ошибка чтения данных: {e}")
            create_backup("corrupted")
            return {}
    return {}

def save_data(data):
    try:
        create_backup()
        with open(DATA_FILE, 'w', encoding='utf-8') as f:
            json.dump(data, f, ensure_ascii=False, indent=2)
        print("✅ Данные сохранены")
    except Exception as e:
        print(f"❌ Ошибка сохранения: {e}")

def create_backup(prefix="backup"):
    if not os.path.exists(DATA_FILE):
        return None
    timestamp = datetime.now().strftime("%Y-%m-%d_%H-%M-%S")
    backup_name = os.path.join(DATA_DIR, f'gacha_data_{prefix}_{timestamp}.json')
    try:
        shutil.copy2(DATA_FILE, backup_name)
        print(f"✅ Бэкап: {os.path.basename(backup_name)}")
        return backup_name
    except Exception as e:
        print(f"❌ Ошибка бэкапа: {e}")
        return None

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
    chosen_cat = None
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
    return {
        'category': chosen_cat,
        'file_name': file_name,
        'emoji': config['emoji'],
        'text': config['text']
    }

# ------------------- КОМАНДЫ -------------------
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        "🎲 Привет! Я гача-бот.\n\n"
        "/pull — вытянуть карточку\n"
        "/pack — коллекция\n"
        "/status — время до следующей\n"
        "/refresh — обновить картинки"
    )

async def status(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = str(update.effective_user.id)
    data = load_data()
    if user_id not in data or 'last_pull' not in data[user_id]:
        await update.message.reply_text("Вы ещё не тянули. Используйте /pull.")
        return
    last_ts = data[user_id]['last_pull']
    last_time = datetime.fromtimestamp(last_ts)
    next_time = last_time + timedelta(seconds=COOLDOWN_SECONDS)
    now = datetime.now()
    if now >= next_time:
        await update.message.reply_text("✅ Можно тянуть!")
    else:
        remain = int((next_time - now).total_seconds())
        hours = remain // 3600
        minutes = (remain % 3600) // 60
        await update.message.reply_text(f"⏳ Осталось {hours}ч {minutes}м")

async def refresh(update: Update, context: ContextTypes.DEFAULT_TYPE):
    refresh_cache()
    await update.message.reply_text("✅ Картинки обновлены!")

async def pull(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = str(update.effective_user.id)
    now = datetime.now()
    data = load_data()

    if user_id not in data:
        data[user_id] = {'last_pull': 0, 'collection': {}, 'last_card': None}

    last_ts = data[user_id].get('last_pull', 0)
    if last_ts:
        last_time = datetime.fromtimestamp(last_ts)
        if now < last_time + timedelta(seconds=COOLDOWN_SECONDS):
            remain = int((last_time + timedelta(seconds=COOLDOWN_SECONDS) - now).total_seconds())
            hours = remain // 3600
            minutes = (remain % 3600) // 60
            await update.message.reply_text(f"❌ Подожди {hours}ч {minutes}м!")
            return

    card = get_random_card(user_id)
    if not card:
        await update.message.reply_text("❌ Нет картинок.")
        return

    file_path = find_image_file(card['file_name'])
    if not file_path:
        await update.message.reply_text("❌ Файл не найден.")
        return

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
        await update.message.reply_text("Коллекция пуста.")
        return
    await show_card(update, context, user_id, 0)

async def show_card(update: Update, context: ContextTypes.DEFAULT_TYPE, user_id: str, index: int):
    data = load_data()
    collection = data[user_id]['collection']
    items = list(collection.keys())
    if index < 0 or index >= len(items):
        return

    file_name = items[index]
    count = collection[file_name]
    file_path = find_image_file(file_name)
    if not file_path:
        await update.message.reply_text("Файл не найден.")
        return

    category = next((cat for cat, cfg in CATEGORY_CONFIG.items() if file_name.startswith(cfg['prefix'])), None)
    emoji = CATEGORY_CONFIG[category]['emoji'] if category else ""
    text = CATEGORY_CONFIG[category]['text'] if category else ""
    caption = f"{emoji} {text}\n\nКарточка {index+1}/{len(items)} (x{count})"

    keyboard = []
    if index > 0:
        keyboard.append(InlineKeyboardButton("◀️", callback_data=f"pack_{user_id}_{index-1}"))
    if index < len(items) - 1:
        keyboard.append(InlineKeyboardButton("▶️", callback_data=f"pack_{user_id}_{index+1}"))
    reply_markup = InlineKeyboardMarkup([keyboard]) if keyboard else None

    try:
        with open(file_path, 'rb') as f:
            if file_path.lower().endswith('.gif'):
                if update.callback_query:
                    media = InputMediaAnimation(media=f, caption=caption, has_spoiler=True)
                    await update.callback_query.edit_message_media(media=media, reply_markup=reply_markup)
                else:
                    await update.message.reply_animation(animation=f, caption=caption, has_spoiler=True, reply_markup=reply_markup)
            else:
                if update.callback_query:
                    media = InputMediaPhoto(media=f, caption=caption, has_spoiler=True)
                    await update.callback_query.edit_message_media(media=media, reply_markup=reply_markup)
                else:
                    await update.message.reply_photo(photo=f, caption=caption, has_spoiler=True, reply_markup=reply_markup)
    except Exception as e:
        await update.message.reply_text(f"Ошибка: {e}")

async def pack_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    data_parts = query.data.split('_')
    if len(data_parts) == 3 and data_parts[0] == 'pack':
        user_id = data_parts[1]
        index = int(data_parts[2])
        if str(query.from_user.id) != user_id:
            await query.answer("Это не ваша коллекция!", show_alert=True)
            return
        await show_card(update, context, user_id, index)
    await query.answer()

async def backup(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = str(update.effective_user.id)
    if user_id != '5698800851':   # ← Замени на свой Telegram ID
        await update.message.reply_text("Нет прав.")
        return
    backup_file = create_backup("manual")
    if backup_file:
        await update.message.reply_text(f"✅ Бэкап создан!")
    else:
        await update.message.reply_text("❌ Не удалось.")

async def set_commands(app):
    commands = [
        BotCommand("start", "Приветствие"),
        BotCommand("pull", "Вытянуть карточку"),
        BotCommand("pack", "Коллекция"),
        BotCommand("status", "Время кулдауна"),
        BotCommand("refresh", "Обновить картинки"),
        BotCommand("backup", "Бэкап (админ)"),
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