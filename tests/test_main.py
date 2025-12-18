import os
import datetime
from dotenv import load_dotenv
import telebot

load_dotenv('../token.env')
TOKEN = os.getenv('TOKEN')
bot = telebot.TeleBot(TOKEN)

expenses = {}
def get_monthly_total(user_id):
    today = datetime.date.today()
    current_month = today.month
    current_year = today.year

    user_expenses = expenses.get(user_id, [])
    monthly = [e['amount'] for e in user_expenses
               if e['date'].month == current_month and e['date'].year == current_year]
    return sum(monthly)

@bot.message_handler(commands=['start'])
def start(message):
    bot.reply_to(message,
                 "Привет! Я бот для учёта месячных трат.\n\n"
                 "Команды:\n"
                 "/add 150.50 — добавить трату\n"
                 "/total — показать сумму за текущий месяц\n"
                 "/clear — очистить все твои траты")

@bot.message_handler(commands=['add'])
def add_expense(message):
    user_id = message.from_user.id
    text = message.text.strip()

    try:
        # Берём число после команды
        amount_str = text.split(maxsplit=1)[1]
        amount = float(amount_str.replace(',', '.'))
        if amount <= 0:
            raise ValueError
    except:
        bot.reply_to(message, "Ошибка! Пример правильной команды:\n/add 299.90")
        return

    today = datetime.date.today()
    if user_id not in expenses:
        expenses[user_id] = []
    expenses[user_id].append({'date': today, 'amount': amount})

    current_total = get_monthly_total(user_id)
    bot.reply_to(message,
                 f"Добавлено {amount} ₽\n"
                 f"Текущая сумма за этот месяц: {current_total} ₽")

# Можно добавлять трату просто отправив число (без команды)
@bot.message_handler(func=lambda m: True)
def add_by_number(message):
    user_id = message.from_user.id
    text = message.text.strip().replace(',', '.')

    try:
        amount = float(text)
        if amount <= 0:
            raise ValueError
    except:
        return  # не число — игнорируем

    today = datetime.date.today()
    if user_id not in expenses:
        expenses[user_id] = []
    expenses[user_id].append({'date': today, 'amount': amount})

    current_total = get_monthly_total(user_id)
    bot.reply_to(message,
                 f"Добавлено {amount} ₽\n"
                 f"Текущая сумма за этот месяц: {current_total} ₽")

@bot.message_handler(commands=['total'])
def total(message):
    user_id = message.from_user.id
    total_sum = get_monthly_total(user_id)
    bot.reply_to(message, f"Ваша ежемесячная трата: {total_sum} ₽")

@bot.message_handler(commands=['clear'])
def clear(message):
    user_id = message.from_user.id
    if user_id in expenses:
        del expenses[user_id]
    bot.reply_to(message, "Все твои траты очищены.")

print("Бот запущен...")
bot.infinity_polling()