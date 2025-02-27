import os
import sqlite3
import asyncio
from datetime import datetime, timedelta
from aiogram import Bot, Dispatcher, types
from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton
from aiogram.utils import executor

# جلب التوكن من متغيرات البيئة
TOKEN = os.getenv("TOKEN")
ADMIN_USERNAME = "AmerDz0"  # اسم المطور

# إعداد البوت
bot = Bot(token=TOKEN)
dp = Dispatcher(bot)

# إنشاء قاعدة بيانات SQLite
conn = sqlite3.connect("bot_data.db")
cursor = conn.cursor()

cursor.execute("""
CREATE TABLE IF NOT EXISTS users (
    id INTEGER PRIMARY KEY, 
    username TEXT, 
    subscription_expiry INTEGER
)
""")

cursor.execute("""
CREATE TABLE IF NOT EXISTS bins (
    bin TEXT PRIMARY KEY, 
    bank TEXT, 
    country TEXT
)
""")
conn.commit()

# التحقق من الاشتراك
def check_subscription(user_id):
    cursor.execute("SELECT subscription_expiry FROM users WHERE id=?", (user_id,))
    result = cursor.fetchone()
    return result and result[0] > int(datetime.utcnow().timestamp())

# /start
@dp.message_handler(commands=['start'])
async def start(message: types.Message):
    await message.reply("👋 مرحبًا بك في بوت فحص البطاقات! استخدم /pay للاشتراك.")

# أمر الدفع /pay
@dp.message_handler(commands=['pay'])
async def pay(message: types.Message):
    keyboard = InlineKeyboardMarkup(row_width=2)
    keyboard.add(
        InlineKeyboardButton("اشتراك ساعتان - ⭐3", callback_data="sub_2h"),
        InlineKeyboardButton("اشتراك 4 ساعات - ⭐6", callback_data="sub_4h"),
        InlineKeyboardButton("اشتراك يوم - ⭐42", callback_data="sub_1d"),
        InlineKeyboardButton("اشتراك 3 أيام - ⭐126", callback_data="sub_3d")
    )
    await message.reply("💎 اختر اشتراكك:", reply_markup=keyboard)

# تفعيل الاشتراك
@dp.callback_query_handler(lambda call: call.data.startswith("sub_"))
async def subscribe(call: types.CallbackQuery):
    user_id = call.from_user.id
    duration_map = {
        "sub_2h": 2,
        "sub_4h": 4,
        "sub_1d": 24,
        "sub_3d": 72
    }
    duration = duration_map[call.data]
    expiry = int((datetime.utcnow() + timedelta(hours=duration)).timestamp())

    cursor.execute("INSERT OR REPLACE INTO users (id, username, subscription_expiry) VALUES (?, ?, ?)", 
                   (user_id, call.from_user.username, expiry))
    conn.commit()
    
    await call.message.answer(f"✅ تم تفعيل الاشتراك لمدة {duration} ساعة 🎉")
    await call.answer()

# فحص بطاقة واحدة otp/
@dp.message_handler(lambda message: message.text.startswith("otp/"))
async def check_card(message: types.Message):
    if not check_subscription(message.from_user.id):
        await message.reply("❌ تحتاج إلى اشتراك لاستخدام هذا الأمر.")
        return

    data = message.text.split(" ")[1]
    bin_number = data[:6]  

    cursor.execute("SELECT bank, country FROM bins WHERE bin=?", (bin_number,))
    result = cursor.fetchone()

    if result:
        bank, country = result
        await message.reply(f"✅ البطاقة شغالة!\n🏦 البنك: {bank}\n🌍 الدولة: {country}")
    else:
        await message.reply(f"❌ البطاقة غير صالحة.")

# توليد بطاقات gen/
@dp.message_handler(lambda message: message.text.startswith("gen/"))
async def generate_cards(message: types.Message):
    bin_number = message.text.split("/")[1]
    if not bin_number.isdigit() or len(bin_number) < 6:
        await message.reply("❌ يجب أن يكون BIN على الأقل 6 أرقام.")
        return

    cards = [f"{bin_number}{str(i).zfill(10)}|12|28|xxx" for i in range(50)]
    buttons = [InlineKeyboardButton("Check 🔍", callback_data=f"check_{bin_number}")]
    keyboard = InlineKeyboardMarkup(row_width=1).add(*buttons)

    await message.reply("\n".join(cards), reply_markup=keyboard)

# فحص البطاقات من الملف
@dp.message_handler(content_types=types.ContentType.DOCUMENT)
async def check_cards_from_file(message: types.Message):
    if not check_subscription(message.from_user.id):
        await message.reply("❌ تحتاج إلى اشتراك لفحص البطاقات.")
        return

    file_id = message.document.file_id
    file = await bot.get_file(file_id)
    file_path = file.file_path
    file_content = await bot.download_file(file_path)

    valid, invalid = 0, 0
    for line in file_content.decode().splitlines():
        bin_number = line.split("|")[0][:6]
        cursor.execute("SELECT bank, country FROM bins WHERE bin=?", (bin_number,))
        result = cursor.fetchone()

        if result:
            valid += 1
        else:
            invalid += 1

    keyboard = InlineKeyboardMarkup(row_width=2)
    keyboard.add(
        InlineKeyboardButton(f"✅ {valid}", callback_data="valid"),
        InlineKeyboardButton(f"✖️ {invalid}", callback_data="invalid")
    )

    await message.reply("📊 نتيجة الفحص:", reply_markup=keyboard)

# لوحة تحكم المطور
@dp.message_handler(commands=['admin'])
async def admin_panel(message: types.Message):
    if message.from_user.username != ADMIN_USERNAME:
        await message.reply("🚫 ليس لديك صلاحية للوصول إلى لوحة التحكم.")
        return

    keyboard = InlineKeyboardMarkup(row_width=2)
    keyboard.add(
        InlineKeyboardButton("🔄 تغيير الأسعار", callback_data="change_prices"),
        InlineKeyboardButton("🛠 صنع أكواد اشتراك", callback_data="generate_codes"),
        InlineKeyboardButton("📊 إحصائيات", callback_data="stats"),
        InlineKeyboardButton("💎 اشتراك لانهائي", callback_data="unlimited_sub")
    )
    
    await message.reply("⚙️ لوحة تحكم المطور:", reply_markup=keyboard)

# تشغيل البوت
if __name__ == "__main__":
    executor.start_polling(dp, skip_updates=True)