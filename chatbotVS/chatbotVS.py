import telebot
import mysql.connector

# Connect to MySQL database
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

# Initialize the Telegram bot with the given token
bot = telebot.TeleBot('YOUR_BOT_API_TOKEN_HERE')

# Define the main menu markup
main_menu_markup = telebot.types.ReplyKeyboardMarkup(resize_keyboard=True)
main_menu_markup.row('Создать заметку\U0001F4DC', 'Посмотреть заметки\U0001F50D')
main_menu_markup.row('Удалить заметку\U0001F5D1')

# Define the back button markup
back_markup = telebot.types.ReplyKeyboardMarkup(resize_keyboard=True)
back_markup.row('Назад')

# Handle the /start command to send a welcome message
@bot.message_handler(commands=['start'])
def send_welcome(message):
    bot.reply_to(message, "Я бот, который помогает отметить выполненные задачи\U0001F4DC. Если возникают вопросы, введите или вы хотите ознакомиться с руководством пользователя то введите команду /help. Используй меню для взаимодействия.", reply_markup=main_menu_markup)

# Handle the /help command to send the help message from a file
@bot.message_handler(commands=['help'])
def help_message(message):
    with open('./RM.txt', 'r') as file:
        help_text = file.read()
    bot.reply_to(message, help_text)

# Start creating a note
@bot.message_handler(func=lambda message: message.text == 'Создать заметку\U0001F4DC')
def create_note_start(message):
    bot.reply_to(message, "Введите имя заметки\U0000270F:")
    bot.register_next_step_handler(message, create_note_name)

# Handle the note name input and create a note
def create_note_name(message):
    note_name = message.text
    user_id = message.from_user.id
    
    # Insert user into User table if not exists
    cursor.execute("INSERT IGNORE INTO User (TelegramId, Username) VALUES (%s, %s)", (user_id, message.from_user.first_name))
    db.commit()
    
    print("Join user: ", user_id)

    tuser_id = user_id

    # Insert the new note into Note table
    cursor.execute("INSERT INTO Note (TUserId, NoteName) VALUES (%s, %s)", (tuser_id, note_name))
    db.commit()
    
    print("user: ", user_id, "create note: ", note_name)
    
    bot.reply_to(message, f"Заметка '{note_name}' создана\U0001F4BE.", reply_markup=back_markup)
    bot.reply_to(message, f"Введите пункт заметки\U0000270F.", reply_markup=back_markup)
    
    bot.register_next_step_handler(message, add_note_item, tuser_id, note_name)

# Handle adding an item to the note
def add_note_item(message, tuser_id, note_name):
    if message.text == 'Назад':
        bot.reply_to(message, "Вы вернулись в главное меню\U0001F519.", reply_markup=main_menu_markup)
        return

    description = message.text

    # Get the note ID from the Note table
    cursor.execute("SELECT NoteId FROM Note WHERE TUserId = %s AND NoteName = %s", (tuser_id, note_name))
    note_row = cursor.fetchone()
    note_id = note_row[0]

    # Insert the item into the ItemNote table
    cursor.execute("INSERT INTO ItemNote (NoteId, Description) VALUES (%s, %s)", (note_id, description))
    db.commit()
    
    print("user: ", tuser_id, "add item: ", description)

    bot.reply_to(message, f"Пункт '{description}' добавлен. Введите количество баллов за этот пункт\U0000270F:")
    bot.register_next_step_handler(message, add_points, note_id, tuser_id, note_name)

# Handle adding points to the note item
def add_points(message, note_id, tuser_id, note_name):
    tt = tuser_id
    nn = note_name
    try:
        points = int(message.text)
        # Update the ItemNote table with points
        cursor.execute("UPDATE ItemNote SET Points = %s WHERE ItemNoteId = LAST_INSERT_ID()", (points,))
        db.commit()
  
        print("user: ", tuser_id, "add points: ", points)

        bot.reply_to(message, f"Баллы за пункт обновлены на {points}.\U0001F504")
        if(message.text == 'Назад'):
            bot.reply_to(message, "Вы вернулись в главное меню.\U0001F519", reply_markup=main_menu_markup)
            return
        else:
            bot.reply_to(message, f"Введите следующий пункт или нажмите 'Назад'.")
            bot.register_next_step_handler(message, add_note_item, tt, nn)
            
    except ValueError:
        bot.reply_to(message, "Пожалуйста, введите число для количества баллов.\U0000270F")
        bot.register_next_step_handler(message, add_points, note_id)

user_selected_notes = {}

# Handle viewing notes
@bot.message_handler(func=lambda message: message.text == 'Посмотреть заметки\U0001F50D')
def view_notes(message):
    user_id = message.from_user.id

    cursor.execute("SELECT NoteId, NoteName FROM Note WHERE TUserId = (SELECT TelegramId FROM User WHERE TelegramId = %s)", (user_id,))
    notes = cursor.fetchall()

    if not notes:
        bot.reply_to(message, "У вас пока нет заметок.\U0001F5FF", reply_markup=main_menu_markup)
        return

    markup = telebot.types.ReplyKeyboardMarkup(resize_keyboard=True)
    for note in notes:
        markup.add(f"{note[1]} ({calculate_points(note[0])})")
    markup.add("Назад")

    bot.reply_to(message, "Выберите заметку для просмотра\U0001F440:", reply_markup=markup)
    bot.register_next_step_handler(message, view_note_items)

# Handle viewing items of a selected note
def view_note_items(message):
    user_id = message.from_user.id
    selected_note = message.text.split(" (")[0]

    if message.text == 'Назад':
        bot.reply_to(message, "Вы вернулись в главное меню.\U0001F519", reply_markup=main_menu_markup)
        return

    cursor.execute("SELECT NoteId FROM Note WHERE NoteName = %s AND TUserId = (SELECT TelegramId FROM User WHERE TelegramId = %s)", (selected_note, user_id))
    note_row = cursor.fetchone()
    if not note_row:
        bot.reply_to(message, "Заметка не найдена.\U0001F5FF", reply_markup=main_menu_markup)
        return

    note_id = note_row[0]
    user_selected_notes[user_id] = note_id  

    cursor.execute("SELECT ItemNoteId, Description, Points, IsCompleted FROM ItemNote WHERE NoteId = %s", (note_id,))
    items = cursor.fetchall()

    if not items:
        bot.reply_to(message, "В этой заметке пока нет пунктов.\U0001F5FF", reply_markup=main_menu_markup)
        return

    markupItems = telebot.types.ReplyKeyboardMarkup(resize_keyboard=True)
    response = f"'{selected_note}':\n"
    
    i = 1;
    id_arr = []
        
    for item in items:
        item_id, description, points, is_completed = item
        id_arr.append(item_id)
        status = "\U00002714" if is_completed else "\U0000274C"
        user_id = item_id - (item_id - i)
        response += f"[{user_id}] {description} ({points} баллов, {status})\n"
        markupItems.add(telebot.types.KeyboardButton(f"{user_id}"))
        i += 1

    markupItems.add("Назад")
    
    bot.reply_to(message, response, reply_markup=markupItems)
    bot.register_next_step_handler(message, update_note_item, id_arr)

# Calculate total and completed points for a note
def calculate_points(note_id):
    cursor.execute("SELECT Points, IsCompleted FROM ItemNote WHERE NoteId = %s", (note_id,))
    items = cursor.fetchall()

    total_points = sum(item[0] for item in items)
    completed_points = sum(item[0] for item in items if item[1])

    result = f"{completed_points}/{total_points}"
    return result

# Handle updating the status of a note item
def update_note_item(message, id_arr):
    user_id = message.from_user.id

    if message.text == "Назад":
        view_note_items(message)
        return

    item_id = id_arr[int(message.text) - 1]

    cursor.execute("SELECT IsCompleted FROM ItemNote WHERE ItemNoteId = %s", (item_id,))
    item = cursor.fetchone()

    if not item:
        bot.reply_to(message, "Пункт не найден.\U0001F5FF", reply_markup=main_menu_markup)
        return

    is_completed = item[0]
    new_status = not is_completed

    cursor.execute("UPDATE ItemNote SET IsCompleted = %s WHERE ItemNoteId = %s", (new_status, item_id))
    db.commit()

    status = "\U00002714" if new_status else "\U0000274C"
    bot.reply_to(message, f"Статус пункта обновлен: {status}")

    if user_id in user_selected_notes:
        note_id = user_selected_notes[user_id]
        cursor.execute("SELECT NoteName FROM Note WHERE NoteId = %s", (note_id,))
        note_name = cursor.fetchone()[0]
        view_note_items_with_note_id(message, note_id, note_name)
    else:
        view_notes(message)

# View items of a note by note ID
def view_note_items_with_note_id(message, note_id, note_name):
    cursor.execute("SELECT ItemNoteId, Description, Points, IsCompleted FROM ItemNote WHERE NoteId = %s", (note_id,))
    items = cursor.fetchall()

    if not items:
        bot.reply_to(message, "В этой заметке пока нет пунктов.\U0001F5FF", reply_markup=main_menu_markup)
        return

    markupItems = telebot.types.ReplyKeyboardMarkup(resize_keyboard=True)
    response = f"'{note_name}':\n"
    
    id_arr = []
    i = 1;
        
    for item in items:
        item_id, description, points, is_completed = item
        id_arr.append(item_id)
        status = "\U00002714" if is_completed else "\U0000274C"
        user_id = item_id - (item_id - i)
        response += f"[{user_id}] {description} ({points} баллов, {status})\n"
        markupItems.add(telebot.types.KeyboardButton(f"{user_id}"))
        i += 1

    markupItems.add("Назад")

    bot.reply_to(message, response, reply_markup=markupItems)
    bot.register_next_step_handler(message, update_note_item, id_arr)

# Handle the process of deleting a note
@bot.message_handler(func=lambda message: message.text == 'Удалить заметку\U0001F5D1')
def delete_note_start(message):
    user_id = message.from_user.id
    print(user_id)

    cursor.execute("SELECT NoteName FROM Note WHERE TUserId = %s", (user_id,))
    notes = cursor.fetchall()

    if not notes:
        bot.reply_to(message, "У вас нет заметок для удаления.\U0001F5FF", reply_markup=main_menu_markup)
        return

    markup = telebot.types.ReplyKeyboardMarkup(resize_keyboard=True)
    for note in notes:
        markup.add(note[0])
    markup.add("Назад")

    bot.reply_to(message, "Выберите заметку для удаления\U0001F6AE:", reply_markup=markup)
    bot.register_next_step_handler(message, delete_note_confirm)

# Confirm and delete the selected note
def delete_note_confirm(message):
    if message.text == "Назад":
        view_note_items(message)
        return    
    user_id = message.from_user.id
    note_name = message.text
    
    # Delete items and note from the database
    cursor.execute("DELETE FROM ItemNote WHERE NoteId = (SELECT NoteId FROM Note WHERE NoteName = %s AND TUserId = %s)", (note_name, user_id))
    
    cursor.execute("DELETE FROM Note WHERE NoteName = %s AND TUserId = %s", (note_name, user_id))
    db.commit()

    print("user_id: ", user_id, "delete note: ", note_name) 
    
    bot.reply_to(message, f"Заметка '{note_name}' удалена.\U000026B0", reply_markup=main_menu_markup)

# Start polling for new messages
bot.polling()
