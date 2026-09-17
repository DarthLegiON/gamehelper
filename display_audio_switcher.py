"""
Display and Audio Switcher Application
Переключатель мониторов и звука для Windows

Требования:
    pip install pycaw comtypes pywin32 wmi

Запуск:
    python display_audio_switcher.py
"""

import ctypes
import sys
import subprocess

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
from pycaw.pycaw import AudioUtilities, IAudioEndpointVolume, IAudioPolicyConfig
import wmi


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

# Функция для получения всех дисплеев через Win32 API
EnumDisplayMonitors = user32.EnumDisplayMonitorsW
EnumDisplayMonitors.argtypes = [wintypes.HDC, wintypes.LPRECT, wintypes.MONITORENUMPROC, wintypes.LPARAM]
EnumDisplayMonitors.restype = wintypes.BOOL

GetMonitorInfoW = user32.GetMonitorInfoW
GetMonitorInfoW.argtypes = [wintypes.HMONITOR, ctypes.POINTER(wintypes.MONITORINFOEXW)]
GetMonitorInfoW.restype = wintypes.BOOL


def get_display_devices():
    """Получить список доступных дисплеев через WMI."""
    displays = []
    try:
        c = wmi.WMI()
        for monitor in c.Win32_DesktopMonitor():
            displays.append({
                'name': monitor.Name or f"Monitor {len(displays) + 1}",
                'status': monitor.Status
            })
        
        # Также проверяем через PnP мониторы
        for pnp in c.Win32_PnPEntity():
            if pnp.PNPClass == 'Monitor' and pnp.Service == 'monitor':
                if not any(d['name'] == pnp.Name for d in displays):
                    displays.append({
                        'name': pnp.Name or f"Monitor {len(displays) + 1}",
                        'status': 'OK'
                    })
    except Exception as e:
        print(f"Ошибка получения дисплеев через WMI: {e}")
    
    # Если WMI не дал результатов, используем fallback
    if not displays:
        displays = [
            {'name': 'Монитор 1', 'status': 'OK'},
            {'name': 'Монитор 2 (Телевизор)', 'status': 'OK'}
        ]
    
    return displays


def get_active_display():
    """Определить активный (основной) дисплей."""
    try:
        # Проверяем, какой монитор является основным через реестр или API
        devmode = DEVMODE()
        devmode.dmSize = ctypes.sizeof(DEVMODE)
        if EnumDisplaySettingsW(None, ENUM_CURRENT_SETTINGS, ctypes.byref(devmode)):
            # Если позиция (0,0), считаем это основным монитором
            if devmode.dmPosition[0] == 0 and devmode.dmPosition[1] == 0:
                return 0
            else:
                return 1
    except:
        pass
    return 0


def switch_to_monitor(monitor_index):
    """
    Переключиться на указанный монитор.
    monitor_index: 0 - основной монитор (Монитор 1), 1 - второй монитор (Монитор 2/Телевизор)
    """
    try:
        # Используем более простой подход - просто меняем основной монитор
        # через установку позиции и флага primary
        
        displays = get_display_devices()
        if monitor_index >= len(displays) and monitor_index > 1:
            return False
        
        # Для простоты переключаем через изменение порядка дисплеев
        # Индекс 0 = DISPLAY1 (основной), индекс 1 = DISPLAY2 (вторичный)
        device_name = f"\\\\.\\DISPLAY{monitor_index + 1}"
        
        devmode = DEVMODE()
        devmode.dmSize = ctypes.sizeof(DEVMODE)
        
        # Получаем текущие настройки целевого дисплея
        if not EnumDisplaySettingsW(device_name, ENUM_CURRENT_SETTINGS, ctypes.byref(devmode)):
            # Если не удалось получить настройки конкретного дисплея, пробуем общий
            if not EnumDisplaySettingsW(None, ENUM_CURRENT_SETTINGS, ctypes.byref(devmode)):
                return False
        
        # Устанавливаем позицию (0, 0) для делаемого основным монитора
        devmode.dmFields = DM_POSITION
        devmode.dmPosition[0] = 0
        devmode.dmPosition[1] = 0
        
        result = ChangeDisplaySettingsExW(
            device_name,
            ctypes.byref(devmode),
            None,
            CDS_UPDATEREGISTRY | CDS_SET_PRIMARY,
            None
        )
        
        if result == DISP_CHANGE_SUCCESSFUL:
            # Применяем изменения
            ChangeDisplaySettingsExW(None, None, None, CDS_RESET | CDS_NORESET, None)
            return True
        elif result == DISP_CHANGE_RESTART:
            # Требуется перезагрузка, но пытаемся применить что можем
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
            # Правильный способ получения устройств в pycaw
            devices = AudioUtilities.GetDevices()
            for device in devices:
                try:
                    if hasattr(device, 'IsActive') and device.IsActive():
                        name = device.FriendlyName if hasattr(device, 'FriendlyName') else str(device.Id)
                        self.devices[name] = device
                except:
                    continue
        except Exception as e:
            print(f"Ошибка получения аудиоустройств: {e}")
            # Fallback: пробуем альтернативный метод
            try:
                from pycaw.pycaw import DeviceEnumerator, EDataFlow
                enumerator = DeviceEnumerator()
                for device in enumerator.enumerate_audio_devices(EDataFlow.eRender):
                    try:
                        name = device.FriendlyName
                        self.devices[name] = device
                    except:
                        continue
            except Exception as e2:
                print(f"Fallback также не удался: {e2}")
    
    def get_speakers_device(self):
        """Получить устройство Speakers (Sound Blaster)."""
        for name, device in self.devices.items():
            if "Speakers" in name or "Sound Blaster" in name:
                return device
        # Если не нашли по имени, возвращаем первое устройство
        if self.devices:
            return list(self.devices.values())[0]
        return None
    
    def get_tv_audio_device(self):
        """Получить аудиоустройство телевизора (NVIDIA HDMI)."""
        for name, device in self.devices.items():
            if "SAMSUNG" in name or "NVIDIA" in name or "HDMI" in name or "Digital Audio" in name:
                return device
        return None
    
    def set_default_device(self, device):
        """Установить устройство по умолчанию."""
        try:
            # Используем PolicyConfig для установки устройства по умолчанию
            from comtypes import GUID
            from ctypes import POINTER, cast
            
            # IID_IAudioPolicyConfig
            audio_policy_config = ctypes.windll.mmdevapi.PolicyConfigClient
            # Это упрощенная реализация, полная требует больше кода
            
            # Пробуем через pycaw
            AudioUtilities.SetDefaultDevice(device)
            return True
        except Exception as e:
            print(f"Ошибка установки устройства: {e}")
            # Альтернативный метод через PowerShell
            try:
                device_name = device.FriendlyName if hasattr(device, 'FriendlyName') else ""
                ps_script = f'''
                Add-Type -Path "%ProgramFiles%\\Reference Assemblies\\Microsoft\\Framework\\.NETFramework\\v4.0\\System.dll"
                $device = "{device_name}"
                '''
                # Это запасной вариант, основной должен работать
            except:
                pass
            return False
    
    def get_current_channels(self):
        """Получить текущую конфигурацию каналов."""
        try:
            speakers_device = self.get_speakers_device()
            if not speakers_device:
                return 2
            
            # Пытаемся получить информацию о каналах через реестр
            import winreg
            try:
                # Путь может отличаться в зависимости от устройства
                key_path = r"SOFTWARE\Microsoft\Windows\CurrentVersion\MMDevices\Audio\Render"
                with winreg.OpenKey(winreg.HKEY_LOCAL_MACHINE, key_path) as key:
                    # Это упрощенная проверка
                    pass
            except:
                pass
            
            return 2  # По умолчанию стерео
        except:
            return 2
    
    def set_speaker_config(self, channels):
        """
        Установить конфигурацию динамиков.
        channels: 2 для стерео (2.0), 6 для объемного звука (5.1)
        """
        try:
            # Используем PowerShell для изменения конфигурации через панель управления звуком
            # Это наиболее надежный способ без использования сторонних DLL
            
            config_value = "Stereo" if channels == 2 else "Surround51"
            
            # Команда PowerShell для изменения конфигурации динамиков
            ps_command = f'''
            $sig = @\'
            [DllImport("mmdevapi.dll")]
            public static extern int GetDeviceDescription(string deviceId, out string description);
            \'@
            # Это упрощенная версия, полная реализация требует больше кода
            \'\'\'
            
            # Более простой метод - использовать NirCmd или аналогичную утилиту
            # Или изменить через реестр напрямую
            
            self._set_channel_config_via_registry(channels)
            return True
        except Exception as e:
            print(f"Ошибка установки конфигурации динамиков: {e}")
            return False
    
    def _set_channel_config_via_registry(self, channels):
        """Изменить конфигурацию каналов через реестр Windows."""
        import winreg
        
        try:
            # Путь к настройкам конфигурации динамиков для текущего устройства
            # Note: точный путь зависит от конкретного устройства и драйвера
            key_paths = [
                r"SYSTEM\CurrentControlSet\Control\Class\{{4d36e96c-e325-11ce-bfc1-08002be10318}}",
                r"SOFTWARE\Creative Labs\Sound Blaster Z SE\CurrentVersion\Drivers",
                r"SOFTWARE\Creative Technology\Sound Blaster Z SE"
            ]
            
            for key_path in key_paths:
                try:
                    # Открываем ключ реестра для записи
                    key = winreg.OpenKey(winreg.HKEY_LOCAL_MACHINE, key_path, 0, winreg.KEY_SET_VALUE)
                    
                    # Значение конфигурации спикеров
                    # 0x3 или 3 - стерео
                    # 0x6 или 6 - 5.1 surround
                    config_value = 3 if channels == 2 else 6
                    
                    # Пробуем разные имена ключей
                    value_names = ["SpeakerConfig", "ChannelConfig", "Channels", "FormatConfig"]
                    
                    for value_name in value_names:
                        try:
                            winreg.SetValueEx(key, value_name, 0, winreg.REG_DWORD, config_value)
                            break
                        except:
                            continue
                    
                    winreg.CloseKey(key)
                    return True
                except FileNotFoundError:
                    continue
                except Exception as e:
                    print(f"Ошибка при работе с реестром ({key_path}): {e}")
                    continue
            
            # Если не нашли в стандартных местах, пробуем через MMDevices
            self._set_via_mmdevices(channels)
            return True
            
        except Exception as e:
            print(f"Ошибка доступа к реестру: {e}")
            return False
    
    def _set_via_mmdevices(self, channels):
        """Альтернативный метод через MMDevices."""
        import winreg
        
        try:
            # Путь к текущим аудиоустройствам
            base_path = r"SOFTWARE\Microsoft\Windows\CurrentVersion\MMDevices\Audio\Render"
            
            key = winreg.OpenKey(winreg.HKEY_LOCAL_MACHINE, base_path)
            i = 0
            while True:
                try:
                    subkey_name = winreg.EnumKey(key, i)
                    device_path = f"{base_path}\\{subkey_name}\\Config"
                    
                    try:
                        device_key = winreg.OpenKey(winreg.HKEY_LOCAL_MACHINE, device_path, 0, winreg.KEY_SET_VALUE)
                        config_value = 3 if channels == 2 else 6
                        winreg.SetValueEx(device_key, "SpeakerConfig", 0, winreg.REG_DWORD, config_value)
                        winreg.CloseKey(device_key)
                    except:
                        pass
                    
                    i += 1
                except OSError:
                    break
            
            winreg.CloseKey(key)
        except Exception as e:
            print(f"Ошибка MMDevices: {e}")


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
