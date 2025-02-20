import numpy as np
from scipy.special.cython_special import eval_sh_legendre

import data_read
import matplotlib.pyplot as plt
from scipy.signal import butter, filtfilt
import time

DB = data_read.DataRead()

# Генерация тестового сигнала
np.random.seed(42)

frame = 20
fs = 2045 * frame  # Частота дискретизации
t = np.linspace(0, fs, fs, endpoint=False)  # Временной массив
frequency = 5 * frame  # Частота основного сигнала
amplitude = 1  # Амплитуда основного сигнала
noise_level = 0.5  # Уровень шума

# signal = amplitude * np.sin(2 * np.pi * frequency * t)  # Основной сигнал
# noise = noise_level * np.random.normal(size=t.shape)  # Шум
# noisy_signal = signal + noise  # Сигнал с шумом

noisy_signal = []
filtered_signal = []
noise_estimated = []

# 1. Фильтрация для выделения основной гармоники
def lowpass_filter(data, cutoff, fs, order=5):
    # Вычисление параметров фильтра
    nyquist = 0.5 * fs
    normal_cutoff = cutoff / nyquist
    b, a = butter(order, normal_cutoff, btype='low', analog=False)
    # Применение фильтра
    filtered_data = filtfilt(b, a, data)
    # Преобразование результата в целочисленный тип (int)
    return filtered_data.astype(int)

# Экспорт данных из базы
def data_export(data, channel=1):
    if channel < 1:
        channel = 1
    elif channel > 4:
        channel = 4

    if not data:
        return np.array([])
    # Извлекаем массив данных из записи
    data_frames = np.array([row[3 + channel] for row in data[::-1]])
    return data_frames.ravel()

#Нахождение индексов интервалов
def find_intervals(above_threshold, min_count):
    start_index = None
    n = 0

    for i, value in enumerate(above_threshold):
        if value:
            if start_index is None:  # Начало нового интервала
                start_index = i
        else:
            if start_index is not None:  # Конец интервала
                yield [start_index, i]
                n += 1
                start_index = None

        if n >= min_count:  # Досрочное завершение, если найдено достаточно интервалов
            break

    # Если последний интервал доходит до конца массива
    if start_index is not None and n < min_count:
        yield [start_index, len(above_threshold)]


# Подсчет оборотов
def count_turn(data, channel = 4, threshold = 5000, sampling_rate=10_000, min_count = 5):
    try:
        noisy_data = data_export(data, channel=channel)
    except Exception as e:
        print(e)
        return 0, [], 0, 0

    # Минимально необходимое кол-во импульсов для расчетов
    if min_count < 2:
        min_count = 2

    # Шаг 1: Находим индексы, где значение выше порогового
    above_threshold = noisy_data > threshold

    # Шаг 2: Вычисляем длительность импульса в точках

    #Находим индексы импульсов
    index_threshold = list(find_intervals(above_threshold, min_count))

    # Шаг 1: Вычисление длительности между импульсами
    if len(index_threshold) < 2:
        print(f"Меньше чем {min_count} импульсов. Индексы импульса : {index_threshold}")
        return 0, [], 0, 0

    # Используем NumPy для векторизации вычислений
    end_indices = np.array([index[1] for index in index_threshold])
    pulse_durations_list = np.diff(end_indices)

    # Проверяем, что есть достаточно данных для вычислений
    if len(pulse_durations_list) == 0:
        print("Недостаточно данных для вычисления длительности импульсов.")
        return 0, [], 0, 0

    # Шаг 2: Вычисляем среднюю длительность между импульсами
    pulse_durations = np.mean(pulse_durations_list)
    #print(f"Средняя длительность между двумя импульсами: {pulse_durations}")

    # Шаг 3: Переводим длительности импульсов в секунды
    pulse_durations_seconds = pulse_durations / sampling_rate if sampling_rate > 0 else 0
    #print(f"Длительности импульсов в секундах: {pulse_durations_seconds}")

    # Шаг 4: Вычисляем RPM для каждого импульса
    rpm_values = 60 / pulse_durations_seconds if pulse_durations_seconds > 0 else 0
    #print(f"Количество оборотов в минуту: {rpm_values}")

    # Собираем индексы концов импульсов
    index_null = end_indices.tolist()

    return len(index_threshold), index_null, pulse_durations, rpm_values

def filter_data(data, channel = 1, freq = 10, fs = 2045, only_filter=True,
                negative_data=True, index_null = -1):
    main_amplitude = []
    noise_amplitude = []
    noise_percentage = 0

    noisy_data = data_export(data, channel=channel)

    filtered_data = lowpass_filter(noisy_data, cutoff=freq * 2, fs=fs)  # Фильтруем выше удвоенной частоты

    if only_filter:
        return filtered_data

    # 2. Вычисление шума
    noise = noisy_data - filtered_data

    # 3. Определение амплитуд
    if index_null == -1:
        main_amplitude = np.max(np.abs(filtered_data)) * 2  # Двойная амплитуда основного сигнала

    else:
        for i in range(len(index_null) - 1):
            wave = filtered_data[index_null[i]:index_null[i+1]]
            if negative_data:
                max_amp = np.max(wave[wave > 0], initial=1)
                min_amp = np.min(wave[wave < 0], initial=0)
            else:
                max_amp = np.max(wave, initial=1)
                min_amp = np.min(wave, initial=0)
            main_amplitude.append(max_amp+abs(min_amp))
        print(main_amplitude)
        main_amplitude = np.mean(main_amplitude)

        for i in range(len(index_null) - 1):
            wave = noise[index_null[i]:index_null[i + 1]]
            if negative_data:
                max_amp = np.max(wave[wave > 0], initial=1)
                min_amp = np.min(wave[wave < 0], initial=0)
            else:
                max_amp = np.max(wave, initial=1)
                min_amp = np.min(wave, initial=0)
            noise_amplitude.append(max_amp + abs(min_amp))
        print(noise_amplitude)
        noise_amplitude = np.mean(noise_amplitude)

    # 4. Вычисление процента шума
    if main_amplitude > 0:
        noise_percentage = (noise_amplitude / main_amplitude) * 100

    return  noisy_data, filtered_data, noise, main_amplitude, noise_amplitude, noise_percentage

def update():
    data = DB.bd_read_last("data_records", frame, True)

    count_impulse, index_null, pulse_durations, rpm_values = count_turn(data, channel=4, min_count=5)

    print(index_null)

    # Запоминаем начальное время
    start_time = time.perf_counter()

    global t, noisy_signal, filtered_signal, noise_estimated, frequency, fs

    (noisy_signal, filtered_signal,
     noise_estimated,main_amplitude,
     noise_amplitude, noise_percentage ) = filter_data(data=data, channel=1, freq=frequency,
                                                       fs=fs, only_filter=False, index_null=index_null)

    # Запоминаем конечное время
    end_time = time.perf_counter()

    # Вычисляем разницу в миллисекундах
    execution_time_ms = (end_time - start_time) * 1000

    print(f"Время выполнения: {execution_time_ms:.3f} миллисекунд")

    # Вывод результатов
    print(f"Амплитуда основного сигнала: {main_amplitude:.2f}")
    print(f"Амплитуда шума: {noise_amplitude:.2f}")
    print(f"Процент шума относительно основного сигнала: {noise_percentage:.2f}%")

    # Визуализация
    plt.figure(figsize=(12, 6))
    plt.subplot(3, 1, 1)
    plt.plot(t, noisy_signal, label="Сигнал с шумом")
    plt.legend()

    plt.subplot(3, 1, 2)
    plt.plot(t, filtered_signal, label="Основной сигнал", color="orange")
    plt.legend()

    plt.subplot(3, 1, 3)
    plt.plot(t, noise_estimated, label="Шум", color="red")
    plt.legend()

    plt.tight_layout()
    plt.show()

if __name__ == "__main__":
        update()

