import os
import sqlite3
import telebot
import logging
from telebot import types, util
from datetime import datetime
from threading import Lock

# ==========================================
# 1. СИСТЕМНАЯ КОНФИГУРАЦИЯ
# ==========================================
TOKEN = os.environ.get('TOKEN', 'ТВОЙ_ТОКЕН_ЗДЕСЬ')
OWNERS = [1614259542, 7716987740]  # ID Руководства
DB_PATH = 'dragpolit_ultimate.db'

# Логирование в файл для отладки
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    filename='bot_internal.log'
)

bot = telebot.TeleBot(TOKEN, parse_mode='HTML')
db_lock = Lock() # Защита базы от одновременной записи

# ==========================================
# 2. МУЛЬТИЯЗЫЧНЫЙ ЯДРО (I18n)
# ==========================================
TRANSLATIONS = {
    'ru': {
        'welcome': "🏛 <b>Центральный узел связи DragPolit</b>\n\nРады видеть вас, Субъект. Ваша активность фиксируется. Выберите департамент для формирования запроса:",
        'b_bug': "🐛 Технический отдел", 'b_upd': "🚀 Отдел инноваций",
        'b_trn': "🌐 Лингвистический центр", 'b_oth': "📝 Общая приемная",
        'b_faq': "❓ Инфо-блок", 'b_lng': "🌍 Язык / Language",
        'b_tic': "📑 Мои обращения",
        'input': "📋 <b>Формирование протокола</b>\nОпишите суть. Допускается вложение медиафайлов (фото/видео).",
        'wait': "⏳ <i>Регистрация сообщения в системе...</i>",
        'success': "✅ <b>Протокол #{id} успешно сформирован.</b>\nСтатус: Направлен руководству департамента {cat}.",
        'closed': "🔒 Обращение #{id} перемещено в архив. Благодарим за содействие.",
        'ban_msg': "⛔️ <b>Доступ аннулирован.</b> Ваша учетная запись была деактивирована службой безопасности.",
        'reply_head': "🏛 <b>ОФИЦИАЛЬНАЯ РЕЗОЛЮЦИЯ РУКОВОДСТВА:</b>\n\n",
        'no_tickets': "📭 У вас нет активных обращений."
    },
    'en': {
        'welcome': "🏛 <b>DragPolit Central Communications Hub</b>\n\nWelcome, Subject. Your activity is being monitored. Select a department to file a report:",
        'b_bug': "🐛 Technical Dept", 'b_upd': "🚀 Innovations",
        'b_trn': "🌐 Linguistics Center", 'b_oth': "📝 General Reception",
        'b_faq': "❓ Info Block", 'b_lng': "🌍 Change Language",
        'b_tic': "📑 My Requests",
        'input': "📋 <b>Report Protocol</b>\nDescribe the issue. Media attachments (photo/video) are allowed.",
        'wait': "⏳ <i>Registering message in the system...</i>",
        'success': "✅ <b>Protocol #{id} successfully filed.</b>\nStatus: Sent to the {cat} leadership.",
        'closed': "🔒 Request #{id} moved to archives. Thank you for your cooperation.",
        'ban_msg': "⛔️ <b>Access Annulled.</b> Your account has been deactivated by the security service.",
        'reply_head': "🏛 <b>OFFICIAL MANAGEMENT RESOLUTION:</b>\n\n",
        'no_tickets': "📭 You have no active requests."
    }
}

# ==========================================
# 3. DB МЕНЕДЖЕР (THREAD-SAFE)
# ==========================================
class Database:
    def __init__(self, path):
        self.path = path
        self._init_tables()

    def _execute(self, query, params=(), commit=False, fetch=False):
        with db_lock:
            conn = sqlite3.connect(self.path)
            cursor = conn.cursor()
            cursor.execute(query, params)
            res = None
            if fetch: res = cursor.fetchall()
            if commit: conn.commit()
            conn.close()
            return res

    def _init_tables(self):
        # Субъекты (Пользователи)
        self._execute('''CREATE TABLE IF NOT EXISTS subjects (
            uid INTEGER PRIMARY KEY, 
            name TEXT, 
            lang TEXT DEFAULT 'ru',
            state TEXT DEFAULT 'ST_IDLE', 
            ban INTEGER DEFAULT 0,
            note TEXT DEFAULT '',
            reg_date TEXT)''', commit=True)
        # Обращения (Тикеты)
        self._execute('''CREATE TABLE IF NOT EXISTS protocols (
            pid INTEGER PRIMARY KEY AUTOINCREMENT, 
            uid INTEGER, 
            category TEXT, 
            status TEXT DEFAULT 'OPEN', 
            date TEXT)''', commit=True)
        # Журнал Аудита
        self._execute('''CREATE TABLE IF NOT EXISTS audit_logs (
            aid INTEGER PRIMARY KEY AUTOINCREMENT, 
            admin_id INTEGER, 
            action TEXT, 
            target_id TEXT, 
            timestamp TEXT)''', commit=True)

    def get_subject(self, uid, name=""):
        res = self._execute("SELECT lang, state, ban, note, reg_date FROM subjects WHERE uid = ?", (uid,), fetch=True)
        if not res:
            dt = datetime.now().strftime("%Y-%m-%d")
            self._execute("INSERT INTO subjects (uid, name, reg_date) VALUES (?, ?, ?)", (uid, name, dt), commit=True)
            return {'lang': 'ru', 'state': 'ST_IDLE', 'ban': 0, 'note': '', 'reg': dt}
        return {'lang': res[0][0], 'state': res[0][1], 'ban': res[0][2], 'note': res[0][3], 'reg': res[0][4]}

    def set_val(self, uid, column, val):
        self._execute(f"UPDATE subjects SET {column} = ? WHERE uid = ?", (val, uid), commit=True)

db = Database(DB_PATH)

# ==========================================
# 4. УТИЛИТЫ ДЛЯ АДМИНИСТРАЦИИ
# ==========================================
def log_event(admin_id, action, target=""):
    dt = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    db._execute("INSERT INTO audit_logs (admin_id, action, target_id, timestamp) VALUES (?, ?, ?, ?)",
               (admin_id, action, str(target), dt), commit=True)

def get_admin_markup(pid, uid):
    kb = types.InlineKeyboardMarkup(row_width=2)
    kb.add(
        types.InlineKeyboardButton("📩 Ответить", callback_data=f"adm_rep_{uid}_{pid}"),
        types.InlineKeyboardButton("🔒 Архив", callback_data=f"adm_cls_{uid}_{pid}"),
        types.InlineKeyboardButton("👤 Досье", callback_data=f"adm_dos_{uid}"),
        types.InlineKeyboardButton("⛔️ Бан", callback_data=f"adm_ban_{uid}")
    )
    return kb

# ==========================================
# 5. UX: ГЕНЕРАТОРЫ КЛАВИАТУР
# ==========================================
def get_main_kb(uid):
    s = db.get_subject(uid)
    l = s['lang']
    kb = types.ReplyKeyboardMarkup(resize_keyboard=True, row_width=2)
    kb.add(TRANSLATIONS[l]['b_bug'], TRANSLATIONS[l]['b_upd'])
    kb.add(TRANSLATIONS[l]['b_trn'], TRANSLATIONS[l]['b_oth'])
    kb.add(TRANSLATIONS[l]['b_tic'], TRANSLATIONS[l]['b_faq'], TRANSLATIONS[l]['b_lng'])
    return kb

# ==========================================
# 6. ЛОГИКА ОБРАБОТКИ
# ==========================================
@bot.message_handler(commands=['start'])
def h_start(message):
    s = db.get_subject(message.chat.id, message.from_user.username)
    if s['ban']: return bot.send_message(message.chat.id, TRANSLATIONS[s['lang']]['ban_msg'])
    
    db.set_val(message.chat.id, 'state', 'ST_IDLE')
    bot.send_message(message.chat.id, TRANSLATIONS[s['lang']]['welcome'], reply_markup=get_main_kb(message.chat.id))

@bot.message_handler(commands=['admin'])
def h_admin(message):
    if message.chat.id not in OWNERS: return
    stats = db._execute("SELECT (SELECT COUNT(*) FROM subjects), (SELECT COUNT(*) FROM protocols WHERE status='OPEN')", fetch=True)[0]
    msg = f"👑 <b>КОНТРОЛЬНАЯ ПАНЕЛЬ DRAGPOLIT</b>\n\n" \
          f"🔹 Зарегистрировано субъектов: <code>{stats[0]}</code>\n" \
          f"🔹 Ожидают решения: <code>{stats[1]}</code>\n\n" \
          f"Доступные действия: /broadcast, /audit_log"
    bot.send_message(message.chat.id, msg)

# --- Работа с обращениями ---

@bot.message_handler(func=lambda m: any(m.text in d.values() for d in TRANSLATIONS.values()))
def h_category_selection(message):
    s = db.get_subject(message.chat.id)
    if s['ban']: return
    
    # Обработка спец. кнопок
    if message.text in [TRANSLATIONS['ru']['b_lng'], TRANSLATIONS['en']['b_lng']]:
        new_l = 'en' if s['lang'] == 'ru' else 'ru'
        db.set_val(message.chat.id, 'lang', new_l)
        return bot.send_message(message.chat.id, "✅ Language switched.", reply_markup=get_main_kb(message.chat.id))
    
    if message.text in [TRANSLATIONS['ru']['b_faq'], TRANSLATIONS['en']['b_faq']]:
        return bot.send_message(message.chat.id, "📒 <b>Информационный реестр:</b>\n1. Мальтийский закон\n2. Регламент сервера.")

    if message.text in [TRANSLATIONS['ru']['b_tic'], TRANSLATIONS['en']['b_tic']]:
        tickets = db._execute("SELECT pid, category, status FROM protocols WHERE uid = ? ORDER BY pid DESC LIMIT 3", (message.chat.id,), fetch=True)
        if not tickets: return bot.send_message(message.chat.id, TRANSLATIONS[s['lang']]['no_tickets'])
        res = "📋 <b>Последние записи:</b>\n" + "\n".join([f"#{t[0]} [{t[1]}] - {t[2]}" for t in tickets])
        return bot.send_message(message.chat.id, res)

    # Стандартные категории тикетов
    db.set_val(message.chat.id, 'state', f"WAIT_CONTENT|{message.text}")
    bot.send_message(message.chat.id, TRANSLATIONS[s['lang']]['input'], reply_markup=types.ReplyKeyboardRemove())

@bot.message_handler(content_types=['text', 'photo', 'video', 'document', 'voice'])
def h_process_submission(message):
    s = db.get_subject(message.chat.id)
    if s['ban'] or "WAIT_CONTENT" not in s['state']: return
    
    category = s['state'].split('|')[1]
    db.set_val(message.chat.id, 'state', 'ST_IDLE')
    
    dt = datetime.now().strftime("%H:%M:%S")
    db._execute("INSERT INTO protocols (uid, category, date) VALUES (?, ?, ?)", (message.chat.id, category, dt), commit=True)
    pid = db._execute("SELECT last_insert_rowid()", fetch=True)[0][0]
    
    bot.send_message(message.chat.id, TRANSLATIONS[s['lang']]['success'].format(id=pid, cat=category), reply_markup=get_main_kb(message.chat.id))
    
    # Маршрутизация в Генштаб (админам)
    adm_card = f"📨 <b>ПРОТОКОЛ #{pid}</b> [{category}]\n" \
               f"├ Субъект: @{message.from_user.username} (ID: <code>{message.chat.id}</code>)\n" \
               f"└ Регистрация: {dt}\n\n"
    
    for owner in OWNERS:
        try:
            if message.content_type == 'text':
                bot.send_message(owner, adm_card + f"💬 <blockquote>{message.text}</blockquote>", reply_markup=get_admin_markup(pid, message.chat.id))
            else:
                bot.send_message(owner, adm_card + "📎 Медиа-материалы прилагаются:")
                bot.copy_message(owner, message.chat.id, message.message_id, reply_markup=get_admin_markup(pid, message.chat.id))
        except Exception as e:
            logging.error(f"Error notifying admin {owner}: {e}")

# ==========================================
# 7. ПАНЕЛЬ CRM (CALLBACK HANDLERS)
# ==========================================
@bot.callback_query_handler(func=lambda c: c.data.startswith('adm_'))
def h_callbacks(call):
    parts = call.data.split('_')
    action, uid = parts[1], int(parts[2])
    
    if action == 'dos': # Dossier
        u = db.get_subject(uid)
        count = db._execute("SELECT COUNT(*) FROM protocols WHERE uid = ?", (uid,), fetch=True)[0][0]
        dos = f"📁 <b>ДОСЬЕ СУБЪЕКТА</b> <code>{uid}</code>\n\n" \
              f"• Репутация: {'🚩 Banned' if u['ban'] else '🏳 Neutral'}\n" \
              f"• Регистрация: {u['reg']}\n" \
              f"• Кол-во запросов: {count}\n" \
              f"• Примечание: <i>{u['note'] if u['note'] else 'N/A'}</i>"
        bot.send_message(call.message.chat.id, dos)

    elif action == 'ban':
        db.set_val(uid, 'ban', 1)
        log_event(call.from_user.id, "BAN_USER", uid)
        bot.answer_callback_query(call.id, "Субъект деактивирован.", show_alert=True)
        try: bot.send_message(uid, TRANSLATIONS['ru']['ban_msg'])
        except: pass

    elif action == 'rep': # Reply
        pid = parts[3]
        bot.send_message(call.message.chat.id, f"📝 <b>Резолюция для #{pid}:</b>")
        bot.register_next_step_handler(call.message, step_send_reply, uid, pid)

    elif action == 'cls':
        pid = parts[3]
        db._execute("UPDATE protocols SET status = 'CLOSED' WHERE pid = ?", (pid,), commit=True)
        bot.edit_message_text(f"🔒 <b>Архивировано:</b> Протокол #{pid}", call.message.chat.id, call.message.message_id)
        u_lang = db.get_subject(uid)['lang']
        try: bot.send_message(uid, TRANSLATIONS[u_lang]['closed'].format(id=pid))
        except: pass

def step_send_reply(message, uid, pid):
    l = db.get_subject(uid)['lang']
    prefix = TRANSLATIONS[l]['reply_head']
    try:
        if message.content_type == 'text':
            bot.send_message(uid, f"{prefix}<i>{message.text}</i>")
        else:
            bot.send_message(uid, prefix)
            bot.copy_message(uid, message.chat.id, message.message_id)
        log_event(message.chat.id, f"REPLY_PROT_{pid}", uid)
        bot.send_message(message.chat.id, f"✅ Резолюция к протоколу #{pid} успешно доставлена.")
    except Exception as e:
        bot.send_message(message.chat.id, "❌ Сбой связи: Субъект ограничил доступ.")

# ==========================================
# 8. ЗАПУСК И КОМАНДЫ
# ==========================================
if __name__ == '__main__':
    # Настройка командного меню для удобства
    bot.set_my_commands([
        types.BotCommand("start", "Подключение к узлу связи"),
        types.BotCommand("help", "Информация"),
        types.BotCommand("admin", "Панель контроля (только руководство)")
    ])
    
    print("--------------------------------------------------")
    print("🏛 DRAGPOLIT SUPPORT NODE IS ONLINE")
    print(f"Time: {datetime.now().strftime('%H:%M:%S')}")
    print("--------------------------------------------------")
    
    try:
        bot.infinity_polling(timeout=10, long_polling_timeout=5)
    except Exception as e:
        logging.critical(f"Global breakdown: {e}")
