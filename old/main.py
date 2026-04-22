import cv2
import datetime
import numpy as np
from telegram import Bot, Update
from telegram.ext import ApplicationBuilder, CommandHandler, CallbackContext, MessageHandler, filters
import asyncio
import time
from multiprocessing import Process
import sqlite3
from ultralytics import YOLO
import os
import uuid

# --- Импорт ваших модулей ---
# Убедитесь, что bot.py содержит функцию run_bot(), которая запускает бота
#from bot import run_bot
# Функции db.py больше не нужны напрямую в этом файле,
# но сама БД используется

# --- Загрузка модели ---
# !!! Замените 'path/to/your/new_model.pt' на путь к вашей модели !!!
try:
    model = YOLO('best.pt')
    CLASS_NAMES = model.names # Получаем имена классов ['person', 'red uniform']
    print(f"Модель загружена. Имена классов: {CLASS_NAMES}")
except Exception as e:
    print(f"Ошибка загрузки модели YOLO: {e}")
    exit()

# --- Инициализация и работа с БД ---
def init_db():
    conn = sqlite3.connect('users.db')
    c = conn.cursor()
    c.execute('''CREATE TABLE IF NOT EXISTS Colors (
                    id INTEGER PRIMARY KEY,
                    name TEXT UNIQUE NOT NULL)''')
    # !!! Добавьте сюда имена классов ВАШЕЙ модели, если их нет !!!
    try:
        c.execute("INSERT OR IGNORE INTO Colors (name) VALUES (?)", ('person',))
        c.execute("INSERT OR IGNORE INTO Colors (name) VALUES (?)", ('red uniform',))
        print("Записи классов 'person' и 'red uniform' проверены/добавлены в Colors.")
    except sqlite3.Error as e:
        print(f"Ошибка при добавлении классов в Colors: {e}")

    c.execute('''CREATE TABLE IF NOT EXISTS Rules (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    camera_id INTEGER NOT NULL,
                    color_id INTEGER NOT NULL,
                    access_granted INTEGER NOT NULL,
                    FOREIGN KEY (camera_id) REFERENCES Cameras(id),
                    FOREIGN KEY (color_id) REFERENCES Colors(id))''')
    c.execute('''CREATE TABLE IF NOT EXISTS Cameras (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    url TEXT NOT NULL,
                    name TEXT)''')
    c.execute('''CREATE TABLE IF NOT EXISTS users (
                    id INTEGER PRIMARY KEY,
                    name TEXT NULL)''')
    # Используется для отправки сообщений
    c.execute('''CREATE TABLE IF NOT EXISTS users1 (
                    id INTEGER PRIMARY KEY,
                    name TEXT NULL)''')
    conn.commit()
    conn.close()

def add_user(user_id, username):
    conn = sqlite3.connect('users.db')
    c = conn.cursor()
    # Добавляем в обе таблицы или выберите одну для согласованности
    c.execute('INSERT OR IGNORE INTO users (id, name) VALUES (?, ?)', (user_id, username))
    c.execute('INSERT OR IGNORE INTO users1 (id, name) VALUES (?, ?)', (user_id, username))
    conn.commit()
    conn.close()

async def start(update: Update, context: CallbackContext):
    user_id = update.message.chat_id
    username = update.message.from_user.first_name
    add_user(user_id, username)
    await update.message.reply_text(f'Привет, {username}! Вы добавлены в список уведомлений.')

def load_image_from_rtsp(rtsp_url):
    cap = None
    try:
        cap = cv2.VideoCapture(rtsp_url, cv2.CAP_FFMPEG)
        cap.set(cv2.CAP_PROP_OPEN_TIMEOUT_MSEC, 10000)
        cap.set(cv2.CAP_PROP_READ_TIMEOUT_MSEC, 5000)
        if not cap.isOpened():
            print(f"Ошибка: Не удалось открыть RTSP: {rtsp_url}")
            return None
        ret, frame = cap.read()
        if ret:
            return frame
        else:
            print(f"Ошибка чтения кадра с RTSP: {rtsp_url}")
            return None
    except Exception as e:
        print(f"Исключение при работе с RTSP {rtsp_url}: {e}")
        return None
    finally:
        if cap is not None:
            cap.release()

# --- Обновленная функция детекции ---
def detect_objects(frame, conf_threshold=0.5):
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

                if conf >= conf_threshold:
                     # Добавляем все обнаруженные объекты нужной уверенности
                     # Фильтрация по типу ('person', 'red uniform') не нужна здесь,
                     # так как модель обучена только на них (или мы проверяем правила для всех)
                    detected_objects.append(((x1, y1, x2, y2), class_name))

        return detected_objects
    except Exception as e:
        print(f'Ошибка в функции detect_objects: {e}')
        return []

def get_cameras():
    conn = sqlite3.connect('users.db')
    cursor = conn.cursor()
    try:
        cursor.execute("SELECT id, url, name FROM Cameras")
        cameras = cursor.fetchall()
    except sqlite3.OperationalError as e:
        print(f"Ошибка при запросе к таблице Cameras: {e}")
        cameras = []
    finally:
        conn.close()
    return cameras

# --- Обновленная функция проверки доступа ---
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


def save_photo_locally(frame, base_filename="violation"):
    current_date = datetime.datetime.now()
    month = current_date.strftime('%Y-%m')
    day = current_date.strftime('%d')
    date_str = current_date.strftime('%d-%m-%Y_%H-%M-%S')
    directory = os.path.join('images', month, day)
    os.makedirs(directory, exist_ok=True)
    unique_suffix = str(uuid.uuid4().hex)[:8]
    filename = f"{base_filename}_{date_str}_{unique_suffix}.jpg"
    save_path = os.path.join(directory, filename)
    try:
        cv2.imwrite(save_path, frame)
        # print(f"Кадр сохранен: {save_path}")
        return save_path
    except Exception as e:
        print(f"Ошибка сохранения кадра {save_path}: {e}")
        return None

async def send_telegram_message_with_image(bot_token, image_path, message):
    conn = sqlite3.connect('users.db')
    c = conn.cursor()
    try:
        c.execute('SELECT id FROM users1')
        chat_ids = [row[0] for row in c.fetchall()]
    except sqlite3.OperationalError:
        print("Ошибка: Таблица users1 не найдена.")
        chat_ids = []
    conn.close()

    if not chat_ids:
        print("Нет пользователей для отправки сообщения.")
        return
    if not image_path or not os.path.exists(image_path):
         print(f"Ошибка: Файл изображения не найден: {image_path}. Отправка без фото.")
         bot = Bot(token=bot_token)
         for chat_id in chat_ids:
            try:
                await bot.send_message(chat_id=chat_id, text=f"{message}\n(Фото недоступно)")
            except Exception as e:
                print(f'Ошибка отправки текста пользователю {chat_id}: {e}')
         return

    bot = Bot(token=bot_token)
    file_id = None
    try:
        with open(image_path, 'rb') as photo:
            # print(f"Отправка фото первому пользователю {chat_ids[0]}...")
            msg = await bot.send_photo(chat_id=chat_ids[0], photo=photo, caption=message)
            if msg.photo:
                 file_id = msg.photo[-1].file_id
            # print(f"Фото отправлено первому, file_id: {file_id}")
        if file_id and len(chat_ids) > 1:
            # print(f"Пересылка фото остальным {len(chat_ids)-1} пользователям...")
            for chat_id in chat_ids[1:]:
                try:
                    await bot.send_photo(chat_id=chat_id, photo=file_id, caption=message)
                except Exception as e:
                    print(f'Ошибка пересылки фото пользователю {chat_id}: {e}')
    except Exception as e:
        print(f'Ошибка отправки фото первому пользователю {chat_ids[0]}: {e}')
        # Попытка отправить остальным только текст
        for chat_id in chat_ids[1:]:
             try:
                 await bot.send_message(chat_id=chat_id, text=f"{message}\n(Ошибка отправки фото)")
             except Exception as e_text:
                 print(f'Ошибка отправки текста пользователю {chat_id}: {e_text}')


def draw_label(frame, text, pos, color=(0, 0, 255), bg_color=(0,0,0)):
    font_face = cv2.FONT_HERSHEY_SIMPLEX
    scale = 0.8
    thickness = 2
    (text_w, text_h), baseline = cv2.getTextSize(text, font_face, scale, thickness)
    x, y = pos
    cv2.rectangle(frame, (x, y - text_h - baseline), (x + text_w, y + baseline), bg_color, -1)
    cv2.putText(frame, text, (x, y), font_face, scale, color, thickness, cv2.LINE_AA)

def load_image_from_file(image_path):
    """Загружает изображение из локального файла."""
    frame = cv2.imread(image_path)
    if frame is None:
        print(f"Ошибка: Не удалось прочитать изображение: {image_path}")
    return frame
# --- Обновленный процесс обработки камеры ---
async def process_camera(camera_id, RTSP_URL, camera_name):
    #bot = Bot(token=bot_token) # Создаем экземпляр бота для этого процесса
    while True:
        current_hour = datetime.datetime.now().hour
        # Проверка рабочего времени (например, с 8:00 до 16:59)
        # if not (8 <= current_hour < 17):
        #     # print(f"Камера {camera_name or camera_id}: Нерабочее время ({current_hour}:00). Пауза.")
        #     await asyncio.sleep(60 * 5) # Пауза 5 минут в нерабочее время
        #     continue

        # print(f"[{time.strftime('%H:%M:%S')}] Обработка камеры: {camera_name or camera_id} ({RTSP_URL})")
        frame = load_image_from_file("123.jpg")

        if frame is None:
            print(f"[{time.strftime('%H:%M:%S')}] Камера {camera_name or camera_id}: Не удалось получить кадр. Повтор через 10 сек.")
            await asyncio.sleep(10) # Пауза перед повторной попыткой
            continue

        detected_objects = detect_objects(frame)
        violation_detected = False
        violation_details = [] # Для сбора информации о нарушениях

        for box, class_name in detected_objects:
            access_allowed = check_access_rule(camera_id, class_name)

            if not access_allowed:
                violation_detected = True
                x1, y1, x2, y2 = box
                # Рисуем красный прямоугольник для нарушений
                cv2.rectangle(frame, (x1, y1), (x2, y2), (0, 0, 255), 2)
                label = f"{class_name}: FORBIDDEN"
                draw_label(frame, label, (x1, y1 - 5), color=(255, 255, 255), bg_color=(0,0,255))
                violation_details.append(class_name)
            # else:
                # Опционально: рисовать зеленый прямоугольник для разрешенных
                # x1, y1, x2, y2 = box
                # cv2.rectangle(frame, (x1, y1), (x2, y2), (0, 255, 0), 1)
                # label = f"{class_name}: OK"
                # draw_label(frame, label, (x1, y1 - 5), color=(0,0,0), bg_color=(0,255,0))


        if violation_detected:
            print(f"[{time.strftime('%H:%M:%S')}] !!! Нарушение на камере {camera_name or camera_id}: Обнаружены классы {', '.join(set(violation_details))}")
            local_image_path = save_photo_locally(frame, base_filename=f"violation_cam_{camera_id}")
            if local_image_path:
                message = (f"🚨 Обнаружено нарушение на камере: {camera_name or camera_id} ({RTSP_URL})\n"
                           f"Запрещенные объекты: {', '.join(set(violation_details))}\n"
                           f"Время: {datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
                try:
                    # Используем токен напрямую, а не объект bot из процесса
                    await send_telegram_message_with_image(bot_token, local_image_path, message)
                except Exception as e:
                    print(f"Ошибка отправки Telegram сообщения: {e}")
            else:
                print("Ошибка сохранения фото нарушения, сообщение не отправлено.")

        # Пауза между циклами обработки одной камеры
        await asyncio.sleep(2) # Например, 2 секунды

# --- Запуск процессов для камер ---
def run_camera_process(camera_id, RTSP_URL, bot_token):
    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)
    bot = Bot(token=bot_token)
    loop.run_until_complete(process_camera(4, RTSP_URL, bot))


async def run_bot_and_cameras():
    init_db()
    #cameras = get_cameras()  # Получаем список камер
    TOKEN = '7744635665:AAHE4R5hFTxnybSlBE8Fgx2zaoPTirbF3g'  # Замените на реальный токен

    # Запускаем бота как аысинхронную задачу
    #bot_task = asyncio.create_task(run_bot())

    processes = []
    #for camera_id, url, name in cameras:
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