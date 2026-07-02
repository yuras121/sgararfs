import os
import time
import threading
import sqlite3
import telebot
from telebot import types
from flask import Flask
from datetime import datetime

# === НАЛАШТУВАННЯ ===
TOKEN = os.environ.get('TOKEN', '8252581199:AAHNfedYh1MrQVNBrL6mYf6OJVoTim_dApM')
OWNERS = [1614259542, 7716987740] 

bot = telebot.TeleBot(TOKEN, parse_mode='HTML')
user_states = {}

# === БАЗА ДАНИХ (SQLite) ===
DB_FILE = 'dragpolit.db'

def init_db():
    conn = sqlite3.connect(DB_FILE)
    c = conn.cursor()
    # Користувачі
    c.execute('''CREATE TABLE IF NOT EXISTS users 
                 (user_id INTEGER PRIMARY KEY, username TEXT, is_banned INTEGER DEFAULT 0, join_date TEXT)''')
    # Статистика
    c.execute('''CREATE TABLE IF NOT EXISTS stats (key TEXT PRIMARY KEY, value INTEGER)''')
    c.execute("INSERT OR IGNORE INTO stats (key, value) VALUES ('total_tickets', 0)")
    # ІСТОРІЯ ПОВІДОМЛЕНЬ
    c.execute('''CREATE TABLE IF NOT EXISTS history 
                 (id INTEGER PRIMARY KEY AUTOINCREMENT, user_id INTEGER, direction TEXT, text TEXT, timestamp TEXT)''')
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

def log_message(user_id, direction, text):
    # direction: 'in' (від гравця), 'out' (від адміна)
    conn = sqlite3.connect(DB_FILE)
    c = conn.cursor()
    date_str = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    c.execute("INSERT INTO history (user_id, direction, text, timestamp) VALUES (?, ?, ?, ?)", 
              (user_id, direction, text, date_str))
    conn.commit()
    conn.close()

def get_all_users():
    conn = sqlite3.connect(DB_FILE)
    c = conn.cursor()
    c.execute("SELECT user_id FROM users WHERE is_banned = 0")
    users = [row[0] for row in c.fetchall()]
    conn.close()
    return users

def get_full_users_data():
    conn = sqlite3.connect(DB_FILE)
    c = conn.cursor()
    c.execute("SELECT user_id, username, join_date, is_banned FROM users")
    data = c.fetchall()
    conn.close()
    return data

def get_history_export():
    conn = sqlite3.connect(DB_FILE)
    c = conn.cursor()
    c.execute("SELECT user_id, direction, text, timestamp FROM history ORDER BY timestamp ASC")
    data = c.fetchall()
    conn.close()
    
    content = "=== ИСТОРИЯ ВСЕХ ОБРАЩЕНИЙ DRAGPOLIT ===\n\n"
    for row in data:
        direction = "➡️ ОТ ИГРОКА" if row[1] == 'in' else "⬅️ ОТВЕТ РУКОВОДСТВА"
        content += f"Время: {row[3]}\nID: {row[0]}\nНаправление: {direction}\nТекст: {row[2]}\n{'-'*40}\n"
    return content

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
        types.InlineKeyboardButton("⛔️ Забанить ID", callback_data="admin_ban"),
        types.InlineKeyboardButton("✅ Разбанить ID", callback_data="admin_unban"),
        types.InlineKeyboardButton("📁 База юзеров", callback_data="admin_export"),
        types.InlineKeyboardButton("🗂 История тикетов", callback_data="admin_history")
    )
    return markup

# Динамічна клавіатура для кожного повідомлення, що приходить адмінам
def get_ticket_action_kb(user_id):
    markup = types.InlineKeyboardMarkup(row_width=2)
    markup.add(
        types.InlineKeyboardButton("✍️ Ответить", callback_data=f"ans_{user_id}"),
        types.InlineKeyboardButton("✅ Закрыть тикет", callback_data=f"close_{user_id}")
    )
    markup.add(types.InlineKeyboardButton("⛔️ Забанить", callback_data=f"tban_{user_id}"))
    return markup


# === КОМАНДИ ===
@bot.message_handler(commands=['start'])
def start_command(message):
    user_id = message.chat.id
    username = f"@{message.from_user.username}" if message.from_user.username else "Анонимный"
    
    is_new = add_user(user_id, username)
    if is_new:
        for owner in OWNERS:
            try: bot.send_message(owner, f"👤 <b>Новый игрок в боте!</b>\nЮзер: {username} | ID: <code>{user_id}</code>")
            except: pass

    if is_banned(user_id):
        return bot.send_message(user_id, "⛔️ <b>Вы заблокированы</b> и не можете обращаться в поддержку.")

    user_states.pop(user_id, None)
    text = "<b>Официальная служба поддержки DragPolit</b>\n\nВыберите раздел. Спам наказуем блокировкой."
    bot.send_message(user_id, text, reply_markup=get_start_kb())

@bot.message_handler(commands=['admin'])
def admin_panel_command(message):
    if message.chat.id not in OWNERS:
        return bot.reply_to(message, "⛔️ У вас нет доступа.")
    bot.send_message(message.chat.id, "👑 <b>Панель управления Владельцев</b>:", reply_markup=get_admin_kb())


# === АДМІН-КНОПКИ ГОЛОВНОГО МЕНЮ (/admin) ===
@bot.callback_query_handler(func=lambda call: call.data.startswith('admin_'))
def handle_admin_callbacks(call):
    if call.message.chat.id not in OWNERS:
        return bot.answer_callback_query(call.id, "Нет доступа!")
    
    action = call.data.split('_')[1]
    
    if action == 'stats':
        t_users, b_users, t_tickets = get_stats()
        text = f"📊 <b>Статистика:</b>\n👥 Юзеров: <b>{t_users}</b>\n⛔️ В бане: <b>{b_users}</b>\n📩 Обращений: <b>{t_tickets}</b>"
        bot.edit_message_text(text, call.message.chat.id, call.message.message_id, reply_markup=get_admin_kb())
        
    elif action == 'export':
        data = get_full_users_data()
        file_content = "=== БАЗА ЮЗЕРОВ ===\n\n"
        for row in data:
            status = "[БАН]" if row[3] == 1 else "[ОК]"
            file_content += f"ID: {row[0]} | Юзер: {row[1]} | Дата: {row[2]} | Статус: {status}\n"
        with open("users.txt", "w", encoding="utf-8") as f: f.write(file_content)
        with open("users.txt", "rb") as f: bot.send_document(call.message.chat.id, f)
        
    elif action == 'history':
        hist_text = get_history_export()
        with open("history.txt", "w", encoding="utf-8") as f: f.write(hist_text)
        with open("history.txt", "rb") as f: bot.send_document(call.message.chat.id, f, caption="🗂 Полная история переписок")

    elif action == 'broadcast':
        user_states[call.message.chat.id] = {'state': 'waiting_broadcast'}
        bot.edit_message_text("📢 Отправьте сообщение для рассылки:", call.message.chat.id, call.message.message_id, reply_markup=get_cancel_kb())


# === ВНУТРІШНІ АДМІН-ДІЇ (Відповісти / Закрити / Бан) З ПОВІДОМЛЕНЬ ===
@bot.callback_query_handler(func=lambda call: call.data.startswith(('ans_', 'close_', 'tban_')))
def handle_ticket_actions(call):
    if call.message.chat.id not in OWNERS: return
    
    parts = call.data.split('_')
    action = parts[0]
    target_id = int(parts[1])
    
    if action == 'ans':
        user_states[call.message.chat.id] = {'state': 'typing_reply', 'target': target_id}
        bot.send_message(call.message.chat.id, f"✍️ <b>Введите ответ</b> для пользователя <code>{target_id}</code>:\n<i>(Можно прикрепить фото/видео)</i>", reply_markup=get_cancel_kb())
        bot.answer_callback_query(call.id)
        
    elif action == 'close':
        # Прибираємо кнопки під повідомленням
        bot.edit_message_reply_markup(call.message.chat.id, call.message.message_id, reply_markup=None)
        bot.answer_callback_query(call.id, "✅ Тикет закрыт!")
        
    elif action == 'tban':
        set_ban_status(target_id, 1)
        bot.edit_message_reply_markup(call.message.chat.id, call.message.message_id, reply_markup=None)
        bot.send_message(call.message.chat.id, f"⛔️ Пользователь <code>{target_id}</code> забанен.")
        bot.answer_callback_query(call.id, "Заблокирован!")


@bot.callback_query_handler(func=lambda call: call.data == 'cancel_action')
def cancel_action(call):
    user_states.pop(call.message.chat.id, None)
    bot.edit_message_text("❌ Действие отменено.", call.message.chat.id, call.message.message_id)


# === ОБРОБКА ТЕКСТУ ВІД КОРИСТУВАЧІВ ТА АДМІНІВ ===
@bot.message_handler(func=lambda message: True, content_types=['text', 'photo', 'video', 'document', 'voice'])
def handle_all_messages(message):
    state_data = user_states.get(message.chat.id, {})
    state = state_data.get('state')

    # 1. АДМІН ВІДПОВІДАЄ НА ТІКЕТ
    if message.chat.id in OWNERS and state == 'typing_reply':
        target_id = state_data['target']
        user_states.pop(message.chat.id) # Очищаємо стан
        
        reply_text = message.text if message.text else "[Медіафайл]"
        log_message(target_id, 'out', reply_text) # Записуємо в історію
        
        official_text = f"🛡 <b>Ответ руководства DragPolit:</b>\n\n"
        try:
            if message.content_type == 'text':
                bot.send_message(target_id, official_text + message.text.replace('<', '&lt;').replace('>', '&gt;'))
            else:
                bot.send_message(target_id, official_text)
                bot.copy_message(target_id, message.chat.id, message.message_id)
            bot.send_message(message.chat.id, "✅ Успешно отправлено!")
        except Exception:
            bot.send_message(message.chat.id, "⚠️ Ошибка. Юзер заблокировал бота.")
        return

    # 2. АДМІН РОБИТЬ РОЗСИЛКУ
    if message.chat.id in OWNERS and state == 'waiting_broadcast':
        user_states.pop(message.chat.id)
        users = get_all_users()
        success = 0
        bot.send_message(message.chat.id, "⏳ Рассылка пошла...")
        for uid in users:
            try:
                bot.copy_message(uid, message.chat.id, message.message_id)
                success += 1
            except: pass
        return bot.send_message(message.chat.id, f"✅ Разослано: {success} юзерам.")

    # 3. КОРИСТУВАЧІ В БАНІ
    if is_banned(message.chat.id):
        return

    # 4. ЗАПОВНЕННЯ АНКЕТИ ЮЗЕРОМ
    if state and state.startswith('apply_step_'):
        if not message.text:
            return bot.send_message(message.chat.id, "⚠️ Отправьте текст.")
        if state == 'apply_step_1':
            user_states[message.chat.id]['answers']['name_age'] = message.text
            user_states[message.chat.id]['state'] = 'apply_step_2'
            return bot.send_message(message.chat.id, "📝 <b>Шаг 2 из 3:</b>\nОпыт игры на RP-проектах и почему вы?")
        elif state == 'apply_step_2':
            user_states[message.chat.id]['answers']['experience'] = message.text
            user_states[message.chat.id]['state'] = 'apply_step_3'
            return bot.send_message(message.chat.id, "📝 <b>Шаг 3 из 3:</b>\nСколько часов готовы уделять?")
        elif state == 'apply_step_3':
            answers = user_states[message.chat.id]['answers']
            user_states.pop(message.chat.id)
            username = f"@{message.from_user.username}" if message.from_user.username else "Анонимный"
            app_text = f"📝 <b>НОВАЯ ЗАЯВКА В АДМИНЫ</b>\n👤 От: {username}\n🔑 ID: <code>{message.chat.id}</code>\n━━━━━━━━━━━━━━━━━━\n<b>1. Имя/Возраст:</b> {answers['name_age']}\n<b>2. Опыт:</b> {answers['experience']}\n<b>3. Онлайн:</b> {message.text}"
            
            log_message(message.chat.id, 'in', "[Подал заявку в админы]")
            inc_ticket_count()
            
            for owner in OWNERS:
                try: bot.send_message(owner, app_text, reply_markup=get_ticket_action_kb(message.chat.id))
                except: pass
            return bot.send_message(message.chat.id, "✅ Заявка отправлена!")

    # 5. ГРАВЕЦЬ ПИШЕ ТІКЕТ АБО ПРОСТО ТЕКСТ (CATCH-ALL)
    if message.chat.id not in OWNERS:
        category = "💬 Свободное сообщение"
        if state == 'waiting_ticket':
            category = user_states[message.chat.id]['category']
            user_states.pop(message.chat.id)
            bot.send_message(message.chat.id, "✅ Ваше обращение отправлено.")
        else:
            bot.send_message(message.chat.id, "🤖 Я передал ваше сообщение руководству. \n<i>Для быстрой связи используйте меню: /start</i>")
            
        username = f"@{message.from_user.username}" if message.from_user.username else "Анонимный"
        header = f"📌 <b>{category}</b>\n👤 От: {username}\n🔑 ID: <code>{message.chat.id}</code>\n━━━━━━━━━━━━━━━━━━"
        
        msg_text = message.text if message.text else "[Медіафайл]"
        log_message(message.chat.id, 'in', f"[{category}] {msg_text}")
        inc_ticket_count()

        for owner in OWNERS:
            try:
                if message.content_type == 'text':
                    bot.send_message(owner, f"{header}\n{message.text.replace('<', '&lt;').replace('>', '&gt;')}", reply_markup=get_ticket_action_kb(message.chat.id))
                else:
                    msg = bot.send_message(owner, header)
                    bot.copy_message(owner, message.chat.id, message.message_id, reply_markup=get_ticket_action_kb(message.chat.id))
            except: pass


# === МЕНЮ КОРИСТУВАЧІВ (Обробка натискань меню) ===
@bot.callback_query_handler(func=lambda call: call.data.startswith('type_'))
def handle_main_menu(call):
    if is_banned(call.message.chat.id):
        return bot.answer_callback_query(call.id, "Вы заблокированы!", show_alert=True)
    action = call.data.split('_')[1]
    
    if action == 'apply':
        user_states[call.message.chat.id] = {'state': 'apply_step_1', 'answers': {}}
        return bot.edit_message_text("📝 <b>Шаг 1 из 3:</b>\nНапишите Имя и Возраст:", call.message.chat.id, call.message.message_id, reply_markup=get_cancel_kb())
    elif action == 'bug': text, cat = "🛠 <b>Баг-репорт</b>\nОпишите проблему:", "Баг-репорт"
    elif action == 'urgent': text, cat = "🚨 <b>ЧП</b>\nПодробно опишите проблему:", "ЧП / Срочно"
    elif action == 'collab': text, cat = "🤝 <b>Сотрудничество</b>\nОпишите предложение:", "Сотрудничество"
        
    user_states[call.message.chat.id] = {'state': 'waiting_ticket', 'category': cat}
    bot.edit_message_text(text, call.message.chat.id, call.message.message_id, reply_markup=get_cancel_kb())


# === ЗАПУСК ===
app = Flask(__name__)
@app.route('/')
def keep_alive(): return "DragPolit CRM is Active!"

def run_web_server():
    app.run(host="0.0.0.0", port=int(os.environ.get("PORT", 10000)))

def start_bot():
    try: bot.delete_webhook(drop_pending_updates=True)
    except: pass
    while True:
        try:
            print("Бот DragPolit CRM підключений...")
            bot.infinity_polling(timeout=10, long_polling_timeout=5, none_stop=True)
        except Exception as e:
            time.sleep(5)

if __name__ == '__main__':
    threading.Thread(target=run_web_server, daemon=True).start()
    start_bot()
