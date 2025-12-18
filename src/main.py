import os
import json
from pathlib import Path
from dotenv import load_dotenv
import telebot
from telebot.types import InlineKeyboardMarkup, InlineKeyboardButton, ReplyKeyboardMarkup, KeyboardButton
from telebot.apihelper import ApiTelegramException  # ← Добавлено для обработки ошибки

# Токен бот

BASE_DIR = Path(__file__).parent.parent
TOKEN_PATH = BASE_DIR / 'token.env'
DATA_FILE = BASE_DIR / 'subscriptions.json'

load_dotenv(TOKEN_PATH)
TOKEN = os.getenv('BOT_TOKEN')
if not TOKEN:
    raise ValueError("Токен не найден! Проверь token.env")

bot = telebot.TeleBot(TOKEN)

# Работа с json, кто написал

def load_data() -> dict:
    if DATA_FILE.exists():
        with open(DATA_FILE, 'r', encoding='utf-8') as f:
            return json.load(f)
    return {}

def save_data(data: dict):
    with open(DATA_FILE, 'w', encoding='utf-8') as f:
        json.dump(data, f, ensure_ascii=False, indent=4)

data = load_data()  # {user_id: list[dict]}

def get_subs(user_id: str) -> list:
    return data.setdefault(user_id, [])

def get_total(user_id: str) -> float:
    return sum(sub["amount"] for sub in get_subs(user_id))

# Инициализация кнопок

def main_keyboard() -> ReplyKeyboardMarkup:
    markup = ReplyKeyboardMarkup(resize_keyboard=True, row_width=2)
    markup.add(
        KeyboardButton("📋 Список подписок"),
        KeyboardButton("💰 Общая сумма")
    )
    return markup

def list_keyboard(user_id: str) -> InlineKeyboardMarkup:
    markup = InlineKeyboardMarkup(row_width=1)
    for i, sub in enumerate(get_subs(user_id)):
        markup.add(InlineKeyboardButton(
            f"❌ {sub['name']} — {sub['amount']:.2f} ₽",
            callback_data=f"delete_{i}"
        ))
    markup.add(InlineKeyboardButton("🔄 Обновить", callback_data="refresh"))
    return markup

# Вывод списка

def send_list(chat_id: int, user_id: str, edit_msg=None):
    subs = get_subs(user_id)
    total = get_total(user_id)

    if not subs:
        text = (
            "😔 У тебя пока нет подписок.\n\n"
            "Добавь новую прямо в чате:\n"
            "Название стоимость\n"
            "Пример: Netflix 699"
        )
        markup = None
    else:
        text = "📋 Твои подписки:\n\n"
        for sub in subs:
            text += f"• {sub['name']} — {sub['amount']:.2f} ₽/мес.\n"
        text += f"\n💸 Общая сумма в месяц: {total:.2f} ₽"
        markup = list_keyboard(user_id)

    if edit_msg:
        try:
            bot.edit_message_text(
                chat_id=edit_msg.message.chat.id,
                message_id=edit_msg.message.message_id,
                text=text,
                reply_markup=markup
            )
        except ApiTelegramException as e:
            if "message is not modified" in str(e):
                pass  # Ничего не изменилось — просто игнорируем ошибку
            else:
                raise  # Другая ошибка — пробрасываем дальше
    else:
        bot.send_message(chat_id, text, reply_markup=markup)

# Команды

@bot.message_handler(commands=['start'])
def start(message):
    user_id = str(message.from_user.id)
    get_subs(user_id)  # создаём пустой список при необходимости

    text = (
        "Привет! Я трекер подписок и регулярных трат 💰\n\n"
        "Добавляй подписку текстом:\n"
        "Название стоимость\n\n"
        "Примеры:\n"
        "• Yandex Music 169\n"
        "• Telegram Premium 249.00\n"
        "• Netflix 699,99\n\n"
        "Кнопки управления всегда внизу 👇"
    )
    bot.send_message(message.chat.id, text, reply_markup=main_keyboard())

@bot.message_handler(commands=['total'])
def total(message):
    user_id = str(message.from_user.id)
    total_amount = get_total(user_id)
    text = "Подписки не добавлены. Сумма: 0 ₽" if total_amount == 0 else f"💸 Общая сумма в месяц: {total_amount:.2f} ₽"
    bot.reply_to(message, text)

@bot.message_handler(commands=['list'])
def cmd_list(message):
    send_list(message.chat.id, str(message.from_user.id))

# Нижние кнопки

@bot.message_handler(func=lambda m: m.text == "📋 Список подписок")
def btn_list(message):
    send_list(message.chat.id, str(message.from_user.id))

@bot.message_handler(func=lambda m: m.text == "💰 Общая сумма")
def btn_total(message):
    total(message)

# Список подписок

@bot.message_handler(func=lambda m: True)
def add_subscription(message):
    if message.text in {"📋 Список подписок", "💰 Общая сумма"}:
        return

    user_id = str(message.from_user.id)
    text = message.text.strip()
    parts = text.split()

    if len(parts) < 2:
        bot.reply_to(message, "❌ Формат: Название стоимость\nПример: Spotify 169")
        return

    amount_str = parts[-1].replace(',', '.')
    try:
        amount = float(amount_str)
        if amount <= 0:
            raise ValueError
    except ValueError:
        bot.reply_to(message, "❌ Стоимость — положительное число.")
        return

    name = ' '.join(parts[:-1]).strip()
    if not name:
        bot.reply_to(message, "❌ Укажи название подписки.")
        return

    get_subs(user_id).append({"name": name, "amount": amount})
    save_data(data)

    bot.reply_to(message, f"✅ Добавлено: «{name}» — {amount:.2f} ₽/мес.")
    bot.send_message(message.chat.id, f"💰 Теперь общая сумма: {get_total(user_id):.2f} ₽")

# Callback

@bot.callback_query_handler(func=lambda call: True)
def callback(call):
    user_id = str(call.from_user.id)

    if call.data == "refresh":
        send_list(call.message.chat.id, user_id, edit_msg=call)
        bot.answer_callback_query(call.id)  # Тихо подтверждаем
        return

    if call.data.startswith("delete_"):
        try:
            idx = int(call.data.split("_")[1])
            subs = get_subs(user_id)
            if 0 <= idx < len(subs):
                deleted = subs.pop(idx)
                save_data(data)
                bot.answer_callback_query(call.id, f"Удалено: {deleted['name']}", show_alert=True)
                send_list(call.message.chat.id, user_id, edit_msg=call)
                return
        except:
            pass
        bot.answer_callback_query(call.id, "Ошибка удаления")

print("Бот запущен...")
bot.infinity_polling()