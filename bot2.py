import os
import sqlite3
import telebot
import sys
import time
from telebot import types
from threading import Lock

# ==========================================
# 1. КОНФИГУРАЦИЯ И СЕРВЕРНЫЙ МАЯК
# ==========================================
TOKEN = os.environ.get('TOKEN')
# Твой список админов
OWNERS = [1614259542, 7716987740, 1751927856] 

print("--- [STARTUP] DRAGPOLIT CORE: BILINGUAL SYSTEM ---", flush=True)

if not TOKEN:
    print("❌ ERROR: ТОКЕН НЕ ЗНАЙДЕНО В НАЛАШТУВАННЯХ DOKPLOY (Вкладка Environment)", flush=True)
    time.sleep(60) # Тримаємо контейнер живим, щоб ти побачив помилку
    sys.exit(1)

bot = telebot.TeleBot(TOKEN, parse_mode='HTML')
db_lock = Lock()
# Путь СТРОГО под твой Volume в Dokploy
DB_FILE = '/app/dragpolit_enterprise_v5.db'

# ==========================================
# 2. МУЛЬТИЯЗЫЧНЫЙ ГЛОССАРИЙ
# ==========================================
STRINGS = {
    'ru': {
        'welcome': "🏛 <b>Центральная Приемная DragPolit</b>\nВыберите департамент для связи с руководством:",
        'b_report': "🛡 Жалоба", 'b_tech': "⚙️ Тех-отдел", 'b_other': "💬 Связь",
        'b_lang': "🇺🇸 Change Language", 'b_faq': "❓ FAQ",
        'input': "📋 <b>РЕЖИМ ЗАПИСИ:</b> Опишите вашу проблему (текст/медиа).",
        'success': "✅ Ваше обращение зарегистрировано в базе штаба.",
        'reply': "🏛 <b>ОФИЦИАЛЬНАЯ РЕЗОЛЮЦИЯ:</b>\n━━━━━━━━━━━━\n\n",
        'banned': "⛔️ Доступ ограничен службой безопасности.",
        'ticket_header': "📑 <b>НОВЫЙ ТИКЕТ</b>"
    },
    'en': {
        'welcome': "🏛 <b>DragPolit Central Command Node</b>\nSelect a department to contact management:",
        'b_report': "🛡 Report", 'b_tech': "⚙️ Tech Dept", 'b_other': "💬 Contact",
        'b_lang': "🇷🇺 Сменить язык", 'b_faq': "❓ Help",
        'input': "📋 <b>RECORD MODE:</b> Describe your issue (text/media).",
        'success': "✅ Your request has been registered in the database.",
        'reply': "🏛 <b>OFFICIAL RESOLUTION:</b>\n━━━━━━━━━━━━\n\n",
        'banned': "⛔️ Access restricted by security service.",
        'ticket_header': "📑 <b>NEW TICKET</b>"
    }
}

# ==========================================
# 3. ENGINE: БАЗА ДАННЫХ
# ==========================================
def db_op(query, params=(), fetch=False, commit=False):
    with db_lock:
        try:
            with sqlite3.connect(DB_FILE, timeout=20) as conn:
                conn.execute("PRAGMA journal_mode=WAL;")
                c = conn.cursor()
                c.execute(query, params)
                res = c.fetchall() if fetch else None
                if commit: conn.commit()
                return res
        except Exception as e:
            print(f"❌ DATABASE ERROR: {e}", flush=True)
            return None

def init_db():
    db_op('''CREATE TABLE IF NOT EXISTS subjects (
        uid INTEGER PRIMARY KEY, uname TEXT, lang TEXT DEFAULT 'ru', 
        state TEXT DEFAULT 'IDLE', banned INTEGER DEFAULT 0, note TEXT)''', commit=True)
    db_op('''CREATE TABLE IF NOT EXISTS tickets (
        tid INTEGER PRIMARY KEY AUTOINCREMENT, uid INTEGER, category TEXT, status TEXT DEFAULT 'OPEN')''', commit=True)

# ==========================================
# 4. СИНХРОНИЗАЦИЯ ШТАБА (ADMIN SYNC)
# ==========================================
def sync_with_admins(sender_id, target_uid, data, action="ANSWER"):
    """ Рассылает уведомление всем админам. В data может быть Message или просто строка. """
    for adm in OWNERS:
        if adm == sender_id: continue
        try:
            head = f"📡 <b>SYNC: Админ <code>{sender_id}</code></b>\n🎯 Игрок: <code>{target_uid}</code>\nДействие: {action}\n━━━━━━━\n"
            
            # Если передали просто текст (например, при бане)
            if isinstance(data, str):
                bot.send_message(adm, head + f"Инфо: <i>{data}</i>")
            # Если передали объект сообщения
            elif hasattr(data, 'content_type'):
                if data.content_type == 'text':
                    bot.send_message(adm, head + f"Текст: <i>{data.text}</i>")
                else:
                    bot.send_message(adm, head + f"Медиа: {data.content_type}")
                    bot.copy_message(adm, sender_id, data.message_id)
        except Exception as e:
            print(f"❌ SYNC ERROR for admin {adm}: {e}", flush=True)

# ==========================================
# 5. UX: КЛАВИАТУРЫ
# ==========================================
def get_main_kb(uid):
    res = db_op("SELECT lang FROM subjects WHERE uid = ?", (uid,), fetch=True)
    l = res[0][0] if res else 'ru'
    kb = types.ReplyKeyboardMarkup(resize_keyboard=True, row_width=2)
    kb.add(STRINGS[l]['b_report'], STRINGS[l]['b_tech'], STRINGS[l]['b_other'])
    kb.add(STRINGS[l]['b_faq'], STRINGS[l]['b_lang'])
    return kb

def get_crm_kb(uid, tid):
    kb = types.InlineKeyboardMarkup(row_width=2)
    kb.add(
        types.InlineKeyboardButton("📩 Ответить", callback_data=f"rep_{uid}_{tid}"),
        types.InlineKeyboardButton("👤 Досье", callback_data=f"dos_{uid}"),
        types.InlineKeyboardButton("⛔️ BAN", callback_data=f"ban_{uid}"),
        types.InlineKeyboardButton("🔒 Архив", callback_data=f"cls_{tid}")
    )
    return kb

# ==========================================
# 6. ЛОГИКА ОБРАБОТКИ
# ==========================================
@bot.message_handler(commands=['start'])
def h_start(m):
    res = db_op("SELECT lang, banned FROM subjects WHERE uid = ?", (m.chat.id,), fetch=True)
    if not res:
        lang = 'en' if m.from_user.language_code != 'ru' else 'ru'
        db_op("INSERT INTO subjects (uid, uname, lang) VALUES (?, ?, ?)", 
              (m.chat.id, m.from_user.username, lang), commit=True)
        u_lang = lang
    else:
        if res[0][1]: return bot.send_message(m.chat.id, STRINGS[res[0][0]]['banned'])
        u_lang = res[0][0]
    
    db_op("UPDATE subjects SET state = 'IDLE' WHERE uid = ?", (m.chat.id,), commit=True)
    bot.send_message(m.chat.id, STRINGS[u_lang]['welcome'], reply_markup=get_main_kb(m.chat.id))

@bot.message_handler(commands=['admin'])
def h_admin(m):
    if m.chat.id not in OWNERS: return
    stats_res = db_op("SELECT COUNT(*) FROM subjects", fetch=True)
    stats = stats_res[0][0] if stats_res else 0
    kb = types.InlineKeyboardMarkup()
    kb.add(types.InlineKeyboardButton("📢 Массовая рассылка", callback_data="adm_mass"))
    bot.send_message(m.chat.id, f"👑 <b>DRAGPOLIT COMMAND CENTER</b>\nСубъектов в базе: {stats}", reply_markup=kb)

@bot.message_handler(func=lambda m: any(m.text in d.values() for d in STRINGS.values()))
def h_menu(m):
    res = db_op("SELECT lang, banned FROM subjects WHERE uid = ?", (m.chat.id,), fetch=True)
    if not res or res[0][1]: return
    u_lang = res[0][0]

    if m.text in [STRINGS['ru']['b_lang'], STRINGS['en']['b_lang']]:
        new_l = 'en' if u_lang == 'ru' else 'ru'
        db_op("UPDATE subjects SET lang = ? WHERE uid = ?", (new_l, m.chat.id), commit=True)
        return bot.send_message(m.chat.id, "🌍 Done!", reply_markup=get_main_kb(m.chat.id))

    if m.text in [STRINGS['ru']['b_faq'], STRINGS['en']['b_faq']]:
        return bot.send_message(m.chat.id, "<b>DragPolit Support</b>: panel.dragpolit.com")

    db_op("UPDATE subjects SET state = ? WHERE uid = ?", (f"SENDING|{m.text}", m.chat.id), commit=True)
    bot.send_message(m.chat.id, STRINGS[u_lang]['input'], reply_markup=types.ReplyKeyboardRemove())

@bot.message_handler(content_types=['text', 'photo', 'video', 'document', 'voice', 'video_note'])
def h_content(m):
    res = db_op("SELECT lang, banned, state FROM subjects WHERE uid = ?", (m.chat.id,), fetch=True)
    if not res or res[0][1]: return
    u_lang, _, u_state = res[0]
    
    if m.chat.id in OWNERS and u_state == 'IDLE': return 

    is_ticket = "SENDING" in u_state
    if not is_ticket:
        return bot.send_message(m.chat.id, "❌ Будь ласка, виберіть департамент у меню через /start")

    cat = u_state.split('|')[1]
    db_op("INSERT INTO tickets (uid, category) VALUES (?, ?)", (m.chat.id, cat), commit=True)
    
    tid_res = db_op("SELECT last_insert_rowid()", fetch=True)
    t_id = tid_res[0][0] if tid_res else 0
    
    db_op("UPDATE subjects SET state = 'IDLE' WHERE uid = ?", (m.chat.id,), commit=True)
    bot.send_message(m.chat.id, STRINGS[u_lang]['success'], reply_markup=get_main_kb(m.chat.id))

    admin_header = f"📩 <b>{STRINGS[u_lang]['ticket_header']} #{t_id}</b> [{cat}]\n👤 @{m.from_user.username} (<code>{m.chat.id}</code>)\n━━━━━━━\n"
    for adm in OWNERS:
        try:
            if m.content_type == 'text':
                bot.send_message(adm, admin_header + f"💬 <i>{m.text}</i>", reply_markup=get_crm_kb(m.chat.id, t_id))
            else:
                bot.send_message(adm, admin_header)
                bot.copy_message(adm, m.chat.id, m.message_id, reply_markup=get_crm_kb(m.chat.id, t_id))
        except Exception as e:
            print(f"❌ ПРОВАЛ ВІДПРАВКИ ТІКЕТА АДМІНУ {adm}: {e}", flush=True)

# --- Коллбеки CRM ---
@bot.callback_query_handler(func=lambda c: True)
def h_callbacks(c):
    if c.from_user.id not in OWNERS: return
    p = c.data.split('_')
    action = p[0]
    
    if action == 'rep': 
        uid, tid = p[1], p[2]
        msg = bot.send_message(c.message.chat.id, f"📝 Пишите ответ для <code>{uid}</code> (Тикет #{tid}):")
        bot.register_next_step_handler(msg, step_reply, uid, tid)
    
    elif action == 'dos': 
        res = db_op("SELECT uname, note FROM subjects WHERE uid = ?", (p[1],), fetch=True)
        uname = res[0][0] if res else "unknown"
        note = res[0][1] if res else "пусто"
        bot.send_message(c.message.chat.id, f"👤 <b>ДОСЬЕ {p[1]}</b>\nЮзер: @{uname}\nЗаметка: {note or 'пусто'}\n\nНапишите новую заметку:")
        bot.register_next_step_handler(c.message, step_note, p[1])

    elif action == 'ban': 
        db_op("UPDATE subjects SET banned = 1 WHERE uid = ?", (p[1],), commit=True)
        sync_with_admins(c.from_user.id, p[1], "Користувач доданий у чорний список.", "BANNED")
        bot.answer_callback_query(c.id, "Заблокирован", show_alert=True)

    elif action == 'cls':
        db_op("UPDATE tickets SET status = 'CLOSED' WHERE tid = ?", (p[1],), commit=True)
        bot.answer_callback_query(c.id, "Тикет закритий", show_alert=True)
        bot.edit_message_reply_markup(c.message.chat.id, c.message.message_id, reply_markup=None)

def step_reply(m, uid, tid):
    res = db_op("SELECT lang FROM subjects WHERE uid = ?", (uid,), fetch=True)
    l = res[0][0] if res else 'ru'
    try:
        h = STRINGS[l]['reply']
        if m.content_type == 'text': 
            bot.send_message(uid, h + f"<i>{m.text}</i>")
        else:
            bot.send_message(uid, h)
            bot.copy_message(uid, m.chat.id, m.message_id)
        
        sync_with_admins(m.from_user.id, uid, m, f"ANSWER (Ticket #{tid})")
        bot.send_message(m.chat.id, "✅ Ответ доставлен и синхронизирован.")
    except Exception as e:
        bot.send_message(m.chat.id, f"❌ Не доставлено (можливо, юзер заблокував бота). Помилка: {e}")

def step_note(m, uid):
    db_op("UPDATE subjects SET note = ? WHERE uid = ?", (m.text, uid), commit=True)
    bot.send_message(m.chat.id, "✅ Заметка сохранена в CRM.")

if __name__ == '__main__':
    try:
        print("--- ИНИЦИАЛИЗАЦИЯ БАЗЫ ДАННЫХ ---", flush=True)
        init_db()
        print("--- [ONLINE] MASTER CORE LOADED ---", flush=True)
        bot.infinity_polling(timeout=10, long_polling_timeout=5)
    except Exception as e:
        print(f"❌ КРИТИЧНА ПОМИЛКА ПРИ ЗАПУСКУ БОТА: {e}", flush=True)
        # Цей сліп тримає контейнер живим хвилину, щоб лог встиг відправитись в дашборд Dokploy
        time.sleep(60) 
        sys.exit(1)
