import os
import json
import io
from pathlib import Path
from dotenv import load_dotenv
import telebot
import matplotlib
matplotlib.use('Agg')  # ← обязательно до импорта pyplot, убирает все ошибки Tkinter
import matplotlib.pyplot as plt
from telebot.types import InlineKeyboardMarkup, InlineKeyboardButton, ReplyKeyboardMarkup, KeyboardButton
from telebot.apihelper import ApiTelegramException

# Токен бота
BASE_DIR = Path(__file__).parent.parent
TOKEN_PATH = BASE_DIR / 'token.env'
DATA_FILE = BASE_DIR / 'data.json'
load_dotenv(TOKEN_PATH)
TOKEN = os.getenv('BOT_TOKEN')
if not TOKEN:
    raise ValueError("Токен не найден! Проверь token.env")
bot = telebot.TeleBot(TOKEN)

# Работа с json
def load_data() -> dict:
    if DATA_FILE.exists():
        with open(DATA_FILE, 'r', encoding='utf-8') as f:
            return json.load(f)
    return {}

def save_data():
    with open(DATA_FILE, 'w', encoding='utf-8') as f:
        json.dump(data, f, ensure_ascii=False, indent=4)

data = load_data() # {user_id: {"subscriptions": [], "incomes": []}}

def get_user_data(user_id: str) -> dict:
    if user_id not in data or not isinstance(data[user_id], dict):
        old_subs = data.get(user_id, []) if isinstance(data.get(user_id), list) else []
        data[user_id] = {"subscriptions": old_subs, "incomes": []}
    return data[user_id]

def get_subs(user_id: str) -> list:
    return get_user_data(user_id)["subscriptions"]

def get_incomes(user_id: str) -> list:
    return get_user_data(user_id)["incomes"]

def get_total_expenses(user_id: str) -> float:
    return sum(sub["amount"] for sub in get_subs(user_id))

def get_total_incomes(user_id: str) -> float:
    return sum(inc["amount"] for inc in get_incomes(user_id))

def get_balance(user_id: str) -> float:
    return get_total_incomes(user_id) - get_total_expenses(user_id)

# Клавиатуры
def main_keyboard() -> ReplyKeyboardMarkup:
    markup = ReplyKeyboardMarkup(resize_keyboard=True, row_width=2)
    markup.add(
        KeyboardButton("📋 Подписки"),
        KeyboardButton("📋 Доходы")
    )
    markup.add(
        KeyboardButton("📊 Баланс"),
        KeyboardButton("📈 Графики доходов и трат")
    )
    return markup

def expenses_keyboard(user_id: str) -> InlineKeyboardMarkup:
    markup = InlineKeyboardMarkup(row_width=1)
    for i, sub in enumerate(get_subs(user_id)):
        markup.add(InlineKeyboardButton(
            f"❌ {sub['name']} — {sub['amount']:.2f} ₽",
            callback_data=f"delete_sub_{i}"
        ))
    return markup

def incomes_keyboard(user_id: str) -> InlineKeyboardMarkup:
    markup = InlineKeyboardMarkup(row_width=1)
    for i, inc in enumerate(get_incomes(user_id)):
        markup.add(InlineKeyboardButton(
            f"❌ {inc['name']} — {inc['amount']:.2f} ₽",
            callback_data=f"delete_inc_{i}"
        ))
    return markup

# Два графика в одном изображении
def create_dual_chart(user_id: str):
    subs = get_subs(user_id)
    incs = get_incomes(user_id)
    exp_total = get_total_expenses(user_id)
    inc_total = get_total_incomes(user_id)
    bal = get_balance(user_id)
    emoji = "💚" if bal > 0 else "🔴" if bal < 0 else "😐"

    fig, axs = plt.subplots(1, 2, figsize=(14, 7))

    # Траты
    if subs:
        labels_exp = [sub['name'] for sub in subs]
        sizes_exp = [sub['amount'] for sub in subs]
        axs[0].pie(sizes_exp, labels=labels_exp, autopct='%1.1f%%', startangle=90, textprops={'fontsize': 11})
        axs[0].set_title(f'Траты\n{exp_total:.2f} ₽/мес.', fontsize=14)
    else:
        axs[0].text(0.5, 0.5, 'Нет трат\n😔', ha='center', va='center', fontsize=16, transform=axs[0].transAxes)
        axs[0].set_title('Траты\n0 ₽', fontsize=14)
        axs[0].axis('off')  # чистый фон без осей

    axs[0].axis('equal')

    # Доходы
    if incs:
        labels_inc = [inc['name'] for inc in incs]
        sizes_inc = [inc['amount'] for inc in incs]
        axs[1].pie(sizes_inc, labels=labels_inc, autopct='%1.1f%%', startangle=90, textprops={'fontsize': 11})
        axs[1].set_title(f'Доходы\n{inc_total:.2f} ₽/мес.', fontsize=14)
    else:
        axs[1].text(0.5, 0.5, 'Нет доходов\n😔', ha='center', va='center', fontsize=16, transform=axs[1].transAxes)
        axs[1].set_title('Доходы\n0 ₽', fontsize=14)
        axs[1].axis('off')  # чистый фон без осей

    axs[1].axis('equal')

    fig.suptitle('Месячные доходы и траты', fontsize=18)
    buf = io.BytesIO()
    plt.savefig(buf, format='png', bbox_inches='tight', dpi=200)
    buf.seek(0)
    plt.close(fig)

    caption = (
        f"📈 Диаграммы доходов и трат\n\n"
        f"💸 Расходы: {exp_total:.2f} ₽\n"
        f"💰 Доходы: {inc_total:.2f} ₽\n"
        f"📊 Баланс: {bal:+.2f} ₽ {emoji}"
    )
    return buf, caption

# Вывод списков и итогов
def send_expenses(chat_id: int, user_id: str, edit_msg=None):
    subs = get_subs(user_id)
    total = get_total_expenses(user_id)
    if not subs:
        text = (
            "😔 У тебя пока нет подписок (расходов).\n\n"
            "Добавляй прямо текстом:\n"
            "Название стоимость\n"
            "или Название стоимость/год\n"
            "Пример: Яндекс Плюс 299"
        )
        markup = None
    else:
        text = "📋 Твои подписки (расходы):\n\n"
        for sub in subs:
            text += f"- {sub['name']} — {sub['amount']:.2f} ₽/мес.\n"
        text += f"\n💸 Итого расходов: {total:.2f} ₽"
        markup = expenses_keyboard(user_id)
    if edit_msg:
        try:
            bot.edit_message_text(chat_id=chat_id, message_id=edit_msg.message.message_id, text=text, reply_markup=markup)
        except ApiTelegramException as e:
            if "message is not modified" in str(e):
                pass
            else:
                raise
    else:
        bot.send_message(chat_id, text, reply_markup=markup)

def send_incomes(chat_id: int, user_id: str, edit_msg=None):
    incs = get_incomes(user_id)
    total = get_total_incomes(user_id)
    if not incs:
        text = (
            "😔 У тебя пока нет доходов.\n\n"
            "Добавляй с префиксом + или «Доход »:\n"
            "+ Название стоимость\n"
            "или + Название стоимость/год\n"
            "Пример: + Зарплата 80000"
        )
        markup = None
    else:
        text = "📋 Твои доходы:\n\n"
        for inc in incs:
            text += f"+ {inc['name']} — {inc['amount']:.2f} ₽/мес.\n"
        text += f"\n💰 Итого доходов: {total:.2f} ₽"
        markup = incomes_keyboard(user_id)
    if edit_msg:
        try:
            bot.edit_message_text(chat_id=chat_id, message_id=edit_msg.message.message_id, text=text, reply_markup=markup)
        except ApiTelegramException as e:
            if "message is not modified" in str(e):
                pass
            else:
                raise
    else:
        bot.send_message(chat_id, text, reply_markup=markup)

def send_balance(chat_id: int, user_id: str):
    exp = get_total_expenses(user_id)
    inc = get_total_incomes(user_id)
    bal = get_balance(user_id)
    emoji = "💚" if bal > 0 else "🔴" if bal < 0 else "😐"
    text = (
        f"💰 Доходы: {inc:.2f} ₽\n"
        f"💸 Расходы: {exp:.2f} ₽\n"
        f"📊 Баланс: {bal:+.2f} ₽ {emoji}"
    )
    bot.send_message(chat_id, text)

# Команды
@bot.message_handler(commands=['start'])
def start(message):
    user_id = str(message.from_user.id)
    get_user_data(user_id)
    text = (
        "💰 Я трекер подписок, доходов и баланса\n\n"
        "Добавляй расходы (подписки) просто текстом:\n"
        "Название стоимость ← месячная\n"
        "Название стоимость/год ← годовая (поделится на 12)\n\n"
        "Примеры расходов:\n"
        "-Яндекс Плюс 299\n"
        "-Кинопоиск 499\n"
        "-IVI 399\n"
        "-Метро 20500/год\n\n"
        "Добавляй доходы с префиксом + или «Доход »:\n"
        "+Название стоимость\n"
        "+Название стоимость/год\n\n"
        "Примеры доходов:\n"
        "+Зарплата 80000\n"
        "+Мама отправляет 400\n"
        "+Доход Стипендия 5000\n\n"
        "Кнопки всегда внизу 👇"
    )
    bot.send_message(message.chat.id, text, reply_markup=main_keyboard())

# Кнопки
@bot.message_handler(func=lambda m: m.text == "📋 Подписки")
def btn_expenses(message):
    send_expenses(message.chat.id, str(message.from_user.id))

@bot.message_handler(func=lambda m: m.text == "📋 Доходы")
def btn_incomes(message):
    send_incomes(message.chat.id, str(message.from_user.id))

@bot.message_handler(func=lambda m: m.text == "📊 Баланс")
def btn_balance(message):
    send_balance(message.chat.id, str(message.from_user.id))

@bot.message_handler(func=lambda m: m.text == "📈 Графики доходов и трат")
def btn_chart(message):
    user_id = str(message.from_user.id)
    img, caption = create_dual_chart(user_id)
    bot.send_photo(message.chat.id, img, caption=caption)

# Добавление доходов/расходов
@bot.message_handler(func=lambda m: True)
def add_entry(message):
    if message.text in {"📋 Подписки", "📋 Доходы", "📊 Баланс", "📈 Графики доходов и трат"}:
        return
    user_id = str(message.from_user.id)
    original_text = message.text.strip()
    text = original_text
    is_income = False
    if text.startswith("+"):
        text = text[1:].strip()
        is_income = True
    elif text.lower().startswith("доход "):
        text = text[6:].strip()
        is_income = True
    parts = text.split()
    if len(parts) < 2:
        bot.reply_to(message, "❌ Формат: [+] Название стоимость\nили [+] Название стоимость/год\nПример: + Зарплата 80000")
        return
    raw_amount = parts[-1]
    name = ' '.join(parts[:-1]).strip()
    if not name:
        bot.reply_to(message, "❌ Укажи название.")
        return
    try:
        extra_info = ""
        if '/' in raw_amount:
            cost_str, period = raw_amount.split('/', 1)
            cost = float(cost_str.replace(',', '.'))
            period = period.strip().lower()
            if period in ["год", "г", "y", "year", "annual"]:
                amount = round(cost / 12, 2)
                extra_info = f" (из годовой {cost:.2f} ₽)"
            elif period in ["месяц", "мес", "м", "month"]:
                amount = round(cost, 2)
            else:
                raise ValueError
        else:
            amount = round(float(raw_amount.replace(',', '.')), 2)
        if amount <= 0:
            raise ValueError
    except ValueError:
        bot.reply_to(message, "❌ Стоимость — положительное число (1234.56 или 1234,56 или 83988/год)")
        return
    if is_income:
        get_incomes(user_id).append({"name": name, "amount": amount})
        category = "доход"
    else:
        get_subs(user_id).append({"name": name, "amount": amount})
        category = "подписка"
    save_data()
    bot.reply_to(message, f"✅ Добавлено {category}: «{name}» — {amount:.2f} ₽/мес.{extra_info}")
    exp = get_total_expenses(user_id)
    inc = get_total_incomes(user_id)
    bal = get_balance(user_id)
    emoji = "💚" if bal > 0 else "🔴" if bal < 0 else "😐"
    bot.send_message(message.chat.id,
                     f"💸 Расходы: {exp:.2f} ₽\n"
                     f"💰 Доходы: {inc:.2f} ₽\n"
                     f"📊 Баланс: {bal:+.2f} ₽ {emoji}")

# Callback (удаление)
@bot.callback_query_handler(func=lambda call: True)
def callback(call):
    user_id = str(call.from_user.id)
    if call.data.startswith("delete_sub_"):
        try:
            idx = int(call.data.split("_")[-1])
            subs = get_subs(user_id)
            if 0 <= idx < len(subs):
                deleted = subs.pop(idx)
                save_data()
                bot.answer_callback_query(call.id, f"Удалена подписка: {deleted['name']}", show_alert=True)
                send_expenses(call.message.chat.id, user_id, edit_msg=call)
                return
        except:
            pass
    elif call.data.startswith("delete_inc_"):
        try:
            idx = int(call.data.split("_")[-1])
            incs = get_incomes(user_id)
            if 0 <= idx < len(incs):
                deleted = incs.pop(idx)
                save_data()
                bot.answer_callback_query(call.id, f"Удалён доход: {deleted['name']}", show_alert=True)
                send_incomes(call.message.chat.id, user_id, edit_msg=call)
                return
        except:
            pass
    bot.answer_callback_query(call.id, "Ошибка удаления")

print("Бот запущен...")
bot.infinity_polling()