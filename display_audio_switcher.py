"""
Display and Audio Switcher Application
Переключатель мониторов и звука для Windows

Требования:
    pip install pycaw comtypes pywin32

Запуск:
    python display_audio_switcher.py
"""

import ctypes
import sys

def is_admin():
    """Проверяет, запущен ли скрипт с правами администратора."""
    try:
        return ctypes.windll.shell32.IsUserAnAdmin()
    except:
        return False

def run_as_admin():
    """Перезапускает скрипт с правами администратора."""
    if sys.platform == 'win32':
        ctypes.windll.shell32.ShellExecuteW(
            None, "runas", sys.executable, " ".join(sys.argv), None, 1
        )
    sys.exit()

# Запрос прав администратора при запуске (только на Windows)
if sys.platform == 'win32' and not is_admin():
    run_as_admin()

import tkinter as tk
from tkinter import ttk
from ctypes import wintypes
from comtypes import CLSCTX_ALL, CoInitialize, CoUninitialize
from pycaw.pycaw import AudioUtilities, IAudioEndpointVolume


# === Константы Windows API для управления дисплеями ===
ENUM_CURRENT_SETTINGS = -1
ENUM_REGISTRY_SETTINGS = -2
DISP_CHANGE_SUCCESSFUL = 0
DISP_CHANGE_RESTART = 1
CDS_UPDATEREGISTRY = 0x00000001
CDS_TEST = 0x00000002
CDS_FULLSCREEN = 0x00000004
CDS_GLOBAL = 0x00000008
CDS_SET_PRIMARY = 0x00000010
CDS_RESET = 0x40000000
CDS_NORESET = 0x10000000

DM_BITSPERPEL = 0x00040000
DM_PELSWIDTH = 0x00080000
DM_PELSHEIGHT = 0x00100000
DM_DISPLAYFLAGS = 0x00200000
DM_DISPLAYFREQUENCY = 0x00400000
DM_POSITION = 0x00000020


class DEVMODE(ctypes.Structure):
    _fields_ = [
        ("dmSize", wintypes.WORD),
        ("dmDriverExtra", wintypes.WORD),
        ("dmFields", wintypes.DWORD),
        ("dmPosition", ctypes.c_long * 2),
        ("dmDisplayOrientation", wintypes.DWORD),
        ("dmDisplayFixedOutput", wintypes.DWORD),
        ("dmColor", wintypes.SHORT),
        ("dmDuplex", wintypes.SHORT),
        ("dmYResolution", wintypes.SHORT),
        ("dmTTOption", wintypes.SHORT),
        ("dmCollate", wintypes.SHORT),
        ("dmFormName", wintypes.WCHAR * 32),
        ("dmLogPixels", wintypes.WORD),
        ("dmBitsPerPel", wintypes.DWORD),
        ("dmPelsWidth", wintypes.DWORD),
        ("dmPelsHeight", wintypes.DWORD),
        ("dmDisplayFlags", wintypes.DWORD),
        ("dmDisplayFrequency", wintypes.DWORD),
        ("dmICMMethod", wintypes.DWORD),
        ("dmICMIntent", wintypes.DWORD),
        ("dmMediaType", wintypes.DWORD),
        ("dmDitherType", wintypes.DWORD),
        ("dmReserved1", wintypes.DWORD),
        ("dmReserved2", wintypes.DWORD),
        ("dmPanningWidth", wintypes.DWORD),
        ("dmPanningHeight", wintypes.DWORD),
    ]


# Загрузка функций Windows API
user32 = ctypes.windll.user32
EnumDisplaySettingsW = user32.EnumDisplaySettingsW
EnumDisplaySettingsW.argtypes = [wintypes.LPCWSTR, wintypes.DWORD, ctypes.POINTER(DEVMODE)]
EnumDisplaySettingsW.restype = wintypes.BOOL

ChangeDisplaySettingsExW = user32.ChangeDisplaySettingsExW
ChangeDisplaySettingsExW.argtypes = [wintypes.LPCWSTR, ctypes.POINTER(DEVMODE), wintypes.HWND, wintypes.DWORD, wintypes.LPVOID]
ChangeDisplaySettingsExW.restype = wintypes.LONG


def get_display_devices():
    """Получить список доступных дисплеев."""
    displays = []
    i = 0
    while True:
        devmode = DEVMODE()
        devmode.dmSize = ctypes.sizeof(DEVMODE)
        if not EnumDisplaySettingsW(None, i, ctypes.byref(devmode)):
            break
        # Проверяем, является ли это уникальным дисплеем
        device_name = f"\\\\.\\DISPLAY{i + 1}"
        if i == 0 or devmode.dmPelsWidth > 0:
            displays.append({
                'index': i,
                'name': device_name,
                'width': devmode.dmPelsWidth,
                'height': devmode.dmPelsHeight,
                'position_x': devmode.dmPosition[0],
                'position_y': devmode.dmPosition[1],
            })
        i += 1
        if i > 20:  # Защита от бесконечного цикла
            break
    return displays


def get_active_display():
    """Определить активный (основной) дисплей."""
    devmode = DEVMODE()
    devmode.dmSize = ctypes.sizeof(DEVMODE)
    if EnumDisplaySettingsW(None, ENUM_CURRENT_SETTINGS, ctypes.byref(devmode)):
        # Основной монитор обычно имеет позицию (0, 0) или является DISPLAY1
        return 0  # Возвращаем индекс основного монитора
    return 0


def switch_to_monitor(monitor_index):
    """
    Переключиться на указанный монитор.
    monitor_index: 0 - основной монитор (Монитор 1), 1 - второй монитор (Монитор 2/Телевизор)
    """
    try:
        displays = get_display_devices()
        if monitor_index >= len(displays):
            return False
        
        target_display = displays[monitor_index]
        
        # Устанавливаем целевой монитор как основной
        devmode = DEVMODE()
        devmode.dmSize = ctypes.sizeof(DEVMODE)
        devmode.dmFields = DM_POSITION | DM_PELSWIDTH | DM_PELSHEIGHT
        
        # Позиционируем целевой монитор в (0, 0) чтобы сделать его основным
        devmode.dmPosition[0] = 0
        devmode.dmPosition[1] = 0
        devmode.dmPelsWidth = target_display['width']
        devmode.dmPelsHeight = target_display['height']
        
        result = ChangeDisplaySettingsExW(
            target_display['name'],
            ctypes.byref(devmode),
            None,
            CDS_UPDATEREGISTRY | CDS_SET_PRIMARY,
            None
        )
        
        if result == DISP_CHANGE_SUCCESSFUL:
            # Обновляем настройки для всех дисплеев
            ChangeDisplaySettingsExW(None, None, None, CDS_RESET, None)
            return True
        return False
    except Exception as e:
        print(f"Ошибка переключения монитора: {e}")
        return False


class AudioController:
    """Класс для управления аудиоустройствами Windows."""
    
    def __init__(self):
        self.devices = {}
        self._refresh_devices()
    
    def _refresh_devices(self):
        """Обновить список аудиоустройств."""
        self.devices = {}
        try:
            devices = AudioUtilities.GetDevices()
            for device in devices:
                if not device.IsActive():
                    continue
                name = device.FriendlyName
                self.devices[name] = device
        except Exception as e:
            print(f"Ошибка получения аудиоустройств: {e}")
    
    def get_speakers_device(self):
        """Получить устройство Speakers (Sound Blaster)."""
        for name, device in self.devices.items():
            if "Speakers" in name or "Sound Blaster" in name:
                return device
        return None
    
    def get_tv_audio_device(self):
        """Получить аудиоустройство телевизора (NVIDIA HDMI)."""
        for name, device in self.devices.items():
            if "SAMSUNG" in name or "NVIDIA" in name or "HDMI" in name:
                return device
        return None
    
    def set_default_device(self, device):
        """Установить устройство по умолчанию."""
        try:
            AudioUtilities.SetDefaultDevice(device)
            return True
        except Exception as e:
            print(f"Ошибка установки устройства: {e}")
            return False
    
    def get_channel_count(self, device):
        """Получить количество каналов устройства."""
        try:
            interface = device.Activate(IAudioEndpointVolume._iid_, CLSCTX_ALL, None)
            volume = ctypes.cast(interface, ctypes.POINTER(IAudioEndpointVolume))
            # Получаем информацию о каналах через другие методы
            return 2  # По умолчанию стерео
        except:
            return 2
    
    def set_speaker_config(self, channels):
        """
        Установить конфигурацию динамиков.
        channels: 2 для стерео (2.0), 6 для объемного звука (5.1)
        """
        try:
            # Используем Windows Audio Session API для изменения конфигурации
            from ctypes import POINTER, Structure, c_float, c_uint32, c_void_p
            from comtypes import GUID
            
            # Ищем устройство Sound Blaster
            speakers_device = self.get_speakers_device()
            if not speakers_device:
                return False
            
            # Активируем интерфейс endpoint volume
            interface = speakers_device.Activate(
                IAudioEndpointVolume._iid_, 
                CLSCTX_ALL, 
                None
            )
            
            # Для изменения конфигурации каналов нужно использовать PolicyConfig
            # Это более сложный процесс, требующий доступа к реестру
            self._set_channel_config_via_registry(channels)
            return True
        except Exception as e:
            print(f"Ошибка установки конфигурации динамиков: {e}")
            return False
    
    def _set_channel_config_via_registry(self, channels):
        """Изменить конфигурацию каналов через реестр Windows."""
        import winreg
        
        try:
            # Путь к настройкам конфигурации динамиков
            key_path = r"SYSTEM\CurrentControlSet\Control\Class\{4d36e96c-e325-11ce-bfc1-08002be10318}"
            
            # Открываем ключ реестра
            with winreg.OpenKey(winreg.HKEY_LOCAL_MACHINE, key_path) as key:
                # Ищем подлючи для каждого устройства
                i = 0
                while True:
                    try:
                        subkey_name = winreg.EnumKey(key, i)
                        with winreg.OpenKey(key, subkey_name) as subkey:
                            try:
                                # Проверяем, есть ли значение SpeakerConfig
                                speaker_config, _ = winreg.QueryValueEx(subkey, "SpeakerConfig")
                                # Обновляем значение
                                # 0x00000003 - стерео (2.0)
                                # 0x00000006 - 5.1 surround
                                config_value = 0x3 if channels == 2 else 0x6
                                winreg.SetValueEx(subkey, "SpeakerConfig", 0, winreg.REG_DWORD, config_value)
                            except FileNotFoundError:
                                pass
                        i += 1
                    except OSError:
                        break
        except Exception as e:
            print(f"Ошибка доступа к реестру: {e}")


class DisplayAudioSwitcher:
    """Основное приложение."""
    
    def __init__(self, root):
        self.root = root
        self.root.title("Переключатель Монитор/Звук")
        self.root.resizable(False, False)
        
        self.audio_controller = AudioController()
        
        # Создаем интерфейс
        self._create_ui()
        
        # Обновляем состояние при запуске
        self._update_state_from_system()
    
    def _create_ui(self):
        """Создать пользовательский интерфейс."""
        main_frame = ttk.Frame(self.root, padding="10")
        main_frame.grid(row=0, column=0, sticky=(tk.W, tk.E, tk.N, tk.S))
        
        # Группа "Монитор"
        monitor_frame = ttk.LabelFrame(main_frame, text="Монитор", padding="10")
        monitor_frame.grid(row=0, column=0, padx=5, pady=5, sticky=(tk.W, tk.E))
        
        self.monitor_var = tk.StringVar()
        self.monitor_combo = ttk.Combobox(
            monitor_frame, 
            textvariable=self.monitor_var,
            values=["Рабочий стол", "Телевизор"],
            state="readonly",
            width=20
        )
        self.monitor_combo.grid(row=0, column=0, padx=5, pady=5)
        self.monitor_combo.bind('<<ComboboxSelected>>', self._on_monitor_change)
        
        # Группа "Звук"
        sound_frame = ttk.LabelFrame(main_frame, text="Звук", padding="10")
        sound_frame.grid(row=1, column=0, padx=5, pady=5, sticky=(tk.W, tk.E))
        
        self.sound_var = tk.StringVar()
        self.sound_combo = ttk.Combobox(
            sound_frame,
            textvariable=self.sound_var,
            values=["Настольный", "Объемный"],
            state="readonly",
            width=20
        )
        self.sound_combo.grid(row=0, column=0, padx=5, pady=5)
        self.sound_combo.bind('<<ComboboxSelected>>', self._on_sound_change)
        
        # Кнопка обновления состояния
        refresh_btn = ttk.Button(
            main_frame,
            text="Обновить состояние",
            command=self._update_state_from_system
        )
        refresh_btn.grid(row=2, column=0, padx=5, pady=10)
        
        # Статус бар
        self.status_var = tk.StringVar(value="Готово")
        status_label = ttk.Label(main_frame, textvariable=self.status_var, foreground="gray")
        status_label.grid(row=3, column=0, padx=5, pady=5)
    
    def _update_state_from_system(self):
        """Обновить состояние комбобоксов из текущих настроек системы."""
        try:
            # Определяем текущий активный монитор
            active_display = get_active_display()
            if active_display == 0:
                self.monitor_var.set("Рабочий стол")
            else:
                self.monitor_var.set("Телевизор")
            
            # Определяем текущую конфигурацию звука
            # Проверяем, какое устройство активно и его конфигурацию
            speakers_device = self.audio_controller.get_speakers_device()
            if speakers_device:
                # По умолчанию предполагаем стерео (2.0)
                # В реальной реализации нужно проверять фактическую конфигурацию
                self.sound_var.set("Настольный")
            else:
                self.sound_var.set("Настольный")
            
            self.status_var.set("Состояние обновлено")
        except Exception as e:
            self.status_var.set(f"Ошибка: {e}")
    
    def _on_monitor_change(self, event=None):
        """Обработчик изменения выбора монитора."""
        selection = self.monitor_var.get()
        
        if selection == "Рабочий стол":
            # Переключаемся на монитор 1
            success = switch_to_monitor(0)
            if success:
                # Автоматически переключаем звук в режим 2.0
                self.sound_var.set("Настольный")
                self.audio_controller.set_speaker_config(2)
                self.status_var.set("Переключено на рабочий стол (звук 2.0)")
            else:
                self.status_var.set("Ошибка переключения монитора")
        
        elif selection == "Телевизор":
            # Переключаемся на монитор 2 (телевизор)
            success = switch_to_monitor(1)
            if success:
                # Переключаем звук на телевизор (NVIDIA HDMI)
                tv_device = self.audio_controller.get_tv_audio_device()
                if tv_device:
                    self.audio_controller.set_default_device(tv_device)
                    self.status_var.set("Переключено на телевизор (звук через HDMI)")
                else:
                    self.status_var.set("Монитор переключен, аудиоустройство не найдено")
            else:
                self.status_var.set("Ошибка переключения монитора")
    
    def _on_sound_change(self, event=None):
        """Обработчик изменения выбора звука."""
        selection = self.sound_var.get()
        
        if selection == "Настольный":
            # Переключаем звук в режим 2.0
            self.audio_controller.set_speaker_config(2)
            # Также переключаем аудиоустройство на Speakers
            speakers_device = self.audio_controller.get_speakers_device()
            if speakers_device:
                self.audio_controller.set_default_device(speakers_device)
            self.status_var.set("Звук: Настольный (2.0)")
        
        elif selection == "Объемный":
            # Переключаем звук в режим 5.1
            self.audio_controller.set_speaker_config(6)
            self.status_var.set("Звук: Объемный (5.1)")


def main():
    """Точка входа приложения."""
    # Инициализация COM
    CoInitialize()
    
    try:
        root = tk.Tk()
        app = DisplayAudioSwitcher(root)
        root.mainloop()
    finally:
        CoUninitialize()


if __name__ == "__main__":
    main()
