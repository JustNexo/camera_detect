import cv2
import os
from ultralytics import YOLO
import tkinter as tk
from tkinter import filedialog
import sys # Для выхода из скрипта

# --- Константы (можно настроить) ---
DEFAULT_CONFIDENCE_THRESHOLD = 0.5 # Порог уверенности для отображения детекций (от 0.0 до 1.0)
BOX_COLOR = (0, 255, 0)  # Цвет рамки (BGR: синий, зеленый, красный)
TEXT_COLOR = (0, 0, 0)   # Цвет текста метки (черный)
TEXT_BG_COLOR = (0, 255, 0) # Цвет фона для текста метки (тот же, что и рамка)
BOX_THICKNESS = 2
FONT_SCALE = 0.6
FONT_FACE = cv2.FONT_HERSHEY_SIMPLEX

def select_file(title="Выберите файл"):
    """Открывает диалоговое окно для выбора файла."""
    root = tk.Tk()
    root.withdraw()  # Скрыть основное окно Tkinter
    root.attributes('-topmost', True) # Поверх других окон
    file_path = filedialog.askopenfilename(title=title)
    root.destroy()
    return file_path

def run_detection():
    """Основная функция для загрузки модели, изображения и выполнения детекции."""
    print("--- Запуск скрипта детекции YOLO ---")

    # --- 1. Выбор файла модели ---
    print("Пожалуйста, выберите файл модели YOLO (.pt)")
    model_path = select_file("Выберите файл модели YOLO (.pt)")

    if not model_path:
        print("Файл модели не выбран. Выход.")
        sys.exit() # Используем sys.exit() для чистого выхода

    if not os.path.exists(model_path):
        print(f"Ошибка: Файл модели не найден по пути: {model_path}")
        sys.exit()
    if not model_path.lower().endswith('.pt'):
         print(f"Предупреждение: Выбранный файл '{os.path.basename(model_path)}' не имеет расширения .pt.")
         # Продолжаем, но предупреждаем пользователя

    print(f"Загрузка модели из: {model_path}")
    try:
        # Загружаем модель YOLO
        model = YOLO(model_path)
        print("Модель успешно загружена.")
        # Получаем имена классов из модели
        class_names = model.names
        print(f"Классы модели: {class_names}")
    except Exception as e:
        print(f"Ошибка при загрузке модели: {e}")
        sys.exit()

    # --- 2. Выбор файла изображения ---
    print("\nПожалуйста, выберите файл изображения для детекции (jpg, png, etc.)")
    image_path = select_file("Выберите файл изображения")

    if not image_path:
        print("Файл изображения не выбран. Выход.")
        sys.exit()

    if not os.path.exists(image_path):
        print(f"Ошибка: Файл изображения не найден по пути: {image_path}")
        sys.exit()

    print(f"Загрузка изображения из: {image_path}")
    try:
        # Загружаем изображение с помощью OpenCV
        image = cv2.imread(image_path)
        if image is None:
            print(f"Ошибка: Не удалось прочитать файл изображения '{image_path}'. Возможно, файл поврежден или имеет неподдерживаемый формат.")
            sys.exit()
        print("Изображение успешно загружено.")
    except Exception as e:
        print(f"Ошибка при чтении изображения: {e}")
        sys.exit()

    # --- 3. Выполнение предсказания ---
    print("\nВыполнение предсказания...")
    try:
        # Запускаем предсказание на изображении
        # stream=False, так как обрабатываем одно изображение
        results = model(source=image, conf=DEFAULT_CONFIDENCE_THRESHOLD, stream=False)
        print("Предсказание завершено.")
    except Exception as e:
        print(f"Ошибка во время выполнения предсказания: {e}")
        sys.exit()

    # --- 4. Обработка результатов и рисование ---
    annotated_image = image.copy() # Создаем копию для рисования, чтобы не изменять оригинал
    detection_count = 0

    # results обычно представляет собой список, даже для одного изображения
    if results and len(results) > 0:
        result = results[0] # Берем результаты для первого (и единственного) изображения
        boxes = result.boxes  # Получаем объект boxes

        for box in boxes:
            detection_count += 1
            # Координаты рамки (xyxy формат)
            x1, y1, x2, y2 = map(int, box.xyxy[0].tolist())
            # Уверенность
            confidence = float(box.conf[0])
            # ID класса
            class_id = int(box.cls[0])
            # Имя класса (если есть в модели, иначе используем ID)
            class_name = class_names.get(class_id, f"ID:{class_id}")

            # Рисуем рамку
            cv2.rectangle(annotated_image, (x1, y1), (x2, y2), BOX_COLOR, BOX_THICKNESS)

            # Формируем текст метки
            label = f"{class_name}: {confidence:.2f}"

            # Рассчитываем размер текста для фона
            (text_width, text_height), baseline = cv2.getTextSize(label, FONT_FACE, FONT_SCALE, BOX_THICKNESS)

            # Рисуем фон для текста (чуть выше рамки)
            cv2.rectangle(annotated_image, (x1, y1 - text_height - baseline), (x1 + text_width, y1), TEXT_BG_COLOR, cv2.FILLED)

            # Рисуем текст метки
            cv2.putText(annotated_image, label, (x1, y1 - baseline // 2), FONT_FACE, FONT_SCALE, TEXT_COLOR, BOX_THICKNESS, cv2.LINE_AA)

    if detection_count > 0:
        print(f"\nНайдено и отрисовано {detection_count} объектов с уверенностью >= {DEFAULT_CONFIDENCE_THRESHOLD}")
    else:
        print(f"\nОбъекты с уверенностью >= {DEFAULT_CONFIDENCE_THRESHOLD} не найдены.")

    # --- 5. Отображение результата ---
    print("Отображение результата. Нажмите любую клавишу в окне изображения, чтобы закрыть.")
    try:
        # Показываем изображение с рамками в окне
        cv2.imshow("YOLO Detection Result", annotated_image)
        # Ждем нажатия любой клавиши бесконечно
        cv2.waitKey(0)
        # Закрываем все окна OpenCV
        cv2.destroyAllWindows()
        print("Окно изображения закрыто.")
    except Exception as e:
        print(f"Ошибка при отображении изображения: {e}")

    print("\n--- Скрипт завершил работу ---")


# --- Точка входа в скрипт ---
if __name__ == "__main__":
    run_detection()