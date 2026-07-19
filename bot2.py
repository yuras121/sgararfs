import os
import sqlite3
import telebot
import sys
from telebot import types
from datetime import datetime
from threading import Lock

# ==========================================
# 1. СИСТЕМНОЕ ЯДРО И ДОСТУПЫ
# ==========================================
TOKEN = os.environ.get('TOKEN')
# Обновленный список Высшего Руководства
OWNERS = [1614259542, 7716987740, 1751927856] 

if not TOKEN:
    print("❌ КРИТИЧЕСКАЯ ОШИБКА: Токен не найден в Environment!")
    sys.exit(1)

bot = telebot.TeleBot(TOKEN, parse_mode='HTML')
db_lock = Lock()
DB_FILE = 'dragpolit_enterprise_v5.db'

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
        'reply_head': "🏛 <b>ОТВЕТ АДМИНИСТРАЦИИ:</b>\n━━━━━━━━━━━━━━━━━━━━\n\n",
        'banned': "⛔️ Доступ ограничен службой безопасности."
    },
    'en': {
        'start': "🏛 <b>DragPolit Central Reception</b>\nChoose a department or check the FAQ:",
        'b_faq': "❓ FAQ / Help", 'b_lang': "🌍 Русский",
        'b_report': "🛡 Report", 'b_tech': "⚙️ Tech Support", 'b_other': "💬 Contact",
        'input': "📋 <b>RECORD MODE:</b> Type your message (text/media).",
        'done': "✅ Message registered. Wait for management's response.",
        'reply_head': "🏛 <b>OFFICIAL RESPONSE:</b>\n━━━━━━━━━━━━━━━━━━━━\n\n",
        'banned': "⛔️ Access restricted by security."
    }
}

# ==========================================
# 3. БАЗА ДАННЫХ (CORE)
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

def init_db():
    db_query('''CREATE TABLE IF NOT EXISTS subjects (
        uid INTEGER PRIMARY KEY, username TEXT, lang TEXT DEFAULT 'ru', 
        state TEXT DEFAULT 'IDLE', banned INTEGER DEFAULT 0, note TEXT, reg TEXT)''', commit=True)
    db_query('''CREATE TABLE IF NOT EXISTS history (
        id INTEGER PRIMARY KEY AUTOINCREMENT, uid INTEGER, txt TEXT, ts TEXT, direction TEXT)''', commit=True)
    db_query('''CREATE TABLE IF NOT EXISTS faq_base (
        id INTEGER PRIMARY KEY AUTOINCREMENT, question TEXT, answer TEXT, lang TEXT)''', commit=True)
    # Таблица аудита действий руководства
    db_query('''CREATE TABLE IF NOT EXISTS admin_logs (
        id INTEGER PRIMARY KEY AUTOINCREMENT, aid INTEGER, action TEXT, target_uid INTEGER, ts TEXT)''', commit=True)

init_db()

# ==========================================
# 4. СЛУЖЕБНЫЕ ФУНКЦИИ КООРДИНАЦИИ
# ==========================================
def sync_notify(sender_id, text, target_id=None):
    """ Оповещает весь штаб о действии одного из админов """
    admin_name = f"ID:{sender_id}"
    for owner in OWNERS:
        if owner != sender_id:
            try:
                bot.send_message(owner, f"🔔 <b>СИНХРОНИЗАЦИЯ:</b>\nАдмин {admin_name}\n{text}")
            except: pass

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
        types.InlineKeyboardButton("📊 Суточный отчет (Audit)", callback_data="adm_report_daily"),
        types.InlineKeyboardButton("➕ Добавить в FAQ", callback_data="adm_faq_add"),
        types.InlineKeyboardButton("📂 Бэкап БД", callback_data="adm_backup")
    )
    return kb

def crm_control_kb(uid):
    kb = types.InlineKeyboardMarkup(row_width=2)
    kb.add(
        types.InlineKeyboardButton("✉️ Ответить", callback_data=f"ans_{uid}"),
        types.InlineKeyboardButton("👤 Досье/Заметка", callback_data=f"prof_{uid}"),
        types.InlineKeyboardButton("📜 История", callback_data=f"hist_{uid}"),
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
    bot.send_message(m.chat.id, "🏛 <b>ШТАБ DRAGPOLIT</b>\nВсе администраторы синхронизированы.", reply_markup=get_admin_panel_kb())

# ОБРАБОТКА ТЕКСТОВЫХ МЕНЮ
@bot.message_handler(func=lambda m: any(m.text in d.values() for d in STRINGS.values()))
def h_menu(m):
    u = db_query("SELECT lang, banned FROM subjects WHERE uid = ?", (m.chat.id,), fetch=True)[0]
    if u[1]: return
    
    if m.text in [STRINGS['ru']['b_lang'], STRINGS['en']['b_lang']]:
        new_lang = 'en' if u[0] == 'ru' else 'ru'
        db_query("UPDATE subjects SET lang = ? WHERE uid = ?", (new_lang, m.chat.id), commit=True)
        return bot.send_message(m.chat.id, "🌐 Localization: OK", reply_markup=get_main_kb(m.chat.id))

    if m.text in [STRINGS['ru']['b_faq'], STRINGS['en']['b_faq']]:
        faqs = db_query("SELECT question, id FROM faq_base WHERE lang = ?", (u[0],), fetch=True)
        if not faqs: return bot.send_message(m.chat.id, "FAQ пуст.")
        kb = types.InlineKeyboardMarkup()
        for q in faqs: kb.add(types.InlineKeyboardButton(q[0], callback_data=f"showfaq_{q[1]}"))
        return bot.send_message(m.chat.id, "<b>Часто задаваемые вопросы:</b>", reply_markup=kb)

    db_query("UPDATE subjects SET state = ? WHERE uid = ?", (f"INPUT|{m.text}", m.chat.id), commit=True)
    bot.send_message(m.chat.id, STRINGS[u[0]]['input'], reply_markup=types.ReplyKeyboardRemove())

# ОБРАБОТКА ЛЮБЫХ ВХОДЯЩИХ ДАННЫХ
@bot.message_handler(content_types=['text', 'photo', 'video', 'document', 'voice'])
def h_catch_all(m):
    u = db_query("SELECT lang, banned, state FROM subjects WHERE uid = ?", (m.chat.id,), fetch=True)[0]
    if u[1]: return
    if m.chat.id in OWNERS and u[2] == 'IDLE': return # Игнорим свободные сообщения админов

    is_input = "INPUT" in u[2]
    ts = datetime.now().strftime("%H:%M")
    txt_log = m.text if m.content_type == 'text' else f"[{m.content_type}]"
    db_query("INSERT INTO history (uid, txt, ts, direction) VALUES (?, ?, ?, ?)", 
             (m.chat.id, txt_log, ts, 'IN'), commit=True)
    
    if is_input:
        bot.send_message(m.chat.id, STRINGS[u[0]]['done'], reply_markup=get_main_kb(m.chat.id))
        db_query("UPDATE subjects SET state = 'IDLE' WHERE uid = ?", (m.chat.id,), commit=True)
    
    # Рассылка по Штабу
    header = f"💬 <b>СООБЩЕНИЕ:</b> @{m.from_user.username} (<code>{m.chat.id}</code>)\n"
    if is_input: header = f"📑 <b>ТИКЕТ:</b> {u[2].split('|')[1]}\n"
    
    for adm in OWNERS:
        try:
            if m.content_type == 'text':
                bot.send_message(adm, header + f"Текст: <i>{m.text}</i>", reply_markup=crm_control_kb(m.chat.id))
            else:
                bot.send_message(adm, header)
                bot.copy_message(adm, m.chat.id, m.message_id, reply_markup=crm_control_kb(m.chat.id))
        except: pass

# ==========================================
# 6. CRM ДЕЙСТВИЯ (ИНЛАЙН)
# ==========================================
@bot.callback_query_handler(func=lambda c: True)
def h_callbacks(c):
    p = c.data.split('_')
    action = p[0]
    aid = c.from_user.id
    
    if action == 'showfaq':
        faq = db_query("SELECT answer FROM faq_base WHERE id = ?", (p[1],), fetch=True)
        bot.send_message(c.message.chat.id, f"💡 <b>FAQ:</b>\n{faq[0][0]}")

    # Блок Администратора
    if aid in OWNERS:
        if action == 'ans':
            msg = bot.send_message(c.message.chat.id, f"✉️ Введите ответ для <code>{p[1]}</code>:")
            bot.register_next_step_handler(msg, step_send_ans, p[1])
            
        elif action == 'prof':
            u = db_query("SELECT username, reg, note FROM subjects WHERE uid = ?", (p[1],), fetch=True)[0]
            bot.send_message(c.message.chat.id, f"👤 <b>ДОСЬЕ {p[1]}</b>\nНик: @{u[0]}\nРегистрация: {u[1]}\nЗаметка: {u[2] or 'нет'}\n\nНапишите новую заметку или '.' для пропуска:")
            bot.register_next_step_handler(c.message, step_save_note, p[1])

        elif action == 'hist':
            h = db_query("SELECT ts, txt, direction FROM history WHERE uid = ? ORDER BY id DESC LIMIT 5", (p[1],), fetch=True)
            res = "📜 <b>Последние 5 сообщений:</b>\n" + "\n".join([f"[{x[0]}] {x[2]}: {x[1][:50]}" for x in h])
            bot.send_message(c.message.chat.id, res)

        elif action == 'ban':
            db_query("UPDATE subjects SET banned = 1 WHERE uid = ?", (p[1],), commit=True)
            db_query("INSERT INTO admin_logs (aid, action, target_uid, ts) VALUES (?, ?, ?, ?)", 
                     (aid, "BANNED", p[1], datetime.now().strftime("%Y-%m-%d %H:%M")), commit=True)
            sync_notify(aid, f"⛔️ Заблокировал субъекта <code>{p[1]}</code>")
            bot.answer_callback_query(c.id, "Забанен")

        # Системное меню
        elif action == 'adm':
            if c.data == 'adm_report_daily':
                logs = db_query("SELECT ts, action, aid, target_uid FROM admin_logs ORDER BY id DESC LIMIT 10", fetch=True)
                res = "📊 <b>ОТЧЕТ АКТИВНОСТИ ШТАБА:</b>\n" + "\n".join([f"• {x[0]} | {x[1]} | Admin {x[2]} -> {x[3]}" for x in logs])
                bot.send_message(c.message.chat.id, res)
            elif c.data == 'adm_backup':
                with open(DB_FILE, 'rb') as f: bot.send_document(c.message.chat.id, f, caption="DATABASE_EXPORT")
            elif c.data == 'adm_broadcast':
                msg = bot.send_message(c.message.chat.id, "📢 Сообщение для ГЛОБАЛЬНОЙ рассылки:")
                bot.register_next_step_handler(msg, step_broadcast)

# --- АДМИН-ЛОГИКА (STEPS) ---
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
        
        # СИНХРОНИЗАЦИЯ: Пишем в базу и уведомляем штаб
        db_query("INSERT INTO history (uid, txt, ts, direction) VALUES (?, ?, ?, ?)", (uid, content, "NOW", "OUT"), commit=True)
        db_query("INSERT INTO admin_logs (aid, action, target_uid, ts) VALUES (?, ?, ?, ?)", 
                 (aid, f"REPLIED: {content[:30]}...", uid, datetime.now().strftime("%H:%M")), commit=True)
        
        sync_notify(aid, f"✉️ Ответил игроку <code>{uid}</code>:\n<i>«{content[:50]}...»</i>")
        bot.send_message(m.chat.id, "✅ Доставлено.")
    except:
        bot.send_message(m.chat.id, "❌ Ошибка доставки.")

def step_save_note(m, uid):
    if m.text != ".":
        db_query("UPDATE subjects SET note = ? WHERE uid = ?", (m.text, uid), commit=True)
        sync_notify(m.from_user.id, f"📝 Изменил заметку для <code>{uid}</code> на: <i>{m.text}</i>")
        bot.send_message(m.chat.id, "✅ Заметка сохранена.")

def step_broadcast(m):
    users = db_query("SELECT uid FROM subjects", fetch=True)
    s, f = 0, 0
    for u in users:
        try:
            bot.copy_message(u[0], m.chat.id, m.message_id)
            s += 1
        except: f += 1
    sync_notify(m.from_user.id, f"📢 Запустил глобальную рассылку. Покрытие: {s} человек.")
    bot.send_message(m.chat.id, f"✅ Готово: {s} | Ошибок: {f}")

# ==========================================
# 7. ГЛОБАЛЬНЫЙ ЗАПУСК
# ==========================================
if __name__ == '__main__':
    bot.set_my_commands([
        types.BotCommand("start", "Главная страница"),
        types.BotCommand("admin", "Терминал управления")
    ])
    print(f"[{datetime.now().strftime('%H:%M:%S')}] DRAGPOLIT V6 SYNC SYSTEM ACTIVE.")
    bot.infinity_polling()
