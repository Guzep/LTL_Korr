import tkinter as tk
from tkinter import ttk, messagebox, scrolledtext
import telnetlib
import threading
import time
import datetime


class TelnetClient:
    def __init__(self):
        self.tn = None
        self.connected = False
        self.lock = threading.Lock()

    def connect(self, host, port):
        try:
            self.tn = telnetlib.Telnet(host, port, timeout=5)
            # Читаем приветственное сообщение
            welcome = self.tn.read_until(b'>', timeout=5).decode('ascii').strip()
            self.connected = True
            return welcome
        except Exception as e:
            return str(e)

    def disconnect(self):
        if self.connected:
            self.tn.close()
            self.connected = False

    def send_command(self, command):
        with self.lock:
            if not self.connected:
                return "Не подключено"
            try:
                self.tn.write(command.encode('ascii') + b'\r\n')
                # Читаем ответ до промпта '>'
                response = self.tn.read_until(b'>', timeout=5).decode('ascii').strip()
                # Убираем последний символ '>' если он есть
                if response.endswith('>'):
                    response = response[:-1].strip()
                return response
            except Exception as e:
                return f"Ошибка: {str(e)}"


class App:
    def __init__(self, root):
        self.root = root
        self.root.title("Управление Мини Корр")
        self.root.geometry("800x700")

        self.telnet = TelnetClient()
        self.logging = False
        self.log_file = None
        self.fan_mode = "auto"  # auto/manual

        # Создаем панели
        main_panel = tk.PanedWindow(root, orient=tk.VERTICAL, sashrelief=tk.RAISED, sashwidth=4)
        main_panel.pack(fill=tk.BOTH, expand=True)

        # Верхняя панель (управление)
        control_frame = ttk.Frame(main_panel)
        main_panel.add(control_frame)

        # Нижняя панель (консоль)
        console_frame = ttk.Frame(main_panel)
        main_panel.add(console_frame)

        # Консоль
        self.console = scrolledtext.ScrolledText(
            console_frame,
            state='disabled',
            wrap=tk.WORD,
            height=15
        )
        self.console.pack(fill=tk.BOTH, expand=True, padx=5, pady=5)

        # Инициализация панели управления
        self.init_control_tab(control_frame)

        # Обработка закрытия окна
        self.root.protocol("WM_DELETE_WINDOW", self.on_closing)

    def log(self, message):
        """Логирование в консоль и файл"""
        timestamp = time.strftime("%H:%M:%S", time.localtime())
        log_message = f"[{timestamp}] {message}"

        self.console.config(state=tk.NORMAL)
        self.console.insert(tk.END, log_message + "\n")
        self.console.config(state=tk.DISABLED)
        self.console.see(tk.END)

        if self.logging and self.log_file:
            try:
                self.log_file.write(log_message + "\n")
                self.log_file.flush()
            except Exception as e:
                self.log(f"Ошибка записи в лог: {str(e)}")
                self.logging = False

    def init_control_tab(self, tab):
        """Инициализация панели управления"""
        # Настройки подключения
        conn_frame = ttk.LabelFrame(tab, text="Настройки подключения")
        conn_frame.pack(fill=tk.X, padx=5, pady=5)

        ttk.Label(conn_frame, text="IP адрес:").grid(row=0, column=0, padx=5, pady=5, sticky=tk.W)
        self.ip_entry = ttk.Entry(conn_frame, width=15)
        self.ip_entry.grid(row=0, column=1, padx=5, pady=5)
        self.ip_entry.insert(0, "192.168.0.100")

        ttk.Label(conn_frame, text="Порт:").grid(row=0, column=2, padx=5, pady=5, sticky=tk.W)
        self.port_entry = ttk.Entry(conn_frame, width=8)
        self.port_entry.grid(row=0, column=3, padx=5, pady=5)
        self.port_entry.insert(0, "5100")

        ttk.Button(
            conn_frame,
            text="Подключиться",
            command=self.connect_device
        ).grid(row=0, column=4, padx=5, pady=5)

        # Управление реле
        relay_frame = ttk.LabelFrame(tab, text="Управление реле")
        relay_frame.pack(fill=tk.X, padx=5, pady=5)

        ttk.Button(
            relay_frame,
            text="Включить реле",
            command=lambda: self.send_command("1")
        ).pack(side=tk.LEFT, padx=5, pady=5)

        ttk.Button(
            relay_frame,
            text="Выключить реле",
            command=lambda: self.send_command("2")
        ).pack(side=tk.LEFT, padx=5, pady=5)

        # Температура
        temp_frame = ttk.LabelFrame(tab, text="Температура")
        temp_frame.pack(fill=tk.X, padx=5, pady=5)

        ttk.Button(
            temp_frame,
            text="Показать температуру",
            command=lambda: self.send_command("3")
        ).pack(side=tk.LEFT, padx=5, pady=5)

        self.temp_label = ttk.Label(temp_frame, text="---")
        self.temp_label.pack(side=tk.LEFT, padx=5, pady=5)

        # Управление вентилятором
        fan_frame = ttk.LabelFrame(tab, text="Управление вентилятором")
        fan_frame.pack(fill=tk.X, padx=5, pady=5)

        mode_frame = ttk.Frame(fan_frame)
        mode_frame.pack(fill=tk.X, padx=5, pady=5)

        ttk.Button(
            mode_frame,
            text="Автоматический режим",
            command=self.enable_auto_fan
        ).pack(side=tk.LEFT, padx=5, pady=5)

        ttk.Button(
            mode_frame,
            text="Ручной режим",
            command=self.enable_manual_fan
        ).pack(side=tk.LEFT, padx=5, pady=5)

        control_frame = ttk.Frame(fan_frame)
        control_frame.pack(fill=tk.X, padx=5, pady=5)

        ttk.Button(
            control_frame,
            text="Включить вентилятор",
            command=lambda: self.send_command("6")
        ).pack(side=tk.LEFT, padx=5, pady=5)

        ttk.Button(
            control_frame,
            text="Выключить вентилятор",
            command=lambda: self.send_command("7")
        ).pack(side=tk.LEFT, padx=5, pady=5)

        # Пороги температуры
        threshold_frame = ttk.LabelFrame(tab, text="Пороги температуры")
        threshold_frame.pack(fill=tk.X, padx=5, pady=5)

        input_frame = ttk.Frame(threshold_frame)
        input_frame.pack(fill=tk.X, padx=5, pady=5)

        ttk.Label(input_frame, text="Min:").pack(side=tk.LEFT, padx=5, pady=5)
        self.min_entry = ttk.Entry(input_frame, width=5)
        self.min_entry.pack(side=tk.LEFT, padx=5, pady=5)

        ttk.Label(input_frame, text="Max:").pack(side=tk.LEFT, padx=5, pady=5)
        self.max_entry = ttk.Entry(input_frame, width=5)
        self.max_entry.pack(side=tk.LEFT, padx=5, pady=5)

        ttk.Button(
            input_frame,
            text="Установить пороги",
            command=self.set_thresholds
        ).pack(side=tk.LEFT, padx=5, pady=5)

        ttk.Button(
            input_frame,
            text="Получить пороги",
            command=lambda: self.send_command("9")
        ).pack(side=tk.LEFT, padx=5, pady=5)

        self.threshold_label = ttk.Label(threshold_frame, text="Текущие пороги: ---")
        self.threshold_label.pack(padx=5, pady=5)

        # Управление логом
        log_frame = ttk.LabelFrame(tab, text="Управление записью лога")
        log_frame.pack(fill=tk.X, padx=5, pady=5)

        self.log_button = ttk.Button(
            log_frame,
            text="Начать запись лога",
            command=self.toggle_logging
        )
        self.log_button.pack(padx=5, pady=5)

    def connect_device(self):
        """Подключение к устройству"""
        ip = self.ip_entry.get()
        port = self.port_entry.get()

        if not ip or not port:
            self.log("Ошибка: Укажите IP и порт")
            return

        try:
            port = int(port)
        except ValueError:
            self.log("Ошибка: Некорректный порт")
            return

        result = self.telnet.connect(ip, port)
        if self.telnet.connected:
            self.log(f"Успешно подключено к {ip}:{port}")
            self.log(f"Сообщение сервера:\n{result}")
        else:
            self.log(f"Ошибка подключения: {result}")

    def send_command(self, command):
        """Отправка команды на устройство"""
        if not self.telnet.connected:
            self.log("Не подключено к устройству")
            return

        self.log(f"Отправка команды: {command}")
        response = self.telnet.send_command(command)
        self.log(f"Ответ: {response}")

        # Обработка ответов для обновления интерфейса
        if command == "3":  # Температура
            self.temp_label.config(text=response)
        elif command == "9":  # Пороги температуры
            self.threshold_label.config(text=f"Текущие пороги: {response}")

    def enable_auto_fan(self):
        """Включение автоматического режима вентилятора"""
        self.fan_mode = "auto"
        self.send_command("4")

    def enable_manual_fan(self):
        """Включение ручного режима вентилятора"""
        self.fan_mode = "manual"
        self.send_command("5")

    def set_thresholds(self):
        """Установка порогов температуры"""
        min_val = self.min_entry.get()
        max_val = self.max_entry.get()

        if not min_val or not max_val:
            self.log("Ошибка: Введите значения min и max")
            return

        command = f"8 {min_val} {max_val}"
        self.send_command(command)

    def toggle_logging(self):
        """Переключение режима записи лога"""
        if not self.logging:
            # Начать запись
            timestamp = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
            filename = f"{timestamp}_logfile.txt"
            try:
                self.log_file = open(filename, 'a')
                self.logging = True
                self.log(f"Начата запись лога в {filename}")
                self.log_button.config(text="Остановить запись лога")
            except Exception as e:
                self.log(f"Ошибка создания файла лога: {str(e)}")
        else:
            # Остановить запись
            try:
                if self.log_file:
                    self.log_file.close()
            except Exception as e:
                self.log(f"Ошибка закрытия файла лога: {str(e)}")
            self.logging = False
            self.log("Запись лога остановлена")
            self.log_button.config(text="Начать запись лога")

    def on_closing(self):
        """Обработка закрытия приложения"""
        if self.logging and self.log_file:
            try:
                self.log_file.close()
            except:
                pass

        if self.telnet.connected:
            self.telnet.disconnect()

        self.root.destroy()


if __name__ == "__main__":
    root = tk.Tk()
    app = App(root)
    root.mainloop()