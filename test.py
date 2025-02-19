import numpy as np
import data_read
import matplotlib.pyplot as plt
from scipy.signal import butter, filtfilt
import time

DB = data_read.DataRead()

# Генерация тестового сигнала
np.random.seed(42)

frame = 5
fs = 2045 * frame  # Частота дискретизации
t = np.linspace(0, fs, fs, endpoint=False)  # Временной массив
frequency = 10 * frame  # Частота основного сигнала
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
    nyquist = 0.5 * fs
    normal_cutoff = cutoff / nyquist
    b, a = butter(order, normal_cutoff, btype='low', analog=False)
    return filtfilt(b, a, data)

def data_export(data, channel=1):
    if channel < 1:
        channel = 1
    elif channel > 4:
        channel = 4

    if data:
        # Извлекаем массив array_1 из записи
        data_frames = [row[3 + channel] for row in data[::-1]]  # Предполагается, что array_1 находится в четвертом столбце
        noisy_data = np.array(data_frames).ravel()  # Преобразуем в массив NumPy
        return noisy_data

    return -1

def count_turn(data, channel = 4, treshold = 1000):
    noisy_data = data_export(data, channel=channel)

def filter_data(data, channel = 1, freq = 10, fs = 2045, only_filter=True):
    noisy_data = data_export(data, channel=channel)

    filtered_data = lowpass_filter(noisy_data, cutoff=freq * 2, fs=fs)  # Фильтруем выше удвоенной частоты

    if only_filter:
        return filtered_data

    # 2. Вычисление шума
    noise = noisy_data - filtered_data

    # 3. Определение амплитуд
    main_amplitude = np.max(np.abs(filtered_data)) * 2  # Двойная амплитуда основного сигнала
    noise_amplitude = np.max(np.abs(noise))  # Амплитуда шума

    # 4. Вычисление процента шума
    noise_percentage = (noise_amplitude / main_amplitude) * 100

    return  noisy_data, filtered_data, noise, main_amplitude, noise_amplitude, noise_percentage

def update():
    data = DB.bd_read_last("data_records", frame, True)
    # Запоминаем начальное время
    start_time = time.perf_counter()

    global t, noisy_signal, filtered_signal, noise_estimated, frequency, fs

    (noisy_signal, filtered_signal,
     noise_estimated,main_amplitude,
     noise_amplitude, noise_percentage ) = filter_data(data=data, channel=1, freq=frequency,
                                                       fs=fs, only_filter=False)

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

