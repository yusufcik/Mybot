# -*- coding: utf-8 -*-
#
# KINO BOT - main.py
#
# ISHGA TUSHIRISHDAN OLDIN:
# 1) Pydroid 3 da Pip -> "pyTelegramBotAPI" ni o'rnating
#    (Pydroid ichidagi "Pip" bo'limidan yoki terminalda: pip install pyTelegramBotAPI)
# 2) Pastdagi BOT_TOKEN ga @BotFather dan olgan tokeningizni yozing
# 3) Botni kanallarga ADMIN qilib qo'shing (kanal qo'shish bo'limi ishlashi uchun shart)
#
# Ishlatilishi:
#   /start  -> oddiy foydalanuvchi rejimi, kino kodi yuboriladi
#   /admin  -> ushbu buyruqni yuborgan HAR QANDAY foydalanuvchi admin panelidan foydalana oladi

import sqlite3
import telebot
from telebot import types

BOT_TOKEN = "8939541620:AAHEejKQGkKd_5Y7QXZzZUUHZl8xqd_br0s"

bot = telebot.TeleBot(BOT_TOKEN)

conn = sqlite3.connect("kino_bot.db", check_same_thread=False)
cur = conn.cursor()

cur.execute("""CREATE TABLE IF NOT EXISTS users (
    user_id INTEGER PRIMARY KEY
)""")
cur.execute("""CREATE TABLE IF NOT EXISTS movies (
    code TEXT PRIMARY KEY,
    file_id TEXT,
    file_type TEXT
)""")
cur.execute("""CREATE TABLE IF NOT EXISTS channels (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    chat_id TEXT,
    link TEXT,
    title TEXT,
    type TEXT
)""")
cur.execute("""CREATE TABLE IF NOT EXISTS admins (
    user_id INTEGER PRIMARY KEY
)""")
conn.commit()

# Har bir foydalanuvchining joriy holatini saqlab turish uchun (xotirada)
user_states = {}


# ================= YORDAMCHI FUNKSIYALAR =================

def add_user(user_id):
    cur.execute("INSERT OR IGNORE INTO users (user_id) VALUES (?)", (user_id,))
    conn.commit()


def add_admin(user_id):
    cur.execute("INSERT OR IGNORE INTO admins (user_id) VALUES (?)", (user_id,))
    conn.commit()


def get_channels():
    cur.execute("SELECT id, chat_id, link, title, type FROM channels")
    return cur.fetchall()


def check_subscription(user_id):
    """Foydalanuvchi obuna bo'lmagan kanallar ro'yxatini qaytaradi."""
    not_subscribed = []
    for ch_id, chat_id, link, title, ch_type in get_channels():
        try:
            member = bot.get_chat_member(chat_id, user_id)
            if member.status in ["left", "kicked"]:
                not_subscribed.append((title, link))
        except Exception:
            # Bot kanalga admin qilib qo'shilmagan yoki chat_id noto'g'ri bo'lsa ham shu yerga tushadi
            not_subscribed.append((title, link))
    return not_subscribed


def subscription_keyboard(not_subscribed):
    kb = types.InlineKeyboardMarkup()
    for i, (title, link) in enumerate(not_subscribed, 1):
        kb.add(types.InlineKeyboardButton(f"{i}-kanal: {title}", url=link))
    kb.add(types.InlineKeyboardButton("✅ Tekshirish", callback_data="check_sub"))
    return kb


def admin_panel_keyboard():
    kb = types.ReplyKeyboardMarkup(resize_keyboard=True)
    kb.row("🎬 Kino qo'shish", "📢 Kanal qo'shish")
    kb.row("📣 Reklama", "📊 Statistika")
    kb.row("🗑 O'chirish")
    kb.row("/start")
    return kb


def clear_state(user_id):
    user_states.pop(user_id, None)


def get_state(user_id):
    return user_states.get(user_id, {}).get("state")


# ================= /start =================

@bot.message_handler(commands=["start"])
def start_handler(message):
    clear_state(message.from_user.id)
    add_user(message.from_user.id)
    not_subscribed = check_subscription(message.from_user.id)
    if not_subscribed:
        bot.send_message(
            message.chat.id,
            "Botdan foydalanish uchun quyidagi kanallarga obuna bo'ling:",
            reply_markup=subscription_keyboard(not_subscribed)
        )
        return
    bot.send_message(
        message.chat.id,
        f"Salom, {message.from_user.first_name}!\n\nKino kodini yuboring:",
        reply_markup=types.ReplyKeyboardRemove()
    )


@bot.callback_query_handler(func=lambda c: c.data == "check_sub")
def check_sub_callback(call):
    not_subscribed = check_subscription(call.from_user.id)
    if not_subscribed:
        bot.answer_callback_query(call.id, "Siz hali barcha kanallarga obuna bo'lmadingiz!", show_alert=True)
        return
    bot.answer_callback_query(call.id, "Obuna tasdiqlandi ✅")
    bot.send_message(
        call.message.chat.id,
        f"Salom, {call.from_user.first_name}!\n\nKino kodini yuboring:"
    )


# ================= /admin =================

@bot.message_handler(commands=["admin"])
def admin_handler(message):
    add_admin(message.from_user.id)
    user_states[message.from_user.id] = {"state": None, "data": {}}
    bot.send_message(message.chat.id, "Admin panelga xush kelibsiz!", reply_markup=admin_panel_keyboard())


# ================= KINO QO'SHISH =================

@bot.message_handler(func=lambda m: m.text == "🎬 Kino qo'shish")
def add_movie_start(message):
    user_states[message.from_user.id] = {"state": "waiting_movie_code", "data": {}}
    bot.send_message(message.chat.id, "Kino kodini yuboring (masalan: 346):")


@bot.message_handler(func=lambda m: get_state(m.from_user.id) == "waiting_movie_code")
def add_movie_code(message):
    code = message.text.strip()
    if not code.isdigit():
        bot.send_message(message.chat.id, "Kod faqat raqamlardan iborat bo'lishi kerak. Qaytadan yuboring:")
        return
    user_states[message.from_user.id]["data"]["code"] = code
    user_states[message.from_user.id]["state"] = "waiting_movie_file"
    bot.send_message(message.chat.id, "Endi kinoni yuboring:")


@bot.message_handler(content_types=["video", "document"],
                      func=lambda m: get_state(m.from_user.id) == "waiting_movie_file")
def add_movie_file(message):
    code = user_states[message.from_user.id]["data"]["code"]
    if message.content_type == "video":
        file_id = message.video.file_id
        file_type = "video"
    else:
        file_id = message.document.file_id
        file_type = "document"
    cur.execute("INSERT OR REPLACE INTO movies (code, file_id, file_type) VALUES (?, ?, ?)",
                (code, file_id, file_type))
    conn.commit()
    clear_state(message.from_user.id)
    bot.send_message(message.chat.id, f"Kino yuklandi kod {code}", reply_markup=admin_panel_keyboard())


# ================= KANAL QO'SHISH =================

@bot.message_handler(func=lambda m: m.text == "📢 Kanal qo'shish")
def add_channel_start(message):
    kb = types.InlineKeyboardMarkup()
    kb.row(
        types.InlineKeyboardButton("Ochiq kanal", callback_data="ch_open"),
        types.InlineKeyboardButton("Yopiq kanal", callback_data="ch_closed")
    )
    user_states[message.from_user.id] = {"state": None, "data": {}}
    bot.send_message(message.chat.id, "Kanal turini tanlang:", reply_markup=kb)


@bot.callback_query_handler(func=lambda c: c.data in ["ch_open", "ch_closed"])
def choose_channel_type(call):
    ch_type = "Ochiq" if call.data == "ch_open" else "Yopiq"
    user_states[call.from_user.id] = {"state": "waiting_channel_id", "data": {"type": ch_type}}
    bot.answer_callback_query(call.id)
    bot.send_message(
        call.message.chat.id,
        "Botni albatta kanalga ADMIN qiling.\n\n"
        "Endi kanal ID sini yuboring (masalan: -1001234567890):"
    )


@bot.message_handler(func=lambda m: get_state(m.from_user.id) == "waiting_channel_id")
def get_channel_id(message):
    user_states[message.from_user.id]["data"]["chat_id"] = message.text.strip()
    user_states[message.from_user.id]["state"] = "waiting_channel_link"
    bot.send_message(message.chat.id, "Endi kanal havolasini yuboring (masalan: https://t.me/kanal):")


@bot.message_handler(func=lambda m: get_state(m.from_user.id) == "waiting_channel_link")
def get_channel_link(message):
    user_states[message.from_user.id]["data"]["link"] = message.text.strip()
    user_states[message.from_user.id]["state"] = "waiting_channel_title"
    bot.send_message(message.chat.id, "Endi kanal nomini yuboring (foydalanuvchilarga shu nom ko'rsatiladi):")


@bot.message_handler(func=lambda m: get_state(m.from_user.id) == "waiting_channel_title")
def get_channel_title(message):
    data = user_states[message.from_user.id]["data"]
    title = message.text.strip()
    cur.execute("INSERT INTO channels (chat_id, link, title, type) VALUES (?, ?, ?, ?)",
                (data["chat_id"], data["link"], title, data["type"]))
    conn.commit()
    clear_state(message.from_user.id)
    bot.send_message(message.chat.id, f"Kanal qo'shildi: {title}", reply_markup=admin_panel_keyboard())


# ================= REKLAMA =================

@bot.message_handler(func=lambda m: m.text == "📣 Reklama")
def broadcast_start(message):
    user_states[message.from_user.id] = {"state": "waiting_broadcast", "data": {}}
    bot.send_message(message.chat.id, "Reklama uchun xabarni yuboring:")


@bot.message_handler(func=lambda m: get_state(m.from_user.id) == "waiting_broadcast",
                      content_types=["text", "photo", "video", "document"])
def broadcast_send(message):
    clear_state(message.from_user.id)
    cur.execute("SELECT user_id FROM users")
    users = cur.fetchall()
    success, fail = 0, 0
    for (uid,) in users:
        try:
            bot.copy_message(uid, message.chat.id, message.message_id)
            success += 1
        except Exception:
            fail += 1
    bot.send_message(
        message.chat.id,
        f"Reklama yuborildi!\n✅ Yuborildi: {success}\n❌ Yuborilmadi: {fail}",
        reply_markup=admin_panel_keyboard()
    )


# ================= STATISTIKA =================

@bot.message_handler(func=lambda m: m.text == "📊 Statistika")
def statistics(message):
    cur.execute("SELECT COUNT(*) FROM users")
    users_count = cur.fetchone()[0]
    cur.execute("SELECT COUNT(*) FROM movies")
    movies_count = cur.fetchone()[0]
    cur.execute("SELECT COUNT(*) FROM admins")
    admins_count = cur.fetchone()[0]
    text = (
        "📊 Statistika:\n\n"
        f"👤 Foydalanuvchilar soni: {users_count}\n"
        f"🎬 Kinolar soni: {movies_count}\n"
        f"👨‍💼 Adminlar soni: {admins_count}"
    )
    bot.send_message(message.chat.id, text, reply_markup=admin_panel_keyboard())


# ================= O'CHIRISH =================

@bot.message_handler(func=lambda m: m.text == "🗑 O'chirish")
def delete_channel_start(message):
    channels = get_channels()
    if not channels:
        bot.send_message(message.chat.id, "Qo'shilgan kanallar mavjud emas.", reply_markup=admin_panel_keyboard())
        return
    kb = types.InlineKeyboardMarkup()
    for ch_id, chat_id, link, title, ch_type in channels:
        kb.add(types.InlineKeyboardButton(f"❌ {title} ({ch_type})", callback_data=f"del_{ch_id}"))
    bot.send_message(message.chat.id, "O'chirmoqchi bo'lgan kanalni tanlang:", reply_markup=kb)


@bot.callback_query_handler(func=lambda c: c.data.startswith("del_"))
def delete_channel(call):
    ch_id = int(call.data.split("_")[1])
    cur.execute("DELETE FROM channels WHERE id = ?", (ch_id,))
    conn.commit()
    bot.answer_callback_query(call.id, "Kanal o'chirildi ✅")
    bot.send_message(call.message.chat.id, "Kanal muvaffaqiyatli o'chirildi.")


# ================= KINO KODI YUBORILGANDA (oddiy foydalanuvchi) =================

@bot.message_handler(
    func=lambda m: get_state(m.from_user.id) is None and m.text and m.text.strip().isdigit()
)
def send_movie(message):
    not_subscribed = check_subscription(message.from_user.id)
    if not_subscribed:
        bot.send_message(
            message.chat.id,
            "Botdan foydalanish uchun quyidagi kanallarga obuna bo'ling:",
            reply_markup=subscription_keyboard(not_subscribed)
        )
        return
    code = message.text.strip()
    cur.execute("SELECT file_id, file_type FROM movies WHERE code = ?", (code,))
    result = cur.fetchone()
    if result:
        file_id, file_type = result
        if file_type == "video":
            bot.send_video(message.chat.id, file_id)
        else:
            bot.send_document(message.chat.id, file_id)
    else:
        bot.send_message(message.chat.id, "Bunday kodli kino topilmadi ❌")


# ================= BOTNI ISHGA TUSHIRISH =================

print("Bot ishga tushdi...")
bot.infinity_polling(skip_pending=True)
