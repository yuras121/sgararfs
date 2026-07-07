import os
import time
import threading
import sqlite3
import telebot
from telebot import types
from flask import Flask
from datetime import datetime
import sys

# ==========================================
# 1. КОНФИГУРАЦИЯ СИСТЕМЫ И ДОСТУПЫ (БЕЗОПАСНАЯ)
# ==========================================
# Токен берется ИСКЛЮЧИТЕЛЬНО из скрытых переменных сервера. 
# Никаких токенов в коде!
TOKEN = os.environ.get('TOKEN')

if not TOKEN:
    print("❌ КРИТИЧЕСКАЯ ОШИБКА: Токен бота не найден! Убедитесь, что переменная TOKEN добавлена в Environment Variables на хостинге.")
    sys.exit(1) # Останавливаем систему, чтобы избежать сбоев

# Идентификаторы Высшего Руководства (Доступ к терминалу)
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
            "<b>Официальные требования Департамента Кадров DragPolit:</b>\n"
            "• Возрастной ценз: от 15 лет (возможны исключения решением руководства).\n"
            "• Глубокое понимание RP-регламента, терминологии и механик проекта.\n"
            "• Грамотная письменная речь, беспристрастность, стрессоустойчивость.\n"
            "• Гарантированный суточный онлайн: от 3-х часов.\n"
            "• Соблюдение субординации и корпоративной этики.\n\n"
            "⚠️ <i>Кандидаты, предоставляющие ложные данные, вносятся в единый черный список проекта.</i>"
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
    c.execute("SELECT user_id, direction, text, timestamp FROM history ORDER BY timestamp DESC LIMIT 1000")
    data = c.fetchall()
    conn.close()
    content = "=== ОФИЦИАЛЬНЫЙ РЕЕСТР ОБРАЩЕНИЙ DRAGPOLIT ===\n\n"
    for row in data:
        dir_text = "[ВХОДЯЩЕЕ]" if row[1] == 'in' else "[ОТВЕТ РУКОВОДСТВА]"
        content += f"[{row[3]}] ID: {row[0]} | {dir_text}\nСодержание: {row[2]}\n{'-'*50}\n"
    return content

def get_audit_export():
    conn = sqlite3.connect(DB_FILE)
    c = conn.cursor()
    c.execute("SELECT admin_id, admin_username, action, target_id, timestamp FROM admin_audit ORDER BY timestamp DESC LIMIT 500")
    data = c.fetchall()
    conn.close()
    content = "=== ЖУРНАЛ СЛУЖЕБНОГО АУДИТА РУКОВОДСТВА ===\n\n"
    for row in data:
        content += f"[{row[4]}] Руководитель: {row[1]} (ID: {row[0]})\nДействие: {row[2]} -> Объект ID: {row[3]}\n{'-'*50}\n"
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
        types.InlineKeyboardButton("🛡 Департамент контроля (Жалоба на Администрацию)", callback_data="type_adminreport"),
        types.InlineKeyboardButton("⚖️ Департамент жалоб (Нарушения Игроков)", callback_data="type_playerreport"),
        types.InlineKeyboardButton("🚨 Экстренное реагирование (Критический сбой)", callback_data="type_urgent"),
        types.InlineKeyboardButton("🛠 Технический отдел (Отчет об ошибке)", callback_data="type_bug"),
        types.InlineKeyboardButton("🤝 Коммерция и партнерство", callback_data="type_collab"),
        types.InlineKeyboardButton("💼 Кадровый резерв (Актуальные вакансии)", callback_data="type_apply")
    )
    return markup

def get_cancel_kb():
    markup = types.InlineKeyboardMarkup()
    markup.add(types.InlineKeyboardButton("❌ Прервать протокол", callback_data="cancel_action"))
    return markup

def get_admin_kb():
    markup = types.InlineKeyboardMarkup(row_width=2)
    # Блок 1: Управление и Кадры
    markup.add(types.InlineKeyboardButton("💼 Управление Кадровым реестром (Вакансии)", callback_data="admin_vac_menu"))
    # Блок 2: Пользователи
    markup.row(
        types.InlineKeyboardButton("⛔️ Блокировка доступа", callback_data="admin_ban"),
        types.InlineKeyboardButton("✅ Восстановление прав", callback_data="admin_unban")
    )
    # Блок 3: Информирование
    markup.row(
        types.InlineKeyboardButton("📢 Массовое оповещение", callback_data="admin_broadcast"),
        types.InlineKeyboardButton("📊 Аналитика системы", callback_data="admin_stats")
    )
    # Блок 4: Базы данных
    markup.row(
        types.InlineKeyboardButton("📁 Реестр субъектов", callback_data="admin_export"),
        types.InlineKeyboardButton("🗂 Архивы обращений", callback_data="admin_history")
    )
    markup.add(types.InlineKeyboardButton("🛡 Журнал служебного аудита", callback_data="admin_audit"))
    return markup

def get_vac_admin_menu_kb():
    markup = types.InlineKeyboardMarkup(row_width=1)
    markup.add(
        types.InlineKeyboardButton("➕ Утвердить новую должность (Вакансию)", callback_data="vacadmin_add"),
        types.InlineKeyboardButton("📋 Реестр должностей (Управление статусами)", callback_data="vacadmin_list"),
        types.InlineKeyboardButton("🔙 Возврат в главный терминал", callback_data="vacadmin_back")
    )
    return markup

def get_vacancies_list_kb():
    vacs = get_all_vacancies(only_active=False)
    markup = types.InlineKeyboardMarkup(row_width=1)
    for vac in vacs:
        status_str = "🟢 АКТИВНА" if vac[3] == 1 else "🔴 ПРИОСТАНОВЛЕНА"
        markup.add(types.InlineKeyboardButton(f"{status_str} | {vac[1]}", callback_data=f"vacmanage_{vac[0]}"))
    markup.add(types.InlineKeyboardButton("🔙 Назад к управлению кадрами", callback_data="admin_vac_menu"))
    return markup

def get_single_vac_manage_kb(vac_id):
    vac = get_vacancy(vac_id)
    toggle_text = "🔴 Приостановить набор (Скрыть)" if vac[3] == 1 else "🟢 Возобновить набор (Открыть)"
    markup = types.InlineKeyboardMarkup(row_width=1)
    markup.add(
        types.InlineKeyboardButton(toggle_text, callback_data=f"vactoggle_{vac_id}"),
        types.InlineKeyboardButton("❌ Ликвидировать должность", callback_data=f"vacdel_{vac_id}"),
        types.InlineKeyboardButton("🔙 К реестру должностей", callback_data="vacadmin_list")
    )
    return markup

def get_public_vacancies_kb():
    vacs = get_all_vacancies(only_active=True)
    markup = types.InlineKeyboardMarkup(row_width=1)
    for vac in vacs:
        markup.add(types.InlineKeyboardButton(f"💼 {vac[1]}", callback_data=f"pubvac_{vac[0]}"))
    markup.add(types.InlineKeyboardButton("🔙 Завершить сеанс", callback_data="cancel_action"))
    return markup

def get_apply_confirm_kb(vac_id):
    markup = types.InlineKeyboardMarkup(row_width=1)
    markup.add(
        types.InlineKeyboardButton("✍️ Инициировать подачу заявления", callback_data=f"applystart_{vac_id}"),
        types.InlineKeyboardButton("🔙 К списку вакансий", callback_data="type_apply")
    )
    return markup

def get_ticket_action_kb(user_id):
    markup = types.InlineKeyboardMarkup(row_width=2)
    markup.add(
        types.InlineKeyboardButton("📨 Направить официальный ответ", callback_data=f"ans_{user_id}"),
        types.InlineKeyboardButton("📁 Архивировать тикет", callback_data=f"close_{user_id}")
    )
    markup.add(types.InlineKeyboardButton("⛔️ Инициировать блокировку", callback_data=f"tban_{user_id}"))
    return markup

def notify_other_owners(sender_id, text):
    for owner in OWNERS:
        if owner != sender_id:
            try: bot.send_message(owner, f"🛡 <b>ВНУТРЕННИЙ АУДИТ:</b>\n{text}")
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
            try: bot.send_message(owner, f"👤 <b>Регистрация в базе DragPolit:</b>\nСубъект: {username} | ID: <code>{user_id}</code>")
            except Exception: pass

    if is_banned(user_id):
        return bot.send_message(user_id, "⛔️ <b>СТАТУС: ОТКАЗ В ДОСТУПЕ.</b>\nВ соответствии с регламентом проекта, обслуживание вашей учетной записи прекращено.")

    user_states.pop(user_id, None)
    text = (
        "🏛 <b>ОФИЦИАЛЬНАЯ ПРИЕМНАЯ DRAGPOLIT</b>\n\n"
        "Добро пожаловать в единую систему регистрации обращений. Данный портал обеспечивает прямую связь с Высшим руководством проекта.\n\n"
        "⚠️ <i>Напоминание: Фиктивные обращения, флуд и несоблюдение субординации влекут за собой бессрочную блокировку профиля. Выберите необходимый департамент:</i>"
    )
    bot.send_message(user_id, text, reply_markup=get_start_kb())

@bot.message_handler(commands=['admin'])
def admin_panel_command(message):
    if message.chat.id not in OWNERS:
        return bot.reply_to(message, "⛔️ <b>Системная ошибка:</b> Недостаточный уровень допуска.")
    
    text = (
        "👑 <b>ТЕРМИНАЛ УПРАВЛЕНИЯ DRAGPOLIT</b>\n"
        "━━━━━━━━━━━━━━━━━━━━━━━━━━━\n"
        "Статус авторизации: <b>ВЫСШЕЕ РУКОВОДСТВО</b>\n\n"
        "Выберите протокол для выполнения:"
    )
    bot.send_message(message.chat.id, text, reply_markup=get_admin_kb())

@bot.message_handler(commands=['get_id'])
def get_id_command(message):
    bot.reply_to(message, f"Идентификатор вашей сессии: <code>{message.chat.id}</code>")

# ==========================================
# 6. НАВИГАЦИЯ ПО МЕНЮ И УПРАВЛЕНИЕ ВАКАНСИЯМИ
# ==========================================
@bot.callback_query_handler(func=lambda call: call.data == 'cancel_action')
def cancel_action(call):
    user_states.pop(call.message.chat.id, None)
    bot.edit_message_text("⭕️ Выполнение протокола прервано. Возврат в главное меню.", call.message.chat.id, call.message.message_id, reply_markup=get_start_kb())

@bot.callback_query_handler(func=lambda call: call.data.startswith('vacadmin_'))
def handle_vac_admin_menu(call):
    if call.message.chat.id not in OWNERS: return
    action = call.data.split('_')[1]
    
    if action == 'add':
        user_states[call.message.chat.id] = {'state': 'addvac_title'}
        bot.edit_message_text("➕ <b>УТВЕРЖДЕНИЕ НОВОЙ ДОЛЖНОСТИ (Этап 1 из 2)</b>\n\n👉 Укажите <b>наименование должности</b> (напр.: <i>Старший Модератор</i>):", call.message.chat.id, call.message.message_id, reply_markup=get_cancel_kb())
    elif action == 'list':
        bot.edit_message_text("📋 <b>РЕЕСТР ДОЛЖНОСТЕЙ И ВАКАНСИЙ:</b>\nВыберите позицию для управления статусом набора:", call.message.chat.id, call.message.message_id, reply_markup=get_vacancies_list_kb())
    elif action == 'back':
        bot.edit_message_text("👑 <b>ТЕРМИНАЛ УПРАВЛЕНИЯ DRAGPOLIT</b>\n━━━━━━━━━━━━━━━━━━━━━━━━━━━", call.message.chat.id, call.message.message_id, reply_markup=get_admin_kb())

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
        status_str = "🟢 НАБОР АКТИВЕН (Отображается)" if vac[3] == 1 else "🔴 НАБОР ПРИОСТАНОВЛЕН (Скрыт)"
        text = f"💼 <b>НОМЕНКЛАТУРА #{vac[0]}</b>\n\n<b>Должность:</b> {vac[1]}\n<b>Системный статус:</b> {status_str}\n\n<b>Утвержденные требования:</b>\n{vac[2]}"
        bot.edit_message_text(text, call.message.chat.id, call.message.message_id, reply_markup=get_single_vac_manage_kb(vac_id))
    elif action == 'vactoggle':
        toggle_vacancy(vac_id)
        vac = get_vacancy(vac_id)
        log_admin_action(call.from_user.id, admin_name, f"Изменил статус вакансии #{vac_id}", 0)
        bot.answer_callback_query(call.id, "Статус номенклатуры обновлен.")
        status_str = "🟢 НАБОР АКТИВЕН (Отображается)" if vac[3] == 1 else "🔴 НАБОР ПРИОСТАНОВЛЕН (Скрыт)"
        text = f"💼 <b>НОМЕНКЛАТУРА #{vac[0]}</b>\n\n<b>Должность:</b> {vac[1]}\n<b>Системный статус:</b> {status_str}\n\n<b>Утвержденные требования:</b>\n{vac[2]}"
        bot.edit_message_text(text, call.message.chat.id, call.message.message_id, reply_markup=get_single_vac_manage_kb(vac_id))
    elif action == 'vacdel':
        delete_vacancy(vac_id)
        log_admin_action(call.from_user.id, admin_name, f"Ликвидировал вакансию #{vac_id}", 0)
        bot.answer_callback_query(call.id, "Должность ликвидирована.")
        bot.edit_message_text("📋 <b>РЕЕСТР ДОЛЖНОСТЕЙ И ВАКАНСИЙ:</b>", call.message.chat.id, call.message.message_id, reply_markup=get_vacancies_list_kb())

@bot.callback_query_handler(func=lambda call: call.data.startswith('admin_'))
def handle_admin_callbacks(call):
    if call.message.chat.id not in OWNERS: return
    action = call.data.split('_')[1]
    
    if action == 'vac':
        bot.edit_message_text("💼 <b>УПРАВЛЕНИЕ КАДРОВЫМ РЕЗЕРВОМ</b>\nФормирование штатного расписания, утверждение должностей и открытие наборов.", call.message.chat.id, call.message.message_id, reply_markup=get_vac_admin_menu_kb())
    elif action == 'stats':
        t_users, b_users, t_tickets = get_stats()
        text = f"📊 <b>СВОДКА АНАЛИТИЧЕСКОГО ЦЕНТРА:</b>\n\n👥 Субъектов в базе: <b>{t_users}</b>\n⛔️ Профилей заблокировано: <b>{b_users}</b>\n📩 Тикетов обработано: <b>{t_tickets}</b>"
        bot.edit_message_text(text, call.message.chat.id, call.message.message_id, reply_markup=get_admin_kb())
    elif action == 'export':
        data = get_full_users_data()
        content = "=== ОФИЦИАЛЬНЫЙ РЕЕСТР ПОЛЬЗОВАТЕЛЕЙ DRAGPOLIT ===\n\n"
        for r in data:
            status = "[ЗАБЛОКИРОВАН]" if r[3] == 1 else "[АКТИВЕН]"
            content += f"ID: {r[0]} | Субъект: {r[1]} | Регистрация: {r[2]} | Статус: {status}\n"
        with open("dragpolit_users.txt", "w", encoding="utf-8") as f: f.write(content)
        with open("dragpolit_users.txt", "rb") as f: bot.send_document(call.message.chat.id, f, caption="📁 Экспорт Реестра субъектов завершен.")
    elif action == 'history':
        content = get_history_export()
        with open("dragpolit_tickets.txt", "w", encoding="utf-8") as f: f.write(content)
        with open("dragpolit_tickets.txt", "rb") as f: bot.send_document(call.message.chat.id, f, caption="🗂 Экспорт Архива обращений завершен.")
    elif action == 'audit':
        content = get_audit_export()
        with open("dragpolit_audit.txt", "w", encoding="utf-8") as f: f.write(content)
        with open("dragpolit_audit.txt", "rb") as f: bot.send_document(call.message.chat.id, f, caption="🛡 Экспорт Журнала аудита завершен.")
    elif action == 'broadcast':
        user_states[call.message.chat.id] = {'state': 'waiting_broadcast'}
        bot.edit_message_text("📢 <b>ПРОТОКОЛ МАССОВОГО ОПОВЕЩЕНИЯ:</b>\nВведите текст или прикрепите медиафайл для рассылки всем субъектам системы:", call.message.chat.id, call.message.message_id, reply_markup=get_cancel_kb())
    elif action == 'ban':
        user_states[call.message.chat.id] = {'state': 'waiting_ban'}
        bot.edit_message_text("⛔️ <b>ПРОЦЕДУРА ОГРАНИЧЕНИЯ ДОСТУПА:</b>\nВведите системный ID субъекта для бессрочной блокировки:", call.message.chat.id, call.message.message_id, reply_markup=get_cancel_kb())
    elif action == 'unban':
        user_states[call.message.chat.id] = {'state': 'waiting_unban'}
        bot.edit_message_text("✅ <b>ПРОЦЕДУРА РЕАБИЛИТАЦИИ:</b>\nВведите системный ID субъекта для снятия ограничений:", call.message.chat.id, call.message.message_id, reply_markup=get_cancel_kb())

@bot.callback_query_handler(func=lambda call: call.data.startswith(('ans_', 'close_', 'tban_')))
def handle_ticket_actions(call):
    if call.message.chat.id not in OWNERS: return
    parts = call.data.split('_')
    action = parts[0]
    target_id = int(parts[1])
    admin_name = f"@{call.from_user.username}" if call.from_user.username else f"ID:{call.from_user.id}"
    
    if action == 'ans':
        user_states[call.message.chat.id] = {'state': 'typing_reply', 'target': target_id}
        bot.send_message(call.message.chat.id, f"📨 <b>ФОРМИРОВАНИЕ ОФИЦИАЛЬНОГО ОТВЕТА</b>\nАдресат ID: <code>{target_id}</code>\n<i>Введите текст резолюции:</i>", reply_markup=get_cancel_kb())
        bot.answer_callback_query(call.id)
    elif action == 'close':
        bot.edit_message_reply_markup(call.message.chat.id, call.message.message_id, reply_markup=None)
        log_admin_action(call.from_user.id, admin_name, "Переместил тикет в архив", target_id)
        notify_other_owners(call.from_user.id, f"Руководитель {admin_name} закрыл тикет от субъекта ID <code>{target_id}</code>.")
        bot.answer_callback_query(call.id, "Тикет заархивирован.")
    elif action == 'tban':
        set_ban_status(target_id, 1)
        bot.edit_message_reply_markup(call.message.chat.id, call.message.message_id, reply_markup=None)
        log_admin_action(call.from_user.id, admin_name, "Заблокировал субъекта", target_id)
        notify_other_owners(call.from_user.id, f"⚠️ Руководитель {admin_name} инициировал блокировку субъекта ID <code>{target_id}</code>.")
        bot.send_message(call.message.chat.id, f"⛔️ Субъект <code>{target_id}</code> успешно изолирован от системы.")
        bot.answer_callback_query(call.id, "Санкции применены.")

@bot.callback_query_handler(func=lambda call: call.data.startswith(('type_', 'pubvac_', 'applystart_')))
def handle_main_menu(call):
    if is_banned(call.message.chat.id):
        return bot.answer_callback_query(call.id, "Доступ ограничен!", show_alert=True)
        
    if call.data.startswith('pubvac_'):
        vac_id = int(call.data.split('_')[1])
        vac = get_vacancy(vac_id)
        if not vac or vac[3] == 0:
            return bot.answer_callback_query(call.id, "Набор на данную должность приостановлен.", show_alert=True)
        text = f"🏛 <b>ДЕПАРТАМЕНТ КАДРОВ DRAGPOLIT</b>\n\n💼 <b>ВАКАНСИЯ: {vac[1].upper()}</b>\n\n{vac[2]}"
        return bot.edit_message_text(text, call.message.chat.id, call.message.message_id, reply_markup=get_apply_confirm_kb(vac_id))

    if call.data.startswith('applystart_'):
        vac_id = int(call.data.split('_')[1])
        vac = get_vacancy(vac_id)
        vac_title = vac[1] if vac else "Неизвестная должность"
        user_states[call.message.chat.id] = {'state': 'apply_step_1', 'vac_title': vac_title, 'answers': {}}
        return bot.edit_message_text(f"📋 <b>Регистрация заявления на должность «{vac_title}» (Этап 1 из 3):</b>\nУкажите ваши паспортные данные (Имя и реальный Возраст):", call.message.chat.id, call.message.message_id, reply_markup=get_cancel_kb())

    action = call.data.split('_')[1]
    
    # Регламент обработки жалоб на игроков
    if action == 'playerreport':
        info_text = (
            "⚖️ <b>РЕГЛАМЕНТ ОБРАБОТКИ ЖАЛОБ НА ИГРОКОВ</b>\n\n"
            "Высшее руководство DragPolit не занимается рассмотрением первичных нарушений правил чата или игрового процесса в данном терминале.\n\n"
            "👉 <b>Алгоритм подачи жалобы на игрока:</b>\n"
            "1. Воспользуйтесь внутриигровой системой обращений (репорт) на сервере.\n"
            "2. Обратитесь в личные сообщения к действующему дежурному модератору.\n\n"
            "<i>Данная приемная предназначена исключительно для жалоб на неправомерные действия самой администрации.</i>"
        )
        return bot.edit_message_text(info_text, call.message.chat.id, call.message.message_id, reply_markup=get_start_kb())

    elif action == 'apply':
        active_vacs = get_all_vacancies(only_active=True)
        if not active_vacs:
            closed_text = (
                "🏛 <b>ДЕПАРТАМЕНТ КАДРОВ DRAGPOLIT</b>\n\n"
                "🔴 <b>НАБОР ПРИОСТАНОВЛЕН</b>\n\n"
                "На текущий момент штатное расписание администрации и модерации укомплектовано. Прием новых заявлений временно закрыт.\n\n"
                "<i>Отслеживайте официальные информационные ресурсы проекта для получения уведомлений об открытии вакансий.</i>"
            )
            return bot.edit_message_text(closed_text, call.message.chat.id, call.message.message_id, reply_markup=get_start_kb())
        else:
            text = "🏛 <b>ДЕПАРТАМЕНТ КАДРОВ DRAGPOLIT</b>\n\nДоступен перечень открытых вакансий. Выберите должность для ознакомления с должностными инструкциями:"
            return bot.edit_message_text(text, call.message.chat.id, call.message.message_id, reply_markup=get_public_vacancies_kb())

    elif action == 'adminreport': text, cat = "🛡 <b>Департамент контроля Администрации:</b>\nУкажите никнейм сотрудника администрации, дату/время инцидента и подробно аргументируйте суть неправомерных действий (наличие доказательств обязательно):", "Жалоба на Администрацию"
    elif action == 'bug': text, cat = "🛠 <b>Технический департамент:</b>\nЗадокументируйте выявленный сбой по форме:\n1. Суть аномалии\n2. Локация/механика\n3. Алгоритм воспроизведения", "Технический отдел"
    elif action == 'urgent': text, cat = "🚨 <b>Экстренное реагирование:</b>\nСформулируйте суть критической угрозы для проекта. Обращение будет проиндексировано с наивысшим приоритетом.", "Экстренное обращение"
    elif action == 'collab': text, cat = "🤝 <b>Коммерческий департамент:</b>\nИзложите суть партнерского или коммерческого предложения, прикрепив контактные данные лица, принимающего решения.", "Партнерский отдел"
        
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

    # ДОБАВЛЕНИЕ ВАКАНСИИ
    if message.chat.id in OWNERS and state == 'addvac_title':
        if not message.text:
            return bot.send_message(message.chat.id, "❌ Формат не поддерживается. Требуется текстовое наименование.")
        user_states[message.chat.id] = {'state': 'addvac_desc', 'title': message.text}
        return bot.send_message(message.chat.id, f"➕ Должность: <b>«{message.text}»</b>\n\n👉 Утвердите должностные инструкции и требования к кандидатам:", reply_markup=get_cancel_kb())

    if message.chat.id in OWNERS and state == 'addvac_desc':
        if not message.text:
            return bot.send_message(message.chat.id, "❌ Формат не поддерживается. Требуется текстовое описание.")
        title = state_data['title']
        add_vacancy(title, message.text)
        user_states.pop(message.chat.id)
        log_admin_action(message.from_user.id, admin_name, f"Утвердил должность «{title}»", 0)
        notify_other_owners(message.from_user.id, f"Руководитель {admin_name} утвердил новую должность: «{title}».")
        return bot.send_message(message.chat.id, f"✅ <b>Должность «{title}» успешно внесена в реестр и опубликована!</b>", reply_markup=get_admin_kb())

    # ОТВЕТ РУКОВОДСТВА
    if message.chat.id in OWNERS and state == 'typing_reply':
        target_id = state_data['target']
        user_states.pop(message.chat.id)
        reply_text = message.text if message.text else "[Прикрепленный медиаматериал]"
        log_message(target_id, 'out', reply_text)
        log_admin_action(message.from_user.id, admin_name, f"Ответил: {reply_text[:30]}...", target_id)
        notify_other_owners(message.from_user.id, f"Руководитель {admin_name} направил резолюцию субъекту <code>{target_id}</code>:\n<i>«{reply_text}»</i>")
        
        official_header = "🏛 <b>ОФИЦИАЛЬНАЯ РЕЗОЛЮЦИЯ РУКОВОДСТВА DRAGPOLIT</b>\n━━━━━━━━━━━━━━━━━━━━━━━━━━━\n\n"
        try:
            if message.content_type == 'text':
                bot.send_message(target_id, official_header + message.text.replace('<', '&lt;').replace('>', '&gt;'))
            else:
                bot.send_message(target_id, official_header)
                bot.copy_message(target_id, message.chat.id, message.message_id)
            bot.send_message(message.chat.id, "✅ Резолюция успешно доставлена адресату.")
        except Exception:
            bot.send_message(message.chat.id, "⚠️ Ошибка маршрутизации: профиль адресата недоступен.")
        return

    # МАССОВАЯ РАССЫЛКА
    if message.chat.id in OWNERS and state == 'waiting_broadcast':
        user_states.pop(message.chat.id)
        users = get_all_users()
        success = 0
        bot.send_message(message.chat.id, "⏳ Инициализация рассылки. Пожалуйста, ожидайте...")
        for uid in users:
            try:
                bot.copy_message(uid, message.chat.id, message.message_id)
                success += 1
            except Exception: pass
        log_admin_action(message.from_user.id, admin_name, f"Рассылка на {success} чел.", 0)
        notify_other_owners(message.from_user.id, f"📢 Руководитель {admin_name} инициировал массовое оповещение ({success} субъектов).")
        return bot.send_message(message.chat.id, f"✅ Протокол оповещения выполнен. Покрытие: {success} субъектов.")

    # БЛОКИРОВКА ВРУЧНУЮ
    if message.chat.id in OWNERS and state in ['waiting_ban', 'waiting_unban']:
        user_states.pop(message.chat.id)
        try:
            target_id = int(message.text.strip())
            is_ban = (state == 'waiting_ban')
            set_ban_status(target_id, 1 if is_ban else 0)
            status_text = "заблокирован ⛔️" if is_ban else "восстановлен в правах ✅"
            act_text = "Изоляция профиля" if is_ban else "Реабилитация профиля"
            log_admin_action(message.from_user.id, admin_name, act_text, target_id)
            notify_other_owners(message.from_user.id, f"Руководитель {admin_name} изменил статус допуска субъекта <code>{target_id}</code>: {status_text}.")
            return bot.send_message(message.chat.id, f"Допуск субъекта <code>{target_id}</code>: {status_text}.", reply_markup=get_admin_kb())
        except ValueError:
            return bot.send_message(message.chat.id, "❌ Формат не поддерживается. Требуется цифровой ID.", reply_markup=get_admin_kb())

    # ИГНОР БАНА
    if is_banned(message.chat.id): return

    # АНКЕТИРОВАНИЕ
    if state and state.startswith('apply_step_'):
        if not message.text:
            return bot.send_message(message.chat.id, "⚠️ Нарушение протокола заполнения: ожидается текстовый ввод.")
        if state == 'apply_step_1':
            user_states[message.chat.id]['answers']['name_age'] = message.text
            user_states[message.chat.id]['state'] = 'apply_step_2'
            return bot.send_message(message.chat.id, "📋 <b>Анкетирование (Этап 2 из 3):</b>\nУкажите ваш послужной список (опыт администрирования на RP-проектах) и аргументируйте вашу кандидатуру:")
        elif state == 'apply_step_2':
            user_states[message.chat.id]['answers']['experience'] = message.text
            user_states[message.chat.id]['state'] = 'apply_step_3'
            return bot.send_message(message.chat.id, "📋 <b>Анкетирование (Этап 3 из 3):</b>\nУкажите гарантированное количество часов суточного онлайна:")
        elif state == 'apply_step_3':
            answers = user_states[message.chat.id]['answers']
            vac_title = state_data.get('vac_title', 'Стажер')
            user_states.pop(message.chat.id)
            username = f"@{message.from_user.username}" if message.from_user.username else f"ID:{message.chat.id}"
            
            app_header = (
                f"📋 <b>ЗАЯВЛЕНИЕ НА ДОЛЖНОСТЬ: «{vac_title.upper()}»</b>\n"
                f"👤 Кандидат: {username}\n"
                f"🔑 Системный ID: <code>{message.chat.id}</code>\n"
                "━━━━━━━━━━━━━━━━━━━━━━━━━━━\n"
                f"<b>1. Идентификация:</b> {answers['name_age']}\n"
                f"<b>2. Компетенции:</b> {answers['experience']}\n"
                f"<b>3. Заявленный онлайн:</b> {message.text}"
            )
            log_message(message.chat.id, 'in', f"[Заявление: {vac_title}]")
            inc_ticket_count()
            
            for owner in OWNERS:
                try: bot.send_message(owner, app_header, reply_markup=get_ticket_action_kb(message.chat.id))
                except Exception: pass
            return bot.send_message(message.chat.id, "✅ <b>Заявление зарегистрировано.</b> Данные переданы на рассмотрение руководству Кадрового департамента DragPolit.")

    # ОБЩИЙ ПОТОК (ИГРОКИ)
    if message.chat.id not in OWNERS:
        category = "💬 Общий поток (Не классифицировано)"
        if state == 'waiting_ticket':
            category = user_states[message.chat.id]['category']
            user_states.pop(message.chat.id)
            bot.send_message(message.chat.id, "✅ <b>Обращение зарегистрировано.</b> Тикет сформирован и передан высшему руководству на рассмотрение.")
        else:
            bot.send_message(message.chat.id, "ℹ️ Система зафиксировала входящий пакет данных. Для маршрутизации обращения в профильный департамент используйте меню: /start")
            
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
            
    # ОТВЕТ ВЛАДЕЛЬЦУ (ЕСЛИ ОН ПРОСТО ПИШЕТ В БОТА)
    else:
        status_msg = (
            "🔐 <b>СИСТЕМА УПРАВЛЕНИЯ DRAGPOLIT</b>\n\n"
            "Статус: <b>Доступ подтвержден (Высшее руководство)</b>\n\n"
            "Служебный режим активирован. Свободные текстовые сообщения от вашего имени не регистрируются как тикеты.\n\n"
            "• Для доступа к панели управления: /admin\n"
            "• Для просмотра клиентского интерфейса: /start"
        )
        bot.send_message(message.chat.id, status_msg)

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
            print("🏛 ERP-система DragPolit подключена к серверам Telegram...")
            bot.infinity_polling(timeout=10, long_polling_timeout=5, none_stop=True)
        except Exception as e:
            time.sleep(5)

if __name__ == '__main__':
    threading.Thread(target=run_web_server, daemon=True).start()
    start_bot()
