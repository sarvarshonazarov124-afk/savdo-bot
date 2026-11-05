
import asyncio
import sqlite3
from aiogram import Bot, Dispatcher, F
from aiogram.filters import CommandStart, Command
from aiogram.types import (
    Message, CallbackQuery,
    ReplyKeyboardMarkup, KeyboardButton,
    InlineKeyboardMarkup, InlineKeyboardButton,
    ReplyKeyboardRemove
)

# ==================================================
# 1. SOZLAMALAR
# ==================================================

TOKEN = "9230325202:AAHl4HlZRBSxPHSepATFFnWIXpakCl8R83I"
ADMIN_ID = 640707683 # Telegram ID raqamingizni yozing

bot = Bot(token=TOKEN)
dp = Dispatcher()

db = sqlite3.connect("savdo.db")
db.execute("PRAGMA foreign_keys = ON")
cursor = db.cursor()

cursor.execute("""
CREATE TABLE IF NOT EXISTS products (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    category TEXT NOT NULL,
    name TEXT NOT NULL,
    price INTEGER NOT NULL
)
""")

cursor.execute("""
CREATE TABLE IF NOT EXISTS cart (
    user_id INTEGER,
    product_id INTEGER,
    quantity INTEGER,
    PRIMARY KEY(user_id, product_id)
)
""")

db.commit()

# Namunaviy mahsulotlar faqat baza bo'sh bo'lsa qo'shiladi
cursor.execute("SELECT COUNT(*) FROM products")

if cursor.fetchone()[0] == 0:
    sample_products = [
        ("Sement", "Portland sement 50 kg", 65000),
        ("Sement", "Oq sement 25 kg", 90000),
        ("Bo'yoq", "Oq emulsiya 10 kg", 85000),
        ("Bo'yoq", "Akril bo'yoq", 60000),
        ("Quvur", "Plastik quvur", 15000),
        ("Quvur", "Kanalizatsiya quvuri", 25000)
    ]

    cursor.executemany(
        "INSERT INTO products(category,name,price) VALUES(?,?,?)",
        sample_products
    )
    db.commit()


# ==================================================
# 2. ASOSIY MENYU
# ==================================================

def main_menu():
    return ReplyKeyboardMarkup(
        keyboard=[
            [
                KeyboardButton(text="🛍 Katalog"),
                KeyboardButton(text="🛒 Savatcha")
            ],
            [
                KeyboardButton(text="🔎 Qidiruv"),
                KeyboardButton(text="📞 Aloqa")
            ]
        ],
        resize_keyboard=True,
        input_field_placeholder="Bo'limni tanlang..."
    )


def home_keyboard():
    return InlineKeyboardMarkup(inline_keyboard=[
        [
            InlineKeyboardButton(
                text="🛍 Katalog",
                callback_data="catalog"
            )
        ],
        [
            InlineKeyboardButton(
                text="🛒 Savatcha",
                callback_data="cart"
            )
        ]
    ])


def back_button():
    return InlineKeyboardMarkup(inline_keyboard=[
        [
            InlineKeyboardButton(
                text="🏠 Bosh menyu",
                callback_data="home"
            )
        ]
    ])


# ==================================================
# 3. KATEGORIYALAR
# ==================================================

# Katalogda ko'rsatiladigan asosiy kategoriyalar.
# Eski bazadagi "Quvurlar" nomi ham "Quvur" sifatida taniladi.
CATEGORY_ALIASES = {
    "Sement": ["Sement"],
    "Bo'yoq": ["Bo'yoq"],
    "Quvur": ["Quvur", "Quvurlar"]
}

CATEGORY_ICONS = {
    "Sement": "🧱",
    "Bo'yoq": "🎨",
    "Quvur": "🚰"
}


def get_categories():
    available = []
    for category, aliases in CATEGORY_ALIASES.items():
        marks = ",".join("?" for _ in aliases)
        cursor.execute(
            f"SELECT COUNT(*) FROM products WHERE category IN ({marks})",
            aliases
        )
        if cursor.fetchone()[0] > 0:
            available.append(category)
    return available


def categories_keyboard():
    categories = get_categories()
    buttons = []

    for i in range(0, len(categories), 2):
        row = []
        for category in categories[i:i + 2]:
            icon = CATEGORY_ICONS.get(category, "📦")
            row.append(
                InlineKeyboardButton(
                    text=f"{icon} {category}",
                    callback_data=f"cat|{category}|0"
                )
            )
        buttons.append(row)

    buttons.append([
        InlineKeyboardButton(
            text="🏠 Bosh menyu",
            callback_data="home"
        )
    ])

    return InlineKeyboardMarkup(inline_keyboard=buttons)


# ==================================================
# 4. MAHSULOTLAR SAHIFASI
# ==================================================

PAGE_SIZE = 6


async def show_products(message, category, offset=0, edit=False):
    aliases = CATEGORY_ALIASES.get(category, [category])
    marks = ",".join("?" for _ in aliases)
    cursor.execute(
        f"SELECT COUNT(*) FROM products WHERE category IN ({marks})",
        aliases
    )
    total = cursor.fetchone()[0]

    if total == 0:
        text = "Bu kategoriyada hozircha mahsulot yo'q."
        keyboard = InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(
                text="⬅️ Kategoriyalar",
                callback_data="catalog"
            )]
        ])

        if edit:
            await message.edit_text(text, reply_markup=keyboard)
        else:
            await message.answer(text, reply_markup=keyboard)
        return

    cursor.execute(f"""
        SELECT id, name, price
        FROM products
        WHERE category IN ({marks})
        ORDER BY id DESC
        LIMIT ? OFFSET ?
    """, (*aliases, PAGE_SIZE, offset))

    products = cursor.fetchall()

    buttons = []

    for product_id, name, price in products:
        buttons.append([
            InlineKeyboardButton(
                text=f"📦 {name} | {price:,} so'm",
                callback_data=f"prod|{product_id}|{category}|{offset}"
            )
        ])

    navigation = []

    if offset > 0:
        navigation.append(
            InlineKeyboardButton(
                text="⬅️ Oldingi",
                callback_data=f"cat|{category}|{max(0, offset-PAGE_SIZE)}"
            )
        )

    if offset + PAGE_SIZE < total:
        navigation.append(
            InlineKeyboardButton(
                text="Keyingi ➡️",
                callback_data=f"cat|{category}|{offset+PAGE_SIZE}"
            )
        )

    if navigation:
        buttons.append(navigation)

    buttons.append([
        InlineKeyboardButton(
            text="⬅️ Kategoriyalar",
            callback_data="catalog"
        )
    ])

    page = offset // PAGE_SIZE + 1
    pages = (total + PAGE_SIZE - 1) // PAGE_SIZE

    text = (
        f"📦 {category.upper()}\n"
        "━━━━━━━━━━━━━━\n"
        f"Mahsulotlar: {total} ta\n"
        f"Sahifa: {page}/{pages}\n\n"
        "Kerakli mahsulotni tanlang:"
    )

    keyboard = InlineKeyboardMarkup(inline_keyboard=buttons)

    if edit:
        await message.edit_text(text, reply_markup=keyboard)
    else:
        await message.answer(text, reply_markup=keyboard)


# ==================================================
# 5. START
# ==================================================

@dp.message(CommandStart())
async def start(message: Message):
    await message.answer(
        "🏗️ SAVDO-SOTIQ\n"
        "━━━━━━━━━━━━━━━━\n"
        "QURILISH MATERIALLARI MARKAZI\n\n"
        "Assalomu alaykum!\n"
        "Bizning do'konimizga xush kelibsiz.\n\n"
        "🧱 Sifatli mahsulotlar\n"
        "💰 Qulay narxlar\n"
        "🚚 Buyurtma berish imkoniyati\n\n"
        "👇 Kerakli bo'limni tanlang:",
        reply_markup=main_menu()
    )


@dp.message(Command("myid"))
async def get_my_id(message: Message):
    await message.answer(
        f"Telegram ID: {message.from_user.id}"
    )


# ==================================================
# 6. KATALOG
# ==================================================

@dp.message(F.text == "🛍 Katalog")
async def catalog_message(message: Message):
    await message.answer(
        "📚 MAHSULOTLAR KATALOGI\n\n"
        "Kerakli kategoriyani tanlang:",
        reply_markup=categories_keyboard()
    )


@dp.callback_query(F.data == "catalog")
async def catalog_callback(call: CallbackQuery):
    await call.message.edit_text(
        "📚 MAHSULOTLAR KATALOGI\n\n"
        "Kerakli kategoriyani tanlang:",
        reply_markup=categories_keyboard()
    )
    await call.answer()


@dp.callback_query(F.data.startswith("cat|"))
async def category_callback(call: CallbackQuery):
    _, category, offset = call.data.split("|", 2)

    await show_products(
        call.message,
        category,
        int(offset),
        edit=True
    )
    await call.answer()


# ==================================================
# 7. MAHSULOT MA'LUMOTI
# ==================================================

@dp.callback_query(F.data.startswith("prod|"))
async def product_callback(call: CallbackQuery):
    _, product_id, category, offset = call.data.split("|", 3)

    cursor.execute(
        "SELECT name, price FROM products WHERE id=?",
        (int(product_id),)
    )
    product = cursor.fetchone()

    if not product:
        await call.answer("Mahsulot topilmadi!", show_alert=True)
        return

    name, price = product

    keyboard = InlineKeyboardMarkup(inline_keyboard=[
        [
            InlineKeyboardButton(
                text="➕ Savatchaga qo'shish",
                callback_data=f"add|{product_id}"
            )
        ],
        [
            InlineKeyboardButton(
                text="⬅️ Orqaga",
                callback_data=f"cat|{category}|{offset}"
            )
        ]
    ])

    await call.message.edit_text(
        "📦 MAHSULOT MA'LUMOTI\n"
        "━━━━━━━━━━━━━━━━\n\n"
        f"🧱 Nomi: {name}\n"
        f"💰 Narxi: {price:,} so'm\n\n"
        "Savatchaga qo'shish uchun tugmani bosing.",
        reply_markup=keyboard
    )

    await call.answer()


# ==================================================
# 8. SAVATCHAGA QO'SHISH
# ==================================================

@dp.callback_query(F.data.startswith("add|"))
async def add_to_cart(call: CallbackQuery):
    product_id = int(call.data.split("|")[1])
    user_id = call.from_user.id

    cursor.execute(
        "SELECT id FROM products WHERE id=?",
        (product_id,)
    )

    if not cursor.fetchone():
        await call.answer("Mahsulot topilmadi!", show_alert=True)
        return

    cursor.execute("""
        INSERT INTO cart(user_id, product_id, quantity)
        VALUES (?, ?, 1)
        ON CONFLICT(user_id, product_id)
        DO UPDATE SET quantity=quantity+1
    """, (user_id, product_id))

    db.commit()

    await call.answer("✅ Savatchaga qo'shildi!")


# ==================================================
# 9. SAVATCHA
# ==================================================

async def show_cart(target, user_id, edit=False):
    cursor.execute("""
        SELECT p.id, p.name, p.price, c.quantity
        FROM cart c
        JOIN products p ON p.id=c.product_id
        WHERE c.user_id=?
        ORDER BY p.name
    """, (user_id,))

    items = cursor.fetchall()

    if not items:
        text = "🛒 SAVATCHA\n\nSavatchangiz hozircha bo'sh."
        keyboard = InlineKeyboardMarkup(inline_keyboard=[
            [
                InlineKeyboardButton(
                    text="🛍 Katalog",
                    callback_data="catalog"
                )
            ]
        ])

        if edit:
            await target.edit_text(text, reply_markup=keyboard)
        else:
            await target.answer(text, reply_markup=keyboard)
        return

    total = 0
    buttons = []

    text = "🛒 SAVATCHANGIZ\n━━━━━━━━━━━━━━━━\n"

    for product_id, name, price, quantity in items:
        subtotal = price * quantity
        total += subtotal

        text += (
            f"\n📦 {name}\n"
            f"   {price:,} × {quantity} = {subtotal:,} so'm\n"
        )

        buttons.append([
            InlineKeyboardButton(
                text=f"➖ {name}",
                callback_data=f"minus|{product_id}"
            ),
            InlineKeyboardButton(
                text=f"{quantity} dona",
                callback_data="nothing"
            ),
            InlineKeyboardButton(
                text="➕",
                callback_data=f"plus|{product_id}"
            )
        ])

        buttons.append([
            InlineKeyboardButton(
                text=f"🗑 O'chirish: {name}",
                callback_data=f"remove|{product_id}"
            )
        ])

    text += (
        "\n━━━━━━━━━━━━━━━━\n"
        f"💰 JAMI: {total:,} so'm"
    )

    buttons.append([
        InlineKeyboardButton(
            text="✅ Buyurtma berish",
            callback_data="checkout"
        )
    ])

    buttons.append([
        InlineKeyboardButton(
            text="🛍 Katalogga qaytish",
            callback_data="catalog"
        )
    ])

    keyboard = InlineKeyboardMarkup(inline_keyboard=buttons)

    if edit:
        await target.edit_text(text, reply_markup=keyboard)
    else:
        await target.answer(text, reply_markup=keyboard)


@dp.message(F.text == "🛒 Savatcha")
async def cart_message(message: Message):
    await show_cart(message, message.from_user.id)


@dp.callback_query(F.data == "cart")
async def cart_callback(call: CallbackQuery):
    await show_cart(call.message, call.from_user.id, edit=True)
    await call.answer()


@dp.callback_query(F.data == "nothing")
async def nothing_callback(call: CallbackQuery):
    await call.answer()


# ==================================================
# 10. SAVATCHA MIQDORLARI
# ==================================================

@dp.callback_query(F.data.startswith("plus|"))
async def plus_item(call: CallbackQuery):
    product_id = int(call.data.split("|")[1])

    cursor.execute("""
        UPDATE cart SET quantity=quantity+1
        WHERE user_id=? AND product_id=?
    """, (call.from_user.id, product_id))

    db.commit()

    await show_cart(call.message, call.from_user.id, edit=True)
    await call.answer("Miqdor oshirildi")


@dp.callback_query(F.data.startswith("minus|"))
async def minus_item(call: CallbackQuery):
    product_id = int(call.data.split("|")[1])

    cursor.execute("""
        SELECT quantity FROM cart
        WHERE user_id=? AND product_id=?
    """, (call.from_user.id, product_id))

    result = cursor.fetchone()

    if result:
        if result[0] <= 1:
            cursor.execute("""
                DELETE FROM cart
                WHERE user_id=? AND product_id=?
            """, (call.from_user.id, product_id))
        else:
            cursor.execute("""
                UPDATE cart SET quantity=quantity-1
                WHERE user_id=? AND product_id=?
            """, (call.from_user.id, product_id))

    db.commit()

    await show_cart(call.message, call.from_user.id, edit=True)
    await call.answer("Miqdor yangilandi")


@dp.callback_query(F.data.startswith("remove|"))
async def remove_item(call: CallbackQuery):
    product_id = int(call.data.split("|")[1])

    cursor.execute("""
        DELETE FROM cart
        WHERE user_id=? AND product_id=?
    """, (call.from_user.id, product_id))

    db.commit()

    await show_cart(call.message, call.from_user.id, edit=True)
    await call.answer("Mahsulot o'chirildi")


# ==================================================
# 11. BUYURTMA VA TELEFON RAQAMI
# ==================================================

waiting_contact = set()


@dp.callback_query(F.data == "checkout")
async def checkout(call: CallbackQuery):
    user_id = call.from_user.id

    cursor.execute(
        "SELECT COUNT(*) FROM cart WHERE user_id=?",
        (user_id,)
    )

    if cursor.fetchone()[0] == 0:
        await call.answer("Savatcha bo'sh!", show_alert=True)
        return

    waiting_contact.add(user_id)

    keyboard = ReplyKeyboardMarkup(
        keyboard=[
            [
                KeyboardButton(
                    text="📱 Telefon raqamimni yuborish",
                    request_contact=True
                )
            ],
            [
                KeyboardButton(text="❌ Bekor qilish")
            ]
        ],
        resize_keyboard=True,
        one_time_keyboard=True
    )

    await call.message.answer(
        "📞 Buyurtmani rasmiylashtirish uchun "
        "telefon raqamingizni yuboring.",
        reply_markup=keyboard
    )

    await call.answer()


@dp.message(F.text == "❌ Bekor qilish")
async def cancel_order(message: Message):
    waiting_contact.discard(message.from_user.id)

    await message.answer(
        "Buyurtma bekor qilindi.",
        reply_markup=main_menu()
    )


@dp.message(F.contact)
async def receive_contact(message: Message):
    user_id = message.from_user.id

    if user_id not in waiting_contact:
        return

    if message.contact.user_id != user_id:
        await message.answer(
            "Iltimos, o'zingizning telefon raqamingizni yuboring."
        )
        return

    waiting_contact.discard(user_id)

    cursor.execute("""
        SELECT p.name, p.price, c.quantity
        FROM cart c
        JOIN products p ON p.id=c.product_id
        WHERE c.user_id=?
    """, (user_id,))

    items = cursor.fetchall()

    if not items:
        await message.answer(
            "Savatcha bo'sh.",
            reply_markup=main_menu()
        )
        return

    total = sum(
        price * quantity
        for name, price, quantity in items
    )

    order = (
        "🛍 YANGI BUYURTMA\n"
        "━━━━━━━━━━━━━━━━\n"
        f"👤 Mijoz: {message.from_user.full_name}\n"
        f"🆔 ID: {user_id}\n"
        f"📞 Telefon: {message.contact.phone_number}\n\n"
    )

    for name, price, quantity in items:
        order += (
            f"📦 {name}\n"
            f"   {quantity} dona × {price:,} so'm\n"
        )

    order += f"\n💰 JAMI: {total:,} so'm"

    if ADMIN_ID == 0:
        waiting_contact.add(user_id)
        await message.answer(
            "Admin ID sozlanmagan. Bot egasiga murojaat qiling.",
            reply_markup=main_menu()
        )
        return

    try:
        await bot.send_message(ADMIN_ID, order)
    except Exception:
        waiting_contact.add(user_id)
        await message.answer(
            "Buyurtma yuborilmadi. Admin sozlamalarini tekshirish kerak.",
            reply_markup=main_menu()
        )
        return

    cursor.execute(
        "DELETE FROM cart WHERE user_id=?",
        (user_id,)
    )
    db.commit()

    await message.answer(
        "✅ BUYURTMANGIZ QABUL QILINDI!\n\n"
        "Tez orada siz bilan bog'lanamiz.\n"
        "Xaridingiz uchun rahmat!",
        reply_markup=main_menu()
    )


# ==================================================
# 12. QIDIRUV
# ==================================================

waiting_search = set()


@dp.message(F.text == "🔎 Qidiruv")
async def search_start(message: Message):
    waiting_search.add(message.from_user.id)

    await message.answer(
        "🔎 Mahsulot nomini yozing:\n"
        "Masalan: sement, kabel, shifer"
    )


@dp.message(
    F.text,
    lambda message: message.from_user.id in waiting_search
)
async def search_products(message: Message):
    user_id = message.from_user.id
    waiting_search.discard(user_id)

    query = message.text.strip()

    cursor.execute("""
        SELECT id, name, price, category
        FROM products
        WHERE name LIKE ?
        ORDER BY name
        LIMIT 15
    """, (f"%{query}%",))

    results = cursor.fetchall()

    if not results:
        await message.answer(
            "❌ Bunday mahsulot topilmadi.",
            reply_markup=main_menu()
        )
        return

    buttons = []

    for product_id, name, price, category in results:
        buttons.append([
            InlineKeyboardButton(
                text=f"{name} — {price:,} so'm",
                callback_data=f"prod|{product_id}|{category}|0"
            )
        ])

    await message.answer(
        f"🔎 Qidiruv natijalari: {len(results)} ta",
        reply_markup=InlineKeyboardMarkup(inline_keyboard=buttons)
    )


# ==================================================
# 13. ALOQA
# ==================================================

@dp.message(F.text == "📞 Aloqa")
async def contact(message: Message):
    await message.answer(
        "📞 DO'KON BILAN ALOQA\n"
        "━━━━━━━━━━━━━━━━\n"
        "Telefon: +998 938684505\n"
        "Manzil: Samarqand viloyati paxtachi tumani Keshtali mahallasi.\n\n"
        "Ish vaqti: 08:00 – 20:00"
    )


# ==================================================
# 14. ADMIN PANEL
# ==================================================

def is_admin(user_id):
    return ADMIN_ID != 0 and user_id == ADMIN_ID


@dp.message(Command("admin"))
async def admin_panel(message: Message):
    if not is_admin(message.from_user.id):
        await message.answer("⛔ Siz admin emassiz.")
        return

    await message.answer(
        "⚙️ ADMIN PANEL\n"
        "━━━━━━━━━━━━━━━━\n\n"
        "/products — Mahsulotlar ro'yxati\n"
        "/add — Mahsulot qo'shish\n"
        "/price — Narxni o'zgartirish\n"
        "/delete — Mahsulotni o'chirish\n\n"
        "Mahsulot qo'shish namunasi:\n"
        "/add Sement | Sement 50 kg | 65000\n\n"
        "Narx o'zgartirish:\n"
        "/price 1 70000\n\n"
        "O'chirish:\n"
        "/delete 1"
    )


@dp.message(Command("products"))
async def admin_products(message: Message):
    if not is_admin(message.from_user.id):
        return

    cursor.execute("""
        SELECT id, category, name, price
        FROM products ORDER BY category, id
    """)

    items = cursor.fetchall()

    if not items:
        await message.answer("Mahsulotlar yo'q.")
        return

    text = "📦 MAHSULOTLAR\n━━━━━━━━━━━━━━━━\n"

    for product_id, category, name, price in items:
        text += (
            f"\nID: {product_id}\n"
            f"Bo'lim: {category}\n"
            f"Nomi: {name}\n"
            f"Narxi: {price:,} so'm\n"
        )

    await message.answer(text)


@dp.message(Command("add"))
async def admin_add(message: Message):
    if not is_admin(message.from_user.id):
        return

    try:
        data = message.text.replace("/add", "", 1).strip()
        category, name, price = [
            item.strip() for item in data.split("|")
        ]

        price = int(price)

        if price <= 0:
            raise ValueError

        cursor.execute("""
            INSERT INTO products(category, name, price)
            VALUES (?, ?, ?)
        """, (category, name, price))

        db.commit()

        await message.answer(
            f"✅ Mahsulot qo'shildi!\n\n"
            f"📦 {name}\n"
            f"💰 {price:,} so'm"
        )

    except Exception:
        await message.answer(
            "❌ Format noto'g'ri!\n\n"
            "Namuna:\n"
            "/add Sement | Sement 50 kg | 65000"
        )


@dp.message(Command("price"))
async def admin_price(message: Message):
    if not is_admin(message.from_user.id):
        return

    try:
        _, product_id, price = message.text.split()
        product_id = int(product_id)
        price = int(price)

        if price <= 0:
            raise ValueError

        cursor.execute(
            "UPDATE products SET price=? WHERE id=?",
            (price, product_id)
        )
        db.commit()

        if cursor.rowcount == 0:
            await message.answer("Mahsulot ID topilmadi.")
        else:
            await message.answer("✅ Narx o'zgartirildi!")

    except Exception:
        await message.answer(
            "Namuna: /price 1 70000"
        )


@dp.message(Command("delete"))
async def admin_delete(message: Message):
    if not is_admin(message.from_user.id):
        return

    try:
        product_id = int(message.text.split()[1])

        cursor.execute(
            "DELETE FROM products WHERE id=?",
            (product_id,)
        )

        cursor.execute(
            "DELETE FROM cart WHERE product_id=?",
            (product_id,)
        )

        db.commit()

        if cursor.rowcount == 0:
            await message.answer("Mahsulot o'chirildi yoki topilmadi.")
        else:
            await message.answer("✅ Mahsulot o'chirildi!")

    except Exception:
        await message.answer("Namuna: /delete 1")


# ==================================================
# 15. BOSH MENYU
# ==================================================

@dp.callback_query(F.data == "home")
async def go_home(call: CallbackQuery):
    await call.message.edit_text(
        "🏗️ SAVDO-SOTIQ\n\n"
        "Qurilish mollari do'koniga xush kelibsiz!",
        reply_markup=home_keyboard()
    )
    await call.answer()


# ==================================================
# 16. BOTNI ISHGA TUSHIRISH
# ==================================================

async def main():
    print("================================")
    print("SAVDO-SOTIQ BOT ISHGA TUSHDI")
    print("================================")

    await dp.start_polling(bot)


if __name__ == "__main__":
    asyncio.run(main())
