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
import math
import threading



DEFAULT_PIXEL_THRESHOLD_NEAR_FENCE = 10

try:
    model = YOLO('best.pt')
    CLASS_NAMES = model.names # Получаем имена классов ['person', 'red uniform']
    print(f"Модель загружена. Имена классов: {CLASS_NAMES}")
except Exception as e:
    print(f"Ошибка загрузки модели YOLO: {e}")
    exit()

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

def get_borders(camera_id):
    zones = []
    try:
        conn = sqlite3.connect('users.db')
        cursor = conn.cursor()
        cursor.execute("SELECT x1, y1, x2, y2, pixel_threshold FROM Borders WHERE camera_id = ?", (camera_id,))
        zones = cursor.fetchall()
        conn.close()
    except sqlite3.Error as e:
        print(f"Ошибка БД при получении зон ограждения для камеры {camera_id}: {e}")
    return zones

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

def detect_objects(frame, conf_threshold=0.7):
    detected_objects = []
    try:
        results = model(frame, verbose=False)
        for result in results:
            boxes = result.boxes
            for box in boxes:
                x1, y1, x2, y2 = map(int, box.xyxy[0])
                conf = float(box.conf[0])
                cls_id = int(box.cls[0])
                class_name = CLASS_NAMES.get(cls_id, f"unknown_id_{cls_id}") # Безопасное получение имени
                print(f"Detection: Class {class_name}, Confidence {conf}, Box {box}")

                if conf >= conf_threshold:
                     # Добавляем все обнаруженные объекты нужной уверенности
                     # Фильтрация по типу ('person', 'red uniform') не нужна здесь,
                     # так как модель обучена только на них (или мы проверяем правила для всех)
                    detected_objects.append(((x1, y1, x2, y2), class_name))

        return detected_objects
    except Exception as e:
        print(f'Ошибка в функции detect_objects: {e}')
        return []

def check_access_rule(camera_id, detected_class_name):
    """
    Проверяет доступ на основе политики камеры (определяемой по правилам для ID 2, 6, 7)
    и обнаруженного класса ('person' или 'red uniform').

    - Если на камере запрещен хотя бы один из ID (2, 6, 7), то это "зона БЕЗ красного".
      В ней разрешен только класс 'person'.
    - Если на камере нет запретов для ID (2, 6, 7), но есть разрешение хотя бы для одного из них,
      то это "зона С красным". В ней разрешен только класс 'red uniform'.
    - Если на камере нет правил для ID (2, 6, 7), по умолчанию считается "зоной БЕЗ красного".

    Возвращает True если доступ разрешен, False если запрещен.
    """
    conn = sqlite3.connect('users.db')
    cursor = conn.cursor()

    # ID цветов, которые определяют политику "красного"
    policy_defining_color_ids = (2, 6, 7)
    placeholders = ','.join('?' * len(policy_defining_color_ids)) # Создаст строку '(?,?,?)'

    is_red_forbidden_on_camera = False
    is_red_allowed_on_camera = False

    try:
        # 1. Проверяем, есть ли ЗАПРЕТ на красный (хотя бы одно правило access_granted=0 для ID 2,6,7)
        cursor.execute(f"""
            SELECT 1 FROM Rules
            WHERE camera_id = ? AND color_id IN ({placeholders}) AND access_granted = 0
            LIMIT 1
        """, (camera_id, *policy_defining_color_ids))
        if cursor.fetchone():
            is_red_forbidden_on_camera = True

        # 2. Если запрета нет, проверяем, есть ли ЯВНОЕ РАЗРЕШЕНИЕ на красный (хотя бы одно правило access_granted=1 для ID 2,6,7)
        if not is_red_forbidden_on_camera:
            cursor.execute(f"""
                SELECT 1 FROM Rules
                WHERE camera_id = ? AND color_id IN ({placeholders}) AND access_granted = 1
                LIMIT 1
            """, (camera_id, *policy_defining_color_ids))
            if cursor.fetchone():
                is_red_allowed_on_camera = True

    except sqlite3.Error as e:
        print(f"Ошибка БД при определении политики камеры {camera_id} по ID {policy_defining_color_ids}: {e}")
        # В случае ошибки считаем зону "без красного" (безопаснее)
        is_red_forbidden_on_camera = True
    finally:
        conn.close()

    # Определяем тип зоны
    # Приоритет у запрета. Если нет запрета, но есть разрешение -> зона с красным. Иначе -> зона без красного.
    is_no_red_zone = is_red_forbidden_on_camera or (not is_red_forbidden_on_camera and not is_red_allowed_on_camera)
    # is_red_uniform_zone = not is_no_red_zone # Это те случаи, когда is_red_allowed_on_camera == True и is_red_forbidden_on_camera == False

    # Применяем логику доступа в зависимости от типа зоны и обнаруженного класса
    access_granted = False
    if is_no_red_zone:
        # Зона БЕЗ красного: разрешен только 'person'
        if detected_class_name == 'Person':
            access_granted = True
        # else: 'red uniform' запрещен
    else: # Это зона С красным (is_red_uniform_zone)
        # Зона С красным: разрешен только 'red uniform'
        if detected_class_name == 'Red uniform':
            access_granted = True
        # else: 'person' запрещен

    # print(f"Камера {camera_id}: Политика={('БЕЗ красного' if is_no_red_zone else 'С красным')}, Класс='{detected_class_name}', Доступ={access_granted}")
    return access_granted

def get_color_namee(frame, person_segments):
    # Преобразуем изображение в цветовое пространство HSV
    hsv_frame = cv2.cvtColor(frame, cv2.COLOR_BGR2HSV)
    
    # Создаем черную маску размером с исходное изображение
    contour_mask = np.zeros(frame.shape[:2], dtype=np.uint8)
    
    # Преобразуем сегменты в формат, который понимает OpenCV
    for segment in person_segments:
        # Преобразуем список координат сегмента в целочисленный numpy массив
        segment = np.array(segment, dtype=np.int32)
        # Рисуем контур на маске
        cv2.drawContours(contour_mask, [segment], -1, 255, thickness=cv2.FILLED)
    
    # Применяем маску к изображению
    masked_frame = cv2.bitwise_and(hsv_frame, hsv_frame, mask=contour_mask)
    
    # Определяем границы для красного цвета в HSV
    lower_red_1 = np.array([0, 60, 40])    # Первый диапазон красного
    upper_red_1 = np.array([6, 255, 255])

    lower_red_2 = np.array([165, 60, 40])  # Второй диапазон красного
    upper_red_2 = np.array([180, 255, 255])

    # Создаем маски для каждого диапазона красного цвета
    mask1 = cv2.inRange(masked_frame, lower_red_1, upper_red_1)
    mask2 = cv2.inRange(masked_frame, lower_red_2, upper_red_2)

    # Объединяем маски для получения полной области красного
    mask = mask1 + mask2

    # Подсчитываем долю пикселей, попавших в маску
    mask_pixels = cv2.countNonZero(mask)
    total_pixels = cv2.countNonZero(contour_mask)

    if total_pixels == 0:
        return "Контур не найден"
        
    ratio = mask_pixels / total_pixels
    
    # Условие для определения, достаточно ли цвета
    if ratio > 0.20:  # Есл  и доля больше 20%, считаем, что цвет найден
        return "Розовый"  # Возвращаем имя цвета, если он найден
    
    return "Запрещенный цвет"
def point_segment_distance(px, py, x1, y1, x2, y2):
    line_magn = math.dist((x1, y1), (x2, y2))
    if line_magn < 1e-6: # Avoid division by zero if segment is a point
        return math.dist((px, py), (x1, y1))

    u1 = (((px - x1) * (x2 - x1)) + ((py - y1) * (y2 - y1)))
    u = u1 / (line_magn * line_magn)

    if u < 0.0 or u > 1.0:
        # Closest point does not fall on the line segment, find distance to endpoints
        dist1 = math.dist((px, py), (x1, y1))
        dist2 = math.dist((px, py), (x2, y2))
        return min(dist1, dist2)
    else:
        # Closest point falls on the line segment, find perpendicular distance
        ix = x1 + u * (x2 - x1)
        iy = y1 + u * (y2 - y1)
        return math.dist((px, py), (ix, iy))
    
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
            msg = await Bot("7744635665:AAHE4R5hFTxnybSlBE8Fgx2zaoPi0rbF3g").send_photo(chat_id=chat_ids[0], photo=photo, caption=message)
            file_id = msg.photo[-1].file_id  

        # Пересылаем фото остальным пользователям, используя file_id
        for chat_id in chat_ids[1:]:
            try:
                await Bot("7744635665:AAHE4R5hFTxnybSlBE8Fgx2zaoPTi0rb3g").send_photo(chat_id=chat_id, photo=file_id, caption='Посещение с запрещенным цветом одежды')
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

fence_zone_cache = {}
fence_cache_lock = threading.Lock()

async def process_camera(camera_id, RTSP_URL, bot):
    global fence_zone_cache
    with fence_cache_lock:
        if camera_id not in fence_zone_cache:
             print(f"Загрузка зон ограждения для камеры {camera_id}")
             fence_zone_cache[camera_id] = get_borders(camera_id)
             print(f"Загружено {len(fence_zone_cache[camera_id])} зон для камеры {camera_id}")

    current_fences = fence_zone_cache.get(camera_id, [])

    while True:
        current_hour = datetime.datetime.now().hour
        if current_hour < 8 or current_hour >= 20:
            await asyncio.sleep(60)  # Ждем 1 минуту перед следующей проверкой
            continue
        print(f"[{time.strftime('%Y-%m-%d %H:%M:%S')}] Обработка камеры: {RTSP_URL}")

        frame = load_image_from_file("123.jpg")
        await asyncio.sleep(3)
        if frame is None:
            continue

        detected_objects = detect_objects(frame)
        violation_detected = False
        fence_violation_detected = False
        violation_details = [] # Для сбора информации о нарушениях

        for box, class_name in detected_objects:
            access_allowed = check_access_rule(camera_id, class_name)
            label_texts = []
            box_color = (0, 0, 255)
            x1, y1, x2, y2 = box
            if not access_allowed:
                violation_detected = True
                box_color = (0, 0, 255) # Red
                label = f"Запрещенный цвет"
                label_texts.append("Запрещенный цвет")
                violation_details.append(class_name)
            person_px = int((x1 + x2) / 2)
            person_py = y2 # Bottom center

            for fx1, fy1, fx2, fy2, threshold in current_fences:
                distance = point_segment_distance(person_px, person_py, fx1, fy1, fx2, fy2)
                effective_threshold = threshold if threshold > 0 else DEFAULT_PIXEL_THRESHOLD_NEAR_FENCE

                if distance < effective_threshold:
                    fence_violation_detected = True
                    is_person_near_fence = True
                    if not violation_detected: # Don't overwrite red
                        box_color = (0, 165, 255) # Orange for fence proximity
                    
                    label_texts.append(f"Близко к ограждению!")
                    break # One fence violation is enough for this person
            
            cv2.rectangle(frame, (x1, y1), (x2, y2), box_color, 2)
            label_y_offset = 10
            for text in label_texts:
                 draw_label(frame, text, (x1, y1 - label_y_offset), (255, 255, 255))
                 label_y_offset += 20 # Move next label up
        if violation_detected or fence_violation_detected:
            try:
                local_image_path = 'result_image.png'
                cv2.imwrite(local_image_path, frame)            
                await send_telegram_message_with_image(bot, local_image_path, f'Посещение с запрещенным цветом одежды \n id: {camera_id}')
  
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
    #cameras = get_cameras()  # Получаем список камер
    TOKEN = '7744635665:AAHE4R5hFTxnybSlBE8Fgx2zaoPTi0rb3g'  # Замените на реальный токен

    # Запускаем бота как аысинхронную задачу
    #bot_task = asyncio.create_task(run_bot())

    processes = []
   
    p = Process(target=run_camera_process, args=(4, "url", TOKEN))
    processes.append(p)
    p.start()

    for p in processes:
        p.join()

    #await bot_task  # Ждём завершения работы бота (если это потребуется)

def main():
    asyncio.run(run_bot_and_cameras())

if __name__ == '__main__':
    main()