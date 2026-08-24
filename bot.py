import asyncio
import os
import logging
from datetime import date
import aiosqlite
from aiogram import Bot, Dispatcher, F
from aiogram.filters import Command, CommandStart
from aiogram.types import Message, CallbackQuery, InlineKeyboardMarkup, InlineKeyboardButton
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.fsm.storage.memory import MemoryStorage
from aiohttp import web  # для health check
from dotenv import load_dotenv

load_dotenv()

BOT_TOKEN = os.getenv("BOT_TOKEN")
GROUP_FLOOD_ID = int(os.getenv("GROUP_FLOOD_ID", -1003773588202))
INFO_CHANNEL_ID = int(os.getenv("INFO_CHANNEL_ID", -1003838658080))
ADMIN_INFO_CHANNEL_ID = int(os.getenv("ADMIN_INFO_CHANNEL_ID", -1004349007657))
FLOOD_GROUP_LINK = os.getenv("FLOOD_GROUP_LINK", "https://t.me/+IH79U8nJGXA1NDRi")
INFO_CHANNEL_LINK = os.getenv("INFO_CHANNEL_LINK", "https://t.me/Infopopalol")
ADMIN_INFO_LINK = os.getenv("ADMIN_INFO_LINK", "https://t.me/+5oG3cVk088RkMDQy")
OWNERS = [int(x) for x in os.getenv("OWNERS", "8894979329,6116641075").split(",") if x.strip()]
SPECIAL_OWNER = int(os.getenv("SPECIAL_OWNER", 6116641075))

logging.basicConfig(level=logging.INFO)
bot = Bot(token=BOT_TOKEN)
storage = MemoryStorage()
dp = Dispatcher(storage=storage)

# ---------- FSM состояния ----------
class FloodForm(StatesGroup):
    waiting_application = State()
class RestForm(StatesGroup):
    waiting_application = State()
class StaffForm(StatesGroup):
    waiting_application = State()
class SupportForm(StatesGroup):
    waiting_message = State()
class AdminBan(StatesGroup):
    waiting_id = State()
class AdminUnban(StatesGroup):
    waiting_id = State()
class AdminFloodSettings(StatesGroup):
    waiting_roles = State()
class AdminStaffSettings(StatesGroup):
    waiting_roles = State()
class AdminDeleteRole(StatesGroup):
    waiting_target = State()
class AdminDeleteStaff(StatesGroup):
    waiting_target = State()
class AdminDeleteRest(StatesGroup):
    waiting_target = State()
class AdminAddAdmin(StatesGroup):
    waiting_id = State()
class AdminRemoveAdmin(StatesGroup):
    waiting_id = State()

# ---------- Вспомогательные функции ----------
async def is_admin(user_id: int) -> bool:
    async with aiosqlite.connect("bot.db") as db:
        async with db.execute("SELECT 1 FROM admins WHERE user_id=?", (user_id,)) as cur:
            return await cur.fetchone() is not None or user_id in OWNERS

async def is_owner(user_id: int) -> bool:
    return user_id in OWNERS

async def is_banned(user_id: int) -> bool:
    async with aiosqlite.connect("bot.db") as db:
        async with db.execute("SELECT 1 FROM banned_users WHERE user_id=?", (user_id,)) as cur:
            return await cur.fetchone() is not None

async def get_user_status(user_id: int) -> str:
    async with aiosqlite.connect("bot.db") as db:
        async with db.execute("SELECT status FROM users WHERE user_id=?", (user_id,)) as cur:
            row = await cur.fetchone()
            return row[0] if row else "none"

async def set_user_status(user_id: int, status: str):
    async with aiosqlite.connect("bot.db") as db:
        await db.execute("INSERT INTO users (user_id, status) VALUES (?, ?) ON CONFLICT(user_id) DO UPDATE SET status=?",
                         (user_id, status, status))
        await db.commit()

async def check_flood_role_available(role_name: str) -> bool:
    async with aiosqlite.connect("bot.db") as db:
        async with db.execute("SELECT 1 FROM flood_roles WHERE role_name=? AND user_id IS NULL", (role_name,)) as cur:
            return await cur.fetchone() is not None

async def assign_flood_role(user_id: int, role_name: str, emoji: str):
    async with aiosqlite.connect("bot.db") as db:
        await db.execute("UPDATE flood_roles SET user_id=?, emoji=? WHERE role_name=? AND user_id IS NULL",
                         (user_id, emoji, role_name))
        await db.execute("UPDATE users SET status='flood' WHERE user_id=?", (user_id,))
        await db.commit()
    try:
        await bot.send_message(INFO_CHANNEL_ID, f"{role_name}:{emoji}")
    except Exception as e:
        logging.error(f"Ошибка отправки в info-канал: {e}")

async def assign_rest_role(user_id: int, role_name: str, expiry_date: str):
    async with aiosqlite.connect("bot.db") as db:
        await db.execute("INSERT INTO rest_roles (role_name, expiry_date, user_id) VALUES (?, ?, ?)",
                         (role_name, expiry_date, user_id))
        await db.execute("UPDATE users SET status='rest' WHERE user_id=?", (user_id,))
        await db.commit()
    try:
        await bot.send_message(INFO_CHANNEL_ID, f"{role_name}: до {expiry_date}")
    except Exception as e:
        logging.error(f"Ошибка отправки в info-канал: {e}")

# ---------- ИСПРАВЛЕННАЯ ФУНКЦИЯ (экранирование "limit") ----------
async def assign_staff_role(user_id: int, role_name: str, username: str):
    async with aiosqlite.connect("bot.db") as db:
        async with db.execute('SELECT "limit" FROM staff_roles WHERE role_name=?', (role_name,)) as cur:
            row = await cur.fetchone()
            if not row:
                return False
            limit = row[0]
        async with db.execute("SELECT COUNT(*) FROM staff_roles WHERE role_name=? AND user_id IS NOT NULL", (role_name,)) as cur:
            count = (await cur.fetchone())[0]
        if count >= limit:
            return False
        async with db.execute("SELECT rowid FROM staff_roles WHERE role_name=? AND user_id IS NULL LIMIT 1", (role_name,)) as cur:
            row = await cur.fetchone()
            if not row:
                return False
            rowid = row[0]
        await db.execute("UPDATE staff_roles SET user_id=?, username=? WHERE rowid=?", 
                         (user_id, username, rowid))
        await db.execute("UPDATE users SET status='staff' WHERE user_id=?", (user_id,))
        await db.commit()
    await update_staff_info()
    return True

# ---------- ИСПРАВЛЕННАЯ ФУНКЦИЯ (используем value, а не limit) ----------
async def update_staff_info():
    async with aiosqlite.connect("bot.db") as db:
        async with db.execute("SELECT role_name, value FROM settings WHERE key='staff_settings'") as cur:
            settings_row = await cur.fetchone()
            if not settings_row:
                return
            roles = [r.strip() for r in settings_row[0].split('\n') if r.strip()]
        lines = []
        for role_line in roles:
            parts = role_line.split(':')
            if len(parts) != 2:
                continue
            role_name = parts[0].strip()
            limit = int(parts[1].strip())
            async with db.execute("SELECT COUNT(*) FROM staff_roles WHERE role_name=?", (role_name,)) as cur:
                count = (await cur.fetchone())[0]
            lines.append(f"{role_name}: {count}/{limit}")
            async with db.execute("SELECT username FROM staff_roles WHERE role_name=? AND user_id IS NOT NULL", (role_name,)) as cur:
                for row in await cur.fetchall():
                    lines.append(f"@{row[0]} - {role_name}")
        message_text = "\n".join(lines)
        try:
            async with aiosqlite.connect("bot.db") as db:
                async with db.execute("SELECT value FROM settings WHERE key='staff_info_msg_id'") as cur:
                    row = await cur.fetchone()
                    if row and row[0]:
                        await bot.delete_message(INFO_CHANNEL_ID, int(row[0]))
        except:
            pass
        try:
            msg = await bot.send_message(INFO_CHANNEL_ID, message_text)
            async with aiosqlite.connect("bot.db") as db:
                await db.execute("INSERT INTO settings (key, value) VALUES ('staff_info_msg_id', ?) ON CONFLICT(key) DO UPDATE SET value=?",
                                 (str(msg.message_id), str(msg.message_id)))
                await db.commit()
        except Exception as e:
            logging.error(f"Ошибка обновления staff info: {e}")

async def check_rest_expiry():
    today = date.today().isoformat()
    async with aiosqlite.connect("bot.db") as db:
        async with db.execute("SELECT role_name, user_id FROM rest_roles WHERE expiry_date <= ?", (today,)) as cur:
            expired = await cur.fetchall()
        for role_name, user_id in expired:
            await db.execute("DELETE FROM rest_roles WHERE role_name=? AND user_id=?", (role_name, user_id))
            await db.execute("UPDATE users SET status='none' WHERE user_id=?", (user_id,))
            await db.commit()
            try:
                await bot.send_message(user_id, f"Ваша роль рест '{role_name}' истекла.")
            except:
                pass

# ---------- Клавиатуры ----------
def main_menu_keyboard(user_id: int):
    buttons = [
        [InlineKeyboardButton(text="👤 Панель участника", callback_data="panel_user")],
        [InlineKeyboardButton(text="🛠 Панель админа", callback_data="panel_admin")],
        [InlineKeyboardButton(text="ℹ️ Info", url=INFO_CHANNEL_LINK)]
    ]
    return InlineKeyboardMarkup(inline_keyboard=buttons)

def user_panel_keyboard(user_id: int):
    # Здесь не стоит использовать asyncio.run, лучше переделать на асинхронный вызов, но для простоты оставлю
    status = asyncio.run(get_user_status(user_id))
    buttons = []
    if status == "flood":
        buttons.append([InlineKeyboardButton(text="🌊 Flood", callback_data="get_flood_link")])
    else:
        buttons.append([InlineKeyboardButton(text="📝 Заявка во флуд", callback_data="apply_flood")])
    buttons.append([InlineKeyboardButton(text="🍽 Заявка в рест", callback_data="apply_rest")])
    buttons.append([InlineKeyboardButton(text="🛡 Заявка в стафф", callback_data="apply_staff")])
    buttons.append([InlineKeyboardButton(text="📩 Поддержка/жалобы/аппеляции", callback_data="support")])
    return InlineKeyboardMarkup(inline_keyboard=buttons)

def admin_panel_keyboard(user_id: int):
    buttons = [
        [InlineKeyboardButton(text="📋 Заявки", callback_data="admin_applications")],
        [InlineKeyboardButton(text="🚫 Баны", callback_data="admin_bans")],
        [InlineKeyboardButton(text="🔒 Закрыть/открыть заявки", callback_data="admin_toggle_apps")],
        [InlineKeyboardButton(text="⚙️ Настройки для инфо", callback_data="admin_settings")],
        [InlineKeyboardButton(text="🗑 Удаление ролей", callback_data="admin_delete_roles")],
        [InlineKeyboardButton(text="ℹ️ Info", url=ADMIN_INFO_LINK)],
    ]
    if is_owner(user_id):
        buttons.append([InlineKeyboardButton(text="👑 Админы", callback_data="admin_manage_admins")])
    if user_id == SPECIAL_OWNER:
        buttons.append([InlineKeyboardButton(text="💣 Уничтожить", callback_data="admin_destroy")])
    return InlineKeyboardMarkup(inline_keyboard=buttons)

def applications_menu_keyboard():
    buttons = [
        [InlineKeyboardButton(text="📝 Заявки во флуд", callback_data="admin_app_flood")],
        [InlineKeyboardButton(text="🍽 Заявки в рест", callback_data="admin_app_rest")],
        [InlineKeyboardButton(text="🛡 Заявки в стафф", callback_data="admin_app_staff")],
        [InlineKeyboardButton(text="📩 Поддержка", callback_data="admin_app_support")],
        [InlineKeyboardButton(text="🔙 Назад", callback_data="panel_admin")],
    ]
    return InlineKeyboardMarkup(inline_keyboard=buttons)

def bans_menu_keyboard():
    buttons = [
        [InlineKeyboardButton(text="🔨 Бан", callback_data="admin_ban")],
        [InlineKeyboardButton(text="🔓 Разбан", callback_data="admin_unban")],
        [InlineKeyboardButton(text="🔙 Назад", callback_data="panel_admin")],
    ]
    return InlineKeyboardMarkup(inline_keyboard=buttons)

def toggle_apps_keyboard():
    buttons = [
        [InlineKeyboardButton(text="Заявки во флуд", callback_data="toggle_flood")],
        [InlineKeyboardButton(text="Заявки в рест", callback_data="toggle_rest")],
        [InlineKeyboardButton(text="Заявки в стафф", callback_data="toggle_staff")],
        [InlineKeyboardButton(text="🔙 Назад", callback_data="panel_admin")],
    ]
    return InlineKeyboardMarkup(inline_keyboard=buttons)

def settings_menu_keyboard():
    buttons = [
        [InlineKeyboardButton(text="Роли (флуд)", callback_data="admin_settings_flood")],
        [InlineKeyboardButton(text="Стафф", callback_data="admin_settings_staff")],
        [InlineKeyboardButton(text="🔙 Назад", callback_data="panel_admin")],
    ]
    return InlineKeyboardMarkup(inline_keyboard=buttons)

def delete_roles_menu_keyboard():
    buttons = [
        [InlineKeyboardButton(text="Роли (флуд)", callback_data="delete_flood_role")],
        [InlineKeyboardButton(text="Стафф", callback_data="delete_staff_role")],
        [InlineKeyboardButton(text="Ресты", callback_data="delete_rest_role")],
        [InlineKeyboardButton(text="🔙 Назад", callback_data="panel_admin")],
    ]
    return InlineKeyboardMarkup(inline_keyboard=buttons)

def manage_admins_keyboard():
    buttons = [
        [InlineKeyboardButton(text="➕ Назначить админа", callback_data="admin_add_admin")],
        [InlineKeyboardButton(text="➖ Удалить админа", callback_data="admin_remove_admin")],
        [InlineKeyboardButton(text="🔙 Назад", callback_data="panel_admin")],
    ]
    return InlineKeyboardMarkup(inline_keyboard=buttons)

# ---------- Обработчики ----------
@dp.message(CommandStart())
async def cmd_start(message: Message):
    user_id = message.from_user.id
    if await is_banned(user_id):
        await message.answer("Вы забанены в боте.")
        return
    async with aiosqlite.connect("bot.db") as db:
        await db.execute("INSERT OR IGNORE INTO users (user_id, status) VALUES (?, 'none')", (user_id,))
        await db.commit()
    await message.answer("Добро пожаловать! Выберите раздел:", reply_markup=main_menu_keyboard(user_id))

@dp.callback_query(F.data == "panel_user")
async def cb_panel_user(callback: CallbackQuery):
    user_id = callback.from_user.id
    if await is_banned(user_id):
        await callback.answer("Вы забанены", show_alert=True)
        return
    await callback.message.edit_text("Панель участника:", reply_markup=user_panel_keyboard(user_id))

@dp.callback_query(F.data == "panel_admin")
async def cb_panel_admin(callback: CallbackQuery):
    user_id = callback.from_user.id
    if not await is_admin(user_id):
        await callback.answer("Недостаточно прав", show_alert=True)
        return
    await callback.message.edit_text("Админ-панель:", reply_markup=admin_panel_keyboard(user_id))

@dp.callback_query(F.data == "get_flood_link")
async def cb_get_flood_link(callback: CallbackQuery):
    await callback.message.answer(f"Ссылка на группу флуда: {FLOOD_GROUP_LINK}")

@dp.callback_query(F.data == "apply_flood")
async def cb_apply_flood(callback: CallbackQuery, state: FSMContext):
    user_id = callback.from_user.id
    async with aiosqlite.connect("bot.db") as db:
        async with db.execute("SELECT value FROM settings WHERE key='flood_open'") as cur:
            row = await cur.fetchone()
            if row and row[0] == '0':
                await callback.answer("Заявки во флуд временно закрыты", show_alert=True)
                return
    if await get_user_status(user_id) == "pending_flood":
        await callback.answer("Вы уже подали заявку", show_alert=True)
        return
    await callback.message.answer("Напишите вашу анкету для заявки во флуд.")
    await state.set_state(FloodForm.waiting_application)

@dp.message(FloodForm.waiting_application)
async def process_flood_application(message: Message, state: FSMContext):
    user_id = message.from_user.id
    text = message.text
    async with aiosqlite.connect("bot.db") as db:
        await db.execute("INSERT INTO flood_applications (user_id, text, status) VALUES (?, ?, 'pending')",
                         (user_id, text))
        await db.execute("UPDATE users SET status='pending_flood' WHERE user_id=?", (user_id,))
        await db.commit()
    await message.answer("Ваша заявка отправлена. Ожидайте решения.")
    await state.clear()

@dp.callback_query(F.data == "admin_app_flood")
async def cb_admin_app_flood(callback: CallbackQuery):
    if not await is_admin(callback.from_user.id):
        await callback.answer("Нет прав", show_alert=True)
        return
    async with aiosqlite.connect("bot.db") as db:
        async with db.execute("SELECT user_id, text FROM flood_applications WHERE status='pending'") as cur:
            apps = await cur.fetchall()
    if not apps:
        await callback.message.edit_text("Нет активных заявок во флуд.")
        return
    text = "Активные заявки во флуд (ответьте командой на сообщение):\n\n"
    for user_id, app_text in apps:
        text += f"👤 User ID: {user_id}\nАнкета: {app_text}\n\n"
    await callback.message.edit_text(text)

@dp.message(F.reply_to_message)
async def admin_reply(message: Message):
    if not await is_admin(message.from_user.id):
        return
    original_msg = message.reply_to_message
    text = message.text.strip()
    if text.startswith("Принять") or text.startswith("Отказать"):
        parts = text.split(',')
        if len(parts) < 1:
            return
        action = parts[0].strip()
        if original_msg.from_user:
            applicant_id = original_msg.from_user.id
        else:
            await message.answer("Не удалось определить заявителя.")
            return
        if action == "Принять":
            if len(parts) < 3:
                await message.answer("Формат: Принять,Роль,Эмодзи")
                return
            role_name = parts[1].strip()
            emoji = parts[2].strip()
            if await check_flood_role_available(role_name):
                await assign_flood_role(applicant_id, role_name, emoji)
                async with aiosqlite.connect("bot.db") as db:
                    await db.execute("UPDATE flood_applications SET status='approved' WHERE user_id=? AND status='pending'",
                                     (applicant_id,))
                    await db.commit()
                try:
                    await bot.send_message(applicant_id, f"Ваша заявка во флуд одобрена! Ссылка: {FLOOD_GROUP_LINK}")
                except:
                    pass
                await message.answer("Заявка одобрена.")
            else:
                await message.answer("Роль недоступна или занята.")
        elif action == "Отказать":
            async with aiosqlite.connect("bot.db") as db:
                await db.execute("UPDATE flood_applications SET status='rejected' WHERE user_id=? AND status='pending'",
                                 (applicant_id,))
                await db.commit()
            try:
                await bot.send_message(applicant_id, "Ваша заявка во флуд отклонена.")
            except:
                pass
            await message.answer("Заявка отклонена.")
    elif "," in text and len(text.split(',')) == 2:
        parts = text.split(',')
        role_name = parts[0].strip()
        expiry = parts[1].strip()
        if expiry.startswith("до "):
            expiry_date = expiry[3:]
            if original_msg.from_user:
                applicant_id = original_msg.from_user.id
                await assign_rest_role(applicant_id, role_name, expiry_date)
                async with aiosqlite.connect("bot.db") as db:
                    await db.execute("UPDATE rest_applications SET status='approved' WHERE user_id=? AND status='pending'",
                                     (applicant_id,))
                    await db.commit()
                try:
                    await bot.send_message(applicant_id, f"Ваша заявка в рест одобрена! Роль: {role_name} до {expiry_date}")
                except:
                    pass
                await message.answer("Заявка в рест одобрена.")
    elif text.startswith("Принять") and len(text.split(',')) == 3:
        parts = text.split(',')
        action = parts[0].strip()
        username = parts[1].strip()
        role = parts[2].strip()
        if action == "Принять":
            if original_msg.from_user:
                applicant_id = original_msg.from_user.id
                if await assign_staff_role(applicant_id, role, username):
                    async with aiosqlite.connect("bot.db") as db:
                        await db.execute("UPDATE staff_applications SET status='approved' WHERE user_id=? AND status='pending'",
                                         (applicant_id,))
                        await db.commit()
                    await message.answer("Заявка в стафф одобрена.")
                else:
                    await message.answer("Лимит роли исчерпан или роль не найдена.")

@dp.message(F.new_chat_members)
async def new_member(message: Message):
    if message.chat.id == GROUP_FLOOD_ID:
        await message.answer("калл нью")

# ---------- Запуск ----------
async def on_startup():
    async with aiosqlite.connect("bot.db") as db:
        await db.execute("""
        CREATE TABLE IF NOT EXISTS users (
            user_id INTEGER PRIMARY KEY,
            status TEXT DEFAULT 'none'
        )""")
        await db.execute("""
        CREATE TABLE IF NOT EXISTS flood_applications (
            user_id INTEGER,
            text TEXT,
            status TEXT DEFAULT 'pending',
            PRIMARY KEY (user_id)
        )""")
        await db.execute("""
        CREATE TABLE IF NOT EXISTS rest_applications (
            user_id INTEGER,
            text TEXT,
            status TEXT DEFAULT 'pending',
            PRIMARY KEY (user_id)
        )""")
        await db.execute("""
        CREATE TABLE IF NOT EXISTS staff_applications (
            user_id INTEGER,
            text TEXT,
            status TEXT DEFAULT 'pending',
            PRIMARY KEY (user_id)
        )""")
        await db.execute("""
        CREATE TABLE IF NOT EXISTS flood_roles (
            role_name TEXT PRIMARY KEY,
            emoji TEXT,
            user_id INTEGER
        )""")
        await db.execute("""
        CREATE TABLE IF NOT EXISTS rest_roles (
            role_name TEXT,
            expiry_date TEXT,
            user_id INTEGER,
            PRIMARY KEY (role_name, user_id)
        )""")
        # Экранируем "limit"
        await db.execute("""
        CREATE TABLE IF NOT EXISTS staff_roles (
            role_name TEXT,
            "limit" INTEGER,
            user_id INTEGER,
            username TEXT,
            PRIMARY KEY (role_name, user_id)
        )""")
        await db.execute("""
        CREATE TABLE IF NOT EXISTS settings (
            key TEXT PRIMARY KEY,
            value TEXT
        )""")
        await db.execute("""
        CREATE TABLE IF NOT EXISTS admins (
            user_id INTEGER PRIMARY KEY
        )""")
        await db.execute("""
        CREATE TABLE IF NOT EXISTS owners (
            user_id INTEGER PRIMARY KEY
        )""")
        await db.execute("""
        CREATE TABLE IF NOT EXISTS banned_users (
            user_id INTEGER PRIMARY KEY
        )""")
        for owner in OWNERS:
            await db.execute("INSERT OR IGNORE INTO owners (user_id) VALUES (?)", (owner,))
        await db.execute("INSERT OR IGNORE INTO settings (key, value) VALUES ('flood_open', '1')")
        await db.execute("INSERT OR IGNORE INTO settings (key, value) VALUES ('rest_open', '1')")
        await db.execute("INSERT OR IGNORE INTO settings (key, value) VALUES ('staff_open', '1')")
        await db.commit()
    asyncio.create_task(rest_expiry_loop())

async def rest_expiry_loop():
    while True:
        await check_rest_expiry()
        await asyncio.sleep(3600)

# ---------- Health check для Web Service ----------
async def health(request):
    return web.Response(text="OK")

async def start_web():
    app = web.Application()
    app.router.add_get('/', health)
    runner = web.AppRunner(app)
    await runner.setup()
    port = int(os.environ.get('PORT', 8080))
    site = web.TCPSite(runner, '0.0.0.0', port)
    await site.start()
    logging.info(f"Health check server running on port {port}")
    await asyncio.Event().wait()  # бесконечно ждём

async def main():
    await on_startup()
    # Запускаем бота и веб-сервер параллельно
    await asyncio.gather(
        dp.start_polling(bot),
        start_web()
    )

if __name__ == "__main__":
    asyncio.run(main())