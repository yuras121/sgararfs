import os
import sqlite3
import telebot
import logging
from telebot import types
from datetime import datetime
from threading import Lock

# ==========================================
# 1. СИСТЕМНЫЕ НАСТРОЙКИ
# ==========================================
TOKEN = os.environ.get('TOKEN')
# Добавь сюда ID админов
OWNERS = [1614259542, 7716987740] 
DB_NAME = 'dragpolit_enterprise.db'

bot = telebot.TeleBot(TOKEN, parse_mode='HTML')
db_lock = Lock()

# ==========================================
# 2. МУЛЬТИЯЗЫЧНЫЙ СЛОВАРЬ (ENTERPRISE STYLE)
# ==========================================
STRINGS = {
    'ru': {
        'start_msg': "🏛 <b>Центральный узел управления DragPolit</b>\n\nСистема приветствует вас. Все входящие данные шифруются и направляются в соответствующие департаменты.",
        'btn_bug': "🐛 Тех. Сбой", 'btn_upd': "🚀 Предложение", 
        'btn_trn': "🌐 Локализация", 'btn_oth': "📝 Связь с Руководством",
        'btn_faq': "❓ Справка", 'btn_lang': "🌍 Сменить язык",
        'input_prompt': "📋 <b>РЕЖИМ ЗАПИСИ ПРОТОКОЛА</b>\n\nИзложите суть вашего обращения в одном сообщении. Мы принимаем текст, видео, фото и документы.",
        'ticket_success': "✅ <b>ПРОТОКОЛ #{id} ЗАРЕГИСТРИРОВАН</b>\n\nДепартамент: {cat}\nСтатус: Ожидание резолюции администрации.",
        'reply_head': "🏛 <b>ОФИЦИАЛЬНАЯ РЕЗОЛЮЦИЯ РУКОВОДСТВА:</b>\n━━━━━━━━━━━━━━━━━━━━\n\n",
        'ticket_closed': "🔒 Обращение #{id} перемещено в архив. Благодарим за содействие.",
        'user_banned': "⛔️ <b>ОТКАЗ В ДОСТУПЕ:</b> Ваша учетная запись была изолирована за нарушение протокола.",
        'confirm_lang': "✅ Локализация успешно обновлена."
    },
    'en': {
        'start_msg': "🏛 <b>DragPolit Central Command Node</b>\n\nSystem greets you. All incoming data is encrypted and forwarded to the appropriate departments.",
        'btn_bug': "🐛 Tech Failure", 'btn_upd': "🚀 Suggestion", 
        'btn_trn': "🌐 Localization", 'btn_oth': "📝 Management Contact",
        'btn_faq': "❓ Help Center", 'btn_lang': "🌍 Switch Language",
        'input_prompt': "📋 <b>PROTOCOL RECORDING MODE</b>\n\nPlease state the essence of your request in one message. Text, video, photo, and docs are supported.",
        'ticket_success': "✅ <b>PROTOCOL #{id} REGISTERED</b>\n\nDepartment: {cat}\nStatus: Waiting for management resolution.",
        'reply_head': "🏛 <b>OFFICIAL MANAGEMENT RESOLUTION:</b>\n━━━━━━━━━━━━━━━━━━━━\n\n",
        'ticket_closed': "🔒 Request #{id} has been archived. Thank you for cooperation.",
        'user_banned': "⛔️ <b>ACCESS DENIED:</b> Your account has been isolated for protocol violation.",
        'confirm_lang': "✅ Localization updated successfully."
    }
}

# ==========================================
# 3. БАЗА ДАННЫХ (CORE PERSISTENCE)
# ==========================================
class DataEngine:
    def __init__(self, path):
        self.path = path
        self._setup()

    def _execute(self, query, params=(), commit=False, fetch=False):
        with db_lock:
            with sqlite3.connect(self.path, timeout=20) as conn:
                conn.execute("PRAGMA journal_mode=WAL;") # Повышаем стабильность
                cursor = conn.cursor()
                cursor.execute(query, params)
                res = cursor.fetchall() if fetch else None
                if commit: conn.commit()
                return res

    def _setup(self):
        # Субъекты системы
        self._execute('''CREATE TABLE IF NOT EXISTS subjects (
            uid INTEGER PRIMARY KEY, username TEXT, lang TEXT DEFAULT 'ru', 
            state TEXT DEFAULT 'HOME', banned INTEGER DEFAULT 0, note TEXT DEFAULT '', reg_date TEXT)''', commit=True)
        # Обращения
        self._execute('''CREATE TABLE IF NOT EXISTS protocols (
            pid INTEGER PRIMARY KEY AUTOINCREMENT, uid INTEGER, category TEXT, 
            status TEXT DEFAULT 'OPEN', created_at TEXT)''', commit=True)
        # Журнал аудита
        self._execute('''CREATE TABLE IF NOT EXISTS logs (
            lid INTEGER PRIMARY KEY AUTOINCREMENT, aid INTEGER, action TEXT, target_id INTEGER, ts TEXT)''', commit=True)

    def get_subject(self, uid, username="Unknown"):
        res = self._execute("SELECT lang, state, banned, note, reg_date FROM subjects WHERE uid = ?", (uid,), fetch=True)
        if not res:
            dt = datetime.now().strftime("%d.%m.%Y")
            self._execute("INSERT INTO subjects (uid, username, reg_date) VALUES (?, ?, ?)", (uid, username, dt), commit=True)
            return {'lang': 'ru', 'state': 'HOME', 'banned': 0, 'note': '', 'reg': dt}
        return {'lang': res[0][0], 'state': res[0][1], 'banned': res[0][2], 'note': res[0][3], 'reg': res[0][4]}

    def set_val(self, uid, table, column, value):
        self._execute(f"UPDATE {table} SET {column} = ? WHERE uid = ?", (value, uid), commit=True)

db = DataEngine(DB_NAME)

# ==========================================
# 4. СИСТЕМА УПРАВЛЕНИЯ (ADMIN UI)
# ==========================================
def admin_dashboard_kb(pid, uid):
    kb = types.InlineKeyboardMarkup(row_width=2)
    kb.add(
        types.InlineKeyboardButton("📩 Ответить", callback_data=f"rep_{uid}_{pid}"),
        types.InlineKeyboardButton("🗄 В Архив", callback_data=f"arc_{uid}_{pid}"),
        types.InlineKeyboardButton("👤 Досье Субъекта", callback_data=f"dos_{uid}"),
        types.InlineKeyboardButton("📝 Заметка", callback_data=f"note_{uid}"),
        types.InlineKeyboardButton("⛔️ Изоляция (БАН)", callback_data=f"ban_{uid}")
    )
    return kb

def main_kb(uid):
    u = db.get_subject(uid)
    l = u['lang']
    kb = types.ReplyKeyboardMarkup(resize_keyboard=True, row_width=2)
    kb.add(STRINGS[l]['btn_bug'], STRINGS[l]['btn_upd'])
    kb.add(STRINGS[l]['btn_trn'], STRINGS[l]['btn_oth'])
    kb.add(STRINGS[l]['btn_faq'], STRINGS[l]['btn_lang'])
    return kb

# ==========================================
# 5. ХЕНДЛЕРЫ И БИЗНЕС-ЛОГИКА
# ==========================================
@bot.message_handler(commands=['start'])
def h_start(message):
    s = db.get_subject(message.chat.id, message.from_user.username)
    if s['banned']: return bot.send_message(message.chat.id, STRINGS[s['lang']]['user_banned'])
    
    db.set_val(message.chat.id, 'subjects', 'state', 'HOME')
    bot.send_message(message.chat.id, STRINGS[s['lang']]['start_msg'], reply_markup=main_kb(message.chat.id))

# Фильтрация кнопок меню
@bot.message_handler(func=lambda m: any(m.text in d.values() for d in STRINGS.values()))
def h_menu_logic(message):
    s = db.get_subject(message.chat.id)
    if s['banned']: return
    
    l = s['lang']
    # Смена языка
    if message.text in [STRINGS['ru']['btn_lang'], STRINGS['en']['btn_lang']]:
        new_lang = 'en' if l == 'ru' else 'ru'
        db.set_val(message.chat.id, 'subjects', 'lang', new_lang)
        return bot.send_message(message.chat.id, STRINGS[new_lang]['confirm_lang'], reply_markup=main_kb(message.chat.id))

    # Справка (пример)
    if message.text in [STRINGS['ru']['btn_faq'], STRINGS['en']['btn_faq']]:
        help_text = "<b>DRAGPOLIT Wiki:</b>\n1. Основные законы\n2. Обучение\n\nВсе вопросы решаются через тикеты."
        return bot.send_message(message.chat.id, help_text)

    # Категории
    category = message.text
    db.set_val(message.chat.id, 'subjects', 'state', f"SEND_MODE|{category}")
    bot.send_message(message.chat.id, STRINGS[l]['input_prompt'], reply_markup=types.ReplyKeyboardRemove())

# Обработка содержимого тикета
@bot.message_handler(content_types=['text', 'photo', 'video', 'document', 'audio', 'voice', 'video_note'])
def h_intake(message):
    s = db.get_subject(message.chat.id)
    if s['banned'] or "SEND_MODE" not in s['state']: return
    
    category = s['state'].split('|')[1]
    ts = datetime.now().strftime("%H:%M:%S")
    db._execute("INSERT INTO protocols (uid, category, created_at) VALUES (?, ?, ?)", 
               (message.chat.id, category, ts), commit=True)
    pid = db._execute("SELECT last_insert_rowid()", fetch=True)[0][0]
    
    # Сброс состояния
    db.set_val(message.chat.id, 'subjects', 'state', 'HOME')
    bot.send_message(message.chat.id, STRINGS[s['lang']]['ticket_success'].format(id=pid, cat=category), reply_markup=main_kb(message.chat.id))

    # Пакет данных для Руководства
    header = (f"📑 <b>НОВЫЙ ПРОТОКОЛ #{pid}</b>\n"
              f"👤 Субъект: @{message.from_user.username} (<code>{message.chat.id}</code>)\n"
              f"🏷 Отдел: {category}\n"
              f"━━━━━━━ ОТПРАВЛЕНО ━━━━━━━\n\n")

    for admin in OWNERS:
        try:
            if message.content_type == 'text':
                bot.send_message(admin, header + f"💬 <i>{message.text}</i>", reply_markup=admin_dashboard_kb(pid, message.chat.id))
            else:
                bot.send_message(admin, header + "📎 Приложенный медиа-файл:")
                bot.copy_message(admin, message.chat.id, message.message_id, reply_markup=admin_dashboard_kb(pid, message.chat.id))
        except: pass

# ==========================================
# 6. CRM-ХЕНДЛЕРЫ (ИНТЕРАКТИВ С ТИКЕТАМИ)
# ==========================================
@bot.callback_query_handler(func=lambda c: True)
def h_callbacks(call):
    # Разбор: действие_пользователь_номер_билета
    p = call.data.split('_')
    action = p[0]
    target_id = int(p[1])
    
    if action == 'dos': # Показать Досье
        s = db.get_subject(target_id)
        tk_stats = db._execute("SELECT COUNT(*) FROM protocols WHERE uid = ?", (target_id,), fetch=True)[0][0]
        st_text = "🚫 Изолирован" if s['banned'] else "🟢 Активен"
        dossier = (f"👤 <b>ДОСЬЕ СУБЪЕКТА {target_id}</b>\n\n"
                   f"🗓 В базе с: {s['reg']}\n"
                   f"📈 Всего обращений: {tk_stats}\n"
                   f"⚖️ Статус допуска: {st_text}\n"
                   f"📓 Админ-заметка: <i>{s['note'] if s['note'] else 'Пусто'}</i>")
        bot.send_message(call.message.chat.id, dossier)

    elif action == 'ban':
        db._execute("UPDATE subjects SET banned = 1 WHERE uid = ?", (target_id,), commit=True)
        bot.answer_callback_query(call.id, "❌ Субъект деактивирован", show_alert=True)
        try: bot.send_message(target_id, STRINGS['ru']['user_banned'])
        except: pass

    elif action == 'arc':
        pid = p[2]
        db._execute("UPDATE protocols SET status = 'CLOSED' WHERE pid = ?", (pid,), commit=True)
        bot.edit_message_text(f"🔒 <b>Архив:</b> Протокол #{pid} закрыт.", call.message.chat.id, call.message.message_id)
        u_lang = db.get_subject(target_id)['lang']
        try: bot.send_message(target_id, STRINGS[u_lang]['ticket_closed'].format(id=pid))
        except: pass

    elif action == 'note':
        msg = bot.send_message(call.message.chat.id, "📝 Введите заметку (её увидите только вы и другие админы):")
        bot.register_next_step_handler(msg, step_save_note, target_id)

    elif action == 'rep':
        pid = p[2]
        msg = bot.send_message(call.message.chat.id, f"✉️ <b>Ваша резолюция по #{pid}:</b>")
        bot.register_next_step_handler(msg, step_reply_ticket, target_id, pid)

def step_save_note(message, target_id):
    db._execute("UPDATE subjects SET note = ? WHERE uid = ?", (message.text, target_id), commit=True)
    bot.send_message(message.chat.id, "✅ Заметка внесена в досье.")

def step_reply_ticket(message, target_id, pid):
    u_lang = db.get_subject(target_id)['lang']
    prefix = STRINGS[u_lang]['reply_head']
    try:
        if message.content_type == 'text':
            bot.send_message(target_id, f"{prefix}<i>{message.text}</i>")
        else:
            bot.send_message(target_id, prefix)
            bot.copy_message(target_id, message.chat.id, message.message_id)
        bot.send_message(message.chat.id, f"✅ Ответ к #{pid} успешно доставлен.")
    except:
        bot.send_message(message.chat.id, "❌ Ошибка доставки: Бот заблокирован субъектом.")

# ==========================================
# 7. ГЛОБАЛЬНЫЙ ЗАПУСК (AUTO-HEAL POLLING)
# ==========================================
if __name__ == '__main__':
    db._setup() # Убеждаемся, что БД готова
    
    # Настройка кнопок-команд
    bot.set_my_commands([
        types.BotCommand("start", "🏠 Главное Меню"),
        types.BotCommand("help", "❓ Справка")
    ])
    
    print(f"[{datetime.now().strftime('%H:%M:%S')}] DRAGPOLIT Enterprise System ACTIVE.")
    
    # Режим infinity_polling защищает бота от вылетов при перебоях со связью
    bot.infinity_polling(timeout=10, long_polling_timeout=5)
