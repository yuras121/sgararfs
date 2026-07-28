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
DB_FILE = '/app/data/dragpolit_enterprise_v5.db'

# ==========================================
# 2. МУЛЬТИЯЗЫЧНЫЙ ГЛОССАРИЙ (RU / EN)
# ==========================================
STRINGS = {
    'ru': {
        'start': "🏛 <b>Central Reception DragPolit</b>\nДобро пожаловать в официальный центр управления игры. Выберите нужный раздел или ознакомьтесь с FAQ:",
        'b_faq': "❓ FAQ / Справка", 
        'b_lang': "🌍 English",
        'b_report': "🛡 Жалоба / Репорт", 
        'b_tech': "⚙️ Тех-отдел", 
        'b_mod': "📝 Вакансии (Модерация)",
        'b_partner': "🤝 Партнерство",
        'b_tester': "🧪 Тестирование (Google Play)",
        'b_review': "⭐ Отзыв / Идея",
        'input': "📋 <b>РЕЖИМ ЗАПИСИ:</b> Отправьте ваше сообщение (текст, фото или файл).",
        'done': "✅ Обращение зарегистрировано. Ожидайте ответа руководства.",
        'reply_head': "🏛 <b>ОФИЦИАЛЬНЫЙ ОТВЕТ АДМИНИСТРАЦИИ DRAGPOLIT:</b>\n━━━━━━━━━━━━━━━━━━━━\n\n",
        'banned': "⛔️ Доступ к боту ограничен службой безопасности DragPolit.",
        'mod_closed': "🚫 <b>Набор в команду модерации временно ЗАКРЫТ.</b>\nСледите за новостями проекта DragPolit!",
        'part_closed': "🚫 <b>Прием заявок на партнерство временно ЗАКРЫТ.</b>",
        'tester_closed': "🚫 <b>Прием заявок на тестирование игры временно ЗАКРЫТ.</b>",
        'no_questions': "⚠️ Для данной формы еще не настроены вопросы. Обратитесь к администрации.",
        'app_done': "✅ Спасибо! Ваша заявка успешно отправлена на рассмотрение Высшему Руководству.",
        'app_already': "⚠️ Вы уже подали заявку. Ожидайте решения администрации.",
        'rev_star': "⭐ <b>ОЦЕНКА ПРОЕКТА / ОБНОВЛЕНИЯ:</b>\nВыберите вашу оценку от 1 до 5 звезд:",
        'rev_text': "📝 Напишите ваш отзыв или предложение по улучшению игры DragPolit:",
        'rev_thanks': "🙏 Спасибо за ваш отзыв! Он отправлен на модерацию руководству."
    },
    'en': {
        'start': "🏛 <b>DragPolit Central Reception</b>\nWelcome to the official game center. Select a department or check the FAQ:",
        'b_faq': "❓ FAQ / Help", 
        'b_lang': "🌍 Русский",
        'b_report': "🛡 Report Player", 
        'b_tech': "⚙️ Tech Support", 
        'b_mod': "📝 Vacancies (Moderation)",
        'b_partner': "🤝 Partnership",
        'b_tester': "🧪 Playtest (Google Play)",
        'b_review': "⭐ Feedback / Ideas",
        'input': "📋 <b>RECORD MODE:</b> Type your message or upload media.",
        'done': "✅ Message registered. Please wait for management response.",
        'reply_head': "🏛 <b>OFFICIAL DRAGPOLIT RESPONSE:</b>\n━━━━━━━━━━━━━━━━━━━━\n\n",
        'banned': "⛔️ Access restricted by DragPolit security service.",
        'mod_closed': "🚫 <b>Moderator recruitment is currently CLOSED.</b>\nFollow DragPolit news for updates!",
        'part_closed': "🚫 <b>Partnership applications are currently CLOSED.</b>",
        'tester_closed': "🚫 <b>Playtest applications are currently CLOSED.</b>",
        'no_questions': "⚠️ Form questions are not configured yet. Contact support.",
        'app_done': "✅ Thank you! Your application has been submitted to Management.",
        'app_already': "⚠️ You have already submitted an application. Please wait for review.",
        'rev_star': "⭐ <b>PROJECT / UPDATE RATING:</b>\nChoose your rating from 1 to 5 stars:",
        'rev_text': "📝 Type your review or feedback for the DragPolit team:",
        'rev_thanks': "🙏 Thank you for your feedback! It has been submitted for review."
    }
}

# ==========================================
# 3. БАЗА ДАННЫХ И АВТО-МИГРАЦИИ (CORE)
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
    # Таблицы БД
    db_query('''CREATE TABLE IF NOT EXISTS subjects (
        uid INTEGER PRIMARY KEY, username TEXT, lang TEXT DEFAULT 'ru', 
        state TEXT DEFAULT 'IDLE', banned INTEGER DEFAULT 0, warns INTEGER DEFAULT 0,
        note TEXT, reg TEXT)''', commit=True)
    
    db_query('''CREATE TABLE IF NOT EXISTS settings (
        key TEXT PRIMARY KEY, val TEXT)''', commit=True)
    
    db_query('''CREATE TABLE IF NOT EXISTS form_questions (
        id INTEGER PRIMARY KEY AUTOINCREMENT, form_type TEXT, step_order INTEGER, q_ru TEXT, q_en TEXT)''', commit=True)
    
    db_query('''CREATE TABLE IF NOT EXISTS history (
        id INTEGER PRIMARY KEY AUTOINCREMENT, uid INTEGER, txt TEXT, ts TEXT, direction TEXT, admin_id INTEGER DEFAULT 0)''', commit=True)
    
    db_query('''CREATE TABLE IF NOT EXISTS faq_base (
        id INTEGER PRIMARY KEY AUTOINCREMENT, question TEXT, answer TEXT, lang TEXT)''', commit=True)
    
    db_query('''CREATE TABLE IF NOT EXISTS admin_logs (
        id INTEGER PRIMARY KEY AUTOINCREMENT, aid INTEGER, action TEXT, target_uid INTEGER, ts TEXT)''', commit=True)
        
    db_query('''CREATE TABLE IF NOT EXISTS applications (
        id INTEGER PRIMARY KEY AUTOINCREMENT, type TEXT, uid INTEGER, username TEXT,
        data_json TEXT, status TEXT DEFAULT 'PENDING', ts TEXT)''', commit=True)

    db_query('''CREATE TABLE IF NOT EXISTS reviews (
        id INTEGER PRIMARY KEY AUTOINCREMENT, uid INTEGER, username TEXT, rating INTEGER, txt TEXT, status TEXT DEFAULT 'PENDING', ts TEXT)''', commit=True)

    # 🛠 АВТОМАТИЧЕСКАЯ МИГРАЦИЯ ДЛЯ СТАРОЙ БАЗЫ ДАННЫХ
    try:
        db_query("ALTER TABLE history ADD COLUMN admin_id INTEGER DEFAULT 0", commit=True)
    except Exception: pass

    try:
        db_query("ALTER TABLE subjects ADD COLUMN warns INTEGER DEFAULT 0", commit=True)
    except Exception: pass

    # Настройки по умолчанию
    if not db_query("SELECT val FROM settings WHERE key = 'mod_open'", fetch=True):
        set_setting('mod_open', '1')
    if not db_query("SELECT val FROM settings WHERE key = 'partner_open'", fetch=True):
        set_setting('partner_open', '1')
    if not db_query("SELECT val FROM settings WHERE key = 'tester_open'", fetch=True):
        set_setting('tester_open', '1')

    # Инициализация дефолтных вопросов
    if not db_query("SELECT id FROM form_questions WHERE form_type = 'MOD'", fetch=True):
        db_query("INSERT INTO form_questions (form_type, step_order, q_ru, q_en) VALUES (?, ?, ?, ?)",
                 ('MOD', 1, "Укажите ваш возраст и имя/никнейм:", "Specify your age and name/nickname:"), commit=True)
        db_query("INSERT INTO form_questions (form_type, step_order, q_ru, q_en) VALUES (?, ?, ?, ?)",
                 ('MOD', 2, "Опишите ваш опыт модерации в Telegram/играх:", "Describe your moderation experience:"), commit=True)
        db_query("INSERT INTO form_questions (form_type, step_order, q_ru, q_en) VALUES (?, ?, ?, ?)",
                 ('MOD', 3, "Сколько часов в день вы готовы уделять игре?", "How many hours per day can you dedicate?"), commit=True)

    if not db_query("SELECT id FROM form_questions WHERE form_type = 'PARTNER'", fetch=True):
        db_query("INSERT INTO form_questions (form_type, step_order, q_ru, q_en) VALUES (?, ?, ?, ?)",
                 ('PARTNER', 1, "Укажите ссылку на ваш канал/проект:", "Link to your channel/project:"), commit=True)
        db_query("INSERT INTO form_questions (form_type, step_order, q_ru, q_en) VALUES (?, ?, ?, ?)",
                 ('PARTNER', 2, "Укажите размер аудитории:", "Audience size:"), commit=True)

    if not db_query("SELECT id FROM form_questions WHERE form_type = 'TESTER'", fetch=True):
        db_query("INSERT INTO form_questions (form_type, step_order, q_ru, q_en) VALUES (?, ?, ?, ?)",
                 ('TESTER', 1, "Укажите ваш e-mail аккаунта Google Play (для выдачи доступа к тесту):", "Specify your Google Play e-mail (for test access):"), commit=True)
        db_query("INSERT INTO form_questions (form_type, step_order, q_ru, q_en) VALUES (?, ?, ?, ?)",
                 ('TESTER', 2, "Укажите модель смартфона и версию Android (например: Samsung S21, Android 13):", "Specify your device model and Android version:"), commit=True)
        db_query("INSERT INTO form_questions (form_type, step_order, q_ru, q_en) VALUES (?, ?, ?, ?)",
                 ('TESTER', 3, "Опишите опыт тестирования и сколько времени готовы уделить поиску багов:", "Describe testing experience and time you can dedicate:"), commit=True)

init_db()

# ==========================================
# 4. УМНАЯ СИНХРОНИЗАЦИЯ И КЛАВИАТУРЫ
# ==========================================
def sync_notify_all(sender_id, text, target_uid=None):
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
    kb.add(STRINGS[lang]['b_tester'], STRINGS[lang]['b_review'])
    kb.add(STRINGS[lang]['b_faq'], STRINGS[lang]['b_lang'])
    return kb

def get_admin_panel_kb():
    mod_status = "🟢 ВКЛ" if get_setting('mod_open') == '1' else "🔴 ВЫКЛ"
    part_status = "🟢 ВКЛ" if get_setting('partner_open') == '1' else "🔴 ВЫКЛ"
    test_status = "🟢 ВКЛ" if get_setting('tester_open') == '1' else "🔴 ВЫКЛ"

    kb = types.InlineKeyboardMarkup(row_width=2)
    kb.add(
        types.InlineKeyboardButton(f"Модерация: {mod_status}", callback_data="toggle_mod"),
        types.InlineKeyboardButton(f"Партнерство: {part_status}", callback_data="toggle_partner")
    )
    kb.add(
        types.InlineKeyboardButton(f"Тестирование: {test_status}", callback_data="toggle_tester"),
        types.InlineKeyboardButton("⚙️ КОНСТРУКТОР АНКЕТ", callback_data="adm_builder")
    )
    kb.add(
        types.InlineKeyboardButton("📢 РАССЫЛКА", callback_data="adm_broadcast"),
        types.InlineKeyboardButton("📂 Список Заявок", callback_data="adm_apps_list")
    )
    kb.add(
        types.InlineKeyboardButton("⭐ Отзывы и Идеи", callback_data="adm_reviews_list"),
        types.InlineKeyboardButton("📊 Статистика", callback_data="adm_stats")
    )
    kb.add(
        types.InlineKeyboardButton("➕ Добавить FAQ", callback_data="adm_faq_add"),
        types.InlineKeyboardButton("💾 Бэкап БД", callback_data="adm_backup")
    )
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

def review_rating_kb():
    kb = types.InlineKeyboardMarkup(row_width=5)
    kb.add(
        types.InlineKeyboardButton("⭐ 1", callback_data="star_1"),
        types.InlineKeyboardButton("⭐ 2", callback_data="star_2"),
        types.InlineKeyboardButton("⭐ 3", callback_data="star_3"),
        types.InlineKeyboardButton("⭐ 4", callback_data="star_4"),
        types.InlineKeyboardButton("⭐ 5", callback_data="star_5")
    )
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
    bot.send_message(m.chat.id, "🏛 <b>ТЕРМИНАЛ УПРАВЛЕНИЯ DRAGPOLIT</b>\nУправление анкетами, рассылкой, тестерами, тикетами и настройками.", reply_markup=get_admin_panel_kb())

# ОБРАБОТКА ТЕКСТОВЫХ КНОПОК
@bot.message_handler(func=lambda m: any(m.text in d.values() for d in STRINGS.values()))
def h_menu(m):
    res = db_query("SELECT lang, banned FROM subjects WHERE uid = ?", (m.chat.id,), fetch=True)
    if not res or res[0][1]: return
    lang = res[0][0]

    if m.text in [STRINGS['ru']['b_lang'], STRINGS['en']['b_lang']]:
        new_lang = 'en' if lang == 'ru' else 'ru'
        db_query("UPDATE subjects SET lang = ? WHERE uid = ?", (new_lang, m.chat.id), commit=True)
        msg = "🌐 Язык изменен на Русский!" if new_lang == 'ru' else "🌐 Language set to English!"
        return bot.send_message(m.chat.id, msg, reply_markup=get_main_kb(m.chat.id))

    if m.text in [STRINGS['ru']['b_faq'], STRINGS['en']['b_faq']]:
        faqs = db_query("SELECT question, id FROM faq_base WHERE lang = ?", (lang,), fetch=True)
        if not faqs: return bot.send_message(m.chat.id, "ℹ️ FAQ пуст.")
        kb = types.InlineKeyboardMarkup()
        for q in faqs: kb.add(types.InlineKeyboardButton(q[0], callback_data=f"showfaq_{q[1]}"))
        return bot.send_message(m.chat.id, "<b>Часто задаваемые вопросы:</b>", reply_markup=kb)

    if m.text in [STRINGS['ru']['b_review'], STRINGS['en']['b_review']]:
        return bot.send_message(m.chat.id, STRINGS[lang]['rev_star'], reply_markup=review_rating_kb())

    if m.text in [STRINGS['ru']['b_mod'], STRINGS['en']['b_mod']]:
        if get_setting('mod_open') == '0': return bot.send_message(m.chat.id, STRINGS[lang]['mod_closed'])
        return start_dynamic_form(m.chat.id, 'MOD', lang)

    if m.text in [STRINGS['ru']['b_partner'], STRINGS['en']['b_partner']]:
        if get_setting('partner_open') == '0': return bot.send_message(m.chat.id, STRINGS[lang]['part_closed'])
        return start_dynamic_form(m.chat.id, 'PARTNER', lang)

    if m.text in [STRINGS['ru']['b_tester'], STRINGS['en']['b_tester']]:
        if get_setting('tester_open') == '0': return bot.send_message(m.chat.id, STRINGS[lang]['tester_closed'])
        return start_dynamic_form(m.chat.id, 'TESTER', lang)

    db_query("UPDATE subjects SET state = ? WHERE uid = ?", (f"INPUT|{m.text}", m.chat.id), commit=True)
    bot.send_message(m.chat.id, STRINGS[lang]['input'], reply_markup=types.ReplyKeyboardRemove())

# ==========================================
# 6. ДИНАМИЧЕСКИЙ ДВИЖОК АНКЕТИРОВАНИЯ
# ==========================================
def start_dynamic_form(uid, form_type, lang):
    check_app = db_query("SELECT id FROM applications WHERE uid = ? AND type = ? AND status = 'PENDING'", (uid, form_type), fetch=True)
    if check_app: return bot.send_message(uid, STRINGS[lang]['app_already'])

    questions = db_query("SELECT id, q_ru, q_en FROM form_questions WHERE form_type = ? ORDER BY step_order ASC", (form_type,), fetch=True)
    if not questions: return bot.send_message(uid, STRINGS[lang]['no_questions'])

    answers_init = json.dumps([])
    db_query("UPDATE subjects SET state = ? WHERE uid = ?", (f"RUNFORM|{form_type}|0|{answers_init}", uid), commit=True)
    
    q_text = questions[0][1] if lang == 'ru' else questions[0][2]
    
    headers = {
        'MOD': "📝 <b>АНКЕТА МОДЕРАТОРА</b>\n\n",
        'PARTNER': "🤝 <b>ЗАЯВКА НА ПАРТНЕРСТВО</b>\n\n",
        'TESTER': "🧪 <b>ЗАЯВКА НА ТЕСТИРОВАНИЕ (GOOGLE PLAY)</b>\n\n"
    }
    header = headers.get(form_type, "📋 <b>ЗАПОЛНЕНИЕ АНКЕТЫ</b>\n\n")
    
    msg = bot.send_message(uid, f"{header}<b>Шаг 1/{len(questions)}:</b> {q_text}", reply_markup=types.ReplyKeyboardRemove())
    bot.register_next_step_handler(msg, process_form_step)

def process_form_step(m):
    # СБРОС АНКЕТЫ ПРИ ВВОДЕ КОМАНДЫ (НАПР. /start ИЛИ /admin)
    if m.text and m.text.startswith('/'):
        db_query("UPDATE subjects SET state = 'IDLE' WHERE uid = ?", (m.chat.id,), commit=True)
        bot.send_message(m.chat.id, "❌ Заполнение анкеты отменено.", reply_markup=get_main_kb(m.chat.id))
        if m.text == '/start': return h_start(m)
        if m.text == '/admin': return h_admin(m)
        return

    res = db_query("SELECT state, lang FROM subjects WHERE uid = ?", (m.chat.id,), fetch=True)
    if not res or "RUNFORM" not in res[0][0]: return
    
    parts = res[0][0].split('|', 3)
    form_type, q_index, answers, lang = parts[1], int(parts[2]), json.loads(parts[3]), res[0][1]

    answers.append(m.text)
    questions = db_query("SELECT q_ru, q_en FROM form_questions WHERE form_type = ? ORDER BY step_order ASC", (form_type,), fetch=True)
    next_index = q_index + 1

    if next_index < len(questions):
        db_query("UPDATE subjects SET state = ? WHERE uid = ?", (f"RUNFORM|{form_type}|{next_index}|{json.dumps(answers)}", m.chat.id), commit=True)
        q_text = questions[next_index][0] if lang == 'ru' else questions[next_index][1]
        msg = bot.send_message(m.chat.id, f"<b>Шаг {next_index+1}/{len(questions)}:</b> {q_text}")
        bot.register_next_step_handler(msg, process_form_step)
    else:
        db_query("UPDATE subjects SET state = 'IDLE' WHERE uid = ?", (m.chat.id,), commit=True)
        ts = datetime.now().strftime("%Y-%m-%d %H:%M")
        db_query("INSERT INTO applications (type, uid, username, data_json, ts) VALUES (?, ?, ?, ?, ?)", 
                 (form_type, m.chat.id, m.from_user.username, json.dumps(answers), ts), commit=True)
        app_id = db_query("SELECT last_insert_rowid()", fetch=True)[0][0]

        bot.send_message(m.chat.id, STRINGS[lang]['app_done'], reply_markup=get_main_kb(m.chat.id))

        titles = {
            'MOD': "📝 <b>НОВАЯ ЗАЯВКА В МОДЕРАТОРЫ</b>",
            'PARTNER': "🤝 <b>НОВАЯ ЗАЯВКА НА ПАРТНЕРСТВО</b>",
            'TESTER': "🧪 <b>НОВАЯ ЗАЯВКА ТЕСТИРОВЩИКА (GOOGLE PLAY)</b>"
        }
        title = titles.get(form_type, "📋 <b>НОВАЯ ЗАЯВКА</b>")
        
        card = f"{title} <b>#{app_id}</b>\n━━━━━━━━━━━━━━━━━━━━\n👤 <b>Заявитель:</b> @{m.from_user.username} (<code>{m.chat.id}</code>)\n\n"
        for idx, q_item in enumerate(questions):
            ans_val = answers[idx] if idx < len(answers) else '—'
            card += f"<b>❓ {q_item[0]}</b>\n💬 <i>{ans_val}</i>\n\n"
        card += f"📅 <b>Дата:</b> {ts}"

        for adm in OWNERS:
            try: bot.send_message(adm, card, reply_markup=app_review_kb(app_id, m.chat.id))
            except: pass

# ==========================================
# 7. ОБРАБОТКА ВХОДЯЩИХ (TICKETS & REVIEWS)
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
    
    # Безопасный логинг в историю
    try:
        db_query("INSERT INTO history (uid, txt, ts, direction) VALUES (?, ?, ?, ?)", (m.chat.id, txt_log, ts, 'IN'), commit=True)
    except: pass

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
# 8. ИНТЕРАКТИВНАЯ АДМИНКА
# ==========================================
@bot.callback_query_handler(func=lambda c: True)
def h_callbacks(c):
    p = c.data.split('_')
    action = p[0]
    aid = c.from_user.id
    
    if action == 'star':
        rating = int(p[1])
        lang = db_query("SELECT lang FROM subjects WHERE uid = ?", (c.from_user.id,), fetch=True)[0][0]
        db_query("UPDATE subjects SET state = ? WHERE uid = ?", (f"REVIEW_TEXT|{rating}", c.from_user.id), commit=True)
        msg = bot.send_message(c.message.chat.id, STRINGS[lang]['rev_text'])
        bot.register_next_step_handler(msg, step_save_review)
        return bot.answer_callback_query(c.id)

    if action == 'showfaq':
        faq = db_query("SELECT answer FROM faq_base WHERE id = ?", (p[1],), fetch=True)
        if faq: bot.send_message(c.message.chat.id, f"💡 <b>FAQ:</b>\n{faq[0][0]}")
        return bot.answer_callback_query(c.id)

    if aid in OWNERS:
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

        if c.data == 'toggle_tester':
            new_v = '0' if get_setting('tester_open') == '1' else '1'
            set_setting('tester_open', new_v)
            bot.edit_message_reply_markup(c.message.chat.id, c.message.message_id, reply_markup=get_admin_panel_kb())
            sync_notify_all(aid, f"⚙️ Изменил прием Тестировщиков на: <b>{'ВКЛ' if new_v=='1' else 'ВЫКЛ'}</b>")
            return bot.answer_callback_query(c.id, "Статус изменен")

        if c.data == 'adm_builder':
            kb = types.InlineKeyboardMarkup(row_width=1)
            kb.add(
                types.InlineKeyboardButton("📝 Вопросы Модерации", callback_data="build_view_MOD"),
                types.InlineKeyboardButton("🤝 Вопросы Партнерства", callback_data="build_view_PARTNER"),
                types.InlineKeyboardButton("🧪 Вопросы Тестировщиков (GP)", callback_data="build_view_TESTER")
            )
            return bot.send_message(c.message.chat.id, "⚙️ <b>КОНСТРУКТОР АНКЕТ DRAGPOLIT</b>\nВыберите форму для настройки:", reply_markup=kb)

        # ЗАПУСК РАССЫЛКИ
        if c.data == 'adm_broadcast':
            msg = bot.send_message(c.message.chat.id, "📢 <b>ГЛОБАЛЬНАЯ РАССЫЛКА</b>\n\nОтправьте сообщение (текст, фото с описанием, видео, файл или стикер), которое нужно разослать всем пользователям:\n\n<i>(Напишите '.' для отмены)</i>")
            return bot.register_next_step_handler(msg, step_broadcast)

        # ПРОСМОТР НЕРАССМОТРЕННЫХ ЗАЯВОК
        if c.data == 'adm_apps_list':
            apps = db_query("SELECT id, type, uid, ts FROM applications WHERE status = 'PENDING' LIMIT 10", fetch=True)
            if not apps:
                return bot.send_message(c.message.chat.id, "📂 Активных нерассмотренных заявок нет.")
            res = "📂 <b>НЕРАССМОТРЕННЫЕ ЗАЯВКИ:</b>\n\n"
            for a in apps:
                res += f"• <b>Заявка #{a[0]} [{a[1]}]</b> от <code>{a[2]}</code> ({a[3]})\n"
            return bot.send_message(c.message.chat.id, res)

        # ДОБАВЛЕНИЕ FAQ
        if c.data == 'adm_faq_add':
            msg = bot.send_message(c.message.chat.id, "➕ <b>ДОБАВЛЕНИЕ FAQ</b>\nВведите ВОПРОС (или напишите '.' для отмены):")
            return bot.register_next_step_handler(msg, step_faq_q)

        if p[0] == 'build' and p[1] == 'view':
            form_type = p[2]
            qs = db_query("SELECT id, step_order, q_ru FROM form_questions WHERE form_type = ? ORDER BY step_order ASC", (form_type,), fetch=True)
            res = f"📋 <b>ТЕКУЩИЕ ВОПРОСЫ [{form_type}]:</b>\n\n"
            kb = types.InlineKeyboardMarkup()
            if qs:
                for q in qs:
                    res += f"<b>{q[1]}.</b> {q[2]}\n"
                    kb.add(types.InlineKeyboardButton(f"🗑 Удалить вопрос #{q[1]}", callback_data=f"build_del_{q[0]}_{form_type}"))
            else: res += "<i>Вопросов нет.</i>\n"
            kb.add(types.InlineKeyboardButton("➕ Добавить вопрос", callback_data=f"build_add_{form_type}"))
            return bot.send_message(c.message.chat.id, res, reply_markup=kb)

        if p[0] == 'build' and p[1] == 'add':
            msg = bot.send_message(c.message.chat.id, f"➕ Введите текст нового вопроса для формы <b>{p[2]}</b>:")
            bot.register_next_step_handler(msg, step_add_question, p[2])

        if p[0] == 'build' and p[1] == 'del':
            db_query("DELETE FROM form_questions WHERE id = ?", (p[2],), commit=True)
            bot.send_message(c.message.chat.id, "✅ Вопрос удален!")

        if action == 'ans':
            msg = bot.send_message(c.message.chat.id, f"✉️ Введите ваш ответ для <code>{p[1]}</code>:")
            bot.register_next_step_handler(msg, step_send_ans, p[1])

        elif action == 'prof':
            u = db_query("SELECT username, reg, note, warns FROM subjects WHERE uid = ?", (p[1],), fetch=True)[0]
            bot.send_message(c.message.chat.id, f"👤 <b>ДОСЬЕ {p[1]}</b>\nНик: @{u[0]}\nЗаметка: <i>{u[2] or 'нет'}</i>\n\nВведите новую заметку или '.':")
            bot.register_next_step_handler(c.message, step_save_note, p[1])

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
                total_revs = db_query("SELECT COUNT(*) FROM reviews", fetch=True)[0][0]
                res = f"📊 <b>СТАТИСТИКА DRAGPOLIT:</b>\n👥 Игроков: <b>{total_users}</b>\n📝 Заявок: <b>{total_apps}</b>\n⭐ Отзывов: <b>{total_revs}</b>"
                bot.send_message(c.message.chat.id, res)
            
            elif c.data == 'adm_reviews_list':
                revs = db_query("SELECT id, rating, txt, username FROM reviews ORDER BY id DESC LIMIT 5", fetch=True)
                if not revs: return bot.send_message(c.message.chat.id, "⭐ Отзывов пока нет.")
                res = "⭐ <b>ПОСЛЕДНИЕ ОТЗЫВЫ:</b>\n\n"
                for r in revs:
                    stars = "⭐" * r[1]
                    res += f"<b>#{r[0]}</b> {stars} от @{r[3]}\n<i>└ {r[2][:80]}</i>\n\n"
                bot.send_message(c.message.chat.id, res)

            elif c.data == 'adm_backup':
                with open(DB_FILE, 'rb') as f: bot.send_document(c.message.chat.id, f, caption="💾 DATABASE BACKUP")

# ==========================================
# 9. КРОКИ АДМИНИСТРАЦИИ И ПОЛЬЗОВАТЕЛЕЙ
# ==========================================
def step_broadcast(m):
    if m.text == '.':
        return bot.send_message(m.chat.id, "❌ Рассылка отменена.")

    users = db_query("SELECT uid FROM subjects WHERE banned = 0", fetch=True)
    if not users:
        return bot.send_message(m.chat.id, "❌ Нет активных пользователей для рассылки.")

    bot.send_message(m.chat.id, f"⏳ <b>Запуск рассылки...</b>\nПолучателей: {len(users)}")

    succeeded = 0
    failed = 0

    for u in users:
        uid = u[0]
        try:
            bot.copy_message(chat_id=uid, from_chat_id=m.chat.id, message_id=m.message_id)
            succeeded += 1
            time.sleep(0.04) # Антифлуд задержка Telegram (25 сообщений в сек)
        except Exception:
            failed += 1

    res_text = (f"📢 <b>РАССЫЛКА ЗАВЕРШЕНА!</b>\n"
                f"━━━━━━━━━━━━━━━━━━━━\n"
                f"✅ Успешно доставлено: <b>{succeeded}</b>\n"
                f"❌ Ошибок / Заблокировали: <b>{failed}</b>\n"
                f"👥 Всего в базе: <b>{len(users)}</b>")

    bot.send_message(m.chat.id, res_text)
    sync_notify_all(m.from_user.id, f"📢 Провел рассылку.\nДоставлено: {succeeded} | Ошибок: {failed}")

def step_faq_q(m):
    if m.text == '.': return bot.send_message(m.chat.id, "❌ Отменено.")
    msg = bot.send_message(m.chat.id, f"❓ <b>Вопрос:</b> <i>{m.text}</i>\n\nТеперь введите ОТВЕТ:")
    bot.register_next_step_handler(msg, step_faq_a, m.text)

def step_faq_a(m, question):
    if m.text == '.': return bot.send_message(m.chat.id, "❌ Отменено.")
    db_query("INSERT INTO faq_base (question, answer, lang) VALUES (?, ?, ?)", 
             (question, m.text, 'ru'), commit=True)
    sync_notify_all(m.from_user.id, f"➕ Добавил пункт в FAQ: {question}")
    bot.send_message(m.chat.id, "✅ Пункт успешно добавлен в FAQ!")

def step_save_review(m):
    st = db_query("SELECT state, lang FROM subjects WHERE uid = ?", (m.chat.id,), fetch=True)[0]
    rating = int(st[0].split('|')[1])
    lang = st[1]
    ts = datetime.now().strftime("%Y-%m-%d %H:%M")

    db_query("INSERT INTO reviews (uid, username, rating, txt, ts) VALUES (?, ?, ?, ?, ?)",
             (m.chat.id, m.from_user.username, rating, m.text, ts), commit=True)
    
    db_query("UPDATE subjects SET state = 'IDLE' WHERE uid = ?", (m.chat.id,), commit=True)
    bot.send_message(m.chat.id, STRINGS[lang]['rev_thanks'], reply_markup=get_main_kb(m.chat.id))

    stars = "⭐" * rating
    rev_card = (f"⭐ <b>НОВЫЙ ОТЗЫВ / ИДЕЯ</b>\n━━━━━━━━━━━━━━━━━━━━\n"
                f"👤 <b>От:</b> @{m.from_user.username} (<code>{m.chat.id}</code>)\n"
                f"Оценка: {stars} ({rating}/5)\n"
                f"<b>Текст:</b> <i>{m.text}</i>\n📅 {ts}")
    for adm in OWNERS:
        try: bot.send_message(adm, rev_card)
        except: pass

def step_add_question(m, form_type):
    if m.text == '.': return bot.send_message(m.chat.id, "❌ Отменено.")
    count = db_query("SELECT COUNT(*) FROM form_questions WHERE form_type = ?", (form_type,), fetch=True)[0][0]
    db_query("INSERT INTO form_questions (form_type, step_order, q_ru, q_en) VALUES (?, ?, ?, ?)", (form_type, count + 1, m.text, m.text), commit=True)
    sync_notify_all(m.from_user.id, f"➕ Добавил вопрос в анкету {form_type}: <i>{m.text}</i>")
    bot.send_message(m.chat.id, f"✅ Вопрос успешно добавлен под номером <b>#{count + 1}</b>!")

# АВАРИЙНО-ЗАЩИЩЕННАЯ ОТПРАВКА ОТВЕТА ПОЛЬЗОВАТЕЛЮ
def step_send_ans(m, uid):
    res_user = db_query("SELECT lang FROM subjects WHERE uid = ?", (uid,), fetch=True)
    u_lang = res_user[0][0] if res_user else 'ru'
    aid = m.from_user.id
    
    try:
        content = m.text if m.content_type == 'text' else f"[{m.content_type}]"
        
        # 1. Отправляем ответ пользователю
        if m.content_type == 'text':
            bot.send_message(uid, STRINGS[u_lang]['reply_head'] + f"<i>{m.text}</i>")
        else:
            bot.send_message(uid, STRINGS[u_lang]['reply_head'])
            bot.copy_message(uid, m.chat.id, m.message_id)
        
        # 2. Безопасно сохраняем историю (с обработкой старых баз)
        try:
            db_query("INSERT INTO history (uid, txt, ts, direction, admin_id) VALUES (?, ?, ?, ?, ?)", 
                     (uid, content, "NOW", "OUT", aid), commit=True)
        except Exception:
            db_query("INSERT INTO history (uid, txt, ts, direction) VALUES (?, ?, ?, ?)", 
                     (uid, content, "NOW", "OUT"), commit=True)
        
        sync_notify_all(aid, f"💬 <b>ОТПРАВЛЕН ОТВЕТ:</b>\n<i>«{content}»</i>", target_uid=uid)
        bot.send_message(m.chat.id, "✅ Ответ успешно доставлен игроку!")
    except Exception as e:
        bot.send_message(m.chat.id, f"❌ Ошибка доставки сообщения пользователю: {e}")

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
    print(f"[{datetime.now().strftime('%H:%M:%S')}] DRAGPOLIT V13 STABLE SYSTEM ONLINE.")
    
    while True:
        try:
            bot.infinity_polling(timeout=10, long_polling_timeout=5)
        except Exception as e:
            print(f"⚠️ Переподключение через 5 сек... Ошибка: {e}")
            time.sleep(5)
