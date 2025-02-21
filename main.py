import sys
import os
import json
from PySide2.QtWidgets import (QApplication, QMainWindow, QWidget, QVBoxLayout, QHBoxLayout,
                               QGridLayout, QLabel, QLineEdit, QPushButton, QTableWidget,
                               QTableWidgetItem, QComboBox, QRadioButton, QCheckBox, QFileDialog,
                               QProgressBar, QTextEdit, QFrame)
from PySide2.QtCore import Qt, QTimer, QThread, Signal
from PySide2.QtGui import QFont
from matplotlib.backends.backend_qt5agg import FigureCanvasQTAgg as FigureCanvas
from matplotlib.figure import Figure
from matplotlib.animation import FuncAnimation
import numpy as np
import data_record
import data_read
import filter_data
from multiprocessing import Process, Event, freeze_support

# Создаем разделяемый флаг завершения
stop_flag = Event()
config_path = "config.json"
exe_path = ""

class Sensor:
    def __init__(self, x_data, line, ax, param_value, label, y_max=20, y_min=0):
        """
        Инициализация класса для управления одним графиком.

        :param x_data: Массив данных для оси X.
        :param line: Линия графика (например, lines4_1).
        :param ax: Ось графика (например, axs[0]).
        :param param_value: Объект для обновления текстового значения.
        :param label: Название параметра для метки.
        """
        self.x = x_data
        self.line = line
        self.ax = ax
        self.param_value = param_value
        self.label = label
        self.y = np.zeros_like(self.x)  # Начальные данные для оси Y
        self.pv = 0

        self.y_max = y_max
        self.y_min = y_min

        self.ax.set_ylim(self.y_min, self.y_max)
        # Округление
        self.digits = 2
        # Коэфициент преобразования АЦП в Вольты
        self.kadc = 0.00125
        # коэффициент масштабирования
        self.k = 1
        # смещение
        self.b = 0
        # коэфициент преобразования единиц измерения
        self.t = 1

    def update_data(self, new_values, transform=True):
        """
        Обновление данных графика.

        :param new_values: Список новых значений для добавления в массив y.
        """
        for value in new_values[::-1]:  # Добавляем новые значения в обратном порядке
            self.y = np.roll(self.y, -1)  # Сдвигаем массив влево
            if transform:
                self.phys_value(value, self.k, self.b, self.t, self.digits)
                self.y[-1] = self.pv  # Добавляем новое значение в конец
            else:
                self.y[-1] = round(value, self.digits)

    def update_graph(self):
        """
        Обновление графика на основе текущих данных.
        """
        self.line.set_ydata(self.y)  # Обновляем данные графика

    def update_ylim(self, min=None, max=None):
        """
        Обновление границ оси Y на основе текущих данных.
        """
        if max and min:
            self.ax.set_ylim(min - max/100, max + max/100)
        else:
            if len(self.y) > 0:
                min_val = np.min(self.y)
                max_val = np.max(self.y)
                range_val = max_val - min_val
                padding = 0.1 * range_val if range_val > 0 else 1  # Добавляем отступ
                self.ax.set_ylim(min_val - padding, max_val + padding)

    def phys_value(self, val, k, b, t, iDigits=2):
        self.pv = round((val * self.kadc * k + b) * t, iDigits)

    def update_label(self):
        """
        Обновление текстовой метки с последним значением.
        """
        if self.param_value is not None:
            self.param_value.setText(f"{self.y[-1]}")


class AnimationThread(QThread):
    update_signal = Signal(list, list)  # Сигнал для передачи данных графика

    def __init__(self, func, interval=50):
        super().__init__()
        self.running = True  # Флаг для управления выполнением потока
        self.func = func  # Функция для генерации данных (sin, cos, tan)
        self.interval = interval  # Интервал обновления в миллисекундах

    def run(self):
        x = np.linspace(0, 20, 100)
        t = 0  # Временной параметр для анимации
        while self.running:
            y = self.func(x + t)  # Обновление данных с использованием функции
            self.update_signal.emit(x.tolist(), y.tolist())  # Передача данных в главный поток
            t += 0.1  # Увеличение времени для анимации
            self.msleep(self.interval)  # Задержка для создания эффекта анимации

    def stop(self):
        self.running = False  # Остановка потока



class MainWindow(QMainWindow):
    def __init__(self, data_record_process=None):
        super().__init__()

        # Считываем данные из кофигурационого файла
        with open(config_path, "r") as f:
            self.config = json.load(f)

        # Подключение к базе данных для считывания
        self.DB_real = data_read.DataRead()
        self.DB_mean = data_read.DataRead()

        self.data_record_process = data_record_process  # Сохраняем ссылку на процесс

        self.setWindowTitle("Регулировка гидродемпферов")
        self.setGeometry(100, 100, 1200, 800)

        # Главный виджет и основной макет
        main_widget = QWidget()
        self.setCentralWidget(main_widget)
        main_layout = QVBoxLayout(main_widget)

        # Верхняя секция
        self.top_layout_init(main_layout)

        # Средняя секция с тремя горизонтальными областями
        self.middle_layout_init(main_layout)

        # Нижняя секция с тремя горизонтальными областями
        self.bottom_layout_init(main_layout)

    def top_layout_init(self, main_layout):
        # Верхняя секция с тремя горизонтальными областями
        top_section = QFrame()
        top_section.setFrameShape(QFrame.StyledPanel)
        top_layout = QHBoxLayout(top_section)
        main_layout.addWidget(top_section, 1)

        # 1) Область ввода данных
        input_data_area = QFrame()
        input_data_area.setFrameShape(QFrame.StyledPanel)
        input_data_layout = QVBoxLayout(input_data_area)
        top_layout.addWidget(input_data_area, 2)

        labels = ["Опознавательный знак", "Заводской номер", "Дата испытания", "Исполнитель", "Контр. мастер"]
        for label in labels:
            lbl = QLabel(label)
            font = QFont()
            font.setPointSize(14)
            lbl.setFont(font)
            input_data_layout.addWidget(lbl)
            if label == "Дата испытания":
                combo = QComboBox()
                combo.addItems(["21.01.2018"])
                input_data_layout.addWidget(combo)
            else:
                line_edit = QLineEdit()
                input_data_layout.addWidget(line_edit)

        # 2) Таблица с параметрами испытаний
        table_area = QFrame()
        table_area.setFrameShape(QFrame.StyledPanel)
        table_layout = QVBoxLayout(table_area)
        top_layout.addWidget(table_area, 3)

        table = QTableWidget(10, 4)
        table.setHorizontalHeaderLabels(["Наименование", "Требования ТУ", "Факт."])
        table_layout.addWidget(table)

        # 3) Область графиков (только синусоида)
        graph_area = QFrame()
        graph_area.setFrameShape(QFrame.StyledPanel)
        graph_layout = QVBoxLayout(graph_area)
        graph_layout.setContentsMargins(0, 0, 0, 0)  # Убираем отступы
        top_layout.addWidget(graph_area, 3)

        # График 1: Синусоида
        self.graph_canvas1 = FigureCanvas(Figure(figsize=(5, 3)))
        self.ax1 = self.graph_canvas1.figure.subplots()
        self.x1 = np.linspace(0, 20, 10000)
        self.y1 = np.sin(self.x1)
        self.line1, = self.ax1.plot(self.x1, self.y1)
        # Убираем подписи осей
        self.ax1.set_xlabel("")
        self.ax1.set_ylabel("")
        # Убираем лишние поля вокруг графика
        self.graph_canvas1.figure.tight_layout()
        self.graph_canvas1.figure.subplots_adjust(left=0.1, right=1, top=1, bottom=0.1)
        # Растягиваем график на всю доступную область
        graph_layout.addWidget(self.graph_canvas1, stretch=1)
        graph_layout.setContentsMargins(0, 0, 0, 0)  # Убираем отступы
        self.ax1.grid(True)
        graph_layout.addWidget(self.graph_canvas1)

        # Анимация с использованием FuncAnimation
        self.t1 = 0
        self.anim1 = FuncAnimation(
            self.graph_canvas1.figure,
            self.update_graph1,
            interval=1000,  # Интервал обновления в миллисекундах
            cache_frame_data=False
        )

    def middle_layout_init(self, main_layout):
        middle_section = QFrame()
        middle_section.setFrameShape(QFrame.StyledPanel)
        middle_layout = QHBoxLayout(middle_section)
        main_layout.addWidget(middle_section, 2)

        # 1) Область графика 1 (косинусоида)
        graph_area1 = QFrame()
        graph_area1.setFrameShape(QFrame.StyledPanel)
        graph_layout1 = QVBoxLayout(graph_area1)
        graph_layout1.setContentsMargins(0, 0, 0, 0)  # Убираем отступы
        middle_layout.addWidget(graph_area1, 1)

        self.graph_canvas2 = FigureCanvas(Figure(figsize=(5, 3)))
        self.ax2 = self.graph_canvas2.figure.subplots()
        # Инициализация данных графика
        self.x2 = np.arange(10000)  # Ось X (например, индексы массива)
        self.y2 = np.zeros(10000)  # Ось Y (начальные данные)
        self.line2, = self.ax2.plot(self.x2, self.y2)
        self.ax2.set_ylim(-8200, 8200)

        # Убираем подписи осей
        self.ax2.set_xlabel("")
        self.ax2.set_ylabel("")
        # Убираем лишние поля вокруг графика
        self.graph_canvas2.figure.tight_layout()
        self.graph_canvas2.figure.subplots_adjust(left=0.1, right=1, top=1, bottom=0.1)
        # Растягиваем график на всю доступную область
        graph_layout1.addWidget(self.graph_canvas2, stretch=1)
        graph_layout1.setContentsMargins(0, 0, 0, 0)  # Убираем отступы
        self.ax2.grid(True)
        graph_layout1.addWidget(self.graph_canvas2)

        # Анимация с использованием FuncAnimation
        self.t2 = 0
        self.anim2 = FuncAnimation(
            self.graph_canvas2.figure,
            self.update_graph2,
            interval=100,
            cache_frame_data=False
        )

        # 2) Область графика 2 (4 горизонтальных графика)
        graph_area2 = QFrame()
        graph_area2.setFrameShape(QFrame.StyledPanel)
        graph_area2.setStyleSheet("background-color: white;")  # Устанавливаем белый фон
        graph_layout2 = QVBoxLayout(graph_area2)
        graph_layout2.setContentsMargins(0, 0, 0, 0)  # Убираем отступы
        middle_layout.addWidget(graph_area2, 2)

        # Добавляем подпись сверху области с 4 графиками
        graph_title_label = QLabel("Графики")
        graph_title_label.setAlignment(Qt.AlignCenter)  # Выравниваем текст по центру
        graph_title_font = QFont()
        graph_title_font.setPointSize(12)  # Устанавливаем размер шрифта
        graph_title_label.setFont(graph_title_font)
        graph_layout2.addWidget(graph_title_label)  # Добавляем подпись в макет

        # Создаем FigureCanvas с 4 подграфиками
        self.graph_canvas4 = FigureCanvas(Figure(figsize=(5, 6)))  # Увеличиваем высоту для 4 графиков
        self.axs = self.graph_canvas4.figure.subplots(4, 1, sharex=True)  # 4 горизонтальных графика

        # Генерация данных для графиков
        self.x4 = np.linspace(0, 20, 100)
        self.y4_1 = np.empty(len(self.x4))
        self.y4_2 = np.empty(len(self.x4))
        self.y4_3 = np.empty(len(self.x4))
        self.y4_4 = np.empty(len(self.x4))

        # Отрисовка графиков
        self.lines4_1, = self.axs[0].plot(self.x4, self.y4_1, label="Усилие, кгс")
        self.lines4_2, = self.axs[1].plot(self.x4, self.y4_2, label="Ход штока, мм")
        self.lines4_3, = self.axs[2].plot(self.x4, self.y4_3, label="Температура, град")
        self.lines4_4, = self.axs[3].plot(self.x4, self.y4_4, label="Обороты, об/мин")

        lines4 = [self.lines4_1, self.lines4_2, self.lines4_3, self.lines4_4]  # Линии графиков
        axs = [self.axs[0], self.axs[1], self.axs[2], self.axs[3]]  # Оси графиков

        # Настройка осей
        for i, ax in enumerate(self.axs):
            ax.grid(True)
            ax.legend(loc="upper left")  # Добавляем легенду

        # Добавляем подпись оси X для нижнего графика
        self.axs[3].set_xlabel("Время (с)")

        # Убираем лишние поля вокруг графиков
        self.graph_canvas4.figure.tight_layout()
        self.graph_canvas4.figure.subplots_adjust(left=0.05, right=1, top=1, bottom=0.1)

        # Растягиваем график на всю доступную область
        graph_layout2.addWidget(self.graph_canvas4, stretch=1)

        # Анимация для 4 графиков
        self.t4 = 0
        self.anim4 = FuncAnimation(
            self.graph_canvas4.figure,
            self.update_graph4,
            interval=1000,  # Интервал обновления в миллисекундах
            cache_frame_data=False
        )

        # 3) Область параметров
        parameters_area = QFrame()
        parameters_area.setFrameShape(QFrame.StyledPanel)
        parameters_layout = QVBoxLayout(parameters_area)
        middle_layout.addWidget(parameters_area, 1)

        # Создаем словарь для хранения меток param_value
        self.param_values = {}
        self.noise_values = {}  # Словарь для хранения меток значений "Процент шума"
        self.parameter_labels = ["Усилие на штоке,\n кгс:", "Ход штока,\n мм:", "Температура,\n град:",
                                 "Обороты эксцентрика,\n об/мин:"]
        for label in self.parameter_labels:
            param_layout = QHBoxLayout()
            param_lbl = QLabel(label)
            param_font = QFont()
            param_font.setPointSize(12)  # Устанавливаем размер шрифта 12
            param_lbl.setFont(param_font)
            # Выравнивание текста по центру
            param_lbl.setAlignment(Qt.AlignCenter)
            # Установка фиксированной ширины метки (например, 150 пикселей)
            param_lbl.setFixedWidth(150)
            # Включение переноса слов
            param_lbl.setWordWrap(True)

            # Создаем метку для значения
            param_value = QLabel("0")
            param_value.setAlignment(Qt.AlignCenter)
            param_value.setStyleSheet("""
                        font-size: 60px; 
                        color: blue;
                        background-color: white; 
                        border: 1px solid black; 
                        padding: 5px;
                        margin: 15px;
                    """)
            # Добавляем метку в словарь
            self.param_values[label] = param_value

            param_layout.addWidget(param_lbl)
            param_layout.addWidget(param_value)
            parameters_layout.addLayout(param_layout)

            # Добавляем "Процент шума" для первых двух параметров
            if label in ["Усилие на штоке,\n кгс:"]:
                noise_layout = QHBoxLayout()

                # Метка "Процент шума"
                noise_lbl = QLabel("Процент шума:")
                noise_lbl.setFont(param_font)
                noise_lbl.setAlignment(Qt.AlignCenter)
                noise_lbl.setFixedWidth(150)
                noise_lbl.setWordWrap(True)

                # Метка для значения "Процент шума"
                noise_value = QLabel("0%")
                noise_value.setAlignment(Qt.AlignCenter)
                noise_value.setStyleSheet("""
                            font-size: 20px; 
                            color: green;
                            background-color: white; 
                            border: 1px solid black; 
                            padding: 5px;
                            margin: 20px;
                        """)
                # Добавляем метку в словарь
                self.noise_values[label] = noise_value

                noise_layout.addWidget(noise_lbl)
                noise_layout.addWidget(noise_value)
                parameters_layout.addLayout(noise_layout)

        param_values = [self.param_values.get(label) for label in self.parameter_labels]  # Текстовые метки
        labels = ["Усилие, кгс", "Ход штока, мм", "Температура, град", "Обороты, об/мин"]  # Названия параметров

        # Создаем экземпляры класса для каждого датчика
        self.Sensors = [0, 0, 0, 0]
        # Датчик силы
        self.Sensors[0] = Sensor(self.x4, lines4[0], axs[0], param_values[0], labels[0],
                                 y_max=self.config["graph_limits"]["force"]["y_max"])
        self.Sensors[0].k = self.config["sensor_coefficients"]["force"]["k"]
        self.Sensors[0].b = self.config["sensor_coefficients"]["force"]["b"]
        self.Sensors[0].t = self.config["sensor_coefficients"]["force"]["t"]
        self.Sensors[0].digits = self.config["sensor_coefficients"]["force"]["iDigits"]

        # Датчик перемещения
        self.Sensors[1] = Sensor(self.x4, lines4[1], axs[1], param_values[1], labels[1],
                                 y_max=self.config["graph_limits"]["displacement"]["y_max"])
        self.Sensors[1].k = self.config["sensor_coefficients"]["displacement"]["k"]
        self.Sensors[1].b = self.config["sensor_coefficients"]["displacement"]["b"]
        self.Sensors[1].t = self.config["sensor_coefficients"]["displacement"]["t"]
        self.Sensors[1].digits = self.config["sensor_coefficients"]["displacement"]["iDigits"]
        # Датчик температуры
        self.Sensors[2] = Sensor(self.x4, lines4[2], axs[2], param_values[2], labels[2],
                                 y_max=self.config["graph_limits"]["temperature"]["y_max"])
        self.Sensors[2].k = self.config["sensor_coefficients"]["temperature"]["k"]
        self.Sensors[2].b = self.config["sensor_coefficients"]["temperature"]["b"]
        self.Sensors[2].t = self.config["sensor_coefficients"]["temperature"]["t"]
        self.Sensors[2].digits = self.config["sensor_coefficients"]["temperature"]["iDigits"]
        # Датчик оборотов
        self.Sensors[3] = Sensor(self.x4, lines4[3], axs[3], param_values[3], labels[3],
                                 y_max=self.config["graph_limits"]["rpm"]["y_max"])
        self.Sensors[3].k = self.config["sensor_coefficients"]["rpm"]["k"]
        self.Sensors[3].b = self.config["sensor_coefficients"]["rpm"]["b"]
        self.Sensors[3].t = self.config["sensor_coefficients"]["rpm"]["t"]
        self.Sensors[3].digits = self.config["sensor_coefficients"]["rpm"]["iDigits"]

    def bottom_layout_init(self, main_layout):
        bottom_section = QFrame()
        bottom_section.setFrameShape(QFrame.StyledPanel)
        bottom_layout = QHBoxLayout(bottom_section)
        main_layout.addWidget(bottom_section)

        # 1) Выбор параметров для вывода графика
        param_selection_area = QFrame()
        param_selection_area.setFrameShape(QFrame.StyledPanel)
        param_selection_layout = QVBoxLayout(param_selection_area)
        bottom_layout.addWidget(param_selection_area)

        radio_buttons = ["Сила", "Перемещение", "Статика (сила, перемещение)", "Динамика (сила, перемещение)"]
        for rb in radio_buttons:
            radio_button = QRadioButton(rb)
            radio_font = QFont()
            radio_font.setPointSize(12)  # Устанавливаем размер шрифта 12
            radio_button.setFont(radio_font)
            param_selection_layout.addWidget(radio_button)

        # 2) Настройки сохранения данных
        save_settings_area = QFrame()
        save_settings_area.setFrameShape(QFrame.StyledPanel)
        save_settings_layout = QVBoxLayout(save_settings_area)
        bottom_layout.addWidget(save_settings_area)

        save_label = QLabel("Настройки сохранения данных в файл:")
        save_font = QFont()
        save_font.setPointSize(12)  # Устанавливаем размер шрифта 12
        save_label.setFont(save_font)
        save_settings_layout.addWidget(save_label)

        save_button = QPushButton("Сохранить")
        save_settings_layout.addWidget(save_button)

        # 3) Вывод отчета
        report_output_area = QFrame()
        report_output_area.setFrameShape(QFrame.StyledPanel)
        report_output_layout = QVBoxLayout(report_output_area)
        bottom_layout.addWidget(report_output_area)

        report_text = QTextEdit()
        report_output_layout.addWidget(report_text)

    def update_graph1(self, frame):
        """Обновление данных первого графика."""

        return self.line1,

    def update_graph2(self, frame):
        """Обновление данных второго графика."""
        # Получаем последние 2 записи из базы данных
        data = self.DB_real.bd_read_last("data_records", 4, True)
        if data:
            # Извлекаем массив array_1 из записи
            array_1 = filter_data.data_export(data, 1)
            # Определяем количество новых значений
            new_values_count = len(array_1)
            # Обновляем данные графика: сдвигаем старые значения влево и добавляем новые
            self.y2 = np.concatenate((self.y2[new_values_count:], array_1))
            # Обновляем данные графика
            self.line2.set_ydata(self.y2)
        return self.line2,

    def update_graph4(self, frame):
        frame = 50
        fs = 1024 * frame  # Частота дискретизации
        frequency = 5 * frame  # Частота основного сигнала

        # Чтение данных из базы данных
        data = self.DB_real.bd_read_last("data_records", frame, False)
        if not data:
            return tuple(graph.line for graph in self.Sensors)

        # Обработка данных для подсчета оборотов
        count_impulse, index_null, pulse_durations, rpm_values = filter_data.count_turn(data, channel=4, min_count=6)
        print(f"Кол-во: {count_impulse}, Индексы: {index_null}, Размер: {pulse_durations}, Обороты: {rpm_values}")

        # Фильтрация данных для усилия и перемещения
        def process_channel(channel, negative_data):
            return filter_data.filter_data(
                data=data,
                channel=channel,
                freq=frequency,
                fs=fs,
                only_filter=False,
                negative_data=negative_data,
                index_null=index_null
            )

        (noisy_strength, filtered_strength, _, strength_ampl, _, noise_strength_perc) = process_channel(1, True)
        (noisy_move, filtered_move, _, move_ampl, _, noise_move_perc) = process_channel(2, False)

        # Обновление значения "Процент шума" для усилия
        self.noise_values["Усилие на штоке,\n кгс:"].setText(f"{noise_strength_perc:.2f}%")

        # Подготовка значений для графиков
        mean_values = [
            [strength_ampl],  # Усилие
            [move_ampl],  # Перемещение
            [np.mean(filter_data.data_export(data, 3))],  # Температура
            [rpm_values]  # Обороты
        ]

        # Обновление графиков
        for i, mean_value in enumerate(mean_values):
            transform = i != 3  # Для оборотов (индекс 3) transform=False
            self.Sensors[i].update_data(mean_value, transform=transform)
            self.Sensors[i].update_graph()
            # self.Sensors[i].update_ylim()  # Раскомментировать, если нужно обновлять границы оси Y
            self.Sensors[i].update_label()

        return tuple(graph.line for graph in self.Sensors)

    def closeEvent(self, event):
        self.DB_mean.bd_close()
        self.DB_real.bd_close()

        """Остановка анимации при закрытии окна."""
        self.anim1._stop()
        self.anim2._stop()
        self.anim4._stop()

        if self.data_record_process and self.data_record_process.is_alive():
            print("Завершение процесса data_record...")
            stop_flag.set()  # Устанавливаем флаг завершения
            self.data_record_process.join()  # Дождаться завершения процесса
        event.accept()  # Разрешить закрытие окна



if __name__ == "__main__":
    freeze_support()

    # Считываем данные из кофигурационого файла
    with open(config_path, "r") as f:
        config = json.load(f)
        exe_path = config["config_exe"]["path"]
        print(exe_path)

    # Создаем процесс для выполнения функции main из data_record
    data_record_process = Process(target=data_record.main, args=(exe_path, False, False, stop_flag))

    # Запускаем процесс
    data_record_process.start()

    # Создаем и запускаем GUI
    app = QApplication(sys.argv)
    window = MainWindow(data_record_process)  # Передаем процесс в конструктор
    window.show()
    sys.exit(app.exec_())


