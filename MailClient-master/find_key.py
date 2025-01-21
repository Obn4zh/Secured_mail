import os
import psutil
import win32api
import time

def get_all_drives():
    """Функция для получения всех подключенных устройств, включая FAT32 и NTFS."""
    drives = []
    # Проверяем все устройства с файловыми системами
    for partition in psutil.disk_partitions():
        # Игнорируем виртуальные устройства и устройства без файловой системы
        if partition.fstype != '':
            # Получаем метку тома с использованием win32api
            try:
                label = win32api.GetVolumeInformation(partition.device)[0]
            except Exception:
                label = 'Без метки'
            drives.append((partition.device, label, partition.fstype))
    return drives

def find_file_on_drive(drive, filename):
    """Функция для поиска файла на внешнем носителе."""
    for root, dirs, files in os.walk(drive):
        if filename in files:
            # Нормализуем путь, заменяя одиночные слеши на двойные
            normalized_path = os.path.join(root, filename)
            return normalized_path.replace("\\", "\\\\")  # Заменяем одиночные слеши на двойные
    return None

def display_drives(drives):
    """Функция для отображения списка подключенных устройств."""
    if not drives:
        print("Подключенных внешних носителей не найдено.")
        return

    # Выводим список подключенных устройств с метками и типом файловой системы
    print("Выберите внешний носитель:")
    for i, (drive, label, fstype) in enumerate(drives, 1):
        print(f"{i}. {drive} - {label} ({fstype})")

def main():
    while True:
        print("\nСканирование подключенных устройств...")
        drives = get_all_drives()

        display_drives(drives)

        # Запрашиваем номер устройства для выбора
        try:
            drive_choice = int(input("Введите номер устройства (или 0 для выхода): ")) - 1
            if drive_choice == -1:
                break
            if drive_choice < 0 or drive_choice >= len(drives):
                print("Неверный выбор.")
                continue
        except ValueError:
            print("Неверный ввод. Пожалуйста, введите число.")
            continue

        # Запрашиваем имя файла для поиска
        filename = input("Введите имя файла для поиска: ")

        # Поиск файла на выбранном устройстве
        file_path = find_file_on_drive(drives[drive_choice][0], filename)
        if file_path:
            print(f"Файл найден: {file_path}")
        else:
            print("Файл не найден.")

        # Пауза перед новым сканированием
        print("\nПодключите новый носитель или выберите другое устройство.")
        time.sleep(2)  # Ожидание 2 секунды перед повторной проверкой

if __name__ == "__main__":
    main()
