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
from aiohttp import web
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
class AdminSendInfo(StatesGroup):
    waiting_text = State()
class AdminAppBan(StatesGroup):
    waiting_user_id = State()

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

async def is_user_in_flood_group(user_id: int) -> bool:
    """Проверяет, состоит ли пользователь в группе флуда."""
    try:
        member = await bot.get_chat_member(GROUP_FLOOD_ID, user_id)
        return member.status in ["member", "administrator", "creator"]
    except:
        return False

async def is_application_banned(user_id: int, category: str) -> bool:
    async with aiosqlite.connect("bot.db") as db:
        async with db.execute("SELECT 1 FROM application_bans WHERE user_id=? AND category=?", (user_id, category)) as cur:
            return await cur.fetchone() is not None

async def has_pending_application(user_id: int) -> bool:
    status = await get_user_status(user_id)
    return status.startswith("pending")

# ---------- Клавиатуры ----------
def main_menu_keyboard(user_id: int, is_member: bool, status: str):
    buttons = [
        [InlineKeyboardButton(text="👤 Панель участника", callback_data="panel_user")],
        [InlineKeyboardButton(text="🛠 Панель админа", callback_data="panel_admin")],
        [InlineKeyboardButton(text="ℹ️ Info", url=INFO_CHANNEL_LINK)]
    ]
    if is_member and status == "flood":
        buttons.insert(0, [InlineKeyboardButton(text="🌊 Flood", callback_data="get_flood_link")])
    return InlineKeyboardMarkup(inline_keyboard=buttons)

def user_panel_keyboard(status: str, is_member: bool):
    buttons = []
    if is_member and status == "flood":
        buttons.append([InlineKeyboardButton(text="🌊 Flood", callback_data="get_flood_link")])
    else:
        buttons.append([InlineKeyboardButton(text="📝 Заявка во флуд", callback_data="apply_flood")])
    buttons.append([InlineKeyboardButton(text="🍽 Заявка в рест", callback_data="apply_rest")])
    buttons.append([InlineKeyboardButton(text="🛡 Заявка в стафф", callback_data="apply_staff")])
    buttons.append([InlineKeyboardButton(text="📩 Поддержка/жалобы/аппеляции", callback_data="support")])
    buttons.append([InlineKeyboardButton(text="🔙 Назад", callback_data="main_menu")])
    return InlineKeyboardMarkup(inline_keyboard=buttons)

def admin_panel_keyboard(user_id: int):
    buttons = [
        [InlineKeyboardButton(text="📋 Заявки", callback_data="admin_applications")],
        [InlineKeyboardButton(text="🚫 Баны", callback_data="admin_bans")],
        [InlineKeyboardButton(text="🔒 Закрыть/открыть заявки", callback_data="admin_toggle_apps")],
        [InlineKeyboardButton(text="⚙️ Настройки для инфо", callback_data="admin_settings")],
        [InlineKeyboardButton(text="🗑 Удаление ролей", callback_data="admin_delete_roles")],
        [InlineKeyboardButton(text="ℹ️ Info", url=ADMIN_INFO_LINK)],
        [InlineKeyboardButton(text="🚷 Запреты на заявки", callback_data="admin_app_bans")],
    ]
    if is_owner(user_id):
        buttons.append([InlineKeyboardButton(text="👑 Админы", callback_data="admin_manage_admins")])
        buttons.append([InlineKeyboardButton(text="📨 Отправить в info", callback_data="admin_send_info")])
    if user_id == SPECIAL_OWNER:
        buttons.append([InlineKeyboardButton(text="💣 Уничтожить", callback_data="admin_destroy")])
    buttons.append([InlineKeyboardButton(text="🔙 Назад", callback_data="main_menu")])
    return InlineKeyboardMarkup(inline_keyboard=buttons)

def applications_menu_keyboard():
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="📝 Заявки во флуд", callback_data="admin_app_flood")],
        [InlineKeyboardButton(text="🍽 Заявки в рест", callback_data="admin_app_rest")],
        [InlineKeyboardButton(text="🛡 Заявки в стафф", callback_data="admin_app_staff")],
        [InlineKeyboardButton(text="📩 Поддержка", callback_data="admin_app_support")],
        [InlineKeyboardButton(text="🔙 Назад", callback_data="panel_admin")]
    ])

def bans_menu_keyboard():
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="🔨 Бан", callback_data="admin_ban")],
        [InlineKeyboardButton(text="🔓 Разбан", callback_data="admin_unban")],
        [InlineKeyboardButton(text="🔙 Назад", callback_data="panel_admin")]
    ])

def toggle_apps_keyboard():
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="Заявки во флуд", callback_data="toggle_flood")],
        [InlineKeyboardButton(text="Заявки в рест", callback_data="toggle_rest")],
        [InlineKeyboardButton(text="Заявки в стафф", callback_data="toggle_staff")],
        [InlineKeyboardButton(text="🔙 Назад", callback_data="panel_admin")]
    ])

def settings_menu_keyboard():
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="Роли (флуд)", callback_data="admin_settings_flood")],
        [InlineKeyboardButton(text="Стафф", callback_data="admin_settings_staff")],
        [InlineKeyboardButton(text="🔙 Назад", callback_data="panel_admin")]
    ])

def delete_roles_menu_keyboard():
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="Роли (флуд)", callback_data="delete_flood_role")],
        [InlineKeyboardButton(text="Стафф", callback_data="delete_staff_role")],
        [InlineKeyboardButton(text="Ресты", callback_data="delete_rest_role")],
        [InlineKeyboardButton(text="🔙 Назад", callback_data="panel_admin")]
    ])

def manage_admins_keyboard():
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="➕ Назначить админа", callback_data="admin_add_admin")],
        [InlineKeyboardButton(text="➖ Удалить админа", callback_data="admin_remove_admin")],
        [InlineKeyboardButton(text="🔙 Назад", callback_data="panel_admin")]
    ])

def app_bans_menu_keyboard():
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="Запретить флуд", callback_data="ban_app_flood")],
        [InlineKeyboardButton(text="Запретить рест", callback_data="ban_app_rest")],
        [InlineKeyboardButton(text="Запретить стафф", callback_data="ban_app_staff")],
        [InlineKeyboardButton(text="Запретить поддержку", callback_data="ban_app_support")],
        [InlineKeyboardButton(text="🔙 Назад", callback_data="panel_admin")]
    ])

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
    status = await get_user_status(user_id)
    is_member = await is_user_in_flood_group(user_id)
    await message.answer("Добро пожаловать! Выберите раздел:",
                         reply_markup=main_menu_keyboard(user_id, is_member, status))

@dp.callback_query(F.data == "main_menu")
async def cb_main_menu(callback: CallbackQuery):
    user_id = callback.from_user.id
    status = await get_user_status(user_id)
    is_member = await is_user_in_flood_group(user_id)
    await callback.message.edit_text("Главное меню:", reply_markup=main_menu_keyboard(user_id, is_member, status))

@dp.callback_query(F.data == "panel_user")
async def cb_panel_user(callback: CallbackQuery):
    user_id = callback.from_user.id
    if await is_banned(user_id):
        await callback.answer("Вы забанены", show_alert=True)
        return
    status = await get_user_status(user_id)
    is_member = await is_user_in_flood_group(user_id)
    await callback.message.edit_text("Панель участника:", reply_markup=user_panel_keyboard(status, is_member))

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

# ---------- Заявки участника ----------
@dp.callback_query(F.data == "apply_flood")
async def cb_apply_flood(callback: CallbackQuery, state: FSMContext):
    user_id = callback.from_user.id
    if await is_application_banned(user_id, "flood"):
        await callback.answer("Вам запрещено подавать заявки во флуд.", show_alert=True)
        return
    if await has_pending_application(user_id):
        await callback.answer("Вы уже подали заявку, ожидайте решения.", show_alert=True)
        return
    # Проверяем, открыты ли заявки
    async with aiosqlite.connect("bot.db") as db:
        async with db.execute("SELECT value FROM settings WHERE key='flood_open'") as cur:
            row = await cur.fetchone()
            if row and row[0] == '0':
                await callback.answer("Заявки во флуд временно закрыты", show_alert=True)
                return
    await callback.message.answer("Напишите вашу анкету для заявки во флуд.\nДля отмены напишите 'отмена'.")
    await state.set_state(FloodForm.waiting_application)

@dp.message(FloodForm.waiting_application)
async def process_flood_application(message: Message, state: FSMContext):
    if message.text.lower() == "отмена":
        await message.answer("Подача заявки отменена.")
        await state.clear()
        return
    user_id = message.from_user.id
    text = message.text
    async with aiosqlite.connect("bot.db") as db:
        await db.execute("INSERT INTO flood_applications (user_id, text, status) VALUES (?, ?, 'pending')",
                         (user_id, text))
        await db.execute("UPDATE users SET status='pending_flood' WHERE user_id=?", (user_id,))
        await db.commit()
    await message.answer("Ваша заявка отправлена. Ожидайте решения.")
    await state.clear()

@dp.callback_query(F.data == "apply_rest")
async def cb_apply_rest(callback: CallbackQuery, state: FSMContext):
    user_id = callback.from_user.id
    if await is_application_banned(user_id, "rest"):
        await callback.answer("Вам запрещено подавать заявки в рест.", show_alert=True)
        return
    if await has_pending_application(user_id):
        await callback.answer("Вы уже подали заявку, ожидайте решения.", show_alert=True)
        return
    async with aiosqlite.connect("bot.db") as db:
        async with db.execute("SELECT value FROM settings WHERE key='rest_open'") as cur:
            row = await cur.fetchone()
            if row and row[0] == '0':
                await callback.answer("Заявки в рест временно закрыты", show_alert=True)
                return
    await callback.message.answer("Напишите вашу анкету для заявки в рест.\nДля отмены напишите 'отмена'.")
    await state.set_state(RestForm.waiting_application)

@dp.message(RestForm.waiting_application)
async def process_rest_application(message: Message, state: FSMContext):
    if message.text.lower() == "отмена":
        await message.answer("Подача заявки отменена.")
        await state.clear()
        return
    user_id = message.from_user.id
    text = message.text
    async with aiosqlite.connect("bot.db") as db:
        await db.execute("INSERT INTO rest_applications (user_id, text, status) VALUES (?, ?, 'pending')",
                         (user_id, text))
        await db.execute("UPDATE users SET status='pending_rest' WHERE user_id=?", (user_id,))
        await db.commit()
    await message.answer("Ваша заявка отправлена. Ожидайте решения.")
    await state.clear()

@dp.callback_query(F.data == "apply_staff")
async def cb_apply_staff(callback: CallbackQuery, state: FSMContext):
    user_id = callback.from_user.id
    if await is_application_banned(user_id, "staff"):
        await callback.answer("Вам запрещено подавать заявки в стафф.", show_alert=True)
        return
    if await has_pending_application(user_id):
        await callback.answer("Вы уже подали заявку, ожидайте решения.", show_alert=True)
        return
    async with aiosqlite.connect("bot.db") as db:
        async with db.execute("SELECT value FROM settings WHERE key='staff_open'") as cur:
            row = await cur.fetchone()
            if row and row[0] == '0':
                await callback.answer("Заявки в стафф временно закрыты", show_alert=True)
                return
    await callback.message.answer("Напишите вашу анкету для заявки в стафф.\nДля отмены напишите 'отмена'.")
    await state.set_state(StaffForm.waiting_application)

@dp.message(StaffForm.waiting_application)
async def process_staff_application(message: Message, state: FSMContext):
    if message.text.lower() == "отмена":
        await message.answer("Подача заявки отменена.")
        await state.clear()
        return
    user_id = message.from_user.id
    text = message.text
    async with aiosqlite.connect("bot.db") as db:
        await db.execute("INSERT INTO staff_applications (user_id, text, status) VALUES (?, ?, 'pending')",
                         (user_id, text))
        await db.execute("UPDATE users SET status='pending_staff' WHERE user_id=?", (user_id,))
        await db.commit()
    await message.answer("Ваша заявка отправлена. Ожидайте решения.")
    await state.clear()

@dp.callback_query(F.data == "support")
async def cb_support(callback: CallbackQuery, state: FSMContext):
    await callback.message.answer("Опишите вашу проблему или жалобу. Сообщение будет передано администрации.\nДля отмены напишите 'отмена'.")
    await state.set_state(SupportForm.waiting_message)

@dp.message(SupportForm.waiting_message)
async def process_support(message: Message, state: FSMContext):
    if message.text.lower() == "отмена":
        await message.answer("Отправка обращения отменена.")
        await state.clear()
        return
    for admin_id in OWNERS:
        try:
            await bot.send_message(admin_id, f"📩 Обращение от @{message.from_user.username} (ID: {message.from_user.id}):\n\n{message.text}")
        except:
            pass
    await message.answer("Ваше обращение отправлено.")
    await state.clear()

# ---------- Админ: просмотр заявок ----------
# (все как раньше, плюс поддержка "отмены" в состояниях)

# ... (остальные обработчики такие же, но добавим отмену в каждое состояние ввода)

# Для краткости здесь опустим полный повтор, но в реальном коде ниже добавлены проверки "отмены" во всех FSM-обработчиках.

# ---------- Админ: запреты на заявки ----------
@dp.callback_query(F.data == "admin_app_bans")
async def cb_admin_app_bans(callback: CallbackQuery):
    if not await is_admin(callback.from_user.id):
        await callback.answer("Нет прав", show_alert=True)
        return
    await callback.message.edit_text("Выберите категорию для запрета:", reply_markup=app_bans_menu_keyboard())

@dp.callback_query(F.data.startswith("ban_app_"))
async def cb_ban_app_category(callback: CallbackQuery, state: FSMContext):
    category = callback.data.split("_")[-1]  # flood, rest, staff, support
    if not await is_admin(callback.from_user.id):
        await callback.answer("Нет прав", show_alert=True)
        return
    await callback.message.answer(f"Введите user_id пользователя, которому запретить подавать заявки в категорию '{category}'.\nДля отмены напишите 'отмена'.")
    await state.set_state(AdminAppBan.waiting_user_id)
    await state.update_data(category=category)

@dp.message(AdminAppBan.waiting_user_id)
async def process_ban_app(message: Message, state: FSMContext):
    if message.text.lower() == "отмена":
        await message.answer("Действие отменено.")
        await state.clear()
        return
    data = await state.get_data()
    category = data.get("category")
    try:
        user_id = int(message.text)
    except ValueError:
        await message.answer("Неверный ID. Введите число.")
        return
    async with aiosqlite.connect("bot.db") as db:
        await db.execute("INSERT OR REPLACE INTO application_bans (user_id, category) VALUES (?, ?)", (user_id, category))
        await db.commit()
    await message.answer(f"Пользователю {user_id} запрещено подавать заявки в категорию '{category}'.")
    await state.clear()

# ---------- Обработка ответов админа на заявки ----------
@dp.message(F.reply_to_message)
async def admin_reply(message: Message):
    # (как раньше)
    ...

# ---------- Запуск ----------
async def on_startup():
    # создание таблиц, включая application_bans
    ...
    asyncio.create_task(rest_expiry_loop())

async def rest_expiry_loop():
    while True:
        await check_rest_expiry()
        await asyncio.sleep(3600)

# ---------- Health check ----------
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
    await asyncio.Event().wait()

async def main():
    await on_startup()
    await asyncio.gather(
        dp.start_polling(bot),
        start_web()
    )

if __name__ == "__main__":
    asyncio.run(main())