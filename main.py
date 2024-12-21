import telebot
from telebot.types import InlineKeyboardMarkup, InlineKeyboardButton, InputMediaPhoto
import threading
import time
import csv
from io import StringIO
import os
import atexit
from telebot import apihelper
from datetime import datetime
from zoneinfo import ZoneInfo
import sqlite3
import logging
import hashlib
import hmac
import requests
import json
import urllib.parse
from fastapi import FastAPI, Form, Header, HTTPException, Request
import uvicorn
from fastapi.responses import JSONResponse
import httpx
import uuid


# Настройка логирования
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')


# Получаем путь к текущей директории скрипта
script_dir = os.path.dirname(os.path.abspath(__file__))
DB_FILE = os.path.join(script_dir, 'bot_database.db')
TEMP_PHOTO_DIR = os.path.join(script_dir, 'temp_photos')

# Создаём временную директорию для хранения фотографий, если она не существует
os.makedirs(TEMP_PHOTO_DIR, exist_ok=True)

TOKEN = '7177665959:AAF5WkUoLg7oZty0XocusW6kDDCUeBd8pww'  # Замените на ваш токен
bot = telebot.TeleBot(TOKEN)
app = FastAPI()
secret_key = '0118af80a1a25a7ec35edb78b4c7f743f72b8991aee68927add8d07e41e6a5f6'

# Получаем информацию о боте
try:
    bot_info = bot.get_me()
    bot_id = bot_info.id
except Exception as e:
    logging.error(f"Не удалось получить информацию о боте: {e}")
    bot_id = None

# Словарь для хранения данных пользователя (состояния)
user_data = {}

# Список ID администраторов (замените на реальные Telegram user IDs)
ADMIN_IDS = []  # Пример: [111111111, 222222222]

app = FastAPI()

@app.post("/telegram")
async def telegram_webhook(request: Request):
    try:
        json_str = await request.json()
        update = telebot.types.Update.de_json(json_str)
        bot.process_new_updates([update])
        return {"ok": True}
    except Exception as e:
        logging.error(f"Ошибка при обработке Webhook: {e}")
        raise HTTPException(status_code=400, detail="Invalid request")

def set_webhook():
    url = f"https://api.telegram.org/bot{TOKEN}/setWebhook"
    webhook_url = "https://ilkbv2909.onrender.com/telegram"  # Убедитесь, что этот URL правильный
    response = requests.post(url, data={"url": webhook_url})
    if response.status_code == 200:
        print("Webhook установлен успешно.")
    else:
        print("Ошибка при установке Webhook:", response.text)

set_webhook()

@bot.message_handler(commands=['manya'])
def send_welcome(message):
    bot.reply_to(message, "Добро пожаловать!")

@app.post("/")
async def process_webhook(
    transaction_id: str = Form(...),
    amount: float = Form(...),
    currency: str = Form(...),
    status: str = Form(...)
):
    # Логика обработки
    return {"message": "Webhook processed successfully"}

@app.get("/")
async def root():
    return {"message": "Hello, World!"}

# Создание базы данных и таблицы
def create_database():
    with sqlite3.connect('orders.db') as conn:
        cursor = conn.cursor()
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS orders (
                order_id TEXT PRIMARY KEY,
                user_id TEXT NOT NULL
            )
        ''')
        conn.commit()

create_database()

# Инициализация базы данных
def init_db():
    with sqlite3.connect(DB_FILE) as conn:
        cursor = conn.cursor()
        # Создаём таблицу пользователей, если она не существует
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS users (
                id INTEGER PRIMARY KEY,
                username TEXT,
                start_time TEXT
            )
        ''')
        # Создаём таблицу статистики кнопок
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS button_presses (
                button_name TEXT PRIMARY KEY,
                count INTEGER DEFAULT 0
            )
        ''')
        # Создаём таблицу для общей статистики
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS stats (
                key TEXT PRIMARY KEY,
                value TEXT
            )
        ''')
        # Инициализируем кнопки в button_presses, если они ещё не добавлены
        buttons = [
            '🎁Расшифровки тут🎁',
            '👉🏻Узнать о себе👈🏻',
            '🙋‍♀️Обо мне',
            'Экзамен года',
            'Что меня ждет?',
            'Сферы реализации',
            'Через что придут деньги',
            '✍️ Создать пост',
            '📊 Статистика',
            'Матрица года',
            'Личный бренд'
            # Добавьте остальные кнопки по мере необходимости
        ]
        for button in buttons:
            cursor.execute('INSERT OR IGNORE INTO button_presses (button_name, count) VALUES (?, ?)', (button, 0))
        # Инициализируем users_started, если ещё не существует
        cursor.execute('INSERT OR IGNORE INTO stats (key, value) VALUES (?, ?)', ('users_started', '0'))
        conn.commit()
        logging.info("База данных инициализирована.")

init_db()

# Функции для работы с базой данных
def add_user(user_id, username, start_time):
    with sqlite3.connect(DB_FILE) as conn:
        cursor = conn.cursor()
        cursor.execute('INSERT OR IGNORE INTO users (id, username, start_time) VALUES (?, ?, ?)',
                       (user_id, username, start_time))
        conn.commit()
        logging.info(f"Пользователь {user_id} добавлен в базу данных.")

def get_all_users():
    with sqlite3.connect(DB_FILE) as conn:
        cursor = conn.cursor()
        cursor.execute('SELECT id, username, start_time FROM users ORDER BY start_time ASC')
        return cursor.fetchall()

def remove_user(user_id):
    with sqlite3.connect(DB_FILE) as conn:
        cursor = conn.cursor()
        cursor.execute('DELETE FROM users WHERE id = ?', (user_id,))
        conn.commit()
        logging.info(f"Пользователь {user_id} удалён из базы данных.")

def user_exists(user_id):
    with sqlite3.connect(DB_FILE) as conn:
        cursor = conn.cursor()
        cursor.execute('SELECT 1 FROM users WHERE id = ?', (user_id,))
        return cursor.fetchone() is not None

def increment_button_press(button_name):
    with sqlite3.connect(DB_FILE) as conn:
        cursor = conn.cursor()
        cursor.execute('UPDATE button_presses SET count = count + 1 WHERE button_name = ?', (button_name,))
        conn.commit()
        logging.info(f"Кнопка '{button_name}' нажата. Счётчик увеличен.")

def get_button_press_count(button_name):
    with sqlite3.connect(DB_FILE) as conn:
        cursor = conn.cursor()
        cursor.execute('SELECT count FROM button_presses WHERE button_name = ?', (button_name,))
        result = cursor.fetchone()
        return result[0] if result else 0

def get_users_started():
    with sqlite3.connect(DB_FILE) as conn:
        cursor = conn.cursor()
        cursor.execute('SELECT value FROM stats WHERE key = ?', ('users_started',))
        result = cursor.fetchone()
        return int(result[0]) if result else 0

def increment_users_started():
    with sqlite3.connect(DB_FILE) as conn:
        cursor = conn.cursor()
        cursor.execute('UPDATE stats SET value = value + 1 WHERE key = ?', ('users_started',))
        conn.commit()
        logging.info("Счётчик users_started увеличен.")

# Вспомогательная функция для получения названия кнопки
def button_name(data):
    mapping = {
        'ya_iz_instagram': "🎁Расшифровки тут🎁",
        'moi_produkti': "👉🏻Узнать о себе👈🏻",
        'obo_mne': "🙋‍♀️Обо мне",
        'matrix_year': "Матрица года",
        'Lichnyi_brend': "Личный бренд",  # Добавлено для ясности
        # Добавьте остальные кнопки по мере необходимости
    }
    return mapping.get(data, data)

# Главное меню с кнопками
def main_menu(chat_id):
    markup = InlineKeyboardMarkup()
    markup.add(InlineKeyboardButton("🎁Расшифровки тут🎁", callback_data='ya_iz_instagram'))
    markup.add(InlineKeyboardButton("👉🏻Узнать о себе👈🏻", callback_data='moi_produkti'))
    if chat_id in ADMIN_IDS:
        markup.add(InlineKeyboardButton("🔧 Админ меню", callback_data='admin_menu'))
    return markup

# Функция создания админского меню
def admin_menu_markup():
    markup = InlineKeyboardMarkup()
    markup.add(InlineKeyboardButton("✍️ Создать пост", callback_data='create_post'))
    markup.add(InlineKeyboardButton("📊 Статистика", callback_data='admin_statistika'))
    markup.add(InlineKeyboardButton("Выгрузить всех пользователей", callback_data='admin_export_users'))
    markup.add(InlineKeyboardButton("Анализ кнопок", callback_data='admin_analyze_buttons'))
    markup.add(InlineKeyboardButton("⬅️ Назад", callback_data='back_to_main'))
    return markup

# Функция создания меню запроса изображения
def admin_image_prompt_menu():
    markup = InlineKeyboardMarkup()
    markup.add(InlineKeyboardButton("Добавить изображение", callback_data='admin_add_image'))
    markup.add(InlineKeyboardButton("Пропустить", callback_data='admin_skip_image'))
    markup.add(InlineKeyboardButton("⬅️ Назад", callback_data='admin_back'))
    return markup

# Функция создания меню для отмены или возврата
def admin_back_cancel_menu():
    markup = InlineKeyboardMarkup()
    markup.add(InlineKeyboardButton("⬅️ Назад", callback_data='admin_back'))
    markup.add(InlineKeyboardButton("❌ Отменить", callback_data='admin_cancel'))
    return markup

# Функция создания меню подтверждения публикации
def admin_publish_confirmation_menu():
    markup = InlineKeyboardMarkup()
    markup.add(InlineKeyboardButton("Опубликовать", callback_data='admin_confirm_publish'))
    markup.add(InlineKeyboardButton("Отменить создание публикации", callback_data='admin_cancel_publish'))
    return markup

# Функция создания меню Да/Нет
def admin_yes_no_menu():
    markup = InlineKeyboardMarkup()
    markup.add(InlineKeyboardButton("Да", callback_data='admin_yes_add_button'))
    markup.add(InlineKeyboardButton("Нет", callback_data='admin_no_add_button'))
    return markup

# Функция создания меню подтверждения экспорта пользователей
def export_users_confirmation_menu():
    markup = InlineKeyboardMarkup()
    markup.add(InlineKeyboardButton("Экспортировать", callback_data='admin_confirm_export_yes'))
    markup.add(InlineKeyboardButton("Отмена", callback_data='admin_confirm_export_no'))
    return markup

# Функция для сохранения заказа
def save_order(order_id, user_id):
    with sqlite3.connect('orders.db') as conn:
        cursor = conn.cursor()
        cursor.execute('INSERT INTO orders (order_id, user_id) VALUES (?, ?)', (order_id, user_id))
        conn.commit()

# Генерация уникального order_id
def generate_unique_order_id():
    return str(uuid.uuid4())

# Извлечение всех заказов
def fetch_orders():
    with sqlite3.connect('orders.db') as conn:
        cursor = conn.cursor()
        cursor.execute('SELECT order_id, user_id FROM orders')
        return cursor.fetchall()

# Проверка подписи
def verify_signature(data: dict, signature: str) -> bool:
    message = ''.join(f"{key}={value}" for key, value in sorted(data.items()))
    calculated_signature = hmac.new(
        secret_key.encode('utf-8'),
        msg=message.encode('utf-8'),
        digestmod=hashlib.sha256
    ).hexdigest()
    return hmac.compare_digest(calculated_signature, signature)

# Получение user_id по order_id
def get_user_id_by_order_id(order_id):
    with sqlite3.connect('orders.db') as conn:
        cursor = conn.cursor()
        cursor.execute('SELECT user_id FROM orders WHERE order_id = ?', (order_id,))
        result = cursor.fetchone()
        return result[0] if result else None

@app.post("/")
async def process_payment_notification(
    date: str = Form(...),
    order_id: str = Form(...),
    order_num: str = Form(...),
    domain: str = Form(...),
    sum: str = Form(...),
    currency: str = Form(...),
    customer_phone: str = Form(...),
    customer_email: str = Form(...),
    customer_extra: str = Form(...),
    payment_type: str = Form(...),
    commission: str = Form(...),
    commission_sum: str = Form(...),
    attempt: str = Form(...),
    payment_status: str = Form(...),
    payment_status_description: str = Form(...),
    payment_init: str = Form(...),
    products_0_name: str = Form(...),
    products_0_price: str = Form(...),
    products_0_quantity: str = Form(...),
    products_0_sum: str = Form(...)
):
    try:
        logging.info("Received webhook data")

        # Подключение к базе данных SQLite
        with sqlite3.connect('orders.db') as conn:
            cursor = conn.cursor()

        # Поиск заказа по order_id
        cursor.execute("SELECT id, telegram_user_id FROM orders WHERE order_id = ?", (order_id,))
        order = cursor.fetchone()

        if not order:
            logging.error("Order ID not found in database")
            raise HTTPException(status_code=404, detail="Order ID not found")

        order_db_id, telegram_user_id = order

        # Проверка статуса оплаты
        if payment_status == "success":
            # Отправка сообщения в Telegram
            message = f"Оплата прошла успешно для заказа с ID: {order_id}"
            bot.send_message(chat_id=telegram_user_id, text=message)

        return {"status": "success"}
    except Exception as e:
        logging.error(f"Error processing payment notification: {e}")
        raise HTTPException(status_code=500, detail="Internal Server Error")
    finally:
        conn.close()

def create_payment_link(product_name, price, quantity,order_id):
    secret_key = '0118af80a1a25a7ec35edb78b4c7f743f72b8991aee68927add8d07e41e6a5f6'
    link_to_form = 'https://daryasunshine.payform.ru'

    # Генерация уникального order_id
    order_id = generate_unique_order_id()

    order_data = {
        'order_id': order_id,
        'customer_phone': '+79998887755',  # Замените на реальные данные
        'customer_email': 'user@example.com',  # Замените на реальные данные
        'products': [
            {
                'name': product_name,
                'price': 50.00,
                'quantity': 1,
            }
        ],
        'customer_extra': 'Полная оплата курса',
        'do': 'pay',
    }

    params = {
        'order_id': order_data['order_id'],
        'customer_phone': order_data['customer_phone'],
        'customer_email': order_data['customer_email'],
        'customer_extra': order_data['customer_extra'],
        'do': order_data['do'],
    }

    for idx, product in enumerate(order_data['products']):
        params[f'products[{idx}][name]'] = product['name']
        params[f'products[{idx}][price]'] = product['price']
        params[f'products[{idx}][quantity]'] = product['quantity']

    sorted_params = sorted(params.items())
    encoded_params = urllib.parse.urlencode(sorted_params)
    signature = hmac.new(secret_key.encode(), encoded_params.encode(), hashlib.sha256).hexdigest()
    payment_url = f'{link_to_form}?{encoded_params}&sign={signature}'

    return payment_url

    # Обработчик команды /buy
@bot.message_handler(commands=['buy'])
def buy(message):
        user_id = message.chat.id  # Используем chat.id как user_id
        try:
            product_name = 'Авторское пособие «Личный бренд»'
            price = 50.00
            quantity = 1

            # Сохраняем order_id и user_id в базе данных
            order_id = generate_unique_order_id()
            save_order(order_id, str(user_id))

            # Формируем ссылку на оплату
            payment_link = create_payment_link(order_id,product_name, price, quantity)

            # Отправляем пользователю ссылку на оплату
            bot.send_message(user_id, f"Ссылка на оплату: {payment_link}")
            logging.info(f"Payment link sent to user {user_id}: {payment_link}")
        except Exception as e:
            logging.error(f"Error processing buy command for user {user_id}: {e}")
            bot.send_message(user_id, "Произошла ошибка при обработке вашего запроса. Пожалуйста, попробуйте позже.")


# Обработчик команды /show_orders
@bot.message_handler(commands=['show_orders'])
def show_orders(message):
    orders = fetch_orders()
    if not orders:
        response = "Заказы отсутствуют."
    else:
        response = "Список заказов:\n"
        for order_id, user_id in orders:
            response += f"Order ID: {order_id}, User ID: {user_id}\n"
    bot.send_message(message.chat.id, response)

# Обработчик команды /start
@bot.message_handler(commands=['start'])
def send_welcome(message):
    chat_id = message.chat.id
    # Проверяем, есть ли предыдущее сообщение для редактирования
    if chat_id in user_data and 'last_message_id' in user_data[chat_id]:
        try:
            photo_url = 'https://i.imgur.com/your-koala-image.jpg'  # Замените на актуальный URL изображения
            welcome_text = """Привет! 🤎
На связи Дарина, нумеролог и специалист по Матрице Судьбы — методу, который помогает глубже понять себя, работать с энергиями и осознанно подходить к жизни.

Здесь ты найдёшь:

• материалы для самопознания,
• полезные инструменты для гармонизации энергий,
• доступ к моим курсам и платным продуктам,
• вдохновение и поддержку на пути к лучшей версии себя."""

            # Создаём объект InputMediaPhoto
            media = InputMediaPhoto(media=photo_url, caption=welcome_text)

            # Редактируем сообщение
            bot.edit_message_media(
                media=media,
                chat_id=chat_id,
                message_id=user_data[chat_id]['last_message_id'],
                reply_markup=main_menu(chat_id)
            )
            user_data[chat_id]['state'] = 'main_menu'
        except Exception as e:
            logging.warning(f"Не удалось отредактировать предыдущее сообщение: {e}")
            # Если редактирование не удалось, отправляем новое сообщение
            photo_url = 'https://i.imgur.com/your-koala-image.jpg'  # Замените на актуальный URL изображения
            welcome_text = """Привет! 🤎
На связи Дарина, нумеролог и специалист по Матрице Судьбы — методу, который помогает глубже понять себя, работать с энергиями и осознанно подходить к жизни.

Здесь ты найдёшь:

• материалы для самопознания,
• полезные инструменты для гармонизации энергий,
• доступ к моим курсам и платным продуктам,
• вдохновение и поддержку на пути к лучшей версии себя."""
            sent = bot.send_photo(
                chat_id,
                photo=photo_url,
                caption=welcome_text,
                reply_markup=main_menu(chat_id)  # Передаём chat_id для определения админа
            )
            user_data[chat_id] = {
                'last_message_id': sent.message_id,
                'state': 'main_menu',
                'last_activity': time.time(),
                'post_creation_messages': []  # Для отслеживания сообщений при создании поста
            }
    else:
        # Отправляем первое сообщение
        photo_url = 'https://i.imgur.com/your-koala-image.jpg'  # Замените на актуальный URL изображения
        welcome_text = """Привет! 🤎
На связи Дарина, нумеролог и специалист по Матрице Судьбы — методу, который помогает глубже понять себя, работать с энергиями и осознанно подходить к жизни.

Здесь ты найдёшь:

• материалы для самопознания,
• полезные инструменты для гармонизации энергий,
• доступ к моим курсам и платным продуктам,
• вдохновение и поддержку на пути к лучшей версии себя."""

        sent = bot.send_photo(
            chat_id,
            photo=photo_url,
            caption=welcome_text,
            reply_markup=main_menu(chat_id)  # Передаём chat_id для определения админа
        )
        user_data[chat_id] = {
            'last_message_id': sent.message_id,
            'state': 'main_menu',
            'last_activity': time.time(),
            'post_creation_messages': []  # Для отслеживания сообщений при создании поста
        }

    # Увеличиваем счетчик запустивших бота пользователей
    increment_users_started()

    # Добавляем пользователя в базу, если его нет и он не бот
    if bot_id and message.from_user.id != bot_id and not user_exists(chat_id):
        # Получаем текущее время в МСК
        start_time = datetime.now(ZoneInfo('Europe/Moscow')).strftime('%H:%M/%d.%m.%Y')
        username = message.from_user.username or 'Нет ника'
        add_user(chat_id, username, start_time)

# Функция для отправки главного меню как нового сообщения
def send_main_menu_message(chat_id):
    photo_url = 'https://i.imgur.com/6gEYdAP.jpg'  # Замените на актуальный URL изображения
    welcome_text = """Привет! 🤎
На связи Дарина, нумеролог и специалист по Матрице Судьбы — методу, который помогает глубже понять себя, работать с энергиями и осознанно подходить к жизни.

Здесь ты найдёшь:

• материалы для самопознания,
• полезные инструменты для гармонизации энергий,
• доступ к моим курсам и платным продуктам,
• вдохновение и поддержку на пути к лучшей версии себя."""
    try:
        sent = bot.send_photo(
            chat_id,
            photo=photo_url,
            caption=welcome_text,
            reply_markup=main_menu(chat_id)  # Передаём chat_id для определения админа
        )
        # Обновляем данные пользователя
        user_data[chat_id] = {
            'last_message_id': sent.message_id,
            'state': 'main_menu',
            'last_activity': time.time(),
            'post_creation_messages': []
        }
    except Exception as e:
        logging.error(f"Не удалось отправить главное меню: {e}")

# Обработка нажатий кнопок
@bot.callback_query_handler(func=lambda call: True)
def callback_inline(call):
    chat_id = call.message.chat.id

    # Инициализируем данные пользователя, если их нет
    if chat_id not in user_data:
        user_data[chat_id] = {
            'last_message_id': None,
            'state': None,
            'last_activity': time.time(),
            'post_creation_messages': []
        }

    # Обновляем время последней активности
    user_data[chat_id]['last_activity'] = time.time()

    # Обработка пользовательских кнопок
    if call.data == 'ya_iz_instagram':
        photo_url = 'https://i.imgur.com/BVxe0d9.jpg'  # Замените на актуальный URL изображения
        text = """Если ты здесь, значит, ты из моего Instagram🤎 

Ты чувствуешь, что пора что-то менять? Может быть, хочется глубже понять себя, улучшить отношения или наконец-то разобраться с тем, что тебя тормозит? Тогда ты попала в нужное место.

Здесь я собрала для тебя бесплатные материалы, которые помогут сделать первый шаг!

Давай начнем вместе! Это только первый шаг, но он уже ведёт к твоим переменам.

Просто выбери, что тебе интересно, на кнопках ниже:"""

        keyboard = InlineKeyboardMarkup()
        keyboard.add(InlineKeyboardButton("Экзамен года", callback_data='Экзамен года'))
        keyboard.add(InlineKeyboardButton("Что меня ждет?", callback_data='Что меня ждет?'))
        keyboard.add(InlineKeyboardButton("Сферы реализации", callback_data='Сферы реализации'))
        keyboard.add(InlineKeyboardButton("Через что придут деньги", callback_data='Через что придут деньги'))
        keyboard.add(InlineKeyboardButton("Для чего встретились?", url='https://t.me/daryaasunshine/1110'))
        keyboard.add(InlineKeyboardButton("⬅️ Назад", callback_data='back_to_main'))

        try:
            bot.edit_message_media(
                media=InputMediaPhoto(media=photo_url, caption=text),
                chat_id=chat_id,
                message_id=call.message.message_id,
                reply_markup=keyboard
            )
            user_data[chat_id]['state'] = 'ya_iz_instagram'
        except Exception as e:
            logging.warning(f"Не удалось отредактировать сообщение: {e}")
            # Если не удалось отредактировать, отправляем новое сообщение
            sent = bot.send_photo(
                chat_id,
                photo=photo_url,
                caption=text,
                reply_markup=keyboard
            )
            user_data[chat_id]['post_creation_messages'].append(sent.message_id)
            user_data[chat_id]['last_message_id'] = sent.message_id
            user_data[chat_id]['state'] = 'ya_iz_instagram'

        # Увеличиваем счетчик нажатий на кнопку "🎁Расшифровки тут🎁"
        increment_button_press('🎁Расшифровки тут🎁')

    elif call.data == 'Экзамен года':
        photo_url = 'https://i.imgur.com/dQnKT00.jpg'  # Замените на актуальный URL изображения
        text = """Каждый год жизни приносит не только новые возможности, но и важные уроки — это и есть «экзамен года». Он помогает понять, над чем важно работать, какие качества развивать и какие вызовы могут ожидать.

Задача экзамена года — научиться справляться с трудностями, трансформировать слабости в силу и выйти на новый уровень в понимании себя и своей жизни.

Нажимай кнопку ниже, чтобы узнать, какой экзамен ждёт тебя в этом году, и получи рекомендации, как пройти его с гармонией и уверенностью"""

        keyboard = InlineKeyboardMarkup()
        keyboard.add(InlineKeyboardButton("Узнать", url="https://t.me/daryaasunshine/1057"))
        keyboard.add(InlineKeyboardButton("⬅️ Назад", callback_data='ya_iz_instagram'))

        try:
            bot.edit_message_media(
                media=InputMediaPhoto(media=photo_url, caption=text),
                chat_id=chat_id,
                message_id=call.message.message_id,
                reply_markup=keyboard
            )
            user_data[chat_id]['state'] = 'exam_year'
        except Exception as e:
            logging.warning(f"Не удалось отредактировать сообщение: {e}")
            sent = bot.send_photo(
                chat_id,
                photo=photo_url,
                caption=text,
                reply_markup=keyboard
            )
            user_data[chat_id]['post_creation_messages'].append(sent.message_id)
            user_data[chat_id]['last_message_id'] = sent.message_id
            user_data[chat_id]['state'] = 'exam_year'

        # Увеличиваем счетчик нажатий на кнопку "Экзамен года"
        increment_button_press('Экзамен года')

    elif call.data == 'Что меня ждет?':
        photo_url = 'https://i.imgur.com/mDKjVCx.jpg'  # Замените на актуальный URL изображения
        text = """Каждый год жизни связан с определённой энергией, которая влияет на наши события, решения и внутренний рост. Матрица Судьбы помогает увидеть, какие возможности открываются перед тобой, и понять, как гармонично пройти этот период.

Узнай, какая энергия определяет твой год, и получи рекомендации, чтобы направить её в плюс. 

Готова заглянуть в своё будущее?

Жми на кнопку ниже и открывай для себя новые горизонты!"""

        keyboard = InlineKeyboardMarkup()
        keyboard.add(InlineKeyboardButton("Узнать", url="https://t.me/daryaasunshine/177"))
        keyboard.add(InlineKeyboardButton("⬅️ Назад", callback_data='ya_iz_instagram'))

        try:
            bot.edit_message_media(
                media=InputMediaPhoto(media=photo_url, caption=text),
                chat_id=chat_id,
                message_id=call.message.message_id,
                reply_markup=keyboard
            )
            user_data[chat_id]['state'] = 'what_awaits'
        except Exception as e:
            logging.warning(f"Не удалось отредактировать сообщение: {e}")
            sent = bot.send_photo(
                chat_id,
                photo=photo_url,
                caption=text,
                reply_markup=keyboard
            )
            user_data[chat_id]['post_creation_messages'].append(sent.message_id)
            user_data[chat_id]['last_message_id'] = sent.message_id
            user_data[chat_id]['state'] = 'what_awaits'

        # Увеличиваем счетчик нажатий на кнопку "Что меня ждет?"
        increment_button_press('Что меня ждет?')

    elif call.data == 'Сферы реализации':
        photo_url = 'https://i.imgur.com/xbHOeSI.jpg'  # Замените на актуальный URL изображения
        text = """Каждая энергия в Матрице Судьбы определяет не только наши сильные стороны, но и направления, в которых мы можем достичь успеха и гармонии.

Узнай свою энергию и открой подходящие для себя сферы работы, творчества или бизнеса. Матрица Судьбы покажет, где ты можешь раскрыть свой потенциал, используя свои сильные стороны и таланты.

Начни своё путешествие прямо сейчас: нажимай кнопку ниже и узнай, как реализовать себя максимально эффективно!"""

        keyboard = InlineKeyboardMarkup()
        keyboard.add(InlineKeyboardButton("Узнать", url="https://t.me/daryaasunshine/498"))
        keyboard.add(InlineKeyboardButton("⬅️ Назад", callback_data='ya_iz_instagram'))

        try:
            bot.edit_message_media(
                media=InputMediaPhoto(media=photo_url, caption=text),
                chat_id=chat_id,
                message_id=call.message.message_id,
                reply_markup=keyboard
            )
            user_data[chat_id]['state'] = 'realization_spheres'
        except Exception as e:
            logging.warning(f"Не удалось отредактировать сообщение: {e}")
            sent = bot.send_photo(
                chat_id,
                photo=photo_url,
                caption=text,
                reply_markup=keyboard
            )
            user_data[chat_id]['post_creation_messages'].append(sent.message_id)
            user_data[chat_id]['last_message_id'] = sent.message_id
            user_data[chat_id]['state'] = 'realization_spheres'

        # Увеличиваем счетчик нажатий на кнопку "Сферы реализации"
        increment_button_press('Сферы реализации')

    elif call.data == 'Через что придут деньги':
        photo_url = 'https://i.imgur.com/J1MjO6m.jpg'  # Замените на актуальный URL изображения
        text = """Каждый год в Матрице Судьбы связан с определённой энергией, которая подсказывает, через какие действия и сферы ты сможешь привлечь финансы.

В ЭТОМ году деньги будут приходить через энергию, рассчитанную для тебя лично. Узнай, что поможет открыть денежный поток, и получи рекомендации для своего финансового успеха!

Жми на кнопку ниже, чтобы рассчитать свою энергию и узнать, как максимально использовать свои возможности!"""

        keyboard = InlineKeyboardMarkup()
        keyboard.add(InlineKeyboardButton("Узнать", url="https://t.me/daryaasunshine/1014"))
        keyboard.add(InlineKeyboardButton("⬅️ Назад", callback_data='ya_iz_instagram'))

        try:
            bot.edit_message_media(
                media=InputMediaPhoto(media=photo_url, caption=text),
                chat_id=chat_id,
                message_id=call.message.message_id,
                reply_markup=keyboard
            )
            user_data[chat_id]['state'] = 'money_coming'
        except Exception as e:
            logging.warning(f"Не удалось отредактировать сообщение: {e}")
            sent = bot.send_photo(
                chat_id,
                photo=photo_url,
                caption=text,
                reply_markup=keyboard
            )
            user_data[chat_id]['post_creation_messages'].append(sent.message_id)
            user_data[chat_id]['last_message_id'] = sent.message_id
            user_data[chat_id]['state'] = 'money_coming'

        # Увеличиваем счетчик нажатий на кнопку "Через что придут деньги"
        increment_button_press('Через что придут деньги')

    elif call.data == 'moi_produkti':
        photo_url = 'https://i.imgur.com/lYbgpso.jpg'  # Исправленная ссылка на изображение
        text = """Готова к переменам?

Чувствуешь, что застряла на месте, не понимаешь, как раскрыть свой потенциал или выделиться? Мои продукты помогут тебе:

• Матрица года — рекомендации, чтобы гармонично прожить 2025 год.
• Личный бренд — создание уникального образа, который привлекает и приносит доход.
• Курс — пошаговая работа с Матрицей для раскрытия талантов и выхода на новый уровень.

Каждый продукт — это инструмент для изменений и раскрытия твоей силы. Выбирай и начни путь к гармонии уже сегодня!"""

        keyboard = InlineKeyboardMarkup()
        keyboard.add(InlineKeyboardButton("Личный бренд", callback_data='Личный бренд'))
        keyboard.add(InlineKeyboardButton("Матрица года", callback_data='Матрица года'))
        keyboard.add(InlineKeyboardButton("Курс «Путь к себе 2.0»", url="https://t.me/+eLbM0CHJ6Ec2NDNi"))
        keyboard.add(InlineKeyboardButton("✨Калькулятор матрицы", url='https://t.me/matrixraschet_bot'))
        keyboard.add(InlineKeyboardButton("🙋‍♀️Обо мне", callback_data='obo_mne'))
        keyboard.add(InlineKeyboardButton("⬅️ Назад", callback_data='back_to_main'))

        try:
            bot.edit_message_media(
                media=InputMediaPhoto(media=photo_url, caption=text),
                chat_id=chat_id,
                message_id=call.message.message_id,
                reply_markup=keyboard
            )
            user_data[chat_id]['state'] = 'moi_produkti'
        except Exception as e:
            logging.warning(f"Не удалось отредактировать сообщение: {e}")
            sent = bot.send_photo(
                chat_id,
                photo=photo_url,
                caption=text,
                reply_markup=keyboard
            )
            user_data[chat_id]['post_creation_messages'].append(sent.message_id)
            user_data[chat_id]['last_message_id'] = sent.message_id
            user_data[chat_id]['state'] = 'moi_produkti'

        # Увеличиваем счетчик нажатий на кнопку "👉🏻Узнать о себе👈🏻"
        increment_button_press('👉🏻Узнать о себе👈🏻')

    elif call.data == 'obo_mne':
        photo_url = 'https://i.imgur.com/NRp1a4h.jpg'  # Исправленная ссылка на изображение
        text = """Привет! Меня зовут Дарина. Я — нумеролог, специалист по Матрице Судьбы и человек, который искренне верит, что осознанность способна менять жизнь.

Когда-то я начала свой путь с изучения нумерологии, чтобы разобраться в себе. Сегодня я делюсь этим знанием с тысячами людей, помогая им раскрывать потенциал, находить гармонию и преодолевать трудности.

Сейчас я развиваю свой блог, создаю курсы по Матрице Судьбы, обучаюсь на психолога, чтобы ещё глубже работать с людьми, и помогаю каждому, кто готов к переменам, стать ближе к себе.

Я верю, что у каждого есть сила менять свою жизнь, и я здесь, чтобы помочь вам сделать первый шаг.

Контакты
• Отзывы: @otzyvidaryasunshine
• Мой сайт: https://daryaasunshine.ru
• Мой Telegram: @amedari
• Помощница София: @soofa4kaa"""

        keyboard = InlineKeyboardMarkup()
        keyboard.add(InlineKeyboardButton("⬅️ Назад", callback_data='moi_produkti'))

        try:
            bot.edit_message_media(
                media=InputMediaPhoto(media=photo_url, caption=text),
                chat_id=chat_id,
                message_id=call.message.message_id,
                reply_markup=keyboard
            )
            user_data[chat_id]['state'] = 'obo_mne'
        except Exception as e:
            logging.warning(f"Не удалось отредактировать сообщение: {e}")
            sent = bot.send_photo(
                chat_id,
                photo=photo_url,
                caption=text,
                reply_markup=keyboard
            )
            user_data[chat_id]['last_message_id'] = sent.message_id
            user_data[chat_id]['state'] = 'obo_mne'

        # Увеличиваем счетчик нажатий на кнопку "🙋‍♀️Обо мне"
        increment_button_press('🙋‍♀️Обо мне')

    elif call.data == 'Матрица года':
        photo_url = 'https://i.imgur.com/23skmqI.jpg'  # Исправленная ссылка на изображение
        text = """Матрицы года, что это?

Матрица года — это словно дорожная карта на год, которая помогает двигаться вперёд, показывая, какие ресурсы использовать, какие вызовы преодолевать, к какому состоянию стремиться.

С помощью нее ты сможешь узнать:

🎟️ Что будет давать ресурс в этом году? А что наоборот будет забирать энергию? 
🎟️ Какой талант в этом году мир подарил тебе как проводнику? 
🎟️ Что важно сделать в этом году?
🎟️ Какие тебя ждут уроки и главный экзамен этого года?
🎟️ В чем могут возникать трудности и как их избежать? 

Матрица года даёт нам возможность не плыть по течению, а осознанно создавать свою реальность, проживая каждый год как уникальный этап на пути к самореализации и счастью."""

        keyboard = InlineKeyboardMarkup()
        keyboard.add(InlineKeyboardButton("💸Купить", url="https://t.me/Matricagoda_bot"))
        keyboard.add(InlineKeyboardButton("⬅️ Назад", callback_data='moi_produkti'))

        try:
            bot.edit_message_media(
                media=InputMediaPhoto(media=photo_url, caption=text),
                chat_id=chat_id,
                message_id=call.message.message_id,
                reply_markup=keyboard
            )
            user_data[chat_id]['state'] = 'matrix_year'
        except Exception as e:
            logging.warning(f"Не удалось отредактировать сообщение: {e}")
            sent = bot.send_photo(
                chat_id,
                photo=photo_url,
                caption=text,
                reply_markup=keyboard
            )
            user_data[chat_id]['last_message_id'] = sent.message_id
            user_data[chat_id]['state'] = 'matrix_year'

        # Увеличиваем счетчик нажатий на кнопку "Матрица года"
        increment_button_press('Матрица года')

    elif call.data == 'Личный бренд':
        photo_url = 'https://imgur.com/ojNzkJr'  # Замените на актуальный URL изображения
        text = """Что входит в полное пособие по Личному бренду?

- Закрытый тг-канал 
- Инструкцию по расчету базовых энергий и знакомство с 22 энергиями (описание)
- Само пособие (которое вы можете себе скачать!)

Содержание:

1️⃣Личные качества: какие личные качества стоит подчеркивать в блоге для привлечения и удержания целевой аудитории.
2️⃣ Профессиональные качества: как раскрывать свою экспертность, представляя профессиональные навыки наиболее выгодным образом.
3️⃣ Ключевые темы: какие темы обсуждать в блоге, исходя из сильных сторон, выявленных по дате рождения.
4️⃣ Что не стоит транслировать: какие аспекты личности лучше не демонстрировать, чтобы не оттолкнуть аудиторию.
5️⃣ Визуальная подача и атрибуты: рекомендации по визуальному оформлению, цветам, предметам и аксессуарам для создания уникального образа.

Доступ навсегда ♾️

➡️ Знания можно использовать, как для личного использования (для построения своего личного бренда), так и для работы с клиентами (для мастеров)."""

        keyboard = InlineKeyboardMarkup()
        keyboard.add(InlineKeyboardButton("💸Купить", url="https://t.me/Personal_brand_daryasunshinebot"))
        keyboard.add(InlineKeyboardButton("⬅️ Назад", callback_data='moi_produkti'))

        try:
            bot.edit_message_media(
                media=InputMediaPhoto(media=photo_url, caption=text),
                chat_id=chat_id,
                message_id=call.message.message_id,
                reply_markup=keyboard
            )
            user_data[chat_id]['state'] = 'personal_brand'
        except Exception as e:
            logging.warning(f"Не удалось отредактировать сообщение: {e}")
            sent = bot.send_photo(
                chat_id,
                photo=photo_url,
                caption=text,
                reply_markup=keyboard
            )
            user_data[chat_id]['last_message_id'] = sent.message_id
            user_data[chat_id]['state'] = 'personal_brand'

        # Увеличиваем счетчик нажатий на кнопку "Личный бренд"
        increment_button_press('Личный бренд')  # Исправлено с 'Матрица года' на 'Личный бренд'

    elif call.data == 'back_to_main':
        # Попытка отредактировать текущее сообщение на главное меню
        photo_url = 'https://i.imgur.com/6gEYdAP.jpg'  # Замените на актуальный URL изображения
        welcome_text = """Привет! 🤎
На связи Дарина, нумеролог и специалист по Матрице Судьбы — методу, который помогает глубже понять себя, работать с энергиями и осознанно подходить к жизни.

Здесь ты найдёшь:

• материалы для самопознания,
• полезные инструменты для гармонизации энергий,
• доступ к моим курсам и платным продуктам,
• вдохновение и поддержку на пути к лучшей версии себя."""

        try:
            media = InputMediaPhoto(media=photo_url, caption=welcome_text)
            bot.edit_message_media(
                media=media,
                chat_id=chat_id,
                message_id=call.message.message_id,
                reply_markup=main_menu(chat_id)
            )
            user_data[chat_id]['state'] = 'main_menu'
        except Exception as e:
            logging.warning(f"Не удалось отредактировать сообщение: {e}")
            # Если редактирование не удалось, отправляем новое сообщение
            try:
                sent = bot.send_photo(
                    chat_id,
                    photo=photo_url,
                    caption=welcome_text,
                    reply_markup=main_menu(chat_id)
                )
                user_data[chat_id]['last_message_id'] = sent.message_id
                user_data[chat_id]['state'] = 'main_menu'
            except Exception as send_e:
                logging.error(f"Не удалось отправить новое сообщение: {send_e}")
                # В крайнем случае, отправляем текстовое сообщение
                bot.send_message(
                    chat_id,
                    welcome_text,
                    reply_markup=main_menu(chat_id)
                )
                user_data[chat_id]['state'] = 'main_menu'

    elif call.data == 'return_to_main_menu':
        # Отправляем новое сообщение с начальным меню, сохраняя текст рассылки
        # Здесь предполагается, что текст рассылки уже отображается, поэтому отправляем только главное меню
        send_main_menu_message(chat_id)
        bot.answer_callback_query(call.id, "Главное меню отправлено.")

    # Обработка Админ Меню
    elif call.data == 'admin_menu':
        if chat_id in ADMIN_IDS:
            admin_text = "Выберите действие:"
            admin_photo_url = 'https://i.imgur.com/mp2tTUu.jpg'  # Замените на актуальный URL изображения для админ-меню

            try:
                bot.edit_message_media(
                    media=InputMediaPhoto(media=admin_photo_url, caption=admin_text),
                    chat_id=chat_id,
                    message_id=call.message.message_id,
                    reply_markup=admin_menu_markup()
                )
                user_data[chat_id]['state'] = 'admin_menu'
            except Exception as e:
                logging.warning(f"Не удалось отредактировать сообщение: {e}")
                # Если редактирование не удалось, отправляем новое сообщение
                sent = bot.send_photo(
                    chat_id,
                    photo=admin_photo_url,
                    caption=admin_text,
                    reply_markup=admin_menu_markup()
                )
                user_data[chat_id]['post_creation_messages'].append(sent.message_id)
                user_data[chat_id]['last_message_id'] = sent.message_id
                user_data[chat_id]['state'] = 'admin_menu'
        else:
            bot.answer_callback_query(call.id, "У вас нет доступа к этому разделу.")

    # Создать пост
    elif call.data == 'create_post':
        text = "Хотите добавить изображение к посту?"
        markup = admin_image_prompt_menu()
        create_post_photo_url = 'https://i.imgur.com/mp2tTUu.jpg'  # Замените на актуальный URL изображения для создания поста
        try:
            sent = bot.send_photo(
                chat_id,
                photo=create_post_photo_url,
                caption=text,
                reply_markup=markup
            )
            user_data[chat_id]['post_creation_messages'].append(sent.message_id)
            user_data[chat_id]['last_message_id'] = sent.message_id
            user_data[chat_id]['state'] = 'admin_create_post'
        except Exception as e:
            logging.warning(f"Не удалось отправить сообщение для создания поста: {e}")

    # Добавить изображение
    elif call.data == 'admin_add_image':
        text = "Отправьте фотографию для поста."
        markup = admin_back_cancel_menu()
        try:
            sent = bot.send_message(
                chat_id,
                text,
                reply_markup=markup
            )
            user_data[chat_id]['post_creation_messages'].append(sent.message_id)
            user_data[chat_id]['last_message_id'] = sent.message_id
            user_data[chat_id]['state'] = 'admin_awaiting_image'
        except Exception as e:
            logging.warning(f"Не удалось отправить запрос на изображение: {e}")

    # Пропустить добавление изображения
    elif call.data == 'admin_skip_image':
        user_data[chat_id]['post_image'] = None
        text = "Введите ваш текст для поста."
        markup = admin_back_cancel_menu()
        try:
            sent = bot.send_message(
                chat_id,
                text,
                reply_markup=markup
            )
            user_data[chat_id]['post_creation_messages'].append(sent.message_id)
            user_data[chat_id]['last_message_id'] = sent.message_id
            user_data[chat_id]['state'] = 'admin_awaiting_post_text'
        except Exception as e:
            logging.warning(f"Не удалось отправить запрос на текст поста: {e}")

    # Назад в Админ меню
    elif call.data == 'admin_back':
        admin_text = "Админ меню:"
        admin_menu_photo_url = 'https://i.imgur.com/mp2tTUu.jpg'  # Замените на актуальный URL изображения для админ-меню
        try:
            bot.edit_message_media(
                media=InputMediaPhoto(media=admin_menu_photo_url, caption=admin_text),
                chat_id=chat_id,
                message_id=call.message.message_id,
                reply_markup=admin_menu_markup()
            )
            user_data[chat_id]['state'] = 'admin_menu'
        except Exception as e:
            logging.warning(f"Не удалось отредактировать сообщение: {e}")
            # Если не удалось отредактировать, отправляем новое сообщение
            sent = bot.send_photo(
                chat_id,
                photo=admin_menu_photo_url,
                caption=admin_text,
                reply_markup=admin_menu_markup()
            )
            user_data[chat_id]['post_creation_messages'].append(sent.message_id)
            user_data[chat_id]['last_message_id'] = sent.message_id
            user_data[chat_id]['state'] = 'admin_menu'

    # Отменить создание поста
    elif call.data == 'admin_cancel':
        text = "Создание публикации отменено."
        markup = admin_menu_markup()
        cancel_photo_url = 'https://i.imgur.com/mp2tTUu.jpg'  # Замените на актуальный URL изображения
        try:
            sent = bot.send_photo(
                chat_id,
                photo=cancel_photo_url,
                caption=text,
                reply_markup=markup
            )
            user_data[chat_id]['post_creation_messages'].append(sent.message_id)
            user_data[chat_id]['last_message_id'] = sent.message_id
            user_data[chat_id]['state'] = 'admin_menu'
            # Удаляем все временные сообщения, связанные с созданием поста
            for msg_id in user_data[chat_id]['post_creation_messages'][:-1]:
                try:
                    bot.delete_message(chat_id, msg_id)
                except Exception as delete_error:
                    logging.warning(f"Не удалось удалить сообщение {msg_id}: {delete_error}")
            user_data[chat_id]['post_creation_messages'] = [sent.message_id]
        except Exception as e:
            logging.warning(f"Не удалось отправить сообщение об отмене: {e}")

    # Подтверждение публикации
    elif call.data == 'admin_confirm_publish':
        # Проверяем, есть ли текст поста
        post_text = user_data[chat_id].get('post_text')
        if post_text:
            # Запускаем массовую рассылку
            send_post_to_all(chat_id)
        else:
            text = "Текст поста отсутствует. Отправка отменена."
            markup = admin_menu_markup()
            no_text_photo_url = 'https://i.imgur.com/mp2tTUu.jpg'  # Замените на актуальный URL изображения
            try:
                # Отправляем сообщение об отсутствии текста
                sent = bot.send_photo(
                    chat_id,
                    photo=no_text_photo_url,
                    caption=text,
                    reply_markup=markup
                )
                user_data[chat_id]['post_creation_messages'].append(sent.message_id)
                user_data[chat_id]['last_message_id'] = sent.message_id
                user_data[chat_id]['state'] = 'admin_menu'
            except Exception as e:
                logging.warning(f"Не удалось отправить сообщение об отсутствии текста: {e}")

    # Отмена публикации
    elif call.data == 'admin_cancel_publish':
        text = "Создание публикации отменено."
        markup = admin_menu_markup()
        cancel_publish_photo_url = 'https://i.imgur.com/mp2tTUu.jpg'  # Замените на актуальный URL изображения
        try:
            sent = bot.send_photo(
                chat_id,
                photo=cancel_publish_photo_url,
                caption=text,
                reply_markup=markup
            )
            user_data[chat_id]['post_creation_messages'].append(sent.message_id)
            user_data[chat_id]['last_message_id'] = sent.message_id
            user_data[chat_id]['state'] = 'admin_menu'
            # Удаляем все временные сообщения, связанные с созданием поста
            for msg_id in user_data[chat_id]['post_creation_messages'][:-1]:
                try:
                    bot.delete_message(chat_id, msg_id)
                except Exception as delete_error:
                    logging.warning(f"Не удалось удалить сообщение {msg_id}: {delete_error}")
            user_data[chat_id]['post_creation_messages'] = [sent.message_id]
        except Exception as e:
            logging.warning(f"Не удалось отправить сообщение об отмене публикации: {e}")

    # Добавить кнопку к посту
    elif call.data == 'admin_add_button':
        text = "Хотите добавить кнопку к посту?"
        markup = admin_yes_no_menu()
        add_button_photo_url = 'https://i.imgur.com/mp2tTUu.jpg'  # Замените на актуальный URL изображения
        try:
            sent = bot.send_photo(
                chat_id,
                photo=add_button_photo_url,
                caption=text,
                reply_markup=markup
            )
            user_data[chat_id]['post_creation_messages'].append(sent.message_id)
            user_data[chat_id]['last_message_id'] = sent.message_id
            user_data[chat_id]['state'] = 'admin_confirm_add_button'
        except Exception as e:
            logging.warning(f"Не удалось отправить запрос на добавление кнопки: {e}")

    # Да, добавить кнопку
    elif call.data == 'admin_yes_add_button':
        text = "Введите название кнопки."
        markup = admin_back_cancel_menu()
        button_text_photo_url = 'https://i.imgur.com/mp2tTUu.jpg'  # Замените на актуальный URL изображения
        try:
            sent = bot.send_photo(
                chat_id,
                photo=button_text_photo_url,
                caption=text,
                reply_markup=markup
            )
            user_data[chat_id]['post_creation_messages'].append(sent.message_id)
            user_data[chat_id]['last_message_id'] = sent.message_id
            user_data[chat_id]['state'] = 'admin_awaiting_button_text'
        except Exception as e:
            logging.warning(f"Не удалось отправить запрос на название кнопки: {e}")

    # Нет, не добавлять кнопку
    elif call.data == 'admin_no_add_button':
        text = "Ваш пост почти опубликован."
        markup = admin_publish_confirmation_menu()
        publish_near_photo_url = 'https://i.imgur.com/mp2tTUu.jpg'  # Замените на актуальный URL изображения
        try:
            sent = bot.send_photo(
                chat_id,
                photo=publish_near_photo_url,
                caption=text,
                reply_markup=markup
            )
            user_data[chat_id]['post_creation_messages'].append(sent.message_id)
            user_data[chat_id]['last_message_id'] = sent.message_id
            user_data[chat_id]['state'] = 'admin_confirm_publish'
        except Exception as e:
            logging.warning(f"Не удалось отправить сообщение о готовности к публикации: {e}")

    # Статистика
    elif call.data == 'admin_statistika':
        user_count = get_user_count()
        users_started = get_users_started()
        text = f"✅ Запустивших бота пользователей - {users_started}\n🧑‍🤝‍🧑 Текущих пользователей - {user_count}"
        markup = InlineKeyboardMarkup().row(
            InlineKeyboardButton("⬅️ Назад", callback_data='admin_menu')
        )
        statistics_photo_url = 'https://i.imgur.com/mp2tTUu.jpg'  # Замените на актуальный URL изображения
        try:
            sent = bot.send_photo(
                chat_id,
                photo=statistics_photo_url,
                caption=text,
                reply_markup=markup
            )
            user_data[chat_id]['post_creation_messages'].append(sent.message_id)
            user_data[chat_id]['last_message_id'] = sent.message_id
            user_data[chat_id]['state'] = 'admin_statistika'
        except Exception as e:
            logging.warning(f"Не удалось отправить статистику: {e}")

    # Анализ кнопок
    elif call.data == 'admin_analyze_buttons':
        buttons = get_all_buttons()
        if not buttons:
            buttons_text = "Анализ кнопок:\nНет данных."
            buttons_photo_url = 'https://i.imgur.com/mp2tTUu.jpg'  # Замените на актуальный URL изображения
        else:
            buttons_text = "Анализ кнопок:\n"
            for button in buttons:
                buttons_text += f"{button[0]} - {button[1]}\n"
            buttons_photo_url = 'https://i.imgur.com/mp2tTUu.jpg'  # Замените на актуальный URL изображения

        markup = admin_menu_markup()
        try:
            sent = bot.send_photo(
                chat_id,
                photo=buttons_photo_url,
                caption=buttons_text,
                reply_markup=markup
            )
            user_data[chat_id]['post_creation_messages'].append(sent.message_id)
            user_data[chat_id]['last_message_id'] = sent.message_id
            user_data[chat_id]['state'] = 'admin_menu'
        except Exception as e:
            logging.warning(f"Не удалось отправить анализ кнопок: {e}")

    # Экспорт пользователей
    elif call.data == 'admin_export_users':
        text = "Вы действительно хотите выгрузить всех пользователей в CSV?"
        markup = export_users_confirmation_menu()
        export_users_photo_url = 'https://i.imgur.com/mp2tTUu.jpg'  # Замените на актуальный URL изображения
        try:
            sent = bot.send_photo(
                chat_id,
                photo=export_users_photo_url,
                caption=text,
                reply_markup=markup
            )
            user_data[chat_id]['post_creation_messages'].append(sent.message_id)
            user_data[chat_id]['last_message_id'] = sent.message_id
            user_data[chat_id]['state'] = 'admin_confirm_export'
        except Exception as e:
            logging.warning(f"Не удалось отправить запрос на экспорт пользователей: {e}")

    # Подтверждение экспорта
    elif call.data == 'admin_confirm_export_yes':
        users = get_all_users()
        if not users:
            text = "Список пользователей пуст."
            markup = admin_menu_markup()
            empty_users_photo_url = 'https://i.imgur.com/mp2tTUu.jpg'  # Замените на актуальный URL изображения
            try:
                # Отправляем сообщение о пустом списке
                sent = bot.send_photo(
                    chat_id,
                    photo=empty_users_photo_url,
                    caption=text,
                    reply_markup=markup
                )
                user_data[chat_id]['post_creation_messages'].append(sent.message_id)
                user_data[chat_id]['last_message_id'] = sent.message_id
                user_data[chat_id]['state'] = 'admin_menu'
            except Exception as e:
                logging.warning(f"Не удалось отправить сообщение о пустом списке пользователей: {e}")
            return

        # Генерируем CSV содержимое
        csv_content = "Ник,ID,Старт\n"
        for u in users:
            csv_content += f"@{u[1]},{u[0]},{u[2]}\n"

        try:
            # Отправляем CSV файл
            bot.send_document(chat_id, ('users.csv', csv_content.encode('utf-8')))

            # Отправляем сообщение об успешном экспорте и главное меню
            success_text = "Пользователи успешно экспортированы."
            success_photo_url = 'https://i.imgur.com/mp2tTUu.jpg'  # Замените на актуальный URL изображения
            sent = bot.send_photo(
                chat_id,
                photo=success_photo_url,
                caption=success_text,
                reply_markup=main_menu(chat_id)
            )
            user_data[chat_id]['post_creation_messages'].append(sent.message_id)
            user_data[chat_id]['last_message_id'] = sent.message_id
            user_data[chat_id]['state'] = 'main_menu'

            # Удаляем все временные сообщения, кроме текущего
            for msg_id in user_data[chat_id]['post_creation_messages'][:-1]:
                try:
                    bot.delete_message(chat_id, msg_id)
                except Exception as delete_error:
                    logging.warning(f"Не удалось удалить сообщение {msg_id}: {delete_error}")
            # Обновляем список сообщений
            user_data[chat_id]['post_creation_messages'] = [sent.message_id]

        except telebot.apihelper.ApiException as e:
            bot.send_message(chat_id, "Ошибка при экспорте.", reply_markup=admin_menu_markup())
            logging.error(f"Ошибка при экспорте пользователей: {e}")

    elif call.data == 'admin_confirm_export_no':
        text = "Экспорт пользователей отменен."
        markup = admin_menu_markup()
        export_cancel_photo_url = 'https://i.imgur.com/mp2tTUu.jpg'  # Замените на актуальный URL изображения
        try:
            sent = bot.send_photo(
                chat_id,
                photo=export_cancel_photo_url,
                caption=text,
                reply_markup=markup
            )
            user_data[chat_id]['post_creation_messages'].append(sent.message_id)
            user_data[chat_id]['last_message_id'] = sent.message_id
            user_data[chat_id]['state'] = 'admin_menu'
        except Exception as e:
            logging.warning(f"Не удалось отправить сообщение об отмене экспорта: {e}")

    # Отправка неизвестной команды
    else:
        bot.answer_callback_query(call.id, "Неизвестная команда.")

# Обработка сообщений
@bot.message_handler(content_types=['text', 'photo'])
def handle_message(message):
    chat_id = message.chat.id
    if chat_id in user_data:
        state = user_data[chat_id].get('state', '')
        if state == 'admin_awaiting_image':
            if message.content_type == 'photo':
                # Получаем файл фото
                file_info = bot.get_file(message.photo[-1].file_id)
                downloaded_file = bot.download_file(file_info.file_path)
                # Сохраняем фото во временную директорию
                file_name = f"{chat_id}_{int(time.time())}.jpg"
                file_path = os.path.join(TEMP_PHOTO_DIR, file_name)
                with open(file_path, 'wb') as new_file:
                    new_file.write(downloaded_file)
                user_data[chat_id]['post_image'] = file_path
                text = "Введите ваш текст для поста."
                markup = admin_back_cancel_menu()
                try:
                    sent = bot.send_message(
                        chat_id,
                        text,
                        reply_markup=markup
                    )
                    user_data[chat_id]['post_creation_messages'].append(sent.message_id)
                    user_data[chat_id]['last_message_id'] = sent.message_id
                    user_data[chat_id]['state'] = 'admin_awaiting_post_text'
                except Exception as e:
                    logging.warning(f"Не удалось отправить запрос на текст поста: {e}")
            else:
                text = "Пожалуйста, отправьте фотографию."
                markup = admin_back_cancel_menu()
                try:
                    sent = bot.send_message(
                        chat_id,
                        text,
                        reply_markup=markup
                    )
                    user_data[chat_id]['post_creation_messages'].append(sent.message_id)
                    user_data[chat_id]['last_message_id'] = sent.message_id
                except Exception as e:
                    logging.warning(f"Не удалось отправить запрос на фотографию: {e}")

        elif state == 'admin_awaiting_post_text':
            post_text = message.text.strip()
            if post_text:
                user_data[chat_id]['post_text'] = post_text
                text = "Хотите добавить кнопку к посту?"
                markup = admin_yes_no_menu()
                try:
                    sent = bot.send_photo(
                        chat_id,
                        photo='https://i.imgur.com/mp2tTUu.jpg',  # Замените на актуальный URL изображения
                        caption=text,
                        reply_markup=markup
                    )
                    user_data[chat_id]['post_creation_messages'].append(sent.message_id)
                    user_data[chat_id]['last_message_id'] = sent.message_id
                    user_data[chat_id]['state'] = 'admin_confirm_add_button'
                except Exception as e:
                    logging.warning(f"Не удалось отправить запрос на добавление кнопки: {e}")
            else:
                text = "Текст поста не может быть пустым. Пожалуйста, введите текст для поста."
                markup = admin_back_cancel_menu()
                try:
                    sent = bot.send_photo(
                        chat_id,
                        photo='https://i.imgur.com/mp2tTUu.jpg',  # Замените на актуальный URL изображения
                        caption=text,
                        reply_markup=markup
                    )
                    user_data[chat_id]['post_creation_messages'].append(sent.message_id)
                    user_data[chat_id]['last_message_id'] = sent.message_id
                except Exception as e:
                    logging.warning(f"Не удалось отправить сообщение об ошибке: {e}")

        elif state == 'admin_awaiting_button_text':
            button_text = message.text.strip()
            if button_text:
                user_data[chat_id]['button_text'] = button_text
                text = "Введите ссылку для кнопки."
                markup = admin_back_cancel_menu()
                try:
                    sent = bot.send_photo(
                        chat_id,
                        photo='https://i.imgur.com/mp2tTUu.jpg',  # Замените на актуальный URL изображения
                        caption=text,
                        reply_markup=markup
                    )
                    user_data[chat_id]['post_creation_messages'].append(sent.message_id)
                    user_data[chat_id]['last_message_id'] = sent.message_id
                    user_data[chat_id]['state'] = 'admin_awaiting_button_url'
                except Exception as e:
                    logging.warning(f"Не удалось отправить запрос на URL кнопки: {e}")
            else:
                text = "Название кнопки не может быть пустым. Пожалуйста, введите название кнопки."
                markup = admin_back_cancel_menu()
                try:
                    sent = bot.send_photo(
                        chat_id,
                        photo='https://i.imgur.com/mp2tTUu.jpg',  # Замените на актуальный URL изображения
                        caption=text,
                        reply_markup=markup
                    )
                    user_data[chat_id]['post_creation_messages'].append(sent.message_id)
                    user_data[chat_id]['last_message_id'] = sent.message_id
                except Exception as e:
                    logging.warning(f"Не удалось отправить сообщение об ошибке кнопки: {e}")

        elif state == 'admin_awaiting_button_url':
            button_url = message.text.strip()
            if button_url.startswith('http://') or button_url.startswith('https://'):
                user_data[chat_id]['button_url'] = button_url
                text = "Ваш пост почти опубликован."
                markup = admin_publish_confirmation_menu()
                try:
                    sent = bot.send_photo(
                        chat_id,
                        photo='https://i.imgur.com/mp2tTUu.jpg',  # Замените на актуальный URL изображения
                        caption=text,
                        reply_markup=markup
                    )
                    user_data[chat_id]['post_creation_messages'].append(sent.message_id)
                    user_data[chat_id]['last_message_id'] = sent.message_id
                    user_data[chat_id]['state'] = 'admin_confirm_publish'
                except Exception as e:
                    logging.warning(f"Не удалось отправить сообщение о готовности к публикации: {e}")
            else:
                text = "Пожалуйста, введите действительный URL для кнопки (начинается с http:// или https://)."
                markup = admin_back_cancel_menu()
                try:
                    sent = bot.send_photo(
                        chat_id,
                        photo='https://i.imgur.com/mp2tTUu.jpg',  # Замените на актуальный URL изображения
                        caption=text,
                        reply_markup=markup
                    )
                    user_data[chat_id]['post_creation_messages'].append(sent.message_id)
                    user_data[chat_id]['last_message_id'] = sent.message_id
                except Exception as e:
                    logging.warning(f"Не удалось отправить сообщение об ошибке URL кнопки: {e}")

        else:
            # Для остальных состояний или пользователей
            send_welcome(message)

# Функция получения всех кнопок и их счетчиков
def get_all_buttons():
    with sqlite3.connect(DB_FILE) as conn:
        cursor = conn.cursor()
        cursor.execute('SELECT button_name, count FROM button_presses')
        return cursor.fetchall()

# Функция получения количества пользователей из базы данных
def get_user_count():
    with sqlite3.connect(DB_FILE) as conn:
        cursor = conn.cursor()
        cursor.execute('SELECT COUNT(*) FROM users')
        result = cursor.fetchone()
        return result[0] if result else 0

# Функция отправки поста всем пользователям с ограничением скорости
def send_post_to_all(admin_chat_id):
    image_path = user_data[admin_chat_id].get('post_image')  # Локальный путь к изображению
    post_text = user_data[admin_chat_id].get('post_text', '')
    button_text = user_data[admin_chat_id].get('button_text')
    button_url = user_data[admin_chat_id].get('button_url')

    if not post_text:
        bot.send_message(admin_chat_id, "Текст поста отсутствует. Отправка отменена.", reply_markup=admin_menu_markup())
        return

    keyboard = InlineKeyboardMarkup()
    if button_text and button_url:
        keyboard.add(InlineKeyboardButton(button_text, url=button_url))

    # Добавляем кнопку "Вернуться в главное меню" с новым callback_data
    keyboard.add(InlineKeyboardButton("Вернуться в главное меню", callback_data='return_to_main_menu'))

    # Функция создания главного меню для отправки после рассылки
    def send_main_menu_after_broadcast():
        photo_url = 'https://i.imgur.com/6gEYdAP.jpg'  # Замените на актуальный URL изображения
        welcome_text = """Привет! 🤎
На связи Дарина, нумеролог и специалист по Матрице Судьбы — методу, который помогает глубже понять себя, работать с энергиями и осознанно подходить к жизни.

Здесь ты найдёшь:

• материалы для самопознания,
• полезные инструменты для гармонизации энергий,
• доступ к моим курсам и платным продуктам,
• вдохновение и поддержку на пути к лучшей версии себя."""
        try:
            sent_main = bot.send_photo(
                admin_chat_id,
                photo=photo_url,
                caption=welcome_text,
                reply_markup=main_menu(admin_chat_id)
            )
            user_data[admin_chat_id]['post_creation_messages'].append(sent_main.message_id)
            user_data[admin_chat_id]['last_message_id'] = sent_main.message_id
            user_data[admin_chat_id]['state'] = 'main_menu'
        except Exception as e:
            logging.warning(f"Не удалось отправить главное меню после рассылки: {e}")

    users = get_all_users()
    total_users = len(users)
    batch_size = 20  # 20 сообщений в секунду
    total_batches = (total_users + batch_size - 1) // batch_size  # Округление вверх
    estimated_time = total_batches  # Примерное время (секунды)

    # Уведомление администратору о начале рассылки
    bot.send_message(
        admin_chat_id,
        f"📝 Начинается рассылка поста.\n🔢 Всего пользователей: {total_users}\n⏳ Примерное время: {estimated_time} сек.",
        parse_mode='HTML'
    )

    # Инициализация счетчиков
    success_count = 0
    failure_count = 0

    def send_batches():
        nonlocal success_count, failure_count
        for batch_number in range(total_batches):
            start_index = batch_number * batch_size
            end_index = start_index + batch_size
            current_batch = users[start_index:end_index]
            for user in current_batch:
                user_id = user[0]
                if user_id not in ADMIN_IDS:
                    try:
                        if image_path and os.path.exists(image_path):
                            with open(image_path, 'rb') as photo:
                                bot.send_photo(
                                    user_id,
                                    photo=photo,
                                    caption=post_text,
                                    reply_markup=keyboard,
                                    parse_mode='HTML'
                                )
                        else:
                            bot.send_message(
                                user_id,
                                post_text,
                                reply_markup=keyboard,
                                parse_mode='HTML'
                            )
                        success_count +=1
                        logging.info(f"Пост отправлен пользователю {user_id}")
                    except apihelper.ApiException as e:
                        if 'blocked by the user' in str(e).lower():
                            # Пользователь заблокировал бота, удаляем его из базы
                            remove_user(user_id)
                            failure_count +=1
                            logging.info(f"Пользователь {user_id} удалён (заблокировал бота).")
                        else:
                            failure_count +=1
                            logging.error(f"Не удалось отправить пост пользователю {user_id}: {e}")
            # Пауза между партиями
            time.sleep(1)

        # Уведомление администратору о завершении рассылки
        summary_text = f"Рассылка успешно завершена✅\nПолучили сообщение: {success_count}\nЗаблокировали бота: {failure_count}."
        sent_summary = bot.send_message(admin_chat_id, summary_text, parse_mode='HTML')

        # Отправляем главное меню
        send_main_menu_after_broadcast()

        # Очистка данных поста после отправки
        user_data[admin_chat_id].pop('post_image', None)
        user_data[admin_chat_id].pop('post_text', None)
        user_data[admin_chat_id].pop('button_text', None)
        user_data[admin_chat_id].pop('button_url', None)

        # Удаление временного файла изображения
        if image_path and os.path.exists(image_path):
            try:
                os.remove(image_path)
                logging.info(f"Временный файл {image_path} удалён.")
            except Exception as delete_error:
                logging.warning(f"Не удалось удалить временный файл {image_path}: {delete_error}")

    threading.Thread(target=send_batches).start()

# Функция получения всех кнопок и их счетчиков
def get_all_buttons():
    with sqlite3.connect(DB_FILE) as conn:
        cursor = conn.cursor()
        cursor.execute('SELECT button_name, count FROM button_presses')
        return cursor.fetchall()

# Функция получения количества пользователей из базы данных
def get_user_count():
    with sqlite3.connect(DB_FILE) as conn:
        cursor = conn.cursor()
        cursor.execute('SELECT COUNT(*) FROM users')
        result = cursor.fetchone()
        return result[0] if result else 0


# Запуск бота
print("Бот запущен...")
if __name__ == "__main__":
    # Используем порт из переменной окружения PORT или 10000 по умолчанию
    port = int(os.environ.get("PORT", 10000))
    uvicorn.run(app, host="0.0.0.0", port=port)
