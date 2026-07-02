import os
import time
import threading
import re
import sqlite3
import telebot
from telebot import types
from flask import Flask
from datetime import datetime

# === НАЛАШТУВАННЯ ===
TOKEN = os.environ.get('TOKEN', '8252581199:AAHNfedYh1MrQVNBrL6mYf6OJVoTim_dApM')
ADMIN_GROUP_ID = "-1614259542" 

# ID ВЛАСНИКІВ (@dragwayder та @p1vi_k)
OWNERS = [1614259542, 7716987740] 

bot = telebot.TeleBot(TOKEN, parse_mode='HTML')
user_states = {}

# === БАЗА ДАНИХ (SQLite) ===
DB_FILE = 'dragpolit.db'

def init_db():
    conn = sqlite3.connect(DB_FILE)
    c = conn.cursor()
    # Таблиця користувачів
    c.execute('''CREATE TABLE IF NOT EXISTS users 
                 (user_id INTEGER PRIMARY KEY, username TEXT, is_banned INTEGER DEFAULT 0, join_date TEXT)''')
    # Таблиця статистики (загальної)
    c.execute('''CREATE TABLE IF NOT EXISTS stats (key TEXT PRIMARY KEY, value INTEGER)''')
    c.execute("INSERT OR IGNORE INTO stats (key, value) VALUES ('total_tickets', 0)")
    conn.commit()
    conn.close()

def add_user(user_id, username):
    conn = sqlite3.connect(DB_FILE)
    c = conn.cursor()
    c.execute("SELECT user_id FROM users WHERE user_id = ?", (user_id,))
    is_new = c.fetchone() is None
    
    if is_new:
        date_str = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        c.execute("INSERT INTO users (user_id, username, join_date) VALUES (?, ?, ?)", (user_id, username, date_str))
    
    conn.commit()
    conn.close()
    return is_new

def get_all_users():
    conn = sqlite3.connect(DB_FILE)
    c = conn.cursor()
    c.execute("SELECT user_id FROM users WHERE is_banned = 0")
    users = [row[0] for row in c.fetchall()]
    conn.close()
    return users

def set_ban_status(user_id, status):
    conn = sqlite3.connect(DB_FILE)
    c = conn.cursor()
    c.execute("UPDATE users SET is_banned = ? WHERE user_id = ?", (status, user_id))
    conn.commit()
    conn.close()

def is_banned(user_id):
    conn = sqlite3.connect(DB_FILE)
    c = conn.cursor()
    c.execute("SELECT is_banned FROM users WHERE user_id = ?", (user_id,))
    result = c.fetchone()
    conn.close()
    return result[0] == 1 if result else False

def inc_ticket_count():
    conn = sqlite3.connect(DB_FILE)
    c = conn.cursor()
    c.execute("UPDATE stats SET value = value + 1 WHERE key = 'total_tickets'")
    conn.commit()
    conn.close()

def get_stats():
    conn = sqlite3.connect(DB_FILE)
    c = conn.cursor()
    c.execute("SELECT COUNT(*) FROM users")
    total_users = c.fetchone()[0]
    
    c.execute("SELECT COUNT(*) FROM users WHERE is_banned = 1")
    banned_users = c.fetchone()[0]
    
    c.execute("SELECT value FROM stats WHERE key = 'total_tickets'")
    total_tickets = c.fetchone()[0]
    
    conn.close()
    return total_users, banned_users, total_tickets

init_db()

# === КЛАВІАТУРИ ===
def get_start_kb():
    markup = types.InlineKeyboardMarkup(row_width=1)
    markup.add(
        types.InlineKeyboardButton("🚨 Экстренная связь / ЧП", callback_data="type_urgent"),
        types.InlineKeyboardButton("🤝 Предложения и сотрудничество", callback_data="type_collab"),
        types.InlineKeyboardButton("🐛 Сообщить о баге", callback_data="type_bug"),
        types.InlineKeyboardButton("📝 Подать заявку в Администрацию", callback_data="type_apply")
    )
    return markup

def get_cancel_kb():
    markup = types.InlineKeyboardMarkup()
    markup.add(types.InlineKeyboardButton("❌ Отменить", callback_data="cancel_action"))
    return markup

def get_admin_kb():
    markup = types.InlineKeyboardMarkup(row_width=2)
    markup.add(
        types.InlineKeyboardButton("📢 Рассылка", callback_data="admin_broadcast"),
        types.InlineKeyboardButton("📊 Статистика", callback_data="admin_stats"),
        types.InlineKeyboardButton("⛔️ Забанить", callback_data="admin_ban"),
        types.InlineKeyboardButton("✅ Разбанить", callback_data="admin_unban")
    )
    return markup

# === КОМАНДИ ===
@bot.message_handler(commands=['start'])
def start_command(message):
    user_id = message.chat.id
    username = f"@{message.from_user.username}" if message.from_user.username else "Анонимный"
    
    # Реєстрація та перевірка на новенького
    is_new = add_user(user_id, username)
    if is_new:
        for owner in OWNERS:
            try:
                bot.send_message(owner, f"👤 <b>Новый игрок в боте!</b>\nПользователь: {username}\nID: <code>{user_id}</code>")
            except: pass

    if is_banned(user_id):
        return bot.send_message(user_id, "⛔️ <b>Вы заблокированы</b> и не можете обращаться в поддержку.")

    user_states.pop(user_id, None)
    text = (
        "<b>Официальная служба поддержки DragPolit</b>\n\n"
        "Выберите необходимый раздел меню. Обратите внимание, что спам и ложные вызовы могут привести к блокировке."
    )
    bot.send_message(user_id, text, reply_markup=get_start_kb())

@bot.message_handler(commands=['admin'])
def admin_panel_command(message):
    if message.chat.id not in OWNERS:
        return bot.reply_to(message, "⛔️ У вас нет доступа к этой команде.")
    bot.send_message(message.chat.id, "👑 <b>Панель управления Владельцев</b>:", reply_markup=get_admin_kb())

@bot.message_handler(commands=['get_id'])
def get_id_command(message):
    bot.reply_to(message, f"Ваш ID: <code>{message.chat.id}</code>")

@bot.callback_query_handler(func=lambda call: call.data == 'cancel_action')
def cancel_action(call):
    user_states.pop(call.message.chat.id, None)
    bot.edit_message_text("Действие отменено. Возврат в главное меню.", call.message.chat.id, call.message.message_id, reply_markup=get_start_kb())

# === АДМІН-КНОПКИ В ЛС ===
@bot.callback_query_handler(func=lambda call: call.data.startswith('admin_'))
def handle_admin_callbacks(call):
    if call.message.chat.id not in OWNERS:
        return bot.answer_callback_query(call.id, "Нет доступа!", show_alert=True)
    
    action = call.data.split('_')[1]
    
    if action == 'stats':
        total_users, banned_users, total_tickets = get_stats()
        text = f"📊 <b>Расширенная статистика:</b>\n\n👥 Всего пользователей: <b>{total_users}</b>\n⛔️ В бане: <b>{banned_users}</b>\n📩 Обработано тикетов: <b>{total_tickets}</b>"
        bot.edit_message_text(text, call.message.chat.id, call.message.message_id, reply_markup=get_admin_kb())
    
    elif action == 'broadcast':
        user_states[call.message.chat.id] = {'state': 'waiting_broadcast'}
        bot.edit_message_text("📢 <b>Рассылка</b>\nОтправьте сообщение (текст/фото/видео) для рассылки всем пользователям:", call.message.chat.id, call.message.message_id, reply_markup=get_cancel_kb())
        
    elif action == 'ban':
        user_states[call.message.chat.id] = {'state': 'waiting_ban'}
        bot.edit_message_text("⛔️ <b>Блокировка</b>\nОтправьте цифровой ID пользователя для бана:", call.message.chat.id, call.message.message_id, reply_markup=get_cancel_kb())

    elif action == 'unban':
        user_states[call.message.chat.id] = {'state': 'waiting_unban'}
        bot.edit_message_text("✅ <b>Разблокировка</b>\nОтправьте цифровой ID пользователя для разбана:", call.message.chat.id, call.message.message_id, reply_markup=get_cancel_kb())

# === МЕНЮ ГРАВЦІВ ===
@bot.callback_query_handler(func=lambda call: call.data.startswith('type_'))
def handle_main_menu(call):
    if is_banned(call.message.chat.id):
        return bot.answer_callback_query(call.id, "Вы заблокированы!", show_alert=True)

    action = call.data.split('_')[1]
    
    # Інтерактивна анкета для адмінів
    if action == 'apply':
        user_states[call.message.chat.id] = {'state': 'apply_step_1', 'answers': {}}
        return bot.edit_message_text("📝 <b>Шаг 1 из 3:</b>\nНапишите ваше Имя и Возраст (например: Иван, 16):", call.message.chat.id, call.message.message_id, reply_markup=get_cancel_kb())

    # Звичайні тікети
    if action == 'bug':
        text = "🛠 <b>Баг-репорт</b>\nОпишите проблему:\n1. Что сломалось?\n2. Где?\n3. Как повторить?"
        category = "Баг-репорт"
    elif action == 'urgent':
        text = "🚨 <b>Экстренная связь (ЧП)</b>\nПодробно опишите вашу проблему."
        category = "ЧП / Срочно"
    elif action == 'collab':
        text = "🤝 <b>Сотрудничество</b>\nОпишите суть вашего предложения."
        category = "Сотрудничество"
        
    user_states[call.message.chat.id] = {'state': 'waiting_ticket', 'category': category}
    bot.edit_message_text(text, call.message.chat.id, call.message.message_id, reply_markup=get_cancel_kb())

# === ОБРОБКА ВВОДУ ВІД КОРИСТУВАЧІВ ТА АДМІНІВ ===
@bot.message_handler(func=lambda message: message.chat.id in user_states, content_types=['text', 'photo', 'video', 'document'])
def handle_user_input(message):
    user_data = user_states.get(message.chat.id)
    state = user_data.get('state')
    
    # --- АДМІН-ФУНКЦІЇ ---
    if state == 'waiting_broadcast':
        user_states.pop(message.chat.id)
        users = get_all_users()
        success = 0
        bot.send_message(message.chat.id, "⏳ Начинаю рассылку...")
        for uid in users:
            try:
                bot.copy_message(uid, message.chat.id, message.message_id)
                success += 1
            except: pass
        return bot.send_message(message.chat.id, f"✅ Разослано: {success} пользователям.", reply_markup=get_admin_kb())

    if state in ['waiting_ban', 'waiting_unban']:
        user_states.pop(message.chat.id)
        try:
            target_id = int(message.text.strip())
            is_ban = (state == 'waiting_ban')
            set_ban_status(target_id, 1 if is_ban else 0)
            status_text = "заблокирован ⛔️" if is_ban else "разблокирован ✅"
            return bot.send_message(message.chat.id, f"Пользователь <code>{target_id}</code> успешно {status_text}.", reply_markup=get_admin_kb())
        except ValueError:
            return bot.send_message(message.chat.id, "❌ Ошибка! Нужно отправить только цифры (ID).", reply_markup=get_admin_kb())

    # --- ІНТЕРАКТИВНА АНКЕТА В АДМІНИ ---
    if state.startswith('apply_step_'):
        if not message.text:
            return bot.send_message(message.chat.id, "⚠️ Пожалуйста, отправьте текст.", reply_markup=get_cancel_kb())
            
        if state == 'apply_step_1':
            user_states[message.chat.id]['answers']['name_age'] = message.text
            user_states[message.chat.id]['state'] = 'apply_step_2'
            return bot.send_message(message.chat.id, "📝 <b>Шаг 2 из 3:</b>\nКакой у вас опыт игры на RP-проектах и почему вы хотите стать админом?", reply_markup=get_cancel_kb())
            
        elif state == 'apply_step_2':
            user_states[message.chat.id]['answers']['experience'] = message.text
            user_states[message.chat.id]['state'] = 'apply_step_3'
            return bot.send_message(message.chat.id, "📝 <b>Шаг 3 из 3:</b>\nСколько часов в день вы готовы уделять проекту?", reply_markup=get_cancel_kb())
            
        elif state == 'apply_step_3':
            answers = user_states[message.chat.id]['answers']
            user_states.pop(message.chat.id)
            
            username = f"@{message.from_user.username}" if message.from_user.username else "Анонимный"
            app_text = f"📝 <b>НОВАЯ ЗАЯВКА В АДМИНЫ</b>\n👤 От: {username}\n🔑 ID: <code>{message.chat.id}</code>\n━━━━━━━━━━━━━━━━━━\n<b>1. Имя/Возраст:</b> {answers['name_age']}\n<b>2. Опыт:</b> {answers['experience']}\n<b>3. Онлайн:</b> {message.text}"
            
            for target in list(OWNERS) + [ADMIN_GROUP_ID]:
                try: bot.send_message(target, app_text)
                except: pass
            
            inc_ticket_count()
            return bot.send_message(message.chat.id, "✅ Ваша заявка успешно отправлена руководству! Ожидайте ответа.", reply_markup=get_start_kb())

    # --- ЗВИЧАЙНІ ТІКЕТИ ---
    if state == 'waiting_ticket':
        user_data = user_states.pop(message.chat.id)
        category = user_data['category']
        username = f"@{message.from_user.username}" if message.from_user.username else "Анонимный"
        header = f"📌 <b>{category}</b>\n👤 От: {username}\n🔑 ID: <code>{message.chat.id}</code>\n━━━━━━━━━━━━━━━━━━"
        
        for target in list(OWNERS) + [ADMIN_GROUP_ID]:
            try:
                if message.content_type == 'text':
                    bot.send_message(target, f"{header}\n{message.text.replace('<', '&lt;').replace('>', '&gt;')}")
                else:
                    bot.send_message(target, header)
                    bot.copy_message(target, message.chat.id, message.message_id)
            except: pass

        inc_ticket_count()
        bot.send_message(message.chat.id, "✅ Ваше обращение отправлено. Руководство скоро вам ответит.", reply_markup=get_start_kb())


# === ВІДПОВІДІ КЕРІВНИЦТВА (REPLY В ЛС ТА ГРУПІ) ===
@bot.message_handler(func=lambda message: (str(message.chat.id) == str(ADMIN_GROUP_ID) or message.chat.id in OWNERS) and message.reply_to_message is not None)
def handle_admin_reply(message):
    if message.reply_to_message.from_user.id != bot.get_me().id:
        return

    bot_text = message.reply_to_message.text or message.reply_to_message.caption or ""
    match = re.search(r"ID:\s*(\d+)", bot_text)
    
    if match:
        target_id = int(match.group(1))
        safe_reply = message.text.replace('<', '&lt;').replace('>', '&gt;')
        official_reply = f"🛡 <b>Ответ руководства DragPolit:</b>\n\n<i>{safe_reply}</i>"
        
        try:
            bot.send_message(target_id, official_reply)
            bot.reply_to(message, "✅ Ответ успешно доставлен.")
        except:
            bot.reply_to(message, "⚠️ Ошибка доставки (пользователь заблокировал бота).")
    else:
        bot.reply_to(message, "❌ Не удалось найти ID. Делайте Reply на сообщение бота с заголовком.")


# === RENDER WEB-СЕРВЕР ТА БЕЗПЕЧНИЙ ЗАПУСК ===
app = Flask(__name__)
@app.route('/')
def keep_alive(): return "DragPolit Support Engine is Active!"

def run_web_server():
    app.run(host="0.0.0.0", port=int(os.environ.get("PORT", 10000)))

def start_bot():
    try: bot.delete_webhook(drop_pending_updates=True)
    except: pass

    while True:
        try:
            print("Бот DragPolit підключений до серверів Telegram...")
            bot.infinity_polling(timeout=10, long_polling_timeout=5, none_stop=True)
        except telebot.apihelper.ApiTelegramException as e:
            if e.error_code == 409:
                print("⚠️ Конфлікт (409): Чекаємо закриття старого процесу...")
                time.sleep(15)
            else:
                time.sleep(5)
        except Exception as e:
            print(f"Помилка: {e}. Перезапуск...")
            time.sleep(5)

if __name__ == '__main__':
    threading.Thread(target=run_web_server, daemon=True).start()
    start_bot()
