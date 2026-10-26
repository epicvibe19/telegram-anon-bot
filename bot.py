import os
import threading
from flask import Flask
import telebot
from telebot import types

TOKEN = '7734660929:AAEPt_gwDDAx6CYm8kBL1nH-NxgqZuzpRCY'
ADMIN_ID = 5101402699

bot = telebot.TeleBot(TOKEN)

# Временная память для ответов и черного списка
admin_reply_targets = {}
blacklisted_users = set()

@bot.message_handler(commands=['start'])
def send_welcome(message):
    if message.from_user.id == ADMIN_ID:
        bot.reply_to(message, "👑 Привет, хозяин! Бот для анонимных сообщений запущен.\n\n📋 Команда для управления банами: /banlist")
    else:
        # Проверяем, не в бане ли пользователь
        if message.from_user.id in blacklisted_users:
            bot.reply_to(message, "❌ Вы заблокированы навсегда в этом боте.")
            return
        bot.reply_to(message, "👋 Привет! Напиши мне любое сообщение (или отправь стикер/фото/голос), и оно анонимно уйдет владельцу бота.")

# Команда для просмотра черного списка и разбана
@bot.message_handler(commands=['banlist'], func=lambda message: message.from_user.id == ADMIN_ID)
def show_banlist(message):
    if not blacklisted_users:
        bot.reply_to(message, "📂 Черный список пуст.")
        return
    
    bot.reply_to(message, "🚫 **Список заблокированных пользователей:**", parse_mode="Markdown")
    
    for user_id in list(blacklisted_users):
        try:
            user_info = bot.get_chat(user_id)
            name = user_info.first_name or "Без имени"
            username = f"@{user_info.username}" if user_info.username else "нет юзернейма"
            user_desc = f"👤 {name} ({username}) [ID: `{user_id}`]"
        except Exception:
            user_desc = f"👤 Пользователь [ID: `{user_id}`]"
        
        # Кнопка разбана для каждого из списка
        markup = types.InlineKeyboardMarkup()
        markup.add(types.InlineKeyboardButton("✅ Разблокировать", callback_data=f"unban_{user_id}"))
        
        bot.send_message(ADMIN_ID, user_desc, parse_mode="Markdown", reply_markup=markup)

# Обработка анонимных сообщений
@bot.message_handler(content_types=['text', 'photo', 'voice', 'video', 'document', 'sticker'], 
                    func=lambda message: message.from_user.id != ADMIN_ID)
def handle_anonymous_message(message):
    user_id = message.from_user.id
    
    if user_id in blacklisted_users:
        bot.reply_to(message, "❌ Вы заблокированы навсегда в этом боте.")
        return
    
    is_banned = user_id in blacklisted_users
    ban_button_text = "✅ Разблокировать" if is_banned else "🚫 Заблокировать"

    markup = types.InlineKeyboardMarkup()
    btn_reveal = types.InlineKeyboardButton("👀 Кто отправил?", callback_data=f"reveal_{user_id}")
    btn_reply = types.InlineKeyboardButton("✍️ Ответить", callback_data=f"reply_{user_id}")
    btn_ban = types.InlineKeyboardButton(ban_button_text, callback_data=f"ban_{user_id}")
    markup.add(btn_reveal, btn_reply)
    markup.add(btn_ban)
    
    bot.send_message(ADMIN_ID, "📩 **Новое анонимное сообщение:**", parse_mode="Markdown")
    bot.copy_message(ADMIN_ID, message.chat.id, message.message_id, reply_markup=markup)
    bot.reply_to(message, "✅ Ваше анонимное сообщение успешно доставлено!")

# Обработка нажатий на инлайн-кнопки
@bot.callback_query_handler(func=lambda call: True)
def callback_query(call):
    if call.from_user.id != ADMIN_ID:
        bot.answer_callback_query(call.id, "❌ Доступ запрещен!", show_alert=True)
        return

    data = call.data
    
    if data.startswith("reveal_"):
        user_id = data.split("_")[1]
        try:
            user_info = bot.get_chat(user_id)
            username = f"@{user_info.username}" if user_info.username else "нет юзернейма"
            name = user_info.first_name or "Без имени"
            
            bot.answer_callback_query(
                call.id, 
                f"👤 Отправитель:\nИмя: {name}\nUsername: {username}\nID: {user_id}", 
                show_alert=True
            )
        except Exception as e:
            bot.answer_callback_query(call.id, f"Ошибка: {e}", show_alert=True)

    elif data.startswith("reply_"):
        user_id = data.split("_")[1]
        admin_reply_targets[call.from_user.id] = int(user_id)
        bot.send_message(ADMIN_ID, "✍️ Напишите ответ следующим сообщением (текст, стикер, фото или голос):")
        bot.answer_callback_query(call.id)

    elif data.startswith("ban_"):
        user_id = int(data.split("_")[1])
        
        if user_id in blacklisted_users:
            blacklisted_users.remove(user_id)
            bot.answer_callback_query(call.id, "✅ Пользователь разблокирован!", show_alert=True)
            bot.send_message(ADMIN_ID, f"🔓 Пользователь с ID `{user_id}` был разблокирован.", parse_mode="Markdown")
        else:
            blacklisted_users.add(user_id)
            bot.answer_callback_query(call.id, "🚫 Пользователь заблокирован навсегда!", show_alert=True)
            bot.send_message(ADMIN_ID, f"⚠️ Пользователь с ID `{user_id}` заблокирован навсегда.", parse_mode="Markdown")

        # Обновляем кнопку под сообщением
        try:
            is_banned = user_id in blacklisted_users
            new_ban_text = "✅ Разблокировать" if is_banned else "🚫 Заблокировать"
            
            markup = types.InlineKeyboardMarkup()
            markup.add(
                types.InlineKeyboardButton("👀 Кто отправил?", callback_data=f"reveal_{user_id}"),
                types.InlineKeyboardButton("✍️ Ответить", callback_data=f"reply_{user_id}")
            )
            markup.add(types.InlineKeyboardButton(new_ban_text, callback_data=f"ban_{user_id}"))
            
            bot.edit_message_reply_markup(chat_id=ADMIN_ID, message_id=call.message.message_id, reply_markup=markup)
        except Exception:
            pass

    elif data.startswith("unban_"):
        user_id = int(data.split("_")[1])
        if user_id in blacklisted_users:
            blacklisted_users.remove(user_id)
            bot.answer_callback_query(call.id, "✅ Пользователь успешно разблокирован из списка!", show_alert=True)
            try:
                bot.delete_message(chat_id=ADMIN_ID, message_id=call.message.message_id)
            except Exception:
                pass
            bot.send_message(ADMIN_ID, f"🔓 Пользователь `{user_id}` удален из черного списка через /banlist.", parse_mode="Markdown")

# Обработка вашего ответа пользователю
@bot.message_handler(content_types=['text', 'photo', 'voice', 'video', 'document', 'sticker'], 
                    func=lambda message: message.from_user.id == ADMIN_ID)
def handle_admin_reply(message):
    admin_id = message.from_user.id
    if admin_id in admin_reply_targets:
        target_user_id = admin_reply_targets[admin_id]
        try:
            bot.send_message(target_user_id, "💌 **Ответ от владельца:**", parse_mode="Markdown")
            bot.copy_message(target_user_id, message.chat.id, message.message_id)
            bot.reply_to(message, "✅ Ваш ответ успешно отправлен пользователю!")
        except Exception as e:
            bot.reply_to(message, "❌ Не удалось отправить ответ (возможно, пользователь заблокировал бота).")
        
        del admin_reply_targets[admin_id]


# --- МИНИ-СЕРВЕР ДЛЯ RENDER ---
app = Flask(__name__)

@app.route('/')
def home():
    return "Bot is running!"

def run_flask():
    port = int(os.environ.get("PORT", 10000))
    app.run(host="0.0.0.0", port=port)

if __name__ == "__main__":
    # Запускаем Flask в отдельном потоке, чтобы он занимал порт для Render
    flask_thread = threading.Thread(target=run_flask)
    flask_thread.start()

    print("Бот запущен и готов к работе...")
    bot.infinity_polling()
