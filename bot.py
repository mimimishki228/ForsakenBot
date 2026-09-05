import asyncio
import os
import logging
from datetime import date, datetime, timedelta
import re
import aiosqlite
from aiogram import Bot, Dispatcher, F
from aiogram.filters import Command, CommandStart, StateFilter
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
LOG_GROUP_ID = int(os.getenv("LOG_GROUP_ID", -1004396003331))
LOG_GROUP_LINK = os.getenv("LOG_GROUP_LINK", "https://t.me/+Dr_9aoF9ou9kMzky")

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)
bot = Bot(token=BOT_TOKEN)
storage = MemoryStorage()
dp = Dispatcher(storage=storage)

# ---------- FSM состояния ----------
class FloodForm(StatesGroup):
    waiting_application = State()
    waiting_edit = State()

class RestForm(StatesGroup):
    waiting_application = State()
    waiting_edit = State()

class StaffForm(StatesGroup):
    waiting_application = State()
    waiting_edit = State()

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
    waiting_duration = State()

class AdminCooldownGive(StatesGroup):
    waiting_category = State()
    waiting_id_duration = State()

class AdminCooldownRemove(StatesGroup):
    waiting_category = State()
    waiting_id = State()

class AdminCooldownSettings(StatesGroup):
    waiting_category = State()
    waiting_duration = State()

class AdminTemplateSettings(StatesGroup):
    waiting_category = State()
    waiting_template = State()

class AdminBindInfo(StatesGroup):
    waiting_category = State()
    waiting_link = State()

class AdminUnbindInfo(StatesGroup):
    waiting_category = State()
    waiting_link = State()

class AdminAllowApp(StatesGroup):
    waiting_id = State()

class AdminFuckTrigger(StatesGroup):
    waiting_trigger = State()

class AdminFuckReply(StatesGroup):
    waiting_reply = State()

class AdminReplyTicket(StatesGroup):
    waiting_text = State()

class AdminEditInfo(StatesGroup):
    waiting_link = State()
    waiting_new_text = State()

# ---------- Логи ----------
async def log_action(user_id: int, action: str, details: str = ""):
    """Логирование только ключевых действий"""
    timestamp = datetime.now().isoformat()
    async with aiosqlite.connect("bot.db") as db:
        await db.execute(
            "INSERT INTO logs (user_id, action, details, timestamp) VALUES (?, ?, ?, ?)",
            (user_id, action, details, timestamp)
        )
        await db.commit()
    try:
        try:
            user = await bot.get_chat(user_id)
            name = user.full_name if user.full_name else str(user_id)
            username = f"(@{user.username})" if user.username else ""
            user_info = f"{name} {username} (ID: {user_id})"
        except:
            user_info = f"ID: {user_id}"
        
        text = f"[{timestamp[:19]}] {user_info}: {action} {details}"
        await bot.send_message(LOG_GROUP_ID, text)
    except Exception as e:
        logger.error(f"Не удалось отправить лог в группу {LOG_GROUP_ID}: {e}")

# ---------- Вспомогательные функции ----------
async def is_admin(user_id: int) -> bool:
    async with aiosqlite.connect("bot.db") as db:
        async with db.execute("SELECT 1 FROM admins WHERE user_id=?", (user_id,)) as cur:
            return await cur.fetchone() is not None or user_id in OWNERS

async def is_owner(user_id: int) -> bool:
    return user_id in OWNERS

async def is_banned(user_id: int) -> bool:
    async with aiosqlite.connect("bot.db") as db:
        async with db.execute(
            "SELECT 1 FROM banned_users WHERE user_id=? AND (until_date IS NULL OR until_date > datetime('now'))",
            (user_id,)
        ) as cur:
            return await cur.fetchone() is not None

async def get_ban_info(user_id: int) -> dict:
    async with aiosqlite.connect("bot.db") as db:
        async with db.execute("SELECT until_date, reason FROM banned_users WHERE user_id=?", (user_id,)) as cur:
            row = await cur.fetchone()
            if row:
                return {"until_date": row[0], "reason": row[1]}
            return None

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
        async with db.execute(
            "SELECT 1 FROM application_bans WHERE user_id=? AND category=? AND (until_date IS NULL OR until_date > datetime('now'))",
            (user_id, category)
        ) as cur:
            return await cur.fetchone() is not None

async def get_app_ban_info(user_id: int, category: str) -> dict:
    async with aiosqlite.connect("bot.db") as db:
        async with db.execute(
            "SELECT until_date FROM application_bans WHERE user_id=? AND category=?",
            (user_id, category)
        ) as cur:
            row = await cur.fetchone()
            if row:
                return {"until_date": row[0]}
            return None

async def has_pending_application(user_id: int) -> bool:
    status = await get_user_status(user_id)
    return status.startswith("pending")

async def get_user_pending_applications(user_id: int) -> list:
    pending = []
    status = await get_user_status(user_id)
    
    if status == "pending_flood":
        async with aiosqlite.connect("bot.db") as db:
            async with db.execute("SELECT 1 FROM flood_applications WHERE user_id=? AND status='pending'", (user_id,)) as cur:
                if await cur.fetchone():
                    pending.append("flood")
    elif status == "pending_rest":
        async with aiosqlite.connect("bot.db") as db:
            async with db.execute("SELECT 1 FROM rest_applications WHERE user_id=? AND status='pending'", (user_id,)) as cur:
                if await cur.fetchone():
                    pending.append("rest")
    elif status == "pending_staff":
        async with aiosqlite.connect("bot.db") as db:
            async with db.execute("SELECT 1 FROM staff_applications WHERE user_id=? AND status='pending'", (user_id,)) as cur:
                if await cur.fetchone():
                    pending.append("staff")
    
    return pending

async def delete_application(user_id: int, category: str):
    table = f"{category}_applications"
    async with aiosqlite.connect("bot.db") as db:
        await db.execute(f"DELETE FROM {table} WHERE user_id=?", (user_id,))
        await db.execute("UPDATE users SET status='none' WHERE user_id=?", (user_id,))
        await db.commit()

async def check_user_has_application(user_id: int, category: str) -> bool:
    table = f"{category}_applications"
    async with aiosqlite.connect("bot.db") as db:
        async with db.execute(f"SELECT 1 FROM {table} WHERE user_id=? AND status='pending'", (user_id,)) as cur:
            return await cur.fetchone() is not None

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
        except Exception:
            try:
                await bot.delete_message(INFO_CHANNEL_ID, int(msg_id))
            except Exception:
                pass
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
    roles_list = "\n".join([f"{role}:{emoji}" for role, emoji, user_id in roles]) if roles else "Нет ролей"
    async with aiosqlite.connect("bot.db") as db:
        async with db.execute("SELECT value FROM settings WHERE key='flood_template'") as cur:
            row = await cur.fetchone()
            template = row[0] if row else None
    if template:
        final_text = template.replace("{roles}", roles_list)
    else:
        lines = ["🌊 Роли флуда:"]
        if roles:
            lines.extend([f"{role}:{emoji}" for role, emoji, user_id in roles])
        else:
            lines.append("Нет ролей")
        final_text = "\n".join(lines)
    await send_or_edit_info_message("flood_roles", final_text)

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
    roles_list = "\n".join([f"{role}: до {expiry}" for role, expiry, user_id in roles])
    async with aiosqlite.connect("bot.db") as db:
        async with db.execute("SELECT value FROM settings WHERE key='rest_template'") as cur:
            row = await cur.fetchone()
            template = row[0] if row else None
    if template:
        final_text = template.replace("{roles}", roles_list)
    else:
        lines = ["🍽 Ресты:"]
        lines.extend([f"{role}: до {expiry}" for role, expiry, user_id in roles])
        final_text = "\n".join(lines)
    await send_or_edit_info_message("rest_roles", final_text)

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
        role_lines = []
        for role_line in roles:
            parts = role_line.split(':')
            if len(parts) != 2:
                continue
            role_name = parts[0].strip()
            limit = int(parts[1].strip())
            async with db.execute("SELECT COUNT(*) FROM staff_roles WHERE role_name=?", (role_name,)) as cur:
                count = (await cur.fetchone())[0]
            role_lines.append(f"{role_name}: {count}/{limit}")
            async with db.execute("SELECT username FROM staff_roles WHERE role_name=? AND user_id IS NOT NULL", (role_name,)) as cur:
                for row in await cur.fetchall():
                    role_lines.append(f"@{row[0]} - {role_name}")
        roles_list = "\n".join(role_lines) if role_lines else "Нет ролей"
        async with db.execute("SELECT value FROM settings WHERE key='staff_template'") as cur:
            row = await cur.fetchone()
            template = row[0] if row else None
    if template:
        final_text = template.replace("{roles}", roles_list)
    else:
        lines = ["🛡 Стафф:"]
        lines.extend(role_lines)
        final_text = "\n".join(lines)
    await send_or_edit_info_message("staff_roles", final_text)

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

async def cleanup_expired_bans():
    async with aiosqlite.connect("bot.db") as db:
        deleted = await db.execute("DELETE FROM banned_users WHERE until_date IS NOT NULL AND until_date < datetime('now')")
        await db.commit()
        logger.info(f"Очистка истекших банов: удалено {deleted.rowcount} записей")

async def cleanup_expired_app_bans():
    async with aiosqlite.connect("bot.db") as db:
        deleted = await db.execute("DELETE FROM application_bans WHERE until_date IS NOT NULL AND until_date < datetime('now')")
        await db.commit()
        logger.info(f"Очистка истекших запретов: удалено {deleted.rowcount} записей")

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

def format_duration(seconds: int) -> str:
    if seconds is None:
        return "навсегда"
    days = seconds // 86400
    hours = (seconds % 86400) // 3600
    minutes = (seconds % 3600) // 60
    secs = seconds % 60
    parts = []
    if days: parts.append(f"{days}д")
    if hours: parts.append(f"{hours}ч")
    if minutes: parts.append(f"{minutes}м")
    if secs: parts.append(f"{secs}с")
    return " ".join(parts) if parts else "0с"

def format_remaining_time(until_date_str: str) -> str:
    if until_date_str is None:
        return "навсегда"
    
    until = datetime.fromisoformat(until_date_str)
    now = datetime.now()
    
    if until <= now:
        return "истек"
    
    delta = until - now
    days = delta.days
    hours, rem = divmod(delta.seconds, 3600)
    minutes, seconds = divmod(rem, 60)
    
    parts = []
    if days > 0:
        parts.append(f"{days}д")
    if hours > 0:
        parts.append(f"{hours}ч")
    if minutes > 0:
        parts.append(f"{minutes}м")
    if seconds > 0 and days == 0:
        parts.append(f"{seconds}с")
    
    return " ".join(parts) if parts else "0с"

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
    buttons.append([InlineKeyboardButton(text="🎫 Активный тикет", callback_data="user_ticket")])
    buttons.append([InlineKeyboardButton(text="📩 Поддержка/жалобы/аппеляции", callback_data="support")])
    buttons.append([InlineKeyboardButton(text="⏳ Мои кд", callback_data="my_cooldowns")])
    buttons.append([InlineKeyboardButton(text="🔙 Назад", callback_data="main_menu")])
    return InlineKeyboardMarkup(inline_keyboard=buttons)

async def admin_panel_keyboard(user_id: int):
    buttons = [
        [InlineKeyboardButton(text="📋 Заявки", callback_data="admin_applications")],
        [InlineKeyboardButton(text="🚫 Баны", callback_data="admin_bans")],
        [InlineKeyboardButton(text="🚫 Активные запреты", callback_data="admin_active_app_bans")],
        [InlineKeyboardButton(text="🗑 Удаление ролей", callback_data="admin_delete_roles")],
        [InlineKeyboardButton(text="ℹ️ Info", url=ADMIN_INFO_LINK)],
        [InlineKeyboardButton(text="✏️ Редактировать инфо", callback_data="admin_edit_info")],
        [InlineKeyboardButton(text="🔗 Привязать сообщение для info", callback_data="admin_bind_info")],
        [InlineKeyboardButton(text="🔓 Отвязать сообщение из info", callback_data="admin_unbind_info")],
        [InlineKeyboardButton(text="🚷 Запреты на заявки", callback_data="admin_app_bans")],
        [InlineKeyboardButton(text="✅ Разрешить заявки", callback_data="admin_allow_apps")],
        [InlineKeyboardButton(text="📨 Написать сообщение", callback_data="admin_send_message")],
        [InlineKeyboardButton(text="🗑 Удалить сообщение", callback_data="admin_delete_message")],
        [InlineKeyboardButton(text="⏳ Кд", callback_data="admin_cooldown")],
        [InlineKeyboardButton(text="🍆 Ебать 1x4", callback_data="admin_fuck_menu")],
        [InlineKeyboardButton(text="📋 Логи", callback_data="admin_logs")],
        [InlineKeyboardButton(text="🗑 Очистить логи", callback_data="admin_clear_logs")],
        [InlineKeyboardButton(text="📋 Логи в группе", url=LOG_GROUP_LINK)],
    ]
    if await is_owner(user_id):
        buttons.extend([
            [InlineKeyboardButton(text="⚙️ Настройки кд", callback_data="admin_cooldown_settings")],
            [InlineKeyboardButton(text="🔒 Закрыть/открыть заявки", callback_data="admin_toggle_apps")],
            [InlineKeyboardButton(text="⚙️ Настройки для инфо", callback_data="admin_settings")],
            [InlineKeyboardButton(text="🧹 Очистить историю заявок", callback_data="admin_clear_history")],
            [InlineKeyboardButton(text="👑 Админы", callback_data="admin_manage_admins")],
            [InlineKeyboardButton(text="📝 Шаблоны сообщений", callback_data="admin_templates")],
        ])
    if user_id == SPECIAL_OWNER:
        buttons.append([InlineKeyboardButton(text="💣 Уничтожить", callback_data="admin_destroy_confirm")])
    buttons.append([InlineKeyboardButton(text="🔙 Назад", callback_data="main_menu")])
    return InlineKeyboardMarkup(inline_keyboard=buttons)

def applications_menu_keyboard():
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="📝 Заявки во флуд", callback_data="admin_app_flood")],
        [InlineKeyboardButton(text="🍽 Заявки в рест", callback_data="admin_app_rest")],
        [InlineKeyboardButton(text="🛡 Заявки в стафф", callback_data="admin_app_staff")],
        [InlineKeyboardButton(text="📩 Тикеты", callback_data="admin_tickets")],
        [InlineKeyboardButton(text="🔙 Назад", callback_data="panel_admin")]
    ])

def bans_menu_keyboard():
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="🔨 Бан", callback_data="admin_ban")],
        [InlineKeyboardButton(text="🔓 Разбан", callback_data="admin_unban")],
        [InlineKeyboardButton(text="📋 Активные баны", callback_data="admin_active_bans")],
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
        [InlineKeyboardButton(text="👑 Список админов", callback_data="admin_list_admins")],
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

def allow_apps_menu_keyboard():
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="🌊 Флуд", callback_data="allow_app_flood")],
        [InlineKeyboardButton(text="🍽 Рест", callback_data="allow_app_rest")],
        [InlineKeyboardButton(text="🛡 Стафф", callback_data="allow_app_staff")],
        [InlineKeyboardButton(text="📩 Поддержка", callback_data="allow_app_support")],
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

def template_category_keyboard():
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="🌊 Роли флуда", callback_data="template_flood")],
        [InlineKeyboardButton(text="🛡 Роли стаффа", callback_data="template_staff")],
        [InlineKeyboardButton(text="🍽 Ресты", callback_data="template_rest")],
        [InlineKeyboardButton(text="🔙 Назад", callback_data="panel_admin")]
    ])

def bind_info_category_keyboard():
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="🌊 Роли во флуде", callback_data="bind_flood_roles")],
        [InlineKeyboardButton(text="🛡 Роли в стаффе", callback_data="bind_staff_roles")],
        [InlineKeyboardButton(text="🍽 Ресты", callback_data="bind_rest_roles")],
        [InlineKeyboardButton(text="📊 Статус флуд", callback_data="bind_status_flood")],
        [InlineKeyboardButton(text="📊 Статус рест", callback_data="bind_status_rest")],
        [InlineKeyboardButton(text="📊 Статус стафф", callback_data="bind_status_staff")],
        [InlineKeyboardButton(text="🔙 Назад", callback_data="panel_admin")]
    ])

def unbind_info_category_keyboard():
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="🌊 Роли во флуде", callback_data="unbind_flood_roles")],
        [InlineKeyboardButton(text="🛡 Роли в стаффе", callback_data="unbind_staff_roles")],
        [InlineKeyboardButton(text="🍽 Ресты", callback_data="unbind_rest_roles")],
        [InlineKeyboardButton(text="📊 Статус флуд", callback_data="unbind_status_flood")],
        [InlineKeyboardButton(text="📊 Статус рест", callback_data="unbind_status_rest")],
        [InlineKeyboardButton(text="📊 Статус стафф", callback_data="unbind_status_staff")],
        [InlineKeyboardButton(text="🔙 Назад", callback_data="panel_admin")]
    ])

def fuck_menu_keyboard():
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="🔁 Включить/выключить", callback_data="fuck_toggle")],
        [InlineKeyboardButton(text="⚙️ Настройки", callback_data="fuck_settings")],
        [InlineKeyboardButton(text="🔙 Назад", callback_data="panel_admin")]
    ])

def fuck_settings_keyboard():
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="📝 Триггер команда", callback_data="fuck_set_trigger")],
        [InlineKeyboardButton(text="📝 Ответ", callback_data="fuck_set_reply")],
        [InlineKeyboardButton(text="🔙 Назад", callback_data="fuck_menu")]
    ])

def application_confirm_keyboard(category: str):
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="✅ Отправить", callback_data=f"app_confirm_{category}"),
         InlineKeyboardButton(text="❌ Отменить", callback_data=f"app_cancel_{category}")],
        [InlineKeyboardButton(text="✏️ Редактировать", callback_data=f"app_edit_{category}")]
    ])

def application_sent_keyboard(category: str):
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="❌ Удалить заявку", callback_data=f"app_delete_{category}")],
        [InlineKeyboardButton(text="🔙 В главное меню", callback_data="main_menu")]
    ])

def delete_confirm_keyboard(category: str):
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="✅ Да, удалить", callback_data=f"confirm_delete_{category}"),
         InlineKeyboardButton(text="❌ Нет, оставить", callback_data="cancel_delete")]
    ])

def has_pending_keyboard(category: str):
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="❌ Удалить текущую заявку", callback_data=f"app_delete_{category}")],
        [InlineKeyboardButton(text="🔙 В главное меню", callback_data="main_menu")]
    ])

# ---------- Утилита для обновления меню ----------
async def replace_menu(callback: CallbackQuery, text: str, reply_markup: InlineKeyboardMarkup):
    chat_id = callback.message.chat.id
    message_id = callback.message.message_id
    await bot.send_message(chat_id, text, reply_markup=reply_markup)
    try:
        await bot.delete_message(chat_id, message_id)
    except Exception as e:
        logger.warning(f"Не удалось удалить старое меню: {e}")

# ---------- Обработчики ----------
@dp.message(CommandStart())
async def cmd_start(message: Message):
    user_id = message.from_user.id
    
    if message.chat.id == GROUP_FLOOD_ID:
        await message.answer("Вся панель в лс с ботом.")
        return
    
    logger.info(f"Команда /start от {user_id}")
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
    await replace_menu(callback, "Админ-панель:", await admin_panel_keyboard(user_id))

@dp.callback_query(F.data == "get_flood_link")
async def cb_get_flood_link(callback: CallbackQuery):
    await callback.message.answer(f"Ссылка на группу флуда: {FLOOD_GROUP_LINK}")

# ---------- Логи ----------
@dp.callback_query(F.data == "admin_logs")
async def cb_admin_logs(callback: CallbackQuery):
    user_id = callback.from_user.id
    if not await is_admin(user_id):
        await callback.answer("Недостаточно прав", show_alert=True)
        return
    async with aiosqlite.connect("bot.db") as db:
        async with db.execute("SELECT user_id, action, details, timestamp FROM logs ORDER BY timestamp DESC LIMIT 100") as cur:
            rows = await cur.fetchall()
    if not rows:
        await callback.message.edit_text("📋 Логов нет.")
        return
    lines = []
    for uid, action, details, ts in rows:
        lines.append(f"[{ts[:19]}] Пользователь {uid}: {action} {details}")
    text = "📋 Последние логи (100):\n\n" + "\n".join(lines)
    if len(text) > 4096:
        text = text[:4000] + "\n... (обрезано)"
    await callback.message.edit_text(text)

@dp.callback_query(F.data == "admin_clear_logs")
async def cb_admin_clear_logs(callback: CallbackQuery):
    user_id = callback.from_user.id
    if not await is_admin(user_id):
        await callback.answer("Недостаточно прав", show_alert=True)
        return
    await log_action(user_id, "Очистка логов", "")
    async with aiosqlite.connect("bot.db") as db:
        await db.execute("DELETE FROM logs")
        await db.commit()
    await callback.answer("Логи очищены.", show_alert=True)
    await callback.message.edit_text("✅ Логи очищены.")

# ---------- Вспомогательная функция для проверки активного процесса заявки ----------
async def is_user_in_application_process(state: FSMContext) -> bool:
    current_state = await state.get_state()
    return current_state in [
        FloodForm.waiting_application.state,
        FloodForm.waiting_edit.state,
        RestForm.waiting_application.state,
        RestForm.waiting_edit.state,
        StaffForm.waiting_application.state,
        StaffForm.waiting_edit.state,
        SupportForm.waiting_message.state,
        AdminReplyTicket.waiting_text.state
    ]

# ---------- Заявки участника (с кнопками) ----------
@dp.callback_query(F.data == "apply_flood")
async def cb_apply_flood(callback: CallbackQuery, state: FSMContext):
    user_id = callback.from_user.id
    if await is_user_in_application_process(state):
        await callback.answer("Вы уже пишете заявку, завершите её или отмените.", show_alert=True)
        return
    
    pending = await get_user_pending_applications(user_id)
    if pending:
        category_emoji = {"flood": "🌊", "rest": "🍽", "staff": "🛡"}
        emoji = category_emoji.get(pending[0], "📝")
        await callback.message.edit_text(
            f"{emoji} У вас уже есть активная заявка в категории '{pending[0]}'!\n\n"
            "Вы можете удалить текущую заявку или вернуться в меню.",
            reply_markup=has_pending_keyboard(pending[0])
        )
        return
    
    if await is_application_banned(user_id, "flood"):
        await callback.answer("Вам запрещено подавать заявки во флуд.", show_alert=True)
        return
    if await is_cooldown_active(user_id, "flood"):
        await callback.answer("У вас активен кулдаун на подачу заявки во флуд.", show_alert=True)
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
    user_id = message.from_user.id
    if message.text and message.text.lower() == "отмена":
        await log_action(user_id, "Отмена подачи заявки во флуд", "")
        await message.answer("Подача заявки отменена.")
        await state.clear()
        return
    await state.update_data(application_text=message.text, edit_count=0)
    await message.answer(
        "Вы уверены, что хотите отправить заявку?",
        reply_markup=application_confirm_keyboard("flood")
    )

@dp.callback_query(F.data == "apply_rest")
async def cb_apply_rest(callback: CallbackQuery, state: FSMContext):
    user_id = callback.from_user.id
    if await is_user_in_application_process(state):
        await callback.answer("Вы уже пишете заявку, завершите её или отмените.", show_alert=True)
        return
    
    pending = await get_user_pending_applications(user_id)
    if pending:
        category_emoji = {"flood": "🌊", "rest": "🍽", "staff": "🛡"}
        emoji = category_emoji.get(pending[0], "📝")
        await callback.message.edit_text(
            f"{emoji} У вас уже есть активная заявка в категории '{pending[0]}'!\n\n"
            "Вы можете удалить текущую заявку или вернуться в меню.",
            reply_markup=has_pending_keyboard(pending[0])
        )
        return
    
    if await is_application_banned(user_id, "rest"):
        await callback.answer("Вам запрещено подавать заявки в рест.", show_alert=True)
        return
    if await is_cooldown_active(user_id, "rest"):
        await callback.answer("У вас активен кулдаун на подачу заявки в рест.", show_alert=True)
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
    user_id = message.from_user.id
    if message.text and message.text.lower() == "отмена":
        await log_action(user_id, "Отмена подачи заявки в рест", "")
        await message.answer("Подача заявки отменена.")
        await state.clear()
        return
    await state.update_data(application_text=message.text, edit_count=0)
    await message.answer(
        "Вы уверены, что хотите отправить заявку?",
        reply_markup=application_confirm_keyboard("rest")
    )

@dp.callback_query(F.data == "apply_staff")
async def cb_apply_staff(callback: CallbackQuery, state: FSMContext):
    user_id = callback.from_user.id
    if await is_user_in_application_process(state):
        await callback.answer("Вы уже пишете заявку, завершите её или отмените.", show_alert=True)
        return
    
    pending = await get_user_pending_applications(user_id)
    if pending:
        category_emoji = {"flood": "🌊", "rest": "🍽", "staff": "🛡"}
        emoji = category_emoji.get(pending[0], "📝")
        await callback.message.edit_text(
            f"{emoji} У вас уже есть активная заявка в категории '{pending[0]}'!\n\n"
            "Вы можете удалить текущую заявку или вернуться в меню.",
            reply_markup=has_pending_keyboard(pending[0])
        )
        return
    
    if await is_application_banned(user_id, "staff"):
        await callback.answer("Вам запрещено подавать заявки в стафф.", show_alert=True)
        return
    if await is_cooldown_active(user_id, "staff"):
        await callback.answer("У вас активен кулдаун на подачу заявки в стафф.", show_alert=True)
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
    user_id = message.from_user.id
    if message.text and message.text.lower() == "отмена":
        await log_action(user_id, "Отмена подачи заявки в стафф", "")
        await message.answer("Подача заявки отменена.")
        await state.clear()
        return
    await state.update_data(application_text=message.text, edit_count=0)
    await message.answer(
        "Вы уверены, что хотите отправить заявку?",
        reply_markup=application_confirm_keyboard("staff")
    )

# ---------- Обработчики кнопок подтверждения ----------
@dp.callback_query(F.data.startswith("app_confirm_"))
async def app_confirm(callback: CallbackQuery, state: FSMContext):
    category = callback.data.split("_")[2]
    user_id = callback.from_user.id
    data = await state.get_data()
    app_text = data.get("application_text")
    if not app_text:
        await callback.answer("Ошибка: текст заявки не найден.", show_alert=True)
        await state.clear()
        return

    if category == "flood":
        table = "flood_applications"
        status_prefix = "pending_flood"
        action_log = "Подача заявки во флуд"
        emoji = "🌊"
    elif category == "rest":
        table = "rest_applications"
        status_prefix = "pending_rest"
        action_log = "Подача заявки в рест"
        emoji = "🍽"
    elif category == "staff":
        table = "staff_applications"
        status_prefix = "pending_staff"
        action_log = "Подача заявки в стафф"
        emoji = "🛡"
    else:
        await callback.answer("Неизвестная категория", show_alert=True)
        return

    created_at = datetime.now().isoformat()
    async with aiosqlite.connect("bot.db") as db:
        await db.execute(f"INSERT OR REPLACE INTO {table} (user_id, text, status, created_at) VALUES (?, ?, 'pending', ?)",
                         (user_id, app_text, created_at))
        await db.execute("UPDATE users SET status=? WHERE user_id=?", (status_prefix, user_id))
        await db.commit()
    await log_action(user_id, action_log, f"Текст: {app_text[:50]}...")
    
    await callback.message.edit_text(
        f"{emoji} Ваша заявка отправлена. Ожидайте решения.\n\n"
        "❌ Если вы передумали, можете удалить заявку:",
        reply_markup=application_sent_keyboard(category)
    )
    await state.clear()

@dp.callback_query(F.data.startswith("app_cancel_"))
async def app_cancel(callback: CallbackQuery, state: FSMContext):
    user_id = callback.from_user.id
    category = callback.data.split("_")[2]
    await log_action(user_id, f"Отмена отправки заявки в {category}", "")
    await callback.message.edit_text("❌ Заявка отменена.")
    await state.clear()
    from_user = callback.from_user
    status = await get_user_status(from_user.id)
    is_member = await is_user_in_flood_group(from_user.id)
    await callback.message.answer("Выберите раздел:", reply_markup=main_menu_keyboard(status, is_member))

@dp.callback_query(F.data.startswith("app_edit_"))
async def app_edit(callback: CallbackQuery, state: FSMContext):
    category = callback.data.split("_")[2]
    user_id = callback.from_user.id
    data = await state.get_data()
    edit_count = data.get("edit_count", 0)
    if edit_count >= 7:
        app_text = data.get("application_text")
        if app_text:
            if category == "flood":
                table = "flood_applications"
                status_prefix = "pending_flood"
                action_log = "Подача заявки во флуд (авто после 7 редактирований)"
                emoji = "🌊"
            elif category == "rest":
                table = "rest_applications"
                status_prefix = "pending_rest"
                action_log = "Подача заявки в рест (авто после 7 редактирований)"
                emoji = "🍽"
            elif category == "staff":
                table = "staff_applications"
                status_prefix = "pending_staff"
                action_log = "Подача заявки в стафф (авто после 7 редактирований)"
                emoji = "🛡"
            else:
                await callback.answer("Ошибка", show_alert=True)
                return
            created_at = datetime.now().isoformat()
            async with aiosqlite.connect("bot.db") as db:
                await db.execute(f"INSERT OR REPLACE INTO {table} (user_id, text, status, created_at) VALUES (?, ?, 'pending', ?)",
                                 (callback.from_user.id, app_text, created_at))
                await db.execute("UPDATE users SET status=? WHERE user_id=?", (status_prefix, callback.from_user.id))
                await db.commit()
            await log_action(callback.from_user.id, action_log, f"Текст: {app_text[:50]}...")
            await callback.message.edit_text(
                f"{emoji} Вы использовали все 7 попыток редактирования. Заявка автоматически отправлена.\n\n"
                "❌ Если вы передумали, можете удалить заявку:",
                reply_markup=application_sent_keyboard(category)
            )
            await state.clear()
            return
        else:
            await callback.answer("Ошибка: текст не найден", show_alert=True)
            await state.clear()
            return

    await state.update_data(edit_count=edit_count + 1)
    if category == "flood":
        await state.set_state(FloodForm.waiting_edit)
    elif category == "rest":
        await state.set_state(RestForm.waiting_edit)
    elif category == "staff":
        await state.set_state(StaffForm.waiting_edit)
    await state.update_data(category=category)
    current_text = data.get("application_text", "")
    await callback.message.edit_text(
        f"Введите новый текст заявки (редактирование {edit_count+1}/7).\n"
        f"Текущий текст:\n{current_text}\n\n"
        "Напишите новый текст или 'отмена' для отмены редактирования."
    )

@dp.message(FloodForm.waiting_edit)
async def flood_edit(message: Message, state: FSMContext):
    user_id = message.from_user.id
    if message.text and message.text.lower() == "отмена":
        await log_action(user_id, "Отмена редактирования заявки во флуд", "")
        await message.answer("Редактирование отменено. Возврат к подтверждению.")
        await message.answer(
            "Вы уверены, что хотите отправить заявку?",
            reply_markup=application_confirm_keyboard("flood")
        )
        return
    await state.update_data(application_text=message.text)
    await message.answer(
        "Текст обновлён. Подтвердите отправку:",
        reply_markup=application_confirm_keyboard("flood")
    )

@dp.message(RestForm.waiting_edit)
async def rest_edit(message: Message, state: FSMContext):
    user_id = message.from_user.id
    if message.text and message.text.lower() == "отмена":
        await log_action(user_id, "Отмена редактирования заявки в рест", "")
        await message.answer("Редактирование отменено. Возврат к подтверждению.")
        await message.answer(
            "Вы уверены, что хотите отправить заявку?",
            reply_markup=application_confirm_keyboard("rest")
        )
        return
    await state.update_data(application_text=message.text)
    await message.answer(
        "Текст обновлён. Подтвердите отправку:",
        reply_markup=application_confirm_keyboard("rest")
    )

@dp.message(StaffForm.waiting_edit)
async def staff_edit(message: Message, state: FSMContext):
    user_id = message.from_user.id
    if message.text and message.text.lower() == "отмена":
        await log_action(user_id, "Отмена редактирования заявки в стафф", "")
        await message.answer("Редактирование отменено. Возврат к подтверждению.")
        await message.answer(
            "Вы уверены, что хотите отправить заявку?",
            reply_markup=application_confirm_keyboard("staff")
        )
        return
    await state.update_data(application_text=message.text)
    await message.answer(
        "Текст обновлён. Подтвердите отправку:",
        reply_markup=application_confirm_keyboard("staff")
    )

# ---------- Обработчики удаления заявок ----------
@dp.callback_query(F.data.startswith("app_delete_"))
async def app_delete(callback: CallbackQuery):
    data_parts = callback.data.split("_")
    if len(data_parts) < 3:
        await callback.answer("Ошибка: неверный формат данных", show_alert=True)
        return
    
    category = data_parts[2]
    user_id = callback.from_user.id
    
    has_app = await check_user_has_application(user_id, category)
    if not has_app:
        await callback.answer("У вас нет активной заявки в этой категории.", show_alert=True)
        return
    
    category_emoji = {"flood": "🌊", "rest": "🍽", "staff": "🛡"}
    emoji = category_emoji.get(category, "📝")
    
    await callback.message.edit_text(
        f"{emoji} Вы уверены, что хотите удалить заявку в категории '{category}'?\n\n"
        "Это действие нельзя отменить.",
        reply_markup=delete_confirm_keyboard(category)
    )

@dp.callback_query(F.data.startswith("confirm_delete_"))
async def confirm_delete(callback: CallbackQuery):
    data_parts = callback.data.split("_")
    if len(data_parts) < 3:
        await callback.answer("Ошибка: неверный формат данных", show_alert=True)
        return
    
    category = data_parts[2]
    user_id = callback.from_user.id
    
    has_app = await check_user_has_application(user_id, category)
    if not has_app:
        await callback.answer("Заявка уже была удалена или не существует.", show_alert=True)
        await callback.message.edit_text("❌ Заявка не найдена.")
        status = await get_user_status(user_id)
        is_member = await is_user_in_flood_group(user_id)
        await callback.message.answer("Выберите раздел:", reply_markup=main_menu_keyboard(status, is_member))
        return
    
    await delete_application(user_id, category)
    await log_action(user_id, f"Удаление заявки в {category}", "")
    
    category_emoji = {"flood": "🌊", "rest": "🍽", "staff": "🛡"}
    emoji = category_emoji.get(category, "📝")
    
    await callback.message.edit_text(
        f"✅ {emoji} Ваша заявка в категории '{category}' успешно удалена."
    )
    
    status = await get_user_status(user_id)
    is_member = await is_user_in_flood_group(user_id)
    await callback.message.answer("Выберите раздел:", reply_markup=main_menu_keyboard(status, is_member))

@dp.callback_query(F.data == "cancel_delete")
async def cancel_delete(callback: CallbackQuery):
    user_id = callback.from_user.id
    status = await get_user_status(user_id)
    is_member = await is_user_in_flood_group(user_id)
    
    text = callback.message.text or ""
    category = "flood"
    for cat in ["flood", "rest", "staff"]:
        if f"категории '{cat}'" in text:
            category = cat
            break
    
    has_app = await check_user_has_application(user_id, category)
    if has_app:
        category_emoji = {"flood": "🌊", "rest": "🍽", "staff": "🛡"}
        emoji = category_emoji.get(category, "📝")
        await callback.message.edit_text(
            f"{emoji} У вас уже есть активная заявка в категории '{category}'!\n\n"
            "Вы можете удалить текущую заявку или вернуться в меню.",
            reply_markup=has_pending_keyboard(category)
        )
    else:
        await callback.message.edit_text("✅ Удаление отменено. Заявка сохранена.")
        await callback.message.answer("Выберите раздел:", reply_markup=main_menu_keyboard(status, is_member))

# ---------- Поддержка (тикеты) ----------
@dp.callback_query(F.data == "support")
async def cb_support(callback: CallbackQuery, state: FSMContext):
    user_id = callback.from_user.id
    if await is_cooldown_active(user_id, "support"):
        await callback.answer("У вас активен кулдаун на отправку обращения в поддержку.", show_alert=True)
        return
    
    async with aiosqlite.connect("bot.db") as db:
        async with db.execute("SELECT 1 FROM support_tickets WHERE user_id=? AND status='active'", (user_id,)) as cur:
            if await cur.fetchone():
                await callback.answer("У вас уже есть активный тикет.", show_alert=True)
                return
    
    await callback.message.answer(
        "Напишите ваше обращение в поддержку. Администраторы смогут ответить вам.\n"
        "После отправки вы сможете продолжать диалог отвечая на сообщения бота.\n"
        "Для отмены напишите 'отмена'."
    )
    await state.set_state(SupportForm.waiting_message)

@dp.message(SupportForm.waiting_message)
async def process_support_start(message: Message, state: FSMContext):
    user_id = message.from_user.id
    if message.text and message.text.lower() == "отмена":
        await log_action(user_id, "Отмена создания тикета", "")
        await message.answer("Отправка обращения отменена.")
        await state.clear()
        return
    
    created_at = datetime.now().isoformat()
    
    async with aiosqlite.connect("bot.db") as db:
        cursor = await db.execute("INSERT INTO support_tickets (user_id, created_at, status) VALUES (?, ?, 'active')",
                                  (user_id, created_at))
        ticket_id = cursor.lastrowid
        await db.execute("INSERT INTO support_messages (ticket_id, sender_id, text, timestamp, is_from_admin) VALUES (?, ?, ?, ?, 0)",
                         (ticket_id, user_id, message.text, datetime.now().isoformat()))
        await db.commit()
    
    admin_list = []
    async with aiosqlite.connect("bot.db") as db:
        async with db.execute("SELECT user_id FROM admins") as cur:
            admin_rows = await cur.fetchall()
        admin_list = [row[0] for row in admin_rows]
        admin_list.extend(OWNERS)
    
    user = message.from_user
    mention = f"@{user.username}" if user.username else f"[{user.full_name}](tg://user?id={user.id})"
    
    for admin_id in admin_list:
        try:
            text = (
                f"📩 **Новый тикет!**\n\n"
                f"👤 От: {mention}\n"
                f"🆔 ID: {user_id}\n"
                f"🎫 Номер тикета: {ticket_id}\n\n"
                f"📝 Сообщение:\n{message.text}\n\n"
                f"Ответьте на это сообщение, чтобы отправить ответ пользователю, или используйте кнопку 'Тикеты' в админ-панели."
            )
            await bot.send_message(admin_id, text, parse_mode="Markdown")
        except:
            pass
    
    await log_action(user_id, "Создание тикета", f"Тикет #{ticket_id}")
    await message.answer(f"✅ Ваше обращение отправлено (тикет #{ticket_id}). Ожидайте ответа.")
    await apply_auto_cooldown(user_id, "support")
    await state.clear()

# ---------- Пользователь: просмотр активного тикета ----------
@dp.callback_query(F.data == "user_ticket")
async def cb_user_ticket(callback: CallbackQuery):
    user_id = callback.from_user.id
    async with aiosqlite.connect("bot.db") as db:
        async with db.execute("SELECT ticket_id FROM support_tickets WHERE user_id=? AND status='active'", (user_id,)) as cur:
            ticket = await cur.fetchone()
            if not ticket:
                await callback.answer("У вас нет активных тикетов.", show_alert=True)
                return
            ticket_id = ticket[0]
        async with db.execute("SELECT sender_id, text, timestamp, is_from_admin FROM support_messages WHERE ticket_id=? ORDER BY timestamp", (ticket_id,)) as cur:
            messages = await cur.fetchall()
    
    if not messages:
        text = f"📩 Тикет #{ticket_id}\nИстория пуста."
    else:
        lines = [f"📩 Тикет #{ticket_id}"]
        for sender_id, msg_text, ts, is_admin in messages:
            sender = "Админ" if is_admin else "Вы"
            lines.append(f"[{ts[11:16]}] {sender}: {msg_text}")
        text = "\n".join(lines)
    
    kb = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="🔒 Закрыть тикет", callback_data=f"user_ticket_close_{ticket_id}")],
        [InlineKeyboardButton(text="🔙 Назад", callback_data="panel_user")]
    ])
    await callback.message.edit_text(text, reply_markup=kb)

@dp.callback_query(F.data.startswith("user_ticket_close_"))
async def cb_user_ticket_close(callback: CallbackQuery):
    ticket_id = int(callback.data.split("_")[3])
    user_id = callback.from_user.id
    await log_action(user_id, f"Закрытие тикета #{ticket_id}", "")
    async with aiosqlite.connect("bot.db") as db:
        await db.execute("UPDATE support_tickets SET status='closed' WHERE ticket_id=? AND user_id=?", (ticket_id, user_id))
        await db.commit()
    await callback.answer("Тикет закрыт.", show_alert=True)
    await callback.message.edit_text("✅ Тикет закрыт.")
    status = await get_user_status(user_id)
    is_member = await is_user_in_flood_group(user_id)
    await callback.message.answer("Панель участника:", reply_markup=user_panel_keyboard(status, is_member))

# ---------- Админ: тикеты ----------
@dp.callback_query(F.data == "admin_tickets")
async def cb_admin_tickets(callback: CallbackQuery):
    user_id = callback.from_user.id
    if not await is_admin(user_id):
        await callback.answer("Нет прав", show_alert=True)
        return
    async with aiosqlite.connect("bot.db") as db:
        async with db.execute("SELECT ticket_id, user_id, created_at FROM support_tickets WHERE status='active' ORDER BY created_at DESC") as cur:
            tickets = await cur.fetchall()
    if not tickets:
        await callback.message.edit_text("📩 Активных тикетов нет.")
        return
    kb = []
    for ticket_id, uid, created_at in tickets:
        try:
            user = await bot.get_chat(uid)
            name = user.full_name if user.full_name else str(uid)
            username = f"(@{user.username})" if user.username else ""
            label = f"Тикет #{ticket_id} - {name} {username}"
        except:
            label = f"Тикет #{ticket_id} - ID:{uid}"
        kb.append([InlineKeyboardButton(text=label, callback_data=f"ticket_view_{ticket_id}")])
    kb.append([InlineKeyboardButton(text="🔙 Назад", callback_data="admin_applications")])
    await callback.message.edit_text("📩 Список активных тикетов:", reply_markup=InlineKeyboardMarkup(inline_keyboard=kb))

@dp.callback_query(F.data.startswith("ticket_view_"))
async def cb_ticket_view(callback: CallbackQuery):
    ticket_id = int(callback.data.split("_")[2])
    async with aiosqlite.connect("bot.db") as db:
        async with db.execute("SELECT user_id, status FROM support_tickets WHERE ticket_id=?", (ticket_id,)) as cur:
            ticket = await cur.fetchone()
            if not ticket:
                await callback.answer("Тикет не найден", show_alert=True)
                return
            uid, status = ticket
        async with db.execute("SELECT sender_id, text, timestamp, is_from_admin FROM support_messages WHERE ticket_id=? ORDER BY timestamp", (ticket_id,)) as cur:
            messages = await cur.fetchall()
    
    if not messages:
        text = f"📩 Тикет #{ticket_id}\nПользователь ID: {uid}\nИстория пуста."
    else:
        lines = [f"📩 Тикет #{ticket_id}\nПользователь ID: {uid}\n"]
        for sender_id, msg_text, ts, is_admin in messages:
            sender = "Админ" if is_admin else "Пользователь"
            lines.append(f"[{ts[11:16]}] {sender}: {msg_text}")
        text = "\n".join(lines)
    
    kb = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="✏️ Ответить", callback_data=f"ticket_reply_{ticket_id}"),
         InlineKeyboardButton(text="🔒 Закрыть тикет", callback_data=f"ticket_close_{ticket_id}")],
        [InlineKeyboardButton(text="🔙 Назад к списку", callback_data="admin_tickets")]
    ])
    await callback.message.edit_text(text, reply_markup=kb)

@dp.callback_query(F.data.startswith("ticket_reply_"))
async def cb_ticket_reply(callback: CallbackQuery, state: FSMContext):
    ticket_id = int(callback.data.split("_")[2])
    await state.update_data(ticket_id=ticket_id)
    await callback.message.answer("Введите текст ответа. Для отмены напишите 'отмена'.")
    await state.set_state(AdminReplyTicket.waiting_text)

@dp.message(AdminReplyTicket.waiting_text)
async def process_ticket_reply(message: Message, state: FSMContext):
    admin_id = message.from_user.id
    if message.text and message.text.lower() == "отмена":
        await message.answer("Ответ отменён.")
        await state.clear()
        return
    data = await state.get_data()
    ticket_id = data.get("ticket_id")
    if not ticket_id:
        await message.answer("Ошибка: тикет не найден.")
        await state.clear()
        return
    async with aiosqlite.connect("bot.db") as db:
        async with db.execute("SELECT user_id FROM support_tickets WHERE ticket_id=? AND status='active'", (ticket_id,)) as cur:
            ticket = await cur.fetchone()
            if not ticket:
                await message.answer("Тикет уже закрыт или не существует.")
                await state.clear()
                return
            user_id = ticket[0]
        await db.execute("INSERT INTO support_messages (ticket_id, sender_id, text, timestamp, is_from_admin) VALUES (?, ?, ?, ?, 1)",
                         (ticket_id, admin_id, message.text, datetime.now().isoformat()))
        await db.commit()
    
    try:
        await bot.send_message(user_id, f"📩 Ответ администратора по тикету #{ticket_id}:\n\n{message.text}")
    except:
        pass
    await log_action(admin_id, "Ответ в тикет", f"Тикет #{ticket_id}")
    await message.answer("✅ Ответ отправлен.")
    await message.answer("Тикет обновлён. Вернуться к списку тикетов можно через админ-панель.")
    await state.clear()

@dp.callback_query(F.data.startswith("ticket_close_"))
async def cb_ticket_close(callback: CallbackQuery):
    user_id = callback.from_user.id
    ticket_id = int(callback.data.split("_")[2])
    await log_action(user_id, f"Закрытие тикета #{ticket_id}", "")
    async with aiosqlite.connect("bot.db") as db:
        await db.execute("UPDATE support_tickets SET status='closed' WHERE ticket_id=?", (ticket_id,))
        await db.commit()
    await callback.answer("Тикет закрыт.", show_alert=True)
    await callback.message.edit_text("✅ Тикет закрыт.")
    await cb_admin_tickets(callback)

# ---------- Обработка ответов админа на заявки (только через reply) ----------
@dp.message(F.reply_to_message)
async def admin_application_reply(message: Message):
    logger.info(f"admin_application_reply ВЫЗВАН от {message.from_user.id}, текст: {message.text}")
    try:
        admin_id = message.from_user.id
        if not await is_admin(admin_id):
            logger.info("Пользователь не админ, выходим")
            return

        original_msg = message.reply_to_message
        if not original_msg or not original_msg.text:
            logger.info("Нет оригинального сообщения или текста")
            return

        if "User ID:" not in original_msg.text:
            logger.info("В оригинальном сообщении нет 'User ID:'")
            return

        if "Заявка во флуд" in original_msg.text:
            table = "flood_applications"
            category = "flood"
            action_name = "заявки во флуд"
            format_hint = "Принять,Роль,Эмодзи (например: Принять,Шедлетский,🔫)"
        elif "Заявка в рест" in original_msg.text:
            table = "rest_applications"
            category = "rest"
            action_name = "заявки в рест"
            format_hint = "Принять,Роль,Время (например: Принять,Рест,7д)"
        elif "Заявка в стафф" in original_msg.text:
            table = "staff_applications"
            category = "staff"
            action_name = "заявки в стафф"
            format_hint = "Принять,РольФлуда,РольСтаффа (например: Принять,Шедлетский,Модератор)"
        else:
            logger.info("Неизвестная категория заявки")
            return

        match = re.search(r"User ID:\s*(\d+)", original_msg.text)
        if not match:
            await message.answer("Не удалось определить ID заявителя.")
            return
        applicant_id = int(match.group(1))
        logger.info(f"Найдена заявка от {applicant_id}")

        if applicant_id == admin_id:
            await message.answer("❌ Вы не можете обрабатывать свою собственную заявку.")
            return

        async with aiosqlite.connect("bot.db") as db:
            async with db.execute(f"SELECT status FROM {table} WHERE user_id=?", (applicant_id,)) as cur:
                row = await cur.fetchone()
                current_status = row[0] if row else "none"
        logger.info(f"Текущий статус заявки: {current_status}")

        if current_status == "approved":
            await message.answer("Заявка уже была принята.")
            return
        if current_status == "rejected":
            await message.answer("Заявка уже была отклонена.")
            return

        text = message.text.strip()
        cmd_lower = text.lower()

        if cmd_lower.startswith("принять"):
            params_str = text[len("принять"):].strip()
            if params_str.startswith(','):
                params_str = params_str[1:].strip()
            params = [p.strip() for p in params_str.split(',') if p.strip()]

            if len(params) == 0:
                await message.answer(f"❌ Неверный формат. Нужно: {format_hint}")
                return

            if category == "flood":
                if len(params) < 2:
                    await message.answer(f"❌ Неверный формат. Нужно: {format_hint}")
                    return
                role_name = params[0]
                emoji = params[1]
                if await check_flood_role_available(role_name):
                    await assign_flood_role(applicant_id, role_name, emoji)
                    new_status = "approved"
                    result_text = f"✅ Ваша заявка во флуд одобрена!\nРоль: {role_name} {emoji}"
                else:
                    await message.answer("❌ Роль недоступна или занята.")
                    return

            elif category == "rest":
                if len(params) < 2:
                    await message.answer(f"❌ Неверный формат. Нужно: {format_hint}")
                    return
                role_name = params[0]
                expiry = params[1]
                await assign_rest_role(applicant_id, role_name, expiry)
                new_status = "approved"
                result_text = f"✅ Ваша заявка в рест одобрена!\nРоль: {role_name} до {expiry}"

            elif category == "staff":
                if len(params) < 2:
                    await message.answer(f"❌ Неверный формат. Нужно: {format_hint}")
                    return
                flood_role = params[0]
                staff_role = params[1]
                if not await check_flood_role_available(flood_role):
                    await message.answer(f"❌ Роль флуда '{flood_role}' недоступна или занята.")
                    return
                emoji = "🌊"
                await assign_flood_role(applicant_id, flood_role, emoji)
                if not await assign_staff_role(applicant_id, staff_role, message.from_user.username or str(message.from_user.id)):
                    await revoke_flood_role(applicant_id)
                    await message.answer("❌ Не удалось назначить роль стаффа (лимит исчерпан).")
                    return
                new_status = "approved"
                result_text = f"✅ Ваша заявка в стафф одобрена!\nРоль флуда: {flood_role}\nРоль стаффа: {staff_role}"

            async with aiosqlite.connect("bot.db") as db:
                await db.execute(f"UPDATE {table} SET status=? WHERE user_id=?", (new_status, applicant_id))
                await db.commit()

            await log_action(admin_id, f"Принял {action_name}", f"Пользователь {applicant_id}")
            try:
                await bot.send_message(applicant_id, result_text)
            except:
                pass

            new_text = original_msg.text
            for old in ["🕒 Ожидает", "🔴 Ожидает"]:
                new_text = new_text.replace(old, "✅ Принята")
            try:
                await bot.edit_message_text(
                    chat_id=message.chat.id,
                    message_id=original_msg.message_id,
                    text=new_text
                )
            except Exception as e:
                logger.warning(f"Не удалось обновить сообщение: {e}")
            await message.answer("✅ Заявка одобрена. Уведомление отправлено.")

        elif cmd_lower.startswith(("отказать", "отказано")):
            command = "отказать"
            params_str = text[len(command):].strip()
            if params_str.startswith(','):
                params_str = params_str[1:].strip()
            comment = params_str if params_str else "Без комментария"

            if current_status == "approved":
                if category == "flood":
                    await revoke_flood_role(applicant_id)
                elif category == "rest":
                    async with aiosqlite.connect("bot.db") as db:
                        async with db.execute("SELECT role_name FROM rest_roles WHERE user_id=?", (applicant_id,)) as cur:
                            row = await cur.fetchone()
                            if row:
                                await revoke_rest_role(applicant_id, row[0])
                elif category == "staff":
                    async with aiosqlite.connect("bot.db") as db:
                        async with db.execute("SELECT role_name FROM staff_roles WHERE user_id=?", (applicant_id,)) as cur:
                            row = await cur.fetchone()
                            if row:
                                await revoke_staff_role(applicant_id, row[0])
                    await revoke_flood_role(applicant_id)

            async with aiosqlite.connect("bot.db") as db:
                await db.execute(f"UPDATE {table} SET status='rejected' WHERE user_id=?", (applicant_id,))
                await db.commit()

            await log_action(admin_id, f"Отклонил {action_name}", f"Пользователь {applicant_id}, причина: {comment[:50]}")
            try:
                await bot.send_message(applicant_id, f"❌ Ваша заявка была отклонена с комментарием:\n{comment}")
            except:
                pass

            new_text = original_msg.text
            for old in ["🕒 Ожидает", "🔴 Ожидает"]:
                new_text = new_text.replace(old, "❌ Отклонена")
            try:
                await bot.edit_message_text(
                    chat_id=message.chat.id,
                    message_id=original_msg.message_id,
                    text=new_text
                )
            except Exception as e:
                logger.warning(f"Не удалось обновить сообщение: {e}")
            await message.answer("❌ Заявка отклонена. Уведомление отправлено.")

        else:
            await message.answer("❌ Неизвестная команда. Используйте 'Принять' или 'Отказать'.")

    except Exception as e:
        logger.error(f"Ошибка в admin_application_reply: {e}", exc_info=True)
        try:
            await message.answer(f"❌ Произошла внутренняя ошибка: {e}")
        except:
            pass

# ---------- Обработка ответов пользователя в активном тикете ----------
@dp.message(StateFilter(None), F.text, F.chat.id != GROUP_FLOOD_ID)
async def support_reply(message: Message):
    logger.info(f"support_reply вызван: {message.from_user.id}, текст: {message.text}")
    user_id = message.from_user.id

    async with aiosqlite.connect("bot.db") as db:
        async with db.execute("SELECT ticket_id FROM support_tickets WHERE user_id=? AND status='active'", (user_id,)) as cur:
            ticket = await cur.fetchone()
            if not ticket:
                logger.info("У пользователя нет активного тикета, пропускаем")
                return
            ticket_id = ticket[0]

    async with aiosqlite.connect("bot.db") as db:
        await db.execute("INSERT INTO support_messages (ticket_id, sender_id, text, timestamp, is_from_admin) VALUES (?, ?, ?, ?, 0)",
                         (ticket_id, user_id, message.text, datetime.now().isoformat()))
        await db.commit()

    admin_list = []
    async with aiosqlite.connect("bot.db") as db:
        async with db.execute("SELECT user_id FROM admins") as cur:
            admin_rows = await cur.fetchall()
        admin_list = [row[0] for row in admin_rows]
        admin_list.extend(OWNERS)

    user = message.from_user
    mention = f"@{user.username}" if user.username else f"[{user.full_name}](tg://user?id={user.id})"

    for admin_id in admin_list:
        try:
            text = (
                f"📩 **Новое сообщение в тикете #{ticket_id}**\n\n"
                f"👤 От: {mention}\n"
                f"🆔 ID: {user_id}\n\n"
                f"📝 Сообщение:\n{message.text}\n\n"
                f"Ответьте на это сообщение, чтобы отправить ответ пользователю."
            )
            await bot.send_message(admin_id, text, parse_mode="Markdown")
        except:
            pass

    await log_action(user_id, "Ответ в тикет", f"Тикет #{ticket_id}")
    await message.answer("✅ Ваше сообщение отправлено администраторам.")

# ---------- Мои кд ----------
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
    text = "\n".join(lines)
    await callback.message.edit_text(f"Ваши кулдауны:\n{text}")

# ---------- Админ: просмотр заявок ----------
async def show_applications(chat_id: int, table: str, title: str, format_hint: str):
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
            text = f"📩 {title}\nUser ID: {user_id}\nСтатус: {status_label}\nАнкета: {app_text}\n\nОтветьте на это сообщение командой (reply).\n\n{format_hint}"
            msg = await bot.send_message(chat_id, text)
            new_ids.append(msg.message_id)
    await set_info_message_ids(info_key, new_ids)

@dp.callback_query(F.data == "admin_applications")
async def cb_admin_applications(callback: CallbackQuery):
    user_id = callback.from_user.id
    if not await is_admin(user_id):
        await callback.answer("Нет прав", show_alert=True)
        return
    await replace_menu(callback, "Выберите категорию:", applications_menu_keyboard())

@dp.callback_query(F.data == "admin_app_flood")
async def cb_admin_app_flood(callback: CallbackQuery):
    user_id = callback.from_user.id
    if not await is_admin(user_id):
        await callback.answer("Нет прав", show_alert=True)
        return
    await show_applications(callback.message.chat.id, "flood_applications", "Заявка во флуд", "Формат: Принять,Роль,Эмодзи\nили Отказать,Причина")

@dp.callback_query(F.data == "admin_app_rest")
async def cb_admin_app_rest(callback: CallbackQuery):
    user_id = callback.from_user.id
    if not await is_admin(user_id):
        await callback.answer("Нет прав", show_alert=True)
        return
    await show_applications(callback.message.chat.id, "rest_applications", "Заявка в рест", "Формат: Принять,Роль,Время\nили Отказать,Причина")

@dp.callback_query(F.data == "admin_app_staff")
async def cb_admin_app_staff(callback: CallbackQuery):
    user_id = callback.from_user.id
    if not await is_admin(user_id):
        await callback.answer("Нет прав", show_alert=True)
        return
    await show_applications(callback.message.chat.id, "staff_applications", "Заявка в стафф", "Формат: Принять,РольФлуда,РольСтаффа\nили Отказать,Причина")

# ---------- Админ: баны ----------
@dp.callback_query(F.data == "admin_bans")
async def cb_admin_bans(callback: CallbackQuery):
    user_id = callback.from_user.id
    if not await is_admin(user_id):
        await callback.answer("Нет прав", show_alert=True)
        return
    await replace_menu(callback, "Управление банами:", bans_menu_keyboard())

@dp.callback_query(F.data == "admin_ban")
async def cb_admin_ban(callback: CallbackQuery, state: FSMContext):
    await callback.message.answer(
        "Введите user_id пользователя для бана.\n"
        "Формат: ID или ID,длительность (например: 123456789,7д)\n"
        "Если указать только ID, бан будет навсегда.\n"
        "Для отмены напишите 'отмена'."
    )
    await state.set_state(AdminBan.waiting_id)

@dp.message(AdminBan.waiting_id)
async def process_ban(message: Message, state: FSMContext):
    user_id = message.from_user.id
    if message.text and message.text.lower() == "отмена":
        await message.answer("Действие отменено.")
        await state.clear()
        return
    
    parts = message.text.split(',')
    try:
        target_id = int(parts[0].strip())
    except ValueError:
        await message.answer("Неверный ID. Введите число.")
        return
    
    if not await is_owner(user_id):
        if await is_admin(target_id):
            await message.answer("Вы не можете забанить администратора или владельца.")
            await state.clear()
            return
    else:
        if await is_owner(target_id):
            await message.answer("Вы не можете забанить владельца.")
            await state.clear()
            return
    
    if target_id == user_id:
        await message.answer("Вы не можете забанить самого себя.")
        await state.clear()
        return
    
    if len(parts) > 1:
        try:
            duration_str = parts[1].strip()
            seconds = parse_duration(duration_str)
        except ValueError as e:
            await message.answer(f"Неверный формат длительности: {e}")
            return
        until_date = (datetime.now() + timedelta(seconds=seconds)).isoformat()
        duration_text = format_duration(seconds)
    else:
        seconds = None
        until_date = None
        duration_text = "навсегда"
    
    async with aiosqlite.connect("bot.db") as db:
        await db.execute(
            "INSERT OR REPLACE INTO banned_users (user_id, until_date, reason) VALUES (?, ?, ?)",
            (target_id, until_date, "Забанен администратором")
        )
        await db.commit()
    
    await log_action(user_id, "Бан пользователя", f"Забанен {target_id} на {duration_text}")
    
    try:
        await bot.send_message(
            target_id,
            f"🚫 Вы были забанены в боте на {duration_text}.\n"
            f"Если вы считаете это ошибкой, обратитесь в поддержку."
        )
    except:
        pass
    
    await message.answer(f"Пользователь {target_id} забанен на {duration_text}.")
    await state.clear()

@dp.callback_query(F.data == "admin_unban")
async def cb_admin_unban(callback: CallbackQuery, state: FSMContext):
    await callback.message.answer("Введите user_id пользователя для разбана.\nДля отмены напишите 'отмена'.")
    await state.set_state(AdminUnban.waiting_id)

@dp.message(AdminUnban.waiting_id)
async def process_unban(message: Message, state: FSMContext):
    user_id = message.from_user.id
    if message.text and message.text.lower() == "отмена":
        await message.answer("Действие отменено.")
        await state.clear()
        return
    try:
        target_id = int(message.text)
    except ValueError:
        await message.answer("Неверный ID. Введите число.")
        return
    if not await is_owner(user_id):
        if await is_admin(target_id):
            await message.answer("Вы не можете разбанить администратора или владельца.")
            await state.clear()
            return
    else:
        if await is_owner(target_id):
            await message.answer("Вы не можете разбанить владельца.")
            await state.clear()
            return
    async with aiosqlite.connect("bot.db") as db:
        await db.execute("DELETE FROM banned_users WHERE user_id=?", (target_id,))
        await db.commit()
    await log_action(user_id, "Разбан пользователя", f"Разбанен {target_id}")
    await message.answer(f"Пользователь {target_id} разбанен.")
    await state.clear()

@dp.callback_query(F.data == "admin_active_bans")
async def cb_admin_active_bans(callback: CallbackQuery):
    user_id = callback.from_user.id
    if not await is_admin(user_id):
        await callback.answer("Нет прав", show_alert=True)
        return
    
    await cleanup_expired_bans()
    
    async with aiosqlite.connect("bot.db") as db:
        async with db.execute("SELECT user_id, until_date, reason FROM banned_users ORDER BY user_id") as cur:
            banned = await cur.fetchall()
    
    if not banned:
        await callback.message.edit_text("📋 Активных банов нет.")
        return
    
    lines = ["📋 **Активные баны:**\n"]
    for uid, until_date, reason in banned:
        try:
            user = await bot.get_chat(uid)
            name = user.full_name if user.full_name else str(uid)
            username = f"(@{user.username})" if user.username else ""
            user_display = f"{name} {username}"
        except:
            user_display = f"ID: {uid}"
        
        if until_date:
            until = datetime.fromisoformat(until_date)
            remaining = until - datetime.now()
            days = remaining.days
            hours, rem = divmod(remaining.seconds, 3600)
            minutes, seconds = divmod(rem, 60)
            time_left = f"{days}д {hours}ч {minutes}м {seconds}с"
            duration_str = f"до {until.strftime('%d.%m.%Y %H:%M')} (осталось {time_left})"
        else:
            duration_str = "навсегда"
        
        lines.append(f"• {user_display}\n  ID: {uid}\n  Срок: {duration_str}\n  Причина: {reason}\n")
    
    text = "\n".join(lines)
    if len(text) > 4096:
        text = text[:4000] + "\n... (обрезано)"
    
    await callback.message.edit_text(text, parse_mode="Markdown")

# ---------- Админ: активные запреты на заявки ----------
@dp.callback_query(F.data == "admin_active_app_bans")
async def cb_admin_active_app_bans(callback: CallbackQuery):
    user_id = callback.from_user.id
    if not await is_admin(user_id):
        await callback.answer("Нет прав", show_alert=True)
        return
    
    await cleanup_expired_app_bans()
    
    async with aiosqlite.connect("bot.db") as db:
        async with db.execute("SELECT user_id, category, until_date FROM application_bans ORDER BY user_id") as cur:
            bans = await cur.fetchall()
    
    if not bans:
        await callback.message.edit_text("🚫 Активных запретов на заявки нет.")
        return
    
    lines = ["🚫 **Активные запреты на заявки:**\n"]
    lines.append("`ID, таймер, категория`\n")
    
    for uid, category, until_date in bans:
        try:
            user = await bot.get_chat(uid)
            name = user.full_name if user.full_name else str(uid)
            username = f"(@{user.username})" if user.username else ""
            user_display = f"{name} {username}"
        except:
            user_display = f"ID: {uid}"
        
        time_left = format_remaining_time(until_date)
        
        category_names = {
            "flood": "флуд",
            "rest": "рест",
            "staff": "стафф",
            "support": "поддержка"
        }
        category_name = category_names.get(category, category)
        
        lines.append(f"• {user_display}\n  ID: `{uid}`, {time_left}, {category_name}\n")
    
    text = "\n".join(lines)
    if len(text) > 4096:
        text = text[:4000] + "\n... (обрезано)"
    
    await callback.message.edit_text(text, parse_mode="Markdown")

# ---------- Админ: переключение заявок ----------
@dp.callback_query(F.data == "admin_toggle_apps")
async def cb_admin_toggle_apps(callback: CallbackQuery):
    user_id = callback.from_user.id
    if not await is_owner(user_id):
        await callback.answer("Только для владельцев", show_alert=True)
        return
    await replace_menu(callback, "Открыть/закрыть заявки:", toggle_apps_keyboard())

async def toggle_app_setting(setting_key: str, info_key: str, text_on: str, text_off: str):
    async with aiosqlite.connect("bot.db") as db:
        async with db.execute(f"SELECT value FROM settings WHERE key=?", (setting_key,)) as cur:
            row = await cur.fetchone()
            current = row[0] if row else '1'
        new = '0' if current == '1' else '1'
        await db.execute(f"UPDATE settings SET value=? WHERE key=?", (new, setting_key))
        await db.commit()
    await delete_info_message(info_key)
    text = text_off if new == '0' else text_on
    msg = await bot.send_message(INFO_CHANNEL_ID, text)
    await set_info_message_id(info_key, msg.message_id)
    return new

@dp.callback_query(F.data == "toggle_flood")
async def cb_toggle_flood(callback: CallbackQuery):
    user_id = callback.from_user.id
    if not await is_owner(user_id):
        await callback.answer("Только для владельцев", show_alert=True)
        return
    new = await toggle_app_setting('flood_open', 'status_flood', "Заявки во флуд открыты!", "Заявки во флуд закрыты!")
    await log_action(user_id, "Переключение заявок во флуд", f"Новое состояние: {'открыты' if new == '1' else 'закрыты'}")
    await callback.answer(f"Заявки во флуд {'закрыты' if new == '0' else 'открыты'}")

@dp.callback_query(F.data == "toggle_rest")
async def cb_toggle_rest(callback: CallbackQuery):
    user_id = callback.from_user.id
    if not await is_owner(user_id):
        await callback.answer("Только для владельцев", show_alert=True)
        return
    new = await toggle_app_setting('rest_open', 'status_rest', "Заявки в рест открыты!", "Заявки в рест закрыты!")
    await log_action(user_id, "Переключение заявок в рест", f"Новое состояние: {'открыты' if new == '1' else 'закрыты'}")
    await callback.answer(f"Заявки в рест {'закрыты' if new == '0' else 'открыты'}")

@dp.callback_query(F.data == "toggle_staff")
async def cb_toggle_staff(callback: CallbackQuery):
    user_id = callback.from_user.id
    if not await is_owner(user_id):
        await callback.answer("Только для владельцев", show_alert=True)
        return
    new = await toggle_app_setting('staff_open', 'status_staff', "Заявки в стафф открыты!", "Заявки в стафф закрыты!")
    await log_action(user_id, "Переключение заявок в стафф", f"Новое состояние: {'открыты' if new == '1' else 'закрыты'}")
    await callback.answer(f"Заявки в стафф {'закрыты' if new == '0' else 'открыты'}")

# ---------- Админ: настройки для инфо ----------
@dp.callback_query(F.data == "admin_settings")
async def cb_admin_settings(callback: CallbackQuery):
    user_id = callback.from_user.id
    if not await is_owner(user_id):
        await callback.answer("Только для владельцев", show_alert=True)
        return
    await replace_menu(callback, "Настройки для инфо:", settings_menu_keyboard())

@dp.callback_query(F.data == "admin_settings_flood")
async def cb_admin_settings_flood(callback: CallbackQuery, state: FSMContext):
    user_id = callback.from_user.id
    if not await is_owner(user_id):
        await callback.answer("Только для владельцев", show_alert=True)
        return
    await callback.message.answer("Введите список ролей (каждая с новой строки) в формате: Роль:Эмодзи\nДля отмены напишите 'отмена'.")
    await state.set_state(AdminFloodSettings.waiting_roles)

@dp.message(AdminFloodSettings.waiting_roles)
async def process_flood_settings(message: Message, state: FSMContext):
    user_id = message.from_user.id
    if message.text and message.text.lower() == "отмена":
        await message.answer("Действие отменено.")
        await state.clear()
        return
    text = message.text
    roles = [line.strip() for line in text.split('\n') if line.strip()]
    async with aiosqlite.connect("bot.db") as db:
        await db.execute("DELETE FROM flood_roles")
        for role in roles:
            parts = role.split(':')
            if len(parts) == 2:
                role_name = parts[0].strip()
                emoji = parts[1].strip()
                await db.execute("INSERT INTO flood_roles (role_name, emoji) VALUES (?, ?)", (role_name, emoji))
        await db.commit()
    await log_action(user_id, "Обновление ролей флуда", f"Количество ролей: {len(roles)}")
    await update_flood_info()
    await message.answer("Роли флуда сохранены.")
    await state.clear()

@dp.callback_query(F.data == "admin_settings_staff")
async def cb_admin_settings_staff(callback: CallbackQuery, state: FSMContext):
    user_id = callback.from_user.id
    if not await is_owner(user_id):
        await callback.answer("Только для владельцев", show_alert=True)
        return
    await callback.message.answer("Введите роли стаффа (каждая с новой строки) в формате: Название:лимит\nДля отмены напишите 'отмена'.")
    await state.set_state(AdminStaffSettings.waiting_roles)

@dp.message(AdminStaffSettings.waiting_roles)
async def process_staff_settings(message: Message, state: FSMContext):
    user_id = message.from_user.id
    if message.text and message.text.lower() == "отмена":
        await message.answer("Действие отменено.")
        await state.clear()
        return
    text = message.text
    roles = [line.strip() for line in text.split('\n') if line.strip()]
    async with aiosqlite.connect("bot.db") as db:
        await db.execute("INSERT OR REPLACE INTO settings (key, value) VALUES ('staff_settings', ?)", (text,))
        await db.execute("DELETE FROM staff_roles")
        for role in roles:
            parts = role.split(':')
            if len(parts) == 2:
                role_name = parts[0].strip()
                limit = int(parts[1].strip())
                await db.execute("INSERT INTO staff_roles (role_name, role_limit) VALUES (?, ?)", (role_name, limit))
        await db.commit()
    await log_action(user_id, "Обновление ролей стаффа", f"Количество ролей: {len(roles)}")
    await update_staff_info()
    await message.answer("Роли стаффа сохранены.")
    await state.clear()

# ---------- Админ: удаление ролей ----------
@dp.callback_query(F.data == "admin_delete_roles")
async def cb_admin_delete_roles(callback: CallbackQuery):
    user_id = callback.from_user.id
    if not await is_admin(user_id):
        await callback.answer("Нет прав", show_alert=True)
        return
    await replace_menu(callback, "Выберите, что удалить:", delete_roles_menu_keyboard())

@dp.callback_query(F.data == "delete_flood_role")
async def cb_delete_flood_role(callback: CallbackQuery, state: FSMContext):
    await callback.message.answer("Введите название роли для удаления (например: Шедлетский)\nДля отмены напишите 'отмена'.")
    await state.set_state(AdminDeleteRole.waiting_target)

@dp.message(AdminDeleteRole.waiting_target)
async def process_delete_flood_role(message: Message, state: FSMContext):
    user_id = message.from_user.id
    if message.text and message.text.lower() == "отмена":
        await message.answer("Действие отменено.")
        await state.clear()
        return
    role_name = message.text.strip()
    await log_action(user_id, "Удаление роли флуда", f"Роль: {role_name}")
    async with aiosqlite.connect("bot.db") as db:
        await db.execute("DELETE FROM flood_roles WHERE role_name=?", (role_name,))
        await db.commit()
    await update_flood_info()
    await message.answer(f"Роль '{role_name}' удалена.")
    await state.clear()

@dp.callback_query(F.data == "delete_staff_role")
async def cb_delete_staff_role(callback: CallbackQuery, state: FSMContext):
    await callback.message.answer("Введите ID пользователя и роль через пробел (например: 123456789 Модератор)\nДля отмены напишите 'отмена'.")
    await state.set_state(AdminDeleteStaff.waiting_target)

@dp.message(AdminDeleteStaff.waiting_target)
async def process_delete_staff_role(message: Message, state: FSMContext):
    user_id = message.from_user.id
    if message.text and message.text.lower() == "отмена":
        await message.answer("Действие отменено.")
        await state.clear()
        return
    parts = message.text.split()
    if len(parts) != 2:
        await message.answer("Неверный формат. Нужно: ID роль")
        return
    target_id = int(parts[0])
    role_name = parts[1]
    await log_action(user_id, "Удаление роли стаффа", f"Пользователь {target_id}, роль {role_name}")
    async with aiosqlite.connect("bot.db") as db:
        await db.execute("UPDATE staff_roles SET user_id=NULL, username=NULL WHERE user_id=? AND role_name=?", (target_id, role_name))
        await db.execute("UPDATE users SET status='none' WHERE user_id=?", (target_id,))
        await db.commit()
    await update_staff_info()
    await message.answer("Роль стаффа удалена.")
    await state.clear()

@dp.callback_query(F.data == "delete_rest_role")
async def cb_delete_rest_role(callback: CallbackQuery, state: FSMContext):
    await callback.message.answer("Введите название роли для удаления:\nДля отмены напишите 'отмена'.")
    await state.set_state(AdminDeleteRest.waiting_target)

@dp.message(AdminDeleteRest.waiting_target)
async def process_delete_rest_role(message: Message, state: FSMContext):
    user_id = message.from_user.id
    if message.text and message.text.lower() == "отмена":
        await message.answer("Действие отменено.")
        await state.clear()
        return
    role_name = message.text.strip()
    await log_action(user_id, "Удаление рест-роли", f"Роль: {role_name}")
    async with aiosqlite.connect("bot.db") as db:
        await db.execute("DELETE FROM rest_roles WHERE role_name=?", (role_name,))
        await db.commit()
    await update_rest_info()
    await message.answer(f"Роль '{role_name}' удалена.")
    await state.clear()

# ---------- Админ: управление админами ----------
@dp.callback_query(F.data == "admin_manage_admins")
async def cb_admin_manage_admins(callback: CallbackQuery):
    user_id = callback.from_user.id
    if not await is_owner(user_id):
        await callback.answer("Только для владельцев", show_alert=True)
        return
    await replace_menu(callback, "Управление админами:", manage_admins_keyboard())

@dp.callback_query(F.data == "admin_add_admin")
async def cb_admin_add_admin(callback: CallbackQuery, state: FSMContext):
    user_id = callback.from_user.id
    if not await is_owner(user_id):
        await callback.answer("Только для владельцев", show_alert=True)
        return
    await callback.message.answer("Введите user_id нового админа.\nДля отмены напишите 'отмена'.")
    await state.set_state(AdminAddAdmin.waiting_id)

@dp.message(AdminAddAdmin.waiting_id)
async def process_add_admin(message: Message, state: FSMContext):
    user_id = message.from_user.id
    if message.text and message.text.lower() == "отмена":
        await message.answer("Действие отменено.")
        await state.clear()
        return
    try:
        target_id = int(message.text)
    except ValueError:
        await message.answer("Неверный ID")
        return
    await log_action(user_id, "Назначение админа", f"Пользователь {target_id}")
    async with aiosqlite.connect("bot.db") as db:
        await db.execute("INSERT OR IGNORE INTO admins (user_id) VALUES (?)", (target_id,))
        await db.commit()
    await message.answer(f"Пользователь {target_id} назначен админом.")
    await state.clear()

@dp.callback_query(F.data == "admin_remove_admin")
async def cb_admin_remove_admin(callback: CallbackQuery, state: FSMContext):
    user_id = callback.from_user.id
    if not await is_owner(user_id):
        await callback.answer("Только для владельцев", show_alert=True)
        return
    await callback.message.answer("Введите user_id админа для удаления.\nДля отмены напишите 'отмена'.")
    await state.set_state(AdminRemoveAdmin.waiting_id)

@dp.message(AdminRemoveAdmin.waiting_id)
async def process_remove_admin(message: Message, state: FSMContext):
    user_id = message.from_user.id
    if message.text and message.text.lower() == "отмена":
        await message.answer("Действие отменено.")
        await state.clear()
        return
    try:
        target_id = int(message.text)
    except ValueError:
        await message.answer("Неверный ID")
        return
    await log_action(user_id, "Удаление админа", f"Пользователь {target_id}")
    async with aiosqlite.connect("bot.db") as db:
        await db.execute("DELETE FROM admins WHERE user_id=?", (target_id,))
        await db.commit()
    await message.answer(f"Пользователь {target_id} удалён из админов.")
    await state.clear()

# ---------- Админ: список админов ----------
@dp.callback_query(F.data == "admin_list_admins")
async def cb_admin_list_admins(callback: CallbackQuery):
    user_id = callback.from_user.id
    if not await is_owner(user_id):
        await callback.answer("Только для владельцев", show_alert=True)
        return
    
    async with aiosqlite.connect("bot.db") as db:
        async with db.execute("SELECT user_id FROM admins") as cur:
            admin_rows = await cur.fetchall()
    
    admin_ids = [row[0] for row in admin_rows]
    
    admins_list = []
    owners_list = []
    
    for owner_id in OWNERS:
        try:
            user = await bot.get_chat(owner_id)
            name = user.full_name if user.full_name else str(owner_id)
            username = f"@{user.username}" if user.username else ""
            owners_list.append(f"• {name} (ID: {owner_id}) {username}")
        except:
            owners_list.append(f"• ID: {owner_id}")
    
    for admin_id in admin_ids:
        if admin_id in OWNERS:
            continue
        try:
            user = await bot.get_chat(admin_id)
            name = user.full_name if user.full_name else str(admin_id)
            username = f"@{user.username}" if user.username else ""
            admins_list.append(f"• {name} (ID: {admin_id}) {username}")
        except:
            admins_list.append(f"• ID: {admin_id}")
    
    text = "👑 **Владельцы:**\n"
    if owners_list:
        text += "\n".join(owners_list)
    else:
        text += "Нет владельцев"
    
    text += "\n\n🛡 **Админы:**\n"
    if admins_list:
        text += "\n".join(admins_list)
    else:
        text += "Нет админов"
    
    await callback.message.edit_text(text, parse_mode="Markdown")

# ---------- Админ: написать сообщение ----------
@dp.callback_query(F.data == "admin_send_message")
async def cb_admin_send_message(callback: CallbackQuery):
    user_id = callback.from_user.id
    if not await is_admin(user_id):
        await callback.answer("Нет прав", show_alert=True)
        return
    await replace_menu(callback, "Куда отправить сообщение?", send_message_menu_keyboard())

@dp.callback_query(F.data == "admin_send_info_msg")
async def cb_admin_send_info_msg(callback: CallbackQuery, state: FSMContext):
    user_id = callback.from_user.id
    if not await is_owner(user_id):
        await callback.answer("Только для владельцев", show_alert=True)
        return
    await callback.message.answer("Отправьте сообщение (текст, фото, видео, стикер и т.д.) для info-канала.\nДля отмены напишите 'отмена'.")
    await state.set_state(AdminSendMessage.waiting_text)
    await state.update_data(target="info")

@dp.callback_query(F.data == "admin_send_flood_msg")
async def cb_admin_send_flood_msg(callback: CallbackQuery, state: FSMContext):
    user_id = callback.from_user.id
    if not await is_admin(user_id):
        await callback.answer("Нет прав", show_alert=True)
        return
    await callback.message.answer("Отправьте сообщение (текст, фото, видео, стикер и т.д.) для группы флуда.\nДля отмены напишите 'отмена'.")
    await state.set_state(AdminSendMessage.waiting_text)
    await state.update_data(target="flood")

@dp.message(AdminSendMessage.waiting_text)
async def process_send_message(message: Message, state: FSMContext):
    user_id = message.from_user.id
    if message.text and message.text.lower() == "отмена":
        await message.answer("Действие отменено.")
        await state.clear()
        return

    data = await state.get_data()
    target = data.get("target")
    target_chat_id = INFO_CHANNEL_ID if target == "info" else GROUP_FLOOD_ID
    target_name = "info-канал" if target == "info" else "группа флуда"

    if any([
        message.photo, message.video, message.document, message.animation,
        message.voice, message.video_note, message.sticker, message.audio
    ]):
        try:
            await bot.copy_message(chat_id=target_chat_id, from_chat_id=message.chat.id, message_id=message.message_id)
            await log_action(user_id, f"Отправка медиа в {target_name}", "")
        except Exception as e:
            await message.answer(f"Не удалось переслать медиа: {e}")
            return
    else:
        text = message.text or ""
        await bot.send_message(target_chat_id, text)
        await log_action(user_id, f"Отправка сообщения в {target_name}", f"Текст: {text[:50]}...")

    await message.answer("Сообщение отправлено.")
    await state.clear()

# ---------- Админ: удалить сообщение ----------
@dp.callback_query(F.data == "admin_delete_message")
async def cb_admin_delete_message(callback: CallbackQuery):
    user_id = callback.from_user.id
    if not await is_admin(user_id):
        await callback.answer("Нет прав", show_alert=True)
        return
    await replace_menu(callback, "Где удалить сообщение?", delete_message_menu_keyboard())

@dp.callback_query(F.data == "admin_delete_info_msg")
async def cb_admin_delete_info_msg(callback: CallbackQuery, state: FSMContext):
    user_id = callback.from_user.id
    if not await is_owner(user_id):
        await callback.answer("Только для владельцев", show_alert=True)
        return
    await callback.message.answer("Отправьте ссылку на сообщение в info-канале.\nДля отмены напишите 'отмена'.")
    await state.set_state(AdminDeleteMessage.waiting_link)
    await state.update_data(target="info")

@dp.callback_query(F.data == "admin_delete_flood_msg")
async def cb_admin_delete_flood_msg(callback: CallbackQuery, state: FSMContext):
    user_id = callback.from_user.id
    if not await is_admin(user_id):
        await callback.answer("Нет прав", show_alert=True)
        return
    await callback.message.answer("Отправьте ссылку на сообщение во флуд-группе.\nДля отмены напишите 'отмена'.")
    await state.set_state(AdminDeleteMessage.waiting_link)
    await state.update_data(target="flood")

@dp.message(AdminDeleteMessage.waiting_link)
async def process_delete_message(message: Message, state: FSMContext):
    user_id = message.from_user.id
    if message.text and message.text.lower() == "отмена":
        await message.answer("Действие отменено.")
        await state.clear()
        return
    link = message.text.strip()
    parts = link.rstrip('/').split('/')
    try:
        msg_id = int(parts[-1])
    except ValueError:
        await message.answer("Неверная ссылка. Убедитесь, что ссылка содержит ID сообщения.")
        return
    data = await state.get_data()
    target = data.get("target")
    chat_id = INFO_CHANNEL_ID if target == "info" else GROUP_FLOOD_ID
    target_name = "info-канал" if target == "info" else "группа флуда"
    try:
        await bot.delete_message(chat_id, msg_id)
        await log_action(user_id, f"Удаление сообщения из {target_name}", f"ID сообщения: {msg_id}")
        await message.answer("Сообщение удалено.")
    except Exception as e:
        await message.answer(f"Не удалось удалить сообщение: {e}")
    await state.clear()

# ---------- Админ: запреты на заявки ----------
@dp.callback_query(F.data == "admin_app_bans")
async def cb_admin_app_bans(callback: CallbackQuery):
    user_id = callback.from_user.id
    if not await is_admin(user_id):
        await callback.answer("Нет прав", show_alert=True)
        return
    await replace_menu(callback, "Выберите категорию для запрета:", app_bans_menu_keyboard())

@dp.callback_query(F.data.startswith("ban_app_"))
async def cb_ban_app_category(callback: CallbackQuery, state: FSMContext):
    category = callback.data.split("_")[-1]
    user_id = callback.from_user.id
    if not await is_admin(user_id):
        await callback.answer("Нет прав", show_alert=True)
        return
    
    await callback.message.answer(
        f"Введите user_id пользователя, которому запретить подавать заявки в категорию '{category}'.\n"
        "Формат: ID или ID,длительность (например: 123456789,7д или 123456789,12ч)\n"
        "Если указать только ID, запрет будет навсегда.\n"
        "Для отмены напишите 'отмена'."
    )
    await state.set_state(AdminAppBan.waiting_user_id)
    await state.update_data(category=category)

@dp.message(AdminAppBan.waiting_user_id)
async def process_ban_app(message: Message, state: FSMContext):
    user_id = message.from_user.id
    if message.text and message.text.lower() == "отмена":
        await message.answer("Действие отменено.")
        await state.clear()
        return
    
    data = await state.get_data()
    category = data.get("category")
    
    parts = message.text.split(',')
    try:
        target_id = int(parts[0].strip())
    except ValueError:
        await message.answer("Неверный ID. Введите число.")
        return
    
    if len(parts) > 1:
        try:
            duration_str = parts[1].strip()
            seconds = parse_duration(duration_str)
        except ValueError as e:
            await message.answer(f"Неверный формат длительности: {e}")
            return
        until_date = (datetime.now() + timedelta(seconds=seconds)).isoformat()
        duration_text = format_duration(seconds)
    else:
        seconds = None
        until_date = None
        duration_text = "навсегда"
    
    async with aiosqlite.connect("bot.db") as db:
        await db.execute(
            "INSERT OR REPLACE INTO application_bans (user_id, category, until_date) VALUES (?, ?, ?)",
            (target_id, category, until_date)
        )
        await db.commit()
    
    await log_action(user_id, f"Запрет на заявки в {category}", f"Пользователь {target_id} на {duration_text}")
    await message.answer(f"Пользователю {target_id} запрещено подавать заявки в категорию '{category}' на {duration_text}.")
    await state.clear()

# ---------- Админ: разрешение заявок ----------
@dp.callback_query(F.data == "admin_allow_apps")
async def cb_admin_allow_apps(callback: CallbackQuery):
    user_id = callback.from_user.id
    if not await is_admin(user_id):
        await callback.answer("Нет прав", show_alert=True)
        return
    await replace_menu(callback, "Выберите категорию для снятия запрета:", allow_apps_menu_keyboard())

@dp.callback_query(F.data.startswith("allow_app_"))
async def cb_allow_app_category(callback: CallbackQuery, state: FSMContext):
    category = callback.data.split("_")[-1]
    user_id = callback.from_user.id
    if not await is_admin(user_id):
        await callback.answer("Нет прав", show_alert=True)
        return
    await callback.message.answer(f"Введите user_id пользователя, которому разрешить подавать заявки в категорию '{category}'.\nДля отмены напишите 'отмена'.")
    await state.set_state(AdminAllowApp.waiting_id)
    await state.update_data(category=category)

@dp.message(AdminAllowApp.waiting_id)
async def process_allow_app(message: Message, state: FSMContext):
    user_id = message.from_user.id
    if message.text and message.text.lower() == "отмена":
        await message.answer("Действие отменено.")
        await state.clear()
        return
    data = await state.get_data()
    category = data.get("category")
    try:
        target_id = int(message.text)
    except ValueError:
        await message.answer("Неверный ID. Введите число.")
        return
    await log_action(user_id, f"Снятие запрета на заявки в {category}", f"Пользователь {target_id}")
    async with aiosqlite.connect("bot.db") as db:
        await db.execute("DELETE FROM application_bans WHERE user_id=? AND category=?", (target_id, category))
        await db.commit()
    await message.answer(f"Пользователю {target_id} разрешено подавать заявки в категорию '{category}'.")
    await state.clear()

# ---------- Админ: кулдаун ----------
@dp.callback_query(F.data == "admin_cooldown")
async def cb_admin_cooldown(callback: CallbackQuery):
    user_id = callback.from_user.id
    if not await is_admin(user_id):
        await callback.answer("Нет прав", show_alert=True)
        return
    await replace_menu(callback, "Управление кулдаунами:", cooldown_menu_keyboard())

@dp.callback_query(F.data == "cooldown_give")
async def cb_cooldown_give(callback: CallbackQuery):
    user_id = callback.from_user.id
    if not await is_admin(user_id):
        await callback.answer("Нет прав", show_alert=True)
        return
    await replace_menu(callback, "Выберите категорию для выдачи кд:", cooldown_give_category_keyboard())

@dp.callback_query(F.data == "cooldown_remove")
async def cb_cooldown_remove(callback: CallbackQuery):
    user_id = callback.from_user.id
    if not await is_admin(user_id):
        await callback.answer("Нет прав", show_alert=True)
        return
    await replace_menu(callback, "Выберите категорию для снятия кд:", cooldown_remove_category_keyboard())

@dp.callback_query(F.data.startswith("cooldown_give_"))
async def cb_cooldown_give_category(callback: CallbackQuery, state: FSMContext):
    category = callback.data.split("_")[-1]
    await state.update_data(category=category)
    await callback.message.answer(
        f"Введите ID пользователя и длительность через запятую.\n"
        "Формат: ID,длительность (например: 123456789,7д или 123456789,12ч).\n"
        "Поддерживаемые единицы: д (дни), ч (часы), м (минуты), с (секунды).\n"
        "Для отмены напишите 'отмена'."
    )
    await state.set_state(AdminCooldownGive.waiting_id_duration)

@dp.message(AdminCooldownGive.waiting_id_duration)
async def process_cooldown_give(message: Message, state: FSMContext):
    user_id = message.from_user.id
    if message.text and message.text.lower() == "отмена":
        await message.answer("Действие отменено.")
        await state.clear()
        return
    try:
        parts = message.text.split(',')
        target_id = int(parts[0].strip())
        duration_str = parts[1].strip()
        seconds = parse_duration(duration_str)
    except (ValueError, IndexError) as e:
        await message.answer(f"Неверный формат. Ошибка: {e}")
        return
    data = await state.get_data()
    category = data.get("category")
    await set_cooldown(target_id, category, seconds)
    days = seconds // 86400
    hours = (seconds % 86400) // 3600
    minutes = (seconds % 3600) // 60
    secs = seconds % 60
    parts_time = []
    if days: parts_time.append(f"{days}д")
    if hours: parts_time.append(f"{hours}ч")
    if minutes: parts_time.append(f"{minutes}м")
    if secs: parts_time.append(f"{secs}с")
    duration_readable = " ".join(parts_time) if parts_time else "0с"
    await log_action(user_id, "Выдача кд", f"Пользователь {target_id}, категория {category}, {duration_readable}")
    await message.answer(f"Пользователю {target_id} выдан кулдаун на {duration_readable} в категории '{category}'.")
    await state.clear()

@dp.callback_query(F.data.startswith("cooldown_remove_"))
async def cb_cooldown_remove_category(callback: CallbackQuery, state: FSMContext):
    category = callback.data.split("_")[-1]
    await state.update_data(category=category)
    await callback.message.answer(f"Введите ID пользователя для снятия кд в категории '{category}'.\nДля отмены напишите 'отмена'.")
    await state.set_state(AdminCooldownRemove.waiting_id)

@dp.message(AdminCooldownRemove.waiting_id)
async def process_cooldown_remove(message: Message, state: FSMContext):
    user_id = message.from_user.id
    if message.text and message.text.lower() == "отмена":
        await message.answer("Действие отменено.")
        await state.clear()
        return
    try:
        target_id = int(message.text)
    except ValueError:
        await message.answer("Неверный ID. Введите число.")
        return
    data = await state.get_data()
    category = data.get("category")
    await remove_cooldown(target_id, category)
    await log_action(user_id, "Снятие кд", f"Пользователь {target_id}, категория {category}")
    await message.answer(f"Кулдаун снят для пользователя {target_id} в категории '{category}'.")
    await state.clear()

# ---------- Настройки кд (только владельцы) ----------
@dp.callback_query(F.data == "admin_cooldown_settings")
async def cb_admin_cooldown_settings(callback: CallbackQuery):
    user_id = callback.from_user.id
    if not await is_owner(user_id):
        await callback.answer("Только для владельцев", show_alert=True)
        return
    await replace_menu(callback, "Настройки автоматических кулдаунов:", cooldown_settings_category_keyboard())

@dp.callback_query(F.data.startswith("cooldown_settings_"))
async def cb_cooldown_settings_category(callback: CallbackQuery, state: FSMContext):
    category = callback.data.split("_")[-1]
    user_id = callback.from_user.id
    if not await is_owner(user_id):
        await callback.answer("Только для владельцев", show_alert=True)
        return
    await state.update_data(category=category)
    await callback.message.answer(
        f"Введите длительность кд для категории '{category}'.\n"
        "Формат: число + буква (д, ч, м, с).\n"
        "Пример: 7д (7 дней), 12ч (12 часов), 30м (30 минут), 45с (45 секунд).\n"
        "Для отмены напишите 'отмена'."
    )
    await state.set_state(AdminCooldownSettings.waiting_duration)

@dp.message(AdminCooldownSettings.waiting_duration)
async def process_cooldown_settings(message: Message, state: FSMContext):
    user_id = message.from_user.id
    if message.text and message.text.lower() == "отмена":
        await message.answer("Действие отменено.")
        await state.clear()
        return
    try:
        seconds = parse_duration(message.text.strip())
    except ValueError as e:
        await message.answer(f"Неверный формат: {e}")
        return
    data = await state.get_data()
    category = data.get("category")
    await set_cooldown_duration(category, seconds)
    days = seconds // 86400
    hours = (seconds % 86400) // 3600
    minutes = (seconds % 3600) // 60
    secs = seconds % 60
    parts = []
    if days: parts.append(f"{days}д")
    if hours: parts.append(f"{hours}ч")
    if minutes: parts.append(f"{minutes}м")
    if secs: parts.append(f"{secs}с")
    duration_readable = " ".join(parts) if parts else "0с"
    await log_action(user_id, "Настройка кд", f"Категория {category}, {duration_readable}")
    await message.answer(f"Кулдаун для '{category}' установлен: {duration_readable}.")
    await state.clear()

# ---------- Админ: шаблоны сообщений ----------
@dp.callback_query(F.data == "admin_templates")
async def cb_admin_templates(callback: CallbackQuery):
    user_id = callback.from_user.id
    if not await is_owner(user_id):
        await callback.answer("Только для владельцев", show_alert=True)
        return
    await replace_menu(callback, "Выберите категорию для настройки шаблона:", template_category_keyboard())

@dp.callback_query(F.data.startswith("template_"))
async def cb_template_category(callback: CallbackQuery, state: FSMContext):
    user_id = callback.from_user.id
    category = callback.data.split("_")[1]
    if not await is_owner(user_id):
        await callback.answer("Только для владельцев", show_alert=True)
        return
    await state.update_data(category=category)
    async with aiosqlite.connect("bot.db") as db:
        async with db.execute("SELECT value FROM settings WHERE key=?", (f"{category}_template",)) as cur:
            row = await cur.fetchone()
            current_template = row[0] if row else "Не установлен"
    await callback.message.answer(
        f"📝 Текущий шаблон для '{category}':\n{current_template}\n\n"
        "Введите новый текст шаблона. Используйте **{roles}** для вставки списка ролей.\n"
        "Пример:\n"
        "📋 Список ролей во флуде:\n{roles}\n\n"
        "Для отмены напишите 'отмена'."
    )
    await state.set_state(AdminTemplateSettings.waiting_template)

@dp.message(AdminTemplateSettings.waiting_template)
async def process_template(message: Message, state: FSMContext):
    user_id = message.from_user.id
    if message.text and message.text.lower() == "отмена":
        await message.answer("Действие отменено.")
        await state.clear()
        return
    template = message.text
    data = await state.get_data()
    category = data.get("category")
    if not category:
        await message.answer("Ошибка: категория не определена.")
        await state.clear()
        return
    await log_action(user_id, "Сохранение шаблона", f"Категория {category}")
    async with aiosqlite.connect("bot.db") as db:
        await db.execute("INSERT OR REPLACE INTO settings (key, value) VALUES (?, ?)",
                         (f"{category}_template", template))
        await db.commit()
    await message.answer(f"✅ Шаблон для '{category}' сохранён.")
    if category == "flood":
        await update_flood_info()
    elif category == "staff":
        await update_staff_info()
    elif category == "rest":
        await update_rest_info()
    await state.clear()

# ---------- Админ: привязка сообщений ----------
@dp.callback_query(F.data == "admin_bind_info")
async def cb_admin_bind_info(callback: CallbackQuery):
    user_id = callback.from_user.id
    if not await is_owner(user_id):
        await callback.answer("Только для владельцев", show_alert=True)
        return
    await replace_menu(callback, "Выберите тип информации для привязки:", bind_info_category_keyboard())

@dp.callback_query(F.data.startswith("bind_"))
async def cb_bind_category(callback: CallbackQuery, state: FSMContext):
    user_id = callback.from_user.id
    category = callback.data.split("_", 1)[1]
    if not await is_owner(user_id):
        await callback.answer("Только для владельцев", show_alert=True)
        return
    await state.update_data(category=category)
    await callback.message.answer(
        "Отправьте ссылку на сообщение в info-канале.\n"
        "Например: https://t.me/c/123456789/12345\n"
        "Или просто ID сообщения (число).\n"
        "Для отмены напишите 'отмена'."
    )
    await state.set_state(AdminBindInfo.waiting_link)

@dp.message(AdminBindInfo.waiting_link)
async def process_bind_link(message: Message, state: FSMContext):
    user_id = message.from_user.id
    if message.text and message.text.lower() == "отмена":
        await message.answer("Действие отменено.")
        await state.clear()
        return
    link = message.text.strip()
    try:
        if link.isdigit():
            msg_id = int(link)
        else:
            parts = link.rstrip('/').split('/')
            msg_id = int(parts[-1])
    except ValueError:
        await message.answer("Неверный формат. Попробуйте ещё раз или напишите 'отмена'.")
        return
    data = await state.get_data()
    category = data.get("category")
    if not category:
        await message.answer("Ошибка: категория не определена.")
        await state.clear()
        return
    await log_action(user_id, "Привязка info", f"Категория {category}, ID {msg_id}")
    await set_info_message_id(category, msg_id)
    await message.answer(f"✅ Сообщение с ID {msg_id} привязано к категории '{category}'. Теперь бот будет обновлять его автоматически.")
    await state.clear()

# ---------- Админ: отвязка сообщений ----------
@dp.callback_query(F.data == "admin_unbind_info")
async def cb_admin_unbind_info(callback: CallbackQuery):
    user_id = callback.from_user.id
    if not await is_owner(user_id):
        await callback.answer("Только для владельцев", show_alert=True)
        return
    await replace_menu(callback, "Выберите тип информации для отвязки:", unbind_info_category_keyboard())

@dp.callback_query(F.data.startswith("unbind_"))
async def cb_unbind_category(callback: CallbackQuery, state: FSMContext):
    user_id = callback.from_user.id
    category = callback.data.split("_", 1)[1]
    if not await is_owner(user_id):
        await callback.answer("Только для владельцев", show_alert=True)
        return
    await state.update_data(category=category)
    
    # Проверяем, привязано ли сообщение
    current_msg_id = await get_info_message_id(category)
    if not current_msg_id:
        await callback.answer(f"❌ Для категории '{category}' нет привязанного сообщения.", show_alert=True)
        return
    
    await callback.message.answer(
        f"📌 Категория: **{category}**\n"
        f"Текущий ID сообщения: **{current_msg_id}**\n\n"
        "Отправьте ссылку на сообщение, которое хотите отвязать.\n"
        "Или отправьте ID сообщения (число).\n"
        "Для отмены напишите 'отмена'."
    )
    await state.set_state(AdminUnbindInfo.waiting_link)

@dp.message(AdminUnbindInfo.waiting_link)
async def process_unbind_link(message: Message, state: FSMContext):
    user_id = message.from_user.id
    if message.text and message.text.lower() == "отмена":
        await message.answer("Действие отменено.")
        await state.clear()
        status = await get_user_status(user_id)
        is_member = await is_user_in_flood_group(user_id)
        await message.answer("Выберите раздел:", reply_markup=main_menu_keyboard(status, is_member))
        return
    
    link = message.text.strip()
    try:
        if link.isdigit():
            msg_id = int(link)
        else:
            parts = link.rstrip('/').split('/')
            msg_id = int(parts[-1])
    except ValueError:
        await message.answer("❌ Неверный формат. Попробуйте ещё раз или напишите 'отмена'.")
        return
    
    data = await state.get_data()
    category = data.get("category")
    if not category:
        await message.answer("❌ Ошибка: категория не определена.")
        await state.clear()
        return
    
    # Проверяем, что это сообщение действительно привязано
    current_msg_id = await get_info_message_id(category)
    if str(current_msg_id) != str(msg_id):
        await message.answer(
            f"❌ Сообщение с ID {msg_id} не привязано к категории '{category}'.\n"
            f"Текущее привязанное сообщение: {current_msg_id}"
        )
        return
    
    # Удаляем привязку
    await delete_info_message(category)
    await log_action(user_id, "Отвязка info", f"Категория {category}, ID {msg_id}")
    await message.answer(f"✅ Сообщение с ID {msg_id} отвязано от категории '{category}'.")
    
    # Обновляем информацию если нужно
    if category == "flood_roles":
        await update_flood_info()
    elif category == "rest_roles":
        await update_rest_info()
    elif category == "staff_roles":
        await update_staff_info()
    
    await state.clear()

# ---------- Админ: редактирование инфо ----------
@dp.callback_query(F.data == "admin_edit_info")
async def cb_admin_edit_info(callback: CallbackQuery, state: FSMContext):
    user_id = callback.from_user.id
    if not await is_admin(user_id):
        await callback.answer("Недостаточно прав", show_alert=True)
        return
    
    categories = ["flood_roles", "rest_roles", "staff_roles", "status_flood", "status_rest", "status_staff"]
    current_messages = []
    
    for cat in categories:
        msg_id = await get_info_message_id(cat)
        if msg_id:
            try:
                msg = await bot.get_messages(INFO_CHANNEL_ID, int(msg_id))
                preview = msg.text[:50] + "..." if msg.text and len(msg.text) > 50 else msg.text or "Медиа-сообщение"
                current_messages.append(f"📌 {cat}: ID {msg_id} - {preview}")
            except:
                current_messages.append(f"❌ {cat}: ID {msg_id} - не найдено")
        else:
            current_messages.append(f"⬜ {cat}: не привязано")
    
    text = "✏️ **Редактирование инфо-сообщений**\n\n"
    text += "Текущие привязанные сообщения:\n" + "\n".join(current_messages) + "\n\n"
    text += "Отправьте ссылку на сообщение в info-канале, которое хотите заменить.\n"
    text += "Например: https://t.me/c/123456789/12345\n"
    text += "Для отмены напишите 'отмена'."
    
    await callback.message.edit_text(text, parse_mode="Markdown")
    await state.set_state(AdminEditInfo.waiting_link)

@dp.message(AdminEditInfo.waiting_link)
async def process_edit_info_link(message: Message, state: FSMContext):
    user_id = message.from_user.id
    if message.text and message.text.lower() == "отмена":
        await message.answer("Действие отменено.")
        await state.clear()
        status = await get_user_status(user_id)
        is_member = await is_user_in_flood_group(user_id)
        await message.answer("Выберите раздел:", reply_markup=main_menu_keyboard(status, is_member))
        return
    
    link = message.text.strip()
    try:
        if link.isdigit():
            msg_id = int(link)
        else:
            parts = link.rstrip('/').split('/')
            msg_id = int(parts[-1])
    except ValueError:
        await message.answer("❌ Неверный формат ссылки. Попробуйте ещё раз или напишите 'отмена'.")
        return
    
    try:
        # Пытаемся получить сообщение через разные методы
        msg = None
        try:
            msgs = await bot.get_messages(INFO_CHANNEL_ID, msg_id)
            if msgs:
                msg = msgs[0]
        except Exception as e1:
            logger.warning(f"Не удалось получить сообщение через get_messages: {e1}")
            try:
                forwarded = await bot.forward_message(message.chat.id, INFO_CHANNEL_ID, msg_id)
                if forwarded:
                    msg = forwarded
                    await bot.delete_message(message.chat.id, forwarded.message_id)
            except Exception as e2:
                logger.warning(f"Не удалось получить сообщение через forward: {e2}")
        
        if not msg:
            await message.answer(
                f"❌ Сообщение с ID {msg_id} не найдено в канале.\n"
                f"Проверьте:\n"
                f"1. Правильность ссылки\n"
                f"2. Бот добавлен в канал как администратор\n"
                f"3. У бота есть права на чтение сообщений\n\n"
                f"Попробуйте ещё раз или напишите 'отмена'."
            )
            return
        
        current_text = msg.text if hasattr(msg, 'text') and msg.text else "Медиа-сообщение"
        await state.update_data(old_msg_id=msg_id, old_text=current_text)
        
        await message.answer(
            f"✅ Найдено сообщение:\n\n{current_text[:500]}\n\n"
            "Теперь отправьте **новый текст** для этого сообщения.\n"
            "Поддерживаются все форматы (текст, фото, видео и т.д.).\n"
            "Для отмены напишите 'отмена'."
        )
        await state.set_state(AdminEditInfo.waiting_new_text)
        
    except Exception as e:
        logger.error(f"Ошибка при получении сообщения: {e}", exc_info=True)
        await message.answer(
            f"❌ Ошибка при получении сообщения: {e}\n\n"
            f"Возможные причины:\n"
            f"1. Бот не является администратором канала\n"
            f"2. Неверный ID канала в настройках (INFO_CHANNEL_ID)\n"
            f"3. Сообщение было удалено\n\n"
            f"Проверьте настройки и попробуйте снова."
        )

@dp.message(AdminEditInfo.waiting_new_text)
async def process_edit_info_new_text(message: Message, state: FSMContext):
    user_id = message.from_user.id
    if message.text and message.text.lower() == "отмена":
        await message.answer("Действие отменено.")
        await state.clear()
        status = await get_user_status(user_id)
        is_member = await is_user_in_flood_group(user_id)
        await message.answer("Выберите раздел:", reply_markup=main_menu_keyboard(status, is_member))
        return
    
    data = await state.get_data()
    old_msg_id = data.get("old_msg_id")
    
    if not old_msg_id:
        await message.answer("❌ Ошибка: ID сообщения не найден.")
        await state.clear()
        return
    
    try:
        if any([
            message.photo, message.video, message.document, message.animation,
            message.voice, message.video_note, message.sticker, message.audio
        ]):
            new_msg = await bot.copy_message(
                chat_id=INFO_CHANNEL_ID,
                from_chat_id=message.chat.id,
                message_id=message.message_id
            )
            
            await bot.delete_message(INFO_CHANNEL_ID, old_msg_id)
            
            async with aiosqlite.connect("bot.db") as db:
                async with db.execute("SELECT key FROM info_messages WHERE message_id=?", (str(old_msg_id),)) as cur:
                    keys = await cur.fetchall()
                
                for key_row in keys:
                    key = key_row[0]
                    await db.execute("UPDATE info_messages SET message_id=? WHERE key=?", (str(new_msg.message_id), key))
                await db.commit()
            
            await log_action(user_id, "Редактирование инфо (медиа)", f"Старый ID {old_msg_id} -> Новый ID {new_msg.message_id}")
            await message.answer(f"✅ Сообщение заменено! Новый ID: {new_msg.message_id}")
            
        else:
            new_text = message.text
            
            await bot.edit_message_text(
                chat_id=INFO_CHANNEL_ID,
                message_id=old_msg_id,
                text=new_text
            )
            
            await log_action(user_id, "Редактирование инфо (текст)", f"ID {old_msg_id}")
            await message.answer(f"✅ Сообщение обновлено!\n\nНовый текст:\n{new_text[:200]}")
        
        await state.clear()
        status = await get_user_status(user_id)
        is_member = await is_user_in_flood_group(user_id)
        await message.answer("Выберите раздел:", reply_markup=main_menu_keyboard(status, is_member))
        
    except Exception as e:
        await message.answer(f"❌ Ошибка при редактировании: {e}")
        await state.clear()

# ---------- Админ: меню "выебать 1x4" ----------
@dp.callback_query(F.data == "admin_fuck_menu")
async def cb_admin_fuck_menu(callback: CallbackQuery):
    user_id = callback.from_user.id
    if not await is_admin(user_id):
        await callback.answer("Недостаточно прав", show_alert=True)
        return
    await replace_menu(callback, "Настройка функции 'Ебать 1x4':", fuck_menu_keyboard())

@dp.callback_query(F.data == "fuck_toggle")
async def cb_fuck_toggle(callback: CallbackQuery):
    user_id = callback.from_user.id
    if not await is_admin(user_id):
        await callback.answer("Недостаточно прав", show_alert=True)
        return
    async with aiosqlite.connect("bot.db") as db:
        async with db.execute("SELECT value FROM settings WHERE key='fuck_1x4_enabled'") as cur:
            row = await cur.fetchone()
            current = row[0] if row else '1'
        new = '0' if current == '1' else '1'
        await db.execute("INSERT OR REPLACE INTO settings (key, value) VALUES ('fuck_1x4_enabled', ?)", (new,))
        await db.commit()
    await log_action(user_id, "Toggle 1x4", f"Новое состояние: {'включена' if new == '1' else 'выключена'}")
    await callback.answer(f"Функция {'включена' if new == '1' else 'выключена'}", show_alert=True)
    await replace_menu(callback, "Настройка функции 'Ебать 1x4':", fuck_menu_keyboard())

@dp.callback_query(F.data == "fuck_settings")
async def cb_fuck_settings(callback: CallbackQuery):
    user_id = callback.from_user.id
    if not await is_admin(user_id):
        await callback.answer("Недостаточно прав", show_alert=True)
        return
    await replace_menu(callback, "Настройки триггера и ответа:", fuck_settings_keyboard())

@dp.callback_query(F.data == "fuck_menu")
async def cb_fuck_menu(callback: CallbackQuery):
    user_id = callback.from_user.id
    if not await is_admin(user_id):
        await callback.answer("Недостаточно прав", show_alert=True)
        return
    await replace_menu(callback, "Настройка функции 'Ебать 1x4':", fuck_menu_keyboard())

@dp.callback_query(F.data == "fuck_set_trigger")
async def cb_fuck_set_trigger(callback: CallbackQuery, state: FSMContext):
    user_id = callback.from_user.id
    if not await is_admin(user_id):
        await callback.answer("Недостаточно прав", show_alert=True)
        return
    await callback.message.answer(
        "Введите триггерные фразы через '/'. Например: Выебать/ударить/трахнуть\n"
        "Бот будет реагировать на любую из них в сообщениях чата флуда.\n"
        "Для отмены напишите 'отмена'."
    )
    await state.set_state(AdminFuckTrigger.waiting_trigger)

@dp.message(AdminFuckTrigger.waiting_trigger)
async def process_fuck_trigger(message: Message, state: FSMContext):
    user_id = message.from_user.id
    if message.text and message.text.lower() == "отмена":
        await message.answer("Действие отменено.")
        await state.clear()
        return
    trigger = message.text.strip()
    await log_action(user_id, "Установка триггера 1x4", trigger)
    async with aiosqlite.connect("bot.db") as db:
        await db.execute("INSERT OR REPLACE INTO settings (key, value) VALUES ('fuck_trigger', ?)", (trigger,))
        await db.commit()
    await message.answer(f"✅ Триггер установлен: {trigger}")
    await state.clear()

@dp.callback_query(F.data == "fuck_set_reply")
async def cb_fuck_set_reply(callback: CallbackQuery, state: FSMContext):
    user_id = callback.from_user.id
    if not await is_admin(user_id):
        await callback.answer("Недостаточно прав", show_alert=True)
        return
    await callback.message.answer(
        "Введите ответы через '/' в том же порядке, что и триггеры.\n"
        "Используйте {mention} для подстановки упоминания автора.\n"
        "Пример: {mention} сладко выебал 1x4/{mention} ударил 1x4\n"
        "Для отмены напишите 'отмена'."
    )
    await state.set_state(AdminFuckReply.waiting_reply)

@dp.message(AdminFuckReply.waiting_reply)
async def process_fuck_reply(message: Message, state: FSMContext):
    user_id = message.from_user.id
    if message.text and message.text.lower() == "отмена":
        await message.answer("Действие отменено.")
        await state.clear()
        return
    reply = message.text.strip()
    await log_action(user_id, "Установка ответа 1x4", reply)
    async with aiosqlite.connect("bot.db") as db:
        await db.execute("INSERT OR REPLACE INTO settings (key, value) VALUES ('fuck_reply', ?)", (reply,))
        await db.commit()
    await message.answer(f"✅ Ответ сохранён: {reply}")
    await state.clear()

# ---------- Обработчик сообщений в группе флуда: "выебать 1x4" ----------
@dp.message(StateFilter(None), F.chat.id == GROUP_FLOOD_ID, F.text)
async def handle_fuck_1x4(message: Message):
    logger.info(f"handle_fuck_1x4 вызван: {message.from_user.id}, текст: {message.text}")
    try:
        if not message.text:
            return
        async with aiosqlite.connect("bot.db") as db:
            async with db.execute("SELECT value FROM settings WHERE key='fuck_1x4_enabled'") as cur:
                row = await cur.fetchone()
                enabled = row[0] if row else '1'
            if enabled == '0':
                logger.info("Функция отключена")
                return

        async with aiosqlite.connect("bot.db") as db:
            async with db.execute("SELECT value FROM settings WHERE key='fuck_trigger'") as cur:
                trigger_row = await cur.fetchone()
                trigger_str = trigger_row[0] if trigger_row else None
            async with db.execute("SELECT value FROM settings WHERE key='fuck_reply'") as cur:
                reply_row = await cur.fetchone()
                reply_str = reply_row[0] if reply_row else None

        if not trigger_str:
            trigger_str = "выебать 1x4"
        if not reply_str:
            reply_str = "1x4 был сладко выебан в очко ({mention})"

        triggers = [t.strip().lower() for t in trigger_str.split('/') if t.strip()]
        replies = [r.strip() for r in reply_str.split('/') if r.strip()]

        text_lower = message.text.lower()
        matched_index = -1
        for idx, trig in enumerate(triggers):
            if trig in text_lower:
                matched_index = idx
                break

        if matched_index == -1:
            logger.info("Триггер не найден")
            return

        if matched_index < len(replies):
            reply_template = replies[matched_index]
        else:
            reply_template = replies[-1] if replies else ""

        user = message.from_user
        mention = f"@{user.username}" if user.username else f"[{user.full_name}](tg://user?id={user.id})"

        if "{mention}" in reply_template:
            final_reply = reply_template.replace("{mention}", mention)
        else:
            final_reply = f"{mention} {reply_template}" if reply_template else mention

        await message.reply(final_reply, parse_mode="Markdown")
        logger.info(f"Ответ отправлен: {final_reply}")

    except Exception as e:
        logger.error(f"Ошибка в handle_fuck_1x4: {e}", exc_info=True)

# ---------- Уничтожение ----------
@dp.callback_query(F.data == "admin_destroy_confirm")
async def cb_admin_destroy_confirm(callback: CallbackQuery):
    user_id = callback.from_user.id
    if user_id != SPECIAL_OWNER:
        await callback.answer("Нет прав", show_alert=True)
        return
    await replace_menu(callback, "⚠️ ВНИМАНИЕ!\n\nВы собираетесь уничтожить группу флуда: кикнуть всех участников (кроме владельцев).\nЭто действие необратимо. Продолжить?", destroy_confirm_keyboard())

@dp.callback_query(F.data == "destroy_yes")
async def cb_destroy_yes(callback: CallbackQuery):
    user_id = callback.from_user.id
    if user_id != SPECIAL_OWNER:
        await callback.answer("Нет прав", show_alert=True)
        return
    await log_action(user_id, "Уничтожение группы", "Начало")
    await callback.answer("Начинаю уничтожение...", show_alert=False)
    try:
        members = await bot.get_chat_members(GROUP_FLOOD_ID)
        kicked = 0
        for member in members:
            uid = member.user.id
            if uid in OWNERS or uid == SPECIAL_OWNER:
                continue
            try:
                await bot.ban_chat_member(GROUP_FLOOD_ID, uid)
                await bot.unban_chat_member(GROUP_FLOOD_ID, uid)
                kicked += 1
            except Exception as e:
                logger.error(f"Не удалось кикнуть {uid}: {e}")
        await log_action(user_id, "Уничтожение группы", f"Кикнуто {kicked} участников")
        await callback.message.edit_text(f"✅ Группа флуда уничтожена (кикнуто {kicked} участников).")
    except Exception as e:
        await log_action(user_id, "Ошибка при уничтожении", str(e))
        await callback.message.edit_text(f"❌ Ошибка при уничтожении: {e}")

@dp.callback_query(F.data == "destroy_no")
async def cb_destroy_no(callback: CallbackQuery):
    await callback.message.edit_text("❌ Уничтожение отменено.")

# ---------- Новые участники и выход ----------
@dp.message(F.new_chat_members)
async def new_member(message: Message):
    if message.chat.id == GROUP_FLOOD_ID:
        for new_user in message.new_chat_members:
            user_id = new_user.id
            await mark_user_in_group(user_id)
            await log_action(user_id, "Вход в группу флуда", "")

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
        await log_action(user_id, "Выход из группы флуда", "")

# ---------- Очистка истории заявок (только владельцы) ----------
@dp.callback_query(F.data == "admin_clear_history")
async def cb_admin_clear_history(callback: CallbackQuery):
    user_id = callback.from_user.id
    if not await is_owner(user_id):
        await callback.answer("Только для владельцев", show_alert=True)
        return
    await replace_menu(callback, "Выберите категорию для очистки:", clear_history_menu_keyboard())

@dp.callback_query(F.data.startswith("clear_history_"))
async def cb_clear_history_category(callback: CallbackQuery):
    user_id = callback.from_user.id
    if not await is_owner(user_id):
        await callback.answer("Только для владельцев", show_alert=True)
        return
    category = callback.data.split("_")[-1]
    if category == "support":
        await callback.answer("История поддержки не хранится в базе.", show_alert=True)
        return
    table = f"{category}_applications"
    
    async with aiosqlite.connect("bot.db") as db:
        await db.execute(f"DELETE FROM {table} WHERE status IN ('approved', 'rejected')")
        await db.execute("UPDATE users SET status='none' WHERE status IN ('approved', 'rejected')")
        await db.commit()
    
    await log_action(user_id, "Очистка истории заявок", f"Категория {category} (только обработанные)")
    await callback.answer(f"Обработанные заявки ({category}) очищены. Ожидающие сохранены.", show_alert=True)
    await replace_menu(callback, "История очищена (обработанные заявки удалены, ожидающие остались).", await admin_panel_keyboard(user_id))

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
            user_id INTEGER PRIMARY KEY,
            until_date TEXT,
            reason TEXT
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
            until_date TEXT,
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
        await db.execute("""
        CREATE TABLE IF NOT EXISTS support_tickets (
            ticket_id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER,
            created_at TEXT,
            status TEXT DEFAULT 'active'
        )""")
        await db.execute("""
        CREATE TABLE IF NOT EXISTS support_messages (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            ticket_id INTEGER,
            sender_id INTEGER,
            text TEXT,
            timestamp TEXT,
            is_from_admin INTEGER DEFAULT 0
        )""")
        await db.execute("""
        CREATE TABLE IF NOT EXISTS logs (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER,
            action TEXT,
            details TEXT,
            timestamp TEXT
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
        await db.execute("INSERT OR IGNORE INTO settings (key, value) VALUES ('fuck_1x4_enabled', '1')")
        await db.commit()
    
    await cleanup_expired_bans()
    await cleanup_expired_app_bans()
    
    try:
        await bot.send_message(LOG_GROUP_ID, "🚀 Бот запущен! Логи будут приходить сюда.")
        logger.info(f"Тестовое сообщение отправлено в LOG_GROUP_ID {LOG_GROUP_ID}")
    except Exception as e:
        logger.error(f"Не удалось отправить тестовое сообщение в LOG_GROUP_ID {LOG_GROUP_ID}: {e}")
    asyncio.create_task(maintenance_loop())

async def maintenance_loop():
    while True:
        await check_rest_expiry()
        await cleanup_expired_pending()
        await cleanup_expired_bans()
        await cleanup_expired_app_bans()
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
    logger.info(f"Health check server running on port {port}")
    await asyncio.Event().wait()

async def main():
    await on_startup()
    await asyncio.gather(
        dp.start_polling(bot),
        start_web()
    )

if __name__ == "__main__":
    asyncio.run(main())