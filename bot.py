import asyncio
import os
import logging
from datetime import date, datetime, timedelta
import re
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
class AdminSendMessage(StatesGroup):
    waiting_text = State()
class AdminDeleteMessage(StatesGroup):
    waiting_link = State()
class AdminAppBan(StatesGroup):
    waiting_user_id = State()
class AdminCooldownGive(StatesGroup):
    waiting_category = State()
    waiting_id_duration = State()
class AdminCooldownRemove(StatesGroup):
    waiting_category = State()
    waiting_id = State()
class AdminCooldownSettings(StatesGroup):
    waiting_category = State()
    waiting_duration = State()

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
    try:
        member = await bot.get_chat_member(GROUP_FLOOD_ID, user_id)
        return member.status in ["member", "administrator", "creator"]
    except:
        return False

async def has_been_in_group(user_id: int) -> bool:
    async with aiosqlite.connect("bot.db") as db:
        async with db.execute("SELECT was_in_group FROM users WHERE user_id=?", (user_id,)) as cur:
            row = await cur.fetchone()
            return bool(row and row[0])

async def mark_user_in_group(user_id: int):
    async with aiosqlite.connect("bot.db") as db:
        await db.execute("UPDATE users SET in_group=1, was_in_group=1 WHERE user_id=?", (user_id,))
        await db.commit()

async def unmark_user_in_group(user_id: int):
    async with aiosqlite.connect("bot.db") as db:
        await db.execute("UPDATE users SET in_group=0 WHERE user_id=?", (user_id,))
        await db.commit()

async def is_application_banned(user_id: int, category: str) -> bool:
    async with aiosqlite.connect("bot.db") as db:
        async with db.execute("SELECT 1 FROM application_bans WHERE user_id=? AND category=?", (user_id, category)) as cur:
            return await cur.fetchone() is not None

async def has_pending_application(user_id: int) -> bool:
    status = await get_user_status(user_id)
    return status.startswith("pending")

# ---------- Работа с info_messages ----------
async def get_info_message_id(key: str):
    async with aiosqlite.connect("bot.db") as db:
        async with db.execute("SELECT message_id FROM info_messages WHERE key=?", (key,)) as cur:
            row = await cur.fetchone()
            return row[0] if row else None

async def set_info_message_id(key: str, message_id: int):
    async with aiosqlite.connect("bot.db") as db:
        await db.execute("INSERT INTO info_messages (key, message_id) VALUES (?, ?) ON CONFLICT(key) DO UPDATE SET message_id=?",
                         (key, str(message_id), str(message_id)))
        await db.commit()

async def delete_info_message(key: str):
    msg_id = await get_info_message_id(key)
    if msg_id:
        try:
            await bot.delete_message(INFO_CHANNEL_ID, int(msg_id))
        except:
            pass
        async with aiosqlite.connect("bot.db") as db:
            await db.execute("DELETE FROM info_messages WHERE key=?", (key,))
            await db.commit()

async def send_or_edit_info_message(key: str, text: str):
    msg_id = await get_info_message_id(key)
    if msg_id:
        try:
            await bot.edit_message_text(text, INFO_CHANNEL_ID, int(msg_id))
        except:
            msg = await bot.send_message(INFO_CHANNEL_ID, text)
            await set_info_message_id(key, msg.message_id)
    else:
        msg = await bot.send_message(INFO_CHANNEL_ID, text)
        await set_info_message_id(key, msg.message_id)

async def get_info_message_ids(key: str) -> list:
    async with aiosqlite.connect("bot.db") as db:
        async with db.execute("SELECT message_id FROM info_messages WHERE key=?", (key,)) as cur:
            row = await cur.fetchone()
            if row and row[0]:
                return [int(x) for x in row[0].split(',')]
            return []

async def set_info_message_ids(key: str, ids: list):
    value = ','.join(map(str, ids)) if ids else ''
    async with aiosqlite.connect("bot.db") as db:
        await db.execute("INSERT INTO info_messages (key, message_id) VALUES (?, ?) ON CONFLICT(key) DO UPDATE SET message_id=?",
                         (key, value, value))
        await db.commit()

# ---------- Функции ролей ----------
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
        await bot.send_message(user_id, f"✅ Ваша заявка во флуд одобрена! Ссылка: {FLOOD_GROUP_LINK}")
    except:
        pass
    await update_flood_info()
    await apply_auto_cooldown(user_id, "flood")

async def revoke_flood_role(user_id: int):
    async with aiosqlite.connect("bot.db") as db:
        await db.execute("UPDATE flood_roles SET user_id=NULL WHERE user_id=?", (user_id,))
        await db.execute("UPDATE users SET status='none' WHERE user_id=?", (user_id,))
        await db.commit()
    await update_flood_info()

async def update_flood_info():
    async with aiosqlite.connect("bot.db") as db:
        async with db.execute("SELECT role_name, emoji, user_id FROM flood_roles") as cur:
            roles = await cur.fetchall()
    lines = ["🌊 Роли флуда:"]
    for role_name, emoji, user_id in roles:
        lines.append(f"{role_name}:{emoji}")
    await send_or_edit_info_message("flood_roles", "\n".join(lines))

async def assign_rest_role(user_id: int, role_name: str, expiry_date: str):
    async with aiosqlite.connect("bot.db") as db:
        await db.execute("INSERT INTO rest_roles (role_name, expiry_date, user_id) VALUES (?, ?, ?)",
                         (role_name, expiry_date, user_id))
        await db.execute("UPDATE users SET status='rest' WHERE user_id=?", (user_id,))
        await db.commit()
    try:
        await bot.send_message(user_id, f"✅ Ваша заявка в рест одобрена! Роль: {role_name} до {expiry_date}")
    except:
        pass
    await update_rest_info()
    await apply_auto_cooldown(user_id, "rest")

async def revoke_rest_role(user_id: int, role_name: str):
    async with aiosqlite.connect("bot.db") as db:
        await db.execute("DELETE FROM rest_roles WHERE user_id=? AND role_name=?", (user_id, role_name))
        await db.execute("UPDATE users SET status='none' WHERE user_id=?", (user_id,))
        await db.commit()
    await update_rest_info()

async def update_rest_info():
    async with aiosqlite.connect("bot.db") as db:
        async with db.execute("SELECT role_name, expiry_date, user_id FROM rest_roles") as cur:
            roles = await cur.fetchall()
    if not roles:
        await delete_info_message("rest_roles")
        return
    lines = ["🍽 Ресты:"]
    for role_name, expiry, user_id in roles:
        lines.append(f"{role_name}: до {expiry}")
    await send_or_edit_info_message("rest_roles", "\n".join(lines))

async def assign_staff_role(user_id: int, role_name: str, username: str):
    async with aiosqlite.connect("bot.db") as db:
        async with db.execute('SELECT role_limit FROM staff_roles WHERE role_name=?', (role_name,)) as cur:
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
    try:
        await bot.send_message(user_id, f"✅ Вы назначены на роль {role_name}!")
    except:
        pass
    await apply_auto_cooldown(user_id, "staff")
    return True

async def revoke_staff_role(user_id: int, role_name: str):
    async with aiosqlite.connect("bot.db") as db:
        await db.execute("UPDATE staff_roles SET user_id=NULL, username=NULL WHERE user_id=? AND role_name=?", (user_id, role_name))
        await db.execute("UPDATE users SET status='none' WHERE user_id=?", (user_id,))
        await db.commit()
    await update_staff_info()

async def update_staff_info():
    async with aiosqlite.connect("bot.db") as db:
        async with db.execute("SELECT value FROM settings WHERE key='staff_settings'") as cur:
            settings_row = await cur.fetchone()
            if not settings_row:
                return
            roles = [r.strip() for r in settings_row[0].split('\n') if r.strip()]
        lines = ["🛡 Стафф:"]
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
    await send_or_edit_info_message("staff_roles", "\n".join(lines))

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
                await bot.send_message(user_id, f"⚠️ Ваша роль рест '{role_name}' истекла.")
            except:
                pass
    await update_rest_info()

async def cleanup_expired_pending():
    now = datetime.now()
    threshold = now - timedelta(days=4)
    threshold_iso = threshold.isoformat()
    async with aiosqlite.connect("bot.db") as db:
        for table in ["flood_applications", "rest_applications", "staff_applications"]:
            async with db.execute(f"SELECT user_id FROM {table} WHERE status='pending' AND created_at < ?", (threshold_iso,)) as cur:
                expired_users = [row[0] for row in await cur.fetchall()]
            for user_id in expired_users:
                await db.execute(f"DELETE FROM {table} WHERE user_id=?", (user_id,))
                await db.execute("UPDATE users SET status='none' WHERE user_id=?", (user_id,))
        await db.commit()

async def is_cooldown_active(user_id: int, category: str) -> bool:
    async with aiosqlite.connect("bot.db") as db:
        async with db.execute("SELECT until_date FROM cooldowns WHERE user_id=? AND category=?", (user_id, category)) as cur:
            row = await cur.fetchone()
            if row and row[0]:
                until = datetime.fromisoformat(row[0])
                return until > datetime.now()
            return False

async def set_cooldown(user_id: int, category: str, seconds: int):
    until = datetime.now() + timedelta(seconds=seconds)
    async with aiosqlite.connect("bot.db") as db:
        await db.execute("INSERT OR REPLACE INTO cooldowns (user_id, category, until_date) VALUES (?, ?, ?)",
                         (user_id, category, until.isoformat()))
        await db.commit()

async def remove_cooldown(user_id: int, category: str):
    async with aiosqlite.connect("bot.db") as db:
        await db.execute("DELETE FROM cooldowns WHERE user_id=? AND category=?", (user_id, category))
        await db.commit()

async def get_cooldown_duration(category: str) -> int:
    async with aiosqlite.connect("bot.db") as db:
        async with db.execute("SELECT duration_seconds FROM cooldown_settings WHERE category=?", (category,)) as cur:
            row = await cur.fetchone()
            return int(row[0]) if row and row[0] else 0

async def set_cooldown_duration(category: str, seconds: int):
    async with aiosqlite.connect("bot.db") as db:
        await db.execute("INSERT OR REPLACE INTO cooldown_settings (category, duration_seconds) VALUES (?, ?)",
                         (category, seconds))
        await db.commit()

async def apply_auto_cooldown(user_id: int, category: str):
    duration = await get_cooldown_duration(category)
    if duration > 0:
        await set_cooldown(user_id, category, duration)

def parse_duration(text: str) -> int:
    text = text.strip().lower()
    match = re.match(r"^(\d+)\s*([дчмс])?$", text)
    if not match:
        raise ValueError("Неверный формат длительности")
    value = int(match.group(1))
    unit = match.group(2)
    if unit is None or unit == "д":
        return value * 86400
    elif unit == "ч":
        return value * 3600
    elif unit == "м":
        return value * 60
    elif unit == "с":
        return value
    else:
        raise ValueError("Неизвестная единица измерения")

# ---------- Клавиатуры ----------
def main_menu_keyboard(status: str, is_member: bool):
    buttons = [
        [InlineKeyboardButton(text="👤 Панель участника", callback_data="panel_user")],
        [InlineKeyboardButton(text="🛠 Панель админа", callback_data="panel_admin")],
        [InlineKeyboardButton(text="ℹ️ Info", url=INFO_CHANNEL_LINK)]
    ]
    if is_member:
        buttons.insert(0, [InlineKeyboardButton(text="🌊 Flood", callback_data="get_flood_link")])
    return InlineKeyboardMarkup(inline_keyboard=buttons)

def user_panel_keyboard(status: str, is_member: bool):
    buttons = []
    if is_member:
        buttons.append([InlineKeyboardButton(text="🌊 Flood", callback_data="get_flood_link")])
    else:
        buttons.append([InlineKeyboardButton(text="📝 Заявка во флуд", callback_data="apply_flood")])
    buttons.append([InlineKeyboardButton(text="🍽 Заявка в рест", callback_data="apply_rest")])
    buttons.append([InlineKeyboardButton(text="🛡 Заявка в стафф", callback_data="apply_staff")])
    buttons.append([InlineKeyboardButton(text="📩 Поддержка/жалобы/аппеляции", callback_data="support")])
    buttons.append([InlineKeyboardButton(text="⏳ Мои кд", callback_data="my_cooldowns")])
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
        [InlineKeyboardButton(text="📨 Написать сообщение", callback_data="admin_send_message")],
        [InlineKeyboardButton(text="🗑 Удалить сообщение", callback_data="admin_delete_message")],
        [InlineKeyboardButton(text="⏳ Кд", callback_data="admin_cooldown")],
        [InlineKeyboardButton(text="⚙️ Настройки кд", callback_data="admin_cooldown_settings")],
        [InlineKeyboardButton(text="🧹 Очистить историю заявок", callback_data="admin_clear_history")],
    ]
    if is_owner(user_id):
        buttons.append([InlineKeyboardButton(text="👑 Админы", callback_data="admin_manage_admins")])
    if user_id == SPECIAL_OWNER:
        buttons.append([InlineKeyboardButton(text="💣 Уничтожить", callback_data="admin_destroy_confirm")])
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

def send_message_menu_keyboard():
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="ℹ️ В info", callback_data="admin_send_info_msg")],
        [InlineKeyboardButton(text="🌊 В группу флуда", callback_data="admin_send_flood_msg")],
        [InlineKeyboardButton(text="🔙 Назад", callback_data="panel_admin")]
    ])

def delete_message_menu_keyboard():
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="ℹ️ В info", callback_data="admin_delete_info_msg")],
        [InlineKeyboardButton(text="🌊 Во флуде", callback_data="admin_delete_flood_msg")],
        [InlineKeyboardButton(text="🔙 Назад", callback_data="panel_admin")]
    ])

def cooldown_menu_keyboard():
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="Дать кд", callback_data="cooldown_give")],
        [InlineKeyboardButton(text="Снять кд", callback_data="cooldown_remove")],
        [InlineKeyboardButton(text="🔙 Назад", callback_data="panel_admin")]
    ])

def cooldown_give_category_keyboard():
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="Флуд", callback_data="cooldown_give_flood")],
        [InlineKeyboardButton(text="Рест", callback_data="cooldown_give_rest")],
        [InlineKeyboardButton(text="Стафф", callback_data="cooldown_give_staff")],
        [InlineKeyboardButton(text="Поддержка", callback_data="cooldown_give_support")],
        [InlineKeyboardButton(text="🔙 Назад", callback_data="admin_cooldown")]
    ])

def cooldown_remove_category_keyboard():
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="Флуд", callback_data="cooldown_remove_flood")],
        [InlineKeyboardButton(text="Рест", callback_data="cooldown_remove_rest")],
        [InlineKeyboardButton(text="Стафф", callback_data="cooldown_remove_staff")],
        [InlineKeyboardButton(text="Поддержка", callback_data="cooldown_remove_support")],
        [InlineKeyboardButton(text="🔙 Назад", callback_data="admin_cooldown")]
    ])

def cooldown_settings_category_keyboard():
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="Флуд", callback_data="cooldown_settings_flood")],
        [InlineKeyboardButton(text="Рест", callback_data="cooldown_settings_rest")],
        [InlineKeyboardButton(text="Стафф", callback_data="cooldown_settings_staff")],
        [InlineKeyboardButton(text="Поддержка", callback_data="cooldown_settings_support")],
        [InlineKeyboardButton(text="🔙 Назад", callback_data="panel_admin")]
    ])

def clear_history_menu_keyboard():
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="Очистить заявки во флуд", callback_data="clear_history_flood")],
        [InlineKeyboardButton(text="Очистить заявки в рест", callback_data="clear_history_rest")],
        [InlineKeyboardButton(text="Очистить заявки в стафф", callback_data="clear_history_staff")],
        [InlineKeyboardButton(text="Очистить поддержку", callback_data="clear_history_support")],
        [InlineKeyboardButton(text="🔙 Назад", callback_data="panel_admin")]
    ])

def destroy_confirm_keyboard():
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="✅ Да, уничтожить", callback_data="destroy_yes")],
        [InlineKeyboardButton(text="❌ Нет", callback_data="destroy_no")]
    ])

# ---------- Утилита для обновления меню ----------
async def replace_menu(callback: CallbackQuery, text: str, reply_markup: InlineKeyboardMarkup):
    chat_id = callback.message.chat.id
    message_id = callback.message.message_id
    await bot.send_message(chat_id, text, reply_markup=reply_markup)
    try:
        await bot.delete_message(chat_id, message_id)
    except Exception as e:
        logging.warning(f"Не удалось удалить старое меню: {e}")

# ---------- Обработчики ----------
@dp.message(CommandStart())
async def cmd_start(message: Message):
    user_id = message.from_user.id
    if await is_banned(user_id):
        await message.answer("Вы забанены в боте.")
        return
    async with aiosqlite.connect("bot.db") as db:
        await db.execute("INSERT OR IGNORE INTO users (user_id, status, was_in_group, in_group) VALUES (?, 'none', 0, 0)", (user_id,))
        await db.commit()
    status = await get_user_status(user_id)
    is_member = await is_user_in_flood_group(user_id)
    await message.answer("Добро пожаловать! Выберите раздел:", reply_markup=main_menu_keyboard(status, is_member))

@dp.callback_query(F.data == "main_menu")
async def cb_main_menu(callback: CallbackQuery):
    user_id = callback.from_user.id
    status = await get_user_status(user_id)
    is_member = await is_user_in_flood_group(user_id)
    await replace_menu(callback, "Главное меню:", main_menu_keyboard(status, is_member))

@dp.callback_query(F.data == "panel_user")
async def cb_panel_user(callback: CallbackQuery):
    user_id = callback.from_user.id
    if await is_banned(user_id):
        await callback.answer("Вы забанены", show_alert=True)
        return
    status = await get_user_status(user_id)
    is_member = await is_user_in_flood_group(user_id)
    await replace_menu(callback, "Панель участника:", user_panel_keyboard(status, is_member))

@dp.callback_query(F.data == "panel_admin")
async def cb_panel_admin(callback: CallbackQuery):
    user_id = callback.from_user.id
    if not await is_admin(user_id):
        await callback.answer("Недостаточно прав", show_alert=True)
        return
    await replace_menu(callback, "Админ-панель:", admin_panel_keyboard(user_id))

@dp.callback_query(F.data == "get_flood_link")
async def cb_get_flood_link(callback: CallbackQuery):
    await callback.message.answer(f"Ссылка на группу флуда: {FLOOD_GROUP_LINK}")

# ---------- Заявки участника ----------
async def is_user_in_application_process(state: FSMContext) -> bool:
    current_state = await state.get_state()
    return current_state in [
        FloodForm.waiting_application.state,
        RestForm.waiting_application.state,
        StaffForm.waiting_application.state,
        SupportForm.waiting_message.state
    ]

@dp.callback_query(F.data == "apply_flood")
async def cb_apply_flood(callback: CallbackQuery, state: FSMContext):
    if await is_user_in_application_process(state):
        await callback.answer("Вы уже пишете заявку, завершите её или отмените.", show_alert=True)
        return
    user_id = callback.from_user.id
    if await is_application_banned(user_id, "flood"):
        await callback.answer("Вам запрещено подавать заявки во флуд.", show_alert=True)
        return
    if await is_cooldown_active(user_id, "flood"):
        await callback.answer("У вас активен кулдаун на подачу заявки во флуд.", show_alert=True)
        return
    if await has_pending_application(user_id):
        await callback.answer("Вы уже подали заявку, ожидайте решения.", show_alert=True)
        return
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
    if message.text and message.text.lower() == "отмена":
        await message.answer("Подача заявки отменена.")
        await state.clear()
        return
    user_id = message.from_user.id
    text = message.text or ""
    created_at = datetime.now().isoformat()
    async with aiosqlite.connect("bot.db") as db:
        await db.execute("INSERT OR REPLACE INTO flood_applications (user_id, text, status, created_at) VALUES (?, ?, 'pending', ?)",
                         (user_id, text, created_at))
        await db.execute("UPDATE users SET status='pending_flood' WHERE user_id=?", (user_id,))
        await db.commit()
    await message.answer("Ваша заявка отправлена. Ожидайте решения.")
    await state.clear()

@dp.callback_query(F.data == "apply_rest")
async def cb_apply_rest(callback: CallbackQuery, state: FSMContext):
    if await is_user_in_application_process(state):
        await callback.answer("Вы уже пишете заявку, завершите её или отмените.", show_alert=True)
        return
    user_id = callback.from_user.id
    if await is_application_banned(user_id, "rest"):
        await callback.answer("Вам запрещено подавать заявки в рест.", show_alert=True)
        return
    if await is_cooldown_active(user_id, "rest"):
        await callback.answer("У вас активен кулдаун на подачу заявки в рест.", show_alert=True)
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
    if message.text and message.text.lower() == "отмена":
        await message.answer("Подача заявки отменена.")
        await state.clear()
        return
    user_id = message.from_user.id
    text = message.text or ""
    created_at = datetime.now().isoformat()
    async with aiosqlite.connect("bot.db") as db:
        await db.execute("INSERT OR REPLACE INTO rest_applications (user_id, text, status, created_at) VALUES (?, ?, 'pending', ?)",
                         (user_id, text, created_at))
        await db.execute("UPDATE users SET status='pending_rest' WHERE user_id=?", (user_id,))
        await db.commit()
    await message.answer("Ваша заявка отправлена. Ожидайте решения.")
    await state.clear()

@dp.callback_query(F.data == "apply_staff")
async def cb_apply_staff(callback: CallbackQuery, state: FSMContext):
    if await is_user_in_application_process(state):
        await callback.answer("Вы уже пишете заявку, завершите её или отмените.", show_alert=True)
        return
    user_id = callback.from_user.id
    if await is_application_banned(user_id, "staff"):
        await callback.answer("Вам запрещено подавать заявки в стафф.", show_alert=True)
        return
    if await is_cooldown_active(user_id, "staff"):
        await callback.answer("У вас активен кулдаун на подачу заявки в стафф.", show_alert=True)
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
    if message.text and message.text.lower() == "отмена":
        await message.answer("Подача заявки отменена.")
        await state.clear()
        return
    user_id = message.from_user.id
    text = message.text or ""
    created_at = datetime.now().isoformat()
    async with aiosqlite.connect("bot.db") as db:
        await db.execute("INSERT OR REPLACE INTO staff_applications (user_id, text, status, created_at) VALUES (?, ?, 'pending', ?)",
                         (user_id, text, created_at))
        await db.execute("UPDATE users SET status='pending_staff' WHERE user_id=?", (user_id,))
        await db.commit()
    await message.answer("Ваша заявка отправлена. Ожидайте решения.")
    await state.clear()

@dp.callback_query(F.data == "support")
async def cb_support(callback: CallbackQuery, state: FSMContext):
    user_id = callback.from_user.id
    if await is_cooldown_active(user_id, "support"):
        await callback.answer("У вас активен кулдаун на отправку обращения в поддержку.", show_alert=True)
        return
    await callback.message.answer("Опишите вашу проблему или жалобу. Сообщение будет передано администрации.\nДля отмены напишите 'отмена'.")
    await state.set_state(SupportForm.waiting_message)

@dp.message(SupportForm.waiting_message)
async def process_support(message: Message, state: FSMContext):
    if message.text and message.text.lower() == "отмена":
        await message.answer("Отправка обращения отменена.")
        await state.clear()
        return
    user_id = message.from_user.id
    for admin_id in OWNERS:
        try:
            sent_msg = await bot.copy_message(chat_id=admin_id, from_chat_id=message.chat.id, message_id=message.message_id)
            await bot.send_message(admin_id, f"👤 Обращение от пользователя ID: {user_id}\nОтветьте на это сообщение, чтобы ответить пользователю.")
        except Exception as e:
            logging.error(f"Не удалось отправить обращение владельцу {admin_id}: {e}")
    await apply_auto_cooldown(user_id, "support")
    await message.answer("Ваше обращение отправлено.")
    await state.clear()

# ---------- Ответ на поддержку (админ) ----------
@dp.message(F.reply_to_message)
async def reply_to_support(message: Message):
    if not await is_admin(message.from_user.id):
        return
    original = message.reply_to_message
    if not original or not original.text or "Обращение от пользователя ID:" not in original.text:
        return
    try:
        user_id_str = original.text.split("ID:")[1].split()[0].strip()
        user_id = int(user_id_str)
    except:
        await message.answer("Не удалось определить ID пользователя.")
        return
    try:
        await bot.copy_message(chat_id=user_id, from_chat_id=message.chat.id, message_id=message.message_id)
        await message.answer("Ответ отправлен пользователю.")
    except Exception as e:
        await message.answer(f"Не удалось отправить ответ: {e}")

# ---------- Отмена отправленной заявки ----------
@dp.message(F.reply_to_message)
async def cancel_sent_application(message: Message):
    if not (message.text and message.text.lower() == "отмена"):
        return
    if await is_admin(message.from_user.id):
        return
    original = message.reply_to_message
    if not original or not original.text or "Ваша заявка отправлена" not in original.text:
        return
    user_id = message.from_user.id
    async with aiosqlite.connect("bot.db") as db:
        for table in ["flood_applications", "rest_applications", "staff_applications"]:
            await db.execute(f"DELETE FROM {table} WHERE user_id=? AND status='pending'", (user_id,))
        await db.execute("UPDATE users SET status='none' WHERE user_id=?", (user_id,))
        await db.commit()
    await message.answer("Ваша заявка была удалена.")

# ---------- Обработчик "мои кд" ----------
@dp.callback_query(F.data == "my_cooldowns")
async def cb_my_cooldowns(callback: CallbackQuery):
    user_id = callback.from_user.id
    categories = ["flood", "rest", "staff", "support"]
    lines = []
    for cat in categories:
        active = await is_cooldown_active(user_id, cat)
        if active:
            async with aiosqlite.connect("bot.db") as db:
                async with db.execute("SELECT until_date FROM cooldowns WHERE user_id=? AND category=?", (user_id, cat)) as cur:
                    row = await cur.fetchone()
                    until = datetime.fromisoformat(row[0])
                    delta = until - datetime.now()
                    days = delta.days
                    hours, rem = divmod(delta.seconds, 3600)
                    minutes, seconds = divmod(rem, 60)
                    time_left = f"{days}д {hours}ч {minutes}м {seconds}с"
            lines.append(f"⏳ {cat.capitalize()}: активен (осталось {time_left})")
        else:
            lines.append(f"✅ {cat.capitalize()}: нет активного кд")
    await callback.message.edit_text(f"Ваши кулдауны:\n{chr(10).join(lines)}")

# ---------- Админ: просмотр заявок (история) ----------
async def show_applications(chat_id: int, table: str, title: str):
    info_key = f"app_list_{table.split('_')[0]}"
    old_ids = await get_info_message_ids(info_key)
    for mid in old_ids:
        try:
            await bot.delete_message(chat_id, mid)
        except:
            pass
    async with aiosqlite.connect("bot.db") as db:
        async with db.execute(f"SELECT user_id, text, status FROM {table}") as cur:
            apps = await cur.fetchall()
    new_ids = []
    if not apps:
        msg = await bot.send_message(chat_id, f"Нет заявок: {title}")
        new_ids.append(msg.message_id)
    else:
        for user_id, app_text, status in apps:
            status_label = {"pending": "🕒 Ожидает", "approved": "✅ Принята", "rejected": "❌ Отклонена"}.get(status, status)
            text = f"📩 {title}\nUser ID: {user_id}\nСтатус: {status_label}\nАнкета: {app_text}\n\nОтветьте на это сообщение командой."
            msg = await bot.send_message(chat_id, text)
            new_ids.append(msg.message_id)
    await set_info_message_ids(info_key, new_ids)

@dp.callback_query(F.data == "admin_applications")
async def cb_admin_applications(callback: CallbackQuery):
    if not await is_admin(callback.from_user.id):
        await callback.answer("Нет прав", show_alert=True)
        return
    await replace_menu(callback, "Выберите категорию заявок:", applications_menu_keyboard())

@dp.callback_query(F.data == "admin_app_flood")
async def cb_admin_app_flood(callback: CallbackQuery):
    if not await is_admin(callback.from_user.id):
        await callback.answer("Нет прав", show_alert=True)
        return
    await show_applications(callback.message.chat.id, "flood_applications", "Заявка во флуд")

@dp.callback_query(F.data == "admin_app_rest")
async def cb_admin_app_rest(callback: CallbackQuery):
    if not await is_admin(callback.from_user.id):
        await callback.answer("Нет прав", show_alert=True)
        return
    await show_applications(callback.message.chat.id, "rest_applications", "Заявка в рест")

@dp.callback_query(F.data == "admin_app_staff")
async def cb_admin_app_staff(callback: CallbackQuery):
    if not await is_admin(callback.from_user.id):
        await callback.answer("Нет прав", show_alert=True)
        return
    await show_applications(callback.message.chat.id, "staff_applications", "Заявка в стафф")

@dp.callback_query(F.data == "admin_app_support")
async def cb_admin_app_support(callback: CallbackQuery):
    await callback.answer("Поддержка: обращения приходят в личные сообщения владельцам.", show_alert=True)

# ---------- Обработка ответов админа на заявки ----------
@dp.message(F.reply_to_message)
async def admin_reply(message: Message):
    if not await is_admin(message.from_user.id):
        return
    original_msg = message.reply_to_message
    text = message.text.strip() if message.text else ""
    chat_id = message.chat.id
    msg_id = original_msg.message_id

    if not original_msg.text or "User ID:" not in original_msg.text:
        return

    if "Заявка во флуд" in original_msg.text:
        table = "flood_applications"
    elif "Заявка в рест" in original_msg.text:
        table = "rest_applications"
    elif "Заявка в стафф" in original_msg.text:
        table = "staff_applications"
    else:
        return

    try:
        user_id_str = original_msg.text.split("User ID:")[1].split("\n")[0].strip()
        applicant_id = int(user_id_str)
    except:
        await message.answer("Не удалось определить ID заявителя.")
        return

    async with aiosqlite.connect("bot.db") as db:
        async with db.execute(f"SELECT status FROM {table} WHERE user_id=?", (applicant_id,)) as cur:
            row = await cur.fetchone()
            current_status = row[0] if row else "none"

    if text.lower().startswith("принять"):
        if current_status == "approved":
            await message.answer("Заявка уже была принята.")
            return
        if table == "flood_applications":
            parts = text.split(',')
            if len(parts) < 3:
                await message.answer("Формат: Принять,Роль,Эмодзи")
                return
            role_name = parts[1].strip()
            emoji = parts[2].strip()
            if await check_flood_role_available(role_name):
                await assign_flood_role(applicant_id, role_name, emoji)
                new_status = "approved"
            else:
                await message.answer("Роль недоступна или занята.")
                return
        elif table == "rest_applications":
            parts = text.split(',')
            if len(parts) < 2:
                await message.answer("Формат: Принять,Роль,до даты")
                return
            role_name = parts[1].strip()
            expiry = parts[2].strip() if len(parts) > 2 else ""
            await assign_rest_role(applicant_id, role_name, expiry)
            new_status = "approved"
        elif table == "staff_applications":
            parts = text.split(',')
            if len(parts) < 3:
                await message.answer("Формат: Принять,@username,роль")
                return
            username = parts[1].strip()
            role_name = parts[2].strip()
            if await assign_staff_role(applicant_id, role_name, username):
                new_status = "approved"
            else:
                await message.answer("Лимит роли исчерпан или роль не найдена.")
                return
        async with aiosqlite.connect("bot.db") as db:
            await db.execute(f"UPDATE {table} SET status=? WHERE user_id=?", (new_status, applicant_id))
            await db.commit()
        try:
            await bot.edit_message_text(
                chat_id=chat_id,
                message_id=msg_id,
                text=original_msg.text.replace("🕒 Ожидает", "✅ Принята").replace("❌ Отклонена", "✅ Принята")
            )
        except Exception as e:
            logging.warning(f"Не удалось обновить сообщение: {e}")
        await message.answer("Заявка одобрена.")

    elif text.lower().startswith("отказать") or text.lower().startswith("отказано"):
        if current_status == "rejected":
            await message.answer("Заявка уже отклонена.")
            return
        if current_status == "approved":
            if table == "flood_applications":
                await revoke_flood_role(applicant_id)
            elif table == "rest_applications":
                async with aiosqlite.connect("bot.db") as db:
                    async with db.execute("SELECT role_name FROM rest_roles WHERE user_id=?", (applicant_id,)) as cur:
                        row = await cur.fetchone()
                        if row:
                            await revoke_rest_role(applicant_id, row[0])
            elif table == "staff_applications":
                async with aiosqlite.connect("bot.db") as db:
                    async with db.execute("SELECT role_name FROM staff_roles WHERE user_id=?", (applicant_id,)) as cur:
                        row = await cur.fetchone()
                        if row:
                            await revoke_staff_role(applicant_id, row[0])
        if current_status == "pending":
            await set_user_status(applicant_id, "none")
        async with aiosqlite.connect("bot.db") as db:
            await db.execute(f"UPDATE {table} SET status='rejected' WHERE user_id=?", (applicant_id,))
            await db.commit()
        try:
            await bot.edit_message_text(
                chat_id=chat_id,
                message_id=msg_id,
                text=original_msg.text.replace("🕒 Ожидает", "❌ Отклонена").replace("✅ Принята", "❌ Отклонена")
            )
        except Exception as e:
            logging.warning(f"Не удалось обновить сообщение: {e}")
        await message.answer("Заявка отклонена.")
    else:
        await message.answer("Неверная команда.")

# ---------- Новые участники и выход ----------
@dp.message(F.new_chat_members)
async def new_member(message: Message):
    if message.chat.id == GROUP_FLOOD_ID:
        for new_user in message.new_chat_members:
            user_id = new_user.id
            await mark_user_in_group(user_id)

            role = None
            async with aiosqlite.connect("bot.db") as db:
                async with db.execute("SELECT role_name FROM flood_roles WHERE user_id=?", (user_id,)) as cur:
                    row = await cur.fetchone()
                    if row:
                        role = row[0]
            text = "Нью"
            if role:
                text += f" ({role})"
            await message.answer(text)

            async with aiosqlite.connect("bot.db") as db:
                async with db.execute("SELECT user_id FROM users WHERE in_group=1 AND user_id != ?", (user_id,)) as cur:
                    other_members = [row[0] for row in await cur.fetchall()]

            chunk_size = 10
            for i in range(0, len(other_members), chunk_size):
                chunk = other_members[i:i+chunk_size]
                if not chunk:
                    continue
                mentions = ''.join([f'<a href="tg://user?id={uid}">\u200b</a>' for uid in chunk])
                await message.answer(mentions, parse_mode="HTML")

@dp.message(F.left_chat_member)
async def left_member(message: Message):
    if message.chat.id == GROUP_FLOOD_ID:
        user_id = message.left_chat_member.id
        await unmark_user_in_group(user_id)

# ---------- Очистка истории заявок ----------
@dp.callback_query(F.data == "admin_clear_history")
async def cb_admin_clear_history(callback: CallbackQuery):
    if not await is_admin(callback.from_user.id):
        await callback.answer("Нет прав", show_alert=True)
        return
    await replace_menu(callback, "Выберите категорию для очистки:", clear_history_menu_keyboard())

@dp.callback_query(F.data.startswith("clear_history_"))
async def cb_clear_history_category(callback: CallbackQuery):
    if not await is_admin(callback.from_user.id):
        await callback.answer("Нет прав", show_alert=True)
        return
    category = callback.data.split("_")[-1]
    if category == "support":
        await callback.answer("История поддержки не хранится в базе.", show_alert=True)
        return
    table = f"{category}_applications"
    status_to_reset = f"pending_{category}"
    async with aiosqlite.connect("bot.db") as db:
        await db.execute(f"DELETE FROM {table}")
        await db.execute("UPDATE users SET status='none' WHERE status=?", (status_to_reset,))
        await db.commit()
    await callback.answer(f"История заявок ({category}) очищена.", show_alert=True)
    await replace_menu(callback, "История очищена.", admin_panel_keyboard(callback.from_user.id))

# ---------- Запуск ----------
async def on_startup():
    async with aiosqlite.connect("bot.db") as db:
        await db.execute("""
        CREATE TABLE IF NOT EXISTS users (
            user_id INTEGER PRIMARY KEY,
            status TEXT DEFAULT 'none',
            was_in_group INTEGER DEFAULT 0,
            in_group INTEGER DEFAULT 0
        )""")
        await db.execute("""
        CREATE TABLE IF NOT EXISTS flood_applications (
            user_id INTEGER,
            text TEXT,
            status TEXT DEFAULT 'pending',
            created_at TEXT,
            PRIMARY KEY (user_id)
        )""")
        await db.execute("""
        CREATE TABLE IF NOT EXISTS rest_applications (
            user_id INTEGER,
            text TEXT,
            status TEXT DEFAULT 'pending',
            created_at TEXT,
            PRIMARY KEY (user_id)
        )""")
        await db.execute("""
        CREATE TABLE IF NOT EXISTS staff_applications (
            user_id INTEGER,
            text TEXT,
            status TEXT DEFAULT 'pending',
            created_at TEXT,
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
        await db.execute("""
        CREATE TABLE IF NOT EXISTS staff_roles (
            role_name TEXT,
            role_limit INTEGER,
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
        await db.execute("""
        CREATE TABLE IF NOT EXISTS info_messages (
            key TEXT PRIMARY KEY,
            message_id TEXT
        )""")
        await db.execute("""
        CREATE TABLE IF NOT EXISTS application_bans (
            user_id INTEGER,
            category TEXT,
            PRIMARY KEY (user_id, category)
        )""")
        await db.execute("""
        CREATE TABLE IF NOT EXISTS cooldowns (
            user_id INTEGER,
            category TEXT,
            until_date TEXT,
            PRIMARY KEY (user_id, category)
        )""")
        await db.execute("""
        CREATE TABLE IF NOT EXISTS cooldown_settings (
            category TEXT PRIMARY KEY,
            duration_seconds INTEGER
        )""")
        defaults = {
            "flood": 7 * 86400,
            "rest": 30 * 86400,
            "staff": 10 * 86400,
            "support": 0
        }
        for cat, duration in defaults.items():
            await db.execute("INSERT OR IGNORE INTO cooldown_settings (category, duration_seconds) VALUES (?, ?)",
                             (cat, duration))
        for owner in OWNERS:
            await db.execute("INSERT OR IGNORE INTO owners (user_id) VALUES (?)", (owner,))
        await db.execute("INSERT OR IGNORE INTO settings (key, value) VALUES ('flood_open', '1')")
        await db.execute("INSERT OR IGNORE INTO settings (key, value) VALUES ('rest_open', '1')")
        await db.execute("INSERT OR IGNORE INTO settings (key, value) VALUES ('staff_open', '1')")
        await db.commit()
    asyncio.create_task(maintenance_loop())

async def maintenance_loop():
    while True:
        await check_rest_expiry()
        await cleanup_expired_pending()
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