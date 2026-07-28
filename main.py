import os
import sqlite3
import telebot
import sys
import time
import json
from telebot import types
from datetime import datetime
from threading import Lock

# ==========================================
# 1. СИСТЕМНОЕ ЯДРО И ДОСТУПЫ
# ==========================================
TOKEN = os.environ.get('TOKEN')
# Список Высшего Руководства (Owner IDs)
OWNERS = [1614259542, 7716987740, 1751927856] 

if not TOKEN:
    print("❌ КРИТИЧЕСКАЯ ОШИБКА: Токен не найден в Environment!")
    sys.exit(1)

bot = telebot.TeleBot(TOKEN, parse_mode='HTML')
db_lock = Lock()
# АБСОЛЮТНЫЙ ПУТЬ ДЛЯ DOCKER VOLUME
DB_FILE = '/app/data/dragpolit_enterprise_v5.db'

# ==========================================
# 2. МУЛЬТИЯЗЫЧНЫЙ ГЛОССАРИЙ (RU / EN)
# ==========================================
STRINGS = {
    'ru': {
        'start': "🏛 <b>Центральная Приемная DragPolit</b>\nДобро пожаловать в официальный центр управления игры. Выберите нужный отдел или ознакомьтесь с FAQ:",
        'b_faq': "❓ FAQ / Справка", 
        'b_lang': "🌍 English",
        'b_report': "🛡 Жалоба / Репорт", 
        'b_tech': "⚙️ Тех-отдел", 
        'b_mod': "📝 Вакансии (Модерация)",
        'b_partner': "🤝 Партнерство",
        'b_other': "💬 Общие вопросы",
        'input': "📋 <b>РЕЖИМ ЗАПИСИ:</b> Отправьте ваше сообщение (текст, фото или файл).",
        'done': "✅ Обращение зарегистрировано. Ожидайте ответа руководства.",
        'reply_head': "🏛 <b>ОФИЦИАЛЬНЫЙ ОТВЕТ АДМИНИСТРАЦИИ DRAGPOLIT:</b>\n━━━━━━━━━━━━━━━━━━━━\n\n",
        'banned': "⛔️ Доступ к боту ограничен службой безопасности DragPolit.",
        'mod_closed': "🚫 <b>Набор в команду модерации временно ЗАКРЫТ.</b>\nСледите за новостями проекта DragPolit!",
        'part_closed': "🚫 <b>Прием заявок на партнерство временно ЗАКРЫТ.</b>",
        'no_questions': "⚠️ Для данной формы еще не настроены вопросы. Обратитесь к администрации.",
        'app_done': "✅ Спасибо! Ваша заявка успешно отправлена на рассмотрение Высшему Руководству.",
        'app_already': "⚠️ Вы уже подали заявку. Ожидайте решения администрации."
    },
    'en': {
        'start': "🏛 <b>DragPolit Central Reception</b>\nWelcome to the official game center. Select a department or check the FAQ:",
        'b_faq': "❓ FAQ / Help", 
        'b_lang': "🌍 Русский",
        'b_report': "🛡 Report Player", 
        'b_tech': "⚙️ Tech Support", 
        'b_mod': "📝 Vacancies (Moderation)",
        'b_partner': "🤝 Partnership",
        'b_other': "💬 General Info",
        'input': "📋 <b>RECORD MODE:</b> Type your message or upload media.",
        'done': "✅ Message registered. Please wait for management response.",
        'reply_head': "🏛 <b>OFFICIAL DRAGPOLIT RESPONSE:</b>\n━━━━━━━━━━━━━━━━━━━━\n\n",
        'banned': "⛔️ Access restricted by DragPolit security service.",
        'mod_closed': "🚫 <b>Moderator recruitment is currently CLOSED.</b>\nFollow DragPolit news for updates!",
        'part_closed': "🚫 <b>Partnership applications are currently CLOSED.</b>",
        'no_questions': "⚠️ Form questions are not configured yet. Contact support.",
        'app_done': "✅ Thank you! Your application has been submitted to Management.",
        'app_already': "⚠️ You have already submitted an application. Please wait for review."
    }
}

# ==========================================
# 3. БАЗА ДАННЫХ И НАСТРОЙКИ (CORE)
# ==========================================
def db_query(sql, params=(), fetch=False, commit=False):
    with db_lock:
        with sqlite3.connect(DB_FILE, timeout=15) as conn:
            conn.execute("PRAGMA journal_mode=WAL;")
            c = conn.cursor()
            c.execute(sql, params)
            res = c.fetchall() if fetch else None
            if commit: conn.commit()
            return res

def get_setting(key, default="1"):
    res = db_query("SELECT val FROM settings WHERE key = ?", (key,), fetch=True)
    return res[0][0] if res else default

def set_setting(key, val):
    db_query("INSERT OR REPLACE INTO settings (key, val) VALUES (?, ?)", (key, str(val)), commit=True)

def init_db():
    # Пользователи
    db_query('''CREATE TABLE IF NOT EXISTS subjects (
        uid INTEGER PRIMARY KEY, username TEXT, lang TEXT DEFAULT 'ru', 
        state TEXT DEFAULT 'IDLE', banned INTEGER DEFAULT 0, warns INTEGER DEFAULT 0,
        note TEXT, reg TEXT)''', commit=True)
    
    # Настройки (Переключатели)
    db_query('''CREATE TABLE IF NOT EXISTS settings (
        key TEXT PRIMARY KEY, val TEXT)''', commit=True)
    
    # Конструктор Вопросов для Анкет (MOD / PARTNER)
    db_query('''CREATE TABLE IF NOT EXISTS form_questions (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        form_type TEXT,
        step_order INTEGER,
        q_ru TEXT,
        q_en TEXT)''', commit=True)
    
    # История сообщений
    db_query('''CREATE TABLE IF NOT EXISTS history (
        id INTEGER PRIMARY KEY AUTOINCREMENT, uid INTEGER, txt TEXT, ts TEXT, direction TEXT, admin_id INTEGER DEFAULT 0)''', commit=True)
    
    # FAQ База
    db_query('''CREATE TABLE IF NOT EXISTS faq_base (
        id INTEGER PRIMARY KEY AUTOINCREMENT, question TEXT, answer TEXT, lang TEXT)''', commit=True)
    
    # Логи администраторов
    db_query('''CREATE TABLE IF NOT EXISTS admin_logs (
        id INTEGER PRIMARY KEY AUTOINCREMENT, aid INTEGER, action TEXT, target_uid INTEGER, ts TEXT)''', commit=True)
        
    # Заявки
    db_query('''CREATE TABLE IF NOT EXISTS applications (
        id INTEGER PRIMARY KEY AUTOINCREMENT, type TEXT, uid INTEGER, username TEXT,
        data_json TEXT, status TEXT DEFAULT 'PENDING', ts TEXT)''', commit=True)

    # Стандартные настройки
    if not db_query("SELECT val FROM settings WHERE key = 'mod_open'", fetch=True):
        set_setting('mod_open', '1')
    if not db_query("SELECT val FROM settings WHERE key = 'partner_open'", fetch=True):
        set_setting('partner_open', '1')

    # Инициализация дефолтных вопросов, если база вопросов пуста
    if not db_query("SELECT id FROM form_questions", fetch=True):
        # Вопросы Модератора
        db_query("INSERT INTO form_questions (form_type, step_order, q_ru, q_en) VALUES (?, ?, ?, ?)",
                 ('MOD', 1, "Укажите ваш возраст и имя/никнейм:", "Specify your age and name/nickname:"), commit=True)
        db_query("INSERT INTO form_questions (form_type, step_order, q_ru, q_en) VALUES (?, ?, ?, ?)",
                 ('MOD', 2, "Опишите ваш опыт модерации в Telegram/играх:", "Describe your moderation experience:"), commit=True)
        db_query("INSERT INTO form_questions (form_type, step_order, q_ru, q_en) VALUES (?, ?, ?, ?)",
                 ('MOD', 3, "Сколько часов в день вы готовы уделять игре?", "How many hours per day can you dedicate?"), commit=True)
        db_query("INSERT INTO form_questions (form_type, step_order, q_ru, q_en) VALUES (?, ?, ?, ?)",
                 ('MOD', 4, "Почему именно вы должны стать модератором DragPolit?", "Why should we select you?"), commit=True)
        
        # Вопросы Партнерства
        db_query("INSERT INTO form_questions (form_type, step_order, q_ru, q_en) VALUES (?, ?, ?, ?)",
                 ('PARTNER', 1, "Укажите ссылку на ваш канал/проект и его тематику:", "Link to your channel/project and topic:"), commit=True)
        db_query("INSERT INTO form_questions (form_type, step_order, q_ru, q_en) VALUES (?, ?, ?, ?)",
                 ('PARTNER', 2, "Укажите размер аудитории и средний охват:", "Audience size and average reach:"), commit=True)
        db_query("INSERT INTO form_questions (form_type, step_order, q_ru, q_en) VALUES (?, ?, ?, ?)",
                 ('PARTNER', 3, "Опишите ваше предложение по сотрудничеству:", "Describe your partnership proposal:"), commit=True)

init_db()

# ==========================================
# 4. УМНАЯ СИНХРОНИЗАЦИЯ И КЛАВИАТУРЫ
# ==========================================
def sync_notify_all(sender_id, text, target_uid=None):
    """ Умное оповещение всего штаба администраторов """
    sender_user = f"ID: {sender_id}"
    try:
        user_obj = bot.get_chat(sender_id)
        if user_obj.username: sender_user = f"@{user_obj.username}"
    except: pass

    sync_msg = f"🔔 <b>СИНХРОНИЗАЦИЯ ШТАБА:</b>\n<b>Администратор:</b> {sender_user}\n"
    if target_uid: sync_msg += f"<b>Субъект:</b> <code>{target_uid}</code>\n"
    sync_msg += f"━━━━━━━━━━━━━━━━━━━━\n{text}"

    for owner in OWNERS:
        if owner != sender_id:
            try: bot.send_message(owner, sync_msg)
            except: pass

def get_main_kb(uid):
    res = db_query("SELECT lang FROM subjects WHERE uid = ?", (uid,), fetch=True)
    lang = res[0][0] if res else 'ru'
    
    kb = types.ReplyKeyboardMarkup(resize_keyboard=True, row_width=2)
    kb.add(STRINGS[lang]['b_report'], STRINGS[lang]['b_tech'])
    kb.add(STRINGS[lang]['b_mod'], STRINGS[lang]['b_partner'])
    kb.add(STRINGS[lang]['b_faq'], STRINGS[lang]['b_lang'])
    return kb

def get_admin_panel_kb():
    mod_status = "🟢 ВКЛ" if get_setting('mod_open') == '1' else "🔴 ВЫКЛ"
    part_status = "🟢 ВКЛ" if get_setting('partner_open') == '1' else "🔴 ВЫКЛ"

    kb = types.InlineKeyboardMarkup(row_width=2)
    kb.add(
        types.InlineKeyboardButton(f"Модерация: {mod_status}", callback_data="toggle_mod"),
        types.InlineKeyboardButton(f"Партнерство: {part_status}", callback_data="toggle_partner")
    )
    kb.add(
        types.InlineKeyboardButton("⚙️ КОНСТРУКТОР АНКЕТ", callback_data="adm_builder"),
        types.InlineKeyboardButton("📂 Список Заявок", callback_data="adm_apps_list")
    )
    kb.add(
        types.InlineKeyboardButton("📢 Рассылка", callback_data="adm_broadcast"),
        types.InlineKeyboardButton("📊 Статистика", callback_data="adm_stats")
    )
    kb.add(
        types.InlineKeyboardButton("➕ Добавить FAQ", callback_data="adm_faq_add"),
        types.InlineKeyboardButton("📜 Журнал Аудита", callback_data="adm_report_daily")
    )
    kb.add(types.InlineKeyboardButton("💾 Бэкап БД", callback_data="adm_backup"))
    return kb

def crm_control_kb(uid):
    kb = types.InlineKeyboardMarkup(row_width=2)
    kb.add(
        types.InlineKeyboardButton("✉️ Ответить", callback_data=f"ans_{uid}"),
        types.InlineKeyboardButton("👤 Досье/Заметка", callback_data=f"prof_{uid}")
    )
    kb.add(
        types.InlineKeyboardButton("📜 История", callback_data=f"hist_{uid}"),
        types.InlineKeyboardButton("⚠️ Варн (+1)", callback_data=f"warn_{uid}")
    )
    kb.add(
        types.InlineKeyboardButton("⛔️ БАН", callback_data=f"ban_{uid}"),
        types.InlineKeyboardButton("🟢 РАЗБАН", callback_data=f"unban_{uid}")
    )
    return kb

def app_review_kb(app_id, applicant_uid):
    kb = types.InlineKeyboardMarkup(row_width=2)
    kb.add(
        types.InlineKeyboardButton("✅ Принять", callback_data=f"appdone_accept_{app_id}_{applicant_uid}"),
        types.InlineKeyboardButton("❌ Отклонить", callback_data=f"appdone_reject_{app_id}_{applicant_uid}")
    )
    kb.add(types.InlineKeyboardButton("💬 Написать кандидату", callback_data=f"ans_{applicant_uid}"))
    return kb

# ==========================================
# 5. ОСНОВНЫЕ ХЕНДЛЕРЫ
# ==========================================
@bot.message_handler(commands=['start'])
def h_start(m):
    res = db_query("SELECT lang, banned FROM subjects WHERE uid = ?", (m.chat.id,), fetch=True)
    if not res:
        dt = datetime.now().strftime("%Y-%m-%d")
        db_query("INSERT INTO subjects (uid, username, reg) VALUES (?, ?, ?)", 
                 (m.chat.id, m.from_user.username, dt), commit=True)
        res = [('ru', 0)]
    
    lang = res[0][0]
    if res[0][1]: return bot.send_message(m.chat.id, STRINGS[lang]['banned'])
        
    db_query("UPDATE subjects SET state = 'IDLE' WHERE uid = ?", (m.chat.id,), commit=True)
    bot.send_message(m.chat.id, STRINGS[lang]['start'], reply_markup=get_main_kb(m.chat.id))

@bot.message_handler(commands=['admin'])
def h_admin(m):
    if m.chat.id not in OWNERS: return
    bot.send_message(m.chat.id, "🏛 <b>ТЕРМИНАЛ УПРАВЛЕНИЯ DRAGPOLIT</b>\nЗдесь доступен полнейший контроль анкет, конструктор вопросов и тикеты.", reply_markup=get_admin_panel_kb())

# ОБРОБКА ТЕКСТОВИХ КНОПОК МЕНЮ
@bot.message_handler(func=lambda m: any(m.text in d.values() for d in STRINGS.values()))
def h_menu(m):
    res = db_query("SELECT lang, banned FROM subjects WHERE uid = ?", (m.chat.id,), fetch=True)
    if not res or res[0][1]: return
    lang = res[0][0]

    # Смена языка (RU / EN)
    if m.text in [STRINGS['ru']['b_lang'], STRINGS['en']['b_lang']]:
        new_lang = 'en' if lang == 'ru' else 'ru'
        db_query("UPDATE subjects SET lang = ? WHERE uid = ?", (new_lang, m.chat.id), commit=True)
        msg = "🌐 Язык изменен на Русский!" if new_lang == 'ru' else "🌐 Language set to English!"
        return bot.send_message(m.chat.id, msg, reply_markup=get_main_kb(m.chat.id))

    # FAQ
    if m.text in [STRINGS['ru']['b_faq'], STRINGS['en']['b_faq']]:
        faqs = db_query("SELECT question, id FROM faq_base WHERE lang = ?", (lang,), fetch=True)
        if not faqs: return bot.send_message(m.chat.id, "ℹ️ FAQ пуст.")
        kb = types.InlineKeyboardMarkup()
        for q in faqs: kb.add(types.InlineKeyboardButton(q[0], callback_data=f"showfaq_{q[1]}"))
        return bot.send_message(m.chat.id, "<b>Часто задаваемые вопросы:</b>", reply_markup=kb)

    # НАБОР МОДЕРАТОРОВ (Динамический)
    if m.text in [STRINGS['ru']['b_mod'], STRINGS['en']['b_mod']]:
        if get_setting('mod_open') == '0':
            return bot.send_message(m.chat.id, STRINGS[lang]['mod_closed'])
        return start_dynamic_form(m.chat.id, 'MOD', lang)

    # ПАРТНЕРСТВО (Динамический)
    if m.text in [STRINGS['ru']['b_partner'], STRINGS['en']['b_partner']]:
        if get_setting('partner_open') == '0':
            return bot.send_message(m.chat.id, STRINGS[lang]['part_closed'])
        return start_dynamic_form(m.chat.id, 'PARTNER', lang)

    # Обычно входящее сообщение (Тикет)
    db_query("UPDATE subjects SET state = ? WHERE uid = ?", (f"INPUT|{m.text}", m.chat.id), commit=True)
    bot.send_message(m.chat.id, STRINGS[lang]['input'], reply_markup=types.ReplyKeyboardRemove())

# ==========================================
# 6. ДИНАМИЧЕСКИЙ ДВИЖОК АНКЕТИРОВАНИЯ
# ==========================================
def start_dynamic_form(uid, form_type, lang):
    # Проверка на супроводительную активную заявку
    check_app = db_query("SELECT id FROM applications WHERE uid = ? AND type = ? AND status = 'PENDING'", (uid, form_type), fetch=True)
    if check_app: return bot.send_message(uid, STRINGS[lang]['app_already'])

    # Загружаем вопросы из БД
    questions = db_query("SELECT id, q_ru, q_en FROM form_questions WHERE form_type = ? ORDER BY step_order ASC", (form_type,), fetch=True)
    if not questions:
        return bot.send_message(uid, STRINGS[lang]['no_questions'])

    # Формат state: RUNFORM|form_type|q_index|json_answers
    answers_init = json.dumps([])
    db_query("UPDATE subjects SET state = ? WHERE uid = ?", (f"RUNFORM|{form_type}|0|{answers_init}", uid), commit=True)
    
    q_text = questions[0][1] if lang == 'ru' else questions[0][2]
    header = "📝 <b>АНКЕТА МОДЕРАТОРА</b>\n\n" if form_type == 'MOD' else "🤝 <b>ЗАЯВКА НА ПАРТНЕРСТВО</b>\n\n"
    msg = bot.send_message(uid, f"{header}<b>Шаг 1/{len(questions)}:</b> {q_text}", reply_markup=types.ReplyKeyboardRemove())
    bot.register_next_step_handler(msg, process_form_step)

def process_form_step(m):
    res = db_query("SELECT state, lang FROM subjects WHERE uid = ?", (m.chat.id,), fetch=True)
    if not res or "RUNFORM" not in res[0][0]: return
    
    parts = res[0][0].split('|', 3)
    form_type = parts[1]
    q_index = int(parts[2])
    answers = json.loads(parts[3])
    lang = res[0][1]

    # Сохраняем полученный ответ
    answers.append(m.text)

    # Загружаем все вопросы для данной формы
    questions = db_query("SELECT q_ru, q_en FROM form_questions WHERE form_type = ? ORDER BY step_order ASC", (form_type,), fetch=True)
    next_index = q_index + 1

    if next_index < len(questions):
        # Переходим к следующему вопросу
        db_query("UPDATE subjects SET state = ? WHERE uid = ?", 
                 (f"RUNFORM|{form_type}|{next_index}|{json.dumps(answers)}", m.chat.id), commit=True)
        
        q_text = questions[next_index][0] if lang == 'ru' else questions[next_index][1]
        msg = bot.send_message(m.chat.id, f"<b>Шаг {next_index+1}/{len(questions)}:</b> {q_text}")
        bot.register_next_step_handler(msg, process_form_step)
    else:
        # Анкета полностью заполнена!
        db_query("UPDATE subjects SET state = 'IDLE' WHERE uid = ?", (m.chat.id,), commit=True)
        ts = datetime.now().strftime("%Y-%m-%d %H:%M")
        
        # Сохраняем в БД
        db_query("INSERT INTO applications (type, uid, username, data_json, ts) VALUES (?, ?, ?, ?, ?)", 
                 (form_type, m.chat.id, m.from_user.username, json.dumps(answers), ts), commit=True)
        app_id = db_query("SELECT last_insert_rowid()", fetch=True)[0][0]

        bot.send_message(m.chat.id, STRINGS[lang]['app_done'], reply_markup=get_main_kb(m.chat.id))

        # Составляемสวยную динамическую карточку для Штаба
        title = "📝 <b>НОВАЯ ЗАЯВКА В МОДЕРАТОРЫ</b>" if form_type == 'MOD' else "🤝 <b>НОВАЯ ЗАЯВКА НА ПАРТНЕРСТВО</b>"
        card = f"{title} <b>#{app_id}</b>\n━━━━━━━━━━━━━━━━━━━━\n"
        card += f"👤 <b>Заявитель:</b> @{m.from_user.username} (<code>{m.chat.id}</code>)\n\n"

        for idx, q_item in enumerate(questions):
            ans_val = answers[idx] if idx < len(answers) else '—'
            card += f"<b>❓ {q_item[0]}</b>\n💬 <i>{ans_val}</i>\n\n"
        
        card += f"📅 <b>Дата:</b> {ts}"

        for adm in OWNERS:
            try: bot.send_message(adm, card, reply_markup=app_review_kb(app_id, m.chat.id))
            except: pass

# ==========================================
# 7. ОБРАБОТКА ВХОДЯЩИХ (TICKETS)
# ==========================================
@bot.message_handler(content_types=['text', 'photo', 'video', 'document', 'voice'])
def h_catch_all(m):
    res = db_query("SELECT lang, banned, state FROM subjects WHERE uid = ?", (m.chat.id,), fetch=True)
    if not res: return 
    u = res[0]
    if u[1]: return 
    if m.chat.id in OWNERS and u[2] == 'IDLE': return 

    is_input = "INPUT" in u[2]
    ts = datetime.now().strftime("%H:%M")
    txt_log = m.text if m.content_type == 'text' else f"[{m.content_type}]"
    
    db_query("INSERT INTO history (uid, txt, ts, direction) VALUES (?, ?, ?, ?)", 
             (m.chat.id, txt_log, ts, 'IN'), commit=True)
    
    if is_input:
        bot.send_message(m.chat.id, STRINGS[u[0]]['done'], reply_markup=get_main_kb(m.chat.id))
        db_query("UPDATE subjects SET state = 'IDLE' WHERE uid = ?", (m.chat.id,), commit=True)
    
    dept = u[2].split('|')[1] if is_input else "Общий чат"
    header = f"📩 <b>СООБЩЕНИЕ [{dept}]:</b> @{m.from_user.username} (<code>{m.chat.id}</code>)\n"
    
    for adm in OWNERS:
        try:
            if m.content_type == 'text':
                bot.send_message(adm, header + f"Текст: <i>{m.text}</i>", reply_markup=crm_control_kb(m.chat.id))
            else:
                bot.send_message(adm, header)
                bot.copy_message(adm, m.chat.id, m.message_id, reply_markup=crm_control_kb(m.chat.id))
        except: pass

# ==========================================
# 8. ИНТЕРАКТИВНАЯ АДМИНКА И КОНСТРУКТОР
# ==========================================
@bot.callback_query_handler(func=lambda c: True)
def h_callbacks(c):
    p = c.data.split('_')
    action = p[0]
    aid = c.from_user.id
    
    if action == 'showfaq':
        faq = db_query("SELECT answer FROM faq_base WHERE id = ?", (p[1],), fetch=True)
        if faq: bot.send_message(c.message.chat.id, f"💡 <b>FAQ:</b>\n{faq[0][0]}")
        return bot.answer_callback_query(c.id)

    if aid in OWNERS:
        # Переключатели ВКЛ/ВЫКЛ
        if c.data == 'toggle_mod':
            new_v = '0' if get_setting('mod_open') == '1' else '1'
            set_setting('mod_open', new_v)
            bot.edit_message_reply_markup(c.message.chat.id, c.message.message_id, reply_markup=get_admin_panel_kb())
            sync_notify_all(aid, f"⚙️ Изменил прием Модераторов на: <b>{'ВКЛ' if new_v=='1' else 'ВЫКЛ'}</b>")
            return bot.answer_callback_query(c.id, "Статус изменен")

        if c.data == 'toggle_partner':
            new_v = '0' if get_setting('partner_open') == '1' else '1'
            set_setting('partner_open', new_v)
            bot.edit_message_reply_markup(c.message.chat.id, c.message.message_id, reply_markup=get_admin_panel_kb())
            sync_notify_all(aid, f"⚙️ Изменил прием Партнерства на: <b>{'ВКЛ' if new_v=='1' else 'ВЫКЛ'}</b>")
            return bot.answer_callback_query(c.id, "Статус изменен")

        # --- КОНСТРУКТОР АНКЕТ ---
        if c.data == 'adm_builder':
            kb = types.InlineKeyboardMarkup(row_width=2)
            kb.add(
                types.InlineKeyboardButton("📝 Вопросы Модерации", callback_data="build_view_MOD"),
                types.InlineKeyboardButton("🤝 Вопросы Партнерства", callback_data="build_view_PARTNER")
            )
            return bot.send_message(c.message.chat.id, "⚙️ <b>КОНСТРУКТОР АНКЕТ DRAGPOLIT</b>\nВыберите, какую форму хотите настроить:", reply_markup=kb)

        if p[0] == 'build' and p[1] == 'view':
            form_type = p[2]
            qs = db_query("SELECT id, step_order, q_ru FROM form_questions WHERE form_type = ? ORDER BY step_order ASC", (form_type,), fetch=True)
            
            title = "📝 МОДЕРАЦИЯ" if form_type == 'MOD' else "🤝 ПАРТНЕРСТВО"
            res = f"📋 <b>ТЕКУЩИЕ ВОПРОСЫ [{title}]:</b>\n\n"
            kb = types.InlineKeyboardMarkup()

            if qs:
                for q in qs:
                    res += f"<b>{q[1]}.</b> {q[2]}\n"
                    kb.add(types.InlineKeyboardButton(f"🗑 Удалить вопрос #{q[1]}", callback_data=f"build_del_{q[0]}_{form_type}"))
            else:
                res += "<i>Вопросов пока нет.</i>\n"

            kb.add(types.InlineKeyboardButton("➕ Добавить вопрос", callback_data=f"build_add_{form_type}"))
            return bot.send_message(c.message.chat.id, res, reply_markup=kb)

        if p[0] == 'build' and p[1] == 'add':
            form_type = p[2]
            msg = bot.send_message(c.message.chat.id, f"➕ Введите текст нового вопроса для формы <b>{form_type}</b>:")
            bot.register_next_step_handler(msg, step_add_question, form_type)

        if p[0] == 'build' and p[1] == 'del':
            q_id, form_type = p[2], p[3]
            db_query("DELETE FROM form_questions WHERE id = ?", (q_id,), commit=True)
            # Переиндексация порядка
            qs = db_query("SELECT id FROM form_questions WHERE form_type = ? ORDER BY step_order ASC", (form_type,), fetch=True)
            for idx, item in enumerate(qs):
                db_query("UPDATE form_questions SET step_order = ? WHERE id = ?", (idx+1, item[0]), commit=True)
                
            sync_notify_all(aid, f"🗑 Удалил вопрос из формы {form_type}")
            bot.send_message(c.message.chat.id, "✅ Вопрос успешно удален!")

        # CRM Ответы
        if action == 'ans':
            msg = bot.send_message(c.message.chat.id, f"✉️ Введите ваш ответ для <code>{p[1]}</code>:")
            bot.register_next_step_handler(msg, step_send_ans, p[1])
            
        elif action == 'prof':
            u = db_query("SELECT username, reg, note, warns FROM subjects WHERE uid = ?", (p[1],), fetch=True)[0]
            bot.send_message(c.message.chat.id, f"👤 <b>ДОСЬЕ {p[1]}</b>\nНик: @{u[0]}\nЗаметка: <i>{u[2] or 'нет'}</i>\n\nВведите новую заметку или '.':")
            bot.register_next_step_handler(c.message, step_save_note, p[1])

        elif action == 'hist':
            h = db_query("SELECT ts, txt, direction FROM history WHERE uid = ? ORDER BY id DESC LIMIT 7", (p[1],), fetch=True)
            res = f"📜 <b>История {p[1]}:</b>\n\n" + "\n".join([f"[{x[0]}] {x[2]}: {x[1][:60]}" for x in h])
            bot.send_message(c.message.chat.id, res)

        elif action == 'warn':
            db_query("UPDATE subjects SET warns = warns + 1 WHERE uid = ?", (p[1],), commit=True)
            warns = db_query("SELECT warns FROM subjects WHERE uid = ?", (p[1],), fetch=True)[0][0]
            sync_notify_all(aid, f"⚠️ Выдал предупреждение (+1). Всего: {warns}/3", target_uid=p[1])
            bot.answer_callback_query(c.id, "Варн выдан")

        elif action == 'ban':
            db_query("UPDATE subjects SET banned = 1 WHERE uid = ?", (p[1],), commit=True)
            sync_notify_all(aid, "⛔️ ЗАБЛОКИРОВАЛ пользователя", target_uid=p[1])
            bot.answer_callback_query(c.id, "Забанен")

        elif action == 'unban':
            db_query("UPDATE subjects SET banned = 0 WHERE uid = ?", (p[1],), commit=True)
            sync_notify_all(aid, "🟢 РАЗБЛОКИРОВАЛ пользователя", target_uid=p[1])
            bot.answer_callback_query(c.id, "Разбанен")

        elif action == 'appdone':
            decision, app_id, applicant_uid = p[1], p[2], p[3]
            u_lang = db_query("SELECT lang FROM subjects WHERE uid = ?", (applicant_uid,), fetch=True)[0][0]
            
            if decision == 'accept':
                db_query("UPDATE applications SET status = 'ACCEPTED' WHERE id = ?", (app_id,), commit=True)
                msg = "🎉 <b>Поздравляем!</b> Ваша заявка в DragPolit ОДОБРЕНА." if u_lang == 'ru' else "🎉 <b>Congratulations!</b> Your application was ACCEPTED."
                bot.send_message(applicant_uid, msg)
                bot.edit_message_text(f"{c.message.text}\n\n<b>СТАТУС: ✅ ОДОБРЕНО (Admin: {aid})</b>", c.message.chat.id, c.message.message_id)
                sync_notify_all(aid, f"✅ ОДОБРИЛ заявку #{app_id}", target_uid=applicant_uid)
                
            elif decision == 'reject':
                db_query("UPDATE applications SET status = 'REJECTED' WHERE id = ?", (app_id,), commit=True)
                msg = "❌ К сожалению, ваша заявка была отклонена." if u_lang == 'ru' else "❌ Unfortunately, your application was rejected."
                bot.send_message(applicant_uid, msg)
                bot.edit_message_text(f"{c.message.text}\n\n<b>СТАТУС: ❌ ОТКЛОНЕНО (Admin: {aid})</b>", c.message.chat.id, c.message.message_id)
                sync_notify_all(aid, f"❌ ОТКЛОНИЛ заявку #{app_id}", target_uid=applicant_uid)

        elif action == 'adm':
            if c.data == 'adm_stats':
                total_users = db_query("SELECT COUNT(*) FROM subjects", fetch=True)[0][0]
                total_apps = db_query("SELECT COUNT(*) FROM applications", fetch=True)[0][0]
                res = f"📊 <b>СТАТИСТИКА DRAGPOLIT:</b>\n👥 Всего игроков: <b>{total_users}</b>\n📝 Подано заявок: <b>{total_apps}</b>"
                bot.send_message(c.message.chat.id, res)
            
            elif c.data == 'adm_apps_list':
                apps = db_query("SELECT id, type, uid, ts FROM applications WHERE status = 'PENDING' LIMIT 5", fetch=True)
                if not apps: return bot.send_message(c.message.chat.id, "📂 Активных заявок нет.")
                res = "📂 <b>НЕРОЗГЛЯНУТІ ЗАЯВКИ:</b>\n\n" + "\n".join([f"• Заявка #{a[0]} [{a[1]}] от <code>{a[2]}</code>" for a in apps])
                bot.send_message(c.message.chat.id, res)

            elif c.data == 'adm_backup':
                with open(DB_FILE, 'rb') as f: bot.send_document(c.message.chat.id, f, caption="💾 DATABASE BACKUP")

# ==========================================
# 9. КРОКИ АДМИНИСТРАЦИИ
# ==========================================
def step_add_question(m, form_type):
    if m.text == '.': return bot.send_message(m.chat.id, "❌ Отменено.")
    count = db_query("SELECT COUNT(*) FROM form_questions WHERE form_type = ?", (form_type,), fetch=True)[0][0]
    
    db_query("INSERT INTO form_questions (form_type, step_order, q_ru, q_en) VALUES (?, ?, ?, ?)",
             (form_type, count + 1, m.text, m.text), commit=True)
    
    sync_notify_all(m.from_user.id, f"➕ Добавил новый вопрос в анкету {form_type}: <i>{m.text}</i>")
    bot.send_message(m.chat.id, f"✅ Вопрос успешно добавлен под номером <b>#{count + 1}</b>!")

def step_send_ans(m, uid):
    u_lang = db_query("SELECT lang FROM subjects WHERE uid = ?", (uid,), fetch=True)[0][0]
    aid = m.from_user.id
    try:
        content = m.text if m.content_type == 'text' else f"[{m.content_type}]"
        
        if m.content_type == 'text':
            bot.send_message(uid, STRINGS[u_lang]['reply_head'] + f"<i>{m.text}</i>")
        else:
            bot.send_message(uid, STRINGS[u_lang]['reply_head'])
            bot.copy_message(uid, m.chat.id, m.message_id)
        
        db_query("INSERT INTO history (uid, txt, ts, direction, admin_id) VALUES (?, ?, ?, ?, ?)", 
                 (uid, content, "NOW", "OUT", aid), commit=True)
        
        sync_notify_all(aid, f"💬 <b>ОТПРАВЛЕН ОТВЕТ:</b>\n<i>«{content}»</i>", target_uid=uid)
        bot.send_message(m.chat.id, "✅ Ответ успешно отправлен.")
    except Exception as e:
        bot.send_message(m.chat.id, f"❌ Ошибка отправки: {e}")

def step_save_note(m, uid):
    if m.text != ".":
        db_query("UPDATE subjects SET note = ? WHERE uid = ?", (m.text, uid), commit=True)
        sync_notify_all(m.from_user.id, f"📝 Изменил заметку: <i>{m.text}</i>", target_uid=uid)
        bot.send_message(m.chat.id, "✅ Заметка сохранена.")

# ==========================================
# 10. ЗАПУСК БОТА
# ==========================================
if __name__ == '__main__':
    bot.set_my_commands([
        types.BotCommand("start", "Главная страница"),
        types.BotCommand("admin", "Терминал управления")
    ])
    print(f"[{datetime.now().strftime('%H:%M:%S')}] DRAGPOLIT V9 DYNAMIC ENGINE ONLINE.")
    
    while True:
        try:
            bot.infinity_polling(timeout=10, long_polling_timeout=5)
        except Exception as e:
            print(f"⚠️ Переподключение через 5 сек... Ошибка: {e}")
            time.sleep(5)
