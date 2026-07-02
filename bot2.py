import os
import time
import threading
import re
import json
import telebot
from telebot import types
from flask import Flask

# === НАЛАШТУВАННЯ ===
TOKEN = os.environ.get('TOKEN', '8252581199:AAHNfedYh1MrQVNBrL6mYf6OJVoTim_dApM')

ADMIN_GROUP_ID = "-1614259542" 

# ВПИШІТЬ СЮДИ ЦИФРОВІ ID ВЛАСНИКІВ (@dragwayder та @p1vi_k)
# Їх можна дізнатися, якщо кожен з власників напише боту команду /get_id
OWNERS = [111111111, 222222222] 

bot = telebot.TeleBot(TOKEN, parse_mode='HTML')

user_states = {}

# === БАЗА ДАНИХ КОРИСТУВАЧІВ (ДЛЯ РОЗСИЛКИ) ===
USERS_FILE = 'users.json'

def load_users():
    if os.path.exists(USERS_FILE):
        try:
            with open(USERS_FILE, 'r') as f:
                return set(json.load(f))
        except:
            return set()
    return set()

def save_user(user_id):
    users = load_users()
    if user_id not in users:
        users.add(user_id)
        with open(USERS_FILE, 'w') as f:
            json.dump(list(users), f)

# === КОРИСТУВАЦЬКИЙ ІНТЕРФЕЙС ===
def get_start_kb():
    markup = types.InlineKeyboardMarkup(row_width=1)
    markup.add(
        types.InlineKeyboardButton("🚨 Экстренная связь / ЧП", callback_data="type_urgent"),
        types.InlineKeyboardButton("🤝 Предложения и сотрудничество", callback_data="type_collab"),
        types.InlineKeyboardButton("🐛 Сообщить о баге", callback_data="type_bug"),
        types.InlineKeyboardButton("📝 Подать заявку в Администрацию", callback_data="type_apply") # НОВА КНОПКА
    )
    return markup

def get_cancel_kb():
    markup = types.InlineKeyboardMarkup()
    markup.add(types.InlineKeyboardButton("❌ Отменить", callback_data="cancel_action"))
    return markup

def get_admin_kb():
    markup = types.InlineKeyboardMarkup(row_width=1)
    markup.add(
        types.InlineKeyboardButton("📢 Сделать рассылку (Оповещение)", callback_data="admin_broadcast"),
        types.InlineKeyboardButton("📊 Статистика бота", callback_data="admin_stats")
    )
    return markup

@bot.message_handler(commands=['start'])
def start_command(message):
    save_user(message.chat.id) # Зберігаємо користувача для розсилки
    user_states.pop(message.chat.id, None)
    
    text = (
        "<b>Официальная служба поддержки DragPolit</b>\n\n"
        "Выберите необходимый раздел меню. Обратите внимание, что спам и ложные вызовы могут привести к блокировке."
    )
    bot.send_message(message.chat.id, text, reply_markup=get_start_kb())

@bot.message_handler(commands=['admin'])
def admin_panel_command(message):
    if message.chat.id not in OWNERS:
        return bot.reply_to(message, "⛔️ У вас нет доступа к этой команде.")
    
    bot.send_message(
        message.chat.id, 
        "👑 <b>Панель управления Владельцев</b>\nЗдесь вы можете управлять ботом:", 
        reply_markup=get_admin_kb()
    )

@bot.message_handler(commands=['get_id'])
def get_id_command(message):
    bot.reply_to(message, f"Ваш ID: <code>{message.chat.id}</code>")

@bot.callback_query_handler(func=lambda call: call.data == 'cancel_action')
def cancel_action(call):
    user_states.pop(call.message.chat.id, None)
    bot.edit_message_text("Действие отменено. Возврат в главное меню.", call.message.chat.id, call.message.message_id, reply_markup=get_start_kb())

# === ОБРОБКА АДМІН-КНОПОК ===
@bot.callback_query_handler(func=lambda call: call.data.startswith('admin_'))
def handle_admin_callbacks(call):
    if call.message.chat.id not in OWNERS:
        return bot.answer_callback_query(call.id, "Нет доступа!", show_alert=True)
    
    action = call.data.split('_')[1]
    
    if action == 'stats':
        users_count = len(load_users())
        bot.edit_message_text(f"📊 <b>Статистика:</b>\nВсего пользователей в базе: {users_count}", call.message.chat.id, call.message.message_id, reply_markup=get_admin_kb())
    
    elif action == 'broadcast':
        user_states[call.message.chat.id] = {'state': 'waiting_broadcast'}
        bot.edit_message_text("📢 <b>Рассылка</b>\nОтправьте сообщение (текст, фото или видео), которое нужно разослать всем пользователям бота:", call.message.chat.id, call.message.message_id, reply_markup=get_cancel_kb())

# === ОБРОБКА КНОПОК МЕНЮ ===
@bot.callback_query_handler(func=lambda call: call.data.startswith('type_'))
def handle_main_menu(call):
    action = call.data.split('_')[1]
    
    if action == 'bug':
        text = "🛠 <b>Баг-репорт</b>\nОпишите проблему одним сообщением:\n1. Что сломалось?\n2. Где?\n3. Как повторить?"
        category = "Баг-репорт"
    elif action == 'urgent':
        text = "🚨 <b>Экстренная связь (ЧП)</b>\nПодробно опишите проблему. Руководство рассмотрит ее вне очереди."
        category = "ЧП / Срочно"
    elif action == 'collab':
        text = "🤝 <b>Сотрудничество</b>\nОпишите ваше коммерческое предложение или идею."
        category = "Сотрудничество"
    elif action == 'apply':
        text = "📝 <b>Набор в Администрацию</b>\nНапишите вашу заявку одним сообщением:\n1. Имя и возраст\n2. Почему хотите стать админом?\n3. Ваш опыт работы."
        category = "Заявка в админы"
        
    user_states[call.message.chat.id] = {'state': 'waiting_ticket', 'category': category}
    bot.edit_message_text(text, call.message.chat.id, call.message.message_id, reply_markup=get_cancel_kb())

def smart_auto_reply(text):
    text_lower = text.lower()
    if "як грати" in text_lower or "как играть" in text_lower:
        return "🤖 <b>Авто-ответ:</b> Инструкцию по игре вы можете найти в нашем главном канале или закрепе группы."
    if "скачать" in text_lower or "завантажити" in text_lower:
        return "🤖 <b>Авто-ответ:</b> Все официальные ссылки на скачивание находятся в описании нашего профиля."
    return None

# === ОБРОБКА ВВОДУ (ТІКЕТИ ТА РОЗСИЛКА) ===
@bot.message_handler(func=lambda message: message.chat.id in user_states, content_types=['text', 'photo', 'video', 'document'])
def handle_user_input(message):
    user_data = user_states.pop(message.chat.id)
    state = user_data.get('state')
    
    # --- РОЗСИЛКА ВІД ВЛАСНИКІВ ---
    if state == 'waiting_broadcast':
        users = load_users()
        success_count = 0
        bot.send_message(message.chat.id, "⏳ Начинаю рассылку...")
        for uid in users:
            try:
                bot.copy_message(uid, message.chat.id, message.message_id)
                success_count += 1
            except Exception:
                pass # Користувач заблокував бота
        bot.send_message(message.chat.id, f"✅ Рассылка завершена!\nДоставлено: {success_count} пользователям.", reply_markup=get_admin_kb())
        return

    # --- ЗВИЧАЙНІ ТІКЕТИ ---
    username = f"@{message.from_user.username}" if message.from_user.username else "Анонимный"
    user_id = message.chat.id
    category = user_data['category']
    
    if message.text:
        auto_reply = smart_auto_reply(message.text)
        if auto_reply:
            bot.send_message(message.chat.id, auto_reply)

    header = f"📌 <b>{category}</b>\n👤 От: {username}\n🔑 ID: <code>{user_id}</code>\n━━━━━━━━━━━━━━━━━━"
    
    # Функція для відправки повідомлення усім цільовим чатам (Група + ЛС Власників)
    targets = set(OWNERS)
    if ADMIN_GROUP_ID:
        targets.add(str(ADMIN_GROUP_ID))
        
    for target in targets:
        try:
            if message.content_type == 'text':
                safe_text = message.text.replace('<', '&lt;').replace('>', '&gt;')
                bot.send_message(target, f"{header}\n{safe_text}")
            else:
                bot.send_message(target, header)
                bot.copy_message(target, message.chat.id, message.message_id)
        except Exception as e:
            print(f"Помилка відправки тікета в {target}: {e}")

    bot.send_message(message.chat.id, "✅ Ваше обращение успешно отправлено руководству.", reply_markup=get_start_kb())


# === ВІДПОВІДІ КЕРІВНИЦТВА (REPLY) ===
# Працює і в групі адмінів, і в ЛС власників
@bot.message_handler(func=lambda message: (str(message.chat.id) == str(ADMIN_GROUP_ID) or message.chat.id in OWNERS) and message.reply_to_message is not None)
def handle_admin_reply(message):
    if message.reply_to_message.from_user.id != bot.get_me().id:
        return

    bot_text = message.reply_to_message.text or message.reply_to_message.caption or ""
    match = re.search(r"ID:\s*(\d+)", bot_text)
    
    if match:
        target_user_id = int(match.group(1))
        safe_reply = message.text.replace('<', '&lt;').replace('>', '&gt;')
        official_reply = f"🛡 <b>Ответ руководства DragPolit:</b>\n\n<i>{safe_reply}</i>"
        
        try:
            bot.send_message(target_user_id, official_reply)
            bot.reply_to(message, "✅ Ответ успешно доставлен пользователю.")
        except Exception as e:
            bot.reply_to(message, "⚠️ Ошибка доставки (возможно, пользователь заблокировал бота).")
    else:
        bot.reply_to(message, "❌ Не удалось найти ID пользователя. Отвечайте (Reply) именно на сообщение с заголовком.")

# === РАБОТА СЕРВЕРА ===
app = Flask(__name__)

@app.route('/')
def keep_alive():
    return "DragPolit Support Engine is Active."

def run_web_server():
    port = int(os.environ.get("PORT", 10000))
    app.run(host="0.0.0.0", port=port)

def start_bot():
    while True:
        try:
            bot.remove_webhook()
            print("Бот підтримки підключений...")
            bot.infinity_polling(timeout=10, long_polling_timeout=5, none_stop=True)
        except Exception as e:
            print(f"Збій API: {e}. Перезапуск через 10 секунд...")
            time.sleep(10)

if __name__ == '__main__':
    threading.Thread(target=run_web_server, daemon=True).start()
    start_bot()
