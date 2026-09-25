import telebot
from telebot import types
import json
import os
from flask import Flask, request

# ================== SOZLAMALAR (Environment Variables) ==================
BOT_TOKEN = os.environ.get("BOT_TOKEN")
ADMIN_ID = int(os.environ.get("ADMIN_ID"))
CHANNEL_ID = int(os.environ.get("CHANNEL_ID"))
WEBHOOK_URL = os.environ.get("WEBHOOK_URL")   # Masalan: https://mybot.onrender.com

if not all([BOT_TOKEN, ADMIN_ID, CHANNEL_ID, WEBHOOK_URL]):
    raise ValueError("BOT_TOKEN, ADMIN_ID, CHANNEL_ID yoki WEBHOOK_URL topilmadi!")

bot = telebot.TeleBot(BOT_TOKEN)
app = Flask(__name__)

LESSONS_FILE = "lessons.json"

def load_lessons():
    if os.path.exists(LESSONS_FILE):
        with open(LESSONS_FILE, "r", encoding="utf-8") as f:
            return json.load(f)
    return {}

def save_lessons():
    with open(LESSONS_FILE, "w", encoding="utf-8") as f:
        json.dump(lessons, f, ensure_ascii=False, indent=2)

lessons = load_lessons()

# ================== MENYULAR ==================
def main_menu():
    markup = types.ReplyKeyboardMarkup(resize_keyboard=True)
    markup.add("📚 Darsliklar ro‘yxati")
    markup.add("ℹ️ Yordam")
    return markup

def admin_menu():
    markup = types.ReplyKeyboardMarkup(resize_keyboard=True)
    markup.add("➕ Yangi dars qo‘shish")
    markup.add("📋 Darsliklar ro‘yxati (Admin)")
    markup.add("🗑 Darsni o‘chirish")
    markup.add("🔙 Oddiy menyu")
    return markup

# ================== /start ==================
@bot.message_handler(commands=['start'])
def start(message):
    if message.from_user.id == ADMIN_ID:
        bot.send_message(message.chat.id, "Admin paneliga xush kelibsiz!", reply_markup=admin_menu())
    else:
        bot.send_message(message.chat.id, "Assalomu alaykum!\nDarsliklar botiga xush kelibsiz.", reply_markup=main_menu())

# ================== ADMIN: YANGI DARS ==================
@bot.message_handler(func=lambda m: m.from_user.id == ADMIN_ID and m.text == "➕ Yangi dars qo‘shish")
def add_lesson_prompt(message):
    bot.send_message(message.chat.id, "Kanalga joylagan dars postini menga **forward** qiling.")

@bot.message_handler(content_types=['video', 'document', 'photo', 'animation', 'audio', 'voice', 'video_note', 'text'],
                     func=lambda m: m.from_user.id == ADMIN_ID)
def handle_admin_messages(message):
    print("="*50)
    print("Yangi xabar keldi:")
    print("content_type:", message.content_type)
    print("forward_from_chat:", message.forward_from_chat)
    print("forward_from_message_id:", message.forward_from_message_id)
    print("forward_origin:", getattr(message, "forward_origin", None))
    print("="*50)

    if not message.forward_from_chat and not getattr(message, "forward_origin", None):
        return

    channel_id = None
    message_id = None

    if message.forward_from_chat:
        channel_id = message.forward_from_chat.id
        message_id = message.forward_from_message_id
    elif hasattr(message, "forward_origin") and message.forward_origin:
        if hasattr(message.forward_origin, "chat"):
            channel_id = message.forward_origin.chat.id
            message_id = message.forward_origin.message_id

    print("Aniqlangan channel_id:", channel_id)
    print("Aniqlangan message_id:", message_id)

    if channel_id != CHANNEL_ID:
        bot.send_message(message.chat.id, f"Bu post boshqa kanaldan.\nKutilgan: {CHANNEL_ID}\nKelgan: {channel_id}")
        return

    if not message_id:
        bot.send_message(message.chat.id, "Message ID aniqlanmadi.")
        return

    msg = bot.send_message(
        message.chat.id,
        f"✅ Post qabul qilindi!\nMessage ID: {message_id}\n\nEndi dars nomini yozing:"
    )
    bot.register_next_step_handler(msg, save_forwarded_lesson, message_id)

def save_forwarded_lesson(message, message_id):
    if message.from_user.id != ADMIN_ID:
        return

    title = message.text.strip()
    new_id = str(len(lessons) + 1)

    lessons[new_id] = {
        "title": title,
        "message_id": message_id
    }
    save_lessons()

    bot.send_message(
        message.chat.id,
        f"✅ Dars qo‘shildi!\nNomi: {title}\nID: {new_id}",
        reply_markup=admin_menu()
    )

# ================== ADMIN: RO‘YXAT VA O‘CHIRISH ==================
@bot.message_handler(func=lambda m: m.from_user.id == ADMIN_ID and m.text == "📋 Darsliklar ro‘yxati (Admin)")
def admin_list_lessons(message):
    if not lessons:
        bot.send_message(message.chat.id, "Hozircha darsliklar yo‘q.")
        return

    text = "📋 Barcha darsliklar:\n\n"
    for key, lesson in lessons.items():
        text += f"{key}. {lesson['title']} (msg_id: {lesson['message_id']})\n"
    bot.send_message(message.chat.id, text)

@bot.message_handler(func=lambda m: m.from_user.id == ADMIN_ID and m.text == "🗑 Darsni o‘chirish")
def delete_lesson_prompt(message):
    if not lessons:
        bot.send_message(message.chat.id, "O‘chirish uchun darslik yo‘q.")
        return

    markup = types.InlineKeyboardMarkup()
    for key, lesson in lessons.items():
        markup.add(types.InlineKeyboardButton(text=f"❌ {lesson['title']}", callback_data=f"del_{key}"))
    bot.send_message(message.chat.id, "O‘chirmoqchi bo‘lgan darsni tanlang:", reply_markup=markup)

@bot.callback_query_handler(func=lambda call: call.data.startswith("del_"))
def delete_lesson(call):
    if call.from_user.id != ADMIN_ID:
        return
    lesson_id = call.data.split("_")[1]
    if lesson_id in lessons:
        title = lessons[lesson_id]["title"]
        del lessons[lesson_id]
        save_lessons()
        bot.edit_message_text(f"✅ \"{title}\" o‘chirildi.", call.message.chat.id, call.message.message_id)
    else:
        bot.answer_callback_query(call.id, "Darslik topilmadi")

@bot.message_handler(func=lambda m: m.from_user.id == ADMIN_ID and m.text == "🔙 Oddiy menyu")
def back_to_user_menu(message):
    bot.send_message(message.chat.id, "Oddiy menyuga o‘tdingiz.", reply_markup=main_menu())

# ================== FOYDALANUVCHI ==================
@bot.message_handler(func=lambda m: m.text == "📚 Darsliklar ro‘yxati")
def show_lessons(message):
    if not lessons:
        bot.send_message(message.chat.id, "Hozircha darsliklar yo‘q.")
        return

    markup = types.InlineKeyboardMarkup()
    for key, lesson in lessons.items():
        markup.add(types.InlineKeyboardButton(text=lesson["title"], callback_data=f"lesson_{key}"))
    bot.send_message(message.chat.id, "Darslikni tanlang:", reply_markup=markup)

@bot.callback_query_handler(func=lambda call: call.data.startswith("lesson_"))
def send_lesson(call):
    lesson_id = call.data.split("_")[1]
    lesson = lessons.get(lesson_id)
    if not lesson:
        bot.answer_callback_query(call.id, "Darslik topilmadi")
        return
    try:
        bot.copy_message(
            chat_id=call.message.chat.id,
            from_chat_id=CHANNEL_ID,
            message_id=lesson["message_id"],
            protect_content=True
        )
        bot.answer_callback_query(call.id)
    except Exception as e:
        bot.send_message(call.message.chat.id, "Xatolik yuz berdi.")
        print(e)

@bot.message_handler(func=lambda m: m.text == "ℹ️ Yordam")
def help_msg(message):
    bot.send_message(message.chat.id, "Savollar bo‘lsa adminga yozing.")

# ================== WEBHOOK ==================
@app.route('/' + BOT_TOKEN, methods=['POST'])
def webhook():
    json_str = request.get_data().decode('utf-8')
    update = telebot.types.Update.de_json(json_str)
    bot.process_new_updates([update])
    return '', 200

@app.route('/')
def index():
    return "Bot ishlayapti!", 200

# ================== ISHGA TUSHIRISH ==================
if __name__ == "__main__":
    bot.remove_webhook()
    bot.set_webhook(url=WEBHOOK_URL.rstrip("/") + "/" + BOT_TOKEN)
    print(f"Webhook o‘rnatildi: {WEBHOOK_URL}/{BOT_TOKEN}")
    app.run(host="0.0.0.0", port=int(os.environ.get("PORT", 5000)))
