import av.error
import cv2
import datetime
import numpy as np
from telegram import Bot, Update
from telegram.ext import ApplicationBuilder, Updater, CommandHandler, CallbackContext, MessageHandler, filters
import asyncio
import time
from multiprocessing import Process
import sqlite3
from ultralytics import YOLO
from concurrent.futures import ThreadPoolExecutor
import os
import uuid
import threading
import av

from jdb import run_bot
from jdb import send_msg
from mdb import get_color_name

model = YOLO('yolov8n-seg.pt')

def init_db():
    conn = sqlite3.connect('users.db')
    c = conn.cursor()
    c.execute('''
        CREATE TABLE IF NOT EXISTS users (
            id INTEGER PRIMARY KEY,
            name TEXT NULL
        )
    ''')
    conn.commit()
    conn.close()

def add_user(user_id, username):
    conn = sqlite3.connect('users.db')
    c = conn.cursor()
    c.execute('INSERT OR IGNORE INTO users (id, name) VALUES (?, ?)', (user_id, username))
    conn.commit()
    conn.close()

# Обработчик команды /start
def start(update: Update, context: CallbackContext):
    user_id = update.message.chat_id
    username = update.message.from_user.first_name
    add_user(user_id, username)

def load_image_from_file(image_path):
    frame = cv2.imread(image_path)
    if frame is None:
        print("Ошибка чтения изображения.")
        return None
    return frame

def load_image_from_rtsp(rtsp_url):
    try:
        cap = cv2.VideoCapture(rtsp_url, apiPreference=cv2.CAP_ANY, params=[cv2.CAP_PROP_OPEN_TIMEOUT_MSEC, 10000])
             
        if not cap.isOpened():
            print("Ошибка подключения к камере.")
            return None
    except Exception as e:
        print(e)
    ret, frame = cap.read()
    cap.release()

    if ret:
        return frame
    else:
        print("Ошибка чтения кадра.")
        return None
    
def get_colors():
    conn = sqlite3.connect('users.db')
    cursor = conn.cursor()
    cursor.execute("SELECT name, lower_bound, upper_bound FROM Colors")
    colors = cursor.fetchall()
    conn.close()
    return [(name, eval(lower_bound), eval(upper_bound)) for name, lower_bound, upper_bound in colors]

def get_color_namee(frame, person_segments):
    conn = sqlite3.connect('users.db')
    cursor = conn.cursor()
    cursor.execute("SELECT name, lower_bound, upper_bound FROM Colors")
    color_data = cursor.fetchall()
    conn.close()

    hsv_frame = cv2.cvtColor(frame, cv2.COLOR_BGR2HSV)
    contour_mask = np.zeros(frame.shape[:2], dtype=np.uint8)
    
    for segment in person_segments:
        segment = np.array(segment, dtype=np.int32)
        cv2.drawContours(contour_mask, [segment], -1, 255, thickness=cv2.FILLED)
    
    masked_frame = cv2.bitwise_and(hsv_frame, hsv_frame, mask=contour_mask)
    
    total_pixels = cv2.countNonZero(contour_mask)
    if total_pixels == 0:
        return "Контур не найден"

    for name, lower_bound, upper_bound in color_data:
        lower_bound = np.array(eval(lower_bound), dtype=np.uint8)
        upper_bound = np.array(eval(upper_bound), dtype=np.uint8)
        mask = cv2.inRange(masked_frame, lower_bound, upper_bound)
        mask_pixels = cv2.countNonZero(mask)
        ratio = mask_pixels / total_pixels
        
        if ratio > 0.15:
            return name  # Возвращаем имя первого найденного подходящего цвета
    
    return "Запрещенный цвет"

def detect_person(frame, conf_threshold=0.7):
    try:
        # Получаем результаты сегментации от модели
        results = model(frame)
        
        # Получаем bounding boxes и маски
        detections = results[0].boxes
        masks = results[0].masks

        persons = []
        
        for i in range(len(detections)):
            box = detections.xyxy[i]
            conf = detections.conf[i]
            cls = detections.cls[i]
            print(f"Detection {i}: Class {cls}, Confidence {conf}, Box {box}")
            
            if cls == 0 and conf >= conf_threshold:  # 0 соответствует человеку
                # Получаем сегменты в виде списка координат (контуры)
                person_segments = masks[i].xy  # Список контуров в формате координат пикселей
                persons.append((box, person_segments))
        
        return persons  # Возвращаем список (box, segments) для каждого человека
    except Exception as e:
        print(f'detect error: {e}')
        return []

def get_cameras():
    conn = sqlite3.connect('users.db')
    cursor = conn.cursor()
    cursor.execute("SELECT id, url, name FROM Cameras")
    cameras = cursor.fetchall()
    conn.close()
    return cameras

def get_access_rule(camera_id, color_name):
    allowed_colors, forbidden_colors = get_access_rules(camera_id)
    
    if color_name == "Запрещенный цвет":
        # Если цвет не распознан, решение принимается на основе правила для красного
        if "ярко-красный" in forbidden_colors:
            return True  # Если красный запрещен, доступ запрещен
        elif "ярко-красный" in allowed_colors:
            return False  # Если красный разрешен, доступ разрешен
    else:
        # Если цвет распознан, проверяем разрешён ли он
        if color_name in allowed_colors:
            return True  # Если цвет разрешен, доступ разрешен
        if color_name in forbidden_colors:
            return False  # Если цвет запрещен, доступ запрещен
    
    return True  # Если правила не найдены, доступ разрешен по умолчанию

def get_access_rules(camera_id):
    conn = sqlite3.connect('users.db')
    cursor = conn.cursor()
    
    # Получаем все правила для данной камеры
    cursor.execute("""
    SELECT r.access_granted, c.name
    FROM Rules r
    JOIN Colors c ON r.color_id = c.id
    WHERE r.camera_id = ?
    """, (camera_id,))
    
    rules = cursor.fetchall()
    conn.close()
    
    allowed_colors = set()
    forbidden_colors = set()
    
    # Сортируем цвета по типу правила
    for access_granted, color_name in rules:
        if access_granted:
            allowed_colors.add(color_name)
        else:
            forbidden_colors.add(color_name)
    
    return allowed_colors, forbidden_colors

def save_photo_locally(image_path):
    # Определяем текущий месяц, день и дату
    current_date = datetime.datetime.now()
    month = current_date.strftime('%Y-%m')
    day = current_date.strftime('%d')
    date_str = current_date.strftime('%d-%m-%Y')

    # Создаем директорию, если она не существует
    directory = os.path.join('images', month, day)
    os.makedirs(directory, exist_ok=True)

    # Получаем оригинальное имя файла и его расширение
    original_filename = os.path.basename(image_path)
    file_name, file_extension = os.path.splitext(original_filename)

    # Создаем новое имя файла с датой и уникальным суффиксом
    unique_suffix = str(uuid.uuid4().int)[:8]  # Уникальные цифры (первые 8 цифр UUID)
    new_filename = f"{file_name}_{date_str}_{unique_suffix}{file_extension}"

    # Полный путь для сохранения файла
    save_path = os.path.join(directory, new_filename)

    # Сохраняем фото в созданной директории
    with open(image_path, 'rb') as src_file:
        with open(save_path, 'wb') as dst_file:
            dst_file.write(src_file.read())
    
    return save_path  # Возвращаем путь, по которому сохранен файл
    
    
async def send_telegram_message_with_image(bot, image_path, message):
    # Подключаемся к базе данных и получаем ID пользователей
    conn = sqlite3.connect('users.db')
    c = conn.cursor()
    c.execute('SELECT id FROM users1')
    chat_ids = [row[0] for row in c.fetchall()]
    conn.close()

    local_image_path = save_photo_locally(image_path)

    try:
        # Отправляем фото одному пользователю, чтобы получить file_id
        with open(local_image_path, 'rb') as photo:
            msg = await Bot("7454817299:AAFqDW1tjGy9n5piF6iMUgQNB2E8FLUCL1s").send_photo(chat_id=chat_ids[0], photo=photo, caption=message)
            file_id = msg.photo[-1].file_id  

        # Пересылаем фото остальным пользователям, используя file_id
        for chat_id in chat_ids[1:]:
            try:
                await Bot("7454817299:AAFqDW1tjGy9n5piF6iMUgQNB2E8FLUCL1s").send_photo(chat_id=chat_id, photo=file_id, caption=message)
            except:
                print('Ошибка отправки сообщения пользователю ' + str(chat_id))

    except Exception as e:
        print(f'Ошибка отправки сообщения через Telegram: {e}')
        # Не прерываем выполнение кода, продолжаем дальше
    """ try:
        await bot.send_photo(chat_id=673492271, photo=open(image_path, 'rb'), caption=message)

    except:
        print('Ошибка отправки сообщения пользователю ' + str(673492271)) """       

def draw_label(frame, text, pos, color):
    font_face = cv2.FONT_HERSHEY_COMPLEX
    scale = 0.9
    thickness = 2
    
    text_size = cv2.getTextSize(text, font_face, scale, thickness)
    x, y = pos
    text_w, text_h = text_size[0]
    cv2.rectangle(frame, (x, y - text_h - 10), (x + text_w, y + 5), (0, 0, 0), -1)
    cv2.putText(frame, text, (x, y), font_face, scale, color, thickness)

async def process_camera(camera_id, RTSP_URL, bot):
    while True:
        # current_hour = datetime.now().hour
        # if current_hour >= 19 or current_hour < 7:
        #     await asyncio.sleep(60)  # Ждем 1 минуту перед следующей проверкой
        #     continue

        print(f"[{time.strftime('%Y-%m-%d %H:%M:%S')}] Обработка камеры: {RTSP_URL}")

        frame = load_image_from_rtsp(RTSP_URL)
        await asyncio.sleep(3)
        if frame is None:
            continue

        persons = detect_person(frame)
        has_person_with_wrong_color = False

        for box, person_segments in persons:
            x1, y1, x2, y2 = map(int, box)  # Преобразуем координаты в целые числа
            person_mask = [person_segments]  # Убедитесь, что person_segments является списком масок

            color_name = get_color_namee(frame, person_mask)
            
            if not get_access_rule(camera_id, color_name):
                has_person_with_wrong_color = True
                
                # Рисуем прямоугольник на изображении
                cv2.rectangle(frame, (x1, y1), (x2, y2), (0, 255, 0), 2)
                draw_label(frame, "запрещенный цвет", (x1, y1 - 10), (0, 255, 0))

        if has_person_with_wrong_color:
            try:
                local_image_path = 'result_image.png'
                cv2.imwrite(local_image_path, frame)            
                await send_telegram_message_with_image(bot, local_image_path, 'Посещение с запрещенным цветом одежды')
  
            except Exception as e:
                print(f'Ошибка отправки сообщения через Telegram: {e}')
        await asyncio.sleep(2)

 
def run_camera_process(camera_id, RTSP_URL, bot_token):
    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)
    bot = Bot(token=bot_token)
    loop.run_until_complete(process_camera(camera_id, RTSP_URL, bot))


async def run_bot_and_cameras():
    init_db()
    cameras = get_cameras()  # Получаем список камер
    TOKEN = '7454817299:AAFqDW1tjGy9n5piF6iMUgQNB2E8FLUCL1s'  # Замените на реальный токен

    # Запускаем бота как асинхронную задачу
    bot_task = asyncio.create_task(run_bot())

    processes = []
    for camera_id, url, name in cameras:
        p = Process(target=run_camera_process, args=(camera_id, url, TOKEN))
        processes.append(p)
        p.start()

    for p in processes:
        p.join()

    await bot_task  # Ждём завершения работы бота (если это потребуется)

def main():
    asyncio.run(run_bot_and_cameras())

if __name__ == '__main__':
    main()