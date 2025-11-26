from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup, InputFile
from telegram.ext import Application, CommandHandler, MessageHandler, CallbackQueryHandler, ConversationHandler, filters, ContextTypes
import sqlite3
import requests
import logging
import os
import openai

# Укажи токены
TOKEN = "8234291857:AAH73OM1I_TkuJHonc_FlrKsMDrIXJyK6gI"
OPENAI_API_KEY = "sk-5678ijklmnopabcd5678ijklmnopabcd5678ijkl"  # ЗАМЕНИ НА СВОЙ

# Установи ключ OpenAI
openai.api_key = OPENAI_API_KEY

# Состояния
ASK_NAME = 1
ASK_AGE = 2

# Настройка логирования
logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.INFO
)

logger = logging.getLogger(__name__)

def init_db():
    db_path = 'users.db'
    print(f"Создаю базу данных в: {os.path.abspath(db_path)}")
    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS users (
            id INTEGER PRIMARY KEY,
            telegram_id INTEGER UNIQUE,
            name TEXT,
            age INTEGER
        )
    ''')
    conn.commit()
    conn.close()

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    logger.info(f"Пользователь {update.effective_user.id} вызвал /start")
    await update.message.reply_text('Привет! Я твой первый бот.')

async def help_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text('Это бот-помощник. Пока что я умею только здороваться.')

async def menu(update: Update, context: ContextTypes.DEFAULT_TYPE):
    keyboard = [
        [InlineKeyboardButton("Профиль", callback_data='profile')],
        [InlineKeyboardButton("Помощь", callback_data='help_callback')],
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)
    await update.message.reply_text('Выбери:', reply_markup=reply_markup)

async def button_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()

    if query.data == 'profile':
        await query.edit_message_text(text="Твой профиль: пока пусто.")
    elif query.data == 'help_callback':
        await query.edit_message_text(text="Помощь: пока нет информации.")

async def ask_name(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("Как тебя зовут?")
    return ASK_NAME

async def get_name(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_name = update.message.text
    context.user_data['name'] = user_name
    await update.message.reply_text(f"Приятно познакомиться, {user_name}! А сколько тебе лет?")
    return ASK_AGE

async def get_age(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_age = update.message.text
    user_id = update.effective_user.id
    name = context.user_data.get('name', 'пользователь')

    conn = sqlite3.connect('users.db')
    cursor = conn.cursor()
    try:
        cursor.execute('''
            INSERT OR REPLACE INTO users (telegram_id, name, age)
            VALUES (?, ?, ?)
        ''', (user_id, name, int(user_age)))
        conn.commit()
    except ValueError:
        await update.message.reply_text("Возраст должен быть числом. Попробуй ещё раз.")
        conn.close()
        return ASK_AGE
    conn.close()

    await update.message.reply_text(f"Тебя зовут {name}, и тебе {user_age} лет. Данные сохранены!")
    return ConversationHandler.END

async def cancel(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("Диалог отменён.")
    return ConversationHandler.END

# Функция для общения с GPT
async def gpt_chat(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_message = update.message.text

    try:
        response = openai.ChatCompletion.create(
            model="gpt-3.5-turbo",
            messages=[
                {"role": "user", "content": user_message}
            ],
            max_tokens=200,
            temperature=0.7
        )
        gpt_response = response.choices[0].message['content'].strip()
        await update.message.reply_text(gpt_response)
    except Exception as e:
        await update.message.reply_text('Не удалось получить ответ от GPT.')
        print(e)

# Обработчик всех текстовых сообщений через GPT
async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await gpt_chat(update, context)

async def send_photo(update: Update, context: ContextTypes.DEFAULT_TYPE):
    photo_path = 'photo.jpg'
    print(f"Ищу фото по пути: {photo_path}")
    try:
        with open(photo_path, 'rb') as photo:
            await update.message.reply_photo(photo=InputFile(photo))
    except FileNotFoundError:
        print("Файл photo.jpg не найден!")
        await update.message.reply_text('Фото не найдено.')

async def send_document(update: Update, context: ContextTypes.DEFAULT_TYPE):
    doc_path = 'document.pdf'
    print(f"Ищу документ по пути: {doc_path}")
    try:
        with open(doc_path, 'rb') as doc:
            await update.message.reply_document(document=InputFile(doc))
    except FileNotFoundError:
        print("Файл document.pdf не найден!")
        await update.message.reply_text('Документ не найден.')

async def handle_photo(update: Update, context: ContextTypes.DEFAULT_TYPE):
    file = await context.bot.get_file(update.message.photo[-1].file_id)
    await file.download_to_drive('downloaded_photo.jpg')
    await update.message.reply_text('Фото сохранено!')

async def handle_document(update: Update, context: ContextTypes.DEFAULT_TYPE):
    file = await context.bot.get_file(update.message.document.file_id)
    await file.download_to_drive(f"downloaded_{update.message.document.file_name}")
    await update.message.reply_text(f'Документ "{update.message.document.file_name}" сохранён!')

async def get_usd_rate(update: Update, context: ContextTypes.DEFAULT_TYPE):
    try:
        logger.info(f"Пользователь {update.effective_user.id} запросил курс USD")
        response = requests.get('https://www.cbr-xml-daily.ru/daily_json.js')
        response.raise_for_status()
        data = response.json()
        usd_rate = data['Valute']['USD']['Value']
        await update.message.reply_text(f'Курс доллара: {usd_rate:.2f} руб.')
    except requests.exceptions.RequestException as e:
        logger.error(f"Ошибка запроса: {e}")
        await update.message.reply_text('Не удалось получить курс.')
    except KeyError:
        logger.error("Неправильный формат данных от API")
        await update.message.reply_text('Ошибка в данных.')

async def error_handler(update: object, context: ContextTypes.DEFAULT_TYPE) -> None:
    logger.error(msg="Вызвана ошибка при обновлении:", exc_info=context.error)
    if update is not None and update.effective_message:
        await update.effective_message.reply_text('Произошла ошибка.')

def main():
    init_db()
    app = Application.builder().token(TOKEN).build()

    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("help", help_command))
    app.add_handler(CommandHandler("menu", menu))
    app.add_handler(CallbackQueryHandler(button_handler))

    conv_handler = ConversationHandler(
        entry_points=[CommandHandler("dialog", ask_name)],
        states={
            ASK_NAME: [MessageHandler(filters.TEXT & ~filters.COMMAND, get_name)],
            ASK_AGE: [MessageHandler(filters.TEXT & ~filters.COMMAND, get_age)],
        },
        fallbacks=[CommandHandler("cancel", cancel)]
    )
    app.add_handler(conv_handler)

    # Заменяем обычный текстовый обработчик на GPT
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message))

    app.add_handler(CommandHandler("send_photo", send_photo))
    app.add_handler(CommandHandler("send_document", send_document))
    app.add_handler(MessageHandler(filters.PHOTO, handle_photo))
    app.add_handler(MessageHandler(filters.Document.ALL, handle_document))
    app.add_handler(CommandHandler("usd", get_usd_rate))

    app.add_error_handler(error_handler)

    # Используем polling вместо webhook
    app.run_polling(drop_pending_updates=True)

if __name__ == '__main__':
    main()