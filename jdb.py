import asyncio
from aiogram import Bot, Dispatcher, types, F
from aiogram.types import ReplyKeyboardMarkup, KeyboardButton, InlineKeyboardMarkup, InlineKeyboardButton
from mdb import add_camera, delete_camera, get_cameras, add_color, delete_color, add_rule, delete_rule, get_color_name, get_colors, get_rule_for_camera, update_camera_name, update_camera_url
from aiogram.filters.command import Command
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
import sqlite3

from aiogram.fsm.storage.memory import MemoryStorage


API_TOKEN = '7454817299:AAFqDW1tjGy9n5piF6iMUgQNB2E8FLUCL1s'

bot = Bot(token=API_TOKEN)
storage = MemoryStorage()
dp = Dispatcher()

class EditState(StatesGroup):
    waiting_for_new_url = State()
    waiting_for_new_name = State()
    waiting_for_rule_type = State()
    waiting_for_rule_color = State()
    waiting_for_camera_name = State()
    waiting_for_camera_url = State()

async def run_bot():
    await dp.start_polling(bot)

async def send_msg(text, chat_id):
    await bot.send_message(chat_id = chat_id, text=text, request_timeout=60)

def main_keyboard():
    buttons = [
    [KeyboardButton(text='Добавить Камеру')],
    [KeyboardButton(text="Список Камер")],
    ]
    keyboard = ReplyKeyboardMarkup(keyboard=buttons, resize_keyboard=True)
    return keyboard

def add_user(user_id, username):
    conn = sqlite3.connect('users.db')
    c = conn.cursor()
    c.execute('INSERT OR IGNORE INTO users1 (id, name) VALUES (?, ?)', (user_id, username))
    conn.commit()
    conn.close()

@dp.message(Command("start"))
async def send_welcome(message: types.Message):
    user_id = message.chat.id
    username = message.from_user.first_name
    add_user(user_id, username)
    await message.reply("Ваш аккаунт добавлен в список получателей рассылки")
    
@dp.message(F.text.lower() == "добавить камеру")
async def add_camera_handler(message: types.Message, state: FSMContext):
    await state.set_state(EditState.waiting_for_camera_name)
    await message.reply("Введите название камеры: (или введите /cancel для отмены)")

@dp.message(EditState.waiting_for_camera_name)
async def camera_name_handler(message: types.Message, state: FSMContext):
    if message.text.lower() == "/cancel":
        await cancel_handler(message, state)
        return

    camera_name = message.text
    await state.update_data(camera_name=camera_name)
    await state.set_state(EditState.waiting_for_camera_url)
    await message.reply("Теперь введите URL камеры: (или введите /cancel для отмены)")

@dp.message(EditState.waiting_for_camera_url)
async def camera_url_handler(message: types.Message, state: FSMContext):
    if message.text.lower() == "/cancel":
        await cancel_handler(message, state)
        return

    camera_url = message.text
    data = await state.get_data()
    camera_name = data.get("camera_name")

    add_camera(camera_url, camera_name)
    await message.reply(f"Камера '{camera_name}' с URL '{camera_url}' добавлена.")
    await state.clear()


@dp.message(F.text.lower() == "удалить камеру")
async def delete_camera_handler(message: types.Message):
    await message.reply("Введите ID камеры для удаления:")

@dp.message(F.text.lower() == "список камер")
async def list_cameras_handler(message: types.Message):
    cameras = get_cameras()
    if cameras:
        inline_keyboard = []
        for cam in cameras:
            button = InlineKeyboardButton(text=f"Камера {cam[2]}", callback_data=f"camera_{cam[0]}")
            inline_keyboard.append([button])
        keyboard = InlineKeyboardMarkup(inline_keyboard=inline_keyboard)
        await message.reply("Список доступных камер:", reply_markup=keyboard)
    else:
        await message.reply("Нет доступных камер.")

@dp.callback_query(F.data.startswith("camera_"))
async def camera_info_handler(callback_query: types.CallbackQuery):
    camera_id = int(callback_query.data.split("_")[1])
    cameras = get_cameras()
    camera = next((cam for cam in cameras if cam[0] == camera_id), None)
    
    if camera:
        rule = get_rule_for_camera(camera_id)
        
        rule_text = "Правило: Нет правила"
        if rule:
            access_type = "разрешение" if rule[0] else "запрет"
            color_name = get_color_name(rule[1])
            rule_text = f"Правило: {access_type} цвета {color_name}"
        
        keyboard = InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text="Удалить", callback_data=f"delete_{camera_id}")],
            [InlineKeyboardButton(text="Изменить URL", callback_data=f"edit_url_{camera_id}")],
            [InlineKeyboardButton(text="Изменить Название", callback_data=f"edit_name_{camera_id}")],
            [InlineKeyboardButton(text="Изменить правило", callback_data=f"addrule_{camera_id}")]
        ])
        await callback_query.message.edit_text(
            f"Камера {camera[2]}\nURL: {camera[1]}\n{rule_text}", 
            reply_markup=keyboard
        )
    else:
        await callback_query.message.reply("Камера не найдена.")

@dp.callback_query(F.data.startswith("delete_"))
async def delete_camera_callback_handler(callback_query: types.CallbackQuery):
    camera_id = int(callback_query.data.split("_")[1])
    delete_camera(camera_id)
    await callback_query.message.reply(f"Камера с ID {camera_id} удалена")

@dp.callback_query(F.data.startswith("edit_ip"))
async def edit_camera_callback_handler(callback_query: types.CallbackQuery, state: FSMContext):
    camera_id = int(callback_query.data.split("_")[1])
    await state.update_data(camera_id=camera_id)
    await state.set_state(EditState.waiting_for_new_url)
    await callback_query.message.reply(f"Введите новый URL для камеры {camera_id}: (или введите /cancel для отмены)")

@dp.callback_query(F.data.startswith("edit_name"))
async def edit_camera_callback_handler(callback_query: types.CallbackQuery, state: FSMContext):
    camera_id = int(callback_query.data.split("_")[2])
    await state.update_data(camera_id=camera_id)
    await state.set_state(EditState.waiting_for_new_name)
    await callback_query.message.reply(f"Введите новое название для камеры {camera_id}: (или введите /cancel для отмены)")

@dp.callback_query(F.data.startswith("addrule_"))
async def add_rule_callback_handler(callback_query: types.CallbackQuery, state: FSMContext):
    camera_id = int(callback_query.data.split("_")[1])
    await state.update_data(camera_id=camera_id)
    await state.set_state(EditState.waiting_for_rule_type)
    keyboard = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="Запрет цвета", callback_data="rule_ban")],
        [InlineKeyboardButton(text="Разрешение цвета", callback_data="rule_allow")]
    ])
    await callback_query.message.edit_text("Выберите тип правила:", reply_markup=keyboard)

@dp.callback_query(F.data == "rule_ban")
async def rule_ban_handler(callback_query: types.CallbackQuery, state: FSMContext):
    await state.update_data(rule_type="ban")
    await send_color_list(callback_query.message, state)

@dp.callback_query(F.data == "rule_allow")
async def rule_allow_handler(callback_query: types.CallbackQuery, state: FSMContext):
    await state.update_data(rule_type="allow")
    await send_color_list(callback_query.message, state)

async def send_color_list(message, state: FSMContext):
    colors = get_colors()

    inline_keyboard = []
    for color in colors:
        button = InlineKeyboardButton(text=f"{color[1]} (ID: {color[0]})", callback_data=f"color_{color[0]}")
        inline_keyboard.append([button])

    keyboard = InlineKeyboardMarkup(inline_keyboard=inline_keyboard)
    await state.set_state(EditState.waiting_for_rule_color)
    await message.edit_text("Выберите цвет для правила:", reply_markup=keyboard)

@dp.callback_query(F.data.startswith("color_"))
async def rule_color_handler(callback_query: types.CallbackQuery, state: FSMContext):
    color_id = int(callback_query.data.split("_")[1])
    data = await state.get_data()
    camera_id = data.get("camera_id")
    rule_type = data.get("rule_type")
    access_granted = rule_type == "allow"

    add_rule(camera_id, color_id, access_granted)
    await callback_query.message.edit_text(f"Правило для камеры {camera_id} обновлено: {rule_type} цвета {get_color_name(color_id)}")
    await state.clear()    

@dp.message(EditState.waiting_for_new_url)
async def update_camera_url_handler(message: types.Message, state: FSMContext):
    if message.text.lower() == "/cancel":
        await cancel_handler(message, state)
        return

    new_url = message.text
    data = await state.get_data()
    camera_id = data.get("camera_id")

    # Обновление URL в базе данных
    update_camera_url(camera_id, new_url)
    await message.reply(f"URL для камеры {camera_id} обновлен на {new_url}.")
    await state.clear()

@dp.message(EditState.waiting_for_new_name)
async def new_name_handler(message: types.Message, state: FSMContext):
    new_name = message.text
    if new_name.lower() == "/cancel":
        await cancel_handler(message, state)
        return

    data = await state.get_data()
    camera_id = data.get("camera_id")
    update_camera_name(camera_id, new_name)
    await message.reply(f"Название камеры с ID {camera_id} обновлен на {new_name}")
    await state.clear()

@dp.message(EditState.waiting_for_rule_color)
async def rule_color_handler(message: types.Message, state: FSMContext):
    if message.text.lower() == "/cancel":
        await cancel_handler(message, state)
        return

    color_id = int(message.text)
    data = await state.get_data()
    camera_id = data.get("camera_id")
    rule_type = data.get("rule_type")
    access_granted = rule_type == "allow"
    add_rule(camera_id, color_id, access_granted)
    await message.reply(f"Правило для камеры {camera_id} с цветом {color_id} {'разрешено' if access_granted else 'запрещено'}")
    await state.clear()

@dp.message(Command("cancel"))
async def cancel_handler(message: types.Message, state: FSMContext):
    await state.clear()
    await message.reply("Действие отменено.", reply_markup=main_keyboard())


@dp.message()
async def handle_input(message: types.Message):
    text = message.text

if __name__ == '__main__':
    asyncio.run(run_bot())
