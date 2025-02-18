import numpy as np
import matplotlib.pyplot as plt
from scipy.signal import butter, filtfilt


# test git
git = True

# Генерация тестового сигнала
np.random.seed(42)
fs = 2500  # Частота дискретизации
t = np.linspace(0, 1, fs, endpoint=False)  # Временной массив
frequency = 5  # Частота основного сигнала
amplitude = 1  # Амплитуда основного сигнала
noise_level = 0.5  # Уровень шума

signal = amplitude * np.sin(2 * np.pi * frequency * t)  # Основной сигнал
noise = noise_level * np.random.normal(size=t.shape)  # Шум
noisy_signal = signal + noise  # Сигнал с шумом

# 1. Фильтрация для выделения основной гармоники
def lowpass_filter(data, cutoff, fs, order=5):
    nyquist = 0.5 * fs
    normal_cutoff = cutoff / nyquist
    b, a = butter(order, normal_cutoff, btype='low', analog=False)
    return filtfilt(b, a, data)

filtered_signal = lowpass_filter(noisy_signal, cutoff=frequency * 2, fs=fs)  # Фильтруем выше удвоенной частоты
filtered_signal = filtered_signal[:2000]

t = t[:2000]
# 2. Вычисление шума
noisy_signal = noisy_signal[:2000]
noise_estimated = noisy_signal - filtered_signal

# 3. Определение амплитуд
main_amplitude = np.max(np.abs(filtered_signal))  # Амплитуда основного сигнала
noise_amplitude = np.mean(np.abs(noise_estimated))  # Амплитуда шума

# 4. Вычисление процента шума
noise_percentage = (noise_amplitude / main_amplitude) * 100

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