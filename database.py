import sqlite3
import datetime
import re


def migrate_db():
    conn = sqlite3.connect("storage.db")
    cursor = conn.cursor()
    cursor.execute("PRAGMA table_info(users)")
    existing_columns = {row[1] for row in cursor.fetchall()}  # row[1] – имя столбца

    # Словарь необходимых столбцов: ключ – имя столбца, значение – его определение
    required_columns = {
        "day_off": "INTEGER DEFAULT 0",
        "notif_count": "INTEGER DEFAULT 0",
        "control_mode": "TEXT DEFAULT 'мягкий'",
        "control_failed_today": "INTEGER DEFAULT 0",
        "challenges_enabled": "INTEGER DEFAULT 0",
        "challenge_assigned_date": "TEXT DEFAULT NULL",
        "award_100": "INTEGER DEFAULT 0",
        "award_500": "INTEGER DEFAULT 0",
        "award_1000": "INTEGER DEFAULT 0",
        "award_streak_7": "INTEGER DEFAULT 0",
        "award_streak_30": "INTEGER DEFAULT 0",
        "award_streak_60": "INTEGER DEFAULT 0",
        "award_streak_100": "INTEGER DEFAULT 0",
        "award_streak_200": "INTEGER DEFAULT 0",
        "award_streak_300": "INTEGER DEFAULT 0",
        "award_streak_365": "INTEGER DEFAULT 0"
    }

    for column, column_def in required_columns.items():
        if column not in existing_columns:
            print(f"Миграция: добавляем столбец {column}")
            cursor.execute(f"ALTER TABLE users ADD COLUMN {column} {column_def}")
    conn.commit()
    conn.close()

def init_db():
    conn = sqlite3.connect("storage.db")
    cursor = conn.cursor()
    
    # Таблица пользователей с новыми полями
    cursor.execute('''
    CREATE TABLE IF NOT EXISTS users (
        user_id INTEGER PRIMARY KEY,
        username TEXT,
        signed_agreement BOOLEAN DEFAULT 0,
        registration_date TEXT DEFAULT (datetime('now')),
        status TEXT DEFAULT 'Свободный день',
        current_streak INTEGER DEFAULT 0,
        max_streak INTEGER DEFAULT 0,
        fail_count INTEGER DEFAULT 0,
        wakeup_time TEXT,
        balance REAL DEFAULT 0,
        day_off INTEGER DEFAULT 0,
        notif_count INTEGER DEFAULT 0,
        control_mode TEXT DEFAULT 'мягкий',
        control_failed_today INTEGER DEFAULT 0,
        challenges_enabled INTEGER DEFAULT 0,
        challenge_assigned_date TEXT DEFAULT NULL,
        award_streak_7 INTEGER DEFAULT 0,
        award_streak_30 INTEGER DEFAULT 0,
        award_streak_60 INTEGER DEFAULT 0,
        award_streak_100 INTEGER DEFAULT 0,
        award_streak_200 INTEGER DEFAULT 0,
        award_streak_300 INTEGER DEFAULT 0,
        award_streak_365 INTEGER DEFAULT 0,
        award_100 INTEGER DEFAULT 0,
        award_500 INTEGER DEFAULT 0,
        award_1000 INTEGER DEFAULT 0
    )
    ''')
    
    # Таблица искушений (зона комфорта)
    cursor.execute('''
    CREATE TABLE IF NOT EXISTS temptations (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        user_id INTEGER,
        temptation TEXT,
        FOREIGN KEY(user_id) REFERENCES users(user_id)
    )
    ''')
    
    # Таблица привычек
    cursor.execute('''
    CREATE TABLE IF NOT EXISTS habits (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        user_id INTEGER,
        habit TEXT,
        frequency TEXT,
        FOREIGN KEY(user_id) REFERENCES users(user_id)
    )
    ''')
    
    conn.commit()
    conn.close()
    # Выполняем миграцию схемы
    migrate_db()


# Функция для нормализации текста
def normalize_text(text: str) -> str:
    """
    Приводит строку к нормальному виду: заменяет последовательности пробелов на один и убирает пробелы по краям.
    """
    return re.sub(r'\s+', ' ', text).strip().lower()



# Функция для добавления пользователя в БД
def add_user(user_id, username):
    conn = sqlite3.connect("storage.db")
    cursor = conn.cursor()
    cursor.execute(
        "INSERT OR IGNORE INTO users (user_id, username) VALUES (?, ?)",
        (user_id, username)
    )
    conn.commit()
    conn.close()

# Функция для получения подписи пользователя
def sign_agreement(user_id):
    conn = sqlite3.connect("storage.db")
    cursor = conn.cursor()
    cursor.execute(
        "UPDATE users SET signed_agreement = 1 WHERE user_id = ?",
        (user_id,)
    )
    conn.commit()
    conn.close()

# Функция для получения искушений
def get_user_temptations(user_id):
    conn = sqlite3.connect("storage.db")
    cursor = conn.cursor()
    cursor.execute("SELECT id, temptation FROM temptations WHERE user_id=?", (user_id,))
    temptations = cursor.fetchall()
    conn.close()
    return temptations

# Функция для добавления искушений
def add_temptation(user_id, temptation):
    conn = sqlite3.connect("storage.db")
    cursor = conn.cursor()
    cursor.execute("INSERT INTO temptations (user_id, temptation) VALUES (?, ?)", (user_id, temptation))
    conn.commit()
    conn.close()

# Функция для удаления искушений
def delete_temptation(user_id, temptation_name):
    """
    Удаляет искушение из списка пользователя с нечувствительностью к регистру и нормализацией пробелов.
    """
    conn = sqlite3.connect("storage.db")
    cursor = conn.cursor()
    # Получаем все искушения пользователя
    cursor.execute("SELECT id, temptation FROM temptations WHERE user_id=?", (user_id,))
    rows = cursor.fetchall()
    conn.close()
    # Нормализуем входную строку
    normalized_input = normalize_text(temptation_name)
    habit_id_to_delete = None
    for tid, tempt_text in rows:
        if normalize_text(tempt_text) == normalized_input:
            habit_id_to_delete = tid
            break
    if habit_id_to_delete is not None:
        conn = sqlite3.connect("storage.db")
        cursor = conn.cursor()
        cursor.execute("DELETE FROM temptations WHERE id=?", (habit_id_to_delete,))
        conn.commit()
        changes = cursor.rowcount
        conn.close()
        return changes
    else:
        return 0


# Функция для добавления привычки
def add_habit(user_id, habit, frequency):
    conn = sqlite3.connect("storage.db")
    cursor = conn.cursor()
    cursor.execute(
        "INSERT INTO habits (user_id, habit, frequency) VALUES (?, ?, ?)",
        (user_id, habit, frequency)
    )
    conn.commit()
    conn.close()

# Функция для получения привычки
def get_user_habits(user_id):
    import sqlite3
    conn = sqlite3.connect("storage.db")
    cursor = conn.cursor()
    cursor.execute("SELECT id, habit, frequency FROM habits WHERE user_id=?", (user_id,))
    habits = cursor.fetchall()
    conn.close()
    return habits

# Функция для удаление привычки
def delete_habit(user_id, habit_name):
    import sqlite3
    conn = sqlite3.connect("storage.db")
    cursor = conn.cursor()
    
    # Получаем все привычки пользователя
    cursor.execute("SELECT id, habit FROM habits WHERE user_id=?", (user_id,))
    rows = cursor.fetchall()
    
    # Нормализуем ввод пользователя
    normalized_input = normalize_text(habit_name)
    habit_id_to_delete = None
    for habit_id, habit_text in rows:
         if normalize_text(habit_text) == normalized_input:
              habit_id_to_delete = habit_id
              break
    
    if habit_id_to_delete is not None:
         cursor.execute("DELETE FROM habits WHERE id=?", (habit_id_to_delete,))
         conn.commit()
         changes = cursor.rowcount
    else:
         changes = 0
    conn.close()
    return changes


# Функция для сохранения времени пробуждения
def set_wakeup_time(user_id, wakeup_time):
    conn = sqlite3.connect("storage.db")
    cursor = conn.cursor()
    cursor.execute("UPDATE users SET wakeup_time=? WHERE user_id=?", (wakeup_time, user_id))
    conn.commit()
    conn.close()

def get_wakeup_time(user_id: int) -> str:
    import sqlite3
    conn = sqlite3.connect("storage.db")
    cursor = conn.cursor()
    cursor.execute("SELECT wakeup_time FROM users WHERE user_id=?", (user_id,))
    row = cursor.fetchone()
    conn.close()
    return row[0] if row and row[0] else None



# Функция для получения задач на сегодня
def get_todays_tasks(user_id):
    conn = sqlite3.connect("storage.db")
    cursor = conn.cursor()
    cursor.execute("SELECT habit, frequency FROM habits WHERE user_id=?", (user_id,))
    rows = cursor.fetchall()
    conn.close()
    today = datetime.datetime.now().strftime("%A")  # английское название дня недели
    mapping = {
       "Monday": "понедельник",
       "Tuesday": "вторник",
       "Wednesday": "среда",
       "Thursday": "четверг",
       "Friday": "пятница",
       "Saturday": "суббота",
       "Sunday": "воскресенье"
    }
    today_ru = mapping.get(today, "")
    tasks = []
    for habit, frequency in rows:
         freq = frequency.strip().lower()
         if freq == "ежедневно":
              tasks.append(habit)
         elif freq == "понедельник, среда, пятница, воскресенье":
              if today_ru in ["понедельник", "среда", "пятница", "воскресенье"]:
                  tasks.append(habit)
         else:
              # custom вариант (например: "понедельник, четверг, суббота")
              days = [d.strip() for d in freq.split(",")]
              if today_ru in days:
                  tasks.append(habit)
    return tasks

# Функция для обновления баланса
def update_balance(user_id, amount):
    conn = sqlite3.connect("storage.db")
    cursor = conn.cursor()
    cursor.execute("UPDATE users SET balance = balance + ? WHERE user_id = ?", (amount, user_id))
    conn.commit()
    conn.close()

# Функция для получения баланса пользователя
def get_user_balance(user_id):
    conn = sqlite3.connect("storage.db")
    cursor = conn.cursor()
    cursor.execute("SELECT balance FROM users WHERE user_id=?", (user_id,))
    row = cursor.fetchone()
    conn.close()
    return row[0] if row else 0

# Функция для установки флага «выходного дня»
def set_day_off(user_id, value):
    import sqlite3
    conn = sqlite3.connect("storage.db")
    cursor = conn.cursor()
    cursor.execute("UPDATE users SET day_off = ? WHERE user_id = ?", (value, user_id))
    conn.commit()
    conn.close()

# Функция для получения флага «выходного дня»
def get_day_off(user_id):
    import sqlite3
    conn = sqlite3.connect("storage.db")
    cursor = conn.cursor()
    cursor.execute("SELECT day_off FROM users WHERE user_id = ?", (user_id,))
    row = cursor.fetchone()
    conn.close()
    return row[0] if row else 0


# Функция для обновления ударного режима
def update_streak(user_id, new_streak):
    conn = sqlite3.connect("storage.db")
    cursor = conn.cursor()
    cursor.execute("UPDATE users SET current_streak = ? WHERE user_id = ?", (new_streak, user_id))
    conn.commit()
    conn.close()

# Функция для обновления максимального ударного
def update_max_streak(user_id, new_max):
    conn = sqlite3.connect("storage.db")
    cursor = conn.cursor()
    cursor.execute("UPDATE users SET max_streak = ? WHERE user_id = ?", (new_max, user_id))
    conn.commit()
    conn.close()

# Функция для смены статуса в профиле 
def set_status(user_id, status):
    conn = sqlite3.connect("storage.db")
    cursor = conn.cursor()
    cursor.execute("UPDATE users SET status = ? WHERE user_id = ?", (status, user_id))
    conn.commit()
    conn.close()

# Функция для подсчета проваленных дней
def increment_fail_count(user_id):
    conn = sqlite3.connect("storage.db")
    cursor = conn.cursor()
    cursor.execute("UPDATE users SET fail_count = fail_count + 1 WHERE user_id = ?", (user_id,))
    conn.commit()
    conn.close()

# Функция для настройки наград в профиле 
def set_award(user_id, award_field, value):
    conn = sqlite3.connect("storage.db")
    cursor = conn.cursor()
    cursor.execute(f"UPDATE users SET {award_field} = ? WHERE user_id = ?", (value, user_id))
    conn.commit()
    conn.close()

# Функция для получения инфы пользователя в профиле 
def get_all_users():
    conn = sqlite3.connect("storage.db")
    cursor = conn.cursor()
    cursor.execute("SELECT user_id, max_streak, balance, award_100, award_500, award_1000 FROM users")
    users = cursor.fetchall()
    conn.close()
    return users

# Функции для Режима челленджей 
def set_challenges_enabled(user_id: int, enabled: int):
    import sqlite3
    conn = sqlite3.connect("storage.db")
    cursor = conn.cursor()
    cursor.execute("UPDATE users SET challenges_enabled = ? WHERE user_id = ?", (enabled, user_id))
    conn.commit()
    conn.close()

def get_challenges_enabled(user_id: int) -> int:
    import sqlite3
    conn = sqlite3.connect("storage.db")
    cursor = conn.cursor()
    cursor.execute("SELECT challenges_enabled FROM users WHERE user_id = ?", (user_id,))
    row = cursor.fetchone()
    conn.close()
    return row[0] if row else 0

def set_challenge_assigned_date(user_id: int, date_str: str):
    import sqlite3
    conn = sqlite3.connect("storage.db")
    cursor = conn.cursor()
    cursor.execute("UPDATE users SET challenge_assigned_date = ? WHERE user_id = ?", (date_str, user_id))
    conn.commit()
    conn.close()

def get_challenge_assigned_date(user_id: int) -> str:
    import sqlite3
    conn = sqlite3.connect("storage.db")
    cursor = conn.cursor()
    cursor.execute("SELECT challenge_assigned_date FROM users WHERE user_id = ?", (user_id,))
    row = cursor.fetchone()
    conn.close()
    return row[0] if row and row[0] is not None else ""



# Функции для Режима контроля 
def set_control_mode(user_id: int, mode: str):
    import sqlite3
    conn = sqlite3.connect("storage.db")
    cursor = conn.cursor()
    cursor.execute("UPDATE users SET control_mode = ? WHERE user_id = ?", (mode, user_id))
    conn.commit()
    conn.close()

def get_control_mode(user_id: int) -> str:
    import sqlite3
    conn = sqlite3.connect("storage.db")
    cursor = conn.cursor()
    cursor.execute("SELECT control_mode FROM users WHERE user_id = ?", (user_id,))
    row = cursor.fetchone()
    conn.close()
    return row[0] if row else "мягкий"

def set_control_failed(user_id: int, failed: int):
    import sqlite3
    conn = sqlite3.connect("storage.db")
    cursor = conn.cursor()
    cursor.execute("UPDATE users SET control_failed_today = ? WHERE user_id = ?", (failed, user_id))
    conn.commit()
    conn.close()

def get_control_failed(user_id: int) -> int:
    import sqlite3
    conn = sqlite3.connect("storage.db")
    cursor = conn.cursor()
    cursor.execute("SELECT control_failed_today FROM users WHERE user_id = ?", (user_id,))
    row = cursor.fetchone()
    conn.close()
    return row[0] if row else 0
#===============================


# Функция для установки напоминаний
def set_notifications(user_id, count):
    import sqlite3
    conn = sqlite3.connect("storage.db")
    cursor = conn.cursor()
    cursor.execute("UPDATE users SET notif_count = ? WHERE user_id = ?", (count, user_id))
    conn.commit()
    conn.close()

# Функция для получения напоминаний
def get_notifications(user_id):
    import sqlite3
    conn = sqlite3.connect("storage.db")
    cursor = conn.cursor()
    cursor.execute("SELECT notif_count FROM users WHERE user_id = ?", (user_id,))
    row = cursor.fetchone()
    conn.close()
    return row[0] if row else 0



def get_user_profile(user_id):
    import sqlite3
    conn = sqlite3.connect("storage.db")
    cursor = conn.cursor()
    cursor.execute(
        "SELECT username, registration_date, status, current_streak, max_streak, fail_count, balance, "
        "award_streak_7, award_streak_30, award_streak_60, award_streak_100, award_streak_200, award_streak_300, award_streak_365, "
        "award_100, award_500, award_1000 "
        "FROM users WHERE user_id=?",
        (user_id,)
    )
    row = cursor.fetchone()
    conn.close()
    return row



