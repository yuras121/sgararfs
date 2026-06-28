import os
import json
import threading
import telebot
from telebot import types
from flask import Flask

# === НАЛАШТУВАННЯ ===
TOKEN = os.environ.get('8252581199:AAHNfedYh1MrQVNBrL6mYf6OJVoTim_dApM', '8252581199:AAHNfedYh1MrQVNBrL6mYf6OJVoTim_dApM')
BUG_CHANNEL_ID = -1000000000000 # Заміни на ID вашого каналу

# Головні адміністратори (юзернейми без @, обов'язково маленькими літерами)
ADMIN_USERNAMES = ['p1vi_k', 'dragwayder']

bot = telebot.TeleBot(TOKEN, parse_mode='HTML')

# === СИСТЕМА ЗБЕРЕЖЕННЯ (БАЗА ДАНИХ) ===
DATA_FILE = 'tickets.json'

def load_data():
    if os.path.exists(DATA_FILE):
        with open(DATA_FILE, 'r', encoding='utf-8') as f:
            return json.load(f)
    return []

def save_data():
    with open(DATA_FILE, 'w', encoding='utf-8') as f:
        json.dump(tickets, f, ensure_ascii=False, indent=4)

tickets = load_data()
user_states = {}
admin_view_index = {}

# === КОРИСТУВАЦЬКИЙ ІНТЕРФЕЙС ===

def get_start_kb():
    markup = types.InlineKeyboardMarkup(row_width=1)
    markup.add(
        types.InlineKeyboardButton("🚨 Экстренная связь / ЧП", callback_data="type_urgent"),
        types.InlineKeyboardButton("🤝 Предложения и сотрудничество", callback_data="type_collab"),
        types.InlineKeyboardButton("🐛 Сообщить о баге (в канал)", callback_data="type_bug"),
        types.InlineKeyboardButton("📋 Мои обращения", callback_data="my_tickets")
    )
    return markup

def get_cancel_kb():
    markup = types.InlineKeyboardMarkup()
    markup.add(types.InlineKeyboardButton("❌ Отменить", callback_data="cancel_action"))
    return markup

@bot.message_handler(commands=['start'])
def start_command(message):
    text = (
        "<b>Официальная служба поддержки DragPolit</b>\n\n"
        "Выберите необходимый раздел меню. Обратите внимание, что спам и ложные вызовы могут привести к блокировке."
    )
    bot.send_message(message.chat.id, text, reply_markup=get_start_kb())
    user_states.pop(message.chat.id, None)

@bot.message_handler(commands=['me'])
def debug_command(message):
    username = message.from_user.username
    status = "✅ Главный Администратор" if username and username.lower() in ADMIN_USERNAMES else "👤 Пользователь"
    text = (
        f"🖥 <b>Системная диагностика:</b>\n\n"
        f"<b>ID:</b> <code>{message.chat.id}</code>\n"
        f"<b>Username:</b> @{username}\n"
        f"<b>Статус доступа:</b> {status}"
    )
    bot.send_message(message.chat.id, text)

@bot.callback_query_handler(func=lambda call: call.data == 'cancel_action')
def cancel_action(call):
    user_states.pop(call.message.chat.id, None)
    bot.edit_message_text("Действие отменено. Возврат в главное меню.", call.message.chat.id, call.message.message_id, reply_markup=get_start_kb())

@bot.callback_query_handler(func=lambda call: call.data == 'my_tickets')
def show_my_tickets(call):
    my_t = [t for t in tickets if t['user_id'] == call.message.chat.id]
    if not my_t:
        bot.answer_callback_query(call.id, "У вас пока нет обращений.", show_alert=True)
        return
    
    text = "📋 <b>Ваши последние обращения:</b>\n\n"
    for t in my_t[-5:]: # Показуємо останні 5
        status_icon = "🟢" if t['status'] == 'Открыт' else "🔴"
        text += f"{status_icon} <b>№{t['id']}</b> ({t['category']}) — {t['status']}\n"
    
    markup = types.InlineKeyboardMarkup().add(types.InlineKeyboardButton("🔙 Назад", callback_data="back_to_main"))
    bot.edit_message_text(text, call.message.chat.id, call.message.message_id, reply_markup=markup)

@bot.callback_query_handler(func=lambda call: call.data == 'back_to_main')
def back_main(call):
    text = "<b>Официальная служба поддержки DragPolit</b>\n\nВыберите необходимый раздел меню."
    bot.edit_message_text(text, call.message.chat.id, call.message.message_id, reply_markup=get_start_kb())

@bot.callback_query_handler(func=lambda call: call.data.startswith('type_'))
def handle_main_menu(call):
    action = call.data.split('_')[1]
    
    if action == 'bug':
        text = "🛠 <b>Баг-репорт</b>\nОпишите проблему одним сообщением:\n1. Что сломалось?\n2. Где?\n3. Как повторить?\n\n<i>Отправляется напрямую в тех. отдел.</i>"
        user_states[call.message.chat.id] = {'state': 'waiting_bug'}
    elif action == 'urgent':
        text = "🚨 <b>Экстренная связь (ЧП)</b>\nПодробно опишите проблему. Руководство рассмотрит ее вне очереди."
        user_states[call.message.chat.id] = {'state': 'waiting_ticket', 'category': 'ЧП / Срочно'}
    elif action == 'collab':
        text = "🤝 <b>Сотрудничество</b>\nОпишите ваше коммерческое предложение или идею."
        user_states[call.message.chat.id] = {'state': 'waiting_ticket', 'category': 'Сотрудничество'}
        
    bot.edit_message_text(text, call.message.chat.id, call.message.message_id, reply_markup=get_cancel_kb())

@bot.message_handler(func=lambda message: message.chat.id in user_states, content_types=['text', 'photo', 'video', 'document'])
def handle_user_input(message):
    user_data = user_states.pop(message.chat.id)
    username = f"@{message.from_user.username}" if message.from_user.username else "Анонимный"
    
    if user_data['state'] == 'waiting_bug':
        bot.send_message(BUG_CHANNEL_ID, f"⚠️ <b>Новый баг-репорт от {username}</b> (ID: <code>{message.chat.id}</code>):\n")
        bot.copy_message(BUG_CHANNEL_ID, message.chat.id, message.message_id)
        bot.send_message(message.chat.id, "✅ Баг-репорт отправлен разработчикам.", reply_markup=get_start_kb())
        
    elif user_data['state'] == 'waiting_ticket':
        ticket_id = len(tickets) + 1
        ticket_text = message.text if message.text else (message.caption if message.caption else "[Медиафайл]")
        
        new_ticket = {
            'id': ticket_id,
            'user_id': message.chat.id,
            'username': username,
            'category': user_data['category'],
            'text': ticket_text,
            'status': 'Открыт'
        }
        tickets.append(new_ticket)
        save_data() # Зберігаємо в JSON
        bot.send_message(message.chat.id, f"✅ Обращение <b>№{ticket_id}</b> зарегистрировано.", reply_markup=get_start_kb())

# === АДМІН-ПАНЕЛЬ ===

def is_admin(username):
    return username and username.lower() in ADMIN_USERNAMES

def get_admin_ticket_kb(ticket_id, current_index, total_tickets):
    markup = types.InlineKeyboardMarkup(row_width=3)
    markup.add(
        types.InlineKeyboardButton("⬅️", callback_data=f"nav_prev_{current_index}"),
        types.InlineKeyboardButton(f"{current_index + 1} / {total_tickets}", callback_data="ignore"),
        types.InlineKeyboardButton("➡️", callback_data=f"nav_next_{current_index}")
    )
    markup.add(
        types.InlineKeyboardButton("💬 Ответить", callback_data=f"admin_reply_{ticket_id}"),
        types.InlineKeyboardButton("❌ Закрыть (Решено)", callback_data=f"admin_close_{ticket_id}")
    )
    return markup

@bot.message_handler(commands=['admin'])
def admin_panel(message):
    if not is_admin(message.from_user.username):
        return bot.send_message(message.chat.id, "⛔ Доступ запрещен.")
        
    open_tickets = [t for t in tickets if t['status'] == 'Открыт']
    if not open_tickets:
        return bot.send_message(message.chat.id, "📭 Актуальных обращений нет.")
        
    send_ticket_view(message.chat.id, 0, open_tickets)

def send_ticket_view(chat_id, index, open_tickets, message_id=None):
    index = index % len(open_tickets) # Безкінечна прокрутка
    ticket = open_tickets[index]
    emoji = "🚨" if ticket['category'] == 'ЧП / Срочно' else "🤝"
    
    text = (
        f"{emoji} <b>Тикет №{ticket['id']}</b> | {ticket['category']}\n"
        f"👤 От: {ticket['username']} (<code>{ticket['user_id']}</code>)\n"
        f"━━━━━━━━━━━━━━━━━━\n"
        f"{ticket['text']}\n"
        f"━━━━━━━━━━━━━━━━━━"
    )
    kb = get_admin_ticket_kb(ticket['id'], index, len(open_tickets))
    
    if message_id:
        try: bot.edit_message_text(text, chat_id, message_id, reply_markup=kb)
        except: pass
    else:
        bot.send_message(chat_id, text, reply_markup=kb)

@bot.callback_query_handler(func=lambda call: call.data.startswith('nav_'))
def handle_pagination(call):
    if not is_admin(call.from_user.username): return bot.answer_callback_query(call.id, "⛔ Отказано", show_alert=True)
    
    open_tickets = [t for t in tickets if t['status'] == 'Открыт']
    if not open_tickets: return bot.edit_message_text("📭 Все обращения закрыты.", call.message.chat.id, call.message.message_id)

    action, index_str = call.data.replace('nav_', '').split('_')
    new_index = int(index_str) + 1 if action == 'next' else int(index_str) - 1
    send_ticket_view(call.message.chat.id, new_index, open_tickets, call.message.message_id)
    bot.answer_callback_query(call.id)

@bot.callback_query_handler(func=lambda call: call.data.startswith('admin_close_'))
def handle_close_ticket(call):
    if not is_admin(call.from_user.username): return
    
    ticket_id = int(call.data.split('_')[2])
    for t in tickets:
        if t['id'] == ticket_id:
            t['status'] = 'Закрыт'
            save_data()
            try: bot.send_message(t['user_id'], f"🔔 Ваш тикет <b>№{ticket_id}</b> закрыт руководством.")
            except: pass
            break
            
    bot.answer_callback_query(call.id, "Тикет закрыт!")
    
    open_tickets = [t for t in tickets if t['status'] == 'Открыт']
    if open_tickets: send_ticket_view(call.message.chat.id, 0, open_tickets, call.message.message_id)
    else: bot.edit_message_text("📭 Все обращения обработаны.", call.message.chat.id, call.message.message_id)

@bot.callback_query_handler(func=lambda call: call.data.startswith('admin_reply_'))
def handle_reply_ticket(call):
    if not is_admin(call.from_user.username): return
    
    ticket_id = int(call.data.split('_')[2])
    user_id = next((t['user_id'] for t in tickets if t['id'] == ticket_id), None)
    
    msg = bot.send_message(call.message.chat.id, f"✍️ Напишите ответ (Тикет №{ticket_id}):", reply_markup=get_cancel_kb())
    user_states[call.message.chat.id] = {'state': 'writing_reply', 'user_id': user_id, 'ticket_id': ticket_id, 'msg_id': msg.message_id}
    bot.answer_callback_query(call.id)

@bot.message_handler(func=lambda message: message.chat.id in user_states and user_states[message.chat.id].get('state') == 'writing_reply')
def send_admin_reply(message):
    state_data = user_states.pop(message.chat.id)
    
    # Видаляємо кнопку скасування попереднього повідомлення для краси
    try: bot.edit_message_reply_markup(message.chat.id, state_data['msg_id'], reply_markup=None)
    except: pass

    official_reply = (
        f"🛡 <b>Ответ руководства DragPolit</b>\n"
        f"По обращению №{state_data['ticket_id']}:\n\n"
        f"<i>{message.text}</i>"
    )
    
    try:
        bot.send_message(state_data['user_id'], official_reply)
        bot.send_message(message.chat.id, "✅ Ответ отправлен. Введите /admin")
    except:
        bot.send_message(message.chat.id, "⚠️ Ошибка. Пользователь заблокировал бота.")

# === РЕНДЕР СЕРВЕР ТА ЗАПУСК ===
app = Flask(__name__)

@app.route('/')
def keep_alive():
    return "DragPolit System Core Active."

def run_web_server():
    port = int(os.environ.get("PORT", 10000))
    app.run(host="0.0.0.0", port=port)

if __name__ == '__main__':
    threading.Thread(target=run_web_server).start()
    bot.remove_webhook()
    print("DragPolit Bot Online...")
    bot.infinity_polling()
