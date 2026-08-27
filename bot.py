import asyncio
import os
import logging
from datetime import date, datetime, timedelta
import re
import aiohttp
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
API_URL = os.getenv("API_URL", "https://your-site.onrender.com")  # URL вашего сайта с API

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
class AdminTemplateSettings(StatesGroup):
    waiting_category = State()
    waiting_template = State()
class AdminBindInfo(StatesGroup):
    waiting_category = State()
    waiting_link = State()
class AdminAllowApp(StatesGroup):
    waiting_id = State()
class AdminFuckTrigger(StatesGroup):
    waiting_trigger = State()
class AdminFuckReply(StatesGroup):
    waiting_reply = State()

# ---------- Класс для работы с API ----------
class BotAPI:
    def __init__(self):
        self.base_url = API_URL
        self.session = None
    
    async def get_session(self):
        if not self.session:
            self.session = aiohttp.ClientSession()
        return self.session
    
    async def close(self):
        if self.session:
            await self.session.close()
    
    async def _get(self, endpoint):
        session = await self.get_session()
        try:
            async with session.get(f"{self.base_url}{endpoint}") as resp:
                if resp.status == 200:
                    return await resp.json()
                return None
        except Exception as e:
            logging.error(f"API GET error: {e}")
            return None
    
    async def _post(self, endpoint, data=None):
        session = await self.get_session()
        try:
            async with session.post(f"{self.base_url}{endpoint}", json=data) as resp:
                if resp.status == 200:
                    return await resp.json()
                return None
        except Exception as e:
            logging.error(f"API POST error: {e}")
            return None
    
    async def _delete(self, endpoint):
        session = await self.get_session()
        try:
            async with session.delete(f"{self.base_url}{endpoint}") as resp:
                if resp.status == 200:
                    return await resp.json()
                return None
        except Exception as e:
            logging.error(f"API DELETE error: {e}")
            return None
    
    # ----- ПОЛЬЗОВАТЕЛИ -----
    async def get_user(self, user_id):
        return await self._get(f"/api/user/{user_id}")
    
    async def update_user(self, user_id, **kwargs):
        data = {'user_id': user_id}
        data.update(kwargs)
        return await self._post("/api/user", data)
    
    # ----- ЗАЯВКИ -----
    async def get_applications(self, table):
        return await self._get(f"/api/applications/{table}")
    
    async def get_application(self, table, user_id):
        return await self._get(f"/api/applications/{table}/{user_id}")
    
    async def save_application(self, table, user_id, text, status, created_at):
        data = {
            'user_id': user_id,
            'text': text,
            'status': status,
            'created_at': created_at
        }
        return await self._post(f"/api/applications/{table}", data)
    
    async def update_application_status(self, table, user_id, status):
        data = {'user_id': user_id, 'status': status}
        return await self._post(f"/api/applications/{table}", data)
    
    async def delete_application(self, table, user_id):
        return await self._delete(f"/api/applications/{table}/{user_id}")
    
    async def delete_all_applications(self, table):
        return await self._delete(f"/api/applications/{table}")
    
    # ----- РОЛИ ФЛУДА -----
    async def get_flood_roles(self):
        return await self._get("/api/flood_roles")
    
    async def update_flood_roles(self, roles):
        return await self._post("/api/flood_roles", {'roles': roles})
    
    # ----- РОЛИ РЕСТА -----
    async def get_rest_roles(self):
        return await self._get("/api/rest_roles")
    
    async def update_rest_roles(self, roles):
        return await self._post("/api/rest_roles", {'roles': roles})
    
    # ----- РОЛИ СТАФФА -----
    async def get_staff_roles(self):
        return await self._get("/api/staff_roles")
    
    async def update_staff_roles(self, roles):
        return await self._post("/api/staff_roles", {'roles': roles})
    
    # ----- АДМИНЫ -----
    async def get_admins(self):
        return await self._get("/api/admins")
    
    async def add_admin(self, user_id):
        return await self._post("/api/admins", {'user_id': user_id})
    
    async def remove_admin(self, user_id):
        return await self._delete(f"/api/admins/{user_id}")
    
    # ----- БАНЫ -----
    async def get_banned_users(self):
        return await self._get("/api/banned_users")
    
    async def add_banned_user(self, user_id):
        return await self._post("/api/banned_users", {'user_id': user_id})
    
    async def remove_banned_user(self, user_id):
        return await self._delete(f"/api/banned_users/{user_id}")
    
    # ----- НАСТРОЙКИ -----
    async def get_setting(self, key):
        return await self._get(f"/api/settings/{key}")
    
    async def set_setting(self, key, value):
        return await self._post("/api/settings", {'key': key, 'value': value})
    
    # ----- КУЛДАУНЫ -----
    async def get_cooldown(self, user_id, category):
        return await self._get(f"/api/cooldowns/{user_id}/{category}")
    
    async def set_cooldown(self, user_id, category, until_date):
        data = {'user_id': user_id, 'category': category, 'until_date': until_date}
        return await self._post("/api/cooldowns", data)
    
    async def remove_cooldown(self, user_id, category):
        return await self._delete(f"/api/cooldowns/{user_id}/{category}")
    
    async def get_cooldown_settings(self, category):
        return await self._get(f"/api/cooldown_settings/{category}")
    
    async def set_cooldown_settings(self, category, duration_seconds):
        data = {'category': category, 'duration_seconds': duration_seconds}
        return await self._post("/api/cooldown_settings", data)
    
    # ----- INFO MESSAGES -----
    async def get_info_message(self, key):
        return await self._get(f"/api/info_messages/{key}")
    
    async def set_info_message(self, key, message_id):
        data = {'key': key, 'message_id': message_id}
        return await self._post("/api/info_messages", data)
    
    async def delete_info_message(self, key):
        return await self._delete(f"/api/info_messages/{key}")
    
    # ----- ЗАПРЕТЫ НА ЗАЯВКИ -----
    async def add_application_ban(self, user_id, category):
        data = {'user_id': user_id, 'category': category}
        return await self._post("/api/application_bans", data)
    
    async def remove_application_ban(self, user_id, category):
        return await self._delete(f"/api/application_bans/{user_id}/{category}")
    
    async def get_application_ban(self, user_id, category):
        return await self._get(f"/api/application_bans/{user_id}/{category}")
    
    # ----- ПОДДЕРЖКА -----
    async def create_support_dialog(self, user_id, created_at):
        data = {'user_id': user_id, 'status': 'active', 'created_at': created_at}
        return await self._post("/api/support_dialogs", data)
    
    async def get_support_dialog(self, user_id):
        return await self._get(f"/api/support_dialogs/{user_id}")
    
    async def close_support_dialog(self, user_id):
        return await self._delete(f"/api/support_dialogs/{user_id}")

# Создаём глобальный объект API
api = BotAPI()

# ---------- ВСПОМОГАТЕЛЬНЫЕ ФУНКЦИИ (работа через API) ----------
async def is_admin(user_id: int) -> bool:
    admins = await api.get_admins()
    return user_id in admins if admins else False or user_id in OWNERS

async def is_owner(user_id: int) -> bool:
    return user_id in OWNERS

async def is_banned(user_id: int) -> bool:
    banned = await api.get_banned_users()
    return user_id in banned if banned else False

async def get_user_status(user_id: int) -> str:
    user = await api.get_user(user_id)
    return user.get('status', 'none') if user else "none"

async def set_user_status(user_id: int, status: str):
    await api.update_user(user_id, status=status)

async def is_user_in_flood_group(user_id: int) -> bool:
    try:
        member = await bot.get_chat_member(GROUP_FLOOD_ID, user_id)
        return member.status in ["member", "administrator", "creator"]
    except:
        return False

async def has_been_in_group(user_id: int) -> bool:
    user = await api.get_user(user_id)
    return bool(user.get('was_in_group', 0)) if user else False

async def mark_user_in_group(user_id: int):
    await api.update_user(user_id, in_group=1, was_in_group=1)

async def unmark_user_in_group(user_id: int):
    await api.update_user(user_id, in_group=0)

async def is_application_banned(user_id: int, category: str) -> bool:
    result = await api.get_application_ban(user_id, category)
    return result.get('banned', False) if result else False

async def has_pending_application(user_id: int) -> bool:
    status = await get_user_status(user_id)
    return status.startswith("pending")

# ---------- РАБОТА С INFO MESSAGES ----------
async def get_info_message_id(key: str):
    result = await api.get_info_message(key)
    return result.get('message_id') if result else None

async def set_info_message_id(key: str, message_id: int):
    await api.set_info_message(key, str(message_id))

async def delete_info_message(key: str):
    msg_id = await get_info_message_id(key)
    if msg_id:
        try:
            await bot.delete_message(INFO_CHANNEL_ID, int(msg_id))
        except:
            pass
        await api.delete_info_message(key)

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
    result = await api.get_info_message(key)
    if result and result.get('message_id'):
        return [int(x) for x in result['message_id'].split(',')]
    return []

async def set_info_message_ids(key: str, ids: list):
    value = ','.join(map(str, ids)) if ids else ''
    await api.set_info_message(key, value)

# ---------- ФУНКЦИИ РОЛЕЙ ----------
async def check_flood_role_available(role_name: str) -> bool:
    roles = await api.get_flood_roles()
    if not roles:
        return False
    for role in roles:
        if role.get('role_name') == role_name and role.get('user_id') is None:
            return True
    return False

async def assign_flood_role(user_id: int, role_name: str, emoji: str):
    roles = await api.get_flood_roles()
    if not roles:
        return
    for role in roles:
        if role.get('role_name') == role_name and role.get('user_id') is None:
            role['user_id'] = user_id
            role['emoji'] = emoji
            await api.update_flood_roles(roles)
            await set_user_status(user_id, "flood")
            break
    try:
        await bot.send_message(user_id, f"✅ Ваша заявка во флуд одобрена! Ссылка: {FLOOD_GROUP_LINK}")
    except:
        pass
    await update_flood_info()
    await apply_auto_cooldown(user_id, "flood")

async def revoke_flood_role(user_id: int):
    roles = await api.get_flood_roles()
    if not roles:
        return
    for role in roles:
        if role.get('user_id') == user_id:
            role['user_id'] = None
    await api.update_flood_roles(roles)
    await set_user_status(user_id, "none")
    await update_flood_info()

async def update_flood_info():
    roles = await api.get_flood_roles()
    if not roles:
        roles = []
    roles_list = "\n".join([f"{role['role_name']}:{role.get('emoji', '')}" for role in roles if role.get('user_id') is not None]) if roles else "Нет ролей"
    
    template_result = await api.get_setting('flood_template')
    template = template_result.get('value') if template_result else None
    
    if template:
        final_text = template.replace("{roles}", roles_list)
    else:
        lines = ["🌊 Роли флуда:"]
        if roles:
            for role in roles:
                if role.get('user_id') is not None:
                    lines.append(f"{role['role_name']}:{role.get('emoji', '')}")
        else:
            lines.append("Нет ролей")
        final_text = "\n".join(lines)
    await send_or_edit_info_message("flood_roles", final_text)

async def assign_rest_role(user_id: int, role_name: str, expiry_date: str):
    roles = await api.get_rest_roles()
    if not roles:
        roles = []
    roles.append({'role_name': role_name, 'expiry_date': expiry_date, 'user_id': user_id})
    await api.update_rest_roles(roles)
    await set_user_status(user_id, "rest")
    try:
        await bot.send_message(user_id, f"✅ Ваша заявка в рест одобрена! Роль: {role_name} до {expiry_date}")
    except:
        pass
    await update_rest_info()
    await apply_auto_cooldown(user_id, "rest")

async def revoke_rest_role(user_id: int, role_name: str):
    roles = await api.get_rest_roles()
    if not roles:
        return
    roles = [r for r in roles if not (r.get('user_id') == user_id and r.get('role_name') == role_name)]
    await api.update_rest_roles(roles)
    await set_user_status(user_id, "none")
    await update_rest_info()

async def update_rest_info():
    roles = await api.get_rest_roles()
    if not roles:
        await delete_info_message("rest_roles")
        return
    roles_list = "\n".join([f"{role['role_name']}: до {role['expiry_date']}" for role in roles])
    template_result = await api.get_setting('rest_template')
    template = template_result.get('value') if template_result else None
    if template:
        final_text = template.replace("{roles}", roles_list)
    else:
        lines = ["🍽 Ресты:"]
        lines.extend([f"{role['role_name']}: до {role['expiry_date']}" for role in roles])
        final_text = "\n".join(lines)
    await send_or_edit_info_message("rest_roles", final_text)

async def assign_staff_role(user_id: int, role_name: str, username: str):
    roles = await api.get_staff_roles()
    if not roles:
        return False
    # Проверяем лимит
    limit = None
    for r in roles:
        if r.get('role_name') == role_name and r.get('role_limit') is not None:
            limit = r.get('role_limit')
            break
    if limit is None:
        return False
    count = sum(1 for r in roles if r.get('role_name') == role_name and r.get('user_id') is not None)
    if count >= limit:
        return False
    # Находим свободную роль
    for r in roles:
        if r.get('role_name') == role_name and r.get('user_id') is None:
            r['user_id'] = user_id
            r['username'] = username
            await api.update_staff_roles(roles)
            await set_user_status(user_id, "staff")
            break
    await update_staff_info()
    try:
        await bot.send_message(user_id, f"✅ Вы назначены на роль {role_name}!")
    except:
        pass
    await apply_auto_cooldown(user_id, "staff")
    return True

async def revoke_staff_role(user_id: int, role_name: str):
    roles = await api.get_staff_roles()
    if not roles:
        return
    for r in roles:
        if r.get('user_id') == user_id and r.get('role_name') == role_name:
            r['user_id'] = None
            r['username'] = None
            break
    await api.update_staff_roles(roles)
    await set_user_status(user_id, "none")
    await update_staff_info()

async def update_staff_info():
    roles = await api.get_staff_roles()
    if not roles:
        return
    settings_result = await api.get_setting('staff_settings')
    if not settings_result or not settings_result.get('value'):
        return
    settings = settings_result['value']
    role_lines = []
    for role_line in settings.split('\n'):
        if not role_line.strip():
            continue
        parts = role_line.split(':')
        if len(parts) != 2:
            continue
        role_name = parts[0].strip()
        limit = int(parts[1].strip())
        count = sum(1 for r in roles if r.get('role_name') == role_name and r.get('user_id') is not None)
        role_lines.append(f"{role_name}: {count}/{limit}")
        for r in roles:
            if r.get('role_name') == role_name and r.get('user_id') is not None:
                role_lines.append(f"@{r.get('username', '')} - {role_name}")
    roles_list = "\n".join(role_lines) if role_lines else "Нет ролей"
    template_result = await api.get_setting('staff_template')
    template = template_result.get('value') if template_result else None
    if template:
        final_text = template.replace("{roles}", roles_list)
    else:
        lines = ["🛡 Стафф:"]
        lines.extend(role_lines)
        final_text = "\n".join(lines)
    await send_or_edit_info_message("staff_roles", final_text)

async def check_rest_expiry():
    today = date.today().isoformat()
    roles = await api.get_rest_roles()
    if not roles:
        return
    expired = [r for r in roles if r.get('expiry_date') and r.get('expiry_date') <= today]
    for role in expired:
        user_id = role.get('user_id')
        role_name = role.get('role_name')
        if user_id:
            await revoke_rest_role(user_id, role_name)
            try:
                await bot.send_message(user_id, f"⚠️ Ваша роль рест '{role_name}' истекла.")
            except:
                pass
    await update_rest_info()

async def cleanup_expired_pending():
    now = datetime.now()
    threshold = now - timedelta(days=4)
    threshold_iso = threshold.isoformat()
    tables = ["flood_applications", "rest_applications", "staff_applications"]
    for table in tables:
        apps = await api.get_applications(table)
        if not apps:
            continue
        for app in apps:
            if app.get('status') == 'pending' and app.get('created_at') and app['created_at'] < threshold_iso:
                user_id = app.get('user_id')
                await api.delete_application(table, user_id)
                await set_user_status(user_id, "none")

async def is_cooldown_active(user_id: int, category: str) -> bool:
    result = await api.get_cooldown(user_id, category)
    if result and result.get('until_date'):
        until = datetime.fromisoformat(result['until_date'])
        return until > datetime.now()
    return False

async def set_cooldown(user_id: int, category: str, seconds: int):
    until = datetime.now() + timedelta(seconds=seconds)
    await api.set_cooldown(user_id, category, until.isoformat())

async def remove_cooldown(user_id: int, category: str):
    await api.remove_cooldown(user_id, category)

async def get_cooldown_duration(category: str) -> int:
    result = await api.get_cooldown_settings(category)
    return result.get('duration_seconds', 0) if result else 0

async def set_cooldown_duration(category: str, seconds: int):
    await api.set_cooldown_settings(category, seconds)

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
    # Базовый набор кнопок для всех админов
    buttons = [
        [InlineKeyboardButton(text="📋 Заявки", callback_data="admin_applications")],
        [InlineKeyboardButton(text="🚫 Баны", callback_data="admin_bans")],
        [InlineKeyboardButton(text="🗑 Удаление ролей", callback_data="admin_delete_roles")],
        [InlineKeyboardButton(text="ℹ️ Info", url=ADMIN_INFO_LINK)],
        [InlineKeyboardButton(text="🚷 Запреты на заявки", callback_data="admin_app_bans")],
        [InlineKeyboardButton(text="✅ Разрешить заявки", callback_data="admin_allow_apps")],
        [InlineKeyboardButton(text="📨 Написать сообщение", callback_data="admin_send_message")],
        [InlineKeyboardButton(text="🗑 Удалить сообщение", callback_data="admin_delete_message")],
        [InlineKeyboardButton(text="⏳ Кд", callback_data="admin_cooldown")],
        [InlineKeyboardButton(text="🍆 Ебать 1x4", callback_data="admin_fuck_menu")],
    ]
    # Кнопки только для владельцев
    if is_owner(user_id):
        buttons.extend([
            [InlineKeyboardButton(text="⚙️ Настройки кд", callback_data="admin_cooldown_settings")],
            [InlineKeyboardButton(text="🔒 Закрыть/открыть заявки", callback_data="admin_toggle_apps")],
            [InlineKeyboardButton(text="⚙️ Настройки для инфо", callback_data="admin_settings")],
            [InlineKeyboardButton(text="🧹 Очистить историю заявок", callback_data="admin_clear_history")],
            [InlineKeyboardButton(text="👑 Админы", callback_data="admin_manage_admins")],
            [InlineKeyboardButton(text="📝 Шаблоны сообщений", callback_data="admin_templates")],
            [InlineKeyboardButton(text="🔗 Привязать сообщение для info", callback_data="admin_bind_info")],
        ])
    # Специальная кнопка для SPECIAL_OWNER
    if user_id == SPECIAL_OWNER:
        buttons.append([InlineKeyboardButton(text="💣 Уничтожить", callback_data="admin_destroy_confirm")])
    # Кнопка "Назад" всегда в конце
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

# ---------- Утилита для обновления меню ----------
async def replace_menu(callback: CallbackQuery, text: str, reply_markup: InlineKeyboardMarkup):
    chat_id = callback.message.chat.id
    message_id = callback.message.message_id
    await bot.send_message(chat_id, text, reply_markup=reply_markup)
    try:
        await bot.delete_message(chat_id, message_id)
    except Exception as e:
        logging.warning(f"Не удалось удалить старое меню: {e}")

# ---------- ОБРАБОТЧИКИ ----------
@dp.message(CommandStart())
async def cmd_start(message: Message):
    user_id = message.from_user.id
    if await is_banned(user_id):
        await message.answer("Вы забанены в боте.")
        return
    # Создаём пользователя, если его нет
    user = await api.get_user(user_id)
    if not user:
        await api.update_user(user_id, status='none', was_in_group=0, in_group=0)
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

# ---------- ЗАЯВКИ УЧАСТНИКА ----------
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
    setting = await api.get_setting('flood_open')
    if setting and setting.get('value') == '0':
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
    await api.save_application("flood_applications", user_id, text, "pending", created_at)
    await set_user_status(user_id, "pending_flood")
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
    setting = await api.get_setting('rest_open')
    if setting and setting.get('value') == '0':
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
    await api.save_application("rest_applications", user_id, text, "pending", created_at)
    await set_user_status(user_id, "pending_rest")
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
    setting = await api.get_setting('staff_open')
    if setting and setting.get('value') == '0':
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
    await api.save_application("staff_applications", user_id, text, "pending", created_at)
    await set_user_status(user_id, "pending_staff")
    await message.answer("Ваша заявка отправлена. Ожидайте решения.")
    await state.clear()

# ---------- ПОДДЕРЖКА ----------
@dp.callback_query(F.data == "support")
async def cb_support(callback: CallbackQuery, state: FSMContext):
    user_id = callback.from_user.id
    if await is_cooldown_active(user_id, "support"):
        await callback.answer("У вас активен кулдаун на отправку обращения в поддержку.", show_alert=True)
        return
    
    dialog = await api.get_support_dialog(user_id)
    if dialog and dialog.get('status') == 'active':
        await callback.answer("У вас уже есть активный диалог с поддержкой.", show_alert=True)
        return
    
    await callback.message.answer(
        "Напишите ваше обращение в поддержку. Администраторы смогут ответить вам.\n"
        "После отправки вы сможете продолжать диалог отвечая на сообщения бота.\n"
        "Для отмены напишите 'отмена'."
    )
    await state.set_state(SupportForm.waiting_message)

@dp.message(SupportForm.waiting_message)
async def process_support_start(message: Message, state: FSMContext):
    if message.text and message.text.lower() == "отмена":
        await message.answer("Отправка обращения отменена.")
        await state.clear()
        return
    
    user_id = message.from_user.id
    created_at = datetime.now().isoformat()
    await api.create_support_dialog(user_id, created_at)
    
    admins = await api.get_admins()
    admin_list = admins if admins else []
    admin_list.extend(OWNERS)
    
    user = message.from_user
    mention = f"@{user.username}" if user.username else f"[{user.full_name}](tg://user?id={user.id})"
    
    for admin_id in admin_list:
        try:
            text = (
                f"📩 **Новое обращение в поддержку!**\n\n"
                f"👤 От: {mention}\n"
                f"🆔 ID: {user_id}\n\n"
                f"📝 Сообщение:\n{message.text}\n\n"
                f"Ответьте на это сообщение, чтобы отправить ответ пользователю."
            )
            await bot.send_message(admin_id, text, parse_mode="Markdown")
        except:
            pass
    
    await message.answer("✅ Ваше обращение отправлено администраторам. Ожидайте ответа.")
    await apply_auto_cooldown(user_id, "support")
    await state.clear()

# ---------- ОБРАБОТКА ОТВЕТОВ АДМИНА ----------
@dp.message(F.reply_to_message)
async def admin_reply(message: Message):
    if not await is_admin(message.from_user.id):
        return
    
    original_msg = message.reply_to_message
    if not original_msg.text:
        return
    
    # Обработка ответа на поддержку
    if "Новое обращение в поддержку" in original_msg.text or "Ответ от администратора" in original_msg.text:
        try:
            lines = original_msg.text.split('\n')
            user_id = None
            for line in lines:
                if "🆔 ID:" in line:
                    user_id = int(line.split(":")[1].strip())
                    break
            
            if not user_id:
                await message.answer("Не удалось определить ID пользователя.")
                return
            
            dialog = await api.get_support_dialog(user_id)
            if not dialog or dialog.get('status') != 'active':
                await message.answer("Диалог с этим пользователем уже завершён.")
                return
            
            admin = message.from_user
            admin_mention = f"@{admin.username}" if admin.username else f"Администратор (ID: {admin.id})"
            
            await bot.send_message(
                user_id,
                f"📩 **Ответ от администратора** ({admin_mention}):\n\n{message.text}"
            )
            
            await message.reply(f"✅ Ответ отправлен пользователю (ID: {user_id})")
            
        except Exception as e:
            await message.answer(f"Ошибка: {e}")
        return
    
    # Обработка заявок
    if not original_msg.text or "User ID:" not in original_msg.text:
        return
    
    if "Заявка во флуд" in original_msg.text:
        table = "flood_applications"
        category = "flood"
    elif "Заявка в рест" in original_msg.text:
        table = "rest_applications"
        category = "rest"
    elif "Заявка в стафф" in original_msg.text:
        table = "staff_applications"
        category = "staff"
    else:
        return
    
    try:
        user_id_str = original_msg.text.split("User ID:")[1].split("\n")[0].strip()
        applicant_id = int(user_id_str)
    except:
        await message.answer("Не удалось определить ID заявителя.")
        return
    
    app = await api.get_application(table, applicant_id)
    if not app:
        await message.answer("Заявка не найдена.")
        return
    
    current_status = app.get('status', 'none')
    
    if current_status == "approved":
        await message.answer("Заявка уже была принята.")
        return
    if current_status == "rejected":
        await message.answer("Заявка уже была отклонена.")
        return
    
    text_parts = message.text.strip().split('\n')
    command = text_parts[0].strip().lower()
    comment = '\n'.join(text_parts[1:]).strip() if len(text_parts) > 1 else "Без комментария"
    
    if command.startswith("принять"):
        if table == "flood_applications":
            parts = command.split(',')
            if len(parts) < 3:
                await message.answer("Формат: Принять,Роль,Эмодзи")
                return
            role_name = parts[1].strip()
            emoji = parts[2].strip()
            if await check_flood_role_available(role_name):
                await assign_flood_role(applicant_id, role_name, emoji)
                new_status = "approved"
                result_text = f"✅ Ваша заявка во флуд одобрена!\nРоль: {role_name} {emoji}\nКомментарий: {comment}"
            else:
                await message.answer("Роль недоступна или занята.")
                return
        elif table == "rest_applications":
            parts = command.split(',')
            if len(parts) < 2:
                await message.answer("Формат: Принять,Роль,до даты")
                return
            role_name = parts[1].strip()
            expiry = parts[2].strip() if len(parts) > 2 else ""
            await assign_rest_role(applicant_id, role_name, expiry)
            new_status = "approved"
            result_text = f"✅ Ваша заявка в рест одобрена!\nРоль: {role_name} до {expiry}\nКомментарий: {comment}"
        elif table == "staff_applications":
            parts = command.split(',')
            if len(parts) < 3:
                await message.answer("Формат: Принять,@username,роль")
                return
            username = parts[1].strip()
            role_name = parts[2].strip()
            if await assign_staff_role(applicant_id, role_name, username):
                new_status = "approved"
                result_text = f"✅ Ваша заявка в стафф одобрена!\nРоль: {role_name}\nКомментарий: {comment}"
            else:
                await message.answer("Лимит роли исчерпан или роль не найдена.")
                return
        
        await api.update_application_status(table, applicant_id, new_status)
        
        try:
            await bot.send_message(applicant_id, result_text)
        except:
            pass
        
        try:
            await bot.edit_message_text(
                chat_id=message.chat.id,
                message_id=original_msg.message_id,
                text=original_msg.text.replace("Ожидает", "✅ Принята").replace("❌ Отклонена", "✅ Принята")
            )
        except Exception as e:
            logging.warning(f"Не удалось обновить сообщение: {e}")
        
        await message.answer(f"✅ Заявка одобрена. Уведомление отправлено пользователю.")
        
    elif command.startswith("отказать") or command.startswith("отказано"):
        if current_status == "pending":
            await set_user_status(applicant_id, "none")
        
        if current_status == "approved":
            if table == "flood_applications":
                await revoke_flood_role(applicant_id)
            elif table == "rest_applications":
                roles = await api.get_rest_roles()
                if roles:
                    for r in roles:
                        if r.get('user_id') == applicant_id:
                            await revoke_rest_role(applicant_id, r.get('role_name'))
                            break
            elif table == "staff_applications":
                roles = await api.get_staff_roles()
                if roles:
                    for r in roles:
                        if r.get('user_id') == applicant_id:
                            await revoke_staff_role(applicant_id, r.get('role_name'))
                            break
        
        await api.update_application_status(table, applicant_id, "rejected")
        
        admin = message.from_user
        admin_info = f"админом {admin.id}"
        try:
            await bot.send_message(
                applicant_id,
                f"❌ Ваша заявка была отклонена {admin_info} с комментарием:\n{comment}"
            )
        except:
            pass
        
        try:
            await bot.edit_message_text(
                chat_id=message.chat.id,
                message_id=original_msg.message_id,
                text=original_msg.text.replace("Ожидает", "❌ Отклонена").replace("✅ Принята", "❌ Отклонена")
            )
        except Exception as e:
            logging.warning(f"Не удалось обновить сообщение: {e}")
        
        await message.answer(f"❌ Заявка отклонена. Уведомление отправлено пользователю.")
    else:
        await message.answer("Неверная команда.")

# ---------- ОБРАБОТКА ОТВЕТОВ ПОЛЬЗОВАТЕЛЯ В ПОДДЕРЖКЕ ----------
@dp.message(F.text)
async def support_reply(message: Message):
    user_id = message.from_user.id
    
    dialog = await api.get_support_dialog(user_id)
    if not dialog or dialog.get('status') != 'active':
        return
    
    if message.reply_to_message:
        return
    
    if await is_admin(user_id):
        return
    
    admins = await api.get_admins()
    admin_list = admins if admins else []
    admin_list.extend(OWNERS)
    
    user = message.from_user
    mention = f"@{user.username}" if user.username else f"[{user.full_name}](tg://user?id={user.id})"
    
    for admin_id in admin_list:
        try:
            text = (
                f"📩 **Новое сообщение в диалоге поддержки!**\n\n"
                f"👤 От: {mention}\n"
                f"🆔 ID: {user_id}\n\n"
                f"📝 Сообщение:\n{message.text}\n\n"
                f"Ответьте на это сообщение, чтобы отправить ответ пользователю."
            )
            await bot.send_message(admin_id, text, parse_mode="Markdown")
        except:
            pass
    
    await message.answer("✅ Ваше сообщение отправлено администраторам.")

# ---------- МОИ КД ----------
@dp.callback_query(F.data == "my_cooldowns")
async def cb_my_cooldowns(callback: CallbackQuery):
    user_id = callback.from_user.id
    categories = ["flood", "rest", "staff", "support"]
    lines = []
    for cat in categories:
        active = await is_cooldown_active(user_id, cat)
        if active:
            result = await api.get_cooldown(user_id, cat)
            if result and result.get('until_date'):
                until = datetime.fromisoformat(result['until_date'])
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

# ---------- АДМИН: ПРОСМОТР ЗАЯВОК ----------
async def show_applications(chat_id: int, table: str, title: str):
    info_key = f"app_list_{table.split('_')[0]}"
    old_ids = await get_info_message_ids(info_key)
    for mid in old_ids:
        try:
            await bot.delete_message(chat_id, mid)
        except:
            pass
    apps = await api.get_applications(table)
    new_ids = []
    if not apps:
        msg = await bot.send_message(chat_id, f"Нет заявок: {title}")
        new_ids.append(msg.message_id)
    else:
        for app in apps:
            user_id = app.get('user_id')
            app_text = app.get('text', '')
            status = app.get('status', 'pending')
            status_label = {"pending": "🕒 Ожидает", "approved": "✅ Принята", "rejected": "❌ Отклонена"}.get(status, status)
            text = f"📩 {title}\nUser ID: {user_id}\nСтатус: {status_label}\nАнкета: {app_text}\n\nОтветьте на это сообщение командой.\n\nФормат ответа:\nПринять,Роль,Эмодзи\nили\nОтказать,Причина"
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
    await callback.answer("Поддержка: ответьте на сообщение админа, чтобы ответить пользователю.", show_alert=True)

# ---------- АДМИН: БАНЫ ----------
@dp.callback_query(F.data == "admin_bans")
async def cb_admin_bans(callback: CallbackQuery):
    if not await is_admin(callback.from_user.id):
        await callback.answer("Нет прав", show_alert=True)
        return
    await replace_menu(callback, "Управление банами:", bans_menu_keyboard())

@dp.callback_query(F.data == "admin_ban")
async def cb_admin_ban(callback: CallbackQuery, state: FSMContext):
    await callback.message.answer("Введите user_id пользователя для бана.\nДля отмены напишите 'отмена'.")
    await state.set_state(AdminBan.waiting_id)

@dp.message(AdminBan.waiting_id)
async def process_ban(message: Message, state: FSMContext):
    if message.text and message.text.lower() == "отмена":
        await message.answer("Действие отменено.")
        await state.clear()
        return
    try:
        target_id = int(message.text)
    except ValueError:
        await message.answer("Неверный ID. Введите число.")
        return
    actor_id = message.from_user.id
    if not await is_owner(actor_id):
        if await is_admin(target_id):
            await message.answer("Вы не можете забанить администратора или владельца.")
            await state.clear()
            return
    else:
        if await is_owner(target_id):
            await message.answer("Вы не можете забанить владельца.")
            await state.clear()
            return
    await api.add_banned_user(target_id)
    await message.answer(f"Пользователь {target_id} забанен.")
    await state.clear()

@dp.callback_query(F.data == "admin_unban")
async def cb_admin_unban(callback: CallbackQuery, state: FSMContext):
    await callback.message.answer("Введите user_id пользователя для разбана.\nДля отмены напишите 'отмена'.")
    await state.set_state(AdminUnban.waiting_id)

@dp.message(AdminUnban.waiting_id)
async def process_unban(message: Message, state: FSMContext):
    if message.text and message.text.lower() == "отмена":
        await message.answer("Действие отменено.")
        await state.clear()
        return
    try:
        target_id = int(message.text)
    except ValueError:
        await message.answer("Неверный ID. Введите число.")
        return
    actor_id = message.from_user.id
    if not await is_owner(actor_id):
        if await is_admin(target_id):
            await message.answer("Вы не можете разбанить администратора или владельца.")
            await state.clear()
            return
    else:
        if await is_owner(target_id):
            await message.answer("Вы не можете разбанить владельца.")
            await state.clear()
            return
    await api.remove_banned_user(target_id)
    await message.answer(f"Пользователь {target_id} разбанен.")
    await state.clear()

# ---------- АДМИН: ПЕРЕКЛЮЧЕНИЕ ЗАЯВОК ----------
@dp.callback_query(F.data == "admin_toggle_apps")
async def cb_admin_toggle_apps(callback: CallbackQuery):
    if not await is_owner(callback.from_user.id):
        await callback.answer("Только для владельцев", show_alert=True)
        return
    await replace_menu(callback, "Открыть/закрыть заявки:", toggle_apps_keyboard())

async def toggle_app_setting(setting_key: str, info_key: str, text_on: str, text_off: str):
    setting = await api.get_setting(setting_key)
    current = setting.get('value', '1') if setting else '1'
    new = '0' if current == '1' else '1'
    await api.set_setting(setting_key, new)
    await delete_info_message(info_key)
    text = text_off if new == '0' else text_on
    msg = await bot.send_message(INFO_CHANNEL_ID, text)
    await set_info_message_id(info_key, msg.message_id)
    return new

@dp.callback_query(F.data == "toggle_flood")
async def cb_toggle_flood(callback: CallbackQuery):
    if not await is_owner(callback.from_user.id):
        await callback.answer("Только для владельцев", show_alert=True)
        return
    new = await toggle_app_setting('flood_open', 'status_flood', "Заявки во флуд открыты!", "Заявки во флуд закрыты!")
    await callback.answer(f"Заявки во флуд {'закрыты' if new == '0' else 'открыты'}")

@dp.callback_query(F.data == "toggle_rest")
async def cb_toggle_rest(callback: CallbackQuery):
    if not await is_owner(callback.from_user.id):
        await callback.answer("Только для владельцев", show_alert=True)
        return
    new = await toggle_app_setting('rest_open', 'status_rest', "Заявки в рест открыты!", "Заявки в рест закрыты!")
    await callback.answer(f"Заявки в рест {'закрыты' if new == '0' else 'открыты'}")

@dp.callback_query(F.data == "toggle_staff")
async def cb_toggle_staff(callback: CallbackQuery):
    if not await is_owner(callback.from_user.id):
        await callback.answer("Только для владельцев", show_alert=True)
        return
    new = await toggle_app_setting('staff_open', 'status_staff', "Заявки в стафф открыты!", "Заявки в стафф закрыты!")
    await callback.answer(f"Заявки в стафф {'закрыты' if new == '0' else 'открыты'}")

# ---------- АДМИН: НАСТРОЙКИ ДЛЯ ИНФО ----------
@dp.callback_query(F.data == "admin_settings")
async def cb_admin_settings(callback: CallbackQuery):
    if not await is_owner(callback.from_user.id):
        await callback.answer("Только для владельцев", show_alert=True)
        return
    await replace_menu(callback, "Настройки для инфо:", settings_menu_keyboard())

@dp.callback_query(F.data == "admin_settings_flood")
async def cb_admin_settings_flood(callback: CallbackQuery, state: FSMContext):
    if not await is_owner(callback.from_user.id):
        await callback.answer("Только для владельцев", show_alert=True)
        return
    await callback.message.answer("Введите список ролей (каждая с новой строки) в формате: Роль:Эмодзи\nДля отмены напишите 'отмена'.")
    await state.set_state(AdminFloodSettings.waiting_roles)

@dp.message(AdminFloodSettings.waiting_roles)
async def process_flood_settings(message: Message, state: FSMContext):
    if message.text and message.text.lower() == "отмена":
        await message.answer("Действие отменено.")
        await state.clear()
        return
    text = message.text
    roles = []
    for line in text.split('\n'):
        if not line.strip():
            continue
        parts = line.strip().split(':')
        if len(parts) == 2:
            roles.append({'role_name': parts[0].strip(), 'emoji': parts[1].strip(), 'user_id': None})
    await api.update_flood_roles(roles)
    await update_flood_info()
    await message.answer("Роли флуда сохранены.")
    await state.clear()

@dp.callback_query(F.data == "admin_settings_staff")
async def cb_admin_settings_staff(callback: CallbackQuery, state: FSMContext):
    if not await is_owner(callback.from_user.id):
        await callback.answer("Только для владельцев", show_alert=True)
        return
    await callback.message.answer("Введите роли стаффа (каждая с новой строки) в формате: Название:лимит\nДля отмены напишите 'отмена'.")
    await state.set_state(AdminStaffSettings.waiting_roles)

@dp.message(AdminStaffSettings.waiting_roles)
async def process_staff_settings(message: Message, state: FSMContext):
    if message.text and message.text.lower() == "отмена":
        await message.answer("Действие отменено.")
        await state.clear()
        return
    text = message.text
    await api.set_setting('staff_settings', text)
    roles = []
    for line in text.split('\n'):
        if not line.strip():
            continue
        parts = line.strip().split(':')
        if len(parts) == 2:
            roles.append({'role_name': parts[0].strip(), 'role_limit': int(parts[1].strip()), 'user_id': None, 'username': None})
    await api.update_staff_roles(roles)
    await update_staff_info()
    await message.answer("Роли стаффа сохранены.")
    await state.clear()

# ---------- АДМИН: УДАЛЕНИЕ РОЛЕЙ ----------
@dp.callback_query(F.data == "admin_delete_roles")
async def cb_admin_delete_roles(callback: CallbackQuery):
    if not await is_admin(callback.from_user.id):
        await callback.answer("Нет прав", show_alert=True)
        return
    await replace_menu(callback, "Выберите, что удалить:", delete_roles_menu_keyboard())

@dp.callback_query(F.data == "delete_flood_role")
async def cb_delete_flood_role(callback: CallbackQuery, state: FSMContext):
    await callback.message.answer("Введите название роли для удаления (например: Шедлетский)\nДля отмены напишите 'отмена'.")
    await state.set_state(AdminDeleteRole.waiting_target)

@dp.message(AdminDeleteRole.waiting_target)
async def process_delete_flood_role(message: Message, state: FSMContext):
    if message.text and message.text.lower() == "отмена":
        await message.answer("Действие отменено.")
        await state.clear()
        return
    role_name = message.text.strip()
    roles = await api.get_flood_roles()
    if roles:
        roles = [r for r in roles if r.get('role_name') != role_name]
        await api.update_flood_roles(roles)
    await update_flood_info()
    await message.answer(f"Роль '{role_name}' удалена.")
    await state.clear()

@dp.callback_query(F.data == "delete_staff_role")
async def cb_delete_staff_role(callback: CallbackQuery, state: FSMContext):
    await callback.message.answer("Введите ID пользователя и роль через пробел (например: 123456789 Модератор)\nДля отмены напишите 'отмена'.")
    await state.set_state(AdminDeleteStaff.waiting_target)

@dp.message(AdminDeleteStaff.waiting_target)
async def process_delete_staff_role(message: Message, state: FSMContext):
    if message.text and message.text.lower() == "отмена":
        await message.answer("Действие отменено.")
        await state.clear()
        return
    parts = message.text.split()
    if len(parts) != 2:
        await message.answer("Неверный формат. Нужно: ID роль")
        return
    user_id = int(parts[0])
    role_name = parts[1]
    await revoke_staff_role(user_id, role_name)
    await message.answer("Роль стаффа удалена.")
    await state.clear()

@dp.callback_query(F.data == "delete_rest_role")
async def cb_delete_rest_role(callback: CallbackQuery, state: FSMContext):
    await callback.message.answer("Введите название роли для удаления:\nДля отмены напишите 'отмена'.")
    await state.set_state(AdminDeleteRest.waiting_target)

@dp.message(AdminDeleteRest.waiting_target)
async def process_delete_rest_role(message: Message, state: FSMContext):
    if message.text and message.text.lower() == "отмена":
        await message.answer("Действие отменено.")
        await state.clear()
        return
    role_name = message.text.strip()
    roles = await api.get_rest_roles()
    if roles:
        roles = [r for r in roles if r.get('role_name') != role_name]
        await api.update_rest_roles(roles)
    await update_rest_info()
    await message.answer(f"Роль '{role_name}' удалена.")
    await state.clear()

# ---------- АДМИН: УПРАВЛЕНИЕ АДМИНАМИ ----------
@dp.callback_query(F.data == "admin_manage_admins")
async def cb_admin_manage_admins(callback: CallbackQuery):
    if not await is_owner(callback.from_user.id):
        await callback.answer("Только для владельцев", show_alert=True)
        return
    await replace_menu(callback, "Управление админами:", manage_admins_keyboard())

@dp.callback_query(F.data == "admin_add_admin")
async def cb_admin_add_admin(callback: CallbackQuery, state: FSMContext):
    if not await is_owner(callback.from_user.id):
        await callback.answer("Только для владельцев", show_alert=True)
        return
    await callback.message.answer("Введите user_id нового админа.\nДля отмены напишите 'отмена'.")
    await state.set_state(AdminAddAdmin.waiting_id)

@dp.message(AdminAddAdmin.waiting_id)
async def process_add_admin(message: Message, state: FSMContext):
    if message.text and message.text.lower() == "отмена":
        await message.answer("Действие отменено.")
        await state.clear()
        return
    try:
        user_id = int(message.text)
    except ValueError:
        await message.answer("Неверный ID")
        return
    await api.add_admin(user_id)
    await message.answer(f"Пользователь {user_id} назначен админом.")
    await state.clear()

@dp.callback_query(F.data == "admin_remove_admin")
async def cb_admin_remove_admin(callback: CallbackQuery, state: FSMContext):
    if not await is_owner(callback.from_user.id):
        await callback.answer("Только для владельцев", show_alert=True)
        return
    await callback.message.answer("Введите user_id админа для удаления.\nДля отмены напишите 'отмена'.")
    await state.set_state(AdminRemoveAdmin.waiting_id)

@dp.message(AdminRemoveAdmin.waiting_id)
async def process_remove_admin(message: Message, state: FSMContext):
    if message.text and message.text.lower() == "отмена":
        await message.answer("Действие отменено.")
        await state.clear()
        return
    try:
        user_id = int(message.text)
    except ValueError:
        await message.answer("Неверный ID")
        return
    await api.remove_admin(user_id)
    await message.answer(f"Пользователь {user_id} удалён из админов.")
    await state.clear()

# ---------- АДМИН: СПИСОК АДМИНОВ ----------
@dp.callback_query(F.data == "admin_list_admins")
async def cb_admin_list_admins(callback: CallbackQuery):
    if not await is_owner(callback.from_user.id):
        await callback.answer("Только для владельцев", show_alert=True)
        return
    
    admins = await api.get_admins()
    admin_ids = admins if admins else []
    
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

# ---------- АДМИН: НАПИСАТЬ СООБЩЕНИЕ ----------
@dp.callback_query(F.data == "admin_send_message")
async def cb_admin_send_message(callback: CallbackQuery):
    if not await is_admin(callback.from_user.id):
        await callback.answer("Нет прав", show_alert=True)
        return
    await replace_menu(callback, "Куда отправить сообщение?", send_message_menu_keyboard())

@dp.callback_query(F.data == "admin_send_info_msg")
async def cb_admin_send_info_msg(callback: CallbackQuery, state: FSMContext):
    if not await is_owner(callback.from_user.id):
        await callback.answer("Только для владельцев", show_alert=True)
        return
    await callback.message.answer("Отправьте сообщение (текст, фото, видео, стикер и т.д.) для info-канала.\nДля отмены напишите 'отмена'.")
    await state.set_state(AdminSendMessage.waiting_text)
    await state.update_data(target="info")

@dp.callback_query(F.data == "admin_send_flood_msg")
async def cb_admin_send_flood_msg(callback: CallbackQuery, state: FSMContext):
    if not await is_admin(callback.from_user.id):
        await callback.answer("Нет прав", show_alert=True)
        return
    await callback.message.answer("Отправьте сообщение (текст, фото, видео, стикер и т.д.) для группы флуда.\nДля отмены напишите 'отмена'.")
    await state.set_state(AdminSendMessage.waiting_text)
    await state.update_data(target="flood")

@dp.message(AdminSendMessage.waiting_text)
async def process_send_message(message: Message, state: FSMContext):
    if message.text and message.text.lower() == "отмена":
        await message.answer("Действие отменено.")
        await state.clear()
        return

    data = await state.get_data()
    target = data.get("target")
    target_chat_id = INFO_CHANNEL_ID if target == "info" else GROUP_FLOOD_ID

    if any([
        message.photo, message.video, message.document, message.animation,
        message.voice, message.video_note, message.sticker, message.audio
    ]):
        try:
            await bot.copy_message(chat_id=target_chat_id, from_chat_id=message.chat.id, message_id=message.message_id)
        except Exception as e:
            await message.answer(f"Не удалось переслать медиа: {e}")
            return
    else:
        text = message.text or ""
        await bot.send_message(target_chat_id, text)

    await message.answer("Сообщение отправлено.")
    await state.clear()

# ---------- АДМИН: УДАЛИТЬ СООБЩЕНИЕ ----------
@dp.callback_query(F.data == "admin_delete_message")
async def cb_admin_delete_message(callback: CallbackQuery):
    if not await is_admin(callback.from_user.id):
        await callback.answer("Нет прав", show_alert=True)
        return
    await replace_menu(callback, "Где удалить сообщение?", delete_message_menu_keyboard())

@dp.callback_query(F.data == "admin_delete_info_msg")
async def cb_admin_delete_info_msg(callback: CallbackQuery, state: FSMContext):
    if not await is_owner(callback.from_user.id):
        await callback.answer("Только для владельцев", show_alert=True)
        return
    await callback.message.answer("Отправьте ссылку на сообщение в info-канале.\nДля отмены напишите 'отмена'.")
    await state.set_state(AdminDeleteMessage.waiting_link)
    await state.update_data(target="info")

@dp.callback_query(F.data == "admin_delete_flood_msg")
async def cb_admin_delete_flood_msg(callback: CallbackQuery, state: FSMContext):
    if not await is_admin(callback.from_user.id):
        await callback.answer("Нет прав", show_alert=True)
        return
    await callback.message.answer("Отправьте ссылку на сообщение во флуд-группе.\nДля отмены напишите 'отмена'.")
    await state.set_state(AdminDeleteMessage.waiting_link)
    await state.update_data(target="flood")

@dp.message(AdminDeleteMessage.waiting_link)
async def process_delete_message(message: Message, state: FSMContext):
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
    try:
        await bot.delete_message(chat_id, msg_id)
        await message.answer("Сообщение удалено.")
    except Exception as e:
        await message.answer(f"Не удалось удалить сообщение: {e}")
    await state.clear()

# ---------- АДМИН: ЗАПРЕТЫ НА ЗАЯВКИ ----------
@dp.callback_query(F.data == "admin_app_bans")
async def cb_admin_app_bans(callback: CallbackQuery):
    if not await is_admin(callback.from_user.id):
        await callback.answer("Нет прав", show_alert=True)
        return
    await replace_menu(callback, "Выберите категорию для запрета:", app_bans_menu_keyboard())

@dp.callback_query(F.data.startswith("ban_app_"))
async def cb_ban_app_category(callback: CallbackQuery, state: FSMContext):
    category = callback.data.split("_")[-1]
    if not await is_admin(callback.from_user.id):
        await callback.answer("Нет прав", show_alert=True)
        return
    await callback.message.answer(f"Введите user_id пользователя, которому запретить подавать заявки в категорию '{category}'.\nДля отмены напишите 'отмена'.")
    await state.set_state(AdminAppBan.waiting_user_id)
    await state.update_data(category=category)

@dp.message(AdminAppBan.waiting_user_id)
async def process_ban_app(message: Message, state: FSMContext):
    if message.text and message.text.lower() == "отмена":
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
    await api.add_application_ban(user_id, category)
    await message.answer(f"Пользователю {user_id} запрещено подавать заявки в категорию '{category}'.")
    await state.clear()

# ---------- АДМИН: РАЗРЕШЕНИЕ ЗАЯВОК ----------
@dp.callback_query(F.data == "admin_allow_apps")
async def cb_admin_allow_apps(callback: CallbackQuery):
    if not await is_admin(callback.from_user.id):
        await callback.answer("Нет прав", show_alert=True)
        return
    await replace_menu(callback, "Выберите категорию для снятия запрета:", allow_apps_menu_keyboard())

@dp.callback_query(F.data.startswith("allow_app_"))
async def cb_allow_app_category(callback: CallbackQuery, state: FSMContext):
    category = callback.data.split("_")[-1]
    if not await is_admin(callback.from_user.id):
        await callback.answer("Нет прав", show_alert=True)
        return
    await callback.message.answer(f"Введите user_id пользователя, которому разрешить подавать заявки в категорию '{category}'.\nДля отмены напишите 'отмена'.")
    await state.set_state(AdminAllowApp.waiting_id)
    await state.update_data(category=category)

@dp.message(AdminAllowApp.waiting_id)
async def process_allow_app(message: Message, state: FSMContext):
    if message.text and message.text.lower() == "отмена":
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
    await api.remove_application_ban(user_id, category)
    await message.answer(f"Пользователю {user_id} разрешено подавать заявки в категорию '{category}'.")
    await state.clear()

# ---------- АДМИН: КУЛДАУН ----------
@dp.callback_query(F.data == "admin_cooldown")
async def cb_admin_cooldown(callback: CallbackQuery):
    if not await is_admin(callback.from_user.id):
        await callback.answer("Нет прав", show_alert=True)
        return
    await replace_menu(callback, "Управление кулдаунами:", cooldown_menu_keyboard())

@dp.callback_query(F.data == "cooldown_give")
async def cb_cooldown_give(callback: CallbackQuery):
    if not await is_admin(callback.from_user.id):
        await callback.answer("Нет прав", show_alert=True)
        return
    await replace_menu(callback, "Выберите категорию для выдачи кд:", cooldown_give_category_keyboard())

@dp.callback_query(F.data == "cooldown_remove")
async def cb_cooldown_remove(callback: CallbackQuery):
    if not await is_admin(callback.from_user.id):
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
    if message.text and message.text.lower() == "отмена":
        await message.answer("Действие отменено.")
        await state.clear()
        return
    try:
        parts = message.text.split(',')
        user_id = int(parts[0].strip())
        duration_str = parts[1].strip()
        seconds = parse_duration(duration_str)
    except (ValueError, IndexError) as e:
        await message.answer(f"Неверный формат. Ошибка: {e}")
        return
    data = await state.get_data()
    category = data.get("category")
    await set_cooldown(user_id, category, seconds)
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
    await message.answer(f"Пользователю {user_id} выдан кулдаун на {duration_readable} в категории '{category}'.")
    await state.clear()

@dp.callback_query(F.data.startswith("cooldown_remove_"))
async def cb_cooldown_remove_category(callback: CallbackQuery, state: FSMContext):
    category = callback.data.split("_")[-1]
    await state.update_data(category=category)
    await callback.message.answer(f"Введите ID пользователя для снятия кд в категории '{category}'.\nДля отмены напишите 'отмена'.")
    await state.set_state(AdminCooldownRemove.waiting_id)

@dp.message(AdminCooldownRemove.waiting_id)
async def process_cooldown_remove(message: Message, state: FSMContext):
    if message.text and message.text.lower() == "отмена":
        await message.answer("Действие отменено.")
        await state.clear()
        return
    try:
        user_id = int(message.text)
    except ValueError:
        await message.answer("Неверный ID. Введите число.")
        return
    data = await state.get_data()
    category = data.get("category")
    await remove_cooldown(user_id, category)
    await message.answer(f"Кулдаун снят для пользователя {user_id} в категории '{category}'.")
    await state.clear()

# ---------- НАСТРОЙКИ КД (ТОЛЬКО ВЛАДЕЛЬЦЫ) ----------
@dp.callback_query(F.data == "admin_cooldown_settings")
async def cb_admin_cooldown_settings(callback: CallbackQuery):
    if not await is_owner(callback.from_user.id):
        await callback.answer("Только для владельцев", show_alert=True)
        return
    await replace_menu(callback, "Настройки автоматических кулдаунов:", cooldown_settings_category_keyboard())

@dp.callback_query(F.data.startswith("cooldown_settings_"))
async def cb_cooldown_settings_category(callback: CallbackQuery, state: FSMContext):
    category = callback.data.split("_")[-1]
    if not await is_owner(callback.from_user.id):
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
    await message.answer(f"Кулдаун для '{category}' установлен: {duration_readable}.")
    await state.clear()

# ---------- АДМИН: ШАБЛОНЫ ----------
@dp.callback_query(F.data == "admin_templates")
async def cb_admin_templates(callback: CallbackQuery):
    if not await is_owner(callback.from_user.id):
        await callback.answer("Только для владельцев", show_alert=True)
        return
    await replace_menu(callback, "Выберите категорию для настройки шаблона:", template_category_keyboard())

@dp.callback_query(F.data.startswith("template_"))
async def cb_template_category(callback: CallbackQuery, state: FSMContext):
    if not await is_owner(callback.from_user.id):
        await callback.answer("Только для владельцев", show_alert=True)
        return
    category = callback.data.split("_")[1]
    await state.update_data(category=category)
    template_result = await api.get_setting(f"{category}_template")
    current_template = template_result.get('value') if template_result else "Не установлен"
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
    await api.set_setting(f"{category}_template", template)
    await message.answer(f"✅ Шаблон для '{category}' сохранён.")
    if category == "flood":
        await update_flood_info()
    elif category == "staff":
        await update_staff_info()
    elif category == "rest":
        await update_rest_info()
    await state.clear()

# ---------- АДМИН: ПРИВЯЗКА СООБЩЕНИЙ ----------
@dp.callback_query(F.data == "admin_bind_info")
async def cb_admin_bind_info(callback: CallbackQuery):
    if not await is_owner(callback.from_user.id):
        await callback.answer("Только для владельцев", show_alert=True)
        return
    await replace_menu(callback, "Выберите тип информации для привязки:", bind_info_category_keyboard())

@dp.callback_query(F.data.startswith("bind_"))
async def cb_bind_category(callback: CallbackQuery, state: FSMContext):
    if not await is_owner(callback.from_user.id):
        await callback.answer("Только для владельцев", show_alert=True)
        return
    category = callback.data.split("_", 1)[1]
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
    await set_info_message_id(category, msg_id)
    await message.answer(f"✅ Сообщение с ID {msg_id} привязано к категории '{category}'.")
    await state.clear()

# ---------- АДМИН: МЕНЮ "ВЫЕБАТЬ 1X4" ----------
@dp.callback_query(F.data == "admin_fuck_menu")
async def cb_admin_fuck_menu(callback: CallbackQuery):
    if not await is_admin(callback.from_user.id):
        await callback.answer("Недостаточно прав", show_alert=True)
        return
    await replace_menu(callback, "Настройка функции 'Ебать 1x4':", fuck_menu_keyboard())

@dp.callback_query(F.data == "fuck_toggle")
async def cb_fuck_toggle(callback: CallbackQuery):
    if not await is_admin(callback.from_user.id):
        await callback.answer("Недостаточно прав", show_alert=True)
        return
    setting = await api.get_setting('fuck_1x4_enabled')
    current = setting.get('value', '1') if setting else '1'
    new = '0' if current == '1' else '1'
    await api.set_setting('fuck_1x4_enabled', new)
    await callback.answer(f"Функция {'включена' if new == '1' else 'выключена'}", show_alert=True)
    await replace_menu(callback, "Настройка функции 'Ебать 1x4':", fuck_menu_keyboard())

@dp.callback_query(F.data == "fuck_settings")
async def cb_fuck_settings(callback: CallbackQuery):
    if not await is_admin(callback.from_user.id):
        await callback.answer("Недостаточно прав", show_alert=True)
        return
    await replace_menu(callback, "Настройки триггера и ответа:", fuck_settings_keyboard())

@dp.callback_query(F.data == "fuck_menu")
async def cb_fuck_menu(callback: CallbackQuery):
    if not await is_admin(callback.from_user.id):
        await callback.answer("Недостаточно прав", show_alert=True)
        return
    await replace_menu(callback, "Настройка функции 'Ебать 1x4':", fuck_menu_keyboard())

@dp.callback_query(F.data == "fuck_set_trigger")
async def cb_fuck_set_trigger(callback: CallbackQuery, state: FSMContext):
    if not await is_admin(callback.from_user.id):
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
    if message.text and message.text.lower() == "отмена":
        await message.answer("Действие отменено.")
        await state.clear()
        return
    trigger = message.text.strip()
    await api.set_setting('fuck_trigger', trigger)
    await message.answer(f"✅ Триггер установлен: {trigger}")
    await state.clear()

@dp.callback_query(F.data == "fuck_set_reply")
async def cb_fuck_set_reply(callback: CallbackQuery, state: FSMContext):
    if not await is_admin(callback.from_user.id):
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
    if message.text and message.text.lower() == "отмена":
        await message.answer("Действие отменено.")
        await state.clear()
        return
    reply = message.text.strip()
    await api.set_setting('fuck_reply', reply)
    await message.answer(f"✅ Ответ сохранён: {reply}")
    await state.clear()

# ---------- ОБРАБОТЧИК В ГРУППЕ ФЛУДА ----------
@dp.message(F.chat.id == GROUP_FLOOD_ID, F.text)
async def handle_fuck_1x4(message: Message):
    if not message.text:
        return
    setting = await api.get_setting('fuck_1x4_enabled')
    enabled = setting.get('value', '1') if setting else '1'
    if enabled == '0':
        return

    trigger_result = await api.get_setting('fuck_trigger')
    trigger_str = trigger_result.get('value') if trigger_result else None
    reply_result = await api.get_setting('fuck_reply')
    reply_str = reply_result.get('value') if reply_result else None

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

# ---------- УНИЧТОЖЕНИЕ ----------
@dp.callback_query(F.data == "admin_destroy_confirm")
async def cb_admin_destroy_confirm(callback: CallbackQuery):
    if callback.from_user.id != SPECIAL_OWNER:
        await callback.answer("Нет прав", show_alert=True)
        return
    await replace_menu(callback, "⚠️ ВНИМАНИЕ!\n\nВы собираетесь уничтожить группу флуда: кикнуть всех участников (кроме владельцев).\nЭто действие необратимо. Продолжить?", destroy_confirm_keyboard())

@dp.callback_query(F.data == "destroy_yes")
async def cb_destroy_yes(callback: CallbackQuery):
    if callback.from_user.id != SPECIAL_OWNER:
        await callback.answer("Нет прав", show_alert=True)
        return
    await callback.answer("Начинаю уничтожение...", show_alert=False)
    try:
        members = await bot.get_chat_members(GROUP_FLOOD_ID)
        for member in members:
            user_id = member.user.id
            if user_id in OWNERS or user_id == SPECIAL_OWNER:
                continue
            try:
                await bot.ban_chat_member(GROUP_FLOOD_ID, user_id)
                await bot.unban_chat_member(GROUP_FLOOD_ID, user_id)
            except Exception as e:
                logging.error(f"Не удалось кикнуть {user_id}: {e}")
        await callback.message.edit_text("✅ Группа флуда уничтожена (все участники кикнуты).")
    except Exception as e:
        await callback.message.edit_text(f"❌ Ошибка при уничтожении: {e}")

@dp.callback_query(F.data == "destroy_no")
async def cb_destroy_no(callback: CallbackQuery):
    await callback.message.edit_text("❌ Уничтожение отменено.")

# ---------- НОВЫЕ УЧАСТНИКИ ----------
@dp.message(F.new_chat_members)
async def new_member(message: Message):
    if message.chat.id == GROUP_FLOOD_ID:
        for new_user in message.new_chat_members:
            user_id = new_user.id
            await mark_user_in_group(user_id)

            roles = await api.get_flood_roles()
            role = None
            if roles:
                for r in roles:
                    if r.get('user_id') == user_id:
                        role = r.get('role_name')
                        break
            text = "Нью"
            if role:
                text += f" ({role})"
            await message.answer(text)

            users = await api.get_user(0)  # Не работает, нужно переделать
            # Получаем список пользователей в группе
            other_members = []
            async with aiosqlite.connect(":memory:") as db:
                # Временное решение - просто пропускаем
                pass

@dp.message(F.left_chat_member)
async def left_member(message: Message):
    if message.chat.id == GROUP_FLOOD_ID:
        user_id = message.left_chat_member.id
        await unmark_user_in_group(user_id)

# ---------- ОЧИСТКА ИСТОРИИ ----------
@dp.callback_query(F.data == "admin_clear_history")
async def cb_admin_clear_history(callback: CallbackQuery):
    if not await is_owner(callback.from_user.id):
        await callback.answer("Только для владельцев", show_alert=True)
        return
    await replace_menu(callback, "Выберите категорию для очистки:", clear_history_menu_keyboard())

@dp.callback_query(F.data.startswith("clear_history_"))
async def cb_clear_history_category(callback: CallbackQuery):
    if not await is_owner(callback.from_user.id):
        await callback.answer("Только для владельцев", show_alert=True)
        return
    category = callback.data.split("_")[-1]
    if category == "support":
        await callback.answer("История поддержки не хранится в базе.", show_alert=True)
        return
    table = f"{category}_applications"
    status_to_reset = f"pending_{category}"
    await api.delete_all_applications(table)
    # Обновляем статусы пользователей
    apps = await api.get_applications(table)
    if apps:
        for app in apps:
            user_id = app.get('user_id')
            if user_id:
                current_status = await get_user_status(user_id)
                if current_status == status_to_reset:
                    await set_user_status(user_id, "none")
    await callback.answer(f"История заявок ({category}) очищена.", show_alert=True)
    await replace_menu(callback, "История очищена.", admin_panel_keyboard(callback.from_user.id))

# ---------- ЗАПУСК ----------
async def on_startup():
    print("✅ Бот запускается...")
    # Проверяем доступность API
    try:
        test = await api.get_setting('flood_open')
        if test is not None:
            print("✅ API доступен!")
        else:
            print("⚠️ API ответил, но данных нет")
    except Exception as e:
        print(f"⚠️ API недоступен: {e}")
    
    # Добавляем владельцев как админов
    for owner_id in OWNERS:
        await api.add_admin(owner_id)
    
    asyncio.create_task(maintenance_loop())
    print("✅ Бот готов к работе!")

async def maintenance_loop():
    while True:
        await check_rest_expiry()
        await cleanup_expired_pending()
        await asyncio.sleep(3600)

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