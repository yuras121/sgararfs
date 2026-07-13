import os
import sqlite3
import telebot
import sys
from telebot import types
from datetime import datetime
from threading import Lock

# ==========================================
# 1. СИСТЕМНОЕ ЯДРО
# ==========================================
TOKEN = os.environ.get('TOKEN')
OWNERS = [1614259542, 7716987740] # Высшее Руководство

if not TOKEN:
    print("❌ КРИТИЧЕСКАЯ ОШИБКА: Токен не найден в Environment!")
    sys.exit(1)

bot = telebot.TeleBot(TOKEN, parse_mode='HTML')
db_lock = Lock()
DB_FILE = 'dragpolit_enterprise_v5.db'

# Стейты для админов (в памяти для скорости)
admin_states = {}

# ==========================================
# 2. МУЛЬТИЯЗЫЧНЫЙ ГЛОССАРИЙ
# ==========================================
STRINGS = {
    'ru': {
        'start': "🏛 <b>Центральная Приемная DragPolit</b>\nВыберите департамент или ознакомьтесь с частыми вопросами (FAQ):",
        'b_faq': "❓ FAQ / Справка", 'b_lang': "🌍 English",
        'b_report': "🛡 Жалоба", 'b_tech': "⚙️ Тех-отдел", 'b_other': "💬 Связь",
        'input': "📋 <b>РЕЖИМ ЗАПИСИ:</b> Напишите ваше сообщение (текст/медиа).",
        'done': "✅ Сообщение зарегистрировано. Ожидайте ответа руководства.",
        'reply': "🏛 <b>ОТВЕТ АДМИНИСТРАЦИИ:</b>\n━━━━━━━━━━━━━━━━━━━━\n\n",
        'banned': "⛔️ Доступ ограничен службой безопасности."
    },
    'en': {
        'start': "🏛 <b>DragPolit Central Reception</b>\nChoose a department or check the FAQ:",
        'b_faq': "❓ FAQ / Help", 'b_lang': "🌍 Русский",
        'b_report': "🛡 Report", 'b_tech': "⚙️ Tech Support", 'b_other': "💬 Contact",
        'input': "📋 <b>RECORD MODE:</b> Type your message (text/media).",
        'done': "✅ Message registered. Wait for management's response.",
        'reply': "🏛 <b>OFFICIAL RESPONSE:</b>\n━━━━━━━━━━━━━━━━━━━━\n\n",
        'banned': "⛔️ Access restricted by security."
    }
}

# ==========================================
# 3. БАЗА ДАННЫХ (CORE)
# ==========================================
def db_query(sql, params=(), fetch=False, commit=False):
    with db_lock:
        with sqlite3.connect(DB_FILE, timeout=10) as conn:
            conn.execute("PRAGMA journal_mode=WAL;")
            c = conn.cursor()
            c.execute(sql, params)
            res = c.fetchall() if fetch else None
            if commit: conn.commit()
            return res

def init_db():
    # Пользователи + Заметки
    db_query('''CREATE TABLE IF NOT EXISTS subjects (
        uid INTEGER PRIMARY KEY, username TEXT, lang TEXT DEFAULT 'ru', 
        state TEXT DEFAULT 'IDLE', banned INTEGER DEFAULT 0, note TEXT, reg TEXT)''', commit=True)
    # Сообщения (Архив)
    db_query('''CREATE TABLE IF NOT EXISTS history (
        id INTEGER PRIMARY KEY AUTOINCREMENT, uid INTEGER, txt TEXT, ts TEXT)''', commit=True)
    # FAQ база
    db_query('''CREATE TABLE IF NOT EXISTS faq_base (
        id INTEGER PRIMARY KEY AUTOINCREMENT, question TEXT, answer TEXT, lang TEXT)''', commit=True)
    
    # Пример FAQ
    if not db_query("SELECT * FROM faq_base", fetch=True):
        db_query("INSERT INTO faq_base (question, answer, lang) VALUES (?, ?, ?)", 
                 ("Как начать игру?", "Зайдите на сервер по IP в нашей группе.", "ru"), commit=True)

init_db()

# ==========================================
# 4. UX: КЛАВИАТУРЫ И ПАНЕЛИ
# ==========================================
def get_main_kb(uid):
    lang = db_query("SELECT lang FROM subjects WHERE uid = ?", (uid,), fetch=True)[0][0]
    kb = types.ReplyKeyboardMarkup(resize_keyboard=True, row_width=2)
    kb.add(STRINGS[lang]['b_report'], STRINGS[lang]['b_tech'], STRINGS[lang]['b_other'])
    kb.add(STRINGS[lang]['b_faq'], STRINGS[lang]['b_lang'])
    return kb

def get_admin_panel_kb():
    kb = types.InlineKeyboardMarkup(row_width=1)
    kb.add(
        types.InlineKeyboardButton("📢 Рассылка ВСЕМ", callback_data="adm_broadcast"),
        types.InlineKeyboardButton("➕ Добавить вопрос в FAQ", callback_data="adm_faq_add"),
        types.InlineKeyboardButton("📋 Статистика и База", callback_data="adm_stats"),
        types.InlineKeyboardButton("📂 Бэкап Базы данных", callback_data="adm_backup")
    )
    return kb

def crm_control_kb(uid):
    kb = types.InlineKeyboardMarkup(row_width=2)
    kb.add(
        types.InlineKeyboardButton("✉️ Ответить", callback_data=f"ans_{uid}"),
        types.InlineKeyboardButton("👤 Профиль/Note", callback_data=f"prof_{uid}"),
        types.InlineKeyboardButton("⛔️ BAN", callback_data=f"ban_{uid}")
    )
    return kb

# ==========================================
# 5. ОСНОВНОЙ ФУНКЦИОНАЛ
# ==========================================
@bot.message_handler(commands=['start'])
def h_start(m):
    res = db_query("SELECT lang, banned FROM subjects WHERE uid = ?", (m.chat.id,), fetch=True)
    if not res:
        dt = datetime.now().strftime("%Y-%m-%d")
        db_query("INSERT INTO subjects (uid, username, reg) VALUES (?, ?, ?)", 
                 (m.chat.id, m.from_user.username, dt), commit=True)
        res = [('ru', 0)]
    
    if res[0][1]: return bot.send_message(m.chat.id, STRINGS[res[0][0]]['banned'])
    db_query("UPDATE subjects SET state = 'IDLE' WHERE uid = ?", (m.chat.id,), commit=True)
    bot.send_message(m.chat.id, STRINGS[res[0][0]]['start'], reply_markup=get_main_kb(m.chat.id))

@bot.message_handler(commands=['admin'])
def h_admin(m):
    if m.chat.id not in OWNERS: return
    bot.send_message(m.chat.id, "👑 <b>ТЕРМИНАЛ DRAGPOLIT</b>\nВсе системы активны. Выберите действие:", reply_markup=get_admin_panel_kb())

# ОБРАБОТКА МЕНЮ
@bot.message_handler(func=lambda m: any(m.text in d.values() for d in STRINGS.values()))
def h_menu(m):
    u = db_query("SELECT lang, banned FROM subjects WHERE uid = ?", (m.chat.id,), fetch=True)[0]
    if u[1]: return
    
    # Смена языка
    if m.text in [STRINGS['ru']['b_lang'], STRINGS['en']['b_lang']]:
        new_lang = 'en' if u[0] == 'ru' else 'ru'
        db_query("UPDATE subjects SET lang = ? WHERE uid = ?", (new_lang, m.chat.id), commit=True)
        return bot.send_message(m.chat.id, "🌐 Language: OK", reply_markup=get_main_kb(m.chat.id))

    # Логика FAQ
    if m.text in [STRINGS['ru']['b_faq'], STRINGS['en']['b_faq']]:
        faqs = db_query("SELECT question, id FROM faq_base WHERE lang = ?", (u[0],), fetch=True)
        if not faqs: return bot.send_message(m.chat.id, "FAQ пуст.")
        kb = types.InlineKeyboardMarkup()
        for q in faqs: kb.add(types.InlineKeyboardButton(q[0], callback_data=f"showfaq_{q[1]}"))
        return bot.send_message(m.chat.id, "<b>Часто задаваемые вопросы:</b>", reply_markup=kb)

    # Вход в режим ввода
    db_query("UPDATE subjects SET state = ? WHERE uid = ?", (f"INPUT|{m.text}", m.chat.id), commit=True)
    bot.send_message(m.chat.id, STRINGS[u[0]]['input'], reply_markup=types.ReplyKeyboardRemove())

# ЛОВИМ ЛЮБЫЕ СООБЩЕНИЯ (ЧАТ С АДМИНОМ)
@bot.message_handler(content_types=['text', 'photo', 'video', 'document', 'voice'])
def h_catch_all(m):
    u = db_query("SELECT lang, banned, state FROM subjects WHERE uid = ?", (m.chat.id,), fetch=True)[0]
    if u[1]: return

    is_input_mode = "INPUT" in u[2]
    
    # Регистрация в истории
    txt_log = m.text if m.content_type == 'text' else f"[Медиа:{m.content_type}]"
    db_query("INSERT INTO history (uid, txt, ts) VALUES (?, ?, ?)", 
             (m.chat.id, txt_log, datetime.now().strftime("%H:%M")), commit=True)
    
    if is_input_mode:
        bot.send_message(m.chat.id, STRINGS[u[0]]['done'], reply_markup=get_main_kb(m.chat.id))
        db_query("UPDATE subjects SET state = 'IDLE' WHERE uid = ?", (m.chat.id,), commit=True)
    
    # Уведомление админам
    header = f"💬 <b>СООБЩЕНИЕ ОТ:</b> @{m.from_user.username} (<code>{m.chat.id}</code>)\n"
    if is_input_mode: header = f"📑 <b>ТИКЕТ:</b> {u[2].split('|')[1]}\nОт: @{m.from_user.username}\n"
    
    for adm in OWNERS:
        try:
            if m.content_type == 'text':
                bot.send_message(adm, header + f"Текст: <i>{m.text}</i>", reply_markup=crm_control_kb(m.chat.id))
            else:
                bot.send_message(adm, header)
                bot.copy_message(adm, m.chat.id, m.message_id, reply_markup=crm_control_kb(m.chat.id))
        except: pass

# ==========================================
# 6. CRM ОБРАБОТЧИКИ (ИНЛАЙН)
# ==========================================
@bot.callback_query_handler(func=lambda c: True)
def h_callbacks(c):
    p = c.data.split('_')
    action = p[0]
    
    # Просмотр FAQ
    if action == 'showfaq':
        faq = db_query("SELECT answer FROM faq_base WHERE id = ?", (p[1],), fetch=True)
        bot.send_message(c.message.chat.id, f"💡 <b>Ответ:</b>\n{faq[0][0]}")

    # Админ действия
    if action == 'ans': # Мгновенный ответ
        msg = bot.send_message(c.message.chat.id, f"✉️ Введите ответ для пользователя {p[1]}:")
        bot.register_next_step_handler(msg, step_send_ans, p[1])
        
    elif action == 'prof': # Досье
        u = db_query("SELECT username, reg, note FROM subjects WHERE uid = ?", (p[1],), fetch=True)[0]
        cnt = db_query("SELECT COUNT(*) FROM history WHERE uid = ?", (p[1],), fetch=True)[0][0]
        info = (f"👤 <b>ПРОФИЛЬ:</b> <code>{p[1]}</code>\nНик: @{u[0]}\n"
                f"Рега: {u[1]}\nВсего сообщений: {cnt}\n"
                f"📝 Заметка: <i>{u[2] or 'нет'}</i>\n\nВведите новую заметку или пропустите:")
        msg = bot.send_message(c.message.chat.id, info)
        bot.register_next_step_handler(msg, step_save_note, p[1])

    elif action == 'ban':
        db_query("UPDATE subjects SET banned = 1 WHERE uid = ?", (p[1],), commit=True)
        bot.answer_callback_query(c.id, "Заблокирован.", show_alert=True)

    # Админ Меню
    elif action == 'adm':
        if c.data == 'adm_stats':
            all_u = db_query("SELECT COUNT(*) FROM subjects", fetch=True)[0][0]
            bot.send_message(c.message.chat.id, f"📊 <b>СТАТИСТИКА:</b>\nВсего субъектов в базе: {all_u}")
        elif c.data == 'adm_backup':
            with open(DB_FILE, 'rb') as f: bot.send_document(c.message.chat.id, f, caption="CORE_DB_BACKUP")
        elif c.data == 'adm_broadcast':
            msg = bot.send_message(c.message.chat.id, "📢 Введите текст ГЛОБАЛЬНОЙ рассылки:")
            bot.register_next_step_handler(msg, step_broadcast)
        elif c.data == 'adm_faq_add':
            msg = bot.send_message(c.message.chat.id, "Напишите Вопрос и Ответ через разделитель '|' (например: Как пить? | Кнопкой Е):")
            bot.register_next_step_handler(msg, step_faq_save)

# --- ШАГИ (ADMIN STEPS) ---
def step_send_ans(m, uid):
    u_lang = db_query("SELECT lang FROM subjects WHERE uid = ?", (uid,), fetch=True)[0][0]
    try:
        if m.content_type == 'text':
            bot.send_message(uid, STRINGS[u_lang]['reply'] + f"<i>{m.text}</i>")
        else:
            bot.send_message(uid, STRINGS[u_lang]['reply'])
            bot.copy_message(uid, m.chat.id, m.message_id)
        bot.send_message(m.chat.id, "✅ Ответ отправлен.")
    except: bot.send_message(m.chat.id, "❌ Не доставлено (блок бота).")

def step_save_note(m, uid):
    if m.text != "." and m.chat.id in OWNERS:
        db_query("UPDATE subjects SET note = ? WHERE uid = ?", (m.text, uid), commit=True)
        bot.send_message(m.chat.id, "✅ Заметка обновлена.")

def step_broadcast(m):
    users = db_query("SELECT uid FROM subjects", fetch=True)
    s, f = 0, 0
    for u in users:
        try:
            bot.copy_message(u[0], m.chat.id, m.message_id)
            s += 1
        except: f += 1
    bot.send_message(m.chat.id, f"✅ Рассылка: {s} ок, {f} ошибок.")

def step_faq_save(m):
    if '|' in m.text:
        q, a = m.text.split('|')
        db_query("INSERT INTO faq_base (question, answer, lang) VALUES (?, ?, ?)", (q.strip(), a.strip(), "ru"), commit=True)
        bot.send_message(m.chat.id, "✅ Добавлено в FAQ.")

# ==========================================
# 7. ГЛОБАЛЬНЫЙ ЗАПУСК
# ==========================================
if __name__ == '__main__':
    bot.set_my_commands([
        types.BotCommand("start", "Главная"),
        types.BotCommand("admin", "Управление (Админ)")
    ])
    print(f"[{datetime.now().strftime('%H:%M:%S')}] DRAGPOLIT V5 CORE ACTIVE.")
    bot.infinity_polling()
