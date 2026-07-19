import os
import sqlite3
import telebot
import sys
from telebot import types
from datetime import datetime
from threading import Lock

# ==========================================
# 1. КОНФИГУРАЦИЯ И КОМАНДА
# ==========================================
TOKEN = os.environ.get('TOKEN')
# Список Высшего Руководства (все видят действия друг друга)
OWNERS = [1614259542, 7716987740, 1751927856] 

if not TOKEN:
    print("❌ ОШИБКА: TOKEN не установлен!")
    sys.exit(1)

bot = telebot.TeleBot(TOKEN, parse_mode='HTML')
db_lock = Lock()
DB_FILE = 'dragpolit_enterprise_v8.db'

# ==========================================
# 2. БАЗА ДАННЫХ
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
    db_query('''CREATE TABLE IF NOT EXISTS admin_msgs 
                (t_id INTEGER PRIMARY KEY AUTOINCREMENT, user_uid INTEGER, msg_map TEXT)''', commit=True)
    db_query('''CREATE TABLE IF NOT EXISTS faq (id INTEGER PRIMARY KEY AUTOINCREMENT, q TEXT, a TEXT)''', commit=True)

init_db()

# ==========================================
# 3. СЛУЖБА СИНХРОНИЗАЦИИ (TEAM SYNC)
# ==========================================
def sync_admin_action(sender_id, target_uid, content_msg, is_reply=True):
    """ Рассылает копию ответа админа всем остальным участникам штаба """
    sender_name = f"ID:{sender_id}"
    for owner in OWNERS:
        if owner == sender_id: continue # Самому себе не шлем повтор
        
        try:
            status = "✍️ ОТВЕТ" if is_reply else "🔒 ЗАКРЫТИЕ"
            header = f"📡 <b>СИНХРОНИЗАЦИЯ ШТАБА</b>\n{status} от админа <code>{sender_id}</code>\nАдресат: <code>{target_uid}</code>\n━━━━━━━━━━━━\n"
            
            if content_msg.content_type == 'text':
                bot.send_message(owner, header + f"Текст: <i>{content_msg.text}</i>")
            else:
                bot.send_message(owner, header + f"Тип данных: {content_msg.content_type}")
                bot.copy_message(owner, sender_id, content_msg.message_id)
        except: pass

def update_ui_status(t_id, status_text):
    """ Меняет текст оригинального тикета у всех админов на статус 'Завершено' """
    res = db_query("SELECT msg_map FROM admin_msgs WHERE t_id = ?", (t_id,), fetch=True)
    if res:
        mapping = eval(res[0][0])
        for aid, mid in mapping.items():
            try:
                bot.edit_message_caption(chat_id=aid, message_id=mid, caption=status_text, reply_markup=None)
            except:
                try: bot.edit_message_text(chat_id=aid, message_id=mid, text=status_text, reply_markup=None)
                except: pass

# ==========================================
# 4. КЛАВИАТУРЫ
# ==========================================
def main_kb():
    kb = types.ReplyKeyboardMarkup(resize_keyboard=True, row_width=2)
    kb.add("🛡 Жалоба", "⚙️ Тех-отдел", "💬 Связь")
    kb.add("❓ FAQ", "🌍 Language")
    return kb

def admin_control_kb(u_id, t_id):
    kb = types.InlineKeyboardMarkup(row_width=2)
    kb.add(
        types.InlineKeyboardButton("📩 Ответить", callback_data=f"ans_{u_id}_{t_id}"),
        types.InlineKeyboardButton("🔒 Архив", callback_data=f"arc_{u_id}_{t_id}"),
        types.InlineKeyboardButton("👤 Досье", callback_data=f"inf_{u_id}"),
        types.InlineKeyboardButton("⛔️ BAN", callback_data=f"ban_{u_id}")
    )
    return kb

# ==========================================
# 5. ОСНОВНАЯ ЛОГИКА
# ==========================================
@bot.message_handler(commands=['start'])
def h_start(m):
    db_query("INSERT OR IGNORE INTO subjects (uid, username) VALUES (?, ?)", (m.chat.id, m.from_user.username), commit=True)
    bot.send_message(m.chat.id, "🏛 <b>Приемная DragPolit</b>", reply_markup=main_kb())

@bot.message_handler(commands=['admin'])
def h_admin(m):
    if m.chat.id not in OWNERS: return
    bot.send_message(m.chat.id, "👑 <b>Терминал Координации</b>\nВы видите действия всех администраторов.")

# Прием сообщений от пользователей
@bot.message_handler(content_types=['text', 'photo', 'video', 'document', 'voice', 'video_note'])
def handle_user_msg(m):
    if m.chat.id in OWNERS: return # Админы не создают тикеты сами себе
    
    # Регистрация тикета для синхронизации
    db_query("INSERT INTO admin_msgs (user_uid, msg_map) VALUES (?, ?)", (m.chat.id, "{}"), commit=True)
    t_id = db_query("SELECT last_insert_rowid()", fetch=True)[0][0]
    
    header = f"📑 <b>ТИКЕТ #{t_id}</b>\nОт: @{m.from_user.username} (<code>{m.chat.id}</code>)\n━━━━━━━━━━━━\n"
    msg_map = {}

    for aid in OWNERS:
        try:
            if m.content_type == 'text':
                r = bot.send_message(aid, header + f"💬 <i>{m.text}</i>", reply_markup=admin_control_kb(m.chat.id, t_id))
            else:
                bot.send_message(aid, header)
                r = bot.copy_message(aid, m.chat.id, m.message_id, reply_markup=admin_control_kb(m.chat.id, t_id))
            msg_map[aid] = r.message_id
        except: pass
    
    db_query("UPDATE admin_msgs SET msg_map = ? WHERE t_id = ?", (str(msg_map), t_id), commit=True)
    bot.send_message(m.chat.id, "✅ Сообщение передано Штабу.")

# Обработка действий админов
@bot.callback_query_handler(func=lambda c: True)
def h_callbacks(c):
    p = c.data.split('_')
    action, uid = p[0], int(p[1])
    aid = c.from_user.id
    
    if action == 'ans':
        t_id = p[2]
        msg = bot.send_message(aid, f"📝 <b>ВАШ ОТВЕТ НА ТИКЕТ #{t_id}:</b>")
        bot.register_next_step_handler(msg, step_admin_reply, uid, t_id)
        
    elif action == 'arc':
        t_id = p[2]
        update_ui_status(t_id, f"✅ <b>ЗАВЕРШЕНО</b>\nАрхивировано админом <code>{aid}</code>")
        sync_admin_action(aid, uid, types.Message(0,None,None,None,None,None,None), is_reply=False)

    elif action == 'inf':
        u = db_query("SELECT username, note FROM subjects WHERE uid = ?", (uid,), fetch=True)[0]
        bot.send_message(aid, f"👤 @{u[0]}\nID: <code>{uid}</code>\nЗаметка: {u[1] or 'пусто'}\n\nНапишите новую заметку:")
        bot.register_next_step_handler(c.message, step_save_note, uid)

# Логика отправки ответа и синхронизации
def step_admin_reply(m, uid, t_id):
    aid = m.from_user.id
    try:
        header = "🏛 <b>ОФИЦИАЛЬНАЯ РЕЗОЛЮЦИЯ:</b>\n━━━━━━━━━━━━\n\n"
        if m.content_type == 'text':
            bot.send_message(uid, header + m.text)
        else:
            bot.send_message(uid, header)
            bot.copy_message(uid, m.chat.id, m.message_id)
        
        # 1. Рассылаем копию ответа всем другим админам
        sync_admin_action(aid, uid, m, is_reply=True)
        
        # 2. Обновляем статус кнопок у всех админов
        txt = f"✅ <b>ОТВЕЧЕНО</b>\nАдмин <code>{aid}</code> дал ответ."
        update_ui_status(t_id, txt)
        
        bot.send_message(aid, "✅ Ответ отправлен и синхронизирован с коллегами.")
    except:
        bot.send_message(aid, "❌ Ошибка отправки пользователю.")

def step_save_note(m, uid):
    db_query("UPDATE subjects SET note = ? WHERE uid = ?", (m.text, uid), commit=True)
    bot.send_message(m.chat.id, "✅ Заметка обновлена в общей базе.")

# ==========================================
# 6. ЗАПУСК
# ==========================================
if __name__ == '__main__':
    print("------------------------------------")
    print("🏛 DRAGPOLIT TEAM SYNC MASTER ONLINE")
    print("------------------------------------")
    bot.infinity_polling()
