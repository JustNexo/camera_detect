from ultralytics import YOLO
import torch
import multiprocessing
def main():
    # Проверка доступности GPU
    print(f"CUDA доступно: {torch.cuda.is_available()}")
    print(f"Количество GPU: {torch.cuda.device_count()}")
    print(f"Текущее устройство: {torch.cuda.current_device()}")
    print(f"Имя устройства: {torch.cuda.get_device_name(0)}")  # Должно показать 3060 Ti

    # Инициализация модели на GPU
    model = YOLO('yolo11s.pt')

    # В обучении добавьте параметр device
    model.train(
        data="E:/ai/camera detect own model/new_model/data.yaml",
        epochs=100,
        imgsz=640,
        batch=16,  # Можно увеличить батч-сайз
        device='cuda',  # Использовать первую GPU
        name="employees", # Использовать FP16 для ускорения
    )
if __name__ == '__main__':
    multiprocessing.freeze_support()  # Только для Windows
    main()