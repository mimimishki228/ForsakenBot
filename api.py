# api.py - API для хранения данных бота
from flask import Flask, request, jsonify
import sqlite3
import json
import os
from datetime import datetime

app = Flask(__name__)

# ---------- НАСТРОЙКИ БАЗЫ ДАННЫХ ----------
DB_PATH = os.path.join(os.path.dirname(__file__), 'bot_data.db')

def get_db():
    """Подключение к SQLite базе данных"""
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn

def init_db():
    """Создание всех таблиц при первом запуске"""
    db = get_db()
    
    # Пользователи
    db.execute('''
        CREATE TABLE IF NOT EXISTS users (
            user_id INTEGER PRIMARY KEY,
            status TEXT DEFAULT 'none',
            was_in_group INTEGER DEFAULT 0,
            in_group INTEGER DEFAULT 0
        )
    ''')
    
    # Заявки во флуд
    db.execute('''
        CREATE TABLE IF NOT EXISTS flood_applications (
            user_id INTEGER PRIMARY KEY,
            text TEXT,
            status TEXT DEFAULT 'pending',
            created_at TEXT
        )
    ''')
    
    # Заявки в рест
    db.execute('''
        CREATE TABLE IF NOT EXISTS rest_applications (
            user_id INTEGER PRIMARY KEY,
            text TEXT,
            status TEXT DEFAULT 'pending',
            created_at TEXT
        )
    ''')
    
    # Заявки в стафф
    db.execute('''
        CREATE TABLE IF NOT EXISTS staff_applications (
            user_id INTEGER PRIMARY KEY,
            text TEXT,
            status TEXT DEFAULT 'pending',
            created_at TEXT
        )
    ''')
    
    # Роли флуда
    db.execute('''
        CREATE TABLE IF NOT EXISTS flood_roles (
            role_name TEXT PRIMARY KEY,
            emoji TEXT,
            user_id INTEGER
        )
    ''')
    
    # Роли реста
    db.execute('''
        CREATE TABLE IF NOT EXISTS rest_roles (
            role_name TEXT,
            expiry_date TEXT,
            user_id INTEGER,
            PRIMARY KEY (role_name, user_id)
        )
    ''')
    
    # Роли стаффа
    db.execute('''
        CREATE TABLE IF NOT EXISTS staff_roles (
            role_name TEXT,
            role_limit INTEGER,
            user_id INTEGER,
            username TEXT,
            PRIMARY KEY (role_name, user_id)
        )
    ''')
    
    # Настройки
    db.execute('''
        CREATE TABLE IF NOT EXISTS settings (
            key TEXT PRIMARY KEY,
            value TEXT
        )
    ''')
    
    # Админы
    db.execute('''
        CREATE TABLE IF NOT EXISTS admins (
            user_id INTEGER PRIMARY KEY
        )
    ''')
    
    # Забаненные
    db.execute('''
        CREATE TABLE IF NOT EXISTS banned_users (
            user_id INTEGER PRIMARY KEY
        )
    ''')
    
    # Info сообщения
    db.execute('''
        CREATE TABLE IF NOT EXISTS info_messages (
            key TEXT PRIMARY KEY,
            message_id TEXT
        )
    ''')
    
    # Запреты на заявки
    db.execute('''
        CREATE TABLE IF NOT EXISTS application_bans (
            user_id INTEGER,
            category TEXT,
            PRIMARY KEY (user_id, category)
        )
    ''')
    
    # Кулдауны
    db.execute('''
        CREATE TABLE IF NOT EXISTS cooldowns (
            user_id INTEGER,
            category TEXT,
            until_date TEXT,
            PRIMARY KEY (user_id, category)
        )
    ''')
    
    # Настройки кулдаунов
    db.execute('''
        CREATE TABLE IF NOT EXISTS cooldown_settings (
            category TEXT PRIMARY KEY,
            duration_seconds INTEGER
        )
    ''')
    
    # Диалоги поддержки
    db.execute('''
        CREATE TABLE IF NOT EXISTS support_dialogs (
            user_id INTEGER PRIMARY KEY,
            status TEXT DEFAULT 'active',
            created_at TEXT
        )
    ''')
    
    # Добавляем настройки по умолчанию
    defaults = {
        "flood_open": "1",
        "rest_open": "1",
        "staff_open": "1",
        "fuck_1x4_enabled": "1"
    }
    for key, value in defaults.items():
        db.execute(
            'INSERT OR IGNORE INTO settings (key, value) VALUES (?, ?)',
            (key, value)
        )
    
    # Добавляем настройки кулдаунов
    cooldown_defaults = {
        "flood": 7 * 86400,
        "rest": 30 * 86400,
        "staff": 10 * 86400,
        "support": 0
    }
    for category, duration in cooldown_defaults.items():
        db.execute(
            'INSERT OR IGNORE INTO cooldown_settings (category, duration_seconds) VALUES (?, ?)',
            (category, duration)
        )
    
    db.commit()
    db.close()
    print("✅ База данных инициализирована!")

# ---------- API ENDPOINTS ----------

@app.route('/', methods=['GET'])
def health_check():
    """Проверка работоспособности API"""
    return jsonify({"status": "ok", "message": "API работает!"})

# ---------- ПОЛЬЗОВАТЕЛИ ----------
@app.route('/api/user/<int:user_id>', methods=['GET'])
def get_user(user_id):
    """Получить данные пользователя"""
    db = get_db()
    user = db.execute('SELECT * FROM users WHERE user_id=?', (user_id,)).fetchone()
    db.close()
    if user:
        return jsonify(dict(user))
    return jsonify({'user_id': user_id, 'status': 'none', 'was_in_group': 0, 'in_group': 0})

@app.route('/api/user', methods=['POST'])
def update_user():
    """Обновить данные пользователя"""
    data = request.json
    db = get_db()
    db.execute(
        'INSERT OR REPLACE INTO users (user_id, status, was_in_group, in_group) VALUES (?, ?, ?, ?)',
        (data['user_id'], data.get('status', 'none'), data.get('was_in_group', 0), data.get('in_group', 0))
    )
    db.commit()
    db.close()
    return jsonify({'status': 'ok'})

# ---------- ЗАЯВКИ ----------
@app.route('/api/applications/<string:table>', methods=['GET'])
def get_all_applications(table):
    """Получить все заявки из таблицы"""
    db = get_db()
    apps = db.execute(f'SELECT * FROM {table}').fetchall()
    db.close()
    return jsonify([dict(app) for app in apps])

@app.route('/api/applications/<string:table>/<int:user_id>', methods=['GET'])
def get_application(table, user_id):
    """Получить заявку пользователя"""
    db = get_db()
    app_data = db.execute(f'SELECT * FROM {table} WHERE user_id=?', (user_id,)).fetchone()
    db.close()
    if app_data:
        return jsonify(dict(app_data))
    return jsonify({'status': 'not_found'})

@app.route('/api/applications/<string:table>', methods=['POST'])
def save_application(table):
    """Сохранить заявку"""
    data = request.json
    db = get_db()
    db.execute(
        f'INSERT OR REPLACE INTO {table} (user_id, text, status, created_at) VALUES (?, ?, ?, ?)',
        (data['user_id'], data.get('text', ''), data.get('status', 'pending'), data.get('created_at', ''))
    )
    db.commit()
    db.close()
    return jsonify({'status': 'ok'})

@app.route('/api/applications/<string:table>/<int:user_id>', methods=['DELETE'])
def delete_application(table, user_id):
    """Удалить заявку пользователя"""
    db = get_db()
    db.execute(f'DELETE FROM {table} WHERE user_id=?', (user_id,))
    db.commit()
    db.close()
    return jsonify({'status': 'ok'})

@app.route('/api/applications/<string:table>', methods=['DELETE'])
def delete_all_applications(table):
    """Удалить все заявки из таблицы"""
    db = get_db()
    db.execute(f'DELETE FROM {table}')
    db.commit()
    db.close()
    return jsonify({'status': 'ok'})

# ---------- РОЛИ ФЛУДА ----------
@app.route('/api/flood_roles', methods=['GET'])
def get_flood_roles():
    """Получить все роли флуда"""
    db = get_db()
    roles = db.execute('SELECT * FROM flood_roles').fetchall()
    db.close()
    return jsonify([dict(role) for role in roles])

@app.route('/api/flood_roles', methods=['POST'])
def update_flood_roles():
    """Обновить роли флуда (полная замена)"""
    data = request.json
    db = get_db()
    db.execute('DELETE FROM flood_roles')
    for role in data.get('roles', []):
        db.execute(
            'INSERT INTO flood_roles (role_name, emoji, user_id) VALUES (?, ?, ?)',
            (role['role_name'], role.get('emoji', ''), role.get('user_id'))
        )
    db.commit()
    db.close()
    return jsonify({'status': 'ok'})

# ---------- АДМИНЫ ----------
@app.route('/api/admins', methods=['GET'])
def get_admins():
    """Получить всех админов"""
    db = get_db()
    admins = db.execute('SELECT user_id FROM admins').fetchall()
    db.close()
    return jsonify([a[0] for a in admins])

@app.route('/api/admins', methods=['POST'])
def add_admin():
    """Добавить админа"""
    data = request.json
    db = get_db()
    db.execute('INSERT OR IGNORE INTO admins (user_id) VALUES (?)', (data['user_id'],))
    db.commit()
    db.close()
    return jsonify({'status': 'ok'})

@app.route('/api/admins/<int:user_id>', methods=['DELETE'])
def remove_admin(user_id):
    """Удалить админа"""
    db = get_db()
    db.execute('DELETE FROM admins WHERE user_id=?', (user_id,))
    db.commit()
    db.close()
    return jsonify({'status': 'ok'})

# ---------- БАНЫ ----------
@app.route('/api/banned_users', methods=['GET'])
def get_banned_users():
    """Получить всех забаненных"""
    db = get_db()
    banned = db.execute('SELECT user_id FROM banned_users').fetchall()
    db.close()
    return jsonify([b[0] for b in banned])

@app.route('/api/banned_users', methods=['POST'])
def add_banned_user():
    """Забанить пользователя"""
    data = request.json
    db = get_db()
    db.execute('INSERT OR IGNORE INTO banned_users (user_id) VALUES (?)', (data['user_id'],))
    db.commit()
    db.close()
    return jsonify({'status': 'ok'})

@app.route('/api/banned_users/<int:user_id>', methods=['DELETE'])
def remove_banned_user(user_id):
    """Разбанить пользователя"""
    db = get_db()
    db.execute('DELETE FROM banned_users WHERE user_id=?', (user_id,))
    db.commit()
    db.close()
    return jsonify({'status': 'ok'})

# ---------- НАСТРОЙКИ ----------
@app.route('/api/settings/<string:key>', methods=['GET'])
def get_setting(key):
    """Получить настройку"""
    db = get_db()
    value = db.execute('SELECT value FROM settings WHERE key=?', (key,)).fetchone()
    db.close()
    return jsonify({'value': value[0] if value else None})

@app.route('/api/settings', methods=['POST'])
def set_setting():
    """Установить настройку"""
    data = request.json
    db = get_db()
    db.execute('INSERT OR REPLACE INTO settings (key, value) VALUES (?, ?)',
               (data['key'], data['value']))
    db.commit()
    db.close()
    return jsonify({'status': 'ok'})

# ---------- КУЛДАУНЫ ----------
@app.route('/api/cooldowns/<int:user_id>/<string:category>', methods=['GET'])
def get_cooldown(user_id, category):
    """Получить кулдаун пользователя"""
    db = get_db()
    cooldown = db.execute(
        'SELECT until_date FROM cooldowns WHERE user_id=? AND category=?',
        (user_id, category)
    ).fetchone()
    db.close()
    return jsonify({'until_date': cooldown[0] if cooldown else None})

@app.route('/api/cooldowns', methods=['POST'])
def set_cooldown():
    """Установить кулдаун"""
    data = request.json
    db = get_db()
    db.execute(
        'INSERT OR REPLACE INTO cooldowns (user_id, category, until_date) VALUES (?, ?, ?)',
        (data['user_id'], data['category'], data['until_date'])
    )
    db.commit()
    db.close()
    return jsonify({'status': 'ok'})

@app.route('/api/cooldowns/<int:user_id>/<string:category>', methods=['DELETE'])
def remove_cooldown(user_id, category):
    """Удалить кулдаун"""
    db = get_db()
    db.execute('DELETE FROM cooldowns WHERE user_id=? AND category=?', (user_id, category))
    db.commit()
    db.close()
    return jsonify({'status': 'ok'})

@app.route('/api/cooldown_settings/<string:category>', methods=['GET'])
def get_cooldown_settings(category):
    """Получить настройки кулдауна"""
    db = get_db()
    duration = db.execute(
        'SELECT duration_seconds FROM cooldown_settings WHERE category=?',
        (category,)
    ).fetchone()
    db.close()
    return jsonify({'duration_seconds': duration[0] if duration else 0})

@app.route('/api/cooldown_settings', methods=['POST'])
def set_cooldown_settings():
    """Установить настройки кулдауна"""
    data = request.json
    db = get_db()
    db.execute(
        'INSERT OR REPLACE INTO cooldown_settings (category, duration_seconds) VALUES (?, ?)',
        (data['category'], data['duration_seconds'])
    )
    db.commit()
    db.close()
    return jsonify({'status': 'ok'})

# ---------- INFO MESSAGES ----------
@app.route('/api/info_messages/<string:key>', methods=['GET'])
def get_info_message(key):
    """Получить ID info сообщения"""
    db = get_db()
    msg_id = db.execute('SELECT message_id FROM info_messages WHERE key=?', (key,)).fetchone()
    db.close()
    return jsonify({'message_id': msg_id[0] if msg_id else None})

@app.route('/api/info_messages', methods=['POST'])
def set_info_message():
    """Установить ID info сообщения"""
    data = request.json
    db = get_db()
    db.execute(
        'INSERT OR REPLACE INTO info_messages (key, message_id) VALUES (?, ?)',
        (data['key'], data['message_id'])
    )
    db.commit()
    db.close()
    return jsonify({'status': 'ok'})

@app.route('/api/info_messages/<string:key>', methods=['DELETE'])
def delete_info_message(key):
    """Удалить ID info сообщения"""
    db = get_db()
    db.execute('DELETE FROM info_messages WHERE key=?', (key,))
    db.commit()
    db.close()
    return jsonify({'status': 'ok'})

# ---------- ЗАПРЕТЫ НА ЗАЯВКИ ----------
@app.route('/api/application_bans', methods=['POST'])
def add_application_ban():
    """Запретить подачу заявок"""
    data = request.json
    db = get_db()
    db.execute(
        'INSERT OR REPLACE INTO application_bans (user_id, category) VALUES (?, ?)',
        (data['user_id'], data['category'])
    )
    db.commit()
    db.close()
    return jsonify({'status': 'ok'})

@app.route('/api/application_bans/<int:user_id>/<string:category>', methods=['DELETE'])
def remove_application_ban(user_id, category):
    """Разрешить подачу заявок"""
    db = get_db()
    db.execute('DELETE FROM application_bans WHERE user_id=? AND category=?', (user_id, category))
    db.commit()
    db.close()
    return jsonify({'status': 'ok'})

@app.route('/api/application_bans/<int:user_id>/<string:category>', methods=['GET'])
def get_application_ban(user_id, category):
    """Проверить, запрещена ли подача заявок"""
    db = get_db()
    ban = db.execute(
        'SELECT 1 FROM application_bans WHERE user_id=? AND category=?',
        (user_id, category)
    ).fetchone()
    db.close()
    return jsonify({'banned': ban is not None})

# ---------- ПОДДЕРЖКА ----------
@app.route('/api/support_dialogs', methods=['POST'])
def create_support_dialog():
    """Создать диалог поддержки"""
    data = request.json
    db = get_db()
    db.execute(
        'INSERT OR REPLACE INTO support_dialogs (user_id, status, created_at) VALUES (?, ?, ?)',
        (data['user_id'], data.get('status', 'active'), data.get('created_at', ''))
    )
    db.commit()
    db.close()
    return jsonify({'status': 'ok'})

@app.route('/api/support_dialogs/<int:user_id>', methods=['GET'])
def get_support_dialog(user_id):
    """Получить диалог поддержки"""
    db = get_db()
    dialog = db.execute(
        'SELECT * FROM support_dialogs WHERE user_id=?',
        (user_id,)
    ).fetchone()
    db.close()
    if dialog:
        return jsonify(dict(dialog))
    return jsonify({'status': 'not_found'})

@app.route('/api/support_dialogs/<int:user_id>', methods=['DELETE'])
def close_support_dialog(user_id):
    """Закрыть диалог поддержки"""
    db = get_db()
    db.execute('DELETE FROM support_dialogs WHERE user_id=?', (user_id,))
    db.commit()
    db.close()
    return jsonify({'status': 'ok'})

if __name__ == '__main__':
    # Инициализируем базу данных при запуске
    init_db()
    # Запускаем сервер
    port = int(os.environ.get('PORT', 5000))
    app.run(host='0.0.0.0', port=port, debug=False)