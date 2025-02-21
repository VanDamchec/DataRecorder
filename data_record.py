import subprocess
import threading
import queue
import numpy as np
from matplotlib import pyplot as plt
from matplotlib.animation import FuncAnimation
import psycopg2
import msvcrt
import time

# Объекты базы данных
bd_connect = None
bd_cursor = None
# Параметры
MAX_DATAPOINTS = 1024 * 30  # Максимальное количество точек для хранения
# Создаём начальные массивы данных для четырёх линий
dataplot = np.zeros(MAX_DATAPOINTS)
dataplot2 = np.zeros(MAX_DATAPOINTS)
dataplot3 = np.zeros(MAX_DATAPOINTS)
dataplot4 = np.zeros(MAX_DATAPOINTS)

# Очередь для передачи данных между потоками
data_queue = queue.Queue()
# Переменная для отслеживания предыдущего значения counter
prev_counter = int()

# Флаг для завершения работы программы
stop_flag = threading.Event()

def is_convertible_to_int(s):
    try:
        int(s)
        return True
    except ValueError:
        return False

def bd_init():
    # Параметры подключения к базе данных
    db_config = {
        "dbname": "postgres",
        "user": "postgres",
        "password": "rekb,zrf",
        "host": "localhost",
        "port": "5432"
    }
    connection = None
    cursor = None
    try:
        # Подключение к базе данных
        print("Попытка подключения к базе данных...")
        connection = psycopg2.connect(**db_config)
        cursor = connection.cursor()
        print("Подключение успешно!")
    except Exception as error:
        print(f"Ошибка: {error}")
    return connection, cursor


def table_exists(connection, table_name):
    try:
        cursor = connection.cursor()
        # Запрос к системному каталогу information_schema.tables
        cursor.execute("""
            SELECT EXISTS (
                SELECT FROM information_schema.tables 
                WHERE table_name = %s
            );
        """, (table_name,))
        exists = cursor.fetchone()[0]
        cursor.close()
        return exists
    except Exception as error:
        print(f"Ошибка при проверке существования таблицы: {error}")
        return False


def bd_close(connection, cursor):
    # Закрываем соединение
    if cursor:
        cursor.close()
    if connection:
        connection.close()
        print("\nСоединение закрыто.")


def bd_clear(connection, table_name):
    try:
        cursor = connection.cursor()
        # Используем TRUNCATE для быстрой очистки таблицы
        cursor.execute(f"TRUNCATE TABLE {table_name};")
        print(f"Таблица '{table_name}' успешно очищена с помощью TRUNCATE.")
        # Фиксируем изменения
        connection.commit()
    except Exception as error:
        # В случае ошибки откатываем изменения
        connection.rollback()
        print(f"Ошибка при очистке таблицы: {error}")
    finally:
        cursor.close()


def bd_write_data(connection, table_name, record_date, record_number, record_time, array_1, array_2, array_3, array_4):
    try:
        cursor = connection.cursor()
        #table_name = f"data_records"
        # Создаем таблицу (если она не существует)
        create_table_query = f"""
                CREATE TABLE IF NOT EXISTS {table_name} (
                    id SERIAL PRIMARY KEY,
                    record_date DATE NOT NULL,
                    record_number INTEGER NOT NULL,
                    record_time TIME(3) NOT NULL,
                    array_1 INTEGER[2048],
                    array_2 INTEGER[2048],
                    array_3 INTEGER[2048],
                    array_4 INTEGER[2048]
                );
                """
        cursor.execute(create_table_query)
        # Вставка данных
        insert_query = f"""
                INSERT INTO {table_name} (record_date, record_number, record_time, array_1, array_2, array_3, array_4)
                VALUES (%s, %s, %s, %s, %s, %s, %s);
                """
        cursor.execute(insert_query, (record_date, record_number, record_time, array_1, array_2, array_3, array_4))
        connection.commit()  # Фиксируем изменения
        print("Данные успешно добавлены.")
    except Exception as error:
        # В случае ошибки откатываем изменения
        connection.rollback()
        print(f"Ошибка при добавлении данных в таблицу: {error}")
    finally:
        cursor.close()

def bd_write_mean(connection, table_name, record_date, record_number, record_time, mean1, mean2, mean3, mean4):
    try:
        cursor = connection.cursor()
        #table_name = f"data_records"
        # Создаем таблицу (если она не существует)
        create_table_query = f"""
                CREATE TABLE IF NOT EXISTS {table_name} (
                    id SERIAL PRIMARY KEY,
                    record_date DATE NOT NULL,
                    record_number INTEGER NOT NULL,
                    record_time TIME(3) NOT NULL,
                    mean1 INTEGER,
                    mean2 INTEGER,
                    mean3 INTEGER,
                    mean4 INTEGER
                );
                """
        cursor.execute(create_table_query)
        # Вставка данных
        insert_query = f"""
                INSERT INTO {table_name} (record_date, record_number, record_time, mean1, mean2, mean3, mean4)
                VALUES (%s, %s, %s, %s, %s, %s, %s);
                """
        cursor.execute(insert_query, (record_date, record_number, record_time, mean1, mean2, mean3, mean4))
        connection.commit()  # Фиксируем изменения
        print("Данные успешно добавлены.")
    except Exception as error:
        # В случае ошибки откатываем изменения
        connection.rollback()
        print(f"Ошибка при добавлении данных в таблицу: {error}")
    finally:
        cursor.close()

def read_process_output(process):
    """Функция для чтения вывода процесса и помещения его в очередь."""
    for line in iter(process.stdout.readline, ''):
        if stop_flag.is_set():  # Проверяем флаг завершения
            break
        data_queue.put(line.rstrip('\n'))
    data_queue.put(None)  # Сигнал о завершении работы потока


def save_to_file(show_plot=False):
    """Функция для сохранения данных в файл и обновления массивов dataplot, dataplot2, dataplot3, dataplot4."""
    global dataplot, dataplot2, dataplot3, dataplot4, prev_counter, bd_connect, bd_cursor
    table_name = f"data_records"

    if table_exists(bd_connect, table_name):
        # Очистка таблицы перед записью данных
        bd_clear(bd_connect, table_name)
    else:
        print(f"Таблица '{table_name}' не существует.")

    while not stop_flag.is_set():  # Проверяем флаг завершения
        # Получение данных из очереди
        try:
            data = data_queue.get(timeout=1)  # Таймаут для проверки флага
        except queue.Empty:
            continue
        if data is None:
            break
        data_list = data.split(" ")
        if len(data_list) > 3:
            counter = data_list[2]
            if is_convertible_to_int(counter):
                if int(counter) > prev_counter:
                    prev_counter = int(counter)

                    data_iter = data_list[8].split(";")
                    # Преобразуем данные из data_iter в числа для первой линии
                    new_data1 = [int(x) for x in data_iter[0:-2:4]]
                    # Данные для второй линии
                    new_data2 = [int(x) for x in data_iter[1:-2:4]]
                    # Данные для третьей линии
                    new_data3 = [int(x) for x in data_iter[2:-2:4]]
                    # Данные для четвёртой линии
                    new_data4 = [int(x) for x in data_iter[3::4]]

                    time = f"{data_list[4]}:{data_list[5]}:{data_list[6]}.{data_list[7]}"

                    bd_write_data(bd_connect, "data_records" , "2025-02-07", counter, time,
                                  new_data1, new_data2, new_data3, new_data4)

                    if show_plot:
                        dataplot = np.append(dataplot, new_data1)[-MAX_DATAPOINTS:]
                        dataplot2 = np.append(dataplot2, new_data2)[-MAX_DATAPOINTS:]
                        dataplot3 = np.append(dataplot3, new_data3)[-MAX_DATAPOINTS:]
                        dataplot4 = np.append(dataplot4, new_data4)[-MAX_DATAPOINTS:]

    print("Файл сохранен.")

def update(frame):
    global dataplot, dataplot2, dataplot3, dataplot4
    # Отображаем только последние MAX_DATAPOINTS точек для всех линий
    line.set_data(np.arange(len(dataplot)), dataplot)
    line2.set_data(np.arange(len(dataplot2)), dataplot2)
    line3.set_data(np.arange(len(dataplot3)), dataplot3)
    line4.set_data(np.arange(len(dataplot4)), dataplot4)
    # Обновляем пределы графика по оси X
    ax.set_xlim(0, max(len(dataplot), len(dataplot2), len(dataplot3), len(dataplot4)))
    return line, line2, line3, line4

def check_for_esc():
    """Функция для отслеживания нажатия клавиши Esc."""
    global stop_flag
    while not stop_flag.is_set():
        if msvcrt.kbhit():  # Проверяем, была ли нажата клавиша
            key = msvcrt.getch()
            if key == b'\x1b':  # Код клавиши Esc
                print("\nEsc нажат, завершение программы...")
                stop_flag.set()
                break
        time.sleep(0.1)  # Небольшая пауза, чтобы не перегружать CPU

def main(path_to_file, show_plot=True, handle_esc=True, in_stop_flag=None):
    """
        Основная функция программы.
        :param show_plot: Если True, отображает графики.
        :param handle_esc: Если True, обрабатывает нажатие клавиши Esc.
    """
    global stop_flag   # Используем глобальный флаг
    if in_stop_flag is not None:
        stop_flag = in_stop_flag  # Присваиваем переданный флаг

    global fig, ax, line, line2, line3, line4, ani, bd_connect, bd_cursor
    # Подключаемся к базе данных
    try:
        bd_connect, bd_cursor = bd_init()

    except Exception as error:
        print(f"Ошибка: {error}")
        bd_close(bd_connect, bd_cursor)

    # Запуск внешнего процесса
    process = subprocess.Popen(
        path_to_file,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        universal_newlines=True,
    )

    # Создание потоков
    reading_thread = threading.Thread(target=read_process_output, args=(process,))
    saving_thread = threading.Thread(target=save_to_file, args=(show_plot,))

    # Запуск потоков
    reading_thread.start()
    saving_thread.start()

    if show_plot:
        fig, ax = plt.subplots()
        # Создание четырёх линий на графике
        line, = ax.plot(np.arange(len(dataplot)), dataplot, label="Линия 1", color="blue")
        line2, = ax.plot(np.arange(len(dataplot2)), dataplot2, label="Линия 2", color="red")
        line3, = ax.plot(np.arange(len(dataplot3)), dataplot3, label="Линия 3", color="green")
        line4, = ax.plot(np.arange(len(dataplot4)), dataplot4, label="Линия 4", color="orange")
        # Настройка осей
        ax.set_xlim(0, MAX_DATAPOINTS)
        ax.set_ylim(-100, 8000)  # Установим пределы по оси Y, например, от -1 до 8000
        ax.legend()

        ani = FuncAnimation(fig, update, interval=500, blit=True, cache_frame_data=False)
        plt.show()

    if handle_esc:
        # Запуск потока для обработки нажатия клавиши Esc
        esc_thread = threading.Thread(target=check_for_esc)
        esc_thread.start()

    if not show_plot:
        while not stop_flag.is_set():
            time.sleep(0.01)  # Небольшая пауза, чтобы не перегружать CPU

    # Устанавливаем флаг завершения, если окно графика закрыто
    stop_flag.set()

    # Ожидание завершения потоков
    reading_thread.join()
    saving_thread.join()

    if handle_esc:
        esc_thread.join()

    # Закрываем процесс
    process.terminate()

    # Закрываем базу данных
    bd_close(bd_connect, bd_cursor)
    print("Программа завершена")

if __name__ == "__main__":
    # Если программа запускается как главный модуль
    path = "C:\\Users\\deminid\\source\\repos\\Test\\Release\\Test.exe -data"
    main(path, show_plot=True, handle_esc=False)