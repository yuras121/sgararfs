import os
import time
import threading
import re
import telebot
from telebot import types
from flask import Flask

# === НАЛАШТУВАННЯ ===
# Рекомендую у продакшені прибрати другий аргумент і залишити лише os.environ.get('TOKEN')
TOKEN = os.environ.get('8252581199:AAHNfedYh1MrQVNBrL6mYf6OJVoTim_dApM', '8252581199:AAHNfedYh1MrQVNBrL6mYf6OJVoTim_dApM')

# ЗАМІНИ ЦЕ НА ID ВАШОЇ АДМІНСЬКОЇ ГРУПИ (починається з мінуса, наприклад -1001234567890)
# Додайте бота в цю групу і дайте йому права адміністратора!
ADMIN_GROUP_ID = -1614259542 

bot = telebot.TeleBot(TOKEN, parse_mode='HTML')

# Пам'ять станів (тимчасова, очищається при /start)
user_states = {}

# === КОРИСТУВАЦЬКИЙ ІНТЕРФЕЙС ===
def get_start_kb():
    markup = types.InlineKeyboardMarkup(row_width=1)
    markup.add(
        types.InlineKeyboardButton("🚨 Экстренная связь / ЧП", callback_data="type_urgent"),
        types.InlineKeyboardButton("🤝 Предложения и сотрудничество", callback_data="type_collab"),
        types.InlineKeyboardButton("🐛 Сообщить о баге", callback_data="type_bug")
    )
    return markup

def get_cancel_kb():
    markup = types.InlineKeyboardMarkup()
    markup.add(types.InlineKeyboardButton("❌ Отменить", callback_data="cancel_action"))
    return markup

@bot.message_handler(commands=['start'])
def start_command(message):
    # Очищаємо стан користувача, якщо він вирішив почати спочатку (запобігає витоку пам'яті)
    user_states.pop(message.chat.id, None)
    
    text = (
        "<b>Официальная служба поддержки DragPolit</b>\n\n"
        "Выберите необходимый раздел меню. Обратите внимание, что спам и ложные вызовы могут привести к блокировке."
    )
    bot.send_message(message.chat.id, text, reply_markup=get_start_kb())

@bot.callback_query_handler(func=lambda call: call.data == 'cancel_action')
def cancel_action(call):
    user_states.pop(call.message.chat.id, None)
    bot.edit_message_text("Действие отменено. Возврат в главное меню.", call.message.chat.id, call.message.message_id, reply_markup=get_start_kb())

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
        
    user_states[call.message.chat.id] = {'state': 'waiting_ticket', 'category': category}
    bot.edit_message_text(text, call.message.chat.id, call.message.message_id, reply_markup=get_cancel_kb())

# === ІНТЕЛЕКТ БОТА (АВТО-ВІДПОВІДІ) ===
def smart_auto_reply(text):
    text_lower = text.lower()
    if "як грати" in text_lower or "как играть" in text_lower:
        return "🤖 <b>Авто-ответ:</b> Инструкцию по игре вы можете найти в нашем главном канале или закрепе группы."
    if "скачать" in text_lower or "завантажити" in text_lower:
        return "🤖 <b>Авто-ответ:</b> Все официальные ссылки на скачивание находятся в описании нашего профиля."
    return None

# === ОБРОБКА ПОВІДОМЛЕНЬ ВІД ГРАВЦІВ ===
@bot.message_handler(func=lambda message: message.chat.id in user_states, content_types=['text', 'photo', 'video', 'document'])
def handle_user_input(message):
    user_data = user_states.pop(message.chat.id)
    username = f"@{message.from_user.username}" if message.from_user.username else "Анонимный"
    user_id = message.chat.id
    category = user_data['category']
    
    # Авто-відповіді для тексту
    if message.text:
        auto_reply = smart_auto_reply(message.text)
        if auto_reply:
            bot.send_message(message.chat.id, auto_reply)
            # Якщо хочете, щоб після авто-відповіді тікет не створювався, розкоментуйте рядок нижче:
            # return bot.send_message(message.chat.id, "Возврат в меню.", reply_markup=get_start_kb())

    # Формуємо заголовок для адмінів з прихованим ID (щоб бот знав, куди відповідати)
    header = f"📌 <b>{category}</b>\n👤 От: {username}\n🔑 ID: <code>{user_id}</code>\n━━━━━━━━━━━━━━━━━━"
    
    try:
        if message.content_type == 'text':
            safe_text = message.text.replace('<', '&lt;').replace('>', '&gt;')
            bot.send_message(ADMIN_GROUP_ID, f"{header}\n{safe_text}")
        else:
            # Якщо це медіа, відправляємо заголовок, а потім копіюємо сам файл
            bot.send_message(ADMIN_GROUP_ID, header)
            bot.copy_message(ADMIN_GROUP_ID, message.chat.id, message.message_id)
            
        bot.send_message(message.chat.id, "✅ Ваше обращение успешно отправлено руководству.", reply_markup=get_start_kb())
    except Exception as e:
        bot.send_message(message.chat.id, "⚠️ Произошла ошибка при отправке. Попробуйте позже.")
        print(f"Помилка відправки в адмін-групу: {e}")

# === АДМІН-ПАНЕЛЬ (ВІДПОВІДІ ЧЕРЕЗ REPLY В ГРУПІ) ===
# Цей блок ловить повідомлення в адмінській групі, які є ВІДПОВІДДЮ (Reply) на повідомлення бота
@bot.message_handler(func=lambda message: str(message.chat.id) == str(ADMIN_GROUP_ID) and message.reply_to_message is not None)
def handle_admin_reply(message):
    # Перевіряємо, чи адмін відповів саме на повідомлення бота
    if message.reply_to_message.from_user.id != bot.get_me().id:
        return

    # Шукаємо ID користувача у повідомленні бота, на яке відповідають
    bot_text = message.reply_to_message.text or message.reply_to_message.caption or ""
    
    # Регулярний вираз для пошуку "ID: 12345678"
    match = re.search(r"ID:\s*(\d+)", bot_text)
    
    if match:
        target_user_id = int(match.group(1))
        safe_reply = message.text.replace('<', '&lt;').replace('>', '&gt;')
        official_reply = f"🛡 <b>Ответ руководства DragPolit:</b>\n\n<i>{safe_reply}</i>"
        
        try:
            bot.send_message(target_user_id, official_reply)
            bot.reply_to(message, "✅ Ответ успешно доставлен пользователю.")
        except Exception as e:
            bot.reply_to(message, f"⚠️ Ошибка доставки (возможно, пользователь заблокировал бота).")
    else:
        bot.reply_to(message, "❌ Не удалось найти ID пользователя. Убедитесь, что вы отвечаете на сообщение с заголовком (где указан ID).")

# === RENDER KEEP-ALIVE ТА БЕЗПЕРЕБІЙНИЙ ЗАПУСК ===
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
            print("Бот підтримки підключений до Telegram...")
            # none_stop=True робить роботу стабільнішою
            bot.infinity_polling(timeout=10, long_polling_timeout=5, none_stop=True)
        except Exception as e:
            print(f"Збій з'єднання з Telegram API: {e}. Перезапуск через 10 секунд...")
            time.sleep(10)


@bot.message_handler(commands=['get_id'])
def get_id_command(message):
    bot.reply_to(message, f"ID цього чату: <code>{message.chat.id}</code>")



if __name__ == '__main__':
    threading.Thread(target=run_web_server).start()
    start_bot()
