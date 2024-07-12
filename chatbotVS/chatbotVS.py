from re import U
from turtle import update
import telebot
import mysql.connector

# Подключение к базе данных
try:
    db = mysql.connector.connect(
        host="localhost",
        user="root",
        password="123456789",
        database="ChatBotDB"
    )
    cursor = db.cursor()
    print("Connected to MySQL database!")
except mysql.connector.Error as err:
    print(f"Error connecting to MySQL: {err}")

# Инициализация бота
bot = telebot.TeleBot('7499772603:AAHG70L316Ql7f-UWss0hTHiZsYnEMwRTjk')

# Клавиатурные кнопки
main_menu_markup = telebot.types.ReplyKeyboardMarkup(resize_keyboard=True)
main_menu_markup.row('Создать заметку', 'Посмотреть заметки')
main_menu_markup.row('Удалить заметку')

back_markup = telebot.types.ReplyKeyboardMarkup(resize_keyboard=True)
back_markup.row('Назад')

# Обработчик команды /start или /help
@bot.message_handler(commands=['start', 'help'])
def send_welcome(message):
    bot.reply_to(message, "Привет! Я бот для создания заметок. Используй меню для взаимодействия.", reply_markup=main_menu_markup)

# Обработчик команды "Создать заметку"
@bot.message_handler(func=lambda message: message.text == 'Создать заметку')
def create_note_start(message):
    bot.reply_to(message, "Введите имя заметки:")
    bot.register_next_step_handler(message, create_note_name)

def create_note_name(message):
    note_name = message.text
    user_id = message.from_user.id
    

    # Вставляем пользователя в таблицу User, если его еще нет
    cursor.execute("INSERT IGNORE INTO User (TelegramId, Username) VALUES (%s, %s)", (user_id, message.from_user.first_name))
    db.commit()

    # Получаем TelegramId пользователя
    tuser_id = user_id

    # Вставляем заметку в таблицу Note
    cursor.execute("INSERT INTO Note (TUserId, NoteName) VALUES (%s, %s)", (tuser_id, note_name))
    db.commit()

    bot.reply_to(message, f"Заметка '{note_name}' создана.", reply_markup=back_markup)
    bot.reply_to(message, f"Введите пункт заметки.", reply_markup=back_markup)
    

    # Ожидание добавления пунктов
    bot.register_next_step_handler(message, add_note_item, tuser_id, note_name)
def add_note_item(message, tuser_id, note_name):
    if message.text == 'Назад':
        bot.reply_to(message, "Вы вернулись в главное меню.", reply_markup=main_menu_markup)
        return

    description = message.text

    cursor.execute("SELECT NoteId FROM Note WHERE TUserId = %s AND NoteName = %s", (tuser_id, note_name))
    note_row = cursor.fetchone()
    note_id = note_row[0]

    cursor.execute("INSERT INTO ItemNote (NoteId, Description) VALUES (%s, %s)", (note_id, description))
    db.commit()

    bot.reply_to(message, f"Пункт '{description}' добавлен. Введите количество баллов за этот пункт:")
    bot.register_next_step_handler(message, add_points, note_id, tuser_id, note_name)

def add_points(message, note_id, tuser_id, note_name):
    tt = tuser_id
    nn = note_name
    try:
        points = int(message.text)
        cursor.execute("UPDATE ItemNote SET Points = %s WHERE ItemNoteId = LAST_INSERT_ID()", (points,))
        db.commit()
        bot.reply_to(message, f"Баллы за пункт обновлены на {points}.")
        if(message.text == 'Назад'):
            bot.reply_to(message, "Вы вернулись в главное меню.", reply_markup=main_menu_markup)
            return
        else:
            bot.reply_to(message, f"Введите следующий пункт заметки.")
            bot.register_next_step_handler(message, add_note_item, tt, nn)
            
    except ValueError:
        bot.reply_to(message, "Пожалуйста, введите число для количества баллов.")
        bot.register_next_step_handler(message, add_points, note_id)


user_selected_notes = {}

# Обработчик команды "Посмотреть заметки"
@bot.message_handler(func=lambda message: message.text == 'Посмотреть заметки')
def view_notes(message):
    user_id = message.from_user.id

    cursor.execute("SELECT NoteId, NoteName FROM Note WHERE TUserId = (SELECT TelegramId FROM User WHERE TelegramId = %s)", (user_id,))
    notes = cursor.fetchall()

    if not notes:
        bot.reply_to(message, "У вас пока нет заметок.", reply_markup=main_menu_markup)
        return

    markup = telebot.types.ReplyKeyboardMarkup(resize_keyboard=True)
    for note in notes:
        markup.add(f"{note[1]} ({calculate_points(note[0])})")
    markup.add("Назад")

    bot.reply_to(message, "Выберите заметку для просмотра:", reply_markup=markup)
    bot.register_next_step_handler(message, view_note_items)

def view_note_items(message):
    user_id = message.from_user.id
    selected_note = message.text.split(" (")[0]  # Используем разделитель " (" чтобы избежать ошибок при разбиении

    if message.text == 'Назад':
        bot.reply_to(message, "Вы вернулись в главное меню.", reply_markup=main_menu_markup)
        return

    cursor.execute("SELECT NoteId FROM Note WHERE NoteName = %s AND TUserId = (SELECT TelegramId FROM User WHERE TelegramId = %s)", (selected_note, user_id))
    note_row = cursor.fetchone()
    if not note_row:
        bot.reply_to(message, "Заметка не найдена.", reply_markup=main_menu_markup)
        return

    note_id = note_row[0]
    user_selected_notes[user_id] = note_id  # Сохраняем выбранную заметку для пользователя

    cursor.execute("SELECT ItemNoteId, Description, Points, IsCompleted FROM ItemNote WHERE NoteId = %s", (note_id,))
    items = cursor.fetchall()

    if not items:
        bot.reply_to(message, "В этой заметке пока нет пунктов.", reply_markup=main_menu_markup)
        return

    markupItems = telebot.types.ReplyKeyboardMarkup(resize_keyboard=True)
    response = f"Пункты в заметке '{selected_note}':\n"
    for item in items:
        item_id, description, points, is_completed = item
        status = "\U00002714" if is_completed else "\U0000274C"
        response += f"[{item_id}] {description} ({points} баллов, {status})\n"
        markupItems.add(telebot.types.KeyboardButton(f"{item_id}"))

    markupItems.add("Назад")

    bot.reply_to(message, response, reply_markup=markupItems)
    bot.register_next_step_handler(message, update_note_item)

def calculate_points(note_id):
    cursor.execute("SELECT Points, IsCompleted FROM ItemNote WHERE NoteId = %s", (note_id,))
    items = cursor.fetchall()

    total_points = sum(item[0] for item in items)
    completed_points = sum(item[0] for item in items if item[1])

    result = f"{completed_points}/{total_points}"
    return result

def update_note_item(message):
    user_id = message.from_user.id

    if message.text == "Назад":
        view_note_items(message)
        return

    item_id = message.text

    cursor.execute("SELECT IsCompleted FROM ItemNote WHERE ItemNoteId = %s", (item_id,))
    item = cursor.fetchone()

    if not item:
        bot.reply_to(message, "Пункт не найден.", reply_markup=main_menu_markup)
        return

    is_completed = item[0]
    new_status = not is_completed

    cursor.execute("UPDATE ItemNote SET IsCompleted = %s WHERE ItemNoteId = %s", (new_status, item_id))
    db.commit()

    status = "\U00002714" if new_status else "\U0000274C"
    bot.reply_to(message, f"Статус пункта обновлен: {status}")

    # Получаем текущую выбранную заметку для пользователя
    if user_id in user_selected_notes:
        note_id = user_selected_notes[user_id]
        cursor.execute("SELECT NoteName FROM Note WHERE NoteId = %s", (note_id,))
        note_name = cursor.fetchone()[0]
        # Обновляем список пунктов для текущей заметки
        view_note_items_with_note_id(message, note_id, note_name)
    else:
        view_notes(message)

def view_note_items_with_note_id(message, note_id, note_name):
    cursor.execute("SELECT ItemNoteId, Description, Points, IsCompleted FROM ItemNote WHERE NoteId = %s", (note_id,))
    items = cursor.fetchall()

    if not items:
        bot.reply_to(message, "В этой заметке пока нет пунктов.", reply_markup=main_menu_markup)
        return

    markupItems = telebot.types.ReplyKeyboardMarkup(resize_keyboard=True)
    response = f"Пункты в заметке '{note_name}':\n"
    for item in items:
        item_id, description, points, is_completed = item
        status = "\U00002714" if is_completed else "\U0000274C"
        response += f"[{item_id}] {description} ({points} баллов, {status})\n"
        markupItems.add(telebot.types.KeyboardButton(f"{item_id}"))

    markupItems.add("Назад")

    bot.reply_to(message, response, reply_markup=markupItems)
    bot.register_next_step_handler(message, update_note_item)

# Обработчик команды "Удалить заметку"
@bot.message_handler(func=lambda message: message.text == 'Удалить заметку')
def delete_note_start(message):
    user_id = message.from_user.id
    print(user_id)

    cursor.execute("SELECT NoteName FROM Note WHERE TUserId = %s", (user_id,))
    notes = cursor.fetchall()

    if not notes:
        bot.reply_to(message, "У вас нет заметок для удаления.", reply_markup=main_menu_markup)
        return

    markup = telebot.types.ReplyKeyboardMarkup(resize_keyboard=True)
    for note in notes:
        markup.add(note[0])

    bot.reply_to(message, "Выберите заметку для удаления:", reply_markup=markup)
    bot.register_next_step_handler(message, delete_note_confirm)

def delete_note_confirm(message):
    user_id = message.from_user.id
    note_name = message.text
    
    #Удаляем пункты заметки
    cursor.execute("DELETE FROM ItemNote WHERE NoteId = (SELECT NoteId FROM Note WHERE NoteName = %s AND TUserId = %s)", (note_name, user_id))
    
    cursor.execute("DELETE FROM Note WHERE NoteName = %s AND TUserId = %s", (note_name, user_id))
    db.commit()

    bot.reply_to(message, f"Заметка '{note_name}' удалена.", reply_markup=main_menu_markup)

# Запуск бота
bot.polling()
