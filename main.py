import os
import sqlite3
import telebot
import sys
import time
import json
from telebot import types
from datetime import datetime
from threading import Lock

# ==========================================
# 1. СИСТЕМНОЕ ЯДРО И ДОСТУПЫ
# ==========================================
TOKEN = os.environ.get('TOKEN')
# Список Высшего Руководства (Owner IDs)
OWNERS = [1614259542, 7716987740, 1751927856] 

if not TOKEN:
    print("❌ КРИТИЧЕСКАЯ ОШИБКА: Токен не найден в Environment!")
    sys.exit(1)

bot = telebot.TeleBot(TOKEN, parse_mode='HTML')
db_lock = Lock()
DB_FILE = os.environ.get('DB_FILE', 'dragpolit_enterprise_v5.db')

db_dir = os.path.dirname(DB_FILE)
if db_dir and not os.path.exists(db_dir):
    try: os.makedirs(db_dir, exist_ok=True)
    except Exception: pass

# ==========================================
# 2. МУЛЬТИЯЗЫЧНЫЙ ГЛОССАРИЙ (5 ЯЗЫКОВ)
# ==========================================
STRINGS = {
    'ru': {
        'start': "🏛 <b>Central Reception DragPolit</b>\nДобро пожаловать в официальный центр управления игры. Выберите нужный раздел:",
        'b_faq': "❓ FAQ / Справка", 
        'b_lang': "🌐 Выбор языка",
        'b_rules': "📜 Правила проекта",
        'b_links': "🔗 Соцсети и Ресурсы",
        'b_status': "📡 Статус сервера",
        'b_report': "🛡 Жалоба / Репорт",
        'b_bug': "🐛 Пообщаться / Баг-репорт",
        'b_tech': "⚙️ Тех-отдел", 
        'b_mod': "📝 Вакансии (Модерация)",
        'b_partner': "🤝 Партнерство",
        'b_review': "⭐ Отзыв / Идея",
        'b_donate': "💎 Поддержать проект / Донат",
        'b_profile': "👤 Мой профиль",
        'b_close': "❌ Закрыть диалог",
        'input': "📋 <b>РЕЖИМ ЗАПИСИ:</b> Отправьте ваше сообщение (текст, фото или файл).\nВы можете нажать кнопку ниже, чтобы закрыть чат в любой момент.",
        'done': "✅ Обращение зарегистрировано. Ожидайте ответа команды модерации.",
        'reply_head': "🏛 <b>ОФИЦИАЛЬНЫЙ ОТВЕТ АДМИНИСТРАЦИИ DRAGPOLIT:</b>\n━━━━━━━━━━━━━━━━━━━━\n\n",
        'banned': "⛔️ Доступ к боту ограничен службой безопасности DragPolit.",
        'mod_closed': "🚫 <b>Набор в команду модерации временно ЗАКРЫТ.</b>\nСледите за новостями проекта DragPolit!",
        'part_closed': "🚫 <b>Прием заявок на партнерство временно ЗАКРЫТ.</b>",
        'no_questions': "⚠️ Для данной формы еще не настроены вопросы. Обратитесь к администрации.",
        'app_done': "✅ Спасибо! Ваша заявка успешно отправлена на рассмотрение Высшему Руководству.",
        'app_already': "⚠️ Вы уже подали заявку. Ожидайте решения администрации.",
        'rev_star': "⭐ <b>ОЦЕНКА ПРОЕКТА / ОБНОВЛЕНИЯ:</b>\nВыберите вашу оценку от 1 до 5 звезд:",
        'rev_text': "📝 Напишите ваш отзыв или предложение по улучшению игры DragPolit (можно отправить текст, фото или файл):",
        'rev_thanks': "🙏 Спасибо за ваш отзыв! Он отправлен на модерацию руководству.",
        'maintenance': "🛠 <b>ТЕХНИЧЕСКИЕ РАБОТЫ</b>\nСервер временно недоступен в связи с обновлением. Пожалуйста, подождите.",
        'b_profile_text': "👤 <b>ЛИЧНЫЙ КАБИНЕТ</b>\n\n🆔 Ваш ID: <code>{uid}</code>\n🎭 Роль: <b>{role}</b>\n📅 Регистрация: {reg}\n⚠️ Варны: {warns}/3\n\n<b>Ваши заявки:</b>\n{apps}",
        'chat_closed': "❌ <b>Диалог успешно завершен.</b> Вы вернулись в главное меню.",
        'donate_text': "💎 <b>ПОДДЕРЖКА ПРОЕКТА DRAGPOLIT</b>\n\nБлагодарим за поддержку разработки нашей игры! Все средства идут на развитие серверов и новые обновления.\n\n<b>Способы оплаты:</b>\n• <b>Binance Pay ID:</b> <code>{binance_id}</code>\n• <b>USDT (TRC20):</b> <code>{usdt_trc}</code>\n• <b>USDT (BEP20):</b> <code>{usdt_bep}</code>\n• <b>TON:</b> <code>{ton_wall}</code>\n• <b>BTC:</b> <code>{btc_wall}</code>\n\nНажмите на кнопку ниже для просмотра деталей:",
        'select_lang': "🌐 <b>Выберите удобный язык интерфейса:</b>",
        'rules_text': "📜 <b>ПРАВИЛА И РЕГЛАМЕНТ DRAGPOLIT</b>\n\n1. <b>Честная игра:</b> Использование читов, модов, багов и стороннего ПО строго запрещено (Бан навсегда).\n2. <b>Уважение в чате:</b> Оскорбления, спам, реклама сторонних проектов и токсичное поведение запрещены.\n3. <b>Мультиаккаунты:</b> Разрешен только один основной аккаунт на устройство.\n4. <b>Обращения:</b> Запрещен спам в техподдержку и ложные репорты.",
        'status_text': "📡 <b>СТАТУС СЕРВЕРОВ DRAGPOLIT</b>\n\n🟢 <b>Основной сервер:</b> ОНЛАЙН\n🟢 <b>База данных:</b> АКТИВНА\n🎮 <b>Версия игры:</b> <code>v1.5.0-beta</code>\n🧪 <b>Тестирование GP:</b> ОТКРЫТО\n\n<i>Обновлено: {time}</i>"
    },
    'uk': {
        'start': "🏛 <b>Central Reception DragPolit</b>\nЛаскаво просимо до офіційного центру управління гри. Оберіть потрібний розділ:",
        'b_faq': "❓ FAQ / Довідка", 
        'b_lang': "🌐 Вибір мови",
        'b_rules': "📜 Правила проєкту",
        'b_links': "🔗 Соцмережі та Ресурси",
        'b_status': "📡 Статус сервера",
        'b_report': "🛡 Скарги / Репорт", 
        'b_bug': "🐛 Повідомити про баг",
        'b_tech': "⚙️ Тех-підтримка", 
        'b_mod': "📝 Вакансії (Модерація)",
        'b_partner': "🤝 Партнерство",
        'b_review': "⭐ Відгуки та ідеї",
        'b_donate': "💎 Підтримка проєкту / Донат",
        'b_profile': "👤 Мій профіль",
        'b_close': "❌ Закрити діалог",
        'input': "📋 <b>РЕЖИМ ЗАПИСУ:</b> Надішліть ваше повідомлення (текст, фото або файл).\nВи можете натиснути кнопку нижче, щоб закрити чат у будь-який момент.",
        'done': "✅ Звернення зареєстровано. Очікуйте на відповідь команди модерації.",
        'reply_head': "🏛 <b>ОФИЦІЙНА ВІДПОВІДЬ АДМІНІСТРАЦІЇ DRAGPOLIT:</b>\n━━━━━━━━━━━━━━━━━━━━\n\n",
        'banned': "⛔️ Доступ до бота обмежено службою безпеки DragPolit.",
        'mod_closed': "🚫 <b>Набір у команду модерації тимчасово ЗАКРИТО.</b>\nСтежте за новинами проєкту DragPolit!",
        'part_closed': "🚫 <b>Прийом заявок на партнерство тимчасово ЗАКРИТО.</b>",
        'no_questions': "⚠️ Для цієї форми ще не налаштовано запитання. Зверніться до адміністрації.",
        'app_done': "✅ Дякуємо! Вашу заявку успішно надіслано на розгляд Керівництву.",
        'app_already': "⚠️ Ви вже подали заявку. Очікуйте на рішення адміністрації.",
        'rev_star': "⭐ <b>ОЦІНКА ПРОЄКТУ / ОНОВЛЕННЯ:</b>\nОберіть вашу оцінку від 1 до 5 зірок:",
        'rev_text': "📝 Напишіть ваш відгук або пропозицію щодо покращення гри DragPolit (можна надіслати текст, фото або файл):",
        'rev_thanks': "🙏 Дякуємо за ваш відгук! Його надіслано на модерацію керівництву.",
        'maintenance': "🛠 <b>ТЕХНІЧНІ РОБОТИ</b>\nСервер тимчасово недоступний у зв'язку з оновленням. Будь ласка, зачекайте.",
        'b_profile_text': "👤 <b>ОСОБИСТИЙ КАБІНЕТ</b>\n\n🆔 Ваш ID: <code>{uid}</code>\n🎭 Роль: <b>{role}</b>\n📅 Реєстрація: {reg}\n⚠️ Варни: {warns}/3\n\n<b>Ваші заявки:</b>\n{apps}",
        'chat_closed': "❌ <b>Діалог успішно завершено.</b> Ви повернулися в головне меню.",
        'donate_text': "💎 <b>ПІДТРИМКА ПРОЄКТУ DRAGPOLIT</b>\n\nДякуємо за підтримку розробки нашої гри! Усі кошти йдуть на розвиток серверів та нові оновлення.\n\n<b>Способи оплати:</b>\n• <b>Binance Pay ID:</b> <code>{binance_id}</code>\n• <b>USDT (TRC20):</b> <code>{usdt_trc}</code>\n• <b>USDT (BEP20):</b> <code>{usdt_bep}</code>\n• <b>TON:</b> <code>{ton_wall}</code>\n• <b>BTC:</b> <code>{btc_wall}</code>\n\nНатисніть на кнопку нижче для перегляду деталей:",
        'select_lang': "🌐 <b>Оберіть зручну мову інтерфейсу:</b>",
        'rules_text': "📜 <b>ПРАВИЛА ТА РЕГЛАМЕНТ DRAGPOLIT</b>\n\n1. <b>Чесна гра:</b> Використання чітів, модів, багів та стороннього ПЗ суворо заборонено (Бан назавжди).\n2. <b>Повага в чаті:</b> Образи, спам, реклама сторонніх проєктів та токсична поведінка заборонені.\n3. <b>Мультіаккаунти:</b> Дозволено лише один основний акаунт на пристрій.\n4. <b>Звернення:</b> Заборонено спам у техпідтримку та неправдиві скарги.",
        'status_text': "📡 <b>СТАТУС СЕРВЕРІВ DRAGPOLIT</b>\n\n🟢 <b>Основний сервер:</b> ОНЛАЙН\n🟢 <b>База даних:</b> АКТИВНА\n🎮 <b>Версія гри:</b> <code>v1.5.0-beta</code>\n🧪 <b>Тестування GP:</b> ВІДКРИТО\n\n<i>Оновлено: {time}</i>"
    },
    'en': {
        'start': "🏛 <b>DragPolit Central Reception</b>\nWelcome to the official game management center. Select a department:",
        'b_faq': "❓ FAQ / Help", 
        'b_lang': "🌐 Select Language",
        'b_rules': "📜 Game Rules",
        'b_links': "🔗 Official Links",
        'b_status': "📡 Server Status",
        'b_report': "🛡 Report Player", 
        'b_bug': "🐛 Report Bug",
        'b_tech': "⚙️ Tech Support", 
        'b_mod': "📝 Vacancies (Moderation)",
        'b_partner': "🤝 Partnership",
        'b_review': "⭐ Feedback / Ideas",
        'b_donate': "💎 Support / Donate",
        'b_profile': "👤 My Profile",
        'b_close': "❌ Close Chat",
        'input': "📋 <b>RECORD MODE:</b> Type your message or upload media.\nYou can click the button below to close the chat at any time.",
        'done': "✅ Message registered. Please wait for moderation team response.",
        'reply_head': "🏛 <b>OFFICIAL DRAGPOLIT RESPONSE:</b>\n━━━━━━━━━━━━━━━━━━━━\n\n",
        'banned': "⛔️ Access restricted by DragPolit security service.",
        'mod_closed': "🚫 <b>Moderator recruitment is currently CLOSED.</b>\nFollow DragPolit news for updates!",
        'part_closed': "🚫 <b>Partnership applications are currently CLOSED.</b>",
        'no_questions': "⚠️ Form questions are not configured yet. Contact support.",
        'app_done': "✅ Thank you! Your application has been submitted to Management.",
        'app_already': "⚠️ You have already submitted an application. Please wait for review.",
        'rev_star': "⭐ <b>PROJECT / UPDATE RATING:</b>\nChoose your rating from 1 to 5 stars:",
        'rev_text': "📝 Type your review or feedback for the DragPolit team:",
        'rev_thanks': "🙏 Thank you for your feedback! It has been submitted for review.",
        'maintenance': "🛠 <b>MAINTENANCE BREAK</b>\nThe server is temporarily unavailable due to an update. Please stand by.",
        'b_profile_text': "👤 <b>USER PROFILE</b>\n\n🆔 Your ID: <code>{uid}</code>\n🎭 Role: <b>{role}</b>\n📅 Registration: {reg}\n⚠️ Warns: {warns}/3\n\n<b>Your applications:</b>\n{apps}",
        'chat_closed': "❌ <b>Chat closed successfully.</b> Returned to main menu.",
        'donate_text': "💎 <b>SUPPORT DRAGPOLIT PROJECT</b>\n\nThank you for supporting our game development! All funds go toward server maintenance and updates.\n\n<b>Payment methods:</b>\n• <b>Binance Pay ID:</b> <code>{binance_id}</code>\n• <b>USDT (TRC20):</b> <code>{usdt_trc}</code>\n• <b>USDT (BEP20):</b> <code>{usdt_bep}</code>\n• <b>TON:</b> <code>{ton_wall}</code>\n• <b>BTC:</b> <code>{btc_wall}</code>\n\nClick the button below for options:",
        'select_lang': "🌐 <b>Select your interface language:</b>",
        'rules_text': "📜 <b>DRAGPOLIT COMMUNITY RULES</b>\n\n1. <b>Fair Play:</b> Cheats, hacks, mods, and bug exploitation are strictly prohibited (Permanent Ban).\n2. <b>Respect:</b> Insults, spam, toxic behavior, and third-party ads are forbidden.\n3. <b>Multi-accounts:</b> Only 1 primary account per device is permitted.\n4. <b>Support Etiquette:</b> Spamming support or fake reports will result in warnings.",
        'status_text': "📡 <b>DRAGPOLIT SERVER STATUS</b>\n\n🟢 <b>Main Server:</b> ONLINE\n🟢 <b>Database:</b> ACTIVE\n🎮 <b>Game Version:</b> <code>v1.5.0-beta</code>\n🧪 <b>GP Playtest:</b> OPEN\n\n<i>Updated: {time}</i>"
    },
    'es': {
        'start': "🏛 <b>Central Reception DragPolit</b>\nBienvenido al centro de administración oficial. Seleccione una sección:",
        'b_faq': "❓ FAQ / Ayuda", 
        'b_lang': "🌐 Idioma",
        'b_rules': "📜 Reglas del Juego",
        'b_links': "🔗 Enlaces Oficiales",
        'b_status': "📡 Estado del Servidor",
        'b_report': "🛡 Reportar Jugador", 
        'b_bug': "🐛 Reportar Bug / Error",
        'b_tech': "⚙️ Soporte Técnico", 
        'b_mod': "📝 Vacantes (Moderación)",
        'b_partner': "🤝 Asociación",
        'b_review': "⭐ Opiniones e Ideas",
        'b_donate': "💎 Apoyar / Donar",
        'b_profile': "👤 Mi Perfil",
        'b_close': "❌ Cerrar Chat",
        'input': "📋 <b>MODO DE GRABACIÓN:</b> Envíe su mensaje.\nPuede presionar el botón de abajo para cerrar el chat.",
        'done': "✅ Mensaje registrado. Espere la respuesta del equipo de moderación.",
        'reply_head': "🏛 <b>RESPUESTA OFICIAL DE DRAGPOLIT:</b>\n━━━━━━━━━━━━━━━━━━━━\n\n",
        'banned': "⛔️ Acceso restringido por el servicio de seguridad de DragPolit.",
        'mod_closed': "🚫 <b>La contratación de moderadores está CERRADA.</b>",
        'part_closed': "🚫 <b>Las solicitudes de asociación están CERRADAS.</b>",
        'no_questions': "⚠️ No hay preguntas configuradas.",
        'app_done': "✅ ¡Gracias! Su solicitud ha sido enviada a la Administración.",
        'app_already': "⚠️ Ya ha enviado una solicitud. Espere la revisión.",
        'rev_star': "⭐ <b>VALORACIÓN DEL PROYECTO:</b>\nSeleccione su calificación de 1 a 5 estrellas:",
        'rev_text': "📝 Escriba sus comentarios o sugerencias para DragPolit:",
        'rev_thanks': "🙏 ¡Gracias por sus comentarios!",
        'maintenance': "🛠 <b>MANTENIMIENTO TÉCNICO</b>\nEl servidor no está disponible temporalmente.",
        'b_profile_text': "👤 <b>PERFIL DE USUARIO</b>\n\n🆔 Su ID: <code>{uid}</code>\n🎭 Rol: <b>{role}</b>\n📅 Registro: {reg}\n⚠️ Advertencias: {warns}/3\n\n<b>Sus solicitudes:</b>\n{apps}",
        'chat_closed': "❌ <b>Chat cerrado con éxito.</b>",
        'donate_text': "💎 <b>APOYAR EL PROYECTO DRAGPOLIT</b>\n\n¡Gracias por apoyar el desarrollo de nuestro juego!\n\n<b>Métodos de pago:</b>\n• <b>Binance Pay ID:</b> <code>{binance_id}</code>\n• <b>USDT (TRC20):</b> <code>{usdt_trc}</code>\n• <b>USDT (BEP20):</b> <code>{usdt_bep}</code>\n• <b>TON:</b> <code>{ton_wall}</code>\n• <b>BTC:</b> <code>{btc_wall}</code>",
        'select_lang': "🌐 <b>Seleccione su idioma de interfaz:</b>",
        'rules_text': "📜 <b>REGLAS DE DRAGPOLIT</b>\n\n1. Juego limpio (Sin trampas/hacks).\n2. Respeto en el chat.\n3. Una sola cuenta por dispositivo.",
        'status_text': "📡 <b>ESTADO DEL SERVIDOR:</b> ONLINE 🟢"
    },
    'pt': {
        'start': "🏛 <b>Central Reception DragPolit</b>\nBem-vindo ao centro de gestão oficial. Escolha uma seção:",
        'b_faq': "❓ FAQ / Ajuda", 
        'b_lang': "🌐 Idioma",
        'b_rules': "📜 Regras do Jogo",
        'b_links': "🔗 Links Oficiais",
        'b_status': "📡 Status do Servidor",
        'b_report': "🛡 Denunciar Jogador", 
        'b_bug': "🐛 Reportar Bug",
        'b_tech': "⚙️ Suporte Técnico", 
        'b_mod': "📝 Vagas (Moderação)",
        'b_partner': "🤝 Parceria",
        'b_review': "⭐ Avaliação e Ideias",
        'b_donate': "💎 Apoiar / Doar",
        'b_profile': "👤 Meu Perfil",
        'b_close': "❌ Fechar Chat",
        'input': "📋 <b>MODO DE REGISTRO:</b> Envie sua mensagem.\nVocê pode clicar no botão abaixo para fechar o chat.",
        'done': "✅ Mensagem registrada. Aguarde a resposta da equipe.",
        'reply_head': "🏛 <b>RESPOSTA OFICIAL DRAGPOLIT:</b>\n━━━━━━━━━━━━━━━━━━━━\n\n",
        'banned': "⛔️ Acesso restrito pelo serviço de segurança DragPolit.",
        'mod_closed': "🚫 <b>Recrutamento FECHADO temporariamente.</b>",
        'part_closed': "🚫 <b>Parcerias FECHADAS.</b>",
        'no_questions': "⚠️ As perguntas não foram configuradas.",
        'app_done': "✅ Obrigado! Sua solicitação foi enviada.",
        'app_already': "⚠️ Você já enviou uma solicitação.",
        'rev_star': "⭐ <b>AVALIAÇÃO DO PROJETO:</b>\nEscolha sua nota de 1 a 5 estrelas:",
        'rev_text': "📝 Digite sua avaliação ou sugestão:",
        'rev_thanks': "🙏 Obrigado pela sua avaliação!",
        'maintenance': "🛠 <b>MANUTENÇÃO TÉCNICA</b>\nServidor temporariamente indisponível.",
        'b_profile_text': "👤 <b>PERFIL DO USUÁRIO</b>\n\n🆔 Seu ID: <code>{uid}</code>\n🎭 Função: <b>{role}</b>\n📅 Registro: {reg}\n⚠️ Avisos: {warns}/3\n\n<b>Suas solicitações:</b>\n{apps}",
        'chat_closed': "❌ <b>Chat fechado com sucesso.</b>",
        'donate_text': "💎 <b>APOIAR O PROJETO DRAGPOLIT</b>\n\nObrigado por apoiar o desenvolvimento do nosso jogo!\n\n<b>Métodos de pagamento:</b>\n• <b>Binance Pay ID:</b> <code>{binance_id}</code>\n• <b>USDT (TRC20):</b> <code>{usdt_trc}</code>\n• <b>USDT (BEP20):</b> <code>{usdt_bep}</code>\n• <b>TON:</b> <code>{ton_wall}</code>\n• <b>BTC:</b> <code>{btc_wall}</code>",
        'select_lang': "🌐 <b>Selecione o idioma da interface:</b>",
        'rules_text': "📜 <b>REGRAS DRAGPOLIT</b>\n\n1. Jogo limpo (Sem hacks/cheats).\n2. Respeito no chat.\n3. Uma conta por dispositivo.",
        'status_text': "📡 <b>STATUS DO SERVIDOR:</b> ONLINE 🟢"
    }
}

LANG_NAMES = {
    'ru': "🇷🇺 Русский",
    'uk': "🇺🇦 Українська",
    'en': "🇬🇧 English",
    'es': "🇪🇸 Español",
    'pt': "🇵🇹 Português"
}

# ==========================================
# 3. БАЗА ДАННЫХ И АВТО-МИГРАЦИИ (CORE)
# ==========================================
def db_query(sql, params=(), fetch=False, commit=False):
    with db_lock:
        with sqlite3.connect(DB_FILE, timeout=15) as conn:
            conn.execute("PRAGMA journal_mode=WAL;")
            c = conn.cursor()
            c.execute(sql, params)
            res = c.fetchall() if fetch else None
            if commit: 
                conn.commit()
                return c.lastrowid
            return res

def get_setting(key, default="1"):
    res = db_query("SELECT val FROM settings WHERE key = ?", (key,), fetch=True)
    return res[0][0] if res else default

def set_setting(key, val):
    db_query("INSERT OR REPLACE INTO settings (key, val) VALUES (?, ?)", (key, str(val)), commit=True)

def init_db():
    db_query('''CREATE TABLE IF NOT EXISTS subjects (
        uid INTEGER PRIMARY KEY, username TEXT, lang TEXT DEFAULT 'ru', 
        state TEXT DEFAULT 'IDLE', banned INTEGER DEFAULT 0, warns INTEGER DEFAULT 0,
        note TEXT, reg TEXT, role TEXT DEFAULT 'USER')''', commit=True)
    
    db_query('''CREATE TABLE IF NOT EXISTS settings (
        key TEXT PRIMARY KEY, val TEXT)''', commit=True)
    
    db_query('''CREATE TABLE IF NOT EXISTS form_questions (
        id INTEGER PRIMARY KEY AUTOINCREMENT, form_type TEXT, step_order INTEGER, q_ru TEXT, q_en TEXT)''', commit=True)
    
    db_query('''CREATE TABLE IF NOT EXISTS history (
        id INTEGER PRIMARY KEY AUTOINCREMENT, uid INTEGER, txt TEXT, ts TEXT, direction TEXT, admin_id INTEGER DEFAULT 0)''', commit=True)
    
    db_query('''CREATE TABLE IF NOT EXISTS faq_base (
        id INTEGER PRIMARY KEY AUTOINCREMENT, question TEXT, answer TEXT, lang TEXT)''', commit=True)
    
    db_query('''CREATE TABLE IF NOT EXISTS admin_logs (
        id INTEGER PRIMARY KEY AUTOINCREMENT, aid INTEGER, action TEXT, target_uid INTEGER, ts TEXT)''', commit=True)
        
    db_query('''CREATE TABLE IF NOT EXISTS applications (
        id INTEGER PRIMARY KEY AUTOINCREMENT, type TEXT, uid INTEGER, username TEXT,
        data_json TEXT, status TEXT DEFAULT 'PENDING', ts TEXT)''', commit=True)

    db_query('''CREATE TABLE IF NOT EXISTS reviews (
        id INTEGER PRIMARY KEY AUTOINCREMENT, uid INTEGER, username TEXT, rating INTEGER, txt TEXT, status TEXT DEFAULT 'PENDING', ts TEXT)''', commit=True)

    try: db_query("ALTER TABLE history ADD COLUMN admin_id INTEGER DEFAULT 0", commit=True)
    except Exception: pass
    try: db_query("ALTER TABLE subjects ADD COLUMN warns INTEGER DEFAULT 0", commit=True)
    except Exception: pass
    try: db_query("ALTER TABLE subjects ADD COLUMN role TEXT DEFAULT 'USER'", commit=True)
    except Exception: pass

    default_settings = {
        'mod_open': '1',
        'partner_open': '1',
        'maintenance': '0',
        'warn_system': '1',
        'binance_id': '884129571',
        'usdt_trc': 'TYX88sGARARFS29104859120481230491',
        'usdt_bep': '0x892a104859120481230491892a104859',
        'ton_wall': 'EQBv173928104859120481230491892a104859',
        'btc_wall': 'bc1q892a104859120481230491892a104859',
        'tg_channel': 'https://t.me/dragpolit_news',
        'tg_chat': 'https://t.me/dragpolit_chat'
    }
    for k, v in default_settings.items():
        if not db_query("SELECT val FROM settings WHERE key = ?", (k,), fetch=True):
            set_setting(k, v)

    for own_id in OWNERS:
        db_query("INSERT OR REPLACE INTO subjects (uid, role, lang, reg) VALUES (?, 'OWNER', 'ru', datetime('now')) ON CONFLICT(uid) DO UPDATE SET role='OWNER'", (own_id,), commit=True)

    if not db_query("SELECT id FROM form_questions WHERE form_type = 'MOD'", fetch=True):
        db_query("INSERT INTO form_questions (form_type, step_order, q_ru, q_en) VALUES (?, ?, ?, ?)",
                 ('MOD', 1, "Укажите ваш возраст и имя/никнейм:", "Specify your age and name/nickname:"), commit=True)
        db_query("INSERT INTO form_questions (form_type, step_order, q_ru, q_en) VALUES (?, ?, ?, ?)",
                 ('MOD', 2, "Опишите ваш опыт модерации в Telegram/играх:", "Describe your moderation experience:"), commit=True)
        db_query("INSERT INTO form_questions (form_type, step_order, q_ru, q_en) VALUES (?, ?, ?, ?)",
                 ('MOD', 3, "Сколько часов в день вы готовы уделять игре?", "How many hours per day can you dedicate?"), commit=True)

init_db()

# ==========================================
# 4. СИСТЕМА РОЛЕЙ И ПРАВ ДОСТУПА
# ==========================================
ROLES_HIERARCHY = {'USER': 0, 'MODERATOR': 1, 'ADMIN': 2, 'OWNER': 3}

def get_user_role(uid):
    if uid in OWNERS: return 'OWNER'
    res = db_query("SELECT role FROM subjects WHERE uid = ?", (uid,), fetch=True)
    if res and res[0][0]: return res[0][0]
    return 'USER'

def has_role(uid, required_role='MODERATOR'):
    user_role = get_user_role(uid)
    return ROLES_HIERARCHY.get(user_role, 0) >= ROLES_HIERARCHY.get(required_role, 1)

def get_staff_ids():
    staff_ids = set(OWNERS)
    res = db_query("SELECT uid FROM subjects WHERE role IN ('MODERATOR', 'ADMIN', 'OWNER') AND banned = 0", fetch=True)
    if res:
        for r in res: staff_ids.add(r[0])
    return list(staff_ids)

# ==========================================
# 5. СИНХРОНИЗАЦИЯ И КЛАВИАТУРЫ
# ==========================================
def sync_notify_all(sender_id, text, target_uid=None):
    sender_role = get_user_role(sender_id)
    sender_user = f"ID: {sender_id} [{sender_role}]"
    try:
        user_obj = bot.get_chat(sender_id)
        if user_obj.username: sender_user = f"@{user_obj.username} [{sender_role}]"
    except: pass

    sync_msg = f"🔔 <b>СИНХРОНИЗАЦИЯ ШТАБА:</b>\n<b>Сотрудник:</b> {sender_user}\n"
    if target_uid: sync_msg += f"<b>Субъект:</b> <code>{target_uid}</code>\n"
    sync_msg += f"━━━━━━━━━━━━━━━━━━━━\n{text}"

    for staff_id in get_staff_ids():
        if staff_id != sender_id:
            try: bot.send_message(staff_id, sync_msg)
            except: pass

def get_lang_choice_kb():
    kb = types.InlineKeyboardMarkup(row_width=2)
    kb.add(
        types.InlineKeyboardButton(LANG_NAMES['uk'], callback_data="setlang_uk"),
        types.InlineKeyboardButton(LANG_NAMES['en'], callback_data="setlang_en")
    )
    kb.add(
        types.InlineKeyboardButton(LANG_NAMES['es'], callback_data="setlang_es"),
        types.InlineKeyboardButton(LANG_NAMES['pt'], callback_data="setlang_pt")
    )
    kb.add(types.InlineKeyboardButton(LANG_NAMES['ru'], callback_data="setlang_ru"))
    return kb

def get_main_kb(uid):
    res = db_query("SELECT lang, state FROM subjects WHERE uid = ?", (uid,), fetch=True)
    lang = res[0][0] if (res and res[0][0] in STRINGS) else 'ru'
    state = res[0][1] if res else 'IDLE'

    if "INPUT" in state:
        kb = types.ReplyKeyboardMarkup(resize_keyboard=True, row_width=1)
        kb.add(STRINGS[lang]['b_close'])
        return kb

    kb = types.ReplyKeyboardMarkup(resize_keyboard=True, row_width=2)
    kb.add(STRINGS[lang]['b_report'], STRINGS[lang]['b_bug'])
    kb.add(STRINGS[lang]['b_tech'], STRINGS[lang]['b_rules'])
    kb.add(STRINGS[lang]['b_links'], STRINGS[lang]['b_status'])
    kb.add(STRINGS[lang]['b_mod'], STRINGS[lang]['b_partner'])
    kb.add(STRINGS[lang]['b_review'], STRINGS[lang]['b_donate'])
    kb.add(STRINGS[lang]['b_profile'], STRINGS[lang]['b_faq'])
    kb.add(STRINGS[lang]['b_lang'])
    return kb

def get_admin_panel_kb(uid):
    role = get_user_role(uid)
    mod_status = "🟢 ВКЛ" if get_setting('mod_open') == '1' else "🔴 ВЫКЛ"
    part_status = "🟢 ВКЛ" if get_setting('partner_open') == '1' else "🔴 ВЫКЛ"
    maint_status = "🔴 АКТИВНЫ" if get_setting('maintenance') == '0' else "🟢 ВЫКЛЮЧЕНЫ"

    kb = types.InlineKeyboardMarkup(row_width=2)
    kb.add(
        types.InlineKeyboardButton("📂 Активные Заявки", callback_data="adm_apps_list"),
        types.InlineKeyboardButton("⭐ Отзывы и Идеи", callback_data="adm_reviews_list")
    )
    
    if role in ('ADMIN', 'OWNER'):
        kb.add(
            types.InlineKeyboardButton(f"Модерация: {mod_status}", callback_data="toggle_mod"),
            types.InlineKeyboardButton(f"Партнерство: {part_status}", callback_data="toggle_partner")
        )
        kb.add(
            types.InlineKeyboardButton(f"🛠 Тех. работы: {maint_status}", callback_data="toggle_maint"),
            types.InlineKeyboardButton("📢 РАССЫЛКА ВСЕМ", callback_data="adm_broadcast_all")
        )
        kb.add(
            types.InlineKeyboardButton("⚙️ КОНСТРУКТОР АНКЕТ", callback_data="adm_builder"),
            types.InlineKeyboardButton("➕ Добавить FAQ", callback_data="adm_faq_add")
        )
        kb.add(
            types.InlineKeyboardButton("💎 Настройка Реквизитов", callback_data="adm_donations_edit"),
            types.InlineKeyboardButton("📊 Статистика", callback_data="adm_stats")
        )

    if role == 'OWNER':
        warn_status = "🟢 ВКЛ" if get_setting('warn_system') == '1' else "🔴 ВЫКЛ"
        kb.add(
            types.InlineKeyboardButton("👑 Управление Ролями", callback_data="adm_roles_manage"),
            types.InlineKeyboardButton(f"⚠️ Варны: {warn_status}", callback_data="toggle_warns")
        )
        kb.add(
            types.InlineKeyboardButton("📥 Экспорт Идей", callback_data="adm_export_reviews")
        )
        kb.add(types.InlineKeyboardButton("💾 Бэкап БД", callback_data="adm_backup"))

    return kb

def crm_control_kb(uid):
    kb = types.InlineKeyboardMarkup(row_width=2)
    kb.add(
        types.InlineKeyboardButton("✉️ Ответить", callback_data=f"ans_{uid}"),
        types.InlineKeyboardButton("❌ Закрыть чат", callback_data=f"closechat_{uid}")
    )
    kb.add(
        types.InlineKeyboardButton("👤 Досье / Заметка", callback_data=f"prof_{uid}"),
        types.InlineKeyboardButton("📜 История", callback_data=f"hist_{uid}")
    )
    kb.add(
        types.InlineKeyboardButton("⚠️ Варн (+1)", callback_data=f"warn_{uid}"),
        types.InlineKeyboardButton("⛔️ БАН", callback_data=f"ban_{uid}")
    )
    kb.add(types.InlineKeyboardButton("🟢 РАЗБАН", callback_data=f"unban_{uid}"))
    return kb



def app_review_kb(app_id, applicant_uid):
    kb = types.InlineKeyboardMarkup(row_width=2)
    kb.add(
        types.InlineKeyboardButton("✅ Принять", callback_data=f"appdone_accept_{app_id}_{applicant_uid}"),
        types.InlineKeyboardButton("❌ Отклонить", callback_data=f"appdone_reject_{app_id}_{applicant_uid}")
    )
    kb.add(types.InlineKeyboardButton("💬 Написать кандидату", callback_data=f"ans_{applicant_uid}"))
    return kb

def review_rating_kb():
    kb = types.InlineKeyboardMarkup(row_width=5)
    kb.add(
        types.InlineKeyboardButton("⭐ 1", callback_data="star_1"),
        types.InlineKeyboardButton("⭐ 2", callback_data="star_2"),
        types.InlineKeyboardButton("⭐ 3", callback_data="star_3"),
        types.InlineKeyboardButton("⭐ 4", callback_data="star_4"),
        types.InlineKeyboardButton("⭐ 5", callback_data="star_5")
    )
    return kb

# ==========================================
# 6. ОСНОВНЫЕ ХЕНДЛЕРЫ
# ==========================================
@bot.message_handler(commands=['start'])
def h_start(m):
    res = db_query("SELECT lang, banned, role FROM subjects WHERE uid = ?", (m.chat.id,), fetch=True)
    if not res:
        dt = datetime.now().strftime("%Y-%m-%d")
        default_role = 'OWNER' if m.chat.id in OWNERS else 'USER'
        db_query("INSERT INTO subjects (uid, username, reg, role) VALUES (?, ?, ?, ?)", 
                 (m.chat.id, m.from_user.username, dt, default_role), commit=True)
        res = [('ru', 0, default_role)]
    
    lang = res[0][0] if (res[0][0] in STRINGS) else 'ru'
    if res[0][1]: return bot.send_message(m.chat.id, STRINGS[lang]['banned'])
        
    db_query("UPDATE subjects SET state = 'IDLE' WHERE uid = ?", (m.chat.id,), commit=True)
    bot.send_message(m.chat.id, STRINGS[lang]['start'], reply_markup=get_main_kb(m.chat.id))

@bot.message_handler(commands=['admin', 'mod'])
def h_admin(m):
    if not has_role(m.chat.id, 'MODERATOR'): return
    role = get_user_role(m.chat.id)
    bot.send_message(m.chat.id, f"🏛 <b>ТЕРМИНАЛ УПРАВЛЕНИЯ DRAGPOLIT [{role}]</b>\nУправление анкетами, тикетами, баг-репортами и настройками.", reply_markup=get_admin_panel_kb(m.chat.id))

@bot.message_handler(commands=['lang'])
def h_lang_cmd(m):
    lang = db_query("SELECT lang FROM subjects WHERE uid = ?", (m.chat.id,), fetch=True)
    cur_lang = lang[0][0] if lang else 'ru'
    bot.send_message(m.chat.id, STRINGS[cur_lang]['select_lang'], reply_markup=get_lang_choice_kb())

# ОБРАБОТКА ТЕКСТОВОЙ КНОПКИ ЗАКРЫТИЯ ДИАЛОГА
@bot.message_handler(func=lambda m: any(m.text == d.get('b_close') for d in STRINGS.values()))
def h_close_chat_button(m):
    res = db_query("SELECT lang FROM subjects WHERE uid = ?", (m.chat.id,), fetch=True)
    lang = res[0][0] if (res and res[0][0] in STRINGS) else 'ru'
    db_query("UPDATE subjects SET state = 'IDLE' WHERE uid = ?", (m.chat.id,), commit=True)
    bot.send_message(m.chat.id, STRINGS[lang]['chat_closed'], reply_markup=get_main_kb(m.chat.id))

# ОБРАБОТКА ВСЕХ ГЛАВНЫХ ТЕКСТОВЫХ КНОПОК
@bot.message_handler(func=lambda m: any(m.text in d.values() for d in STRINGS.values()))
def h_menu(m):
    if get_setting('maintenance') == '1' and not has_role(m.chat.id, 'MODERATOR'):
        lang_res = db_query("SELECT lang FROM subjects WHERE uid = ?", (m.chat.id,), fetch=True)
        lang = lang_res[0][0] if (lang_res and lang_res[0][0] in STRINGS) else 'ru'
        return bot.send_message(m.chat.id, STRINGS[lang]['maintenance'])

    res = db_query("SELECT lang, banned FROM subjects WHERE uid = ?", (m.chat.id,), fetch=True)
    if not res or res[0][1]: return
    lang = res[0][0] if (res[0][0] in STRINGS) else 'ru'

    # Профиль
    if m.text in [d['b_profile'] for d in STRINGS.values() if 'b_profile' in d]:
        u_data = db_query("SELECT reg, warns, role FROM subjects WHERE uid = ?", (m.chat.id,), fetch=True)[0]
        apps = db_query("SELECT type, status FROM applications WHERE uid = ?", (m.chat.id,), fetch=True)
        
        apps_text = ""
        if apps:
            status_emoji = {'PENDING': '⏳', 'ACCEPTED': '✅', 'REJECTED': '❌'}
            for a in apps:
                apps_text += f"• {a[0]}: {status_emoji.get(a[1], '')} {a[1]}\n"
        else:
            apps_text = "<i>Нет поданных заявок</i>" if lang == 'ru' else "<i>No applications found</i>"
            
        role_title = u_data[2] or ('OWNER' if m.chat.id in OWNERS else 'USER')
        profile_msg = STRINGS[lang]['b_profile_text'].format(uid=m.chat.id, role=role_title, reg=u_data[0], warns=u_data[1], apps=apps_text)
        return bot.send_message(m.chat.id, profile_msg)

    # Правила
    if m.text in [d['b_rules'] for d in STRINGS.values() if 'b_rules' in d]:
        return bot.send_message(m.chat.id, STRINGS[lang]['rules_text'])

    # Соцсети и ресурсы
    if m.text in [d['b_links'] for d in STRINGS.values() if 'b_links' in d]:
        kb = types.InlineKeyboardMarkup(row_width=1)
        kb.add(
            types.InlineKeyboardButton("📢 Официальный Канал DragPolit", url=get_setting('tg_channel')),
            types.InlineKeyboardButton("💬 Общий Чат Игроков", url=get_setting('tg_chat'))
        )
        return bot.send_message(m.chat.id, "🔗 <b>ОФИЦИАЛЬНЫЕ РЕСУРСЫ DRAGPOLIT:</b>\nПрисоединяйтесь к нашим сообществам!", reply_markup=kb)

    # Статус сервера
    if m.text in [d['b_status'] for d in STRINGS.values() if 'b_status' in d]:
        cur_time = datetime.now().strftime("%Y-%m-%d %H:%M")
        return bot.send_message(m.chat.id, STRINGS[lang]['status_text'].format(time=cur_time))

    # Выбор языка
    if m.text in [d['b_lang'] for d in STRINGS.values() if 'b_lang' in d]:
        return bot.send_message(m.chat.id, STRINGS[lang]['select_lang'], reply_markup=get_lang_choice_kb())

    # FAQ
    if m.text in [d['b_faq'] for d in STRINGS.values() if 'b_faq' in d]:
        faqs = db_query("SELECT question, id FROM faq_base WHERE lang = ? OR lang = 'ru'", (lang,), fetch=True)
        if not faqs: return bot.send_message(m.chat.id, "ℹ️ FAQ пуст.")
        kb = types.InlineKeyboardMarkup()
        for q in faqs: kb.add(types.InlineKeyboardButton(q[0], callback_data=f"showfaq_{q[1]}"))
        return bot.send_message(m.chat.id, "<b>Часто задаваемые вопросы:</b>", reply_markup=kb)

    # Отзыв
    if m.text in [d['b_review'] for d in STRINGS.values() if 'b_review' in d]:
        return bot.send_message(m.chat.id, STRINGS[lang]['rev_star'], reply_markup=review_rating_kb())

    # Донат / Поддержка
    if m.text in [d['b_donate'] for d in STRINGS.values() if 'b_donate' in d]:
        donate_msg = STRINGS[lang]['donate_text'].format(
            binance_id=get_setting('binance_id'),
            usdt_trc=get_setting('usdt_trc'),
            usdt_bep=get_setting('usdt_bep'),
            ton_wall=get_setting('ton_wall'),
            btc_wall=get_setting('btc_wall')
        )
        kb = types.InlineKeyboardMarkup()
        kb.add(types.InlineKeyboardButton("🪙 Binance Pay", callback_data="don_binance"))
        kb.add(types.InlineKeyboardButton("💵 USDT (TRC20 / BEP20)", callback_data="don_usdt"))
        kb.add(types.InlineKeyboardButton("💎 TON / BTC", callback_data="don_crypto"))
        return bot.send_message(m.chat.id, donate_msg, reply_markup=kb)

    # Вакансии / Партнерство / Тест
    if m.text in [d['b_mod'] for d in STRINGS.values() if 'b_mod' in d]:
        if get_setting('mod_open') == '0': return bot.send_message(m.chat.id, STRINGS[lang]['mod_closed'])
        return start_dynamic_form(m.chat.id, 'MOD', lang)

    if m.text in [d['b_partner'] for d in STRINGS.values() if 'b_partner' in d]:
        if get_setting('partner_open') == '0': return bot.send_message(m.chat.id, STRINGS[lang]['part_closed'])
        return start_dynamic_form(m.chat.id, 'PARTNER', lang)


    # Баг-репорт
    if m.text in [d['b_bug'] for d in STRINGS.values() if 'b_bug' in d]:
        db_query("UPDATE subjects SET state = 'INPUT|БАГ-РЕПОРТ' WHERE uid = ?", (m.chat.id,), commit=True)
        return bot.send_message(m.chat.id, STRINGS[lang]['input'], reply_markup=get_main_kb(m.chat.id))

    # Скарги / Репорт
    if m.text in [d['b_report'] for d in STRINGS.values() if 'b_report' in d]:
        db_query("UPDATE subjects SET state = 'INPUT|РЕПОРТ' WHERE uid = ?", (m.chat.id,), commit=True)
        return bot.send_message(m.chat.id, STRINGS[lang]['input'], reply_markup=get_main_kb(m.chat.id))

    # Тех-підтримка
    if m.text in [d['b_tech'] for d in STRINGS.values() if 'b_tech' in d]:
        db_query("UPDATE subjects SET state = 'INPUT|ТЕХ-ОТДЕЛ' WHERE uid = ?", (m.chat.id,), commit=True)
        return bot.send_message(m.chat.id, STRINGS[lang]['input'], reply_markup=get_main_kb(m.chat.id))

    db_query("UPDATE subjects SET state = ? WHERE uid = ?", (f"INPUT|{m.text}", m.chat.id), commit=True)
    bot.send_message(m.chat.id, STRINGS[lang]['input'], reply_markup=get_main_kb(m.chat.id))

# ==========================================
# 7. ДИНАМИЧЕСКИЙ ДВИЖОК АНКЕТИРОВАНИЯ
# ==========================================
def start_dynamic_form(uid, form_type, lang):
    check_app = db_query("SELECT id FROM applications WHERE uid = ? AND type = ? AND status = 'PENDING'", (uid, form_type), fetch=True)
    if check_app: return bot.send_message(uid, STRINGS[lang]['app_already'])

    questions = db_query("SELECT id, q_ru, q_en FROM form_questions WHERE form_type = ? ORDER BY step_order ASC", (form_type,), fetch=True)
    if not questions: return bot.send_message(uid, STRINGS[lang]['no_questions'])

    answers_init = json.dumps([])
    db_query("UPDATE subjects SET state = ? WHERE uid = ?", (f"RUNFORM|{form_type}|0|{answers_init}", uid), commit=True)
    
    q_text = questions[0][1] if lang in ('ru', 'uk') else questions[0][2]
    
    headers = {
        'MOD': "📝 <b>АНКЕТА МОДЕРАТОРА</b>\n\n",
        'PARTNER': "🤝 <b>ЗАЯВКА НА ПАРТНЕРСТВО</b>\n\n",
    }
    header = headers.get(form_type, "📋 <b>ЗАПОЛНЕНИЕ АНКЕТЫ</b>\n\n")
    
    msg = bot.send_message(uid, f"{header}<b>Шаг 1/{len(questions)}:</b> {q_text}", reply_markup=get_main_kb(uid))
    bot.register_next_step_handler(msg, process_form_step)

def process_form_step(m):
    if m.text and m.text.startswith('/'):
        db_query("UPDATE subjects SET state = 'IDLE' WHERE uid = ?", (m.chat.id,), commit=True)
        bot.send_message(m.chat.id, "❌ Заполнение анкеты отменено.", reply_markup=get_main_kb(m.chat.id))
        if m.text == '/start': return h_start(m)
        if m.text in ('/admin', '/mod'): return h_admin(m)
        return

    res = db_query("SELECT state, lang FROM subjects WHERE uid = ?", (m.chat.id,), fetch=True)
    if not res or "RUNFORM" not in res[0][0]: return
    
    parts = res[0][0].split('|', 3)
    form_type, q_index, answers, lang = parts[1], int(parts[2]), json.loads(parts[3]), res[0][1]

    answers.append(m.text)
    questions = db_query("SELECT q_ru, q_en FROM form_questions WHERE form_type = ? ORDER BY step_order ASC", (form_type,), fetch=True)
    next_index = q_index + 1

    if next_index < len(questions):
        db_query("UPDATE subjects SET state = ? WHERE uid = ?", (f"RUNFORM|{form_type}|{next_index}|{json.dumps(answers)}", m.chat.id), commit=True)
        q_text = questions[next_index][0] if lang in ('ru', 'uk') else questions[next_index][1]
        msg = bot.send_message(m.chat.id, f"<b>Шаг {next_index+1}/{len(questions)}:</b> {q_text}")
        bot.register_next_step_handler(msg, process_form_step)
    else:
        db_query("UPDATE subjects SET state = 'IDLE' WHERE uid = ?", (m.chat.id,), commit=True)
        ts = datetime.now().strftime("%Y-%m-%d %H:%M")
        
        app_id = db_query("INSERT INTO applications (type, uid, username, data_json, ts) VALUES (?, ?, ?, ?, ?)", 
                 (form_type, m.chat.id, m.from_user.username, json.dumps(answers), ts), commit=True)

        bot.send_message(m.chat.id, STRINGS[lang]['app_done'], reply_markup=get_main_kb(m.chat.id))

        titles = {
            'MOD': "📝 <b>НОВАЯ ЗАЯВКА В МОДЕРАТОРЫ</b>",
            'PARTNER': "🤝 <b>НОВАЯ ЗАЯВКА НА ПАРТНЕРСТВО</b>",
        }
        title = titles.get(form_type, "📋 <b>НОВАЯ ЗАЯВКА</b>")
        
        card = f"{title} <b>#{app_id}</b>\n━━━━━━━━━━━━━━━━━━━━\n👤 <b>Заявитель:</b> @{m.from_user.username} (<code>{m.chat.id}</code>)\n\n"
        for idx, q_item in enumerate(questions):
            ans_val = answers[idx] if idx < len(answers) else '—'
            card += f"<b>❓ {q_item[0]}</b>\n💬 <i>{ans_val}</i>\n\n"
        card += f"📅 <b>Дата:</b> {ts}"

        for staff_id in get_staff_ids():
            try: bot.send_message(staff_id, card, reply_markup=app_review_kb(app_id, m.chat.id))
            except: pass

# ==========================================
# 8. ОБРАБОТКА ВХОДЯЩИХ (TICKETS, BUGS, REVIEWS)
# ==========================================
@bot.message_handler(content_types=['text', 'photo', 'video', 'document', 'voice'])
def h_catch_all(m):
    res = db_query("SELECT lang, banned, state FROM subjects WHERE uid = ?", (m.chat.id,), fetch=True)
    if not res: return 
    u = res[0]
    lang = u[0] if u[0] in STRINGS else 'ru'
    
    if get_setting('maintenance') == '1' and not has_role(m.chat.id, 'MODERATOR'):
        bot.send_message(m.chat.id, STRINGS[lang]['maintenance'])
        return
        
    if u[1]: return 
    if has_role(m.chat.id, 'MODERATOR') and u[2] == 'IDLE': return 

    is_input = "INPUT" in u[2]
    ts = datetime.now().strftime("%H:%M")
    txt_log = m.text if m.content_type == 'text' else f"[{m.content_type}]"
    
    try:
        db_query("INSERT INTO history (uid, txt, ts, direction) VALUES (?, ?, ?, ?)", (m.chat.id, txt_log, ts, 'IN'), commit=True)
    except: pass

    if is_input:
        bot.send_message(m.chat.id, STRINGS[lang]['done'], reply_markup=get_main_kb(m.chat.id))
        db_query("UPDATE subjects SET state = 'IDLE' WHERE uid = ?", (m.chat.id,), commit=True)
    
    dept = u[2].split('|')[1] if is_input else "Общий чат"
    header = f"📩 <b>СООБЩЕНИЕ [{dept}]:</b> @{m.from_user.username} (<code>{m.chat.id}</code>)\n"
    
    for staff_id in get_staff_ids():
        try:
            if m.content_type == 'text':
                bot.send_message(staff_id, header + f"Текст: <i>{m.text}</i>", reply_markup=crm_control_kb(m.chat.id))
            else:
                bot.send_message(staff_id, header)
                bot.copy_message(staff_id, m.chat.id, m.message_id, reply_markup=crm_control_kb(m.chat.id))
        except: pass

# ==========================================
# 9. ИНТЕРАКТИВНАЯ АДМИНКА И CALLBACKS
# ==========================================
@bot.callback_query_handler(func=lambda c: True)
def h_callbacks(c):
    p = c.data.split('_')
    action = p[0]
    aid = c.from_user.id
    
    if action == 'setlang':
        new_lang = p[1]
        db_query("UPDATE subjects SET lang = ? WHERE uid = ?", (new_lang, c.from_user.id), commit=True)
        msg_text = {
            'uk': "🌐 Мову успішно змінено на Українську!",
            'en': "🌐 Language successfully set to English!",
            'es': "🌐 ¡Idioma cambiado a Español con éxito!",
            'pt': "🌐 Idioma alterado para Português com sucesso!",
            'ru': "🌐 Язык успешно изменен на Русский!"
        }.get(new_lang, "🌐 Language updated!")
        
        bot.answer_callback_query(c.id, "Saved!")
        return bot.send_message(c.message.chat.id, msg_text, reply_markup=get_main_kb(c.from_user.id))

    if action == 'don':
        if p[1] == 'binance':
            bot.send_message(c.message.chat.id, f"🪙 <b>Binance Pay ID:</b>\n<code>{get_setting('binance_id')}</code>\n\n<i>Нажмите на код выше, чтобы скопировать.</i>")
        elif p[1] == 'usdt':
            bot.send_message(c.message.chat.id, f"💵 <b>USDT TRC20:</b>\n<code>{get_setting('usdt_trc')}</code>\n\n💵 <b>USDT BEP20:</b>\n<code>{get_setting('usdt_bep')}</code>")
        elif p[1] == 'crypto':
            bot.send_message(c.message.chat.id, f"💎 <b>TON Wallet:</b>\n<code>{get_setting('ton_wall')}</code>\n\n₿ <b>Bitcoin (BTC):</b>\n<code>{get_setting('btc_wall')}</code>")
        return bot.answer_callback_query(c.id)

    if action == 'star':
        rating = int(p[1])
        lang = db_query("SELECT lang FROM subjects WHERE uid = ?", (c.from_user.id,), fetch=True)[0][0]
        if lang not in STRINGS: lang = 'ru'
        db_query("UPDATE subjects SET state = ? WHERE uid = ?", (f"REVIEW_TEXT|{rating}", c.from_user.id), commit=True)
        msg = bot.send_message(c.message.chat.id, STRINGS[lang]['rev_text'])
        bot.register_next_step_handler(msg, step_save_review)
        return bot.answer_callback_query(c.id)

    if action == 'showfaq':
        faq = db_query("SELECT answer FROM faq_base WHERE id = ?", (p[1],), fetch=True)
        if faq: bot.send_message(c.message.chat.id, f"💡 <b>FAQ:</b>\n{faq[0][0]}")
        return bot.answer_callback_query(c.id)

    if action == 'closechat':
        target_uid = int(p[1])
        db_query("UPDATE subjects SET state = 'IDLE' WHERE uid = ?", (target_uid,), commit=True)
        target_lang = db_query("SELECT lang FROM subjects WHERE uid = ?", (target_uid,), fetch=True)
        u_lang = target_lang[0][0] if (target_lang and target_lang[0][0] in STRINGS) else 'ru'
        
        try: bot.send_message(target_uid, STRINGS[u_lang]['chat_closed'], reply_markup=get_main_kb(target_uid))
        except: pass
        
        sync_notify_all(aid, f"❌ Закрыл активный чат с пользователем", target_uid=target_uid)
        return bot.answer_callback_query(c.id, "Чат закрыт")

    # Staff checks
    if has_role(aid, 'MODERATOR'):
        if c.data == 'toggle_mod' and has_role(aid, 'ADMIN'):
            new_v = '0' if get_setting('mod_open') == '1' else '1'
            set_setting('mod_open', new_v)
            bot.edit_message_reply_markup(c.message.chat.id, c.message.message_id, reply_markup=get_admin_panel_kb(aid))
            sync_notify_all(aid, f"⚙️ Изменил прием Модераторов на: <b>{'ВКЛ' if new_v=='1' else 'ВЫКЛ'}</b>")
            return bot.answer_callback_query(c.id, "Статус изменен")

        if c.data == 'toggle_partner' and has_role(aid, 'ADMIN'):
            new_v = '0' if get_setting('partner_open') == '1' else '1'
            set_setting('partner_open', new_v)
            bot.edit_message_reply_markup(c.message.chat.id, c.message.message_id, reply_markup=get_admin_panel_kb(aid))
            sync_notify_all(aid, f"⚙️ Изменил прием Партнерства на: <b>{'ВКЛ' if new_v=='1' else 'ВЫКЛ'}</b>")
            return bot.answer_callback_query(c.id, "Статус изменен")

        if c.data == 'toggle_warns' and get_user_role(aid) == 'OWNER':
            new_v = '0' if get_setting('warn_system') == '1' else '1'
            set_setting('warn_system', new_v)
            bot.edit_message_reply_markup(c.message.chat.id, c.message.message_id, reply_markup=get_admin_panel_kb(aid))
            sync_notify_all(aid, f"⚠️ Изменил статус Системы Варнов на: <b>{'ВКЛ' if new_v=='1' else 'ВЫКЛ'}</b>")
            return bot.answer_callback_query(c.id, "Статус изменен")

        if c.data == 'toggle_maint' and has_role(aid, 'ADMIN'):
            new_v = '0' if get_setting('maintenance') == '1' else '1'
            set_setting('maintenance', new_v)
            bot.edit_message_reply_markup(c.message.chat.id, c.message.message_id, reply_markup=get_admin_panel_kb(aid))
            sync_notify_all(aid, f"🛠 Режим тех. работ: <b>{'ВКЛЮЧЕН' if new_v=='1' else 'ВЫКЛЮЧЕН'}</b>")
            return bot.answer_callback_query(c.id, "Статус изменен")

        if c.data == 'adm_roles_manage' and get_user_role(aid) == 'OWNER':
            msg = bot.send_message(c.message.chat.id, "👑 <b>УПРАВЛЕНИЕ РОЛЯМИ</b>\nВведите ID пользователя и роль через пробел:\n<code>123456789 MODERATOR</code>\n<i>Доступные роли: USER, MODERATOR, ADMIN</i>\n(или '.' для отмены):")
            return bot.register_next_step_handler(msg, step_set_role)

        if c.data == 'adm_builder' and has_role(aid, 'ADMIN'):
            kb = types.InlineKeyboardMarkup(row_width=1)
            kb.add(
                types.InlineKeyboardButton("📝 Вопросы Модерации", callback_data="build_view_MOD"),
                types.InlineKeyboardButton("🤝 Вопросы Партнерства", callback_data="build_view_PARTNER")
            )
            return bot.send_message(c.message.chat.id, "⚙️ <b>КОНСТРУКТОР АНКЕТ DRAGPOLIT</b>\nВыберите форму для настройки:", reply_markup=kb)

        if c.data == 'adm_broadcast_all' and has_role(aid, 'ADMIN'):
            msg = bot.send_message(c.message.chat.id, f"📢 <b>РАССЫЛКА ВСЕМ ИГРОКАМ</b>\n\nОтправьте сообщение (текст, фото с описанием, видео, файл или стикер), которое нужно разослать:\n\n<i>(Напишите '.' для отмены)</i>")
            return bot.register_next_step_handler(msg, step_broadcast, 'adm_broadcast_all')

        if c.data == 'adm_apps_list':
            apps = db_query("SELECT id, type, uid, ts FROM applications WHERE status = 'PENDING' LIMIT 10", fetch=True)
            if not apps:
                return bot.send_message(c.message.chat.id, "📂 Активных нерассмотренных заявок нет.")
            res = "📂 <b>НЕРАССМОТРЕННЫЕ ЗАЯВКИ:</b>\n\n"
            for a in apps:
                res += f"• <b>Заявка #{a[0]} [{a[1]}]</b> от <code>{a[2]}</code> ({a[3]})\n"
            return bot.send_message(c.message.chat.id, res)

        if c.data == 'adm_faq_add' and has_role(aid, 'ADMIN'):
            msg = bot.send_message(c.message.chat.id, "➕ <b>ДОБАВЛЕНИЕ FAQ</b>\nВведите ВОПРОС (или напишите '.' для отмены):")
            return bot.register_next_step_handler(msg, step_faq_q)

        if c.data == 'adm_donations_edit' and has_role(aid, 'ADMIN'):
            msg = bot.send_message(c.message.chat.id, "💎 <b>НАСТРОЙКА РЕКВИЗИТОВ</b>\nВведите Binance Pay ID (или '.' для пропуска):")
            return bot.register_next_step_handler(msg, step_edit_donations)

        if action == 'ans':
            msg = bot.send_message(c.message.chat.id, f"✉️ Введите ваш ответ для <code>{p[1]}</code>:")
            bot.register_next_step_handler(msg, step_send_ans, p[1])

        elif action == 'prof':
            u = db_query("SELECT username, reg, note, warns, role FROM subjects WHERE uid = ?", (p[1],), fetch=True)[0]
            bot.send_message(c.message.chat.id, f"👤 <b>ДОСЬЕ {p[1]}</b>\nНик: @{u[0]}\nРоль: <b>{u[4]}</b>\nЗаметка: <i>{u[2] or 'нет'}</i>\n\nВведите новую заметку или '.':")
            bot.register_next_step_handler(c.message, step_save_note, p[1])

        elif action == 'warn':
            if get_setting('warn_system') != '1':
                return bot.answer_callback_query(c.id, "Система варнов отключена!", show_alert=True)
            db_query("UPDATE subjects SET warns = warns + 1 WHERE uid = ?", (p[1],), commit=True)
            warns = db_query("SELECT warns FROM subjects WHERE uid = ?", (p[1],), fetch=True)[0][0]
            sync_notify_all(aid, f"⚠️ Выдал предупреждение (+1). Всего: {warns}/3", target_uid=p[1])
            bot.answer_callback_query(c.id, "Варн выдан")

        elif action == 'ban':
            db_query("UPDATE subjects SET banned = 1 WHERE uid = ?", (p[1],), commit=True)
            sync_notify_all(aid, "⛔️ ЗАБЛОКИРОВАЛ пользователя", target_uid=p[1])
            bot.answer_callback_query(c.id, "Забанен")

        elif action == 'unban':
            db_query("UPDATE subjects SET banned = 0 WHERE uid = ?", (p[1],), commit=True)
            sync_notify_all(aid, "🟢 РАЗБЛОКИРОВАЛ пользователя", target_uid=p[1])
            bot.answer_callback_query(c.id, "Разбанен")

        elif action == 'appdone':
            decision, app_id, applicant_uid = p[1], p[2], p[3]
            u_lang_res = db_query("SELECT lang FROM subjects WHERE uid = ?", (applicant_uid,), fetch=True)
            u_lang = u_lang_res[0][0] if (u_lang_res and u_lang_res[0][0] in STRINGS) else 'ru'
            
            if decision == 'accept':
                db_query("UPDATE applications SET status = 'ACCEPTED' WHERE id = ?", (app_id,), commit=True)
                msg = "🎉 <b>Поздравляем!</b> Ваша заявка в DragPolit ОДОБРЕНА." if u_lang in ('ru', 'uk') else "🎉 <b>Congratulations!</b> Your application was ACCEPTED."
                bot.send_message(applicant_uid, msg)
                bot.edit_message_text(f"{c.message.text}\n\n<b>СТАТУС: ✅ ОДОБРЕНО (Staff: {aid})</b>", c.message.chat.id, c.message.message_id)
                sync_notify_all(aid, f"✅ ОДОБРИЛ заявку #{app_id}", target_uid=applicant_uid)
            elif decision == 'reject':
                db_query("UPDATE applications SET status = 'REJECTED' WHERE id = ?", (app_id,), commit=True)
                msg = "❌ К сожалению, ваша заявка была отклонена." if u_lang in ('ru', 'uk') else "❌ Unfortunately, your application was rejected."
                bot.send_message(applicant_uid, msg)
                bot.edit_message_text(f"{c.message.text}\n\n<b>СТАТУС: ❌ ОТКЛОНЕНО (Staff: {aid})</b>", c.message.chat.id, c.message.message_id)
                sync_notify_all(aid, f"❌ ОТКЛОНИЛ заявку #{app_id}", target_uid=applicant_uid)

        elif action == 'adm':
            if c.data == 'adm_stats':
                total_users = db_query("SELECT COUNT(*) FROM subjects", fetch=True)[0][0]
                total_apps = db_query("SELECT COUNT(*) FROM applications", fetch=True)[0][0]
                total_revs = db_query("SELECT COUNT(*) FROM reviews", fetch=True)[0][0]
                staff_count = len(get_staff_ids())

                res = f"📊 <b>СТАТИСТИКА DRAGPOLIT:</b>\n👥 Игроков в системе: <b>{total_users}</b>\n🛡 Состав модерации: <b>{staff_count}</b>\n📝 Заявок всего: <b>{total_apps}</b>\n⭐ Отзывов: <b>{total_revs}</b>"
                bot.send_message(c.message.chat.id, res)
            
            elif c.data == 'adm_reviews_list':
                revs = db_query("SELECT id, rating, txt, username FROM reviews ORDER BY id DESC LIMIT 5", fetch=True)
                if not revs: return bot.send_message(c.message.chat.id, "⭐ Отзывов пока нет.")
                res = "⭐ <b>ПОСЛЕДНИЕ ОТЗЫВЫ:</b>\n\n"
                for r in revs:
                    stars = "⭐" * r[1]
                    res += f"<b>#{r[0]}</b> {stars} от @{r[3]}\n<i>└ {r[2][:80]}</i>\n\n"
                bot.send_message(c.message.chat.id, res)

            elif c.data == 'adm_backup' and get_user_role(aid) == 'OWNER':
                with open(DB_FILE, 'rb') as f: bot.send_document(c.message.chat.id, f, caption="💾 DATABASE BACKUP")
                
            elif c.data == 'adm_export_reviews' and get_user_role(aid) == 'OWNER':
                revs = db_query("SELECT id, uid, username, rating, txt FROM reviews ORDER BY id DESC", fetch=True)
                if not revs: return bot.send_message(c.message.chat.id, "Отзывов пока нет.")
                content = "ID | UID | Username | Rating | Текст\n" + "-"*50 + "\n"
                for r in revs: content += f"#{r[0]} | {r[1]} | @{r[2]} | {r[3]}⭐ | {r[4]}\n"
                import io
                bio = io.BytesIO(content.encode('utf-8'))
                bio.name = 'reviews_ideas.txt'
                bot.send_document(c.message.chat.id, bio, caption="📥 Экспорт Отзывов и Идей")

# ==========================================
# 10. КРОКИ АДМИНИСТРАЦИИ И ПОЛЬЗОВАТЕЛЕЙ
# ==========================================
def step_set_role(m):
    if m.text == '.': return bot.send_message(m.chat.id, "❌ Отменено.")
    try:
        parts = m.text.split()
        target_uid = int(parts[0])
        role = parts[1].upper()
        if role not in ('USER', 'MODERATOR', 'ADMIN', 'OWNER'):
            return bot.send_message(m.chat.id, "❌ Неверная роль. Доступные: USER, MODERATOR, ADMIN, OWNER")
        
        db_query("UPDATE subjects SET role = ? WHERE uid = ?", (role, target_uid), commit=True)
        sync_notify_all(m.from_user.id, f"👑 Изменил роль пользователя <code>{target_uid}</code> на <b>{role}</b>")
        bot.send_message(m.chat.id, f"✅ Роль пользователя <code>{target_uid}</code> успешно изменена на <b>{role}</b>!")
    except Exception as e:
        bot.send_message(m.chat.id, f"❌ Ошибка ввода: {e}. Напишите например: <code>123456789 MODERATOR</code>")

def step_edit_donations(m):
    if m.text != '.': set_setting('binance_id', m.text)
    msg = bot.send_message(m.chat.id, "Введите новый USDT TRC20 адрес (или '.' для пропуска):")
    bot.register_next_step_handler(msg, step_edit_donations_usdt)

def step_edit_donations_usdt(m):
    if m.text != '.': set_setting('usdt_trc', m.text)
    bot.send_message(m.chat.id, "✅ Реквизиты успешно обновлены!")

def step_broadcast(m, target_group):
    if m.text == '.':
        return bot.send_message(m.chat.id, "❌ Рассылка отменена.")

    users = db_query("SELECT uid FROM subjects WHERE banned = 0", fetch=True)
    target_name = "Всем игрокам"

    if not users:
        return bot.send_message(m.chat.id, "❌ Нет подходящих пользователей для этой рассылки.")

    bot.send_message(m.chat.id, f"⏳ <b>Запуск рассылки ({target_name})...</b>\nПолучателей: {len(users)}")

    succeeded = 0
    failed = 0

    for u in users:
        uid = u[0]
        try:
            bot.copy_message(chat_id=uid, from_chat_id=m.chat.id, message_id=m.message_id)
            succeeded += 1
            time.sleep(0.04) 
        except Exception:
            failed += 1

    res_text = (f"📢 <b>РАССЫЛКА ЗАВЕРШЕНА!</b>\n"
                f"━━━━━━━━━━━━━━━━━━━━\n"
                f"Аудитория: <b>{target_name}</b>\n"
                f"✅ Успешно доставлено: <b>{succeeded}</b>\n"
                f"❌ Ошибок / Заблокировали бота: <b>{failed}</b>\n"
                f"👥 Всего в выборке: <b>{len(users)}</b>")

    bot.send_message(m.chat.id, res_text)
    sync_notify_all(m.from_user.id, f"📢 Провел рассылку ({target_name}).\nДоставлено: {succeeded} | Ошибок: {failed}")

def step_faq_q(m):
    if m.text == '.': return bot.send_message(m.chat.id, "❌ Отменено.")
    msg = bot.send_message(m.chat.id, f"❓ <b>Вопрос:</b> <i>{m.text}</i>\n\nТеперь введите ОТВЕТ:")
    bot.register_next_step_handler(msg, step_faq_a, m.text)

def step_faq_a(m, question):
    if m.text == '.': return bot.send_message(m.chat.id, "❌ Отменено.")
    db_query("INSERT INTO faq_base (question, answer, lang) VALUES (?, ?, ?)", 
             (question, m.text, 'ru'), commit=True)
    sync_notify_all(m.from_user.id, f"➕ Добавил пункт в FAQ: {question}")
    bot.send_message(m.chat.id, "✅ Пункт успешно добавлен в FAQ!")

def step_save_review(m):
    st = db_query("SELECT state, lang FROM subjects WHERE uid = ?", (m.chat.id,), fetch=True)[0]
    rating = int(st[0].split('|')[1])
    lang = st[1] if st[1] in STRINGS else 'ru'
    ts = datetime.now().strftime("%Y-%m-%d %H:%M")

    txt = m.text or m.caption or f"[{m.content_type}]"

    db_query("INSERT INTO reviews (uid, username, rating, txt, ts) VALUES (?, ?, ?, ?, ?)",
             (m.chat.id, m.from_user.username, rating, txt, ts), commit=True)
    
    db_query("UPDATE subjects SET state = 'IDLE' WHERE uid = ?", (m.chat.id,), commit=True)
    bot.send_message(m.chat.id, STRINGS[lang]['rev_thanks'], reply_markup=get_main_kb(m.chat.id))

    stars = "⭐" * rating
    rev_card = (f"⭐ <b>НОВЫЙ ОТЗЫВ / ИДЕЯ</b>\n━━━━━━━━━━━━━━━━━━━━\n"
                f"👤 <b>От:</b> @{m.from_user.username} (<code>{m.chat.id}</code>)\n"
                f"Оценка: {stars} ({rating}/5)\n"
                f"<b>Текст:</b> <i>{txt}</i>\n📅 {ts}")
    for staff_id in get_staff_ids():
        try:
            if m.content_type == 'text':
                bot.send_message(staff_id, rev_card)
            else:
                bot.send_message(staff_id, rev_card)
                bot.copy_message(staff_id, m.chat.id, m.message_id)
        except: pass

def step_send_ans(m, uid):
    res_user = db_query("SELECT lang FROM subjects WHERE uid = ?", (uid,), fetch=True)
    u_lang = res_user[0][0] if (res_user and res_user[0][0] in STRINGS) else 'ru'
    aid = m.from_user.id
    
    try:
        content = m.text if m.content_type == 'text' else f"[{m.content_type}]"
        
        if m.content_type == 'text':
            bot.send_message(uid, STRINGS[u_lang]['reply_head'] + f"<i>{m.text}</i>")
        else:
            bot.send_message(uid, STRINGS[u_lang]['reply_head'])
            bot.copy_message(uid, m.chat.id, m.message_id)
        
        try:
            db_query("INSERT INTO history (uid, txt, ts, direction, admin_id) VALUES (?, ?, ?, ?, ?)", 
                     (uid, content, "NOW", "OUT", aid), commit=True)
        except Exception:
            db_query("INSERT INTO history (uid, txt, ts, direction) VALUES (?, ?, ?, ?)", 
                     (uid, content, "NOW", "OUT"), commit=True)
        
        sync_notify_all(aid, f"💬 <b>ОТПРАВЛЕН ОТВЕТ:</b>\n<i>«{content}»</i>", target_uid=uid)
        bot.send_message(m.chat.id, "✅ Ответ успешно доставлен игроку!")
    except Exception as e:
        bot.send_message(m.chat.id, f"❌ Ошибка доставки сообщения пользователю: {e}")

def step_save_note(m, uid):
    if m.text != ".":
        db_query("UPDATE subjects SET note = ? WHERE uid = ?", (m.text, uid), commit=True)
        sync_notify_all(m.from_user.id, f"📝 Изменил заметку: <i>{m.text}</i>", target_uid=uid)
        bot.send_message(m.chat.id, "✅ Заметка сохранена.")

# ==========================================
# 11. ЗАПУСК БОТА
# ==========================================
if __name__ == '__main__':
    bot.set_my_commands([
        types.BotCommand("start", "Главная страница"),
        types.BotCommand("admin", "Терминал управления"),
        types.BotCommand("mod", "Панель модератора"),
        types.BotCommand("lang", "Выбор языка / Language")
    ])
    print(f"[{datetime.now().strftime('%H:%M:%S')}] DRAGPOLIT ENTERPRISE V7 ULTIMATE ONLINE.")
    
    while True:
        try:
            bot.infinity_polling(timeout=10, long_polling_timeout=5)
        except Exception as e:
            print(f"⚠️ Переподключение через 5 сек... Ошибка: {e}")
            time.sleep(5)
