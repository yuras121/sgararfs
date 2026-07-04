import os
import time
import threading
import sqlite3
import telebot
from telebot import types
from flask import Flask
from datetime import datetime

# ==========================================
# 1. КОНФИГУРАЦИЯ СИСТЕМЫ И ДОСТУПЫ
# ==========================================
TOKEN = os.environ.get('TOKEN', '8252581199:AAHNfedYh1MrQVNBrL6mYf6OJVoTim_dApM')

# ID Владельцев (Управление исключительно из ЛС)
OWNERS = [1614259542, 7716987740] 

bot = telebot.TeleBot(TOKEN, parse_mode='HTML')
user_states = {}

# ==========================================
# 2. ЯДРО БАЗЫ ДАННЫХ (ENTERPRISE SQLITE)
# ==========================================
DB_FILE = 'dragpolit_enterprise.db'

def init_db():
    conn = sqlite3.connect(DB_FILE)
    c = conn.cursor()
    c.execute('''CREATE TABLE IF NOT EXISTS users 
                 (user_id INTEGER PRIMARY KEY, username TEXT, is_banned INTEGER DEFAULT 0, join_date TEXT)''')
    c.execute('''CREATE TABLE IF NOT EXISTS stats (key TEXT PRIMARY KEY, value INTEGER)''')
    c.execute("INSERT OR IGNORE INTO stats (key, value) VALUES ('total_tickets', 0)")
    c.execute('''CREATE TABLE IF NOT EXISTS vacancies 
                 (id INTEGER PRIMARY KEY AUTOINCREMENT, title TEXT, description TEXT, is_active INTEGER DEFAULT 1)''')
    
    c.execute("SELECT COUNT(*) FROM vacancies")
    if c.fetchone()[0] == 0:
        start_desc = (
            "<b>Официальные требования Кадрового отдела DragPolit:</b>\n"
            "• Возраст от 15 лет (возможны исключения по решению высшего руководства).\n"
            "• Идеальное знание RP-регламента, терминологии и игровых механик проекта.\n"
            "• Грамотная письменная речь, беспристрастность, хладнокровие и стрессоустойчивость.\n"
            "• Наличие свободного времени и суточный онлайн строго от 3-х часов."
        )
        c.execute("INSERT INTO vacancies (title, description, is_active) VALUES (?, ?, ?)", 
                  ("Младший Модератор / Стажер", start_desc, 1))
    
    c.execute('''CREATE TABLE IF NOT EXISTS history 
                 (id INTEGER PRIMARY KEY AUTOINCREMENT, user_id INTEGER, direction TEXT, text TEXT, timestamp TEXT)''')
    c.execute('''CREATE TABLE IF NOT EXISTS admin_audit 
                 (id INTEGER PRIMARY KEY AUTOINCREMENT, admin_id INTEGER, admin_username TEXT, action TEXT, target_id INTEGER, timestamp TEXT)''')
    conn.commit()
    conn.close()

def get_all_vacancies(only_active=False):
    conn = sqlite3.connect(DB_FILE)
    c = conn.cursor()
    if only_active:
        c.execute("SELECT id, title, description FROM vacancies WHERE is_active = 1")
    else:
        c.execute("SELECT id, title, description, is_active FROM vacancies")
    res = c.fetchall()
    conn.close()
    return res

def get_vacancy(vac_id):
    conn = sqlite3.connect(DB_FILE)
    c = conn.cursor()
    c.execute("SELECT id, title, description, is_active FROM vacancies WHERE id = ?", (vac_id,))
    res = c.fetchone()
    conn.close()
    return res

def add_vacancy(title, desc):
    conn = sqlite3.connect(DB_FILE)
    c = conn.cursor()
    c.execute("INSERT INTO vacancies (title, description, is_active) VALUES (?, ?, 1)", (title, desc))
    conn.commit()
    conn.close()

def toggle_vacancy(vac_id):
    conn = sqlite3.connect(DB_FILE)
    c = conn.cursor()
    c.execute("UPDATE vacancies SET is_active = CASE WHEN is_active = 1 THEN 0 ELSE 1 END WHERE id = ?", (vac_id,))
    conn.commit()
    conn.close()

def delete_vacancy(vac_id):
    conn = sqlite3.connect(DB_FILE)
    c = conn.cursor()
    c.execute("DELETE FROM vacancies WHERE id = ?", (vac_id,))
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
    conn = sqlite3.connect(DB_FILE)
    c = conn.cursor()
    date_str = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    c.execute("INSERT INTO history (user_id, direction, text, timestamp) VALUES (?, ?, ?, ?)", 
              (user_id, direction, text, date_str))
    conn.commit()
    conn.close()

def log_admin_action(admin_id, admin_username, action, target_id):
    conn = sqlite3.connect(DB_FILE)
    c = conn.cursor()
    date_str = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    c.execute("INSERT INTO admin_audit (admin_id, admin_username, action, target_id, timestamp) VALUES (?, ?, ?, ?, ?)", 
              (admin_id, admin_username, action, target_id, date_str))
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
    c.execute("SELECT user_id, username, join_date, is_banned FROM users ORDER BY join_date DESC")
    data = c.fetchall()
    conn.close()
    return data

def get_history_export():
    conn = sqlite3.connect(DB_FILE)
    c = conn.cursor()
    c.execute("SELECT user_id, direction, text, timestamp FROM history ORDER BY timestamp DESC LIMIT 500")
    data = c.fetchall()
    conn.close()
    content = "=== ОФИЦИАЛЬНЫЙ РЕЕСТР ОБРАЩЕНИЙ DRAGPOLIT ===\n\n"
    for row in data:
        dir_text = "[ПОСТУПЛЕНИЕ]" if row[1] == 'in' else "[ОТВЕТ РУКОВОДСТВА]"
        content += f"[{row[3]}] ID: {row[0]} | {dir_text}\nСодержание: {row[2]}\n{'-'*50}\n"
    return content

def get_audit_export():
    conn = sqlite3.connect(DB_FILE)
    c = conn.cursor()
    c.execute("SELECT admin_id, admin_username, action, target_id, timestamp FROM admin_audit ORDER BY timestamp DESC LIMIT 300")
    data = c.fetchall()
    conn.close()
    content = "=== СЛУЖЕБНЫЙ АУДИТ ДЕЙСТВИЙ РУКОВОДСТВА ===\n\n"
    for row in data:
        content += f"[{row[4]}] Руководитель: {row[1]} (ID: {row[0]})\nДействие: {row[2]} -> Цель ID: {row[3]}\n{'-'*50}\n"
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

# ==========================================
# 3. ИНТЕРФЕЙСЫ И СЛУЖЕБНЫЕ КЛАВИАТУРЫ
# ==========================================
def get_start_kb():
    markup = types.InlineKeyboardMarkup(row_width=1)
    markup.add(
        types.InlineKeyboardButton("⚖️ Жалоба на Администрацию проекта", callback_data="type_adminreport"),
        types.InlineKeyboardButton("👤 Жалоба на Игрока (Разъяснение)", callback_data="type_playerreport"),
        types.InlineKeyboardButton("🚨 Критический сбой / Экстренная связь", callback_data="type_urgent"),
        types.InlineKeyboardButton("🤝 Коммерческий и партнерский отдел", callback_data="type_collab"),
        types.InlineKeyboardButton("🛠 Технический отдел (Отчет об ошибке)", callback_data="type_bug"),
        types.InlineKeyboardButton("📋 Кадровый отдел (Открытые вакансии)", callback_data="type_apply")
    )
    return markup

def get_cancel_kb():
    markup = types.InlineKeyboardMarkup()
    markup.add(types.InlineKeyboardButton("❌ Отменить действие", callback_data="cancel_action"))
    return markup

def get_admin_kb():
    markup = types.InlineKeyboardMarkup(row_width=1)
    markup.add(types.InlineKeyboardButton("💼 Управление вакансиями (Мульти-система)", callback_data="admin_vac_menu"))
    markup.row(
        types.InlineKeyboardButton("📢 Оповещение", callback_data="admin_broadcast"),
        types.InlineKeyboardButton("📊 Аналитика", callback_data="admin_stats")
    )
    markup.row(
        types.InlineKeyboardButton("⛔️ Забанить ID", callback_data="admin_ban"),
        types.InlineKeyboardButton("✅ Разбанить ID", callback_data="admin_unban")
    )
    markup.row(
        types.InlineKeyboardButton("📁 Реестр юзеров", callback_data="admin_export"),
        types.InlineKeyboardButton("🗂 Журнал тикетов", callback_data="admin_history")
    )
    markup.add(types.InlineKeyboardButton("🛡 Служебный аудит админов", callback_data="admin_audit"))
    return markup

def get_vac_admin_menu_kb():
    markup = types.InlineKeyboardMarkup(row_width=1)
    markup.add(
        types.InlineKeyboardButton("➕ Добавить новую вакансию", callback_data="vacadmin_add"),
        types.InlineKeyboardButton("📋 Список вакансий (Открыть/Закрыть/Удалить)", callback_data="vacadmin_list"),
        types.InlineKeyboardButton("🔙 Вернуться в админ-панель", callback_data="vacadmin_back")
    )
    return markup

def get_vacancies_list_kb():
    vacs = get_all_vacancies(only_active=False)
    markup = types.InlineKeyboardMarkup(row_width=1)
    for vac in vacs:
        status_str = "🟢 Открыта" if vac[3] == 1 else "🔴 Закрыта"
        markup.add(types.InlineKeyboardButton(f"{status_str} | {vac[1]}", callback_data=f"vacmanage_{vac[0]}"))
    markup.add(types.InlineKeyboardButton("🔙 Вернуться к управлению", callback_data="admin_vac_menu"))
    return markup

def get_single_vac_manage_kb(vac_id):
    vac = get_vacancy(vac_id)
    toggle_text = "🔴 Закрыть вакансию (Скрыть от игроков)" if vac[3] == 1 else "🟢 Открыть вакансию (Показать игрокам)"
    markup = types.InlineKeyboardMarkup(row_width=1)
    markup.add(
        types.InlineKeyboardButton(toggle_text, callback_data=f"vactoggle_{vac_id}"),
        types.InlineKeyboardButton("❌ Удалить вакансию навсегда", callback_data=f"vacdel_{vac_id}"),
        types.InlineKeyboardButton("🔙 К списку вакансий", callback_data="vacadmin_list")
    )
    return markup

def get_public_vacancies_kb():
    vacs = get_all_vacancies(only_active=True)
    markup = types.InlineKeyboardMarkup(row_width=1)
    for vac in vacs:
        markup.add(types.InlineKeyboardButton(f"💼 {vac[1]}", callback_data=f"pubvac_{vac[0]}"))
    markup.add(types.InlineKeyboardButton("🔙 В главное меню", callback_data="cancel_action"))
    return markup

def get_apply_confirm_kb(vac_id):
    markup = types.InlineKeyboardMarkup(row_width=1)
    markup.add(
        types.InlineKeyboardButton("✍️ Подать анкету на эту должность", callback_data=f"applystart_{vac_id}"),
        types.InlineKeyboardButton("🔙 К списку вакансий", callback_data="type_apply")
    )
    return markup

def get_ticket_action_kb(user_id):
    markup = types.InlineKeyboardMarkup(row_width=2)
    markup.add(
        types.InlineKeyboardButton("📨 Ответить заявителю", callback_data=f"ans_{user_id}"),
        types.InlineKeyboardButton("📁 Закрыть тикет", callback_data=f"close_{user_id}")
    )
    markup.add(types.InlineKeyboardButton("⛔️ Блокировать нарушителя", callback_data=f"tban_{user_id}"))
    return markup

def notify_other_owners(sender_id, text):
    for owner in OWNERS:
        if owner != sender_id:
            try: bot.send_message(owner, f"🛡 <b>СЛУЖЕБНЫЙ АУДИТ ДЕЙСТВИЙ:</b>\n{text}")
            except Exception: pass

# ==========================================
# 5. ОБРАБОТЧИКИ КОМАНД
# ==========================================
@bot.message_handler(commands=['start'])
def start_command(message):
    user_id = message.chat.id
    username = f"@{message.from_user.username}" if message.from_user.username else "ID:" + str(user_id)
    
    is_new = add_user(user_id, username)
    if is_new:
        for owner in OWNERS:
            try: bot.send_message(owner, f"👤 <b>Новая регистрация в системе DragPolit:</b>\nСубъект: {username} | ID: <code>{user_id}</code>")
            except Exception: pass

    if is_banned(user_id):
        return bot.send_message(user_id, "⛔️ <b>Доступ ограничен.</b> Обслуживание вашей учетной записи приостановлено.")

    user_states.pop(user_id, None)
    text = (
        "🏛 <b>Официальный портал поддержки проекта DragPolit</b>\n\n"
        "Добро пожаловать. Данная система предназначена для коммуникации с высшим руководством проекта.\n\n"
        "⚠️ <i>Обратите внимание: подача заведомо ложных обращений преследуется блокировкой доступа. Выберите профильный отдел:</i>"
    )
    bot.send_message(user_id, text, reply_markup=get_start_kb())

@bot.message_handler(commands=['admin'])
def admin_panel_command(message):
    if message.chat.id not in OWNERS:
        return bot.reply_to(message, "⛔️ Ошибка доступа: недостаточный уровень привилегий.")
    bot.send_message(message.chat.id, "👑 <b>Терминал управления высшего руководства DragPolit:</b>", reply_markup=get_admin_kb())

@bot.message_handler(commands=['get_id'])
def get_id_command(message):
    bot.reply_to(message, f"Ваш системный ID: <code>{message.chat.id}</code>")

# ==========================================
# 6. НАВИГАЦИЯ ПО МЕНЮ И УПРАВЛЕНИЕ ВАКАНСИЯМИ
# ==========================================
@bot.callback_query_handler(func=lambda call: call.data == 'cancel_action')
def cancel_action(call):
    user_states.pop(call.message.chat.id, None)
    bot.edit_message_text("⭕️ Действие прервано. Возврат в главное меню.", call.message.chat.id, call.message.message_id, reply_markup=get_start_kb())

@bot.callback_query_handler(func=lambda call: call.data.startswith('vacadmin_'))
def handle_vac_admin_menu(call):
    if call.message.chat.id not in OWNERS: return
    action = call.data.split('_')[1]
    
    if action == 'add':
        user_states[call.message.chat.id] = {'state': 'addvac_title'}
        bot.edit_message_text("➕ <b>ДОБАВЛЕНИЕ НОВОЙ ВАКАНСИИ (Шаг 1 из 2)</b>\n\n👉 Отправьте следующим сообщением <b>название должности</b> (например: <i>Модератор Discord</i>):", call.message.chat.id, call.message.message_id, reply_markup=get_cancel_kb())
    elif action == 'list':
        bot.edit_message_text("📋 <b>СПИСОК ВСЕХ ВАКАНСИЙ СИСТЕМЫ:</b>\nВыберите вакансию для управления её статусом или удаления:", call.message.chat.id, call.message.message_id, reply_markup=get_vacancies_list_kb())
    elif action == 'back':
        bot.edit_message_text("👑 <b>Терминал управления высшего руководства DragPolit:</b>", call.message.chat.id, call.message.message_id, reply_markup=get_admin_kb())

@bot.callback_query_handler(func=lambda call: call.data.startswith(('vacmanage_', 'vactoggle_', 'vacdel_')))
def handle_single_vac_manage(call):
    if call.message.chat.id not in OWNERS: return
    parts = call.data.split('_')
    action = parts[0]
    vac_id = int(parts[1])
    admin_name = f"@{call.from_user.username}" if call.from_user.username else f"ID:{call.from_user.id}"
    
    if action == 'vacmanage':
        vac = get_vacancy(vac_id)
        if not vac: return
        status_str = "🟢 Открыта (Видна игрокам)" if vac[3] == 1 else "🔴 Закрыта (Скрыта от игроков)"
        text = f"💼 <b>Управление вакансией #{vac[0]}</b>\n\n<b>Название:</b> {vac[1]}\n<b>Текущий статус:</b> {status_str}\n\n<b>Описание и требования:</b>\n{vac[2]}"
        bot.edit_message_text(text, call.message.chat.id, call.message.message_id, reply_markup=get_single_vac_manage_kb(vac_id))
    elif action == 'vactoggle':
        toggle_vacancy(vac_id)
        vac = get_vacancy(vac_id)
        log_admin_action(call.from_user.id, admin_name, f"Изменил статус вакансии #{vac_id}", 0)
        bot.answer_callback_query(call.id, "Статус вакансии успешно изменен!")
        status_str = "🟢 Открыта (Видна игрокам)" if vac[3] == 1 else "🔴 Закрыта (Скрыта от игроков)"
        text = f"💼 <b>Управление вакансией #{vac[0]}</b>\n\n<b>Название:</b> {vac[1]}\n<b>Текущий статус:</b> {status_str}\n\n<b>Описание и требования:</b>\n{vac[2]}"
        bot.edit_message_text(text, call.message.chat.id, call.message.message_id, reply_markup=get_single_vac_manage_kb(vac_id))
    elif action == 'vacdel':
        delete_vacancy(vac_id)
        log_admin_action(call.from_user.id, admin_name, f"Удалил вакансию #{vac_id}", 0)
        bot.answer_callback_query(call.id, "Вакансия удалена!")
        bot.edit_message_text("📋 <b>СПИСОК ВСЕХ ВАКАНСИЙ СИСТЕМЫ:</b>\nВыберите вакансию для управления её статусом или удаления:", call.message.chat.id, call.message.message_id, reply_markup=get_vacancies_list_kb())

@bot.callback_query_handler(func=lambda call: call.data.startswith('admin_'))
def handle_admin_callbacks(call):
    if call.message.chat.id not in OWNERS: return
    action = call.data.split('_')[1]
    
    if action == 'vac':
        bot.edit_message_text("💼 <b>УПРАВЛЕНИЕ КАДРОВЫМ ОТДЕЛОМ (Мульти-вакансии)</b>\nЗдесь вы можете добавлять новые должности, временно закрывать их от игроков или удалять.", call.message.chat.id, call.message.message_id, reply_markup=get_vac_admin_menu_kb())
    elif action == 'stats':
        t_users, b_users, t_tickets = get_stats()
        text = f"📊 <b>Аналитический отчет DragPolit:</b>\n\n👥 Зарегистрировано в базе: <b>{t_users}</b>\n⛔️ Заблокированных субьектов: <b>{b_users}</b>\n📩 Обработано обращений: <b>{t_tickets}</b>"
        bot.edit_message_text(text, call.message.chat.id, call.message.message_id, reply_markup=get_admin_kb())
    elif action == 'export':
        data = get_full_users_data()
        content = "=== ОФИЦИАЛЬНЫЙ РЕЕСТР ПОЛЬЗОВАТЕЛЕЙ DRAGPOLIT ===\n\n"
        for r in data:
            status = "[ЗАБЛОКИРОВАН]" if r[3] == 1 else "[АКТИВЕН]"
            content += f"ID: {r[0]} | Субъект: {r[1]} | Регистрация: {r[2]} | Статус: {status}\n"
        with open("dragpolit_users.txt", "w", encoding="utf-8") as f: f.write(content)
        with open("dragpolit_users.txt", "rb") as f: bot.send_document(call.message.chat.id, f, caption="📁 Полный реестр пользователей")
    elif action == 'history':
        content = get_history_export()
        with open("dragpolit_tickets.txt", "w", encoding="utf-8") as f: f.write(content)
        with open("dragpolit_tickets.txt", "rb") as f: bot.send_document(call.message.chat.id, f, caption="🗂 Официальный журнал обращений")
    elif action == 'audit':
        content = get_audit_export()
        with open("dragpolit_audit.txt", "w", encoding="utf-8") as f: f.write(content)
        with open("dragpolit_audit.txt", "rb") as f: bot.send_document(call.message.chat.id, f, caption="🛡 Служебный аудит руководства")
    elif action == 'broadcast':
        user_states[call.message.chat.id] = {'state': 'waiting_broadcast'}
        bot.edit_message_text("📢 <b>Подготовка официального оповещения:</b>\nОтправьте текст или медиаматериал для массовой рассылки по всем субъектам системы:", call.message.chat.id, call.message.message_id, reply_markup=get_cancel_kb())
    elif action == 'ban':
        user_states[call.message.chat.id] = {'state': 'waiting_ban'}
        bot.edit_message_text("⛔️ <b>Процедура блокировки:</b>\nВведите системный ID пользователя для бессрочного ограничения доступа:", call.message.chat.id, call.message.message_id, reply_markup=get_cancel_kb())
    elif action == 'unban':
        user_states[call.message.chat.id] = {'state': 'waiting_unban'}
        bot.edit_message_text("✅ <b>Процедура реабилитации:</b>\nВведите системный ID пользователя для восстановления доступа:", call.message.chat.id, call.message.message_id, reply_markup=get_cancel_kb())

@bot.callback_query_handler(func=lambda call: call.data.startswith(('ans_', 'close_', 'tban_')))
def handle_ticket_actions(call):
    if call.message.chat.id not in OWNERS: return
    parts = call.data.split('_')
    action = parts[0]
    target_id = int(parts[1])
    admin_name = f"@{call.from_user.username}" if call.from_user.username else f"ID:{call.from_user.id}"
    
    if action == 'ans':
        user_states[call.message.chat.id] = {'state': 'typing_reply', 'target': target_id}
        bot.send_message(call.message.chat.id, f"📨 <b>Подготовка официального ответа</b>\nРеспондент ID: <code>{target_id}</code>\n<i>Введите текст ответа:</i>", reply_markup=get_cancel_kb())
        bot.answer_callback_query(call.id)
    elif action == 'close':
        bot.edit_message_reply_markup(call.message.chat.id, call.message.message_id, reply_markup=None)
        log_admin_action(call.from_user.id, admin_name, "Закрыл тикет в архив", target_id)
        notify_other_owners(call.from_user.id, f"Руководитель {admin_name} закрыл тикет от субъекта ID <code>{target_id}</code>.")
        bot.answer_callback_query(call.id, "Обращение архивировано!")
    elif action == 'tban':
        set_ban_status(target_id, 1)
        bot.edit_message_reply_markup(call.message.chat.id, call.message.message_id, reply_markup=None)
        log_admin_action(call.from_user.id, admin_name, "Заблокировал субъекта", target_id)
        notify_other_owners(call.from_user.id, f"⚠️ Руководитель {admin_name} применил блокировку к субъекту ID <code>{target_id}</code>.")
        bot.send_message(call.message.chat.id, f"⛔️ Субъект <code>{target_id}</code> внесен в черный список.")
        bot.answer_callback_query(call.id, "Блокировка применена!")

@bot.callback_query_handler(func=lambda call: call.data.startswith(('type_', 'pubvac_', 'applystart_')))
def handle_main_menu(call):
    if is_banned(call.message.chat.id):
        return bot.answer_callback_query(call.id, "Доступ ограничен!", show_alert=True)
        
    if call.data.startswith('pubvac_'):
        vac_id = int(call.data.split('_')[1])
        vac = get_vacancy(vac_id)
        if not vac or vac[3] == 0:
            return bot.answer_callback_query(call.id, "Эта вакансия уже закрыта!", show_alert=True)
        text = f"🏛 <b>КАДРОВЫЙ ОТДЕЛ DRAGPOLIT</b>\n\n💼 <b>ВАКАНСИЯ: {vac[1].upper()}</b>\n\n{vac[2]}"
        return bot.edit_message_text(text, call.message.chat.id, call.message.message_id, reply_markup=get_apply_confirm_kb(vac_id))

    if call.data.startswith('applystart_'):
        vac_id = int(call.data.split('_')[1])
        vac = get_vacancy(vac_id)
        vac_title = vac[1] if vac else "Неизвестная должность"
        user_states[call.message.chat.id] = {'state': 'apply_step_1', 'vac_title': vac_title, 'answers': {}}
        return bot.edit_message_text(f"📋 <b>Анкетирование на должность «{vac_title}» (Этап 1 из 3):</b>\nУкажите ваши паспортные данные: Имя и реальный Возраст:", call.message.chat.id, call.message.message_id, reply_markup=get_cancel_kb())

    action = call.data.split('_')[1]
    
    # НОВЕ: Жалоба на звичайного ігрока (Автовідповідь без турбування вищого керівництва)
    if action == 'playerreport':
        info_text = (
            "👤 <b>РЕГЛАМЕНТ ПОДАЧИ ЖАЛОБ НА ИГРОКОВ</b>\n\n"
            "Высшее руководство DragPolit не занимается рассмотрением бытовых жалоб на обычных игроков или нарушений правил чата/игрового процесса в данном портале.\n\n"
            "👉 <b>Для подачи жалобы на игрока:</b>\n"
            "1. Воспользуйтесь внутриигровым репортом на сервере.\n"
            "2. Обратитесь в личные сообщения к действующему дежурному модератору в официальных каналах связи.\n\n"
            "<i>Высшее руководство рассматривает исключительно жалобы на неправомерные действия самой администрации проекта.</i>"
        )
        return bot.edit_message_text(info_text, call.message.chat.id, call.message.message_id, reply_markup=get_start_kb())

    elif action == 'apply':
        active_vacs = get_all_vacancies(only_active=True)
        if not active_vacs:
            closed_text = (
                "🏛 <b>КАДРОВЫЙ ОТДЕЛ DRAGPOLIT</b>\n\n"
                "🔴 <b>ОТКРЫТЫХ ВАКАНСИЙ НЕТ / НАБОР ЗАКРЫТ</b>\n\n"
                "На текущий момент штат администрации и модерации проекта полностью укомплектован. Прием новых анкет временно приостановлен руководством.\n\n"
                "<i>Следите за новостями проекта, чтобы не пропустить открытие следующей волны набора.</i>"
            )
            return bot.edit_message_text(closed_text, call.message.chat.id, call.message.message_id, reply_markup=get_start_kb())
        else:
            text = "🏛 <b>КАДРОВЫЙ ОТДЕЛ DRAGPOLIT</b>\n\nВ настоящий момент открыты следующие вакансии. Выберите интересующую должность для ознакомления с требованиями:"
            return bot.edit_message_text(text, call.message.chat.id, call.message.message_id, reply_markup=get_public_vacancies_kb())

    elif action == 'adminreport': text, cat = "⚖️ <b>Жалоба на Администрацию:</b>\nУкажите никнейм администратора, дату/время инцидента и подробно опишите суть неправомерных действий (желательно прикрепить доказательства):", "Жалоба на Администрацию"
    elif action == 'bug': text, cat = "🛠 <b>Технический регламент:</b>\nПодробно опишите выявленный сбой:\n1. Суть ошибки\n2. Локация/механика\n3. Способ воспроизведения", "Технический отдел"
    elif action == 'urgent': text, cat = "🚨 <b>Экстренный регламент:</b>\nИзложите суть критической ситуации или сбоя. Запрос будет рассмотрен руководством в приоритетном порядке.", "Экстренное обращение"
    elif action == 'collab': text, cat = "🤝 <b>Коммерческий регламент:</b>\nИзложите суть коммерческого предложения с указанием контактов для связи.", "Партнерский отдел"
        
    user_states[call.message.chat.id] = {'state': 'waiting_ticket', 'category': cat}
    bot.edit_message_text(text, call.message.chat.id, call.message.message_id, reply_markup=get_cancel_kb())

# ==========================================
# 7. МАРШРУТИЗАЦИЯ И ПОТОКИ СООБЩЕНИЙ
# ==========================================
@bot.message_handler(func=lambda message: True, content_types=['text', 'photo', 'video', 'document', 'voice'])
def handle_all_messages(message):
    state_data = user_states.get(message.chat.id, {})
    state = state_data.get('state')
    admin_name = f"@{message.from_user.username}" if message.from_user.username else f"ID:{message.from_user.id}"

    if message.chat.id in OWNERS and state == 'addvac_title':
        if not message.text:
            return bot.send_message(message.chat.id, "❌ Отправьте название текстом.")
        user_states[message.chat.id] = {'state': 'addvac_desc', 'title': message.text}
        return bot.send_message(message.chat.id, f"➕ Название: <b>«{message.text}»</b>\n\n👉 Теперь следующим сообщением отправьте <b>описание и требования</b> к кандидатам на эту должность:", reply_markup=get_cancel_kb())

    if message.chat.id in OWNERS and state == 'addvac_desc':
        if not message.text:
            return bot.send_message(message.chat.id, "❌ Отправьте описание текстом.")
        title = state_data['title']
        add_vacancy(title, message.text)
        user_states.pop(message.chat.id)
        log_admin_action(message.from_user.id, admin_name, f"Создал вакансию «{title}»", 0)
        notify_other_owners(message.from_user.id, f"Руководитель {admin_name} добавил новую вакансию «{title}».")
        return bot.send_message(message.chat.id, f"✅ <b>Вакансия «{title}» успешно создана и открыта для игроков!</b>", reply_markup=get_admin_kb())

    if message.chat.id in OWNERS and state == 'typing_reply':
        target_id = state_data['target']
        user_states.pop(message.chat.id)
        reply_text = message.text if message.text else "[Прикрепленный медиаматериал]"
        log_message(target_id, 'out', reply_text)
        log_admin_action(message.from_user.id, admin_name, f"Ответил: {reply_text[:30]}...", target_id)
        notify_other_owners(message.from_user.id, f"Руководитель {admin_name} направил ответ субъекту <code>{target_id}</code>:\n<i>«{reply_text}»</i>")
        
        official_header = "🏛 <b>ОФИЦИАЛЬНЫЙ ОТВЕТ РУКОВОДСТВА DRAGPOLIT</b>\n━━━━━━━━━━━━━━━━━━━━━━━━━━━\n\n"
        try:
            if message.content_type == 'text':
                bot.send_message(target_id, official_header + message.text.replace('<', '&lt;').replace('>', '&gt;'))
            else:
                bot.send_message(target_id, official_header)
                bot.copy_message(target_id, message.chat.id, message.message_id)
            bot.send_message(message.chat.id, "✅ Официальный ответ успешно доставлен адресату.")
        except Exception:
            bot.send_message(message.chat.id, "⚠️ Сбой доставки: пользователь заблокировал портал поддержки.")
        return

    if message.chat.id in OWNERS and state == 'waiting_broadcast':
        user_states.pop(message.chat.id)
        users = get_all_users()
        success = 0
        bot.send_message(message.chat.id, "⏳ Инициирована массовая рассылка протокола...")
        for uid in users:
            try:
                bot.copy_message(uid, message.chat.id, message.message_id)
                success += 1
            except Exception: pass
        log_admin_action(message.from_user.id, admin_name, f"Запустил рассылку на {success} чел.", 0)
        notify_other_owners(message.from_user.id, f"📢 Руководитель {admin_name} произвел массовую рассылку. Доставлено: {success} субъектам.")
        return bot.send_message(message.chat.id, f"✅ Официальное оповещение доставлено: {success} субъектам.")

    if message.chat.id in OWNERS and state in ['waiting_ban', 'waiting_unban']:
        user_states.pop(message.chat.id)
        try:
            target_id = int(message.text.strip())
            is_ban = (state == 'waiting_ban')
            set_ban_status(target_id, 1 if is_ban else 0)
            status_text = "заблокирован ⛔️" if is_ban else "восстановлен в правах ✅"
            act_text = "Заблокировал (вручную)" if is_ban else "Разблокировал (вручную)"
            log_admin_action(message.from_user.id, admin_name, act_text, target_id)
            notify_other_owners(message.from_user.id, f"Руководитель {admin_name} изменил статус субъекта <code>{target_id}</code>: {status_text}.")
            return bot.send_message(message.chat.id, f"Субъект <code>{target_id}</code> {status_text}.", reply_markup=get_admin_kb())
        except ValueError:
            return bot.send_message(message.chat.id, "❌ Ошибка: системный ID должен состоять исключительно из цифр.", reply_markup=get_admin_kb())

    if is_banned(message.chat.id): return

    if state and state.startswith('apply_step_'):
        if not message.text:
            return bot.send_message(message.chat.id, "⚠️ Ошибка регламента: на данном этапе требуется текстовый ответ.")
        if state == 'apply_step_1':
            user_states[message.chat.id]['answers']['name_age'] = message.text
            user_states[message.chat.id]['state'] = 'apply_step_2'
            return bot.send_message(message.chat.id, "📋 <b>Анкетирование (Этап 2 из 3):</b>\nУкажите ваш послужной список (опыт на RP-проектах) и почему вы подходите:")
        elif state == 'apply_step_2':
            user_states[message.chat.id]['answers']['experience'] = message.text
            user_states[message.chat.id]['state'] = 'apply_step_3'
            return bot.send_message(message.chat.id, "📋 <b>Анкетирование (Этап 3 из 3):</b>\nУкажите точное количество часов суточного онлайна:")
        elif state == 'apply_step_3':
            answers = user_states[message.chat.id]['answers']
            vac_title = state_data.get('vac_title', 'Стажер')
            user_states.pop(message.chat.id)
            username = f"@{message.from_user.username}" if message.from_user.username else f"ID:{message.chat.id}"
            
            app_header = (
                f"📋 <b>ЗАЯВКА НА ВАКАНСИЮ: «{vac_title.upper()}»</b>\n"
                f"👤 Кандидат: {username}\n"
                f"🔑 Системный ID: <code>{message.chat.id}</code>\n"
                "━━━━━━━━━━━━━━━━━━━━━━━━━━━\n"
                f"<b>1. Паспортные данные:</b> {answers['name_age']}\n"
                f"<b>2. Послужной список:</b> {answers['experience']}\n"
                f"<b>3. Гарантированный онлайн:</b> {message.text}"
            )
            log_message(message.chat.id, 'in', f"[Анкета на должность «{vac_title}»]")
            inc_ticket_count()
            
            for owner in OWNERS:
                try: bot.send_message(owner, app_header, reply_markup=get_ticket_action_kb(message.chat.id))
                except Exception: pass
            return bot.send_message(message.chat.id, "✅ <b>Анкета зарегистрирована.</b> Данные переданы на рассмотрение руководству Кадрового отдела DragPolit.")

    # ПРИЕМ ТИКЕТОВ И ОБЩИЙ ПОТОК (ОТ ИГРОКОВ)
    if message.chat.id not in OWNERS:
        category = "💬 Общий поток (Без классификации)"
        if state == 'waiting_ticket':
            category = user_states[message.chat.id]['category']
            user_states.pop(message.chat.id)
            bot.send_message(message.chat.id, "✅ <b>Обращение зарегистрировано.</b> Тикет передан высшему руководству. Ожидайте решения.")
        else:
            bot.send_message(message.chat.id, "ℹ️ Ваше сообщение принято системой. Для точной маршрутизации запроса рекомендуем использовать официальное меню: /start")
            
        username = f"@{message.from_user.username}" if message.from_user.username else f"ID:{message.from_user.id}"
        header = (
            f"📌 <b>ОТДЕЛ: {category.upper()}</b>\n"
            f"👤 Субъект: {username}\n"
            f"🔑 Системный ID: <code>{message.chat.id}</code>\n"
            "━━━━━━━━━━━━━━━━━━━━━━━━━━━"
        )
        msg_text = message.text if message.text else "[Прикрепленный файл/медиа]"
        log_message(message.chat.id, 'in', f"[{category}] {msg_text}")
        inc_ticket_count()

        for owner in OWNERS:
            try:
                if message.content_type == 'text':
                    bot.send_message(owner, f"{header}\n{message.text.replace('<', '&lt;').replace('>', '&gt;')}", reply_markup=get_ticket_action_kb(message.chat.id))
                else:
                    bot.send_message(owner, header)
                    bot.copy_message(owner, message.chat.id, message.message_id, reply_markup=get_ticket_action_kb(message.chat.id))
            except Exception: pass
    # НОВЕ: Відповідь Власнику, якщо він пише просто так без меню
    else:
        bot.send_message(message.chat.id, "👑 <b>Система DragPolit в строю!</b>\nБосс, я распознал вас как руководителя высшего звена, поэтому я не создаю тикет от вашего имени.\n\n👉 Для входа в терминал управления введите команду: /admin\n👉 Для просмотра меню игрока нажмите: /start")

# ==========================================
# 8. БЕЗПЕРЕБОЙНЫЙ ЗАПУСК СЕРВЕРА
# ==========================================
app = Flask(__name__)
@app.route('/')
def keep_alive(): return "DragPolit Enterprise Support Node: ACTIVE"

def run_web_server():
    app.run(host="0.0.0.0", port=int(os.environ.get("PORT", 10000)))

def start_bot():
    try: bot.delete_webhook(drop_pending_updates=True)
    except Exception: pass
    while True:
        try:
            print("🏛 Сервер DragPolit Enforcement подключен к шлюзам Telegram...")
            bot.infinity_polling(timeout=10, long_polling_timeout=5, none_stop=True)
        except Exception as e:
            time.sleep(5)

if __name__ == '__main__':
    threading.Thread(target=run_web_server, daemon=True).start()
    start_bot()
