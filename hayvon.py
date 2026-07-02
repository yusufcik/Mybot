# -*- coding: utf-8 -*-
"""
🐣 VIRTUAL PET TELEGRAM BOT
Pydroid 3 uchun tayyorlangan.

O'RNATISH (Pydroid 3 ichida):
    1. Pydroid 3 -> Pip -> qidiruvga "pyTelegramBotAPI" deb yozib o'rnating.
    2. Shu faylni saqlang (masalan bot.py nomi bilan).
    3. Pastdagi TOKEN = "..." qatoriga @BotFather dan olgan tokeningizni qo'ying.
    4. ADMIN_IDS ro'yxatiga o'z Telegram ID raqamingizni yozing
       (ID ni bilish uchun @userinfobot ga /start yozing).
    5. Faylni ishga tushiring (Run tugmasi).
"""

import sqlite3
import time
import random
from datetime import datetime, timedelta

import telebot
from telebot import types

# ============================================================
# SOZLAMALAR (shu joyni o'zgartiring)
# ============================================================
TOKEN = "8727953270:AAGAdprvvzZ2Qt1JfrRAhvCFXWQ4eFC7lu0"          # @BotFather dan olingan token
ADMIN_IDS = [7060092076]                          # O'z Telegram ID raqamingiz
DB_NAME = "petbot.db"

bot = telebot.TeleBot(TOKEN)

# ============================================================
# DATABASE
# ============================================================
def db():
    conn = sqlite3.connect(DB_NAME)
    conn.row_factory = sqlite3.Row
    return conn


def init_db():
    conn = db()
    conn.execute("""
        CREATE TABLE IF NOT EXISTS users (
            user_id INTEGER PRIMARY KEY,
            username TEXT,
            pet_name TEXT DEFAULT 'Pet',
            hunger INTEGER DEFAULT 100,
            energy INTEGER DEFAULT 100,
            happiness INTEGER DEFAULT 100,
            xp INTEGER DEFAULT 0,
            level INTEGER DEFAULT 1,
            coins INTEGER DEFAULT 100,
            last_daily TEXT,
            last_feed TEXT,
            last_play TEXT,
            last_sleep TEXT,
            join_date TEXT
        )
    """)
    conn.commit()
    conn.close()


def get_user(user_id, username=None):
    conn = db()
    row = conn.execute("SELECT * FROM users WHERE user_id=?", (user_id,)).fetchone()
    if row is None:
        conn.execute(
            "INSERT INTO users (user_id, username, join_date) VALUES (?,?,?)",
            (user_id, username or "noma'lum", datetime.now().isoformat())
        )
        conn.commit()
        row = conn.execute("SELECT * FROM users WHERE user_id=?", (user_id,)).fetchone()
    conn.close()
    return row


def update_user(user_id, **fields):
    conn = db()
    keys = ", ".join([f"{k}=?" for k in fields])
    values = list(fields.values()) + [user_id]
    conn.execute(f"UPDATE users SET {keys} WHERE user_id=?", values)
    conn.commit()
    conn.close()


def all_users():
    conn = db()
    rows = conn.execute("SELECT * FROM users").fetchall()
    conn.close()
    return rows


def clamp(value, low=0, high=100):
    return max(low, min(high, value))


def add_xp(user_id, amount):
    u = get_user(user_id)
    xp = u["xp"] + amount
    level = u["level"]
    needed = level * 100
    leveled_up = False
    while xp >= needed:
        xp -= needed
        level += 1
        needed = level * 100
        leveled_up = True
    update_user(user_id, xp=xp, level=level)
    return level, leveled_up


def cooldown_ok(last_time_str, minutes):
    if not last_time_str:
        return True, 0
    last_time = datetime.fromisoformat(last_time_str)
    diff = datetime.now() - last_time
    remaining = timedelta(minutes=minutes) - diff
    if remaining.total_seconds() <= 0:
        return True, 0
    return False, int(remaining.total_seconds() // 60) + 1


# ============================================================
# KLAVIATURALAR
# ============================================================
def main_menu(user_id):
    kb = types.ReplyKeyboardMarkup(resize_keyboard=True, row_width=2)
    kb.add(
        types.KeyboardButton("🎮 O'ynash"), types.KeyboardButton("🍖 Ovqat berish"),
        types.KeyboardButton("😴 Uxlatish"), types.KeyboardButton("📊 Holati"),
        types.KeyboardButton("⭐ XP va Level"), types.KeyboardButton("🪙 Tangalar"),
        types.KeyboardButton("🛒 Do'kon"), types.KeyboardButton("🎁 Kunlik bonus"),
        types.KeyboardButton("🏆 Reyting"), types.KeyboardButton("✏️ Ism qo'yish"),
    )
    return kb


def admin_menu():
    kb = types.ReplyKeyboardMarkup(resize_keyboard=True, row_width=2)
    kb.add(
        types.KeyboardButton("📢 Broadcast"),
        types.KeyboardButton("👥 Userlar statistikasi"),
        types.KeyboardButton("⬅️ Asosiy menyu"),
    )
    return kb


def shop_menu():
    kb = types.InlineKeyboardMarkup(row_width=1)
    kb.add(
        types.InlineKeyboardButton("🍎 Ovqat (+30 to'yinganlik) - 20 tanga", callback_data="buy_food"),
        types.InlineKeyboardButton("🧸 O'yinchoq (+25 xursandchilik) - 30 tanga", callback_data="buy_toy"),
        types.InlineKeyboardButton("⚡ Energy Drink (+40 energiya) - 25 tanga", callback_data="buy_energy"),
        types.InlineKeyboardButton("🎩 Maxsus aksessuar (+50 XP) - 60 tanga", callback_data="buy_xp"),
    )
    return kb


# ============================================================
# /start
# ============================================================
@bot.message_handler(commands=["start"])
def cmd_start(message):
    user_id = message.from_user.id
    get_user(user_id, message.from_user.username)
    bot.send_message(
        message.chat.id,
        "🐣 <b>Virtual Pet</b> botiga xush kelibsiz!\n\n"
        "Sizning virtual uy hayvoningiz paydo bo'ldi. Uni boqing, o'ynating, "
        "uxlating va level oshiring!\n\n"
        "Quyidagi menyudan foydalaning 👇",
        parse_mode="HTML",
        reply_markup=main_menu(user_id)
    )


# ============================================================
# ✏️ ISM QO'YISH
# ============================================================
@bot.message_handler(func=lambda m: m.text == "✏️ Ism qo'yish")
def ask_pet_name(message):
    msg = bot.send_message(message.chat.id, "Uy hayvoningizga qanday ism qo'ymoqchisiz? Yozing:")
    bot.register_next_step_handler(msg, save_pet_name)


def save_pet_name(message):
    name = message.text.strip()[:20]
    update_user(message.from_user.id, pet_name=name)
    bot.send_message(message.chat.id, f"✅ Ajoyib! Endi uy hayvoningizning ismi: <b>{name}</b>",
                      parse_mode="HTML", reply_markup=main_menu(message.from_user.id))


# ============================================================
# 🎮 O'YNASH
# ============================================================
@bot.message_handler(func=lambda m: m.text == "🎮 O'ynash")
def play(message):
    user_id = message.from_user.id
    u = get_user(user_id)
    ok, wait = cooldown_ok(u["last_play"], 15)
    if not ok:
        bot.send_message(message.chat.id, f"⏳ {u['pet_name']} charchagan, {wait} daqiqadan keyin qayta o'ynang.")
        return
    if u["energy"] < 15:
        bot.send_message(message.chat.id, f"😩 {u['pet_name']} juda charchagan! Avval uxlatib oling (😴 Uxlatish).")
        return

    happiness = clamp(u["happiness"] + 15)
    energy = clamp(u["energy"] - 15)
    coins_won = random.randint(3, 10)
    update_user(user_id, happiness=happiness, energy=energy,
                coins=u["coins"] + coins_won, last_play=datetime.now().isoformat())
    level, leveled_up = add_xp(user_id, 10)

    text = (f"🎮 {u['pet_name']} bilan o'ynadingiz!\n"
            f"😊 Xursandchilik: +15\n⚡ Energiya: -15\n🪙 +{coins_won} tanga\n⭐ +10 XP")
    if leveled_up:
        text += f"\n\n🎉 Tabriklaymiz! Level {level} ga yetdingiz!"
    bot.send_message(message.chat.id, text)


# ============================================================
# 🍖 OVQAT BERISH
# ============================================================
@bot.message_handler(func=lambda m: m.text == "🍖 Ovqat berish")
def feed(message):
    user_id = message.from_user.id
    u = get_user(user_id)
    ok, wait = cooldown_ok(u["last_feed"], 20)
    if not ok:
        bot.send_message(message.chat.id, f"⏳ {u['pet_name']} hali och emas. {wait} daqiqadan keyin urinib ko'ring.")
        return
    hunger = clamp(u["hunger"] + 25)
    update_user(user_id, hunger=hunger, last_feed=datetime.now().isoformat())
    level, leveled_up = add_xp(user_id, 5)
    text = f"🍖 {u['pet_name']} ovqatlandi!\n🍗 To'yinganlik: +25\n⭐ +5 XP"
    if leveled_up:
        text += f"\n\n🎉 Level {level} ga yetdingiz!"
    bot.send_message(message.chat.id, text)


# ============================================================
# 😴 UXLATISH
# ============================================================
@bot.message_handler(func=lambda m: m.text == "😴 Uxlatish")
def sleep(message):
    user_id = message.from_user.id
    u = get_user(user_id)
    ok, wait = cooldown_ok(u["last_sleep"], 30)
    if not ok:
        bot.send_message(message.chat.id, f"⏳ {u['pet_name']} hali uyg'oq. {wait} daqiqadan keyin urinib ko'ring.")
        return
    energy = clamp(u["energy"] + 40)
    update_user(user_id, energy=energy, last_sleep=datetime.now().isoformat())
    bot.send_message(message.chat.id, f"😴 {u['pet_name']} yaxshi dam oldi!\n⚡ Energiya: +40")


# ============================================================
# 📊 HOLATI
# ============================================================
@bot.message_handler(func=lambda m: m.text == "📊 Holati")
def status(message):
    u = get_user(message.from_user.id)

    def bar(value):
        filled = value // 10
        return "🟩" * filled + "⬜" * (10 - filled)

    text = (
        f"📊 <b>{u['pet_name']}ning holati</b>\n\n"
        f"🍗 To'yinganlik: {u['hunger']}/100\n{bar(u['hunger'])}\n\n"
        f"⚡ Energiya: {u['energy']}/100\n{bar(u['energy'])}\n\n"
        f"😊 Xursandchilik: {u['happiness']}/100\n{bar(u['happiness'])}\n"
    )
    bot.send_message(message.chat.id, text, parse_mode="HTML")


# ============================================================
# ⭐ XP VA LEVEL
# ============================================================
@bot.message_handler(func=lambda m: m.text == "⭐ XP va Level")
def xp_level(message):
    u = get_user(message.from_user.id)
    needed = u["level"] * 100
    bot.send_message(
        message.chat.id,
        f"⭐ <b>Level:</b> {u['level']}\n"
        f"📈 <b>XP:</b> {u['xp']} / {needed}\n"
        f"Keyingi levelgacha: {needed - u['xp']} XP qoldi",
        parse_mode="HTML"
    )


# ============================================================
# 🪙 TANGALAR
# ============================================================
@bot.message_handler(func=lambda m: m.text == "🪙 Tangalar")
def coins(message):
    u = get_user(message.from_user.id)
    bot.send_message(message.chat.id, f"🪙 Sizda hozir <b>{u['coins']}</b> tanga bor.", parse_mode="HTML")


# ============================================================
# 🛒 DO'KON
# ============================================================
@bot.message_handler(func=lambda m: m.text == "🛒 Do'kon")
def shop(message):
    bot.send_message(message.chat.id, "🛒 <b>Do'kon</b>\nXarid qilmoqchi bo'lgan narsangizni tanlang:",
                      parse_mode="HTML", reply_markup=shop_menu())


@bot.callback_query_handler(func=lambda call: call.data.startswith("buy_"))
def buy_item(call):
    user_id = call.from_user.id
    u = get_user(user_id)
    items = {
        "buy_food": ("🍎 Ovqat", 20, {"hunger": clamp(u["hunger"] + 30)}),
        "buy_toy": ("🧸 O'yinchoq", 30, {"happiness": clamp(u["happiness"] + 25)}),
        "buy_energy": ("⚡ Energy Drink", 25, {"energy": clamp(u["energy"] + 40)}),
        "buy_xp": ("🎩 Maxsus aksessuar", 60, None),
    }
    name, cost, fields = items[call.data]

    if u["coins"] < cost:
        bot.answer_callback_query(call.id, "❌ Tanga yetarli emas!", show_alert=True)
        return

    update_user(user_id, coins=u["coins"] - cost)
    if fields:
        update_user(user_id, **fields)
        extra = ""
    else:
        level, leveled_up = add_xp(user_id, 50)
        extra = f"\n⭐ +50 XP" + (f"\n🎉 Level {level}!" if leveled_up else "")

    bot.answer_callback_query(call.id, f"✅ {name} sotib olindi!")
    bot.send_message(call.message.chat.id, f"✅ Siz <b>{name}</b> sotib oldingiz!{extra}", parse_mode="HTML")


# ============================================================
# 🎁 KUNLIK BONUS
# ============================================================
@bot.message_handler(func=lambda m: m.text == "🎁 Kunlik bonus")
def daily_bonus(message):
    user_id = message.from_user.id
    u = get_user(user_id)
    ok, wait_min = cooldown_ok(u["last_daily"], 24 * 60)
    if not ok:
        hours = wait_min // 60
        mins = wait_min % 60
        bot.send_message(message.chat.id, f"⏳ Kunlik bonusni allaqachon oldingiz.\nKeyingisi: {hours} soat {mins} daqiqadan keyin.")
        return

    bonus = random.randint(30, 80)
    update_user(user_id, coins=u["coins"] + bonus, last_daily=datetime.now().isoformat())
    bot.send_message(message.chat.id, f"🎁 Kunlik bonusingiz: <b>+{bonus} tanga</b>!\nErtaga qayta keling 😉", parse_mode="HTML")


# ============================================================
# 🏆 REYTING
# ============================================================
@bot.message_handler(func=lambda m: m.text == "🏆 Reyting")
def leaderboard(message):
    conn = db()
    rows = conn.execute("SELECT username, pet_name, level, xp FROM users ORDER BY level DESC, xp DESC LIMIT 10").fetchall()
    conn.close()

    if not rows:
        bot.send_message(message.chat.id, "Hozircha reytingda hech kim yo'q.")
        return

    text = "🏆 <b>TOP 10 REYTING</b>\n\n"
    medals = ["🥇", "🥈", "🥉"]
    for i, r in enumerate(rows):
        medal = medals[i] if i < 3 else f"{i+1}."
        text += f"{medal} {r['pet_name']} (@{r['username']}) — Level {r['level']}, {r['xp']} XP\n"

    bot.send_message(message.chat.id, text, parse_mode="HTML")


# ============================================================
# 👑 ADMIN PANEL  (/admin buyrug'i orqali ochiladi)
# ============================================================
@bot.message_handler(commands=["admin"])
def admin_panel(message):
    user_id = message.from_user.id
    if user_id not in ADMIN_IDS:
        bot.send_message(message.chat.id, "⛔ Sizda admin huquqi yo'q.")
        return
    bot.send_message(message.chat.id, "👑 <b>Admin panelga xush kelibsiz</b>", parse_mode="HTML",
                      reply_markup=admin_menu())


@bot.message_handler(func=lambda m: m.text == "⬅️ Asosiy menyu")
def back_to_main(message):
    bot.send_message(message.chat.id, "⬅️ Asosiy menyu", reply_markup=main_menu(message.from_user.id))


# ---- 👥 Userlar statistikasi ----
@bot.message_handler(func=lambda m: m.text == "👥 Userlar statistikasi")
def user_stats(message):
    if message.from_user.id not in ADMIN_IDS:
        return
    users = all_users()
    total = len(users)
    total_coins = sum(u["coins"] for u in users)
    avg_level = round(sum(u["level"] for u in users) / total, 1) if total else 0

    bot.send_message(
        message.chat.id,
        f"👥 <b>Userlar statistikasi</b>\n\n"
        f"👤 Jami foydalanuvchilar: {total}\n"
        f"🪙 Umumiy tangalar: {total_coins}\n"
        f"⭐ O'rtacha level: {avg_level}",
        parse_mode="HTML"
    )


# ---- 📢 Broadcast ----
@bot.message_handler(func=lambda m: m.text == "📢 Broadcast")
def ask_broadcast(message):
    if message.from_user.id not in ADMIN_IDS:
        return
    msg = bot.send_message(message.chat.id, "📢 Barcha foydalanuvchilarga yubormoqchi bo'lgan xabaringizni yozing:")
    bot.register_next_step_handler(msg, do_broadcast)


def do_broadcast(message):
    if message.from_user.id not in ADMIN_IDS:
        return
    text = message.text
    users = all_users()
    sent, failed = 0, 0
    for u in users:
        try:
            bot.send_message(u["user_id"], f"📢 <b>E'lon:</b>\n\n{text}", parse_mode="HTML")
            sent += 1
            time.sleep(0.05)  # flood limitga tushmaslik uchun
        except Exception:
            failed += 1
    bot.send_message(message.chat.id, f"✅ Yuborildi: {sent}\n❌ Yuborilmadi: {failed}")


# ============================================================
# BOTNI ISHGA TUSHIRISH
# ============================================================
if __name__ == "__main__":
    init_db()
    print("Bot ishga tushdi...")
    bot.infinity_polling(skip_pending=True)
