import telebot
from telebot import types

# === НАЛАШТУВАННЯ ===
TOKEN = 'ТВІЙ_ТОКЕН_ВІД_BOTFATHER'
BUG_CHANNEL_ID = -1000000000000 # ID каналу для багів (обов'язково починається з -100)

# ТІЛЬКИ ДВА МОДЕРАТОРИ (повний доступ)
ADMIN_USERNAMES = ['p1vi_k', 'dragwayder']

bot = telebot.TeleBot(TOKEN)

# База даних у пам'яті
tickets = [] 
user_states = {}
admin_view_index = {}

# === ГОЛОВНЕ МЕНЮ ===

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
        # Інструкція, ЯК ПИСАТИ ПОСТ ПРО БАГ
        text = (
            "🛠 **Сообщение об ошибке (Баг-репорт)**\n\n"
            "Чтобы технический отдел смог быстро решить проблему, пожалуйста, напишите **одно сообщение** по следующему шаблону:\n\n"
            "1️⃣ **Суть проблемы:** (Кратко, что именно сломалось)\n"
            "2️⃣ **Где произошла ошибка:** (В боте, в игре, в чате)\n"
            "3️⃣ **Как повторить:** (Какие кнопки вы нажали до появления ошибки)\n\n"
            "_Можете прикрепить фото или видео к тексту._\n"
            "Ваше сообщение будет напрямую отправлено разработчикам в технический канал."
        )
        bot.send_message(call.message.chat.id, text, parse_mode='Markdown')
        user_states[call.message.chat.id] = {'state': 'waiting_bug'}
        
    elif action == 'urgent':
        text = "🚨 **Экстренная связь (ЧП)**\n\nОпишите вашу проблему максимально подробно. Руководство рассмотрит это обращение в первую очередь."
        bot.send_message(call.message.chat.id, text, parse_mode='Markdown')
        user_states[call.message.chat.id] = {'state': 'waiting_ticket', 'category': 'ЧП / Срочно'}
        
    elif action == 'collab':
        text = "🤝 **Предложения и сотрудничество**\n\nНапишите вашу идею или коммерческое предложение. Мы открыты к диалогу."
        bot.send_message(call.message.chat.id, text, parse_mode='Markdown')
        user_states[call.message.chat.id] = {'state': 'waiting_ticket', 'category': 'Сотрудничество'}
        
    bot.answer_callback_query(call.id)

# === ОБРОБКА ПОВІДОМЛЕНЬ ВІД КОРИСТУВАЧА ===

@bot.message_handler(func=lambda message: message.chat.id in user_states, content_types=['text', 'photo', 'video', 'document'])
def handle_user_input(message):
    user_data = user_states.pop(message.chat.id)
    username = f"@{message.from_user.username}" if message.from_user.username else "Анонимный пользователь"
    
    if user_data['state'] == 'waiting_bug':
        # Відправляємо напряму в канал, тикет НЕ створюємо
        bot.send_message(BUG_CHANNEL_ID, f"⚠️ **Новый баг-репорт от {username}** (ID: `{message.chat.id}`)\n", parse_mode='Markdown')
        bot.copy_message(BUG_CHANNEL_ID, message.chat.id, message.message_id)
        
        bot.send_message(message.chat.id, "✅ Ваш баг-репорт успешно отправлен в технический отдел. Спасибо за помощь проекту!", reply_markup=get_start_kb())
        
    elif user_data['state'] == 'waiting_ticket':
        # Створюємо тикет для ЧП або Співпраці
        ticket_id = len(tickets) + 1
        new_ticket = {
            'id': ticket_id,
            'user_id': message.chat.id,
            'username': username,
            'category': user_data['category'],
            'text': message.caption if message.caption else message.text, # Якщо надіслали фото з текстом
            'status': 'Открыт'
        }
        
        # Якщо тексту немає (просто фото без підпису)
        if not new_ticket['text']:
            new_ticket['text'] = "[Медиафайл без текста]"

        tickets.append(new_ticket)
        bot.send_message(message.chat.id, f"✅ Ваше обращение (№{ticket_id}) зарегистрировано. Ожидайте ответа руководства.", reply_markup=get_start_kb())

# === ЗАКРИТА АДМІН-ПАНЕЛЬ ===

def get_admin_ticket_kb(ticket_id, current_index, total_tickets):
    markup = types.InlineKeyboardMarkup(row_width=3)
    btn_prev = types.InlineKeyboardButton("⬅️", callback_data=f"nav_prev_{current_index}")
    btn_count = types.InlineKeyboardButton(f"{current_index + 1} / {total_tickets}", callback_data="ignore")
    btn_next = types.InlineKeyboardButton("➡️", callback_data=f"nav_next_{current_index}")
    btn_reply = types.InlineKeyboardButton("💬 Ответить", callback_data=f"admin_reply_{ticket_id}")
    btn_close = types.InlineKeyboardButton("❌ Решено (Закрыть)", callback_data=f"admin_close_{ticket_id}")
    markup.add(btn_prev, btn_count, btn_next)
    markup.add(btn_reply)
    markup.add(btn_close)
    return markup

@bot.message_handler(commands=['admin'])
def admin_panel(message):
    if message.from_user.username not in ADMIN_USERNAMES:
        bot.send_message(message.chat.id, "⛔ Доступ запрещен. Вы не являетесь администратором.")
        return
        
    open_tickets = [t for t in tickets if t['status'] == 'Открыт']
    if not open_tickets:
        bot.send_message(message.chat.id, "📭 Актуальных обращений (ЧП/Сотрудничество) нет.")
        return
        
    admin_view_index[message.chat.id] = 0
    send_ticket_view(message.chat.id, 0, open_tickets)

def send_ticket_view(chat_id, index, open_tickets, message_id=None):
    ticket = open_tickets[index]
    # Додаємо емодзі для статусності
    emoji = "🚨" if ticket['category'] == 'ЧП / Срочно' else "🤝"
    
    text = (
        f"{emoji} **Тикет №{ticket['id']}** | {ticket['category']}\n"
        f"👤 От: {ticket['username']}\n"
        f"━━━━━━━━━━━━━━━━━━\n"
        f"{ticket['text']}\n"
        f"━━━━━━━━━━━━━━━━━━"
    )
    kb = get_admin_ticket_kb(ticket['id'], index, len(open_tickets))
    
    if message_id:
        bot.edit_message_text(text, chat_id, message_id, reply_markup=kb, parse_mode='Markdown')
    else:
        bot.send_message(chat_id, text, reply_markup=kb, parse_mode='Markdown')

@bot.callback_query_handler(func=lambda call: call.data.startswith('nav_') or call.data == 'ignore')
def handle_pagination(call):
    if call.data == 'ignore' or call.from_user.username not in ADMIN_USERNAMES:
        return bot.answer_callback_query(call.id)
        
    open_tickets = [t for t in tickets if t['status'] == 'Открыт']
    if not open_tickets:
        return bot.edit_message_text("📭 Все обращения закрыты.", call.message.chat.id, call.message.message_id)

    action, index_str = call.data.replace('nav_', '').split('_')
    current_index = int(index_str)
    
    if action == 'next':
        new_index = (current_index + 1) % len(open_tickets)
    else:
        new_index = (current_index - 1) % len(open_tickets)
        
    send_ticket_view(call.message.chat.id, new_index, open_tickets, call.message.message_id)
    bot.answer_callback_query(call.id)

@bot.callback_query_handler(func=lambda call: call.data.startswith('admin_close_'))
def handle_close_ticket(call):
    if call.from_user.username not in ADMIN_USERNAMES: return
        
    ticket_id = int(call.data.split('_')[2])
    for t in tickets:
        if t['id'] == ticket_id:
            t['status'] = 'Закрыт'
            bot.send_message(t['user_id'], f"🔔 Вопрос по вашему обращению №{ticket_id} был успешно решен руководством.")
            break
            
    bot.answer_callback_query(call.id, "Тикет закрыт!")
    
    open_tickets = [t for t in tickets if t['status'] == 'Открыт']
    if open_tickets:
        send_ticket_view(call.message.chat.id, 0, open_tickets, call.message.message_id)
    else:
        bot.edit_message_text("📭 Все обращения успешно обработаны.", call.message.chat.id, call.message.message_id)

@bot.callback_query_handler(func=lambda call: call.data.startswith('admin_reply_'))
def handle_reply_ticket(call):
    if call.from_user.username not in ADMIN_USERNAMES: return
        
    ticket_id = int(call.data.split('_')[2])
    user_id = next((t['user_id'] for t in tickets if t['id'] == ticket_id), None)
            
    if not user_id:
        return bot.answer_callback_query(call.id, "Ошибка: тикет не найден.")
        
    msg = bot.send_message(call.message.chat.id, "✍️ Введите текст официального ответа:\n_(Для отмены напишите 'отмена')_", parse_mode='Markdown')
    user_states[call.message.chat.id] = {'state': 'writing_reply', 'user_id': user_id, 'ticket_id': ticket_id}
    bot.answer_callback_query(call.id)

@bot.message_handler(func=lambda message: message.chat.id in user_states and user_states[message.chat.id].get('state') == 'writing_reply')
def send_admin_reply(message):
    state_data = user_states.pop(message.chat.id)
    
    if message.text.lower() == 'отмена':
        return bot.send_message(message.chat.id, "❌ Ответ отменен. Введите /admin для возврата.")
        
    official_reply = (
        f"🛡 **Ответ руководства DragPolit**\n"
        f"По вашему обращению №{state_data['ticket_id']}:\n\n"
        f"_{message.text}_"
    )
    
    try:
        bot.send_message(state_data['user_id'], official_reply, parse_mode='Markdown')
        bot.send_message(message.chat.id, "✅ Ответ отправлен! Введите /admin чтобы вернуться к списку.")
    except Exception:
        bot.send_message(message.chat.id, "⚠️ Ошибка отправки. Пользователь заблокировал бота.")

if __name__ == '__main__':
    print("Бот DragPolit успешно запущен...")
    bot.infinity_polling()
