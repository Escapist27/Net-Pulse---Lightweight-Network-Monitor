"""
NetPulse — лёгкий монитор сети / lightweight network monitor.

Добавляешь устройства (имя + IP/хост), ставишь период (дни/часы/минуты),
жмёшь «Запустить» — программа пингует все устройства с заданным интервалом
и фиксирует каждый обрыв связи: когда начался, когда закончился, сколько длился.
Лог (.log) и отчёт (.json) сохраняются в выбранную папку.

Зависимость: pip install customtkinter
"""

import ctypes
import json
import os
import platform
import queue
import re
import shutil
import subprocess
import sys
import threading
import time
import uuid
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timedelta
from tkinter import filedialog, messagebox, ttk
import tkinter as tk

import customtkinter as ctk

# --------------------------------------------------------------------------- #
# Пути и константы
# --------------------------------------------------------------------------- #
if getattr(sys, "frozen", False):
    APP_DIR = os.path.dirname(sys.executable)
else:
    APP_DIR = os.path.dirname(os.path.abspath(__file__))

def _is_writable(path) -> bool:
    """Можно ли писать в папку (в Program Files — нельзя без прав администратора)."""
    try:
        os.makedirs(path, exist_ok=True)
        probe = os.path.join(path, ".netpulse_write_test")
        with open(probe, "w", encoding="utf-8") as f:
            f.write("ok")
        os.remove(probe)
        return True
    except Exception:
        return False


# Данные держим рядом с программой (portable-режим). Если туда писать нельзя
# (установка в Program Files) — уходим в LOCALAPPDATA/NetPulse.
if _is_writable(APP_DIR):
    DATA_DIR = APP_DIR
else:
    DATA_DIR = os.path.join(os.environ.get("LOCALAPPDATA")
                            or os.path.expanduser("~"), "NetPulse")
    try:
        os.makedirs(DATA_DIR, exist_ok=True)
    except Exception:
        DATA_DIR = APP_DIR

CONFIG_FILE = os.path.join(DATA_DIR, "netpulse_config.json")
LOG_DIR = os.path.join(DATA_DIR, "logs")

# первый запуск после установки: подхватить настройки, лежащие рядом с exe
if DATA_DIR != APP_DIR and not os.path.exists(CONFIG_FILE):
    try:
        _old_cfg = os.path.join(APP_DIR, "netpulse_config.json")
        if os.path.isfile(_old_cfg):
            shutil.copyfile(_old_cfg, CONFIG_FILE)
    except Exception:
        pass

IS_WIN = platform.system() == "Windows"

BG = "#0b0e12"
PANEL = "#141920"
PANEL_2 = "#1a2028"
BORDER = "#262d37"
BTN = "#262d37"
BTN_HOVER = "#3a4350"
TEXT = "#e8ecf1"
MUTED = "#8b95a3"
GREEN = "#22c55e"
GREEN_HOVER = "#16a34a"
RED = "#ef4444"
RED_HOVER = "#dc2626"
RED_TEXT = "#ff6b6b"
RED_BG = "#1d0f12"
RED_BORDER = "#7f1d1d"
YELLOW = "#f59e0b"

TYPE_KEYS = ["pc", "printer", "server", "router", "camera", "terminal", "other"]
INTERVALS = [1, 2, 3, 5, 10, 30, 60]
THRESHOLDS = ["1", "2", "3", "5"]
LANGS = {"ru": "Русский", "en": "English"}

# Имя файла отчёта: только латиница, цифры, _ - .
SAFE_NAME_RE = re.compile(r"[A-Za-z0-9_.\-]{0,80}")

# --------------------------------------------------------------------------- #
# Переводы
# --------------------------------------------------------------------------- #
STRINGS = {
    "ru": {
        "period": "Период мониторинга", "u_d": "дн", "u_h": "ч", "u_m": "мин", "sec": "сек",
        "day_short": "д",
        "interval": "Интервал", "threshold": "Потерь до обрыва",
        "start": "▶   Запустить", "stop": "■   Остановить",
        "online": "Онлайн", "offline": "Офлайн", "loss": "Потери", "pending": "Ожидание",
        "availability": "Доступность", "uptime": "Время работы",
        "pings_ok": "Успешных пингов: {ok} из {total}",
        "remaining": "Осталось: {left}  (до {end})",
        "unlimited": "Без ограничения по времени",
        "idle_period": "Период 0 дн 0 ч 0 мин = без ограничения",
        "devices": "Устройства ({n})", "search": "🔍  Поиск...",
        "col_type": "Тип", "col_name": "Устройство", "col_host": "IP / Хост",
        "col_status": "Статус", "col_lat": "Задержка",
        "ph_name": "Название (напр. POS-01)", "ph_host": "IP или хост",
        "add": "+ Добавить", "delete": "Удалить",
        "outages": "Обрывы связи ({n})", "active_now": "Сейчас без связи: {n}",
        "col_dev": "Устройство / IP", "col_start": "Начало обрыва",
        "col_end": "Восстановлено", "col_dur": "Длительность",
        "no_link": "— нет связи —", "ms": "мс",
        "st_stopped": "Мониторинг остановлен", "st_active": "Мониторинг активен",
        "st_finished": "Мониторинг завершён ({r})",
        "info": "Интервал: {i} сек    |    Устройств: {n}",
        "folder_lbl": "Папка отчётов: {p}",
        "open": "📂 Открыть", "location": "📁 Расположение", "settings": "⚙ Настройки",
        "choose_dir": "Куда сохранять отчёты NetPulse",
        "t_pc": "Компьютер", "t_printer": "Принтер", "t_server": "Сервер", "t_router": "Роутер",
        "t_camera": "Камера", "t_terminal": "Терминал", "t_other": "Другое",
        "bad_host": "Введите корректный IP-адрес или имя хоста.",
        "dup_host": "{h} уже есть в списке.",
        "no_devices": "Сначала добавьте хотя бы одно устройство.",
        "err_log": "Не удалось создать файл журнала в папке:\n{p}\n\n{e}",
        "ask_stop": "Остановить мониторинг?",
        "ask_exit": "Мониторинг ещё идёт. Остановить и выйти?",
        "r_user": "остановлен пользователем", "r_timer": "завершён по таймеру",
        "r_close": "остановлен при закрытии программы",
        "log_started": "NetPulse — мониторинг запущен {t}", "log_period": "Период: {p}",
        "period_fmt": "{d} дн {h} ч {m} мин (до {end})", "period_inf": "без ограничения",
        "log_interval": "Интервал пинга: {i} сек | обрыв после {n} потерь подряд",
        "log_devices": "Устройства:",
        "ev_down": "ОБРЫВ", "ev_up": "ВОССТАНОВЛЕНО", "ev_open": "ОБРЫВ НЕ ЗАКРЫТ",
        "msg_down": "{dev} — пинг не проходит",
        "msg_up": "{dev} — связь появилась. Пинг не шёл {dur} (с {s} по {e})",
        "msg_open": "{dev} — связи нет на момент остановки, длится уже {dur} (с {s})",
        "sum_title": "ИТОГ", "sum_mon": "Мониторинг {r}: {t}", "sum_dur": "Длительность: {d}",
        "sum_avail": "Общая доступность: {a:.2f} %", "sum_out": "Всего обрывов: {n}",
        "sum_cols": ("Устройство", "Хост", "Доступн.", "Обрывов", "Простой"),
        "dlg_title": "NetPulse — итог мониторинга", "dlg_done": "Мониторинг завершён",
        "dlg_hint": "Название файла — только латиница, цифры и  _ - .",
        "dlg_files": "Будут сохранены два файла: <имя>.log (читаемый) и <имя>.json",
        "share_note": "Отчёты хранятся файлами .log и .json. Их можно передавать друг другу: "
                      "возьми файлы из папки «Расположение» и скинь кому нужно. "
                      "Открыть их можно в NetPulse (кнопка «📄 Отчёт») или в любом блокноте.",
        "report": "📄 Отчёт", "open_report": "Открыть отчёт NetPulse",
        "rep_title": "Отчёт: {n}", "rep_started": "Начало", "rep_finished": "Конец",
        "rep_duration": "Длительность", "rep_avail": "Доступность", "rep_outages": "Обрывов",
        "rep_reason": "Причина остановки: {r}   |   Интервал: {i} сек   |   Порог: {t}",
        "rep_devices": "Устройства", "rep_out_list": "Обрывы связи",
        "rep_none": "Обрывов не было 🎉", "rep_ongoing": "— не восстановлено —",
        "col_avail": "Доступность", "col_outages": "Обрывов", "col_downtime": "Простой",
        "show_log": "📝 Показать лог", "bad_report": "Это не отчёт NetPulse или файл повреждён:\n{e}",
        "save": "💾  Сохранить", "close": "Закрыть",
        "need_name": "Введите название файла (латиницей).",
        "overwrite": "Файл «{n}» уже существует. Перезаписать?",
        "save_err": "Не удалось сохранить:\n{e}", "saved": "Сохранено:\n{a}\n{b}",
        "settings_title": "Настройки", "lang": "Язык интерфейса",
        "sound": "Звук при обрыве связи", "folder": "Папка для отчётов",
        "title_offline": "NetPulse — {n} офлайн",
        "theme": "Тема оформления", "theme_dark": "Dark — тёмная", "theme_light": "Light — светлая",
        "soon": "скоро", "light_soon": "Светлая тема появится в следующей версии",
    },
    "en": {
        "period": "Monitoring period", "u_d": "d", "u_h": "h", "u_m": "min", "sec": "s",
        "day_short": "d",
        "interval": "Interval", "threshold": "Losses to outage",
        "start": "▶   Start", "stop": "■   Stop",
        "online": "Online", "offline": "Offline", "loss": "Loss", "pending": "Waiting",
        "availability": "Availability", "uptime": "Uptime",
        "pings_ok": "Successful pings: {ok} of {total}",
        "remaining": "Remaining: {left}  (until {end})",
        "unlimited": "No time limit",
        "idle_period": "Period 0d 0h 0min = no limit",
        "devices": "Devices ({n})", "search": "🔍  Search...",
        "col_type": "Type", "col_name": "Device", "col_host": "IP / Host",
        "col_status": "Status", "col_lat": "Latency",
        "ph_name": "Name (e.g. POS-01)", "ph_host": "IP or host",
        "add": "+ Add", "delete": "Delete",
        "outages": "Connection outages ({n})", "active_now": "Currently down: {n}",
        "col_dev": "Device / IP", "col_start": "Outage start",
        "col_end": "Restored", "col_dur": "Duration",
        "no_link": "— no link —", "ms": "ms",
        "st_stopped": "Monitoring stopped", "st_active": "Monitoring active",
        "st_finished": "Monitoring finished ({r})",
        "info": "Interval: {i} s    |    Devices: {n}",
        "folder_lbl": "Reports folder: {p}",
        "open": "📂 Open", "location": "📁 Location", "settings": "⚙ Settings",
        "choose_dir": "Where to save NetPulse reports",
        "t_pc": "Computer", "t_printer": "Printer", "t_server": "Server", "t_router": "Router",
        "t_camera": "Camera", "t_terminal": "Terminal", "t_other": "Other",
        "bad_host": "Enter a valid IP address or host name.",
        "dup_host": "{h} is already in the list.",
        "no_devices": "Add at least one device first.",
        "err_log": "Cannot create the log file in:\n{p}\n\n{e}",
        "ask_stop": "Stop monitoring?",
        "ask_exit": "Monitoring is still running. Stop and exit?",
        "r_user": "stopped by user", "r_timer": "finished by timer",
        "r_close": "stopped on program exit",
        "log_started": "NetPulse — monitoring started {t}", "log_period": "Period: {p}",
        "period_fmt": "{d}d {h}h {m}min (until {end})", "period_inf": "no limit",
        "log_interval": "Ping interval: {i} s | outage after {n} consecutive losses",
        "log_devices": "Devices:",
        "ev_down": "DOWN", "ev_up": "RESTORED", "ev_open": "STILL DOWN",
        "msg_down": "{dev} — ping failing",
        "msg_up": "{dev} — link restored. Ping was down for {dur} ({s} – {e})",
        "msg_open": "{dev} — still down when stopped, lasting {dur} (since {s})",
        "sum_title": "SUMMARY", "sum_mon": "Monitoring {r}: {t}", "sum_dur": "Duration: {d}",
        "sum_avail": "Overall availability: {a:.2f} %", "sum_out": "Total outages: {n}",
        "sum_cols": ("Device", "Host", "Avail.", "Outages", "Downtime"),
        "dlg_title": "NetPulse — monitoring summary", "dlg_done": "Monitoring finished",
        "dlg_hint": "File name — Latin letters, digits and  _ - .  only",
        "dlg_files": "Two files will be saved: <name>.log (readable) and <name>.json",
        "share_note": "Reports are stored as .log and .json files. You can share them: "
                      "take the files from the «Location» folder and send them to anyone. "
                      "Open them in NetPulse (the «📄 Report» button) or in any text editor.",
        "report": "📄 Report", "open_report": "Open NetPulse report",
        "rep_title": "Report: {n}", "rep_started": "Started", "rep_finished": "Finished",
        "rep_duration": "Duration", "rep_avail": "Availability", "rep_outages": "Outages",
        "rep_reason": "Stop reason: {r}   |   Interval: {i} s   |   Threshold: {t}",
        "rep_devices": "Devices", "rep_out_list": "Connection outages",
        "rep_none": "No outages 🎉", "rep_ongoing": "— not restored —",
        "col_avail": "Availability", "col_outages": "Outages", "col_downtime": "Downtime",
        "show_log": "📝 Show log", "bad_report": "Not a NetPulse report or the file is damaged:\n{e}",
        "save": "💾  Save", "close": "Close",
        "need_name": "Enter a file name (Latin letters).",
        "overwrite": "File \"{n}\" already exists. Overwrite?",
        "save_err": "Could not save:\n{e}", "saved": "Saved:\n{a}\n{b}",
        "settings_title": "Settings", "lang": "Interface language",
        "sound": "Sound on outage", "folder": "Reports folder",
        "title_offline": "NetPulse — {n} offline",
        "theme": "Theme", "theme_dark": "Dark", "theme_light": "Light",
        "soon": "soon", "light_soon": "Light theme is coming in a future version",
    },
}

LANG = "ru"


def T(key, **kw):
    s = STRINGS[LANG].get(key) or STRINGS["ru"].get(key, key)
    return s.format(**kw) if kw else s


def type_key(value):
    """Ключ типа устройства из ключа или подписи на любом языке."""
    if value in TYPE_KEYS:
        return value
    for lang in STRINGS.values():
        for k in TYPE_KEYS:
            if lang[f"t_{k}"] == value:
                return k
    return "other"


# --------------------------------------------------------------------------- #
# Пинг
# --------------------------------------------------------------------------- #
if IS_WIN:
    try:
        PING_ENCODING = f"cp{ctypes.windll.kernel32.GetOEMCP()}"
    except Exception:
        PING_ENCODING = "cp866"
else:
    PING_ENCODING = "utf-8"

# "time=3ms", "time<1ms", "время=3мс", "время<1мс", "time=0.045 ms"
LATENCY_RE = re.compile(r"([=<])\s*(\d+(?:[.,]\d+)?)\s*(?:ms|мс)", re.IGNORECASE)


def ping(host: str, timeout_ms: int = 1000):
    """Один ICMP-пинг. Возвращает (успех, задержка_мс | None)."""
    if IS_WIN:
        cmd = ["ping", "-n", "1", "-w", str(timeout_ms), host]
        flags = subprocess.CREATE_NO_WINDOW
    else:
        cmd = ["ping", "-c", "1", "-W", str(max(1, timeout_ms // 1000)), host]
        flags = 0
    try:
        res = subprocess.run(cmd, capture_output=True, timeout=timeout_ms / 1000 + 4,
                             creationflags=flags)
    except Exception:
        return False, None
    out = res.stdout.decode(PING_ENCODING, errors="ignore")
    # На Windows «Заданный узел недоступен» может вернуть код 0 — поэтому проверяем TTL
    ok = res.returncode == 0 and "ttl" in out.lower()
    latency = None
    if ok:
        m = LATENCY_RE.search(out)
        if m:
            latency = 0.5 if m.group(1) == "<" else float(m.group(2).replace(",", "."))
    return ok, latency


class Monitor(threading.Thread):
    """Фоновый поток: раз в interval секунд параллельно пингует все цели."""

    def __init__(self, session, targets, interval, out_q, timeout_ms=1000):
        super().__init__(daemon=True)
        self.session = session
        self.targets = targets  # [(dev_id, host)]
        self.interval = interval
        self.timeout_ms = timeout_ms
        self.q = out_q
        self.stop_evt = threading.Event()

    def stop(self):
        self.stop_evt.set()

    def run(self):
        workers = min(64, max(4, len(self.targets)))
        with ThreadPoolExecutor(max_workers=workers) as ex:
            while not self.stop_evt.is_set():
                t0 = time.monotonic()
                ts = datetime.now()
                futures = [(ex.submit(ping, host, self.timeout_ms), dev_id)
                           for dev_id, host in self.targets]
                for fut, dev_id in futures:
                    ok, lat = fut.result()
                    if self.stop_evt.is_set():
                        return
                    self.q.put((self.session, dev_id, ok, lat, ts))
                self.stop_evt.wait(max(0.0, self.interval - (time.monotonic() - t0)))


# --------------------------------------------------------------------------- #
# Утилиты
# --------------------------------------------------------------------------- #
def fmt_dur(seconds) -> str:
    seconds = max(0, int(seconds))
    d, rem = divmod(seconds, 86400)
    h, rem = divmod(rem, 3600)
    m, s = divmod(rem, 60)
    return (f"{d}{T('day_short')} " if d else "") + f"{h:02}:{m:02}:{s:02}"


def fmt_ts(dt: datetime) -> str:
    return dt.strftime("%d.%m %H:%M:%S")


def short_path(path, n):
    return path if len(path) <= n else "…" + path[-(n - 1):]


def keep_awake(on: bool):
    """Не даём Windows уснуть, пока идёт мониторинг."""
    if not IS_WIN:
        return
    try:
        ES_CONTINUOUS, ES_SYSTEM_REQUIRED = 0x80000000, 0x00000001
        ctypes.windll.kernel32.SetThreadExecutionState(
            ES_CONTINUOUS | (ES_SYSTEM_REQUIRED if on else 0))
    except Exception:
        pass


def beep():
    if IS_WIN:
        try:
            import winsound
            winsound.MessageBeep(winsound.MB_ICONHAND)
        except Exception:
            pass


def parse_int(value, default=0):
    try:
        return max(0, int(str(value).split()[0]))
    except Exception:
        return default


# --------------------------------------------------------------------------- #
# Приложение
# --------------------------------------------------------------------------- #
class NetPulseApp(ctk.CTk):
    def __init__(self):
        super().__init__()
        ctk.set_appearance_mode("dark")
        self.title("NetPulse — Network Monitor")
        self.configure(fg_color=BG)

        self.devices = []          # список dict
        self.outages = []          # список dict
        self.q = queue.Queue()
        self.monitor = None
        self.session = 0
        self.start_time = None
        self.end_time = None
        self.log_path = None
        self._log_fh = None
        self._settings_win = None

        # настройки (переживают перестройку интерфейса)
        self.period = [1, 0, 0]
        self.interval = 1
        self.threshold = 1
        self.export_dir = LOG_DIR
        self.sound = True

        self._ui_scale = 1.0       # масштаб интерфейса, подобранный под экран
        self.F = lambda size, weight="normal": ctk.CTkFont(family="Segoe UI", size=size, weight=weight)

        self._setup_tree_styles()
        self._load_config()
        self._build_ui()

        self._fit_to_screen()
        self.protocol("WM_DELETE_WINDOW", self._on_close)
        self.after(100, self._drain_queue)
        self.after(1000, self._tick)

    # ------------------------------------------------------- сборка интерфейса
    def _build_ui(self):
        self._build_header()
        self._build_controls()
        self._build_stats()
        self._build_statusbar()   # до main, чтобы при сжатии окна статус-бар не пропадал
        self._build_main()

        self._refresh_dev_tree()
        self._populate_outages()
        self._apply_running_state()
        self._update_stats()
        if self.monitor:
            self._tick_labels()

    def _fit_to_screen(self):
        """Подогнать окно под экран: если макет не влезает — уменьшить масштаб интерфейса."""
        try:
            sf = ctk.ScalingTracker.get_window_scaling(self) or 1.0
        except Exception:
            sf = 1.0
        screen_w, screen_h = self.winfo_screenwidth(), self.winfo_screenheight()
        avail_w, avail_h = screen_w - 40, screen_h - 90     # поля + панель задач

        # 1. ужимаем масштаб виджетов, пока содержимое не влезет по ширине и высоте
        scale = self._ui_scale
        for _ in range(5):
            self.update()
            req_w, req_h = self.winfo_reqwidth(), self.winfo_reqheight()
            factor = min(avail_w / req_w, avail_h / req_h, 1.0)
            if factor > 0.99:
                break
            scale = max(0.62, scale * factor * 0.98)
            try:
                ctk.set_widget_scaling(scale)
            except Exception:
                break

        self._ui_scale = scale

        # 2. размер окна = по содержимому, но не больше рабочей области
        self.update()
        w = min(max(self.winfo_reqwidth() + 4, int(900 * sf)), avail_w)
        h = min(max(self.winfo_reqheight() + 4, int(600 * sf)), avail_h)
        x, y = max(0, (screen_w - w) // 2), max(0, (screen_h - h) // 2 - 20)
        self.minsize(int(min(w, 900 * sf) / sf), int(min(h, 580 * sf) / sf))
        self.geometry(f"{int(w / sf)}x{int(h / sf)}+{int(x / sf)}+{int(y / sf)}")

    def _rebuild_ui(self):
        """Пересобрать весь интерфейс (смена языка). Мониторинг не прерывается."""
        if not self.monitor:
            self._read_controls()
        for w in self.winfo_children():
            w.destroy()
        self._settings_win = None
        self._build_ui()
        self._fit_to_screen()

    def _read_controls(self):
        self.period = [parse_int(self.cb_days.get()), parse_int(self.cb_hours.get()),
                       parse_int(self.cb_mins.get())]
        self.interval = parse_int(self.cb_interval.get(), 1) or 1
        self.threshold = parse_int(self.cb_threshold.get(), 1) or 1

    # ------------------------------------------------------------------ стили
    def _setup_tree_styles(self):
        style = ttk.Style(self)
        style.theme_use("clam")
        row_h = int(round(float(self.tk.call("tk", "scaling")) * 26))

        for name, bg, sel in (("Dev", PANEL, "#1f2a37"), ("Out", RED_BG, "#3a1a1f")):
            style.configure(f"{name}.Treeview", background=bg, fieldbackground=bg,
                            foreground=TEXT, borderwidth=0, relief="flat",
                            rowheight=row_h, font=("Segoe UI", 11))
            style.map(f"{name}.Treeview", background=[("selected", sel)],
                      foreground=[("selected", TEXT)])
            style.configure(f"{name}.Treeview.Heading", background=bg, foreground=MUTED,
                            borderwidth=0, relief="flat", font=("Segoe UI", 10),
                            padding=(8, 6))
            style.map(f"{name}.Treeview.Heading", background=[("active", bg)])
            style.layout(f"{name}.Treeview", [(f"{name}.Treeview.treearea", {"sticky": "nswe"})])

    def _btn(self, parent, text, command, width=120, height=34, size=13):
        return ctk.CTkButton(parent, text=text, width=width, height=height, font=self.F(size),
                             fg_color=BTN, hover_color=BTN_HOVER, text_color=TEXT,
                             corner_radius=10, command=command)

    def _card(self, parent, **kw):
        return ctk.CTkFrame(parent, fg_color=PANEL, border_color=BORDER, border_width=1,
                            corner_radius=12, **kw)

    # ------------------------------------------------------------------ шапка
    def _build_header(self):
        hdr = ctk.CTkFrame(self, fg_color="transparent")
        hdr.pack(fill="x", padx=20, pady=(16, 8))

        logo = tk.Canvas(hdr, width=46, height=36, bg=BG, highlightthickness=0)
        logo.create_line(2, 20, 12, 20, 17, 8, 24, 32, 30, 14, 34, 20, 44, 20,
                         fill=GREEN, width=3, capstyle="round", joinstyle="round")
        logo.pack(side="left", padx=(0, 12))

        titles = ctk.CTkFrame(hdr, fg_color="transparent")
        titles.pack(side="left")
        ctk.CTkLabel(titles, text="NETPULSE", font=self.F(24, "bold"),
                     text_color=TEXT).pack(anchor="w")
        ctk.CTkLabel(titles, text="Network Monitor", font=self.F(13),
                     text_color=MUTED).pack(anchor="w")

        # кнопки справа в шапке
        self._btn(hdr, T("settings"), self._open_settings, width=124, height=38
                  ).pack(side="right")
        self._btn(hdr, T("location"), self._choose_dir, width=140, height=38
                  ).pack(side="right", padx=(0, 8))
        self._btn(hdr, T("open"), self._open_logs, width=108, height=38
                  ).pack(side="right", padx=(0, 8))
        self._btn(hdr, T("report"), self._open_report, width=108, height=38
                  ).pack(side="right", padx=(0, 8))

    # ------------------------------------------------------------- управление
    def _build_controls(self):
        bar = self._card(self)
        bar.pack(fill="x", padx=20, pady=(0, 12))
        inner = ctk.CTkFrame(bar, fg_color="transparent")
        inner.pack(fill="x", padx=18, pady=12)

        ctk.CTkLabel(inner, text=T("period"), font=self.F(15),
                     text_color=TEXT).pack(side="left", padx=(0, 16))

        def combo(values, default, suffix, width=72):
            cb = ctk.CTkOptionMenu(inner, values=values, width=width, height=36,
                                   font=self.F(15, "bold"), dropdown_font=self.F(13),
                                   fg_color=PANEL_2, button_color=PANEL_2,
                                   button_hover_color=BORDER, text_color=TEXT,
                                   dropdown_fg_color=PANEL_2, dropdown_hover_color=BORDER,
                                   dropdown_text_color=TEXT, corner_radius=10,
                                   anchor="center", dynamic_resizing=False)
            cb.set(default)
            cb.pack(side="left", padx=(0, 4 if suffix else 10))
            if suffix:
                ctk.CTkLabel(inner, text=suffix, font=self.F(13), text_color=MUTED
                             ).pack(side="left", padx=(0, 12))
            return cb

        self.cb_days = combo([str(i) for i in range(0, 31)], str(self.period[0]), T("u_d"))
        self.cb_hours = combo([str(i) for i in range(0, 24)], str(self.period[1]), T("u_h"))
        self.cb_mins = combo([str(i) for i in range(0, 60, 5)], str(self.period[2]), T("u_m"))

        ctk.CTkFrame(inner, width=1, height=34, fg_color=BORDER).pack(side="left", padx=(2, 12))

        ctk.CTkLabel(inner, text=T("interval"), font=self.F(13), text_color=MUTED
                     ).pack(side="left", padx=(4, 8))
        self.cb_interval = combo([f"{i} {T('sec')}" for i in INTERVALS],
                                 f"{self.interval} {T('sec')}", "", width=92)

        ctk.CTkLabel(inner, text=T("threshold"), font=self.F(13), text_color=MUTED
                     ).pack(side="left", padx=(4, 8))
        self.cb_threshold = combo(THRESHOLDS, str(self.threshold), "", width=64)

        self.btn_start = ctk.CTkButton(inner, text=T("start"), font=self.F(16, "bold"),
                                       fg_color=GREEN, hover_color=GREEN_HOVER,
                                       text_color="white", height=44, width=180,
                                       corner_radius=10, command=self._toggle)
        self.btn_start.pack(side="right")

    # ------------------------------------------------------------- статистика
    def _build_stats(self):
        row = ctk.CTkFrame(self, fg_color="transparent")
        row.pack(fill="x", padx=20, pady=(0, 12))
        for i in range(4):
            row.grid_columnconfigure(i, weight=1, uniform="s")

        def stat(col, title, dot=None):
            c = self._card(row)
            c.grid(row=0, column=col, sticky="nsew",
                   padx=(0 if col == 0 else 6, 0 if col == 3 else 6))
            top = ctk.CTkFrame(c, fg_color="transparent")
            top.pack(anchor="w", padx=20, pady=(12, 0))
            if dot:
                ctk.CTkLabel(top, text="●", text_color=dot, font=self.F(14)).pack(side="left", padx=(0, 8))
            ctk.CTkLabel(top, text=title, font=self.F(13), text_color=MUTED).pack(side="left")
            val = ctk.CTkLabel(c, text="0", font=self.F(28, "bold"), text_color=TEXT)
            val.pack(anchor="w", padx=20, pady=(0, 2))
            sub = ctk.CTkLabel(c, text=" ", font=self.F(11), text_color=MUTED)
            sub.pack(anchor="w", padx=20, pady=(0, 10))
            return val, sub

        self.lbl_online, _ = stat(0, T("online"), GREEN)
        self.lbl_offline, _ = stat(1, T("offline"), RED)
        self.lbl_avail, self.lbl_avail_sub = stat(2, T("availability"))
        self.lbl_uptime, self.lbl_remaining = stat(3, T("uptime"))
        self.lbl_uptime.configure(text="00:00:00")
        self.lbl_remaining.configure(text=T("idle_period"))

    # ------------------------------------------------------------- центральная
    def _build_main(self):
        main = ctk.CTkFrame(self, fg_color="transparent")
        main.pack(fill="both", expand=True, padx=20, pady=(0, 12))
        main.grid_columnconfigure(0, weight=11, uniform="m")
        main.grid_columnconfigure(1, weight=9, uniform="m")
        main.grid_rowconfigure(0, weight=1)

        # ---------- устройства
        left = self._card(main)
        left.grid(row=0, column=0, sticky="nsew", padx=(0, 8))

        head = ctk.CTkFrame(left, fg_color="transparent")
        head.pack(fill="x", padx=20, pady=(14, 6))
        self.lbl_dev_title = ctk.CTkLabel(head, text=T("devices", n=0), font=self.F(17, "bold"),
                                          text_color=TEXT)
        self.lbl_dev_title.pack(side="left")
        self.search = ctk.CTkEntry(head, placeholder_text=T("search"), width=180, height=34,
                                   fg_color=PANEL_2, border_color=BORDER, corner_radius=10,
                                   font=self.F(13))
        self.search.pack(side="right")
        self.search.bind("<KeyRelease>", lambda e: self._refresh_dev_tree())

        tree_wrap = ctk.CTkFrame(left, fg_color="transparent")
        tree_wrap.pack(fill="both", expand=True, padx=(12, 6), pady=(0, 6))
        cols = ("type", "name", "host", "status", "lat")
        self.dev_tree = ttk.Treeview(tree_wrap, columns=cols, show="headings",
                                     style="Dev.Treeview", selectmode="extended", height=6)
        for col, key, w, anchor in (("type", "col_type", 84, "w"), ("name", "col_name", 150, "w"),
                                    ("host", "col_host", 124, "w"),
                                    ("status", "col_status", 96, "w"),
                                    ("lat", "col_lat", 74, "center")):
            self.dev_tree.heading(col, text=T(key), anchor=anchor)
            self.dev_tree.column(col, width=w, minwidth=48, anchor=anchor, stretch=True)
        self.dev_tree.tag_configure("online", foreground=TEXT)
        self.dev_tree.tag_configure("offline", foreground=RED_TEXT)
        self.dev_tree.tag_configure("loss", foreground=YELLOW)
        self.dev_tree.tag_configure("pending", foreground=MUTED)
        sb = ctk.CTkScrollbar(tree_wrap, command=self.dev_tree.yview, fg_color="transparent",
                              button_color=BORDER, button_hover_color=MUTED)
        self.dev_tree.configure(yscrollcommand=sb.set)
        self.dev_tree.pack(side="left", fill="both", expand=True)
        sb.pack(side="right", fill="y")
        self.dev_tree.bind("<Delete>", lambda e: self._remove_selected())

        # панель добавления
        add = ctk.CTkFrame(left, fg_color=PANEL_2, corner_radius=10)
        add.pack(fill="x", padx=12, pady=(0, 12))
        self.ent_name = ctk.CTkEntry(add, placeholder_text=T("ph_name"), height=36,
                                     fg_color=PANEL, border_color=BORDER, font=self.F(13))
        self.ent_name.pack(side="left", fill="x", expand=True, padx=(10, 6), pady=10)
        self.ent_host = ctk.CTkEntry(add, placeholder_text=T("ph_host"), width=140, height=36,
                                     fg_color=PANEL, border_color=BORDER, font=self.F(13))
        self.ent_host.pack(side="left", padx=6, pady=10)
        self.opt_type = ctk.CTkOptionMenu(add, values=[T(f"t_{k}") for k in TYPE_KEYS],
                                          width=118, height=36, fg_color=PANEL,
                                          button_color=PANEL, button_hover_color=BORDER,
                                          font=self.F(13), dropdown_font=self.F(13))
        self.opt_type.set(T("t_pc"))
        self.opt_type.pack(side="left", padx=6, pady=10)
        self.btn_add = ctk.CTkButton(add, text=T("add"), width=96, height=36,
                                     font=self.F(13, "bold"), fg_color="#2563eb",
                                     hover_color="#1d4ed8", command=self._add_device)
        self.btn_add.pack(side="left", padx=6, pady=10)
        self.btn_del = ctk.CTkButton(add, text=T("delete"), width=84, height=36, font=self.F(13),
                                     fg_color=BTN, hover_color=BTN_HOVER,
                                     command=self._remove_selected)
        self.btn_del.pack(side="left", padx=(0, 10), pady=10)
        self.ent_host.bind("<Return>", lambda e: self._add_device())
        self.ent_name.bind("<Return>", lambda e: self.ent_host.focus_set())

        # ---------- обрывы
        right = ctk.CTkFrame(main, fg_color=RED_BG, border_color=RED_BORDER, border_width=1,
                             corner_radius=12)
        right.grid(row=0, column=1, sticky="nsew", padx=(8, 0))
        rhead = ctk.CTkFrame(right, fg_color="transparent")
        rhead.pack(fill="x", padx=20, pady=(14, 6))
        ctk.CTkLabel(rhead, text="⚠", font=self.F(20, "bold"), text_color=RED).pack(side="left", padx=(0, 10))
        self.lbl_out_title = ctk.CTkLabel(rhead, text=T("outages", n=0), font=self.F(17, "bold"),
                                          text_color=RED_TEXT)
        self.lbl_out_title.pack(side="left")
        self.lbl_out_active = ctk.CTkLabel(rhead, text="", font=self.F(12), text_color=RED_TEXT)
        self.lbl_out_active.pack(side="right")

        out_wrap = ctk.CTkFrame(right, fg_color="transparent")
        out_wrap.pack(fill="both", expand=True, padx=(12, 6), pady=(0, 12))
        ocols = ("dev", "start", "end", "dur")
        self.out_tree = ttk.Treeview(out_wrap, columns=ocols, show="headings",
                                     style="Out.Treeview", selectmode="browse", height=6)
        for col, key, w, anchor in (("dev", "col_dev", 150, "w"),
                                    ("start", "col_start", 96, "center"),
                                    ("end", "col_end", 96, "center"),
                                    ("dur", "col_dur", 84, "center")):
            self.out_tree.heading(col, text=T(key), anchor=anchor)
            self.out_tree.column(col, width=w, minwidth=56, anchor=anchor, stretch=True)
        self.out_tree.tag_configure("active", foreground=RED_TEXT, font=("Segoe UI", 11, "bold"))
        self.out_tree.tag_configure("closed", foreground="#c9a3a8")
        osb = ctk.CTkScrollbar(out_wrap, command=self.out_tree.yview, fg_color="transparent",
                               button_color=RED_BORDER, button_hover_color=RED)
        self.out_tree.configure(yscrollcommand=osb.set)
        self.out_tree.pack(side="left", fill="both", expand=True)
        osb.pack(side="right", fill="y")

    # ------------------------------------------------------------- статус-бар
    def _build_statusbar(self):
        sbar = ctk.CTkFrame(self, fg_color=PANEL, corner_radius=0, height=44)
        sbar.pack(fill="x", side="bottom")
        self.lbl_status_dot = ctk.CTkLabel(sbar, text="●", font=self.F(16), text_color=MUTED)
        self.lbl_status_dot.pack(side="left", padx=(22, 8), pady=8)
        self.lbl_status = ctk.CTkLabel(sbar, text=T("st_stopped"), font=self.F(13),
                                       text_color=TEXT)
        self.lbl_status.pack(side="left")

        self.lbl_dir = ctk.CTkLabel(sbar, text="", font=self.F(12), text_color=MUTED)
        self.lbl_dir.pack(side="right", padx=(16, 22))
        self.lbl_info = ctk.CTkLabel(sbar, text="", font=self.F(13), text_color=MUTED)
        self.lbl_info.pack(side="right")
        self._update_dir_label()

    # ================================================================ конфиг
    def _load_config(self):
        global LANG
        try:
            with open(CONFIG_FILE, encoding="utf-8") as f:
                cfg = json.load(f)
        except Exception:
            cfg = {}
        if cfg.get("lang") in LANGS:
            LANG = cfg["lang"]
        for d in cfg.get("devices", []):
            if d.get("host"):
                self.devices.append(self._new_device(d.get("name") or d["host"], d["host"],
                                                     type_key(d.get("type", "other"))))
        p = cfg.get("period", {})
        self.period = [parse_int(p.get("days", 1), 1), parse_int(p.get("hours", 0)),
                       parse_int(p.get("minutes", 0))]
        iv = parse_int(cfg.get("interval", 1), 1)
        self.interval = iv if iv in INTERVALS else 1
        th = str(cfg.get("threshold", "1"))
        self.threshold = int(th) if th in THRESHOLDS else 1
        if cfg.get("export_dir"):
            self.export_dir = cfg["export_dir"]
        self.sound = bool(cfg.get("sound", True))

    def _save_config(self):
        if not self.monitor and hasattr(self, "cb_days"):
            try:
                self._read_controls()
            except tk.TclError:
                pass
        cfg = {
            "lang": LANG,
            "devices": [{"name": d["name"], "host": d["host"], "type": d["type"]} for d in self.devices],
            "period": {"days": self.period[0], "hours": self.period[1], "minutes": self.period[2]},
            "interval": self.interval,
            "threshold": self.threshold,
            "export_dir": self.export_dir,
            "sound": self.sound,
        }
        try:
            with open(CONFIG_FILE, "w", encoding="utf-8") as f:
                json.dump(cfg, f, ensure_ascii=False, indent=2)
        except Exception:
            pass

    # ============================================================= настройки
    def _open_settings(self):
        if self._settings_win and self._settings_win.winfo_exists():
            self._settings_win.lift()
            self._settings_win.focus_force()
            return
        win = ctk.CTkToplevel(self)
        self._settings_win = win
        win.title("NetPulse — " + T("settings_title"))
        win.configure(fg_color=BG)
        win.resizable(False, False)
        win.transient(self)

        ctk.CTkLabel(win, text=T("settings"), font=self.F(20, "bold"),
                     text_color=TEXT).pack(anchor="w", padx=24, pady=(20, 12))
        card = self._card(win)
        card.pack(fill="x", padx=24)

        # --- язык
        ctk.CTkLabel(card, text=T("lang"), font=self.F(13), text_color=MUTED
                     ).pack(anchor="w", padx=18, pady=(16, 6))

        def on_lang(label):
            global LANG
            new = next(k for k, v in LANGS.items() if v == label)
            if new == LANG:
                return
            LANG = new
            self._save_config()
            self._rebuild_ui()
            self.after(150, self._open_settings)

        seg = ctk.CTkSegmentedButton(card, values=list(LANGS.values()), command=on_lang,
                                     font=self.F(14), height=38,
                                     selected_color="#2563eb", selected_hover_color="#1d4ed8",
                                     unselected_color=PANEL_2, unselected_hover_color=BTN_HOVER,
                                     fg_color=PANEL_2)
        seg.set(LANGS[LANG])
        seg.pack(anchor="w", padx=18)

        # --- тема (Dark — текущая, Light — пока заглушка)
        ctk.CTkLabel(card, text=T("theme"), font=self.F(13), text_color=MUTED
                     ).pack(anchor="w", padx=18, pady=(18, 6))
        theme_var = tk.StringVar(value="dark")
        theme_note = ctk.CTkLabel(card, text="", font=self.F(11), text_color=YELLOW)

        def on_light():
            theme_var.set("dark")   # пока остаёмся на тёмной
            theme_note.configure(text=T("light_soon"))
            theme_note.pack(anchor="w", padx=18, pady=(4, 0), after=lrow)

        radio_kw = dict(font=self.F(14), text_color=TEXT, fg_color=GREEN, hover_color=GREEN_HOVER,
                        border_color=MUTED, variable=theme_var)
        ctk.CTkRadioButton(card, text=T("theme_dark"), value="dark", **radio_kw
                           ).pack(anchor="w", padx=18, pady=(0, 8))
        lrow = ctk.CTkFrame(card, fg_color="transparent")
        lrow.pack(anchor="w", padx=18)
        ctk.CTkRadioButton(lrow, text=T("theme_light"), value="light", command=on_light,
                           **radio_kw).pack(side="left")
        ctk.CTkLabel(lrow, text=T("soon"), font=self.F(11), text_color=MUTED, fg_color=PANEL_2,
                     corner_radius=8, width=50, height=20).pack(side="left", padx=(4, 0))

        # --- звук
        def on_sound():
            self.sound = bool(sw.get())
            self._save_config()

        sw = ctk.CTkSwitch(card, text=T("sound"), font=self.F(13), text_color=TEXT,
                           progress_color=GREEN, command=on_sound)
        if self.sound:
            sw.select()
        sw.pack(anchor="w", padx=18, pady=(18, 6))

        # --- папка
        ctk.CTkLabel(card, text=T("folder"), font=self.F(13), text_color=MUTED
                     ).pack(anchor="w", padx=18, pady=(14, 6))
        frow = ctk.CTkFrame(card, fg_color="transparent")
        frow.pack(fill="x", padx=18, pady=(0, 18))
        dir_lbl = ctk.CTkLabel(frow, text=short_path(self.export_dir, 44), font=self.F(12),
                               text_color=TEXT, anchor="w", width=340)
        dir_lbl.pack(side="left", fill="x", expand=True)

        def change_dir():
            self._choose_dir(parent=win)
            dir_lbl.configure(text=short_path(self.export_dir, 44))

        self._btn(frow, T("location"), change_dir, width=160).pack(side="right", padx=(10, 0))

        self._btn(win, T("close"), win.destroy, width=120, height=40
                  ).pack(anchor="e", padx=24, pady=(16, 20))

        def focus():
            if win.winfo_exists():
                win.lift()
                win.focus_force()
        win.after(200, focus)

    # ============================================================= устройства
    @staticmethod
    def _new_device(name, host, dtype):
        return {"id": uuid.uuid4().hex[:10], "name": name, "host": host, "type": dtype,
                "status": "pending", "lat": None, "ok": 0, "total": 0, "streak": 0,
                "first_fail": None, "outage": None, "outage_count": 0, "downtime": 0.0}

    def _add_device(self):
        if self.monitor:
            return
        host = self.ent_host.get().strip()
        name = self.ent_name.get().strip() or host
        if not host or " " in host:
            messagebox.showwarning("NetPulse", T("bad_host"))
            return
        if any(d["host"].lower() == host.lower() for d in self.devices):
            messagebox.showwarning("NetPulse", T("dup_host", h=host))
            return
        self.devices.append(self._new_device(name, host, type_key(self.opt_type.get())))
        self.ent_name.delete(0, "end")
        self.ent_host.delete(0, "end")
        self.ent_name.focus_set()
        self._save_config()
        self._refresh_dev_tree()
        self._update_stats()

    def _remove_selected(self):
        if self.monitor:
            return
        sel = set(self.dev_tree.selection())
        if not sel:
            return
        self.devices = [d for d in self.devices if d["id"] not in sel]
        self._save_config()
        self._refresh_dev_tree()
        self._update_stats()

    def _dev_values(self, d):
        dot = "○" if d["status"] == "pending" else "●"
        status = f"{dot}  {T(d['status'])}"
        if d["lat"] is None:
            lat = "—"
        elif d["lat"] < 1:
            lat = f"<1 {T('ms')}"
        else:
            lat = f"{d['lat']:.0f} {T('ms')}"
        return (T(f"t_{d['type']}"), d["name"], d["host"], status, lat)

    def _refresh_dev_tree(self):
        q = self.search.get().strip().lower()
        self.dev_tree.delete(*self.dev_tree.get_children())
        for d in self.devices:
            if q and q not in f"{d['name']} {d['host']} {T('t_' + d['type'])}".lower():
                continue
            self.dev_tree.insert("", "end", iid=d["id"], values=self._dev_values(d),
                                 tags=(d["status"],))
        self.lbl_dev_title.configure(text=T("devices", n=len(self.devices)))

    def _update_dev_row(self, d):
        if self.dev_tree.exists(d["id"]):
            self.dev_tree.item(d["id"], values=self._dev_values(d), tags=(d["status"],))

    # ============================================================== обрывы (UI)
    @staticmethod
    def _out_values(rec, now=None):
        d = rec["dev"]
        end = rec["end"]
        dur = ((end or now or datetime.now()) - rec["start"]).total_seconds()
        return (f"{d['name']} · {d['host']}", fmt_ts(rec["start"]),
                fmt_ts(end) if end else T("no_link"), fmt_dur(dur))

    def _populate_outages(self):
        self.out_tree.delete(*self.out_tree.get_children())
        for rec in self.outages:   # по порядку, каждая новая — наверх
            rec["iid"] = self.out_tree.insert("", 0, values=self._out_values(rec),
                                              tags=("closed" if rec["end"] else "active",))

    # ============================================================ старт/стоп
    def _toggle(self):
        if self.monitor:
            if messagebox.askyesno("NetPulse", T("ask_stop")):
                self._stop(T("r_user"))
        else:
            self._start()

    def _apply_running_state(self):
        running = self.monitor is not None
        state = "disabled" if running else "normal"
        for w in (self.ent_name, self.ent_host, self.opt_type, self.btn_add, self.btn_del,
                  self.cb_days, self.cb_hours, self.cb_mins, self.cb_interval, self.cb_threshold):
            w.configure(state=state)
        if running:
            self.btn_start.configure(text=T("stop"), fg_color=RED, hover_color=RED_HOVER)
            self.lbl_status.configure(text=T("st_active"))
        else:
            self.btn_start.configure(text=T("start"), fg_color=GREEN, hover_color=GREEN_HOVER)
            self.lbl_status_dot.configure(text_color=MUTED)

    def _start(self):
        if not self.devices:
            messagebox.showwarning("NetPulse", T("no_devices"))
            return
        self._read_controls()
        days, hours, mins = self.period
        period = timedelta(days=days, hours=hours, minutes=mins)
        self._save_config()

        # сброс
        for d in self.devices:
            d.update(status="pending", lat=None, ok=0, total=0, streak=0, first_fail=None,
                     outage=None, outage_count=0, downtime=0.0)
        self.outages.clear()
        self.out_tree.delete(*self.out_tree.get_children())
        self._refresh_dev_tree()

        self.start_time = datetime.now()
        self.end_time = self.start_time + period if period.total_seconds() > 0 else None

        # лог
        try:
            os.makedirs(LOG_DIR, exist_ok=True)
            self.log_path = os.path.join(
                LOG_DIR, f"netpulse_{self.start_time:%Y-%m-%d_%H-%M-%S}.log")
            self._log_fh = open(self.log_path, "a", encoding="utf-8")
        except Exception as exc:
            messagebox.showerror("NetPulse", T("err_log", p=LOG_DIR, e=exc))
            self.log_path, self._log_fh = None, None
            return
        period_txt = (T("period_fmt", d=days, h=hours, m=mins,
                        end=f"{self.end_time:%d.%m.%Y %H:%M:%S}")
                      if self.end_time else T("period_inf"))
        self._log_raw("=" * 78)
        self._log_raw("  " + T("log_started", t=f"{self.start_time:%d.%m.%Y %H:%M:%S}"))
        self._log_raw("  " + T("log_period", p=period_txt))
        self._log_raw("  " + T("log_interval", i=self.interval, n=self.threshold))
        self._log_raw("  " + T("log_devices"))
        for d in self.devices:
            self._log_raw(f"    - {d['name']} ({d['host']}) [{T('t_' + d['type'])}]")
        self._log_raw("=" * 78)

        self.session += 1
        self.monitor = Monitor(self.session, [(d["id"], d["host"]) for d in self.devices],
                               self.interval, self.q)
        self.monitor.start()
        keep_awake(True)

        self._apply_running_state()
        self.lbl_status_dot.configure(text_color=GREEN)
        self._update_stats()
        self._tick_labels()

    def _stop(self, reason, show_summary=True):
        if not self.monitor:
            return
        self.monitor.stop()
        self.monitor = None
        keep_awake(False)
        now = datetime.now()

        for d in self.devices:
            if d["outage"]:
                rec = d["outage"]
                dur = (now - rec["start"]).total_seconds()
                self._log(T("ev_open"), T("msg_open", dev=f"{d['name']} ({d['host']})",
                                          dur=fmt_dur(dur), s=fmt_ts(rec["start"])))
                d["downtime"] += dur

        summary = self._write_summary(now, reason)
        report = self._build_report(now, reason)
        # автокопия в JSON рядом с .log (на случай, если отчёт не сохранят вручную)
        try:
            with open(os.path.splitext(self.log_path)[0] + ".json", "w", encoding="utf-8") as f:
                json.dump(report, f, ensure_ascii=False, indent=2)
        except Exception:
            pass

        self._apply_running_state()
        self.lbl_status.configure(text=T("st_finished", r=reason))
        self._update_stats()
        if self._log_fh:
            self._log_fh.close()
            self._log_fh = None
        if show_summary:
            self._show_summary_dialog(summary, report)

    def _write_summary(self, now, reason):
        total_ok = sum(d["ok"] for d in self.devices)
        total = sum(d["total"] for d in self.devices)
        avail = (total_ok / total * 100) if total else 0
        lines = [
            T("sum_mon", r=reason, t=f"{now:%d.%m.%Y %H:%M:%S}"),
            T("sum_dur", d=fmt_dur((now - self.start_time).total_seconds())),
            T("sum_avail", a=avail),
            T("sum_out", n=len(self.outages)),
        ]
        c = T("sum_cols")
        self._log_raw("")
        self._log_raw("=" * 78)
        self._log_raw("  " + T("sum_title"))
        for line in lines:
            self._log_raw("  " + line)
        self._log_raw("")
        self._log_raw(f"  {c[0]:<24}{c[1]:<20}{c[2]:>10}{c[3]:>9}{c[4]:>14}")
        for d in self.devices:
            a = (d["ok"] / d["total"] * 100) if d["total"] else 0
            self._log_raw(f"  {d['name'][:23]:<24}{d['host'][:19]:<20}{a:>9.2f}%"
                          f"{d['outage_count']:>9}{fmt_dur(d['downtime']):>14}")
        self._log_raw("=" * 78)
        return "\n".join(lines)

    def _build_report(self, now, reason):
        def iso(dt):
            return dt.isoformat(timespec="seconds") if dt else None

        total_ok = sum(d["ok"] for d in self.devices)
        total = sum(d["total"] for d in self.devices)
        dur = (now - self.start_time).total_seconds()
        devices = []
        for d in self.devices:
            devices.append({
                "name": d["name"], "host": d["host"], "type": d["type"],
                "pings_ok": d["ok"], "pings_total": d["total"],
                "availability_pct": round(d["ok"] / d["total"] * 100, 2) if d["total"] else 0,
                "outages": d["outage_count"],
                "downtime_sec": int(d["downtime"]), "downtime": fmt_dur(d["downtime"]),
            })
        outages = []
        for r in self.outages:
            o_dur = ((r["end"] or now) - r["start"]).total_seconds()
            outages.append({
                "name": r["dev"]["name"], "host": r["dev"]["host"], "type": r["dev"]["type"],
                "start": iso(r["start"]), "end": iso(r["end"]), "ongoing": r["end"] is None,
                "duration_sec": int(o_dur), "duration": fmt_dur(o_dur),
            })
        return {
            "app": "NetPulse",
            "format_version": 1,
            "language": LANG,
            "session": {
                "started": iso(self.start_time), "finished": iso(now),
                "planned_end": iso(self.end_time), "stop_reason": reason,
                "duration_sec": int(dur), "duration": fmt_dur(dur),
                "interval_sec": self.interval, "loss_threshold": self.threshold,
            },
            "summary": {
                "availability_pct": round(total_ok / total * 100, 2) if total else 0,
                "pings_ok": total_ok, "pings_total": total,
                "outages_total": len(self.outages),
                "outages_unresolved": sum(1 for r in self.outages if r["end"] is None),
            },
            "devices": devices,
            "outages": outages,
        }

    # ===================================================== окно итога / сохранение
    def _show_summary_dialog(self, summary, report):
        log_src = self.log_path
        dlg = ctk.CTkToplevel(self)
        dlg.title(T("dlg_title"))
        dlg.configure(fg_color=BG)
        dlg.resizable(False, False)
        dlg.transient(self)

        ctk.CTkLabel(dlg, text=T("dlg_done"), font=self.F(20, "bold"),
                     text_color=TEXT).pack(anchor="w", padx=24, pady=(20, 10))
        box = self._card(dlg)
        box.pack(fill="x", padx=24)
        ctk.CTkLabel(box, text=summary, justify="left", font=self.F(13),
                     text_color=TEXT).pack(anchor="w", padx=16, pady=12)

        # --- имя файла
        hint = ctk.CTkLabel(dlg, text=T("dlg_hint"), font=self.F(12), text_color=MUTED)
        hint.pack(anchor="w", padx=24, pady=(18, 4))

        def validate(proposed):
            ok = bool(SAFE_NAME_RE.fullmatch(proposed))
            hint.configure(text_color=MUTED if ok else RED)
            if not ok:
                dlg.bell()
            return ok

        name_var = tk.StringVar(value=f"netpulse_{self.start_time:%Y-%m-%d_%H-%M}")
        ent = ctk.CTkEntry(dlg, textvariable=name_var, width=460, height=38, font=self.F(14),
                           fg_color=PANEL_2, border_color=BORDER, validate="key",
                           validatecommand=(dlg.register(validate), "%P"))
        ent.pack(anchor="w", padx=24)
        ctk.CTkLabel(dlg, text=T("dlg_files"), font=self.F(11), text_color=MUTED
                     ).pack(anchor="w", padx=24, pady=(4, 0))

        # --- подсказка: отчётами можно делиться
        note = ctk.CTkFrame(dlg, fg_color="#0f1a2b", border_color="#1e3a5f", border_width=1,
                            corner_radius=10)
        note.pack(fill="x", padx=24, pady=(14, 0))
        ctk.CTkLabel(note, text="ℹ", font=self.F(16, "bold"), text_color="#60a5fa", width=20
                     ).pack(side="left", anchor="n", padx=(12, 6), pady=10)
        ctk.CTkLabel(note, text=T("share_note"), font=self.F(12), text_color="#c7d7ee",
                     justify="left", anchor="w", wraplength=400
                     ).pack(side="left", fill="x", expand=True, padx=(0, 12), pady=10)

        # --- папка
        drow = ctk.CTkFrame(dlg, fg_color="transparent")
        drow.pack(fill="x", padx=24, pady=(14, 0))
        dir_lbl = ctk.CTkLabel(drow, text=short_path(self.export_dir, 46),
                               font=self.F(12), text_color=TEXT, anchor="w")
        dir_lbl.pack(side="left", fill="x", expand=True)

        def change_dir():
            self._choose_dir(parent=dlg)
            dir_lbl.configure(text=short_path(self.export_dir, 46))

        self._btn(drow, T("location"), change_dir, width=160, height=32, size=12).pack(side="right")

        # --- кнопки
        brow = ctk.CTkFrame(dlg, fg_color="transparent")
        brow.pack(fill="x", padx=24, pady=(20, 22))

        def save():
            name = name_var.get().strip().strip(".")
            if not name:
                messagebox.showwarning("NetPulse", T("need_name"), parent=dlg)
                return
            log_dst = os.path.join(self.export_dir, name + ".log")
            json_dst = os.path.join(self.export_dir, name + ".json")
            if (os.path.exists(log_dst) or os.path.exists(json_dst)) and not messagebox.askyesno(
                    "NetPulse", T("overwrite", n=name), parent=dlg):
                return
            try:
                os.makedirs(self.export_dir, exist_ok=True)
                if os.path.abspath(log_src) != os.path.abspath(log_dst):
                    shutil.copyfile(log_src, log_dst)
                with open(json_dst, "w", encoding="utf-8") as f:
                    json.dump(report, f, ensure_ascii=False, indent=2)
            except Exception as e:
                messagebox.showerror("NetPulse", T("save_err", e=e), parent=dlg)
                return
            self.log_path = log_dst
            messagebox.showinfo("NetPulse", T("saved", a=log_dst, b=json_dst), parent=dlg)
            dlg.destroy()

        ctk.CTkButton(brow, text=T("save"), width=180, height=42, font=self.F(15, "bold"),
                      fg_color=GREEN, hover_color=GREEN_HOVER, text_color="white",
                      command=save).pack(side="right")
        self._btn(brow, T("close"), dlg.destroy, width=110, height=42).pack(side="right", padx=(0, 10))

        ent.bind("<Return>", lambda e: save())

        def focus():
            if not dlg.winfo_exists():
                return
            dlg.lift()
            dlg.focus_force()
            ent.focus_set()
            ent.select_range(0, "end")
            try:
                dlg.grab_set()
            except tk.TclError:
                pass
        dlg.after(200, focus)

    def _update_dir_label(self):
        self.lbl_dir.configure(text=T("folder_lbl", p=short_path(self.export_dir, 38)))

    def _choose_dir(self, parent=None):
        d = filedialog.askdirectory(parent=parent or self,
                                    initialdir=self.export_dir if os.path.isdir(self.export_dir) else APP_DIR,
                                    title=T("choose_dir"))
        if d:
            self.export_dir = os.path.normpath(d)
            self._save_config()
            self._update_dir_label()

    # ======================================================= просмотр отчётов
    def _open_report(self, path=None):
        if not path:
            path = filedialog.askopenfilename(
                parent=self, title=T("open_report"),
                initialdir=self.export_dir if os.path.isdir(self.export_dir) else APP_DIR,
                filetypes=[("NetPulse", "*.json *.log"), ("JSON", "*.json"), ("Log", "*.log")])
        if not path:
            return
        base = os.path.splitext(path)[0]
        if path.lower().endswith(".log"):
            if os.path.exists(base + ".json"):
                path = base + ".json"
            else:
                self._show_log_window(path)
                return
        try:
            with open(path, encoding="utf-8") as f:
                rep = json.load(f)
            if rep.get("app") != "NetPulse":
                raise ValueError("app != NetPulse")
            self._show_report_window(path, rep)
        except Exception as e:
            messagebox.showerror("NetPulse", T("bad_report", e=e))

    @staticmethod
    def _iso_fmt(value):
        if not value:
            return "—"
        try:
            return datetime.fromisoformat(value).strftime("%d.%m.%Y %H:%M:%S")
        except Exception:
            return str(value)

    def _show_log_window(self, path):
        win = ctk.CTkToplevel(self)
        win.title(os.path.basename(path))
        win.configure(fg_color=BG)
        win.geometry("900x600")
        box = ctk.CTkTextbox(win, font=ctk.CTkFont(family="Consolas", size=13), fg_color=PANEL,
                             text_color=TEXT, border_color=BORDER, border_width=1, wrap="none")
        box.pack(fill="both", expand=True, padx=16, pady=16)
        try:
            with open(path, encoding="utf-8", errors="replace") as f:
                box.insert("1.0", f.read())
        except Exception as e:
            box.insert("1.0", str(e))
        box.configure(state="disabled")
        win.after(200, lambda: win.winfo_exists() and (win.lift(), win.focus_force()))

    def _show_report_window(self, path, rep):
        s = rep.get("session", {})
        summ = rep.get("summary", {})
        win = ctk.CTkToplevel(self)
        win.title("NetPulse — " + T("rep_title", n=os.path.basename(path)))
        win.configure(fg_color=BG)
        win.geometry("1100x720")
        win.minsize(900, 560)

        top = ctk.CTkFrame(win, fg_color="transparent")
        top.pack(fill="x", padx=20, pady=(18, 4))
        ctk.CTkLabel(top, text=T("rep_title", n=os.path.basename(path)), font=self.F(20, "bold"),
                     text_color=TEXT).pack(side="left")
        log_path = os.path.splitext(path)[0] + ".log"
        if os.path.exists(log_path):
            self._btn(top, T("show_log"), lambda: self._show_log_window(log_path), width=150
                      ).pack(side="right")

        ctk.CTkLabel(win, text=T("rep_reason", r=s.get("stop_reason", "—"),
                                 i=s.get("interval_sec", "—"), t=s.get("loss_threshold", "—")),
                     font=self.F(12), text_color=MUTED).pack(anchor="w", padx=20, pady=(0, 10))

        # карточки
        row = ctk.CTkFrame(win, fg_color="transparent")
        row.pack(fill="x", padx=20, pady=(0, 12))
        cards = [(T("rep_started"), self._iso_fmt(s.get("started"))),
                 (T("rep_finished"), self._iso_fmt(s.get("finished"))),
                 (T("rep_duration"), s.get("duration", "—")),
                 (T("rep_avail"), f"{summ.get('availability_pct', 0)} %"),
                 (T("rep_outages"), str(summ.get("outages_total", 0)))]
        for i, (title, value) in enumerate(cards):
            row.grid_columnconfigure(i, weight=1, uniform="r")
            c = self._card(row)
            c.grid(row=0, column=i, sticky="nsew", padx=(0 if i == 0 else 5, 0 if i == len(cards) - 1 else 5))
            ctk.CTkLabel(c, text=title, font=self.F(12), text_color=MUTED).pack(anchor="w", padx=16, pady=(10, 0))
            color = RED_TEXT if title == T("rep_outages") and value != "0" else TEXT
            ctk.CTkLabel(c, text=value, font=self.F(17, "bold"), text_color=color
                         ).pack(anchor="w", padx=16, pady=(0, 10))

        body = ctk.CTkFrame(win, fg_color="transparent")
        body.pack(fill="both", expand=True, padx=20, pady=(0, 18))
        body.grid_columnconfigure(0, weight=1, uniform="b")
        body.grid_columnconfigure(1, weight=1, uniform="b")
        body.grid_rowconfigure(0, weight=1)

        def table(parent, style, cols, rows, title, title_color):
            ctk.CTkLabel(parent, text=title, font=self.F(15, "bold"), text_color=title_color
                         ).pack(anchor="w", padx=16, pady=(12, 4))
            wrap = ctk.CTkFrame(parent, fg_color="transparent")
            wrap.pack(fill="both", expand=True, padx=(10, 6), pady=(0, 10))
            tv = ttk.Treeview(wrap, columns=[c[0] for c in cols], show="headings", style=style)
            for key, head, w, anchor in cols:
                tv.heading(key, text=head, anchor=anchor)
                tv.column(key, width=w, minwidth=50, anchor=anchor, stretch=True)
            sb = ctk.CTkScrollbar(wrap, command=tv.yview, fg_color="transparent",
                                  button_color=BORDER, button_hover_color=MUTED)
            tv.configure(yscrollcommand=sb.set)
            tv.pack(side="left", fill="both", expand=True)
            sb.pack(side="right", fill="y")
            for values, tag in rows:
                tv.insert("", "end", values=values, tags=(tag,))
            tv.tag_configure("bad", foreground=RED_TEXT)
            tv.tag_configure("ok", foreground=TEXT)
            tv.tag_configure("active", foreground=RED_TEXT, font=("Segoe UI", 11, "bold"))
            tv.tag_configure("closed", foreground="#c9a3a8")
            return tv

        left = self._card(body)
        left.grid(row=0, column=0, sticky="nsew", padx=(0, 6))
        dev_rows = []
        for d in rep.get("devices", []):
            dev_rows.append(((d.get("name", ""), d.get("host", ""),
                              f"{d.get('availability_pct', 0)} %", d.get("outages", 0),
                              d.get("downtime", "")),
                             "bad" if d.get("outages") else "ok"))
        table(left, "Dev.Treeview",
              [("name", T("col_name"), 140, "w"), ("host", T("col_host"), 120, "w"),
               ("avail", T("col_avail"), 90, "center"), ("out", T("col_outages"), 70, "center"),
               ("down", T("col_downtime"), 90, "center")],
              dev_rows, T("rep_devices"), TEXT)

        right = ctk.CTkFrame(body, fg_color=RED_BG, border_color=RED_BORDER, border_width=1,
                             corner_radius=12)
        right.grid(row=0, column=1, sticky="nsew", padx=(6, 0))
        out_rows = []
        for o in reversed(rep.get("outages", [])):
            end = T("rep_ongoing") if o.get("ongoing") else self._iso_fmt(o.get("end"))
            out_rows.append(((f"{o.get('name', '')} · {o.get('host', '')}",
                              self._iso_fmt(o.get("start")), end, o.get("duration", "")),
                             "active" if o.get("ongoing") else "closed"))
        table(right, "Out.Treeview",
              [("dev", T("col_dev"), 170, "w"), ("start", T("col_start"), 140, "center"),
               ("end", T("col_end"), 140, "center"), ("dur", T("col_dur"), 90, "center")],
              out_rows, T("rep_out_list") + f" ({len(out_rows)})", RED_TEXT)
        if not out_rows:
            ctk.CTkLabel(right, text=T("rep_none"), font=self.F(14), text_color=MUTED
                         ).place(relx=0.5, rely=0.5, anchor="center")

        win.after(200, lambda: win.winfo_exists() and (win.lift(), win.focus_force()))

    # ================================================================ логи
    def _log_raw(self, line):
        if self._log_fh:
            self._log_fh.write(line + "\n")
            self._log_fh.flush()

    def _log(self, kind, text, ts=None):
        ts = ts or datetime.now()
        self._log_raw(f"[{ts:%d.%m.%Y %H:%M:%S}]  {kind:<16} {text}")

    def _open_logs(self):
        target = self.export_dir
        try:
            os.makedirs(target, exist_ok=True)
            if IS_WIN:
                os.startfile(target)
            else:
                subprocess.Popen(["xdg-open", target])
        except Exception as e:
            messagebox.showerror("NetPulse", str(e))

    # ======================================================== обработка пинга
    def _drain_queue(self):
        try:
            changed = False
            for _ in range(2000):
                try:
                    session, dev_id, ok, lat, ts = self.q.get_nowait()
                except queue.Empty:
                    break
                if not self.monitor or session != self.session:
                    continue
                d = next((x for x in self.devices if x["id"] == dev_id), None)
                if d:
                    self._on_result(d, ok, lat, ts)
                    changed = True
            if changed:
                self._update_stats()
        finally:
            self.after(150, self._drain_queue)

    def _on_result(self, d, ok, lat, ts):
        d["total"] += 1
        if ok:
            d["ok"] += 1
            d["lat"] = lat
            if d["outage"]:
                self._close_outage(d, ts)
            d["status"] = "online"
            d["streak"] = 0
            d["first_fail"] = None
        else:
            d["lat"] = None
            d["streak"] += 1
            if d["streak"] == 1:
                d["first_fail"] = ts
            if d["outage"] is None and d["streak"] >= self.threshold:
                self._open_outage(d, d["first_fail"])
            d["status"] = "offline" if d["outage"] else "loss"
        self._update_dev_row(d)

    def _open_outage(self, d, start):
        rec = {"dev": d, "start": start, "end": None}
        rec["iid"] = self.out_tree.insert("", 0, values=self._out_values(rec), tags=("active",))
        self.outages.append(rec)
        d["outage"] = rec
        d["outage_count"] += 1
        self._log(T("ev_down"), T("msg_down", dev=f"{d['name']} ({d['host']})"), start)
        if self.sound:
            beep()

    def _close_outage(self, d, end):
        rec = d["outage"]
        rec["end"] = end
        dur = (end - rec["start"]).total_seconds()
        d["downtime"] += dur
        d["outage"] = None
        if self.out_tree.exists(rec["iid"]):
            self.out_tree.item(rec["iid"], values=self._out_values(rec), tags=("closed",))
        self._log(T("ev_up"), T("msg_up", dev=f"{d['name']} ({d['host']})", dur=fmt_dur(dur),
                                s=f"{rec['start']:%H:%M:%S}", e=f"{end:%H:%M:%S}"), end)

    # ============================================================== таймеры
    def _tick(self):
        try:
            if self.monitor:
                self._tick_labels()
                if self.end_time and datetime.now() >= self.end_time:
                    self._stop(T("r_timer"))
        finally:
            self.after(1000, self._tick)

    def _tick_labels(self):
        now = datetime.now()
        self.lbl_uptime.configure(text=fmt_dur((now - self.start_time).total_seconds()))
        if self.end_time:
            self.lbl_remaining.configure(
                text=T("remaining", left=fmt_dur((self.end_time - now).total_seconds()),
                       end=f"{self.end_time:%d.%m %H:%M}"))
        else:
            self.lbl_remaining.configure(text=T("unlimited"))
        for rec in self.outages:
            if rec["end"] is None and self.out_tree.exists(rec["iid"]):
                self.out_tree.item(rec["iid"], values=self._out_values(rec, now))

    def _update_stats(self):
        online = sum(1 for d in self.devices if d["status"] == "online")
        offline = sum(1 for d in self.devices if d["status"] == "offline")
        ok = sum(d["ok"] for d in self.devices)
        total = sum(d["total"] for d in self.devices)
        self.lbl_online.configure(text=str(online))
        self.lbl_offline.configure(text=str(offline))
        self.lbl_avail.configure(text=f"{ok / total * 100:.1f} %" if total else "— %")
        self.lbl_avail_sub.configure(text=T("pings_ok", ok=ok, total=total) if total else " ")

        active = sum(1 for r in self.outages if r["end"] is None)
        self.lbl_out_title.configure(text=T("outages", n=len(self.outages)))
        self.lbl_out_active.configure(text=T("active_now", n=active) if active else "")
        self.title(T("title_offline", n=offline) if offline else "NetPulse — Network Monitor")

        interval = self.interval if self.monitor else (parse_int(self.cb_interval.get(), 1) or 1)
        self.lbl_info.configure(text=T("info", i=interval, n=len(self.devices)))
        if self.monitor:
            self.lbl_status_dot.configure(text_color=RED if offline else GREEN)

    # ============================================================== закрытие
    def _on_close(self):
        if self.monitor:
            if not messagebox.askyesno("NetPulse", T("ask_exit")):
                return
            self._stop(T("r_close"), show_summary=False)
        self._save_config()
        self.destroy()


if __name__ == "__main__":
    NetPulseApp().mainloop()
