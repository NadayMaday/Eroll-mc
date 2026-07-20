import os
import json
import random
from datetime import datetime, timedelta
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup, InputMediaPhoto
from telegram.ext import Application, CommandHandler, CallbackQueryHandler, ContextTypes

# ------------------- КОНФИГУРАЦИЯ -------------------
TOKEN = os.environ.get('BOT_TOKEN')
if not TOKEN:
    raise ValueError("Токен не найден! Добавьте переменную BOT_TOKEN.")
IMAGES_DIR = r'C:\Users\lakib\OneDrive\Рабочий стол\telegram_gacha\images'
DATA_FILE = 'gacha_data.json'
COOLDOWN_SECONDS = 2 * 60 * 60

# Конфигурация категорий (без списков файлов — они будут сканироваться)
CATEGORY_CONFIG = {
    'common': {
        'prefix': 'common_',
        'weight': 50,
        'emoji': '💙',
        'text': 'тебе повезло'
    },
    'rare': {
        'prefix': 'rare_',
        'weight': 25,
        'emoji': '💜',
        'text': 'тебе повезло'
    },
    'epic': {
        'prefix': 'epic_',
        'weight': 19,
        'emoji': '❤️',
        'text': 'тебе повезло'
    },
    'legend': {
        'prefix': 'legend_',
        'weight': 5,
        'emoji': '💖',
        'text': 'тебе повезло'
    },
    'porn': {
        'prefix': 'Porn_',
        'weight': 1,
        'emoji': '🖤',
        'text': 'ого! вот это удача'
    }
}

# Глобальный кеш картинок
IMAGE_CACHE = {}

# ------------------- ФУНКЦИИ СКАНИРОВАНИЯ -------------------
def scan_images():
    """Сканирует папку images и возвращает словарь {категория: [список имён без расширения]}"""
    categories = {cat: [] for cat in CATEGORY_CONFIG}
    if not os.path.exists(IMAGES_DIR):
        return categories
    for filename in os.listdir(IMAGES_DIR):
        if not filename.lower().endswith(('.png', '.jpg', '.jpeg')):
            continue
        base, ext = os.path.splitext(filename)
        for cat, config in CATEGORY_CONFIG.items():
            if base.startswith(config['prefix']):
                categories[cat].append(base)
                break
    return categories

def refresh_cache():
    """Обновляет кеш картинок из папки"""
    global IMAGE_CACHE
    IMAGE_CACHE = scan_images()
    print("📂 Кеш обновлён:")
    for cat, files in IMAGE_CACHE.items():
        print(f"  {cat}: {len(files)} файлов")

# При первом импорте заполняем кеш
refresh_cache()

# ------------------- ФУНКЦИИ РАБОТЫ С ДАННЫМИ -------------------
def load_data():
    if os.path.exists(DATA_FILE):
        try:
            with open(DATA_FILE, 'r', encoding='utf-8') as f:
                return json.load(f)
        except (json.JSONDecodeError, OSError):
            return {}
    return {}

def save_data(data):
    with open(DATA_FILE, 'w', encoding='utf-8') as f:
        json.dump(data, f, ensure_ascii=False, indent=2)

# ------------------- ВСПОМОГАТЕЛЬНЫЕ ФУНКЦИИ -------------------
def find_image_file(name):
    """Ищет файл в папке images по имени без расширения"""
    if not os.path.exists(IMAGES_DIR):
        return None
    for filename in os.listdir(IMAGES_DIR):
        base, ext = os.path.splitext(filename)
        if base.lower() == name.lower():
            return os.path.join(IMAGES_DIR, filename)
    return None

def get_random_card():
    """Выбирает случайную карточку из актуального кеша"""
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
    file_name = random.choice(IMAGE_CACHE[chosen_cat])
    config = CATEGORY_CONFIG[chosen_cat]
    return {
        'category': chosen_cat,
        'file_name': file_name,
        'emoji': config['emoji'],
        'text': config['text']
    }

# ------------------- ОБРАБОТЧИКИ КОМАНД -------------------
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        "🎲 Привет! Я гача-бот.\n"
        "Команды:\n"
        "/pull — вытянуть случайную карточку (раз в 2 часа)\n"
        "/pack — посмотреть свою коллекцию\n"
        "/status — узнать, когда можно тянуть снова\n"
        "/refresh — обновить список картинок из папки (если добавили новые)"
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
        await update.message.reply_text(f"⏳ Осталось {hours} ч {minutes} мин до следующего вытягивания.")

async def refresh(update: Update, context: ContextTypes.DEFAULT_TYPE):
    refresh_cache()
    await update.message.reply_text("✅ Список картинок обновлён! Теперь доступны новые файлы.")

async def pull(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = str(update.effective_user.id)
    now = datetime.now()

    data = load_data()
    if user_id not in data:
        data[user_id] = {'last_pull': 0, 'collection': []}

    last_ts = data[user_id].get('last_pull', 0)
    if last_ts:
        last_time = datetime.fromtimestamp(last_ts)
        next_time = last_time + timedelta(seconds=COOLDOWN_SECONDS)
        if now < next_time:
            remain = (next_time - now).seconds
            hours = remain // 3600
            minutes = (remain % 3600) // 60
            await update.message.reply_text(f"❌ Подожди {hours} ч {minutes} мин! Тянуть можно раз в 2 часа.")
            return

    card = get_random_card()
    if not card:
        await update.message.reply_text("❌ В папке images нет ни одной подходящей картинки. Проверьте имена файлов.")
        return

    file_path = find_image_file(card['file_name'])
    if not file_path:
        await update.message.reply_text(f"❌ Файл {card['file_name']} не найден в папке images.")
        return

    data[user_id]['last_pull'] = now.timestamp()
    data[user_id]['collection'].append(card['file_name'])
    save_data(data)

    caption = f"{card['emoji']} {card['text']}"
    with open(file_path, 'rb') as photo:
        await update.message.reply_photo(
            photo=photo,
            caption=caption,
            has_spoiler=True
        )

async def pack(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = str(update.effective_user.id)
    data = load_data()
    if user_id not in data or not data[user_id].get('collection'):
        await update.message.reply_text("📭 Ваша коллекция пуста. Тяните карточки командой /pull!")
        return
    collection = data[user_id]['collection']
    await show_card(update, context, user_id, 0)

async def show_card(update: Update, context: ContextTypes.DEFAULT_TYPE, user_id: str, index: int):
    data = load_data()
    collection = data[user_id]['collection']
    if not collection or index < 0 or index >= len(collection):
        return

    file_name = collection[index]
    file_path = find_image_file(file_name)
    if not file_path:
        await update.message.reply_text(f"❌ Файл {file_name} не найден.")
        return

    # Определяем категорию по префиксу (для отображения смайлика)
    category = None
    for cat, config in CATEGORY_CONFIG.items():
        if file_name.startswith(config['prefix']):
            category = cat
            break
    if category:
        emoji = CATEGORY_CONFIG[category]['emoji']
        text = CATEGORY_CONFIG[category]['text']
        caption = f"{emoji} {text}"
    else:
        caption = "Карточка"

    keyboard = []
    if index > 0:
        keyboard.append(InlineKeyboardButton("◀️ Назад", callback_data=f"pack_{user_id}_{index-1}"))
    if index < len(collection) - 1:
        keyboard.append(InlineKeyboardButton("Вперёд ▶️", callback_data=f"pack_{user_id}_{index+1}"))
    reply_markup = InlineKeyboardMarkup([keyboard]) if keyboard else None

    if update.callback_query is None:
        with open(file_path, 'rb') as photo:
            await update.message.reply_photo(
                photo=photo,
                caption=f"{caption}\n\nКарточка {index+1} из {len(collection)}",
                has_spoiler=True,
                reply_markup=reply_markup
            )
    else:
        query = update.callback_query
        await query.answer()
        media = InputMediaPhoto(open(file_path, 'rb'), caption=f"{caption}\n\nКарточка {index+1} из {len(collection)}", has_spoiler=True)
        await query.edit_message_media(media=media, reply_markup=reply_markup)

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

# ------------------- ЗАПУСК БОТА -------------------
def main():
    app = Application.builder().token(TOKEN).build()
    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("status", status))
    app.add_handler(CommandHandler("refresh", refresh))
    app.add_handler(CommandHandler("pull", pull))
    app.add_handler(CommandHandler("pack", pack))
    app.add_handler(CallbackQueryHandler(pack_callback, pattern="^pack_"))
    print("Бот запущен...")
    app.run_polling()

if __name__ == '__main__':
    main()