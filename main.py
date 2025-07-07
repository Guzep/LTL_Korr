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
            # Читаем приветственное сообщение полностью
            welcome = self.read_full_welcome()
            self.connected = True
            return welcome
        except Exception as e:
            return str(e)

    def read_full_welcome(self):
        """Чтение всего приветственного сообщения до промпта '>'"""
        full_message = ""
        while True:
            try:
                part = self.tn.read_until(b'\n', timeout=0.5).decode('ascii')
                if not part:
                    break
                full_message += part
                if full_message.endswith('>'):
                    break
            except (EOFError, ConnectionResetError):
                break
        return full_message.strip()

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
        self.root.title("Управление антенной")
        self.root.geometry("800x750")  # Увеличили высоту для частоты опроса

        self.telnet = TelnetClient()
        self.logging = False
        self.log_file = None
        self.monitoring_active = False
        self.monitoring_thread = None
        self.polling_interval = 10  # seconds

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
            command=lambda: self.send_command("4")
        ).pack(side=tk.LEFT, padx=5, pady=5)

        ttk.Button(
            mode_frame,
            text="Ручной режим",
            command=lambda: self.send_command("5")
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

        # Мониторинг температуры
        monitor_frame = ttk.LabelFrame(tab, text="Мониторинг температуры")
        monitor_frame.pack(fill=tk.X, padx=5, pady=5)

        ttk.Label(monitor_frame, text="Интервал опроса (сек):").pack(side=tk.LEFT, padx=5, pady=5)
        self.interval_entry = ttk.Entry(monitor_frame, width=5)
        self.interval_entry.pack(side=tk.LEFT, padx=5, pady=5)
        self.interval_entry.insert(0, "10")

        self.monitor_button = ttk.Button(
            monitor_frame,
            text="Начать мониторинг",
            command=self.toggle_monitoring
        )
        self.monitor_button.pack(side=tk.LEFT, padx=5, pady=5)

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

        return response

    def set_thresholds(self):
        """Установка порогов температуры"""
        min_val = self.min_entry.get()
        max_val = self.max_entry.get()

        if not min_val or not max_val:
            self.log("Ошибка: Введите значения min и max")
            return

        command = f"8 {min_val} {max_val}"
        self.send_command(command)

    def toggle_monitoring(self):
        """Переключение режима мониторинга температуры"""
        if not self.monitoring_active:
            # Начать мониторинг
            try:
                self.polling_interval = int(self.interval_entry.get())
                if self.polling_interval <= 0:
                    raise ValueError("Интервал должен быть положительным числом")
            except ValueError as e:
                self.log(f"Ошибка: {str(e)}")
                return

            # Создаем файл лога
            timestamp = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
            self.log_filename = f"{timestamp}_temperature_log.txt"
            try:
                self.log_file = open(self.log_filename, 'a')
                self.logging = True
                self.log(f"Начата запись температуры в {self.log_filename}")
            except Exception as e:
                self.log(f"Ошибка создания файла лога: {str(e)}")
                return

            # Запускаем поток мониторинга
            self.monitoring_active = True
            self.monitoring_thread = threading.Thread(target=self.monitor_temperature)
            self.monitoring_thread.daemon = True
            self.monitoring_thread.start()

            self.monitor_button.config(text="Остановить мониторинг")
        else:
            # Остановить мониторинг
            self.monitoring_active = False
            if self.logging and self.log_file:
                try:
                    self.log_file.close()
                except Exception as e:
                    self.log(f"Ошибка закрытия файла лога: {str(e)}")
                self.logging = False
                self.log("Мониторинг температуры остановлен")

            self.monitor_button.config(text="Начать мониторинг")

    def monitor_temperature(self):
        """Периодический опрос температуры"""
        while self.monitoring_active:
            start_time = time.time()

            # Отправляем команду запроса температуры
            response = self.send_command("3")

            # Записываем в лог-файл
            if self.logging and self.log_file:
                timestamp = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
                try:
                    self.log_file.write(f"{timestamp},{response}\n")
                    self.log_file.flush()
                except Exception as e:
                    self.log(f"Ошибка записи температуры: {str(e)}")

            # Ожидаем до следующего опроса
            elapsed = time.time() - start_time
            sleep_time = max(0.1, self.polling_interval - elapsed)
            time.sleep(sleep_time)

    def on_closing(self):
        """Обработка закрытия приложения"""
        if self.monitoring_active:
            self.monitoring_active = False
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