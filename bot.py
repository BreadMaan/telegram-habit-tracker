import logging
import asyncio
import datetime
import re
import os
import random
import pytz
from database import init_db, add_user, sign_agreement, add_temptation, add_habit, get_user_profile, get_todays_tasks, set_wakeup_time, get_wakeup_time, update_balance, update_streak, update_max_streak, set_status, increment_fail_count, get_user_balance, set_award, get_all_users, set_day_off, get_day_off, get_user_habits, delete_habit, get_user_temptations, delete_temptation, normalize_text, set_notifications, get_notifications, set_control_mode, get_control_mode, set_control_failed, get_control_failed, set_challenges_enabled, get_challenges_enabled, get_challenge_assigned_date, set_challenge_assigned_date
from aiogram import Bot, Dispatcher, Router, types, F
from aiogram.filters import Command
from aiogram.types import KeyboardButton, ReplyKeyboardMarkup, ReplyKeyboardRemove
from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton, ReplyKeyboardRemove
from aiogram.fsm.state import State, StatesGroup
from aiogram.fsm.storage.memory import MemoryStorage
from aiogram.fsm.context import FSMContext
from aiogram.exceptions import TelegramBadRequest
from aiohttp import web
from config import BOT_TOKEN
from apscheduler.schedulers.asyncio import AsyncIOScheduler


bot = Bot(token=BOT_TOKEN)
#scheduler = AsyncIOScheduler()
scheduler = AsyncIOScheduler(timezone=pytz.timezone("Europe/Moscow"))


logging.basicConfig(level=logging.INFO)

storage = MemoryStorage()
dp = Dispatcher(storage=storage)
router = Router()

# Глобальная переменная для отслеживания вечернего ответа (проверка выполнения привычек)
pending_checks = {}  # Ключ: user_id, значение: True (ожидание ответа)

# Клавиатуры
start_keyboard = ReplyKeyboardMarkup(
    keyboard=[[KeyboardButton(text="Ознакомиться с соглашением")]],
    resize_keyboard=True
)

sign_keyboard = ReplyKeyboardMarkup(
    keyboard=[[KeyboardButton(text="Подписать соглашение")]],
    resize_keyboard=True
)

# Клавиатура главного меню
main_menu_keyboard = ReplyKeyboardMarkup(
    keyboard=[
        [KeyboardButton(text="Мой профиль")],
        [KeyboardButton(text="Мои привычки")],
        [KeyboardButton(text="Зона комфорта")],
        [KeyboardButton(text="⚙️ Настройки")]
    ],
    resize_keyboard=True
)

# Клавиатура - Меню профиля 
profile_menu_keyboard = ReplyKeyboardMarkup(
    keyboard=[
        [KeyboardButton(text="Магазин"), KeyboardButton(text="Назад")]
    ],
    resize_keyboard=True
)

# Клавиатура для меню «Мои привычки»
my_habits_menu_keyboard = ReplyKeyboardMarkup(
    keyboard=[
        [KeyboardButton(text="Добавить привычку"), KeyboardButton(text="Удалить привычку")],
        [KeyboardButton(text="Назад")]
    ],
    resize_keyboard=True
)

# Клавиатура для меню «Зона комфорта»
comfort_zone_menu_keyboard = ReplyKeyboardMarkup(
    keyboard=[
        [KeyboardButton(text="Добавить искушение"), KeyboardButton(text="Удалить искушение")],
        [KeyboardButton(text="Назад")]
    ],
    resize_keyboard=True
)

# Клавиатура для меню «Настройки»
settings_menu_keyboard = ReplyKeyboardMarkup(
    keyboard=[
        [KeyboardButton(text="📖 FAQ"), KeyboardButton(text="⏰ Напоминания")],
        [KeyboardButton(text="🔥 Режим контроля"), KeyboardButton(text="🎲 Рандомные челленджи")],
        [KeyboardButton(text="💰 Поддержать создателя")],
        [KeyboardButton(text="Назад")]
    ],
    resize_keyboard=True
)

# Клавиатура подменю «Напоминаний»
reminders_menu_keyboard = ReplyKeyboardMarkup(
    keyboard=[
        [KeyboardButton(text="Уведомления"), KeyboardButton(text="Изменить время пробуждения")],
        [KeyboardButton(text="Назад к настройкам")]
    ],
    resize_keyboard=True
)

# Клавиатура для меню «Рандомные челленджи»
challenges_menu_keyboard = ReplyKeyboardMarkup(
    keyboard=[
        [KeyboardButton(text="Включить челленджи"), KeyboardButton(text="Отключить челленджи")],
        [KeyboardButton(text="Назад к настройкам")]
    ],
    resize_keyboard=True
)




# FSM-состояния
class AgreementStates(StatesGroup):
    waiting_for_sign = State()

class ComfortZoneStates(StatesGroup):
    waiting_for_temptation = State()

# Для добавления и удаления привычек
class HabitsStates(StatesGroup):
    waiting_for_habit = State()
    waiting_for_custom_frequency = State()

class DeleteHabitStates(StatesGroup):
    waiting_for_habit_name = State()

# Для добавления и удаления искушений
class AddTemptationState(StatesGroup):
    waiting_for_temptation = State()

class DeleteTemptationState(StatesGroup):
    waiting_for_temptation_name = State()

# Для утренних уведомлений
class WakeUpStates(StatesGroup):
    waiting_for_time = State()



# Inline-клавиатура для выбора частоты привычки
frequency_keyboard = InlineKeyboardMarkup(
    inline_keyboard=[
        [InlineKeyboardButton(text="Ежедневно", callback_data="frequency_daily")],
        [InlineKeyboardButton(text="Через день", callback_data="frequency_alternate")],
        [InlineKeyboardButton(text="Свой вариант", callback_data="frequency_custom")]
    ]
)

# Inline-клавиатура для ежедневного опроса
check_keyboard = InlineKeyboardMarkup(
    inline_keyboard=[
         [InlineKeyboardButton(text="✅ Да", callback_data="check_yes"),
          InlineKeyboardButton(text="❌ Нет", callback_data="check_no")]
    ]
)

# Inline-клавиатура - Меню магазина 
shop_menu_keyboard = InlineKeyboardMarkup(
    inline_keyboard=[
        [
            InlineKeyboardButton(text="Купить 30 мин", callback_data="buy_30"),
            InlineKeyboardButton(text="Купить 1 час", callback_data="buy_1h")
        ],
        [
            InlineKeyboardButton(text="Купить 2 часа", callback_data="buy_2h")
        ],
        [
            InlineKeyboardButton(text="Отменить ограниченный день", callback_data="buy_cancel")
        ],
        [
            InlineKeyboardButton(text="Выходной от привычек", callback_data="buy_dayoff")
        ],
        [
            InlineKeyboardButton(text="Назад", callback_data="shop_back")
        ]
    ]
)

# Inline-клавиатура - «Добавить уведомления»
notif_options_keyboard = InlineKeyboardMarkup(
    inline_keyboard=[
        [
            InlineKeyboardButton(text="1 раз в день", callback_data="notif_1"),
            InlineKeyboardButton(text="3 раза в день", callback_data="notif_3"),
            InlineKeyboardButton(text="5 раз в день", callback_data="notif_5")
        ]
    ]
)

# Inline-клавиатура - «Режим контроля»
control_mode_keyboard = InlineKeyboardMarkup(
    inline_keyboard=[
        [InlineKeyboardButton(text="Мягкий (минимальный контроль)", callback_data="control_mild")],
        [InlineKeyboardButton(text="Жесткий (строгий контроль)", callback_data="control_strict")]
    ]
)

# Inline-клавиатура с вопросом в День с ограниченным функционалом - «Режим контроля»
control_response_keyboard = InlineKeyboardMarkup(
    inline_keyboard=[
        [
            InlineKeyboardButton(text="Я держусь!", callback_data="control_hold"),
            InlineKeyboardButton(text="Я сорвался.", callback_data="control_fail")
        ]
    ]
)



# Глобальные функции для уведомлений
def schedule_notifications(user_id: int, notif_times: list):
    """
    Планирует для пользователя уведомления на указанные времена.
    notif_times – список строк в формате "HH:MM".
    """
    # Для каждого времени создаём задачу с уникальным идентификатором.
    for time_str in notif_times:
        hour, minute = map(int, time_str.split(":"))
        # Формируем job_id, например "notif_123_1000" для user_id 123 и времени 10:00
        job_id = f"notif_{user_id}_{time_str.replace(':','')}"
        # Если такая задача уже есть, удаляем её
        if scheduler.get_job(job_id):
            scheduler.remove_job(job_id)
        # Добавляем задачу, которая будет срабатывать каждый день в указанное время
        scheduler.add_job(
            send_notification,
            trigger="cron",
            args=[user_id],
            id=job_id,
            hour=hour,
            minute=minute,
            timezone="Europe/Moscow"  # Московское время
        )

def unschedule_notifications(user_id: int):
    """
    Удаляет все задачи уведомлений для данного пользователя.
    """
    for job in scheduler.get_jobs():
        if job.id.startswith(f"notif_{user_id}_"):
            scheduler.remove_job(job.id)

async def send_notification(user_id: int):
    """
    Функция-обработчик для отправки уведомления пользователю.
    """
    established_notices_messages = [
    "Эй, не забыл про свои привычки? ⏳ Делай дело, чтобы потом гордиться собой!",
    "Твои привычки не выполнятся сами! 💪 Пора встать и сделать то, что ты обещал себе.",
    "Ты идёшь к цели или топчешься на месте? 🤔 Напоминаю: привычки ждут выполнения!",
    "Каждый день – это шанс стать лучше. 🔥 А ты уже сделал шаг вперёд сегодня?",
    "Успех – это маленькие победы каждый день. 🏆 Выполни привычки, чтобы приближаться к нему!",
    "Не позволяй лени побеждать! Пора действовать – привычки не ждут!",
    "Если не сейчас, то когда? ⏳ Отложишь выполнение привычек – отложишь и результат.",
    "Ты держишь ударный режим? 🚀 Тогда докажи это и выполни свои привычки сегодня!",
    "День пройдёт в любом случае. 📅 Вопрос только в том, станешь ли ты сегодня лучше. Выполняй привычки!"
    ]

    text_established_notices = random.choice(established_notices_messages)
    try:
        await bot.send_message(user_id, text_established_notices)
    except Exception as e:
        print(f"Ошибка при отправке уведомления пользователю {user_id}: {e}")


# Функция, о ограниченном дне запускается по расписанию (после утреннего напоминания о привычках)
def schedule_control_mode_for_user(user_id: int):
    from database import get_control_mode, get_user_profile
    # Получаем статус пользователя из профиля (предположим, что он находится в profile[2])
    profile = get_user_profile(user_id)
    if not profile:
        return
    status = profile[2]
    # Контрольный режим применяется только если статус "День с ограниченным функционалом"
    if status != "День с ограниченным функционалом":
        return
    mode = get_control_mode(user_id)
    # Перед планированием, можно удалить уже существующие задачи контроля для этого пользователя
    for job in scheduler.get_jobs():
        if job.id.startswith(f"control_{user_id}_"):
            scheduler.remove_job(job.id)
    if mode == "жесткий":
        # Планируем 3 сообщения: 12:30, 16:30, 21:30 (Moscow time)
        for t in ["12:30", "16:30", "21:30"]:
            hour, minute = map(int, t.split(":"))
            job_id = f"control_{user_id}_{t.replace(':','')}"
            scheduler.add_job(send_hard_control_message, "cron", args=[user_id], id=job_id, hour=hour, minute=minute, timezone="Europe/Moscow")
    elif mode == "мягкий":
        # Мягкий режим: одно сообщение в 17:30
        job_id = f"control_{user_id}_1900"
        scheduler.add_job(send_mild_control_message, "cron", args=[user_id], id=job_id, hour=17, minute=30, timezone="Europe/Moscow")



# Функция, для расчета ежедневного бонуса (в зависимости от наград пользователя)
def get_daily_bonus(max_streak):
    if max_streak >= 365:
         return 10
    elif max_streak >= 300:
         return 5
    elif max_streak >= 200:
         return 4
    elif max_streak >= 100:
         return 3
    elif max_streak >= 60:
         return 2
    elif max_streak >= 30:
         return 1
    elif max_streak >= 7:
         return 0.5
    return 0

# Функция, для получения наград в зависимости от баланса
async def daily_bonus_job():
    users = get_all_users()  # (user_id, max_streak, balance, award_100, award_500, award_1000, ...)
    for user in users:
         user_id, max_streak, balance, award_100, award_500, award_1000, *_ = user
         bonus = get_daily_bonus(max_streak)
         if bonus:
              update_balance(user_id, bonus)
         new_balance = get_user_balance(user_id)
         notifications = []
         if new_balance >= 100 and award_100 == 0:
              set_award(user_id, "award_100", 1)
              notifications.append("Поздравляю! Ты заработал награду '💵 Подушка безопасности - 100 монет на балансе!'")
         if new_balance >= 500 and award_500 == 0:
              set_award(user_id, "award_500", 1)
              notifications.append("Поздравляю! Ты заработал награду '💰 Инвестор - 500 монет на балансе!'")
         if new_balance >= 1000 and award_1000 == 0:
              set_award(user_id, "award_1000", 1)
              notifications.append("Поздравляю! Ты заработал награду '💎 Один из богатейших - 1000 монет на балансе!'")
         for note in notifications:
              try:
                   await bot.send_message(user_id, note)
              except Exception as e:
                   print(f"Ошибка при отправке наградного сообщения пользователю {user_id}: {e}")



# Функция, которая будет отправлять пользователю задачи на сегодня
async def send_daily_tasks(user_id, bot_instance): 
    tasks = get_todays_tasks(user_id)
    if tasks:
         text = "Ваши задачи на сегодня:\n" + "\n".join(f"- {task}" for task in tasks)
    else:
         text = "На сегодня задач нет."
    try:
         await bot.send_message(user_id, text)
         # Проверяем статус: если ограниченный день, отправляем дополнительное сообщение и планируем контроль
         profile = get_user_profile(user_id)
         if profile and profile[2] == "День с ограниченным функционалом":
             await send_control_morning_message(user_id)
             schedule_control_mode_for_user(user_id)
         else:
             # Если статус свободный – удаляем задачи контроля (если есть)
             unschedule_control_mode(user_id)
    except Exception as e:
         print(f"Ошибка при отправке задач пользователю {user_id}: {e}")


# Функция для планирования ежедневной отправки задач. 
# Эта функция получит время (в формате HH:MM) и добавит задачу в планировщик
def schedule_daily_tasks(user_id, wakeup_time):
    # wakeup_time в формате HH:MM
    hour, minute = map(int, wakeup_time.split(":"))
    # Формируем уникальный id задачи для пользователя
    job_id = f"daily_tasks_{user_id}"
    # Если задача с таким id уже существует, её можно удалить (на случай, если время меняется)
    if scheduler.get_job(job_id):
         scheduler.remove_job(job_id)
    # Добавляем задачу, которая будет срабатывать каждый день в указанное время
    scheduler.add_job(send_daily_tasks, "cron", args=[user_id, bot], id=job_id, hour=hour, minute=minute)


# Функция, для отправки ежедневного опроса о выполнение привычек
async def send_daily_check():
    import sqlite3
    conn = sqlite3.connect("storage.db")
    cursor = conn.cursor()
    cursor.execute("SELECT user_id FROM users")
    user_ids = [row[0] for row in cursor.fetchall()]
    conn.close()

    for user_id in user_ids:
         if get_day_off(user_id) == 1:
              # Логика для "выходного" дня (пользователь купил выходной)
              conn = sqlite3.connect("storage.db")
              cursor = conn.cursor()
              cursor.execute("SELECT current_streak, max_streak FROM users WHERE user_id=?", (user_id,))
              row = cursor.fetchone()
              conn.close()
              current_streak, max_streak = row[0], row[1]
              new_streak = current_streak + 1
              update_streak(user_id, new_streak)
              if new_streak > max_streak:
                   update_max_streak(user_id, new_streak)
              try:
                  await bot.send_message(user_id, 
                        f"Сегодня у тебя выходной, сегодня ты вне системы! Без угрызений совести, без отчётов – просто день для себя.\nНо завтра снова в строй! Не забывай, зачем ты всё это начал 🔥")
                  # Сбрасываем флаг для следующего дня
                  set_day_off(user_id, 0)
              except Exception as e:
                  print(f"Ошибка при отправке сообщения о выходном пользователю {user_id}: {e}")
         else:
              # Здесь добавляем проверку: если пользователь уже сорвался сегодня, отправляем соответствующее сообщение
              if get_control_failed(user_id) == 1:
                  try:
                      await bot.send_message(user_id,
                          "Сегодня без вечерней проверки, сегодня победило искушение. Но ты всё ещё в игре!\nЗавтра ограничения продолжаются, но у тебя – есть шанс взять реванш.",
                          reply_markup=main_menu_keyboard)
                  except Exception as e:
                      print(f"Ошибка при отправке сообщения для пользователя {user_id}: {e}")
              else:
                  try:
                      await bot.send_message(user_id, "Выполнены ли привычки сегодня?", reply_markup=check_keyboard)
                      pending_checks[user_id] = True
                  except Exception as e:
                      print(f"Ошибка при отправке опроса пользователю {user_id}: {e}")


# Callback-обработчик для кнопки опроса - ДА
@router.callback_query(F.data == "check_yes")
async def check_yes_handler(callback: types.CallbackQuery):
    user_id = callback.from_user.id
    if user_id in pending_checks:
         pending_checks.pop(user_id)
    set_status(user_id, "Свободный день")
    # Начисляем бонус. Вместо стандартных 10 монет проверяем наличие челленджа.
    today_str = datetime.datetime.now().strftime("%Y-%m-%d")
    assigned_date = get_challenge_assigned_date(user_id)
    bonus_money = 15 if assigned_date == today_str else 10
    update_balance(user_id, bonus_money)  # начисляем монеты за выполненный день
    # Получаем текущий ударный режим флаги streak-наград
    import sqlite3
    conn = sqlite3.connect("storage.db")
    cursor = conn.cursor()
    cursor.execute(
         "SELECT current_streak, award_streak_7, award_streak_30, award_streak_60, award_streak_100, award_streak_200, award_streak_300, award_streak_365 FROM users WHERE user_id=?",
         (user_id,)
    )
    row = cursor.fetchone()
    conn.close()

    current_streak = row[0] if row else 0
    new_streak = current_streak + 1
    update_streak(user_id, new_streak)

    # Поздравляем пользователя, если он достиг награды!
    notifications = []
    if new_streak >= 7 and (row[1] == 0):
         set_award(user_id, "award_streak_7", 1)
         notifications.append("Поздравляю! Ты заработал(а) награду 'Несгибаемый новичок - 7 дней без перерыва'.\nТы продержался целую неделю! Это уже не случайность – это сила характера. Продолжай в том же духе!\nТеперь ты ежедневно будешь получать +0.5 монет к своему балансу.")
    if new_streak >= 30 and (row[2] == 0):
         set_award(user_id, "award_streak_30", 1)
         notifications.append("Поздравляю! Ты заработал(а) награду '🥉 Дисциплинированный - 30 дней без перерыва'.\nМесяц дисциплины позади, и ты уже далеко не новичок. Ты доказываешь, что привычки – твой новый стиль жизни!\nТеперь ты ежедневно будешь получать +1 монету к своему балансу.")
    if new_streak >= 60 and (row[3] == 0):
         set_award(user_id, "award_streak_60", 1)
         notifications.append("Поздравляю! Ты заработал(а) награду '🥈 Стойкий чемпион - 60 дней без перерыва'.\nДва месяца – это уже серьезный уровень! Ты не просто идёшь к цели, ты становишься примером для других. Продолжай!\nТеперь ты ежедневно будешь получать +2 монеты к своему балансу.")
    if new_streak >= 100 and (row[4] == 0):
         set_award(user_id, "award_streak_100", 1)
         notifications.append("Поздравляю! Ты заработал(а) награду '🥇 Неудержимый - 100 дней без перерыва'.\nСто дней силы, фокуса и дисциплины. Это уже не просто привычки – это твоя новая реальность. Ты – машина!\nТеперь ты ежедневно будешь получать +3 монеты к своему балансу.")
    if new_streak >= 200 and (row[5] == 0):
         set_award(user_id, "award_streak_200", 1)
         notifications.append("Поздравляю! Ты заработал(а) награду '🏅 Человек железной воли - 200 дней без перерыва'.\nДвести дней – и ты по-прежнему в строю. К этому моменту большинство уже сдаются, но не ты. Ты идёшь дальше!\nТеперь ты ежедневно будешь получать +4 монеты к своему балансу.")
    if new_streak >= 300 and (row[6] == 0):
         set_award(user_id, "award_streak_300", 1)
         notifications.append("Поздравляю! Ты заработал(а) награду '🎖 Легенда самодисциплины - 300 дней без перерыва'.\nТри сотни дней. Кто-то мечтает о результатах, а ты просто их создаёшь. Это уровень чемпиона!\nТеперь ты ежедневно будешь получать +5 монет к своему балансу.")
    if new_streak >= 365 and (row[7] == 0):
         set_award(user_id, "award_streak_365", 1)
         notifications.append("Поздравляю! Ты заработал(а) награду '🏆 Мастер своей жизни - 365 дней без перерыва'.\nГод без остановки! Ты доказал, что способен на невероятное. Это не просто достижение – это новый стиль жизни. Ты победил систему!\nТеперь ты ежедневно будешь получать +10 монет к своему балансу.")
    

    # Обновляем максимум, если нужно
    conn = sqlite3.connect("storage.db")
    cursor = conn.cursor()
    cursor.execute("SELECT max_streak FROM users WHERE user_id=?", (user_id,))
    max_streak = cursor.fetchone()[0]
    conn.close()
    if new_streak > max_streak:
         update_max_streak(user_id, new_streak)

    # Отправляем уведомления о наградах (если заработал)
    for note in notifications:
         await bot.send_message(user_id, note)

    # ИСПРАВЛЯЛ
    # Список рандомных сообщений с поздравлением об успешном выполненом дне
    congratulations_successful_day_message = [
    "Миссия выполнена! ✅\nТы справился с сегодняшними задачами и получаешь заслуженный бонус - монеты в копилку!",
    "Отличная работа! 🎯 \nВсе привычки выполнены, день удался, и вот твоя награда — несколько монет на баланс. Так держать!",
    "Ты закрыл этот день на 100%! 📅 \nПриложение засчитывает успех и добавляет к твоим достижениям монеты на баланс. Вперёд к новым вершинам!",
    "Твой режим под контролем! 💪\nСегодня ты сделал всё, что нужно, а значит, +монеты в награду за стабильность. Не сбавляй темп!",
    "День прожит не зря! 🎉 \nТы снова на шаг ближе к своим целям, и за это тебе полагаются бонусные монеты. Завтра повторим? 😉",
    "Ты доказал, что держишь слово! 🔥\nВсе привычки выполнены — а значит, монеты отправляются на твой счёт. Так рождаются чемпионы!",
    " Вот это настрой! 🚀 \nСегодня ты снова в игре, привычки выполнены, и монеты летят к тебе в копилку. Завтра повторим этот успех!"
    ]

    text_congratulations_successful_day = random.choice(congratulations_successful_day_message)

    # Удаляем инлайн-клавиатуру и отправляем финальное сообщение
    # вместо прямого edit_reply_markup оборачиваем в try/except
    try:
        await callback.message.edit_reply_markup(reply_markup=None)
    except TelegramBadRequest:
        # ничего не делаем, клавиатура уже чистая
        pass
    await callback.message.answer(text_congratulations_successful_day, reply_markup=main_menu_keyboard)  # До этого, было так await callback.message.answer("Отлично! Ты справился, тебе начислено 10 монет.", reply_markup=main_menu_keyboard)
    await callback.answer()

# Callback-обработчик для кнопки опроса - НЕТ
@router.callback_query(F.data == "check_no")
async def check_no_handler(callback: types.CallbackQuery):
    user_id = callback.from_user.id
    if user_id in pending_checks:
         pending_checks.pop(user_id)
    set_status(user_id, "День с ограниченным функционалом")
    update_streak(user_id, 0)
    increment_fail_count(user_id)
    # вместо прямого edit_reply_markup оборачиваем в try/except
    try:
        await callback.message.edit_reply_markup(reply_markup=None)
    except TelegramBadRequest:
        # ничего не делаем, клавиатура уже чистая
        pass
    await callback.message.answer("Ошибки – часть пути. Но они имеют последствия.\nЗавтра день запретов и шанс стать лучше!", reply_markup=main_menu_keyboard)
    await callback.answer()


# Функция, для обработки неответа опроса о выполнение привычек (23:57)
async def handle_no_response():
    # ИСПРАВЛЯЛ
    no_answear_survey_message = [
    "Тишина – тоже ответ… 🤨\nТы не подтвердил выполнение привычек, а значит, день засчитан как провальный. Завтра – ограничения. Надеюсь, ты сделаешь выводы!",
    "Алло, приём? 📢 \nТы пропустил вечернюю проверку, а значит, сегодня без достижений. Завтра правила ужесточаются. Давай без повторений, ок?",
    "Бот не услышал твоего отчёта… 🤖 \nА раз нет ответа, значит, день пошёл в минус. Завтра тебя ждёт день без привилегий. В следующий раз не теряйся!",
    "Ты ушёл в подполье? 🕵️‍♂️ \nПропущенная проверка = провальный день. Завтра будет сложнее. Не забывай – привычки работают только, если ты в игре!",
    "Молчание – не всегда золото… ⏳ \nТы не ответил на проверку, а значит, день не засчитан. Завтра режим ограниченного дня. Будь начеку!",
    "Не отмечено – не выполнено! 📝 \nТы не дал ответа, а значит, день провален. Завтра ограничения. В следующий раз удели минуту – оно того стоит!",
    "Игнор – плохая стратегия. 🙅‍♂️ \nЕсли нет подтверждения, то нет и успеха. День провален, а завтра условия станут жестче. Не теряйся!",
    "Система ждала, но не дождалась… 🤷‍♂️ \nДень в минусе, а завтра ограничения. Надеюсь, это не станет новой привычкой?"
    ]

    text_no_answear_survey = random.choice(HARD_CONTROL_MESSAGES)
    for user_id in list(pending_checks.keys()):
         if pending_checks.get(user_id):
             try:
                 await bot.send_message(user_id, text_no_answear_survey)
             except Exception as e:
                 print(f"Ошибка при отправке сообщения о неответе пользователю {user_id}: {e}")
             # Обновляем статистику: сбрасываем ударный режим, увеличиваем счётчик провалов, устанавливаем статус
             set_status(user_id, "День с ограниченным функционалом")
             update_streak(user_id, 0)
             increment_fail_count(user_id)
             pending_checks.pop(user_id)


@router.message(Command("start"))
async def start_command(message: types.Message, state: FSMContext):
    user_id = message.from_user.id
    username = message.from_user.username or "Инкогнито"
    add_user(user_id, username)
    
    text = (
        f"Привет, {message.from_user.first_name} 👋\n\n"
        "Этот бот поможет тебе внедрить полезные привычки и избавиться от прокрастинации.\n"
        "Слабые ломаются, сильные становятся лучше. Ты с нами?\n\n"
        "Этот путь не будет лёгким, но он того стоит. Прежде чем начать, подпиши соглашение с совестью – она будет твоим союзником и судьёй.\n"
        "Если ты готов(а), то нажми кнопку внизу."
    )
    await message.answer(text, reply_markup=start_keyboard)

@router.message(F.text == "Ознакомиться с соглашением")
async def view_agreement(message: types.Message, state: FSMContext):
    text = (
        f"📝 Я, {message.from_user.first_name}, обещаю перед самим собой честно следовать правилам этого бота. "
        "Если я хоть раз совру, то накажу себя ещё строже. Клянусь дисциплиной, ответственностью и железной волей!\n\n"
        "Для подписания нажми кнопку внизу!"
    )
    await message.answer(text, reply_markup=sign_keyboard)
    await state.set_state(AgreementStates.waiting_for_sign)

@router.message(AgreementStates.waiting_for_sign, F.text == "Подписать соглашение")
async def sign_agreement_handler(message: types.Message, state: FSMContext):
    user_id = message.from_user.id
    sign_agreement(user_id)
    await message.answer(
        "🔥 СУПЕР! Теперь ты в игре. Добро пожаловать в свою новую жизнь!\n\n"
        "Давай начнем с Зоны комфорта.\n"
        "Какое искушение ты хочешь добавить? (Напиши 'стоп', чтобы закончить)",
        reply_markup=ReplyKeyboardRemove()
    )
    await state.clear()
    await state.set_state(ComfortZoneStates.waiting_for_temptation)


# Обработчик завершения Зоны комфорта – переход к привычкам
@router.message(ComfortZoneStates.waiting_for_temptation, F.text.casefold() == "стоп")
async def finish_comfort_zone(message: types.Message, state: FSMContext):
    await message.answer(
        "Зона комфорта заполнена. Теперь давай добавим привычки.\n"
        "Введи одну привычку, которую хочешь внедрить в свою жизнь. Если закончил, напиши 'стоп' для завершения.",
        reply_markup=ReplyKeyboardRemove()
    )
    await state.clear()
    await state.set_state(HabitsStates.waiting_for_habit)


# Обработчик, если пользователь пишет "стоп" в состоянии привычек
@router.message(HabitsStates.waiting_for_habit, F.text.casefold() == "стоп")
async def finish_habits(message: types.Message, state: FSMContext):
    await message.answer(
        "Список привычек сохранен.\nТеперь, мне нужно знать, во сколько ты обычно просыпаешься?\nВведи время в формате HH:MM (например, 07:00)",
        reply_markup=ReplyKeyboardRemove() #reply_markup=main_menu_keyboard
    )
    await state.clear()
    await state.set_state(WakeUpStates.waiting_for_time)


# Обработчик для ввода времени пробуждения
@router.message(WakeUpStates.waiting_for_time)
async def process_wakeup_time(message: types.Message, state: FSMContext):
    wakeup_time = message.text.strip()
    # Проверяем формат: два числа, двоеточие, два числа (например, 07:00)
    if not re.match(r"^\d{2}:\d{2}$", wakeup_time):
         await message.answer("Неверный формат. Введите время в формате HH:MM, например: 07:00")
         return
    try:
         hour, minute = map(int, wakeup_time.split(":"))
         if not (0 <= hour < 24 and 0 <= minute < 60):
              raise ValueError
    except ValueError:
         await message.answer("Неверное время. Попробуйте ещё раз. Пример: 07:00")
         return
    # Сохраняем время пробуждения для пользователя
    set_wakeup_time(message.from_user.id, wakeup_time)
    # Планируем отправку ежедневных задач (функция schedule_daily_tasks будет описана далее)
    schedule_daily_tasks(message.from_user.id, wakeup_time)
    await message.answer("Список привычек загружен! Время установлено. \nПеренаправляю в главное меню.", reply_markup=main_menu_keyboard)
    await state.clear()


# Обработчик ввода привычки
@router.message(HabitsStates.waiting_for_habit)
async def process_habit(message: types.Message, state: FSMContext):
    # Если пользователь написал не "стоп", считаем, что это привычка
    habit = message.text.strip()
    await state.update_data(current_habit=habit)
    await message.answer(
         f"Привычка: '{habit}'\nВыберите частоту повторения:",
         reply_markup=frequency_keyboard
    )


# Обработчик выбора частоты привыки через inline-кнопки
@router.callback_query(HabitsStates.waiting_for_habit, F.data.in_(["frequency_daily", "frequency_alternate", "frequency_custom"]))
async def frequency_handler(callback: types.CallbackQuery, state: FSMContext):
    data = await state.get_data()
    habit = data.get("current_habit")
    user_id = callback.from_user.id
    if callback.data == "frequency_daily":
         frequency = "ежедневно"
         add_habit(user_id, habit, frequency)
         # вместо прямого edit_reply_markup оборачиваем в try/except
         try:
             await callback.message.edit_reply_markup(reply_markup=None)
         except TelegramBadRequest:
             # ничего не делаем, клавиатура уже чистая
             pass  # удаляем клавиатуру
         await callback.message.answer(
             f"Привычка '{habit}' с частотой 'ежедневно' добавлена.\nВведите следующую привычку или напишите 'стоп' для завершения."
         )
         await state.update_data(current_habit=None)
    elif callback.data == "frequency_alternate":
         # Фиксированный набор дней для "через день"
         frequency = "понедельник, среда, пятница, воскресенье"
         add_habit(user_id, habit, frequency)
         await callback.message.answer(
             f"Привычка '{habit}' с частотой 'через день' (понедельник, среда, пятница, воскресенье) добавлена.\nВведите следующую привычку или напишите 'стоп' для завершения."
         )
         await state.update_data(current_habit=None)
    elif callback.data == "frequency_custom":
         await callback.message.answer(
             "Введите, пожалуйста, через запятую дни недели, в которые должна повторяться привычка.\nПример: понедельник, четверг, суббота"
         )
         await state.set_state(HabitsStates.waiting_for_custom_frequency)
         # Привычка (current_habit) остается в state для последующего сохранения
    await callback.answer()  # отвечаем на callback-запрос


# Обработчик ввода пользовательского варианта дней
@router.message(HabitsStates.waiting_for_custom_frequency)
async def process_custom_frequency(message: types.Message, state: FSMContext):
    user_id = message.from_user.id
    text = message.text
    # Разбиваем по запятым, удаляем лишние пробелы и приводим к нижнему регистру
    days = [day.strip().lower() for day in text.split(",")]
    allowed_days = ["понедельник", "вторник", "среда", "четверг", "пятница", "суббота", "воскресенье"]
    # Проверка на корректность
    invalid = [day for day in days if day not in allowed_days]
    if invalid:
         await message.answer(
             f"Ошибка: следующих дней не существует: {', '.join(invalid)}.\nПопробуйте снова. Пример: понедельник, четверг, суббота"
         )
         return
    frequency = ", ".join(days)
    data = await state.get_data()
    habit = data.get("current_habit")
    add_habit(user_id, habit, frequency)
    await message.answer(
        f"Привычка '{habit}' с частотой '{frequency}' добавлена.\nВведите следующую привычку или напишите 'стоп' для завершения."
    )
    # Возвращаемся в состояние ожидания следующей привычки
    await state.set_state(HabitsStates.waiting_for_habit)


@router.message(ComfortZoneStates.waiting_for_temptation)
async def process_temptation(message: types.Message, state: FSMContext):
    user_id = message.from_user.id
    temptation = message.text.strip()
    add_temptation(user_id, temptation)
    await message.answer(f"Искушение «{temptation}» добавлено. Добавь следующее или напиши 'стоп' для завершения.")


# Обработчик для кнопки «Назад» из меню профиля - возвращает в главное меню
@router.message(F.text == "Назад")
async def profile_back_handler(message: types.Message):
    await message.answer("Возвращаемся в главное меню.", reply_markup=main_menu_keyboard)


# Обработчик для кнопки «Магазин»
@router.message(F.text == "Магазин")
async def shop_handler(message: types.Message):
    shop_text = (
        "Добро пожаловать в магазин времени! \nЗдесь ты можешь купить себе небольшую передышку и немного смягчить свой режим ограниченного дня. Но помни – поблажки стоят дорого, ведь каждая из них может замедлить твой прогресс. Используй их с умом!\n\n"
        "Позиции товаров:\n"
        "1) ⏳ 30 минут свободы – 30 монет\nХочешь немного расслабиться? Купи 30 минут доступа к своим искушениям в режиме ограниченного дня. Но будь осторожен – время летит быстрее, чем ты думаешь!\n"
        "2) ⏳ 1 час вольной жизни – 55 монет\nЦелый час, чтобы заглянуть в соцсети, посмотреть серию сериала или залипнуть в игру. Но не забывай, что дисциплина важнее минутных радостей!\n"
        "3) ⏳ 2 часа без правил – 100 монет\nДва часа свободы от ограничений. Достаточно, чтобы как следует расслабиться, но хватит ли тебе силы воли вернуться в режим?\n"
        "4) 🚀 Полный день без ограничений – 300 монет\n Этот товар отменяет ограниченный режим.\nТы выкупил свою свободу в день ограниченного режима! Сегодня можешь делать что угодно, сколько угодно. Но не забывай – завтра дисциплина ждёт тебя с удвоенной силой!\n"
        "5) 🏖️ Выходной от привычек – 500 монет.\nТы заслужил передышку! Сегодня твой ударный режим не прервётся, даже если ты ничего не будешь делать. Но не превращай это в привычку!\n\n"
        "⚠️ Помни: эти поблажки – не слабость, а инструмент. Используй их мудро, ведь каждая монета даётся за упорство и труд! 💪🔥\n"
    )
    await message.answer(shop_text, reply_markup=ReplyKeyboardRemove())
    # Отправляем меню магазина (inline)
    await message.answer("Выберите товар:", reply_markup=shop_menu_keyboard)


# Далее идут обработчики для покупки товаров в магазине
# =====================================================
@router.callback_query(F.data == "buy_30")
async def buy_30_handler(callback: types.CallbackQuery):
    user_id = callback.from_user.id
    cost = 30
    current_balance = get_user_balance(user_id)
    if current_balance < cost:
         await callback.message.answer("Недостаточно средств для покупки 30 минут. Попробуйте другой товар.")
    else:
         update_balance(user_id, -cost)
    # Удаляем inline-клавиатуру и возвращаемся в меню магазина
    # вместо прямого edit_reply_markup оборачиваем в try/except
    try:
        await callback.message.edit_reply_markup(reply_markup=None)
    except TelegramBadRequest:
        # ничего не делаем, клавиатура уже чистая
        pass
    await callback.message.answer("Покупка успешна! Теперь ты можешь 30 минут посвятить любой своей хотелке.\nВозвращаемся в главное меню.", reply_markup=main_menu_keyboard)
    await callback.answer()

@router.callback_query(F.data == "buy_1h")
async def buy_1h_handler(callback: types.CallbackQuery):
    user_id = callback.from_user.id
    cost = 55
    current_balance = get_user_balance(user_id)
    if current_balance < cost:
         await callback.message.answer("Недостаточно средств для покупки 1 часа. Попробуйте другой товар.")
    else:
         update_balance(user_id, -cost)
    # вместо прямого edit_reply_markup оборачиваем в try/except
    try:
        await callback.message.edit_reply_markup(reply_markup=None)
    except TelegramBadRequest:
        # ничего не делаем, клавиатура уже чистая
        pass
    await callback.message.answer("Покупка успешна! Теперь ты можешь 1 час посвятить любой своей хотелке.\nВозвращаемся в главное меню.", reply_markup=main_menu_keyboard)
    await callback.answer()

@router.callback_query(F.data == "buy_2h")
async def buy_2h_handler(callback: types.CallbackQuery):
    user_id = callback.from_user.id
    cost = 100
    current_balance = get_user_balance(user_id)
    if current_balance < cost:
         await callback.message.answer("Недостаточно средств для покупки 2 часов. Попробуйте другой товар.")
    else:
         update_balance(user_id, -cost)
    # вместо прямого edit_reply_markup оборачиваем в try/except
    try:
        await callback.message.edit_reply_markup(reply_markup=None)
    except TelegramBadRequest:
        # ничего не делаем, клавиатура уже чистая
        pass
    await callback.message.answer("Покупка успешна! Теперь ты можешь 2 часа посвятить любой своей хотелке.\nВозвращаемся в главное меню.", reply_markup=main_menu_keyboard)
    await callback.answer()

@router.callback_query(F.data == "buy_cancel")
async def buy_cancel_handler(callback: types.CallbackQuery):
    user_id = callback.from_user.id
    cost = 300
    current_balance = get_user_balance(user_id)
    if current_balance < cost:
         await callback.message.answer("Недостаточно средств для покупки отмены ограниченного режима.")
    else:
         update_balance(user_id, -cost)
         # Изменяем статус с "День с ограниченным функционалом" на "Свободный день"
         set_status(user_id, "Свободный день")
         unschedule_control_mode(user_id)
    # вместо прямого edit_reply_markup оборачиваем в try/except
    try:
        await callback.message.edit_reply_markup(reply_markup=None)
    except TelegramBadRequest:
        # ничего не делаем, клавиатура уже чистая
        pass
    await callback.message.answer("Покупка успешна! Ограниченный режим на сегодня отменён.\nВозвращаемся в главное меню.", reply_markup=main_menu_keyboard)
    await callback.answer()

@router.callback_query(F.data == "buy_dayoff")
async def buy_dayoff_handler(callback: types.CallbackQuery):
    user_id = callback.from_user.id
    cost = 500
    current_balance = get_user_balance(user_id)
    if current_balance < cost:
         await callback.message.answer("Недостаточно средств для покупки выходного от привычек.")
    else:
         update_balance(user_id, -cost)
         # Устанавливаем флаг, что сегодня куплен выходной от привычек
         set_day_off(user_id, 1)
    # вместо прямого edit_reply_markup оборачиваем в try/except
    try:
        await callback.message.edit_reply_markup(reply_markup=None)
    except TelegramBadRequest:
        # ничего не делаем, клавиатура уже чистая
        pass
    await callback.message.answer("Покупка успешна! Выходной от привычек приобретён.\nВозвращаемся в главное меню.", reply_markup=main_menu_keyboard)
    await callback.answer()

@router.callback_query(F.data == "shop_back")
async def shop_back_handler(callback: types.CallbackQuery):
    # При нажатии "Назад" в магазине возвращаем пользователя в меню профиля
    # вместо прямого edit_reply_markup оборачиваем в try/except
    try:
        await callback.message.edit_reply_markup(reply_markup=None)
    except TelegramBadRequest:
        # ничего не делаем, клавиатура уже чистая
        pass
    await callback.message.answer("Возвращаемся в главное меню.", reply_markup=main_menu_keyboard)
    await callback.answer()

# =====================================================


@router.message(F.text == "Мой профиль")
async def profile_handler(message: types.Message):
    user_id = message.from_user.id
    profile = get_user_profile(user_id)  # получаем все данные пользователя
    if profile:
        (username, registration_date, status, current_streak, max_streak, fail_count, balance,
         award_streak_7, award_streak_30, award_streak_60, award_streak_100, award_streak_200, award_streak_300, award_streak_365,
         award_100, award_500, award_1000) = profile
        try:
            reg_date = datetime.datetime.fromisoformat(registration_date)
        except Exception:
            reg_date = datetime.datetime.now()
        days_in_bot = (datetime.datetime.now() - reg_date).days


        # Получаем дополнительные настройки
        control_mode = get_control_mode(user_id)  # "мягкий" или "жесткий"
        challenges = "Включены" if get_challenges_enabled(user_id) == 1 else "Отключены"
        notif_count = get_notifications(user_id)
        notif_status = f"Включены ({notif_count} раз(а) в день)" if notif_count > 0 else "Отключены"

        # Добавляем значок к статусу
        status_icon = "✅" if status == "Свободный день" else "❌" if status == "День с ограниченным функционалом" else ""

        # Обработка даты регистрации:
        # registration_date может быть вида "YYYY-MM-DD HH:MM:SS"
        reg_date = registration_date.split()[0]  # оставляем только дату
        # Чтобы считать, что с первого дня прошло хотя бы 1 день, используем разницу в днях и прибавляем 1
        reg_dt = datetime.datetime.strptime(reg_date, "%Y-%m-%d")
        days_in_bot = (datetime.datetime.now() - reg_dt).days + 1


        # Составляем список наград по стрику
        rewards = []
        if max_streak >= 7:
             rewards.append("🎗 Несгибаемый новичок - 7 дней без перерыва")
        if max_streak >= 30:
             rewards.append("🥉 Дисциплинированный - 30 дней без перерыва")
        if max_streak >= 60:
             rewards.append("🥈 Стойкий чемпион - 60 дней без перерыва")
        if max_streak >= 100:
             rewards.append("🥇 Неудержимый - 100 дней без перерыва")
        if max_streak >= 200:
             rewards.append("🏅 Человек железной воли - 200 дней без перерыва")
        if max_streak >= 300:
             rewards.append("🎖 Легенда самодисциплины - 300 дней без перерыва")
        if max_streak >= 365:
             rewards.append("🏆 Мастер своей жизни - 365 дней без перерыва")
        # Балансовые награды
        if award_100:
             rewards.append("💵 Подушка безопасности - 100 монет на балансе!")
        if award_500:
             rewards.append("💰 Инвестор - 500 монет на балансе!")
        if award_1000:
             rewards.append("💎 Один из богатейших - 1000 монет на балансе!")
        rewards_text = "\n".join(rewards) if rewards else "Наград пока нет."

        text = (
            f"Информация о профиле - *{message.from_user.first_name}*\n\n"
            f"{status_icon} *Статус:* {status}\n"
            f"🔥 *Режим контроля:* {control_mode.capitalize()}\n"
            f"⏰ *Уведомления:* {notif_status}\n"
            f"🎲 *Челленджи:* {challenges}\n\n"
            f"📊 *Статистика*\n"
            f"Дата регистрации: {reg_date} (в боте уже {days_in_bot} дней)\n"
            f"Текущий ударный режим: {current_streak} дней\n"
            f"Максимальный ударный режим: {max_streak} дней\n"
            f"Провалов ударного режима: {fail_count}\n\n"
            f"💰 *Баланс:* {balance} монет\n\n"
            f"🎖 *Награды:*\n{rewards_text}"
        )
        await message.answer(text, parse_mode="Markdown", reply_markup=profile_menu_keyboard)
    else:
        await message.answer("Профиль не найден.", reply_markup=main_menu_keyboard)

# ============================================================


# ОБРАБОТЧИКИ ДЛЯ РАЗДЕЛА МЕНЮ МОИ ПРИВЫЧКИ!
# Обработчик для раздела «Мои привычки»
@router.message(F.text == "Мои привычки")
async def my_habits_handler(message: types.Message):
    user_id = message.from_user.id
    habits = get_user_habits(user_id)  # Ожидается список кортежей (id, habit, frequency)
    
    daily = []
    alternate = []
    custom_dict = {}  # ключ: нормализованная строка дней, значение: список привычек
    text = "" # Инициализируем переменную text, чтобы она точно была определена
    
    for h in habits:
        habit_text = h[1].strip()
        # Приводим привычку так, чтобы первая буква была заглавной:
        habit_text = habit_text.capitalize()
        freq = h[2].strip().lower()
        if freq == "ежедневно":
            daily.append(habit_text)
        elif freq == "понедельник, среда, пятница, воскресенье":
            alternate.append(habit_text)
        else:
            # Для пользовательского варианта: нормализуем строку дней.
            # Разбиваем по запятым, обрезаем лишние пробелы и делаем первую букву каждого дня заглавной.
            days = [day.strip().capitalize() for day in freq.split(",")]
            normalized_freq = ", ".join(days)
            if normalized_freq not in custom_dict:
                custom_dict[normalized_freq] = []
            custom_dict[normalized_freq].append(habit_text)
    
    output_lines = []
    if daily:
        output_lines.append("*📈 Ежедневные привычки:*")
        for i, habit in enumerate(daily, start=1):
            output_lines.append(f"{i}. {habit}")
        output_lines.append("=========================")
    if alternate:
        output_lines.append("*📆 Понедельник/Среда/Пятница/Воскресенье:*")
        for i, habit in enumerate(alternate, start=1):
            output_lines.append(f"{i}. {habit}")
        output_lines.append("=========================")
    if custom_dict:
        output_lines.append("📌 Привычки по выбранным дням:")
        for freq, habit_list in custom_dict.items():
            output_lines.append(f"*{freq}:*")
            for i, habit in enumerate(habit_list, start=1):
                output_lines.append(f"{i}) {habit}")
            output_lines.append("-------------------------")
        output_lines.append("")
    if not output_lines:
        output_lines.append("У тебя пока нет привычек.")
    
    text = "\n".join(output_lines)
    await message.answer(text, parse_mode="Markdown", reply_markup=my_habits_menu_keyboard)



# Обработчик для кнопки «Добавить привычку»
@router.message(F.text == "Добавить привычку")
async def add_habit_from_my_habits(message: types.Message, state: FSMContext):
    await message.answer("Введи привычку, которую хочешь добавить (вводи по одной; напиши 'стоп' для завершения):", reply_markup=ReplyKeyboardRemove())
    await state.set_state(HabitsStates.waiting_for_habit)


# Обработчик, который запрашивает у пользователя название привычки для удаления:
@router.message(F.text == "Удалить привычку")
async def delete_habit_prompt(message: types.Message, state: FSMContext):
    await message.answer("Введи название привычки, которую хочешь удалить:", reply_markup=ReplyKeyboardRemove())
    await state.set_state(DeleteHabitStates.waiting_for_habit_name)


# Обработчик для ввода названия привычки:
@router.message(DeleteHabitStates.waiting_for_habit_name)
async def process_delete_habit(message: types.Message, state: FSMContext):
    user_id = message.from_user.id
    habit_name = message.text.strip()
    deleted = delete_habit(user_id, habit_name)
    if deleted:
        await message.answer(f"Привычка '{habit_name}' удалена.", reply_markup=my_habits_menu_keyboard)
    else:
        await message.answer(f"Привычки '{habit_name}' нет в твоем списке.", reply_markup=my_habits_menu_keyboard)
    await state.clear()


# Обработчик для кнопки «Назад» в меню Добавить привычку
@router.message(F.text == "Назад")
async def my_habits_back_handler(message: types.Message):
    await message.answer("Возвращаемся в главное меню.", reply_markup=main_menu_keyboard)

# ============================================================

# ОБРАБОТЧИКИ ДЛЯ РАЗДЕЛА МЕНЮ ЗОНА КОМФОРТА!
# Обработчик для раздела «Зона комфорта»
@router.message(F.text == "Зона комфорта")
async def comfort_zone_handler(message: types.Message):
    user_id = message.from_user.id
    temptations = get_user_temptations(user_id)  # список кортежей (id, temptation)
    output_lines = []
    if temptations:
        output_lines.append("**Зона комфорта:**")
        for i, temp in enumerate(temptations, start=1):
            # Приводим первую букву к заглавной
            t_text = temp[1].strip().capitalize()
            output_lines.append(f"{i}. {t_text}")
        output_lines.append("")
    else:
        output_lines.append("В Зоне комфорта пока нет искушений.")
    text = "\n".join(output_lines)
    await message.answer(text, parse_mode="Markdown", reply_markup=comfort_zone_menu_keyboard)


# Обработчики для добавления искушений в меню Зона комфорта
@router.message(F.text == "Добавить искушение")
async def add_temptation_prompt(message: types.Message, state: FSMContext):
    await message.answer("Введи искушение, которое хочешь добавить (или напиши 'стоп' для завершения):", reply_markup=ReplyKeyboardRemove())
    await state.set_state(AddTemptationState.waiting_for_temptation)

@router.message(AddTemptationState.waiting_for_temptation)
async def process_add_temptation(message: types.Message, state: FSMContext):
    if message.text.strip().lower() == "стоп":
        await message.answer("Список искушений обновлён.", reply_markup=ReplyKeyboardRemove())
        await state.clear()
        # Выводим обновлённый список и меню Зоны комфорта
        await update_comfort_zone(message)
        return
    user_id = message.from_user.id
    temptation_text = message.text.strip()
    add_temptation(user_id, temptation_text)
    await message.answer(f"Искушение '{temptation_text}' добавлено. Введи следующее или напиши 'стоп' для завершения.", reply_markup=ReplyKeyboardRemove())


# Обработчики для удаления искушений в меню Зона комфорта
@router.message(F.text == "Удалить искушение")
async def delete_temptation_prompt(message: types.Message, state: FSMContext):
    await message.answer("Введи искушение, которое хочешь удалить:", reply_markup=ReplyKeyboardRemove())
    await state.set_state(DeleteTemptationState.waiting_for_temptation_name)

@router.message(DeleteTemptationState.waiting_for_temptation_name)
async def process_delete_temptation(message: types.Message, state: FSMContext):
    user_id = message.from_user.id
    temptation_name = message.text.strip()
    deleted = delete_temptation(user_id, temptation_name)
    if deleted:
        await message.answer(f"Искушение '{temptation_name}' удалено.", reply_markup=ReplyKeyboardRemove())
    else:
        await message.answer(f"Искушения '{temptation_name}' нет в твоем списке.", reply_markup=ReplyKeyboardRemove())
    await state.clear()
    # Выводим обновлённый список и меню Зоны комфорта
    await update_comfort_zone(message)



# Функция формирует обновлённый список искушений (после добавления или удаления)
async def update_comfort_zone(message: types.Message):
    user_id = message.from_user.id
    temptations = get_user_temptations(user_id)  # Получаем список искушений (id, temptation)
    output_lines = []
    if temptations:
        output_lines.append("**Зона комфорта:**")
        for i, temp in enumerate(temptations, start=1):
            # Приводим первую букву к заглавной
            t_text = temp[1].strip().capitalize()
            output_lines.append(f"{i}. {t_text}")
        output_lines.append("")
    else:
        output_lines.append("В Зоне комфорта пока нет искушений.")
    text = "\n".join(output_lines)
    await message.answer(text, parse_mode="Markdown", reply_markup=comfort_zone_menu_keyboard)


# Обработчики для возврата в главноем меню из меню Зона комфорта
@router.message(F.text == "Назад")
async def comfort_zone_back_handler(message: types.Message):
    await message.answer("Возвращаемся в главное меню.", reply_markup=main_menu_keyboard)

# ============================================================


# ОБРАБОТЧИКИ ДЛЯ РАЗДЕЛА МЕНЮ Настройки!
# Обработчик для кнопки «Назад» для главного меню «Настройки», возвращаем его в Главное меню:
@router.message(lambda message: message.text == "Назад" and message.chat.id)
async def settings_back_handler(message: types.Message):
    await message.answer("Возвращаемся в Главное меню.", reply_markup=main_menu_keyboard)


# Обработчик для раздела «Настройки»
@router.message(F.text == "⚙️ Настройки")
async def settings_handler(message: types.Message):
    await message.answer("Меню настроек", reply_markup=settings_menu_keyboard)

# dp.include_router(router)

# Обработчик для кнопки FAQ
@router.message(F.text == "📖 FAQ")
async def faq_handler(message: types.Message):
    faq_text = (
        "Этот бот поможет тебе внедрить полезные привычки, отслеживать их выполнение, "
        "мотивировать себя ежедневными бонусами и наградами, а также предлагать различные челленджи! \n\n"
        "Это не просто трекер привычек – это твой личный вызов. Здесь нет места отговоркам и слабостям. Либо ты держишь слово, либо платишь цену за срыв.\n\n"
        "📌 Как это работает?\n"
        "1️⃣ Создаёшь привычки – сам решаешь, какие правила задаёшь для своей жизни.\n"
        "2️⃣ Получаешь напоминания – приложение не даст тебе забыть о важных делах.\n"
        "3️⃣ Отчитываешься перед собой – каждый вечер проверка: справился или нет?\n"
        "4️⃣ Живёшь по правилам – если сорвался, на следующий день ждут ограничения. Хочешь любимые развлечения? Тогда держись!\n"
        "5️⃣ Можешь купить поблажку – в магазине есть временные послабления, но они стоят дорого. Свобода имеет цену!\n\n"
        "🔥 Чем оно крутое?\n"
        "✔ Дисциплина без компромиссов – ты либо выполняешь, либо платишь за слабость. Никакого самообмана!\n"
        "✔ Система наград и штрафов – выдержал серию дней без срывов? Получи бонусы! Провалился? Готовься к ограничениям.\n"
        "✔ Контроль искушений – хочешь позволить себе расслабиться? Тебе придётся заработать это!\n"
        "✔ Сорвался? Бот следит за тобой! – если ты нарушишь правила, приложение не просто это отметит – оно усложнит тебе жизнь.\n"
        "✔ Выходной за монеты – накопил ресурсы? Можешь купить себе день отдыха, но помни – халява тут не приветствуется.\n"
    )
    # Отправляем текст FAQ и затем повторно показываем меню Настроек
    await message.answer(faq_text, reply_markup=settings_menu_keyboard)


# Обработчик для кнопки «Назад» в меню Напоминаний возвращает в меню Настроек
@router.message(lambda message: message.text == "Назад к настройкам" and message.chat.id)
async def reminders_back_handler(message: types.Message):
    # Здесь можно добавить проверку контекста, если необходимо
    await message.answer("Возвращаемся в меню Настроек.", reply_markup=settings_menu_keyboard)


# Обработчик для кнопки Напоминания
@router.message(F.text == "⏰ Напоминания")
async def reminders_handler(message: types.Message):
    await message.answer("Меню напоминаний:", reply_markup=reminders_menu_keyboard)


# Обработчик callback‑запросов для уведомлений (1, 3, 5 раз)
@router.callback_query(lambda c: c.data in ["notif_1", "notif_3", "notif_5"])
async def set_notif_handler(callback: types.CallbackQuery):
    user_id = callback.from_user.id
    option = callback.data
    if option == "notif_1":
        count = 1 
        schedule_times = ["15:00"]
    elif option == "notif_3":
        count = 3
        schedule_times = ["10:00", "15:00", "20:00"]
    elif option == "notif_5":
        count = 5
        schedule_times = ["10:00", "12:00", "15:00", "18:00", "20:00"]
    
    # Обновляем настройки уведомлений в базе
    set_notifications(user_id, count)
    # Удаляем старые задачи уведомлений, если они есть
    unschedule_notifications(user_id)
    # Планируем новые уведомления
    schedule_notifications(user_id, schedule_times)
    # ПРОВЕРКА_1
    #await callback.message.edit_reply_markup(reply_markup=None)
    try:
        await callback.message.edit_reply_markup(reply_markup=None)
    except TelegramBadRequest as e:
        if "message is not modified" in str(e):
            pass
        else:
            raise
    await bot.send_message(user_id, f"Уведомления успешно установлены ({count} раз в день).", reply_markup=reminders_menu_keyboard)
    await callback.answer()

    
    # Обновляем в БД
    set_notifications(user_id, count)
    
    # Здесь можно добавить логику для планирования уведомлений через APScheduler,
    # например, создать задачу, которая будет отправлять сообщение "Выполните привычки" в указанные часы.
    # Для простоты мы просто сообщим об установке.
    
    # вместо прямого edit_reply_markup оборачиваем в try/except
    try:
        await callback.message.edit_reply_markup(reply_markup=None)
    except TelegramBadRequest:
        # ничего не делаем, клавиатура уже чистая
        pass
    await bot.send_message(user_id, f"Уведомления успешно установлены ({count} раз в день).", reply_markup=reminders_menu_keyboard)
    await callback.answer()


# Обработчик для кнопки «Назад» (возвращает в меню Напоминаний):
@router.message(F.text == "🔙 Назад")
async def notif_back_handler(message: types.Message):
    await message.answer("Возвращаемся в меню напоминаний.", reply_markup=reminders_menu_keyboard)

# Обработчик, когда пользователь нажимает «Уведомления», проверяем состояние:
@router.message(F.text == "Уведомления")
async def notifications_status_handler(message: types.Message):
    user_id = message.from_user.id
    notif_count = get_notifications(user_id)
    if notif_count == 0:
        status_text = "В данный момент уведомления не установлены."
        # Показываем меню уведомлений с кнопками "Добавить уведомления" и "Назад"
        notif_menu_keyboard = ReplyKeyboardMarkup(
            keyboard=[
                [KeyboardButton(text="Добавить уведомления")],
                [KeyboardButton(text="🔙 Назад")]
            ],
            resize_keyboard=True
        )
    else:
        status_text = f"Уведомления уже установлены. Они будут приходить {notif_count} раз(а) в день."
        # Если уведомления установлены, можно предложить кнопку для удаления уведомлений
        notif_menu_keyboard = ReplyKeyboardMarkup(
            keyboard=[
                [KeyboardButton(text="Удалить уведомления")],
                [KeyboardButton(text="🔙 Назад")]
            ],
            resize_keyboard=True
        )
    await message.answer(status_text, reply_markup=notif_menu_keyboard)


# Обработчик для кнопки Добавить уведомления»:
@router.message(F.text == "Добавить уведомления")
async def add_notifications_handler(message: types.Message):
    await message.answer(
        "Как часто ты хочешь, чтоб бот напоминал тебе о необходимости выполнить привычки?",
        reply_markup=notif_options_keyboard
    )


# Обработчик для кнопки «Удалить уведомления»:
@router.message(F.text == "Удалить уведомления")
async def delete_notif_handler(message: types.Message):
    user_id = message.from_user.id
    set_notifications(user_id, 0)
    await message.answer("Уведомления удалены.", reply_markup=reminders_menu_keyboard)


# Обработчик для кнопки «Изменить время пробуждения»:
@router.message(F.text == "Изменить время пробуждения")
async def change_wakeup_prompt(message: types.Message, state: FSMContext):
    example_text = "Например: 07:00"
    await message.answer(f"На какое время ты хочешь изменить время пробуждения? Введи время в формате HH:MM. {example_text}", reply_markup=ReplyKeyboardRemove())
    await state.set_state(WakeUpStates.waiting_for_time)  # Используем тот же FSM-состояние, что и при регистрации


# Обработчик для ввода нового времени пробуждения
@router.message(WakeUpStates.waiting_for_time)
async def process_wakeup_time(message: types.Message, state: FSMContext):
    import re
    time_str = message.text.strip()
    if not re.match(r"^\d{2}:\d{2}$", time_str):
         await message.answer("Неверный формат. Введите время в формате HH:MM, например: 07:00")
         return
    try:
         hour, minute = map(int, time_str.split(":"))
         if not (0 <= hour < 24 and 0 <= minute < 60):
              raise ValueError
    except ValueError:
         await message.answer("Неверное время. Попробуй ещё раз. Пример: 07:00")
         return
    # Сохраняем время пробуждения для пользователя
    set_wakeup_time(message.from_user.id, time_str)
    # Перепланируем утренние задачи для этого пользователя
    schedule_daily_tasks(message.from_user.id, time_str)
    await message.answer("Время пробуждения успешно изменено.", reply_markup=reminders_menu_keyboard)
    await state.clear()



HARD_CONTROL_MESSAGES = [
    "Надеюсь, ты не нарушаешь наши договоренности и соблюдаешь день без искушений?",
    "Помни, сегодня нельзя поддаваться искушениям. Как у тебя дела?",
    "День с ограниченным функционалом – серьезное дело. Ты справляешься?",
    "Сегодня твой день испытаний. Ты до сих пор соблюдаешь ограничения или искушение взяло верх?",
    "У тебя сегодня режим ограниченного дня. Запретный плод сладок, но ты же сильнее, верно? Не поддался соблазну? Отвечай честно!",
    "Сегодня день ограничений, но завтра ты скажешь себе “спасибо”. Держишься или уже нет?",
    "Ты обещал держаться и не использовать сегодня свои искушения. Ты сдержал своё слово? Или пришлось схитрить?"
]


#Обработчик выбора режима контроля:
@router.message(F.text == "🔥 Режим контроля")
async def control_mode_prompt(message: types.Message):
    user_id = message.from_user.id
    current_mode = get_control_mode(user_id)  # функция из базы, возвращающая строку, например "мягкий" или "жесткий"
    # Сообщаем текущий режим и предлагаем изменить его
    await message.answer(
        f"У вас установлен режим контроля: {current_mode.capitalize()}.\nВыберите, какой режим хотите установить:",
        reply_markup=control_mode_keyboard
    )


#Обработчик callback режима контроля:
@router.callback_query(lambda c: c.data in ["control_mild", "control_strict"])
async def control_mode_handler(callback: types.CallbackQuery):
    user_id = callback.from_user.id
    if callback.data == "control_mild":
        set_control_mode(user_id, "мягкий")
        response_text = "Выбран минимальный режим контроля."
    else:
        set_control_mode(user_id, "жесткий")
        response_text = "Выбран строгий режим контроля."
    # Удаляем inline клавиатуру и отправляем сообщение
    # вместо прямого edit_reply_markup оборачиваем в try/except
    try:
        await callback.message.edit_reply_markup(reply_markup=None)
    except TelegramBadRequest:
        # ничего не делаем, клавиатура уже чистая
        pass
    await bot.send_message(user_id, response_text, reply_markup=settings_menu_keyboard)
    await callback.answer()

# Функции, которая отправляет сообщение о контроле утром (после напоминания)
async def send_control_morning_message(user_id: int):
    # Проверяем, что статус пользователя – "День с ограниченным функционалом"
    from database import get_user_profile
    profile = get_user_profile(user_id)
    if not profile:
        return
    status = profile[2]  # предположим, что 3-й столбец – статус
    if status != "День с ограниченным функционалом":
        return
    # Получаем список искушений (ограничений) для пользователя
    temptations = get_user_temptations(user_id)
    if not temptations:
        restrictions_text = "Нет установленных ограничений."
    else:
        restrictions_lines = []
        for i, temp in enumerate(temptations, start=1):
            restrictions_lines.append(f"{i}. {temp[1].strip().capitalize()}")
        restrictions_text = "\n".join(restrictions_lines)
    message_text = f"❌ Активирован режим ограниченного дня!\nВчера ты сорвался – так бывает. Главное – сделать выводы. Сегодня без поблажек, но завтра будет новый день.\n\nСегодня твой день исключает:\n{restrictions_text}"
    try:
        await bot.send_message(user_id, message_text)
    except Exception as e:
        print(f"Ошибка при отправке утреннего контрольного сообщения пользователю {user_id}: {e}")


# Функции, которая отправляет сообщение с вопросом (соблюдает ли пользователь ограниченный режим)
async def send_hard_control_message(user_id: int):
    # Если пользователь уже нажал "Я сорвался" сегодня, не отправляем
    if get_control_failed(user_id) == 1:
        return
    text_variant = random.choice(HARD_CONTROL_MESSAGES)
    try:
        await bot.send_message(user_id, text_variant, reply_markup=control_response_keyboard)
    except Exception as e:
        print(f"Ошибка при отправке сообщения контроля (жесткий режим) пользователю {user_id}: {e}")


#Обработчик callback‑запросы для ответов:
@router.callback_query(lambda c: c.data in ["control_hold", "control_fail"])
async def control_response_handler(callback: types.CallbackQuery):
    user_id = callback.from_user.id
    if callback.data == "control_fail":
        # Если пользователь сорвался, устанавливаем флаг
        set_control_failed(user_id, 1)
        # вместо прямого edit_reply_markup оборачиваем в try/except
        try:
            await callback.message.edit_reply_markup(reply_markup=None)
        except TelegramBadRequest:
            # ничего не делаем, клавиатура уже чистая
            pass
        await bot.send_message(user_id, "Очень жаль. Сегодня ты сорвался, и ограниченный день продлен. Возвращаемся в Главное меню.", reply_markup=main_menu_keyboard)
    else:
        # Если пользователь держится
        # вместо прямого edit_reply_markup оборачиваем в try/except
        try:
            await callback.message.edit_reply_markup(reply_markup=None)
        except TelegramBadRequest:
            # ничего не делаем, клавиатура уже чистая
            pass
        await bot.send_message(user_id, "Отлично, продолжай в том же духе!", reply_markup=main_menu_keyboard)
    await callback.answer()


# Функция режим контроля установлена на "мягкий", бот должен отправить одно сообщение в 19:00
async def send_mild_control_message(user_id: int):
    # В мягком режиме, отправляем сообщение без inline-клавиатуры
    try:
        await bot.send_message(user_id, "Напоминаем, что сегодня действует мягкий режим контроля. Держись своих принципов!", reply_markup=main_menu_keyboard)
    except Exception as e:
        print(f"Ошибка при отправке мягкого контрольного сообщения пользователю {user_id}: {e}")


# Функция которая удаляет контрольные задачи для пользователя купившего товар, отменяющий ограниченный день.
def unschedule_control_mode(user_id: int):
    for job in scheduler.get_jobs():
        if job.id.startswith(f"control_{user_id}_"):
            scheduler.remove_job(job.id)


# Варианты челленджей
RANDOM_CHALLENGES = [
    "100 приседаний и отжиманий за день (можно разбить на подходы)",
    "Пить только воду весь день (без чая, кофе, сладких напитков)",
    "Сделать растяжку утром и перед сном",
    "Попробовать контрастный душ",
    "За час до сна выключить телефон (час без экрана перед сном)",
    "Сделать дыхательное упражнение (4-7-8 или квадратное дыхание)",
    "Разобрать один 'бардак' (заметки, почту, сохраненки)",
    "Составить план на неделю",
    "Выучить 15 новых слов на иностранном языке",
    "Прочитать 20 страниц книги",
    "Написать письмо самому себе в будущее",
    "Сделать 'цифровую уборку' (разгрузить телефон, удалить ненужные файлы)",
    "Попробовать технику визуализации (представь свой идеальный день)",
    "Разобрать подписки в соцсетях и оставить только полезные",
    "Составить список 10 вещей, которые ты хотел бы изучить или попробовать",
    "Задать кому-то неожиданный, но интересный вопрос (например, 'Какая книга изменила твою жизнь?')",
    "Выбрать одно 'слабое место' в жизни и составить мини-план улучшения",
    "Сделать доброе дело, не ожидая ничего взамен",
    "Погулять 1 час"
]


# Функция и обработчики для Рандомыных челленджей
@router.message(F.text == "🎲 Рандомные челленджи")
async def challenges_settings_handler(message: types.Message):
    user_id = message.from_user.id
    enabled = get_challenges_enabled(user_id)
    if enabled == 1:
        status_text = "Рандомные челленджи сейчас включены."
        keyboard = ReplyKeyboardMarkup(
            keyboard=[
                [KeyboardButton(text="Отключить челленджи")],
                [KeyboardButton(text="Назад к настройкам")]
            ],
            resize_keyboard=True
        )
    else:
        status_text = "Рандомные челленджи сейчас отключены."
        keyboard = ReplyKeyboardMarkup(
            keyboard=[
                [KeyboardButton(text="Включить челленджи")],
                [KeyboardButton(text="Назад к настройкам")]
            ],
            resize_keyboard=True
        )
    await message.answer(status_text, reply_markup=keyboard)


@router.message(F.text == "Включить челленджи")
async def enable_challenges_handler(message: types.Message):
    user_id = message.from_user.id
    set_challenges_enabled(user_id, 1)
    # Запланировать рандомный челлендж для этого пользователя
    schedule_random_challenge_for_user(user_id)
    await message.answer("Рандомные челленджи включены. Они будут приходить раз в 3-7 дней в утреннем сообщении.", reply_markup=settings_menu_keyboard)

@router.message(F.text == "Отключить челленджи")
async def disable_challenges_handler(message: types.Message):
    user_id = message.from_user.id
    set_challenges_enabled(user_id, 0)
    unschedule_random_challenge(user_id)
    await message.answer("Рандомные челленджи отключены.", reply_markup=settings_menu_keyboard)

@router.message(lambda message: message.text == "Назад к настройкам")
async def challenges_back_handler(message: types.Message):
    await message.answer("Возвращаемся в меню Настроек.", reply_markup=settings_menu_keyboard)


# Функция планирования рандомного челленджа (должна выбрать случайный интервал (от 3 до 7 дней) и запланировать задачу)
def schedule_random_challenge_for_user(user_id: int):
    # Сначала удалим уже запланированные задачи челленджей для этого пользователя
    for job in scheduler.get_jobs():
        if job.id.startswith(f"challenge_{user_id}_"):
            scheduler.remove_job(job.id)
    # Выбираем случайный интервал от 3 до 7 дней
    days_interval = random.randint(3, 7)
    # Получаем время пробуждения пользователя
    wakeup_time = get_wakeup_time(user_id)  # Предполагается, что такая функция возвращает строку "HH:MM"
    if not wakeup_time:
        # Если время не установлено, ничего не делаем
        return
    hour, minute = map(int, wakeup_time.split(":"))
    # Определяем дату и время запуска: сегодня + days_interval, в установленное время
    # APScheduler позволяет планировать задачи по cron, но для разовых задач можно использовать date trigger
    # Здесь создадим задачу с trigger="date"
    run_date = (datetime.datetime.now() + datetime.timedelta(days=days_interval)).replace(hour=hour, minute=minute, second=0, microsecond=0)
    job_id = f"challenge_{user_id}"
    scheduler.add_job(send_random_challenge, "date", run_date=run_date, args=[user_id], id=job_id, timezone="Europe/Moscow")

# Функция для получения рандомного челленджа
def get_random_challenge() -> str:
    return random.choice(RANDOM_CHALLENGES)
# Функция для отправки рандомного челленджа
async def send_random_challenge(user_id: int):
    challenge_text = get_random_challenge()
    # Можно сохранить этот челлендж в базе для данного дня, если нужно; для простоты просто отправим сообщение
    message_text = (
        "Сегодня я добавил тебе челлендж, он обязателен к выполнению:\n"
        f"- {challenge_text}\n\n"
        "Если ты выполнишь челлендж, тебе будут начислены 15 монет за день!"
    )
    try:
        await bot.send_message(user_id, message_text)
        # Сохраняем сегодняшнюю дату в поле challenge_assigned_date
        today_str = datetime.datetime.now().strftime("%Y-%m-%d")
        set_challenge_assigned_date(user_id, today_str)
    except Exception as e:
        print(f"Ошибка при отправке рандомного челленджа пользователю {user_id}: {e}")
    # После отправки, можно сразу запланировать следующий рандомный челлендж для этого пользователя:
    if get_challenges_enabled(user_id) == 1:
        schedule_random_challenge_for_user(user_id)

# Функция для удаления рандомных челленджей
def unschedule_random_challenge(user_id: int):
    for job in scheduler.get_jobs():
        if job.id.startswith(f"challenge_{user_id}"):
            scheduler.remove_job(job.id)


# Обработчик для кнопки Поддержать автора 
@router.message(F.text == "💰 Поддержать создателя")
async def support_author_handler(message: types.Message):
    donat_text = (
        "*Спасибо что решили поддержать создателя!* ❤️\n\n"
        "💳 *Способы поддержки:*\n"
        "- [Donat](https://www.donationalerts.com/r/breadman_vl) - сайт для донатов.\n"
        "- USDT (Ethereum, ERC-20): `0x8920eecFbe78045852D464D92F24d6d6CB9509Cf`\n"
        "- USDT (TRC-20): `TVcGfCSUyX17bm2Ff1iZdjBeXnLfxbfgqu`\n"
        "- Т-Банк: `5536 9137 8940 0328`\n\n"
        "💎 Создатель: [BreadMan](https://t.me/breadman96)"
    )
    await message.answer(
        donat_text, 
        parse_mode="Markdown", 
        disable_web_page_preview=True,
        reply_markup=settings_menu_keyboard
    )


dp.include_router(router)

async def handle_health(request):
    return web.Response(text="OK")

async def start_webserver():
    app = web.Application()
    app.router.add_get("/", handle_health)
    port = int(os.environ.get("PORT", 8000))
    runner = web.AppRunner(app)
    await runner.setup()
    site = web.TCPSite(runner, '0.0.0.0', port)
    await site.start()
    print(f"Health endpoint listening on port {port} (GET+HEAD /)")

async def main():
    # 2) запускаем web‑сервер первым
    await start_webserver()
    # 3) затем стартуем APScheduler, Telegram‑polling и т.д.
    scheduler.start()  # Теперь event loop уже запущен
    # Планируем ежедневный опрос о выполнение привычек в 22:00
    scheduler.add_job(send_daily_check, "cron", hour=22, minute=00, id="daily_check")
    # Планируем проверку неответа в 23:55
    scheduler.add_job(handle_no_response, "cron", hour=23, minute=55, id="daily_no_response") 
    # Планируем отправку бонусных монет (если есть награды)
    scheduler.add_job(daily_bonus_job, "cron", hour=0, minute=5, id="daily_bonus")
    await dp.start_polling(bot)

if __name__ == "__main__":
    init_db()  # Инициализируем базу данных
    asyncio.run(main())
