import os
import json
from pathlib import Path
from dotenv import load_dotenv
import telebot

BASE_DIR = Path(__file__).parent.parent  # корень проекта
TOKEN_PATH = BASE_DIR / 'token.env'
DATA_FILE = BASE_DIR / 'subscriptions.json'

load_dotenv(TOKEN_PATH)
TOKEN = os.getenv('BOT_TOKEN')
if not TOKEN:
    raise ValueError("Токен не найден! Проверь token.env")
bot = telebot.TeleBot(TOKEN)


def load_data():
    if DATA_FILE.exists():
        with open(DATA_FILE, 'r', encoding='utf-8') as f:
            return json.load(f)
    return {}

def save_data(data):
    with open(DATA_FILE, 'w', encoding='utf-8') as f:
        json.dump(data, f, ensure_ascii=False, indent=4)

data = load_data()  # {user_id: [{"name": "...", "amount": float}, ...]}

@bot.message_handler(commands=['start'])
def start(message):
    user_id = str(message.from_user.id)
    if user_id not in data:
        data[user_id] = []
        save_data(data)
    text = (
        "Я трекер подписок 💰\n\n"
        "Пиши подписку в формате:\n"
        "Название стоимость\n"
        "Например: YandexDisk 2400\n"
        "Или: Telegram Premium 249.00\n\n"
        "Команды:\n"
        "/total — общая сумма в месяц\n"
        "/list — показать все подписки"
    )
    bot.reply_to(message, text)

@bot.message_handler(commands=['total'])
def total(message):
    user_id = str(message.from_user.id)
    subs = data.get(user_id, [])
    if not subs:
        bot.reply_to(message, "Подписки не добавлены. Сумма: 0 ₽")
        return
    total_amount = sum(sub['amount'] for sub in subs)
    bot.reply_to(message, f"💸 Общая сумма в месяц: {total_amount:.2f} ₽")

@bot.message_handler(commands=['list'])
def list_subscriptions(message):
    user_id = str(message.from_user.id)
    subs = data.get(user_id, [])
    if not subs:
        bot.reply_to(message, "У тебя пока нет подписок.")
        return
    text = "Твои подписки:\n\n"
    for sub in subs:
        text += f"• {sub['name']} — {sub['amount']:.2f} ₽/мес.\n"
    bot.reply_to(message, text)

@bot.message_handler(func=lambda m: True)
def add_subscription(message):
    user_id = str(message.from_user.id)
    if user_id not in data:
        data[user_id] = []

    text = message.text.strip()
    parts = text.split()

    try:
        amount_str = parts[-1]
        amount = float(amount_str.replace(',', '.'))
        name = ' '.join(parts[:-1]).strip()

        if not name:
            raise ValueError

        data[user_id].append({"name": name, "amount": amount})
        save_data(data)
        bot.reply_to(message, f"✅ Добавлено: «{name}» — {amount:.2f} ₽/мес.")

        # Сразу показываем новую общую сумму
        total_amount = sum(sub['amount'] for sub in data[user_id])
        bot.send_message(message.chat.id, f"💰 Теперь общая сумма в месяц: {total_amount:.2f} ₽")

    except ValueError:
        bot.reply_to(message, "❌ Не понял. Пиши в формате: Название стоимость\nПример: Mail.ru Space 2900")

print("Бот запущен...")
bot.infinity_polling()