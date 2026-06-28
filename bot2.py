import os
import threading
import telebot
from telebot import types
from flask import Flask

# === НАСТРОЙКИ ===
# Замените токен на ваш собственный из @BotFather или используйте переменные окружения
TOKEN = os.environ.get('BOT_TOKEN', '8252581199:AAHNfedYh1MrQVNBrL6mYf6OJVoTim_dApM')
BUG_CHANNEL_ID = -1000000000000  # ID канала для багов (обязательно должен начинаться с -100)

# ТОЛЬКО ДВА МОДЕРАТОРА с полным доступом к админ-панели
ADMIN_USERNAMES = ['p1vi_k', 'dragwayder']

bot = telebot.TeleBot(TOKEN)

# База данных в оперативной памяти (для хранения активных тикетов)
tickets = [] 
user_states = {}
admin_view_index = {}

# === ГОЛОВНОЕ МЕНЮ (ДЛЯ ПОЛЬЗОВАТЕЛЕЙ) ===

def get_start_kb():
    markup = types.InlineKeyboardMarkup(row_width=1)
    btn_urgent = types.InlineKeyboardButton("🚨 Экстренная связь / ЧП", callback_data="type_urgent")
    btn_collab = types.InlineKeyboardButton("🤝 Предложения и сотрудничество", callback_data="type_collab")
    btn_bug = types.InlineKeyboardButton("🐛 Сообщить о баге (в канал)", callback_data="type_bug")
    markup.add(btn_urgent, btn_collab, btn_bug)
    return markup

@bot.message_handler(commands=['start'])
def start_command(message):
    text = (
        "Здравствуйте! Вы обратились в официальную службу поддержки **DragPolit**.\n\n"
        "Пожалуйста, выберите нужный раздел меню. Обратите внимание, что ложные вызовы по экстренным каналам связи могут привести к блокировке."
    )
    bot.send_message(message.chat.id, text, reply_markup=get_start_kb(), parse_mode='Markdown')
    if message.chat.id in user_states:
        del user_states[message.chat.id]

@bot.callback_query_handler(func=lambda call: call.data.startswith('type_'))
def handle_main_menu(call):
    action = call.data.split('_')[1]
    
    if action == 'bug':
        text = (
            "🛠 **Сообщение об ошибке (Баг-репорт)**\n\n"
            "Чтобы технический отдел смог быстро решить проблему, пожалуйста, напишите **одно сообщение** по следующему шаблону:\n\n"
            "1️⃣ **Суть проблемы:** (Кратко, что именно сломалось)\n"
            "2️⃣ **Где произошла ошибка:** (В боте, в игре, в чате)\n"
            "3️⃣ **Как повторить:** (Какие кнопки вы нажали до появления ошибки)\n\n"
            "_Вы также можете прикрепить скриншот или видео к этому сообщению._\n"
            "Ваша информация будет напрямую перенаправлена разработчикам в технический канал."
        )
        bot.send_message(call.message.chat.id, text, parse_mode='Markdown')
        user_states[call.message.chat.id] = {'state': 'waiting_bug'}
        
    elif action == 'urgent':
        text = "🚨 **Экстренная связь (ЧП)**\n\nПожалуйста, опишите вашу проблему максимально подробно в следующем сообщении. Руководство рассмотрит это обращение в приоритетном порядке."
        bot.send_message(call.message.chat.id, text, parse_mode='Markdown')
        user_states[call.message.chat.id] = {'state': 'waiting_ticket', 'category': 'ЧП / Срочно'}
        
    elif action == 'collab':
        text = "🤝 **Предложения и сотрудничество**\n\nОпишите вашу идею или коммерческое предложение в следующем сообщении. Мы открыты к диалогу и конструктивным предложениям."
        bot.send_message(call.message.chat.id, text, parse_mode='Markdown')
        user_states[call.message.chat.id] = {'state': 'waiting_ticket', 'category': 'Сотрудничество'}
        
    bot.answer_callback_query(call.id)

# === ОБРАБОТКА ВХОДЯЩИХ СООБЩЕНИЙ ОТ ПОЛЬЗОВАТЕЛЕЙ ===

@bot.message_handler(func=lambda message: message.chat.id in user_states, content_types=['text', 'photo', 'video', 'document'])
def handle_user_input(message):
    user_data = user_states.pop(message.chat.id)
    username = f"@{message.from_user.username}" if message.from_user.username else "Анонимный пользователь"
    
    if user_data['state'] == 'waiting_bug':
        # Отправляем напрямую в технический канал, тикет в панели не создаем
        bot.send_message(BUG_CHANNEL_ID, f"⚠️ **Новый баг-репорт от {username}** (ID: `{message.chat.id}`):\n", parse_mode='Markdown')
        bot.copy_message(BUG_CHANNEL_ID, message.chat.id, message.message_id)
        
        bot.send_message(message.chat.id, "✅ Ваш баг-репорт успешно отправлен в технический канал. Спасибо за помощь в улучшении проекта!", reply_markup=get_start_kb())
        
    elif user_data['state'] == 'waiting_ticket':
        # Создаем тикет для ЧП или Сотрудничества
        ticket_id = len(tickets) + 1
        
        # Захватываем текст сообщения или описание к медиафайлу
        ticket_text = message.text if message.text else (message.caption if message.caption else "[Медиафайл без текста]")
        
        new_ticket = {
            'id': ticket_id,
            'user_id': message.chat.id,
            'username': username,
            'category': user_data['category'],
            'text': ticket_text,
            'status': 'Открыт'
        }

        tickets.append(new_ticket)
        bot.send_message(message.chat.id, f"✅ Ваше обращение №{ticket_id} зарегистрировано. Ожидайте официального ответа от руководства.", reply_markup=get_start_kb())

# === ЗАКРЫТАЯ АДМИН-ПАНЕЛЬ (УПРАВЛЕНИЕ КНОПКАМИ СЛОВАМИ ТУДА-СЮДА) ===

def get_admin_ticket_kb(ticket_id, current_index, total_tickets):
    markup = types.InlineKeyboardMarkup(row_width=3)
    btn_prev = types.InlineKeyboardButton("⬅️ Назад", callback_data=f"nav_prev_{current_index}")
    btn_count = types.InlineKeyboardButton(f"{current_index + 1} / {total_tickets}", callback_data="ignore")
    btn_next = types.InlineKeyboardButton("Вперед ➡️", callback_data=f"nav_next_{current_index}")
    btn_reply = types.InlineKeyboardButton("💬 Ответить", callback_data=f"admin_reply_{ticket_id}")
    btn_close = types.InlineKeyboardButton("❌ Решено (Закрыть)", callback_data=f"admin_close_{ticket_id}")
    markup.add(btn_prev, btn_count, btn_next)
    markup.add(btn_reply)
    markup.add(btn_close)
    return markup

@bot.message_handler(commands=['admin'])
def admin_panel(message):
    if message.from_user.username not in ADMIN_USERNAMES:
        bot.send_message(message.chat.id, "⛔ Доступ запрещен. Вы не являетесь главным администратором.")
        return
        
    open_tickets = [t for t in tickets if t['status'] == 'Открыт']
    if not open_tickets:
        bot.send_message(message.chat.id, "📭 Актуальных обращений (ЧП/Сотрудничество) на данный момент нет.")
        return
        
    admin_view_index[message.chat.id] = 0
    send_ticket_view(message.chat.id, 0, open_tickets)

def send_ticket_view(chat_id, index, open_tickets, message_id=None):
    if index >= len(open_tickets):
        index = 0
    elif index < 0:
        index = len(open_tickets) - 1
        
    ticket = open_tickets[index]
    emoji = "🚨" if ticket['category'] == 'ЧП / Срочно' else "🤝"
    
    text = (
        f"{emoji} **Тикет №{ticket['id']}** | {ticket['category']}\n"
        f"👤 От: {ticket['username']} (ID: `{ticket['user_id']}`)\n"
        f"━━━━━━━━━━━━━━━━━━\n"
        f"{ticket['text']}\n"
        f"━━━━━━━━━━━━━━━━━━"
    )
    kb = get_admin_ticket_kb(ticket['id'], index, len(open_tickets))
    
    if message_id:
        try:
            bot.edit_message_text(text, chat_id, message_id, reply_markup=kb, parse_mode='Markdown')
        except Exception:
            # На случай, если текст сообщения не изменился, чтобы избежать ошибки Telegram API
            pass
    else:
        bot.send_message(chat_id, text, reply_markup=kb, parse_mode='Markdown')

@bot.callback_query_handler(func=lambda call: call.data.startswith('nav_') or call.data == 'ignore')
def handle_pagination(call):
    if call.data == 'ignore':
        bot.answer_callback_query(call.id)
        return
        
    if call.from_user.username not in ADMIN_USERNAMES:
        bot.answer_callback_query(call.id, "⛔ У вас нет доступа к управлению.", show_alert=True)
        return
        
    open_tickets = [t for t in tickets if t['status'] == 'Открыт']
    if not open_tickets:
        bot.edit_message_text("📭 Все обращения успешно закрыты.", call.message.chat.id, call.message.message_id)
        bot.answer_callback_query(call.id)
        return

    action, index_str = call.data.replace('nav_', '').split('_')
    current_index = int(index_str)
    
    if action == 'next':
        new_index = (current_index + 1) % len(open_tickets)
    else:
        new_index = (current_index - 1) % len(open_tickets)
        
    admin_view_index[call.message.chat.id] = new_index
    send_ticket_view(call.message.chat.id, new_index, open_tickets, call.message.message_id)
    bot.answer_callback_query(call.id)

@bot.callback_query_handler(func=lambda call: call.data.startswith('admin_close_'))
def handle_close_ticket(call):
    if call.from_user.username not in ADMIN_USERNAMES:
        return bot.answer_callback_query(call.id)
        
    ticket_id = int(call.data.split('_')[2])
    for t in tickets:
        if t['id'] == ticket_id:
            t['status'] = 'Закрыт'
            try:
                bot.send_message(t['user_id'], f"🔔 Вопрос по вашему обращению №{ticket_id} был успешно решен руководством. Спасибо за обратную связь!")
            except Exception:
                pass
            break
            
    bot.answer_callback_query(call.id, "Обращение закрыто!")
    
    open_tickets = [t for t in tickets if t['status'] == 'Открыт']
    if open_tickets:
        send_ticket_view(call.message.chat.id, 0, open_tickets, call.message.message_id)
    else:
        bot.edit_message_text("📭 Все обращения успешно обработаны и закрыты.", call.message.chat.id, call.message.message_id)

@bot.callback_query_handler(func=lambda call: call.data.startswith('admin_reply_'))
def handle_reply_ticket(call):
    if call.from_user.username not in ADMIN_USERNAMES:
        return bot.answer_callback_query(call.id)
        
    ticket_id = int(call.data.split('_')[2])
    user_id = next((t['user_id'] for t in tickets if t['id'] == ticket_id), None)
            
    if not user_id:
        return bot.answer_callback_query(call.id, "Ошибка: пользователь не найден.")
        
    msg = bot.send_message(call.message.chat.id, f"✍️ Введите текст официального ответа для тикета №{ticket_id}:\n_(Для отмены напишите слово 'отмена')_", parse_mode='Markdown')
    user_states[call.message.chat.id] = {'state': 'writing_reply', 'user_id': user_id, 'ticket_id': ticket_id}
    bot.answer_callback_query(call.id)

@bot.message_handler(func=lambda message: message.chat.id in user_states and user_states[message.chat.id].get('state') == 'writing_reply')
def send_admin_reply(message):
    state_data = user_states.pop(message.chat.id)
    
    if message.text and message.text.lower() == 'отмена':
        return bot.send_message(message.chat.id, "❌ Отправка ответа отменена. Используйте /admin для возврата в панель управления.")
        
    official_reply = (
        f"🛡 **Официальный ответ руководства DragPolit**\n"
        f"По вашему обращению №{state_data['ticket_id']}:\n\n"
        f"_{message.text}_"
    )
    
    try:
        bot.send_message(state_data['user_id'], official_reply, parse_mode='Markdown')
        bot.send_message(message.chat.id, "✅ Официальный ответ успешно отправлен пользователю! Введите /admin для продолжения работы.")
    except Exception:
        bot.send_message(message.chat.id, "⚠️ Ошибка отправки. Возможно, пользователь заблокировал бота или остановил его.")

# === ФИКТИВНЫЙ ВЕБ-СЕРВЕР ДЛЯ ХОСТИНГА (RENDER KEEP-ALIVE) ===
app = Flask(__name__)

@app.route('/')
def keep_alive():
    return "DragPolit Support Bot is fully operational and running!"

def run_web_server():
    # Render автоматически подставляет порт в переменную PORT
    port = int(os.environ.get("PORT", 10000))
    app.run(host="0.0.0.0", port=port)

if __name__ == '__main__':
    # Запуск веб-сервера в отдельном потоке, чтобы Render не отключал бота
    print("Инициализация веб-сервера для платформы Render...")
    threading.Thread(target=run_web_server).start()
    
    # Запуск основного процесса бота
    print("Официальный бот поддержки DragPolit успешно запущен...")
    bot.infinity_polling()
