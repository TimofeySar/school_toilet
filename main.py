import telebot
from telebot import types
import sqlite3

token = "7379983182:AAEQwTf8b89NgK6Op3cA8QGVD4nozoOKosI"
bot = telebot.TeleBot(token)

conn = sqlite3.connect('voting_bot.db', check_same_thread=False)
cursor = conn.cursor()

cursor.execute('''
CREATE TABLE IF NOT EXISTS votes (
    chat_id INTEGER,
    candidate_id INTEGER,
    username TEXT,
    PRIMARY KEY (chat_id, candidate_id)
)
''')

def add_candidate(name, description, photo):
    cursor.execute('INSERT INTO candidates (name, description, photo) VALUES (?, ?, ?)', (name, description, photo))
    conn.commit()



@bot.message_handler(commands=['start'])
def welcome(message):
    bot.send_message(message.chat.id, "Привет! Я бот для голосования.\nДля начала голосования введите /vote")


@bot.message_handler(commands=['vote'])
def show_candidates(message):
    cursor.execute('SELECT id, name, description, photo, votes FROM candidates')
    candidates = cursor.fetchall()

    if candidates:
        send_candidate(message.chat.id, candidates, 0)
    else:
        bot.send_message(message.chat.id, "Список кандидатов пуст.")


def send_candidate(chat_id, candidates, index):
    candidate = candidates[index]
    candidate_id = candidate[0]
    name = candidate[1]
    description = candidate[2]
    photo = candidate[3]
    votes = candidate[4]

    markup = types.InlineKeyboardMarkup(row_width=2)
    navigation_buttons = []
    if index > 0:
        markup.add(types.InlineKeyboardButton("<<", callback_data=f"prev_{index - 1}"))
    if index < len(candidates) - 1:
        markup.add(types.InlineKeyboardButton(">>", callback_data=f"next_{index + 1}"))

    if navigation_buttons:
        markup.add(*navigation_buttons)

    vote_button = types.InlineKeyboardButton(f"Голосовать (Голосов: {votes})", callback_data=f"vote_{candidate_id}")
    markup.add(vote_button)

    bot.send_photo(chat_id, open(photo, 'rb'),
                   caption=f"{name}\n{description}\nГолосов: {votes}",
                   reply_markup=markup)


@bot.callback_query_handler(func=lambda call: call.data.startswith("prev_") or call.data.startswith("next_"))
def handle_navigation(call):
    index = int(call.data.split('_')[1])

    cursor.execute('SELECT id, name, description, photo, votes FROM candidates')
    candidates = cursor.fetchall()

    if 0 <= index < len(candidates):
        bot.edit_message_media(media=types.InputMediaPhoto(open(candidates[index][3], 'rb'),
                                                           caption=f"{candidates[index][1]}\n{candidates[index][2]}\nГолосов: {candidates[index][4]}"),
                               chat_id=call.message.chat.id,
                               message_id=call.message.message_id,
                               reply_markup=create_navigation_markup(candidates, index))


def create_navigation_markup(candidates, index):
    markup = types.InlineKeyboardMarkup()
    if index > 0:
        markup.add(types.InlineKeyboardButton("<<", callback_data=f"prev_{index - 1}"))
    if index < len(candidates) - 1:
        markup.add(types.InlineKeyboardButton(">>", callback_data=f"next_{index + 1}"))

    vote_button = types.InlineKeyboardButton(f"Голосовать (Голосов: {candidates[index][4]})",
                                             callback_data=f"vote_{candidates[index][0]}")
    markup.add(vote_button)

    return markup


@bot.callback_query_handler(func=lambda call: call.data.startswith('vote_'))
def handle_vote(call):
    candidate_id = int(call.data.split('_')[1])
    user_id = call.message.chat.id
    username = call.message.chat.username

    cursor.execute('SELECT * FROM votes WHERE chat_id = ?', (user_id,))
    vote_exists = cursor.fetchone()

    if vote_exists:
        bot.answer_callback_query(call.id, "Вы уже голосовали за этого кандидата!")
    else:
        cursor.execute('INSERT INTO votes (chat_id, candidate_id, username) VALUES (?, ?, ?)',
                       (user_id, candidate_id, username))
        cursor.execute('UPDATE candidates SET votes = votes + 1 WHERE id = ?', (candidate_id,))
        conn.commit()

        cursor.execute('SELECT name, votes, photo FROM candidates WHERE id = ?', (candidate_id,))
        candidate_name, votes, photo = cursor.fetchone()

        bot.send_photo(call.message.chat.id, open(photo, 'rb'),
                       caption=f"Вы проголосовали за {candidate_name}!\nТекущее количество голосов: {votes}")

        bot.answer_callback_query(call.id, "Ваш голос учтен!")


def is_admin(username):
    cursor.execute('SELECT * FROM admins WHERE username = ?', (username,))
    return cursor.fetchone() is not None


@bot.message_handler(commands=['admin'])
def admin_menu(message):
    if is_admin(message.chat.username):
        markup = types.InlineKeyboardMarkup()
        view_votes_button = types.InlineKeyboardButton(text="Просмотр всех голосов", callback_data="view_votes")
        markup.add(view_votes_button)

        bot.send_message(message.chat.id, "Добро пожаловать в админское меню:", reply_markup=markup)
    else:
        bot.send_message(message.chat.id, "У вас нет прав доступа к этой команде.")


@bot.callback_query_handler(func=lambda call: call.data == "view_votes")
def view_votes(call):
    if is_admin(call.message.chat.username):
        cursor.execute(
            '''SELECT votes.username, candidates.name
            FROM votes
            JOIN candidates ON votes.candidate_id = candidates.id''')
        results = cursor.fetchall()

        if results:
            result_message = "Список проголосовавших пользователей и их выбор:\n\n"
            for row in results:
                chat_id, candidate_name = row
                result_message += f"Пользователь {chat_id} проголосовал за {candidate_name}\n"
            bot.send_message(call.message.chat.id, result_message)
        else:
            bot.send_message(call.message.chat.id, "Пока нет данных о голосах.")

    else:
        bot.send_message(call.message.chat.id, "У вас нет прав для использования этой команды.")


bot.infinity_polling()
