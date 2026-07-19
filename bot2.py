import os
import sqlite3
import telebot
import sys
from telebot import types
from datetime import datetime
from threading import Lock

# ==========================================
# 1. КОНФІГУРАЦІЯ
# ==========================================
TOKEN = os.environ.get('TOKEN')
# ID вищого керівництва
OWNERS = [1614259542, 7716987740, 1751927856] 

if not TOKEN:
    print("❌ ПОМИЛКА: ТОКЕН не знайдено!")
    sys.exit(1)

bot = telebot.TeleBot(TOKEN, parse_mode='HTML')
db_lock = Lock()
DB_FILE = 'dragpolit_enterprise_v9.db'

# ==========================================
# 2. БАЗА ДАНИХ
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
    # Зберігаємо зв'язки між адмінами та повідомленнями
    db_query('''CREATE TABLE IF NOT EXISTS ticket_map 
                (t_id INTEGER PRIMARY KEY AUTOINCREMENT, user_uid INTEGER, admin_msgs_map TEXT)''', commit=True)

init_db()

# ==========================================
# 3. СЕРВІС ДЗЕРКАЛЮВАННЯ (ADMIN MIRROR)
# ==========================================
def broadcast_admin_action(sender_id, target_uid, content_msg):
    """ Кожен адмін бачить відповідь колеги в реальному часі """
    sender_info = f"Адмін (<code>{sender_id}</code>)"
    target_info = f"Гравцеві (<code>{target_uid}</code>)"
    
    header = f"📡 <b>ДЗЕРКАЛО ДІЙ ШТАБУ</b>\n👤 Відправник: {sender_info}\n🎯 Адресат: {target_info}\n━━━━━━━━━━━━━━━━━━━━\n"
    
    for owner in OWNERS:
        if owner == sender_id:
            continue # Самому собі не дублюємо
        
        try:
            # Якщо адмін написав текст
            if content_msg.content_type == 'text':
                bot.send_message(owner, header + f"💬 Текст: <i>{content_msg.text}</i>")
            # Якщо адмін відправив медіа (фото/відео/файл)
            else:
                bot.send_message(owner, header + f"📂 Тип медіа: {content_msg.content_type}")
                bot.copy_message(owner, sender_id, content_msg.message_id)
        except Exception as e:
            print(f"Помилка синхронізації з {owner}: {e}")

def update_all_admins_ui(t_id, status_text):
    """ Видаляє кнопки у всіх адмінів під конкретним тікетом """
    res = db_query("SELECT admin_msgs_map FROM ticket_map WHERE t_id = ?", (t_id,), fetch=True)
    if res:
        # admin_msgs_map збережений як рядок словника "{admin_id: message_id}"
        mapping = eval(res[0][0])
        for aid, mid in mapping.items():
            try:
                bot.edit_message_caption(chat_id=aid, message_id=mid, caption=status_text, reply_markup=None)
            except:
                try: bot.edit_message_text(chat_id=aid, message_id=mid, text=status_text, reply_markup=None)
                except: pass

# ==========================================
# 4. UX/UI ЕЛЕМЕНТИ
# ==========================================
def admin_inline_kb(u_id, t_id):
    kb = types.InlineKeyboardMarkup(row_width=2)
    kb.add(
        types.InlineKeyboardButton("✉️ Відповісти", callback_data=f"ans_{u_id}_{t_id}"),
        types.InlineKeyboardButton("🔒 В архів", callback_data=f"arc_{u_id}_{t_id}"),
        types.InlineKeyboardButton("👤 Профіль", callback_data=f"inf_{u_id}"),
        types.InlineKeyboardButton("⛔️ BAN", callback_data=f"ban_{u_id}")
    )
    return kb

def main_kb():
    kb = types.ReplyKeyboardMarkup(resize_keyboard=True, row_width=2)
    kb.add("🛡 Жалоба", "⚙️ Тех-отдел", "💬 Связь")
    kb.add("🌍 Language")
    return kb

# ==========================================
# 5. ХЕНДЛЕРИ ТА ЛОГІКА
# ==========================================
@bot.message_handler(commands=['start'])
def h_start(m):
    db_query("INSERT OR IGNORE INTO subjects (uid, username) VALUES (?, ?)", (m.chat.id, m.from_user.username), commit=True)
    bot.send_message(m.chat.id, "🏛 <b>Центральна Приемная DragPolit</b>", reply_markup=main_kb())

@bot.message_handler(commands=['admin'])
def h_admin(m):
    i
