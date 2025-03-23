import logging
import asyncio
from aiogram import Bot, Dispatcher, Router, types, F
from aiogram.filters import Command
from aiogram.types import KeyboardButton, ReplyKeyboardMarkup, ReplyKeyboardRemove
from aiogram.fsm.state import State, StatesGroup
from aiogram.fsm.storage.memory import MemoryStorage
from aiogram.fsm.context import FSMContext
from config import BOT_TOKEN
from database import init_db, add_user, sign_agreement, add_temptation

logging.basicConfig(level=logging.INFO)

storage = MemoryStorage()
dp = Dispatcher(storage=storage)
router = Router()

# Клавиатуры
start_keyboard = ReplyKeyboardMarkup(
    keyboard=[[KeyboardButton(text="Ознакомиться с соглашением")]],
    resize_keyboard=True
)

sign_keyboard = ReplyKeyboardMarkup(
    keyboard=[[KeyboardButton(text="Подписать соглашение")]],
    resize_keyboard=True
)

# FSM-состояния
class AgreementStates(StatesGroup):
    waiting_for_sign = State()

class ComfortZoneStates(StatesGroup):
    waiting_for_temptation = State()

@router.message(Command("start"))
async def start_command(message: types.Message, state: FSMContext):
    user_id = message.from_user.id
    username = message.from_user.username or "Без ника"
    add_user(user_id, username)
    
    text = (
        f"Привет, {message.from_user.first_name} 👋\n\n"
        "Этот бот поможет тебе внедрить полезные привычки и избавиться от прокрастинации. "
        "Ты готов взять ответственность за свою жизнь?\n\n"
        "📜 Для начала тебе нужно ознакомиться и подписать соглашение с совестью. "
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

@router.message(ComfortZoneStates.waiting_for_temptation, F.text.casefold() == "стоп")
async def finish_comfort_zone(message: types.Message, state: FSMContext):
    await message.answer("Зона комфорта заполнена. Переходим к добавлению привычек.")
    await state.clear()

@router.message(ComfortZoneStates.waiting_for_temptation)
async def process_temptation(message: types.Message, state: FSMContext):
    user_id = message.from_user.id
    temptation = message.text.strip()
    add_temptation(user_id, temptation)
    await message.answer(f"Искушение «{temptation}» добавлено. Добавь следующее или напиши 'стоп' для завершения.")

dp.include_router(router)

async def main():
    await dp.start_polling(Bot(token=BOT_TOKEN))

if __name__ == "__main__":
    init_db()  # Инициализируем базу данных
    asyncio.run(main())
