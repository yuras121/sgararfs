import os
import sqlite3
import telebot
import sys
import time
from telebot import types
from datetime import datetime
from threading import Lock

# ==========================================
# 1. СИСТЕМНОЕ ЯДРО
# ==========================================
TOKEN = os.environ.get('TOKEN')
OWNERS = [1614259542, 7716987740, 1751927856] 

if not TOKEN:
    print("❌ ТОКЕН НЕ НАЙДЕН")
    sys.exit(1)

bot = telebot.TeleBot(TOKEN, parse_mode='HTML')
db_lock = Lock()
DB_FILE = 'dragpolit_enterprise_v7.db'

# ==========================================
# 2. БАЗА ДАННЫХ (SYNC ARCHITECTURE)
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
    # Субъекты
    db_query('''CREATE TABLE IF NOT EXISTS subjects (
        uid INTEGER PRIMARY KEY, username TEXT, lang TEXT DEFAULT 'ru', 
        state TEXT DEFAULT 'IDLE', banned INTEGER DEFAULT 0, note TEXT)''', commit=True)
    # Глобальный реестр админ-сообщений (чтобы бот мог их удалять/редактировать у всех)
    db_query('''CREATE TABLE IF NOT EXISTS admin_msgs (
        ticket_id INTEGER PRIMARY KEY AUTOINCREMENT, 
        user_uid INTEGER, 
        msg_json TEXT)''', commit=True) # msg_json хранит "admin_id:msg_id" для всех админов
    # Логи действий
    db_query('''CREATE TABLE IF NOT EXISTS admin_logs (
        id INTEGER PRIMARY KEY AUTOINCREMENT, aid INTEGER, action TEXT, target INTEGER, ts TEXT)''', commit=True)
    # FAQ
    db_query('''CREATE TABLE IF NOT EXISTS faq (id INTEGER PRIMARY KEY AUTOINCREMENT, q TEXT, a TEXT)''', commit=True)

init_db()

# ==========================================
# 3. ЛОГИКА СИНХРОНИЗАЦИИ (UI UPDATE)
# ==========================================
def broadcast_admin_update(user_uid, status_text, ticket_id=None):
    """ Находит все копии сообщения у админов и редактирует их """
    if not ticket_id:
        res = db_query("SELECT msg_json, ticket_id FROM admin_msgs WHERE user_uid = ? ORDER BY ticket_id DESC LIMIT 1", (user_uid,), fetch=True)
    else:
        res = db_query("SELECT msg_json, ticket_id FROM admin_msgs WHERE ticket_id = ?", (ticket_id,), fetch=True)
    
    if res:
        mapping = eval(res[0][0]) # Превращаем строку назад в словарь {admin_id: msg_id}
        t_id = res[0][1]
        for aid, mid in mapping.items():
            try:
                bot.edit_message_caption(
                    chat_id=aid, 
                    message_id=mid, 
                    caption=f"📝 <b>СТАТУС ОБНОВЛЕН:</b>\n{status_text}\n━━━━━━━━━━━━\nTicket #{t_id}",
                    reply_markup=None # Убираем кнопки
                )
            except:
                try:
                    bot.edit_message_text(
                        chat_id=aid, 
                        message_id=mid, 
                        text=f"📝 <b>СТАТУС ОБНОВЛЕН:</b>\n{status_text}\n━━━━━━━━━━━━\nTicket #{t_id}",
                        reply_markup=None
                    )
                except: pass

# ==========================================
# 4. ИНТЕРФЕЙСЫ
# ==========================================
def main_kb(uid):
    kb = types.ReplyKeyboardMarkup(resize_keyboard=True, row_width=2)
    kb.add("🛡 Жалоба", "⚙️ Тех-отдел", "💬 Связь")
    kb.add("❓ FAQ", "🌍 English")
    return kb

def admin_kb(u_id, t_id):
    kb = types.InlineKeyboardMarkup(row_width=2)
    kb.add(
        types.InlineKeyboardButton("📩 Ответить", callback_data=f"ans_{u_id}_{t_id}"),
        types.InlineKeyboardButton("🔒 Архив", callback_data=f"arc_{u_id}_{t_id}"),
        types.InlineKeyboardButton("👤 Профиль", callback_data=f"prof_{u_id}"),
        types.InlineKeyboardButton("⛔️ BAN", callback_data=f"ban_{u_id}")
    )
    return kb

# ==========================================
# 5. ХЕНДЛЕРЫ
# ==========================================
@bot.message_handler(commands=['start'])
def start(m):
    res = db_query("SELECT banned FROM subjects WHERE uid = ?", (m.chat.id,), fetch=True)
    if not res:
        db_query("INSERT INTO subjects (uid, username) VALUES (?, ?)", (m.chat.id, m.from_user.username), commit=True)
    elif res[0][0]: return bot.send_message(m.chat.id, "⛔️ Доступ ограничен.")
    
    bot.send_message(m.chat.id, "🏛 <b>Центральная Приемная DragPolit</b>", reply_markup=main_kb(m.chat.id))

@bot.message_handler(commands=['admin'])
def admin(m):
    if m.chat.id not in OWNERS: return
    kb = types.InlineKeyboardMarkup()
    kb.add(types.InlineKeyboardButton("📢 Рассылка", callback_data="adm_mass"),
           types.InlineKeyboardButton("📊 Отчет", callback_data="adm_rep"))
    bot.send_message(m.chat.id, "🏛 <b>Терминал Координации</b>", reply_markup=kb)

# --- Прием сообщений от игроков ---
@bot.message_handler(content_types=['text', 'photo', 'video', 'document', 'voice'])
def handle_incoming(m):
    if m.chat.id in OWNERS: return
    
    # Регистрация нового тикета
    db_query("INSERT INTO admin_msgs (user_uid, msg_json) VALUES (?, ?)", (m.chat.id, "{}"), commit=True)
    t_id = db_query("SELECT last_insert_rowid()", fetch=True)[0][0]
    
    header = f"📑 <b>НОВЫЙ ТИКЕТ #{t_id}</b>\nСубъект: @{m.from_user.username} (<code>{m.chat.id}</code>)\n\n"
    
    msg_map = {} # Здесь будем хранить {id_админа: id_сообщения}
    for aid in OWNERS:
        try:
            if m.content_type == 'text':
                res = bot.send_message(aid, header + f"💬 <i>{m.text}</i>", reply_markup=admin_kb(m.chat.id, t_id))
            else:
                bot.send_message(aid, header)
                res = bot.copy_message(aid, m.chat.id, m.message_id, reply_markup=admin_kb(m.chat.id, t_id))
            msg_map[aid] = res.message_id
        except: pass
    
    # Сохраняем мапинг в базу, чтобы потом редактировать у всех
    db_query("UPDATE admin_msgs SET msg_json = ? WHERE ticket_id = ?", (str(msg_map), t_id), commit=True)
    bot.send_message(m.chat.id, "✅ Ваше сообщение передано в Штаб.")

# --- Коллбеки ---
@bot.callback_query_handler(func=lambda c: True)
def callbacks(c):
    p = c.data.split('_')
    act, uid = p[0], int(p[1])
    aid = c.from_user.id
    
    if act == 'ans':
        t_id = p[2]
        msg = bot.send_message(c.message.chat.id, f"📝 Ответ для тикета #{t_id}:")
        bot.register_next_step_handler(msg, step_reply, uid, t_id)
        
    elif act == 'arc':
        t_id = p[2]
        broadcast_admin_update(uid, f"🔒 Закрыто админом <code>{aid}</code>", ticket_id=t_id)
        db_query("INSERT INTO admin_logs (aid, action, target, ts) VALUES (?, ?, ?, ?)", 
                 (aid, "CLOSED_TICKET", t_id, datetime.now().strftime("%H:%M")), commit=True)

    elif act == 'ban':
        db_query("UPDATE subjects SET banned = 1 WHERE uid = ?", (uid,), commit=True)
        broadcast_admin_update(uid, f"⛔️ БАН выдан админом <code>{aid}</code>")
        bot.answer_callback_query(c.id, "Субъект забанен", show_alert=True)

    elif act == 'prof':
        res = db_query("SELECT note, username FROM subjects WHERE uid = ?", (uid,), fetch=True)[0]
        bot.send_message(c.message.chat.id, f"👤 @{res[1]}\nID: <code>{uid}</code>\nЗаметка: {res[0] or 'нет'}\n\nНапишите новую заметку:")
        bot.register_next_step_handler(c.message, step_note, uid)

# --- Шаги админа ---
def step_reply(m, uid, t_id):
    aid = m.from_user.id
    try:
        header = "🏛 <b>ОТВЕТ АДМИНИСТРАЦИИ:</b>\n━━━━━━━━━━━━\n\n"
        if m.content_type == 'text':
            bot.send_message(uid, header + m.text)
            content = m.text
        else:
            bot.send_message(uid, header)
            bot.copy_message(uid, m.chat.id, m.message_id)
            content = f"[{m.content_type}]"
        
        # Обновляем сообщение у всех админов!
        broadcast_admin_update(uid, f"✅ Ответил админ <code>{aid}</code>:\n<i>«{content[:40]}...»</i>", ticket_id=t_id)
        
        # Лог
        db_query("INSERT INTO admin_logs (aid, action, target, ts) VALUES (?, ?, ?, ?)", 
                 (aid, f"REPLY_#{t_id}", uid, datetime.now().strftime("%H:%M")), commit=True)
        bot.send_message(m.chat.id, "✅ Отправлено и синхронизировано.")
    except:
        bot.send_message(m.chat.id, "❌ Ошибка доставки.")

def step_note(m, uid):
    db_query("UPDATE subjects SET note = ? WHERE uid = ?", (m.text, uid), commit=True)
    bot.send_message(m.chat.id, "✅ Заметка обновлена.")

# ==========================================
# 6. ЗАПУСК
# ==========================================
if __name__ == '__main__':
    print("🏛 DRAGPOLIT SYNC MASTER ACTIVE")
    bot.infinity_polling()
