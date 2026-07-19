import os
import sqlite3
import telebot
import sys
from telebot import types
from datetime import datetime
from threading import Lock

# ==========================================
# 1. КОНФІГУРАЦІЯ (ВСЕ СИНХРОНІЗОВАНО)
# ==========================================
TOKEN = os.environ.get('TOKEN')
# Твої ID + новий адмін
OWNERS = [1614259542, 7716987740, 1751927856] 

# Маяк для логів
print("--- [SYSTEM] ИНИЦИАЛИЗАЦИЯ DRAGPOLIT CORE ---")

if not TOKEN:
    print("❌ КРИТИЧЕСКАЯ ОШИБКА: Токен не найден!")
    sys.exit(1)

bot = telebot.TeleBot(TOKEN, parse_mode='HTML')
db_lock = Lock()
# ВАЖНО: имя файла как в твоем Mount в Dokploy!
DB_FILE = 'dragpolit_enterprise_v5.db'

# ==========================================
# 2. БАЗА ДАНИХ (CORE ENGINE)
# ==========================================
def db_query(sql, params=(), fetch=False, commit=False):
    with db_lock:
        with sqlite3.connect(DB_FILE, timeout=20) as conn:
            conn.execute("PRAGMA journal_mode=WAL;")
            c = conn.cursor()
            c.execute(sql, params)
            res = c.fetchall() if fetch else None
            if commit: conn.commit()
            return res

def init_db():
    db_query('''CREATE TABLE IF NOT EXISTS subjects 
                (uid INTEGER PRIMARY KEY, username TEXT, lang TEXT DEFAULT 'ru', banned INTEGER DEFAULT 0, note TEXT)''', commit=True)
    db_query('''CREATE TABLE IF NOT EXISTS ticket_map 
                (t_id INTEGER PRIMARY KEY AUTOINCREMENT, user_uid INTEGER, admin_msgs_map TEXT)''', commit=True)
    db_query('''CREATE TABLE IF NOT EXISTS faq (id INTEGER PRIMARY KEY AUTOINCREMENT, q TEXT, a TEXT, lang TEXT)''', commit=True)

# ==========================================
# 3. СИНХРОНІЗАЦІЯ ШТАБУ (MIRRORING)
# ==========================================
def broadcast_to_admins(sender_id, target_uid, content_msg, is_system=False):
    """ Кожен адмін бачить дії іншого в реальному часі """
    for owner in OWNERS:
        if owner == sender_id: continue 
        try:
            header = f"📡 <b>СИНХРОНІЗАЦІЯ ДІЙ:</b>\n👤 Адмін: <code>{sender_id}</code>\n🎯 Гравець: <code>{target_uid}</code>\n━━━━━━━━━━━━━━━━━━━━\n"
            if is_system:
                bot.send_message(owner, header + f"⚙️ Статус: {content_msg}")
            elif content_msg.content_type == 'text':
                bot.send_message(owner, header + f"💬 Текст: <i>{content_msg.text}</i>")
            else:
                bot.send_message(owner, header + f"📂 Тип: {content_msg.content_type}")
                bot.copy_message(owner, sender_id, content_msg.message_id)
        except: pass

def update_ui_for_all(t_id, new_text):
    """ Прибирає кнопки у всіх адмінів, коли хтось відповів """
    res = db_query("SELECT admin_msgs_map FROM ticket_map WHERE t_id = ?", (t_id,), fetch=True)
    if res:
        mapping = eval(res[0][0])
        for aid, mid in mapping.items():
            try: bot.edit_message_caption(chat_id=aid, message_id=mid, caption=new_text, reply_markup=None)
            except:
                try: bot.edit_message_text(chat_id=aid, message_id=mid, text=new_text, reply_markup=None)
                except: pass

# ==========================================
# 4. UX/UI ЕЛЕМЕНТИ
# ==========================================
def admin_kb(u_id, t_id):
    kb = types.InlineKeyboardMarkup(row_width=2)
    kb.add(
        types.InlineKeyboardButton("✉️ Відповісти", callback_data=f"ans_{u_id}_{t_id}"),
        types.InlineKeyboardButton("🔒 Архів", callback_data=f"arc_{u_id}_{t_id}"),
        types.InlineKeyboardButton("👤 Досьє", callback_data=f"inf_{u_id}"),
        types.InlineKeyboardButton("⛔️ BAN", callback_data=f"ban_{u_id}")
    )
    return kb

def main_kb():
    kb = types.ReplyKeyboardMarkup(resize_keyboard=True, row_width=2)
    kb.add("🛡 Жалоба", "⚙️ Тех-отдел", "💬 Связь")
    kb.add("❓ FAQ", "🌍 English")
    return kb

# ==========================================
# 5. ХЕНДЛЕРИ
# ==========================================
@bot.message_handler(commands=['start'])
def h_start(m):
    db_query("INSERT OR IGNORE INTO subjects (uid, username) VALUES (?, ?)", (m.chat.id, m.from_user.username), commit=True)
    bot.send_message(m.chat.id, "🏛 <b>Центральна Приемная DragPolit</b>", reply_markup=main_kb())

@bot.message_handler(commands=['admin'])
def h_admin(m):
    if m.chat.id not in OWNERS: return
    bot.send_message(m.chat.id, "👑 <b>Адмін-термінал</b>\nСинхронізація увімкнена.")

@bot.message_handler(content_types=['text', 'photo', 'video', 'document', 'voice', 'video_note'])
def h_incoming(m):
    if m.chat.id in OWNERS: return 
    
    db_query("INSERT INTO ticket_map (user_uid, admin_msgs_map) VALUES (?, ?)", (m.chat.id, "{}"), commit=True)
    t_id = db_query("SELECT last_insert_rowid()", fetch=True)[0][0]
    header = f"📑 <b>ПРОТОКОЛ #{t_id}</b>\nГравець: @{m.from_user.username}\nID: <code>{m.chat.id}</code>\n━━━━━━━━━━━━\n"
    
    msg_map = {}
    for aid in OWNERS:
        try:
            if m.content_type == 'text': r = bot.send_message(aid, header + f"💬 <i>{m.text}</i>", reply_markup=admin_kb(m.chat.id, t_id))
            else:
                bot.send_message(aid, header)
                r = bot.copy_message(aid, m.chat.id, m.message_id, reply_markup=admin_kb(m.chat.id, t_id))
            msg_map[aid] = r.message_id
        except: pass
    
    db_query("UPDATE ticket_map SET admin_msgs_map = ? WHERE t_id = ?", (str(msg_map), t_id), commit=True)
    bot.send_message(m.chat.id, "✅ Повідомлення передано в Штаб.")

# Адмінські кнопки
@bot.callback_query_handler(func=lambda c: True)
def h_callbacks(c):
    p = c.data.split('_')
    act, uid = p[0], int(p[1])
    aid = c.from_user.id
    
    if act == 'ans':
        t_id = p[2]
        msg = bot.send_message(aid, f"✉️ <b>ВІДПОВІДЬ ДЛЯ #{t_id}:</b>")
        bot.register_next_step_handler(msg, process_reply, uid, t_id)
        
    elif act == 'arc':
        t_id = p[2]
        update_ui_for_all(t_id, f"✅ <b>ЗАКРИТО</b> адміном <code>{aid}</code>")
        broadcast_to_admins(aid, uid, f"заархівував тікет #{t_id}", is_system=True)

    elif act == 'inf':
        u = db_query("SELECT note FROM subjects WHERE uid = ?", (uid,), fetch=True)[0]
        bot.send_message(aid, f"👤 ID: <code>{uid}</code>\nЗамітка: {u[0] or 'пусто'}\n\nОновіть або напишіть нову:")
        bot.register_next_step_handler(c.message, lambda m: db_query("UPDATE subjects SET note=? WHERE uid=?",(m.text, uid), commit=True))

    elif action == 'ban':
        db_query("UPDATE subjects SET banned = 1 WHERE uid = ?", (uid,), commit=True)
        broadcast_to_admins(aid, uid, "ВИДАВ БАН", is_system=True)
        bot.answer_callback_query(c.id, "Забанено", show_alert=True)

def process_reply(message, user_uid, t_id):
    aid = message.from_user.id
    try:
        h = "🏛 <b>ВІДПОВІДЬ КЕРІВНИЦТВА:</b>\n━━━━━━━━━━━━\n\n"
        if message.content_type == 'text':
            bot.send_message(user_uid, h + message.text)
            short = message.text
        else:
            bot.send_message(user_uid, h)
            bot.copy_message(user_uid, aid, message.message_id)
            short = f"[{message.content_type}]"
            
        broadcast_to_admins(aid, user_uid, message)
        update_ui_for_all(t_id, f"✅ <b>ВІДПОВІВ</b> адмін <code>{aid}</code>:\n<i>{short[:40]}...</i>")
        bot.send_message(aid, "✅ Надіслано.")
    except Exception as e:
        bot.send_message(aid, f"❌ Помилка: {e}")

# ==========================================
# 6. СТАРТ
# ==========================================
if __name__ == '__main__':
    init_db()
    print("🏛 СЕРВЕР DRAGPOLIT MASTER ЗАПУЩЕН!")
    bot.infinity_polling()
