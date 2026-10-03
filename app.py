"""托盘窗口版：设置每天的预约计划，到点启动现有 main.py。"""

import ctypes
from ctypes import wintypes
from datetime import datetime, timedelta
import json
import os
from pathlib import Path
from queue import Empty, SimpleQueue
import re
import subprocess
import sys
import threading
import time
import tkinter as tk
from tkinter import messagebox, ttk
from tkinter.scrolledtext import ScrolledText

import pyautogui
import pystray
from PIL import Image, ImageDraw

from calibration import PROFILE_PATH, estimate_slider_start, load_profile
from calibration_ui import CalibrationWindow
from license_client import (APP_VERSION, CHECK_INTERVAL_SECONDS, LicenseError,
                            UpdateRequired, check_license, download_update)


APP_NAME = "羽约助手"
APP_DIR = Path(os.environ.get("LOCALAPPDATA", Path.home())) / "WechatBookingBot"
SETTINGS_FILE = APP_DIR / "settings.json"
LOG_FILE = APP_DIR / "scheduled_run.log"
PROJECT = (
    Path(sys.executable).resolve().parent
    if getattr(sys, "frozen", False)
    else Path(__file__).resolve().parent
)
TIME_MODES = {
    "19:00-21:00": (["19:00-20:00", "20:00-21:00"], False),
    "仅19:00-20:00": (["19:00-20:00"], False),
    "仅20:00-21:00": (["20:00-21:00"], False),
    "10:30-12:30": (["10:30-11:30", "11:30-12:30"], False),
    "仅10:30-11:30": (["10:30-11:30"], False),
    "仅11:30-12:30": (["11:30-12:30"], False),
}


def validate_settings(court_text, time_mode, start_time):
    if time_mode in ("晚场", "晚场（先20点、后19点）"):
        time_mode = "19:00-21:00"  # 兼容已保存的旧版设置。
    if not re.fullmatch(r"\d{1,2}", court_text.strip()):
        raise ValueError("场地号必须是 1～17 的整数")
    court = int(court_text)
    if not 1 <= court <= 17:
        raise ValueError("场地号必须是 1～17 的整数")
    if time_mode not in TIME_MODES:
        raise ValueError("请选择预约时段")
    if start_time is not None:  # 测试运行不使用定时输入。
        start_time = start_time.strip()
        if not re.fullmatch(r"\d{2}:\d{2}:\d{2}", start_time):
            raise ValueError("启动时间请填写 HH:MM:SS，例如 07:59:40")
        try:
            datetime.strptime(start_time, "%H:%M:%S")
        except ValueError as error:
            raise ValueError("启动时间无效，请填写 00:00:00～23:59:59") from error
    return {"court": court, "time_mode": time_mode, "start_time": start_time}


def next_start(now, start_time):
    hour, minute, second = map(int, start_time.split(":"))
    target = now.replace(hour=hour, minute=minute, second=second, microsecond=0)
    return target if target > now else target + timedelta(days=1)


def calibration_warnings(required_times=()):
    profile = load_profile()
    missing = set(required_times) - set(profile["TIME_Y"])
    if missing:
        raise ValueError(f"所选时段 {', '.join(sorted(missing))} 尚未校准，请重新校准坐标")
    width, height = pyautogui.size()
    for name in ("ENTRY_WINDOW_RECT", "BOOKING_WINDOW_RECT", "ENTRY_CHECK_REGION",
                 "PAGE_CHECK_REGION"):
        x, y, w, h = profile[name]
        if x + w <= 0 or y + h <= 0 or x >= width or y >= height:
            raise ValueError(f"当前屏幕容不下校准的 {name}，请重新校准")
        if name.endswith("CHECK_REGION") and (x < 0 or y < 0 or x + w > width or y + h > height):
            raise ValueError(f"{name} 超出当前屏幕，请重新校准")
    for name in ("BADMINTON_POS", "TOMORROW_POS", "TOMORROW_SELECTED_POS",
                 "REFRESH_POS", "SUBMIT_POS", "SUBMIT_STATE_POS", "VERIFY_PIXEL_POS"):
        x, y = profile[name]
        if not (0 <= x < width and 0 <= y < height):
            raise ValueError(f"{name} 超出当前屏幕，请重新校准")
    slider_x, slider_y = profile.get(
        "SLIDER_START_POS", estimate_slider_start(profile["BOOKING_WINDOW_RECT"])
    )
    if not (0 <= slider_x < width and 0 <= slider_y < height):
        raise ValueError("滑块起点超出当前屏幕，请重新校准")
    offset_x, offset_y = profile["COURT_CLICK_OFFSET"]
    if any(not 0 <= x + offset_x < width for x in profile["COURT_X"].values()):
        raise ValueError("场地列超出当前屏幕，请重新校准")
    if any(not 0 <= y + offset_y < height for y in profile["TIME_Y"].values()):
        raise ValueError("时段行超出当前屏幕，请重新校准")
    if tuple(profile["SCREEN_SIZE"]) != (width, height):
        return ["屏幕分辨率与校准时不同，请核对点击位置并重新校准。"]
    return []


class BookingWindow:
    def __init__(self):
        self.root = tk.Tk()
        self.root.title(APP_NAME)
        self.root.configure(bg="#F6F8FC")
        self.root.minsize(720, 600)
        self.root.columnconfigure(0, weight=1)
        self.root.rowconfigure(0, weight=1)
        self.root.protocol("WM_DELETE_WINDOW", self.close)
        self.armed = False
        self.child = None
        self.target = None
        self.settings = None
        self.warnings = []
        self.log_pending = False
        self.log_offset = None
        self.result = None
        self.tray_actions = SimpleQueue()
        self.license_results = SimpleQueue()
        self.update_results = SimpleQueue()
        self.update_required = None
        self.update_downloading = False
        self.license_allowed = False
        self.license_checking = False
        self.license_next_check = 0.0

        self.court = tk.StringVar(value="17")
        self.time_mode = tk.StringVar(value=next(iter(TIME_MODES)))
        self.start_time = tk.StringVar(value="07:59:40")
        self.status = tk.StringVar(value="未启动")
        self.license_status = tk.StringVar(value="● 许可检查中")

        style = ttk.Style(self.root)
        style.configure("Booking.TButton", font=("Microsoft YaHei UI", 10), padding=(10, 7))

        frame = tk.Frame(self.root, bg="#F6F8FC", padx=20, pady=16)
        frame.grid(sticky="nsew")
        frame.columnconfigure(0, weight=1)
        tk.Label(frame, text=f"{APP_NAME}  v{APP_VERSION}", bg="#F6F8FC", fg="#18253B",
                 font=("Microsoft YaHei UI", 18, "bold")).grid(row=0, column=0, sticky="w")
        license_area = tk.Frame(frame, bg="#F6F8FC")
        license_area.grid(row=0, column=0, sticky="e")
        self.license_badge = tk.Label(
            license_area, textvariable=self.license_status, bg="#FFF3D9", fg="#8A6217",
            padx=10, pady=5, font=("Microsoft YaHei UI", 9, "bold"),
        )
        self.license_badge.pack(side="left")
        self.update_button = ttk.Button(
            license_area, text="下载新版", command=self.request_update_download,
            style="Booking.TButton",
        )
        tk.Label(frame, text="每天定时预约，也可立即测试完整流程", bg="#F6F8FC", fg="#66758A",
                 font=("Microsoft YaHei UI", 9)).grid(row=1, column=0, sticky="w", pady=(0, 12))

        notice = tk.Frame(frame, bg="#EAF2FF", highlightbackground="#C9DBF7",
                          highlightthickness=1)
        notice.grid(row=2, column=0, sticky="ew", pady=(0, 14))
        tk.Frame(notice, bg="#3975E6", width=4).pack(side="left", fill="y")
        notice_text = tk.Frame(notice, bg="#EAF2FF", padx=14, pady=10)
        notice_text.pack(side="left", fill="x", expand=True)
        tk.Label(notice_text, text="运行前请准备微信", bg="#EAF2FF", fg="#234A88",
                 font=("Microsoft YaHei UI", 11, "bold")).pack(anchor="w", pady=(0, 5))
        for line in (
            "1. 在微信打开场地预约窗口，进入“体育中心”，让“羽毛球（南京校区）”入口显示出来。",
            "2. 停留在入口页面，不要提前点进羽毛球预约。",
            "3. 最小化原微信聊天主窗口；保留场地预约窗口打开，不要用其他窗口遮挡。",
        ):
            tk.Label(notice_text, text=line, bg="#EAF2FF", fg="#2D4263",
                     font=("Microsoft YaHei UI", 10), anchor="w", justify="left",
                     wraplength=650).pack(anchor="w", pady=1)

        settings = tk.Frame(frame, bg="white", padx=14, pady=12,
                            highlightbackground="#E1E7F0", highlightthickness=1)
        settings.grid(row=3, column=0, sticky="ew")
        for column in range(3):
            settings.columnconfigure(column, weight=1, uniform="setting")
        tk.Label(settings, text="预约设置", bg="white", fg="#18253B",
                 font=("Microsoft YaHei UI", 11, "bold")).grid(
                     row=0, column=0, columnspan=3, sticky="w", pady=(0, 8))
        for column, label in enumerate(("首选场地号（1～17）", "预约时段", "每天启动时间（HH:MM:SS）")):
            tk.Label(settings, text=label, bg="white", fg="#4B5B72",
                     font=("Microsoft YaHei UI", 9)).grid(
                         row=1, column=column, sticky="w", padx=(0, 12))
        self.court_entry = ttk.Entry(settings, textvariable=self.court, width=10)
        self.court_entry.grid(row=2, column=0, sticky="ew", padx=(0, 12), pady=(4, 0))
        self.time_box = ttk.Combobox(
            settings, textvariable=self.time_mode, values=list(TIME_MODES),
            state="readonly", width=20,
        )
        self.time_box.grid(row=2, column=1, sticky="ew", padx=(0, 12), pady=(4, 0))
        self.time_entry = ttk.Entry(settings, textvariable=self.start_time, width=14)
        self.time_entry.grid(row=2, column=2, sticky="ew", pady=(4, 0))
        buttons = tk.Frame(frame, bg="#F6F8FC")
        buttons.grid(row=4, column=0, sticky="w", pady=(14, 0))
        self.start_button = ttk.Button(buttons, text="启动定时", command=self.start,
                                       style="Booking.TButton")
        self.start_button.pack(side="left")
        self.test_button = ttk.Button(buttons, text="测试运行", command=self.test_run,
                                      style="Booking.TButton")
        self.test_button.pack(side="left", padx=(8, 0))
        self.stop_button = ttk.Button(
            buttons, text="停止", command=self.stop, state="disabled", style="Booking.TButton"
        )
        self.stop_button.pack(side="left", padx=(8, 0))
        self.calibrate_button = ttk.Button(
            buttons, text="首次校准 / 重新校准", command=self.calibrate,
            style="Booking.TButton",
        )
        self.calibrate_button.pack(side="left", padx=(8, 0))
        self.morning_button = ttk.Button(
            buttons, text="补充上午坐标", command=self.calibrate_morning,
            style="Booking.TButton",
        )
        self.morning_button.pack(side="left", padx=(8, 0))
        tk.Label(frame, textvariable=self.status, bg="#E8EEF8", fg="#254878",
                 anchor="w", padx=11, pady=8, wraplength=650,
                 font=("Microsoft YaHei UI", 10)).grid(
                     row=5, column=0, sticky="ew", pady=(14, 10)
        )
        tk.Label(frame, text="运行记录", bg="#F6F8FC", fg="#4B5B72",
                 font=("Microsoft YaHei UI", 10, "bold")).grid(
                     row=6, column=0, sticky="nw", pady=(0, 4))
        self.progress = ScrolledText(
            frame, width=72, height=9, wrap="word", state="disabled",
            font=("Microsoft YaHei UI", 10),
        )
        self.progress.grid(row=7, column=0, sticky="nsew")
        frame.rowconfigure(7, weight=1)
        self.progress.tag_configure("timestamp", foreground="#777777")
        tk.Label(frame,
                 text="关闭窗口会隐藏到托盘；运行时窗口自动隐藏。",
                 bg="#F6F8FC", fg="#748197", wraplength=680,
                 font=("Microsoft YaHei UI", 9)).grid(
                     row=8, column=0, sticky="w", pady=(8, 0)
        )

        self.load_settings()
        self.set_active(False)  # 首次联网检查通过前不开放操作。
        icon_image = Image.new("RGB", (64, 64), "#790079")
        draw = ImageDraw.Draw(icon_image)
        draw.ellipse((12, 12, 52, 52), fill="white")
        draw.ellipse((21, 21, 43, 43), fill="#790079")
        self.tray_icon = pystray.Icon(
            "WechatBookingBot", icon_image, APP_NAME,
            menu=pystray.Menu(
                pystray.MenuItem("打开界面", lambda *_: self.tray_actions.put("show"), default=True),
                pystray.MenuItem("退出程序", lambda *_: self.tray_actions.put("quit")),
            ),
        )
        self.tray_thread = threading.Thread(target=self.tray_icon.run, daemon=True)
        self.tray_thread.start()
        self.root.after(200, self.tick)

    def calibrate(self):
        if self.armed:
            messagebox.showinfo("校准", "请先停止当前运行或预约计划，再重新校准。", parent=self.root)
            return
        try:
            previous_profile = load_profile()
        except FileNotFoundError:
            previous_profile = None
        except (OSError, KeyError, TypeError, ValueError) as error:
            messagebox.showwarning("校准", f"无法读取旧校准，滑块起点不能自动沿用：{error}", parent=self.root)
            previous_profile = None
        CalibrationWindow(self.root, lambda: self.status.set("坐标校准已保存"),
                          previous_profile=previous_profile)

    def calibrate_morning(self):
        if self.armed:
            messagebox.showinfo("校准", "请先停止当前运行或预约计划，再补充上午坐标。", parent=self.root)
            return
        try:
            profile = load_profile()
            if "SLIDER_START_POS" not in profile:
                raise ValueError("旧校准没有保存滑块起点，请使用完整校准")
        except (OSError, KeyError, TypeError, ValueError) as error:
            messagebox.showerror("无法补充坐标", str(error), parent=self.root)
            return
        CalibrationWindow(self.root, lambda: self.status.set("上午坐标已保存"),
                          existing_profile=profile)

    def load_settings(self):
        try:
            saved = json.loads(SETTINGS_FILE.read_text(encoding="utf-8"))
            settings = validate_settings(
                str(saved["court"]), saved["time_mode"], saved["start_time"]
            )
        except FileNotFoundError:
            return
        except (OSError, ValueError, KeyError, TypeError):
            self.status.set("设置文件无效，已使用默认值")
            return
        self.court.set(str(settings["court"]))
        self.time_mode.set(settings["time_mode"])
        self.start_time.set(settings["start_time"])

    def start(self):
        try:
            settings = validate_settings(
                self.court.get(), self.time_mode.get(), self.start_time.get()
            )
            self.warnings = calibration_warnings(TIME_MODES[settings["time_mode"]][0])
            check_license("idle")
            self.set_license_badge(True)
            APP_DIR.mkdir(parents=True, exist_ok=True)
            temporary = SETTINGS_FILE.with_suffix(".json.tmp")
            temporary.write_text(
                json.dumps(settings, ensure_ascii=False, indent=2), encoding="utf-8"
            )
            temporary.replace(SETTINGS_FILE)
        except (FileNotFoundError, KeyError, TypeError, ValueError) as error:
            if isinstance(error, FileNotFoundError) and not PROFILE_PATH.exists():
                error = "尚未校准，请先点击“首次校准 / 重新校准”。"
            messagebox.showerror("输入有误", str(error), parent=self.root)
            return
        except OSError as error:
            messagebox.showerror("无法保存设置", str(error), parent=self.root)
            return
        except UpdateRequired as error:
            self.show_update_required(error)
            return
        except LicenseError as error:
            self.set_license_badge(False)
            messagebox.showerror("云端许可", str(error), parent=self.root)
            return

        self.settings = settings
        self.target = next_start(datetime.now(), settings["start_time"])
        self.set_active(True)
        self.status.set(f"等待 {self.target:%m月%d日 %H:%M:%S} 自动执行")

    def test_run(self):
        if self.armed:
            return
        try:
            settings = validate_settings(self.court.get(), self.time_mode.get(), None)
        except ValueError as error:
            messagebox.showerror("输入有误", str(error), parent=self.root)
            return
        if not messagebox.askyesno(
            "确认测试运行", "将立即执行真实预约流程；所选时段没有可预约场地时，会改选 07:30–08:30 并提交预约。确定开始吗？",
            parent=self.root,
        ):
            return
        self.settings = settings
        self.target = None
        if self.launch():
            self.set_active(True)

    def set_active(self, active):
        self.armed = active
        locked = active or self.update_required is not None or not self.license_allowed
        self.court_entry.configure(state="disabled" if locked else "normal")
        self.time_box.configure(state="disabled" if locked else "readonly")
        self.time_entry.configure(state="disabled" if locked else "normal")
        self.start_button.configure(state="disabled" if locked else "normal")
        self.test_button.configure(state="disabled" if locked else "normal")
        self.stop_button.configure(state="normal" if active else "disabled")
        self.calibrate_button.configure(state="disabled" if locked else "normal")
        self.morning_button.configure(state="disabled" if locked else "normal")

    def set_license_badge(self, allowed):
        self.license_allowed = allowed
        if allowed and self.update_required is not None:
            self.update_required = None
            self.update_button.pack_forget()
        self.set_active(self.armed)
        self.license_status.set("● 云端许可已通过" if allowed else "● 云端许可不可用")
        self.license_badge.configure(
            bg="#E4F4EA" if allowed else "#FCE9E9",
            fg="#216A40" if allowed else "#A73939",
        )

    def show_update_required(self, update):
        self.update_required = update
        self.license_allowed = False
        if self.child is not None and self.child.poll() is None:
            self.terminate_child()
        self.target = None
        self.set_active(False)
        self.license_status.set(f"● 必须更新至 v{update.version}")
        self.license_badge.configure(bg="#FFF1D6", fg="#915C00")
        self.update_button.configure(state="disabled" if self.update_downloading else "normal")
        self.update_button.pack(side="left", padx=(8, 0))
        self.status.set(str(update))
        self.show_window()

    def request_update_download(self):
        if self.update_required is None or self.update_downloading:
            return
        self.update_downloading = True
        self.update_button.configure(state="disabled")
        self.status.set("正在下载新版并校验文件，请稍候…")
        threading.Thread(target=self.download_update_worker, daemon=True).start()

    def download_update_worker(self):
        try:
            check_license("idle")  # 重新取得有效下载链接。
        except UpdateRequired as update:
            try:
                self.update_results.put((download_update(update), None))
            except Exception as error:
                self.update_results.put((None, error))
        except Exception as error:
            self.update_results.put((None, error))
        else:
            self.update_results.put((None, None))

    def stop(self):
        if self.child is not None and self.child.poll() is None:
            if not messagebox.askyesno(
                "确认停止", "预约流程正在运行，立即停止可能中断当前操作。确定停止吗？",
                parent=self.root,
            ):
                return False
            self.terminate_child()
        self.child = None
        self.target = None
        self.read_progress()
        self.log_offset = None
        self.set_active(False)
        self.status.set("已停止")
        self.show_warnings()
        return True

    def terminate_child(self):
        subprocess.run(
            ["taskkill", "/PID", str(self.child.pid), "/T", "/F"],
            stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
            creationflags=subprocess.CREATE_NO_WINDOW, check=False,
        )
        if self.child.poll() is None:
            self.child.terminate()

    def show_warnings(self):
        if self.log_pending:
            try:
                self.warnings.extend(
                    line.removeprefix("校准警告：").strip()
                    for line in decode_log(LOG_FILE.read_bytes()).splitlines()
                    if line.startswith("校准警告：")
                )
            except OSError:
                pass
            self.log_pending = False
        if self.warnings:
            self.root.deiconify()
            messagebox.showwarning("校准提醒", "\n".join(self.warnings), parent=self.root)
            self.warnings.clear()

    def read_progress(self):
        if self.log_offset is None:
            return
        lines = []
        try:
            with LOG_FILE.open("rb") as log:
                log.seek(self.log_offset)
                while True:
                    line = log.readline()
                    if not line or not line.endswith(b"\n"):
                        break
                    lines.append(decode_log(line).replace("\r\n", "\n"))
                    self.log_offset = log.tell()
        except OSError:
            return
        if lines:
            self.progress.configure(state="normal")
            for line in lines:
                if line.startswith("本轮结果："):
                    self.result = line.strip().removeprefix("本轮结果：")
                    if self.result.startswith("云端许可"):
                        self.set_license_badge(False)
                self.progress.insert(
                    "end", f"[{datetime.now():%Y-%m-%d %H:%M:%S}]  ", "timestamp"
                )
                self.progress.insert("end", line)
            self.progress.see("end")
            self.progress.configure(state="disabled")
            if self.child is not None and self.update_required is None:
                self.status.set(f"正在执行：{lines[-1].strip()}")

    def launch(self):
        self.log_offset = None
        self.result = None
        self.progress.configure(state="normal")
        self.progress.delete("1.0", "end")
        self.progress.configure(state="disabled")
        try:
            self.warnings = calibration_warnings(TIME_MODES[self.settings["time_mode"]][0])
        except (OSError, KeyError, TypeError, ValueError) as error:
            self.status.set(f"校准文件失效，本轮未启动：{error}")
            return False
        try:
            check_license("booking")
        except UpdateRequired as error:
            self.show_update_required(error)
            return False
        except LicenseError as error:
            self.set_license_badge(False)
            self.target = None
            self.set_active(False)
            self.status.set(str(error))
            return False
        self.set_license_badge(True)
        times, fallback = TIME_MODES[self.settings["time_mode"]]
        env = os.environ.copy()
        env.update({
            "WECHAT_BOOKING_COURT": str(self.settings["court"]),
            "WECHAT_BOOKING_TIMES": ",".join(times),
            "WECHAT_BOOKING_MORNING_FALLBACK": "1" if self.target is None or fallback else "0",
            "WECHAT_BOOKING_CALIBRATION": str(PROFILE_PATH),
            "PYTHONUNBUFFERED": "1",
            "PYTHONIOENCODING": "utf-8",
        })
        command = (
            [sys.executable, "--run-now"]
            if getattr(sys, "frozen", False)
            else [sys.executable, str(PROJECT / "main.py")]
        )
        try:
            with LOG_FILE.open("w", encoding="utf-8") as log:
                self.child = subprocess.Popen(
                    command, cwd=PROJECT, env=env, stdout=log,
                    stderr=subprocess.STDOUT, creationflags=subprocess.CREATE_NO_WINDOW,
                )
        except OSError as error:
            self.status.set(f"启动失败：{error}")
            return False
        else:
            ctypes.windll.user32.AllowSetForegroundWindow(self.child.pid)
            self.root.withdraw()  # 子进程取得前台切换权限后再隐藏窗口。
            self.log_offset = 0
            self.log_pending = True
            self.status.set(
                "测试运行中" if self.target is None
                else f"预约流程正在运行；下次计划 {self.target:%m月%d日 %H:%M:%S}"
            )
            return True

    def tick(self):
        while True:
            try:
                action = self.tray_actions.get_nowait()
            except Empty:
                break
            if action == "show":
                self.show_window()
            elif action == "quit" and self.quit():
                return
        if not self.tray_thread.is_alive() and self.root.state() == "withdrawn":
            self.show_window()
            self.status.set("托盘图标异常退出，窗口已恢复")
        try:
            path, download_error = self.update_results.get_nowait()
        except Empty:
            pass
        else:
            self.update_downloading = False
            self.update_button.configure(state="normal")
            if download_error:
                self.status.set(f"新版下载失败：{download_error}")
            elif path is None:
                self.set_license_badge(True)
                self.status.set("云端已取消更新要求，可以继续使用")
            else:
                self.status.set(f"新版已下载并校验：{path}；请关闭旧版并运行新版")
                self.show_window()
                try:
                    os.startfile(path.parent)
                except OSError:
                    pass  # 路径已显示在界面中，资源管理器打不开也不影响更新文件。
        if hasattr(self, "license_results"):
            try:
                license_error = self.license_results.get_nowait()
            except Empty:
                pass
            else:
                self.license_checking = False
                self.license_next_check = time.monotonic() + CHECK_INTERVAL_SECONDS
                if isinstance(license_error, UpdateRequired):
                    self.show_update_required(license_error)
                else:
                    self.set_license_badge(not license_error)
                if license_error and not isinstance(license_error, UpdateRequired):
                    if self.child is not None and self.child.poll() is None:
                        self.terminate_child()
                    self.target = None
                    self.set_active(False)
                    self.status.set(f"云端许可不可用：{license_error}")
            if (self.child is None and not self.license_checking and
                    time.monotonic() >= self.license_next_check):
                self.license_checking = True
                threading.Thread(target=self.check_idle_license, daemon=True).start()
        self.read_progress()
        if self.child is not None and self.child.poll() is not None:
            code = self.child.returncode
            self.child = None
            self.log_offset = None
            if self.armed and self.target is None:
                self.set_active(False)
                self.root.deiconify()
                self.status.set(getattr(self, "result", None) or f"测试已结束（退出码 {code}）")
            elif self.armed:
                outcome = getattr(self, "result", None) or f"本轮已结束（退出码 {code}）"
                if outcome.startswith("云端"):
                    self.target = None
                    self.set_active(False)
                    self.status.set(outcome)
                else:
                    self.status.set(f"{outcome}；下次计划 {self.target:%m月%d日 %H:%M:%S}")
            self.show_warnings()

        if self.armed and self.target is not None and datetime.now() >= self.target:
            now = datetime.now()
            due = self.target
            self.target = next_start(now, self.settings["start_time"])
            if (now - due).total_seconds() <= 20 and self.child is None:
                self.launch()
            elif self.child is not None:
                self.status.set(f"上轮仍在运行，跳过本轮；下次计划 {self.target:%m月%d日 %H:%M:%S}")
            else:
                self.status.set(f"已错过本轮启动窗口；下次计划 {self.target:%m月%d日 %H:%M:%S}")
        self.root.after(200, self.tick)

    def check_idle_license(self):
        try:
            check_license("idle")
            error = None
        except Exception as exc:
            error = exc
        self.license_results.put(error)

    def close(self):
        if self.tray_thread.is_alive() and self.tray_icon.visible:
            self.root.withdraw()
        elif messagebox.askyesno(
            "托盘不可用", "托盘图标不可用，无法隐藏。是否退出程序？", parent=self.root
        ):
            self.quit()

    def show_window(self):
        self.root.deiconify()
        self.root.lift()

    def quit(self):
        self.show_window()
        if self.armed and not self.stop():
            return False
        if self.tray_thread.is_alive():
            self.tray_icon.stop()
        self.root.destroy()
        return True


def decode_log(data):
    try:
        return data.decode("utf-8")
    except UnicodeDecodeError:
        return data.decode("gbk", errors="replace")


def configure_child_output():
    # windowed EXE 的标准输出可能沿用系统代码页；日志统一写 UTF-8。
    for stream in (sys.stdout, sys.stderr):
        if hasattr(stream, "reconfigure"):
            stream.reconfigure(encoding="utf-8", errors="replace", line_buffering=True)


def run_booking():
    configure_child_output()
    import pyautogui
    from main import main

    try:
        main()
    except (KeyboardInterrupt, pyautogui.FailSafeException):
        print("程序已由用户紧急停止")


def main():
    kernel32 = ctypes.WinDLL("kernel32", use_last_error=True)
    kernel32.CreateMutexW.argtypes = (wintypes.LPVOID, wintypes.BOOL, wintypes.LPCWSTR)
    kernel32.CreateMutexW.restype = wintypes.HANDLE
    mutex = kernel32.CreateMutexW(None, False, "Local\\WechatBookingBotVisibleGUI")
    if not mutex:
        raise OSError(ctypes.get_last_error(), "无法创建程序实例锁")
    if ctypes.get_last_error() == 183:
        ctypes.windll.user32.MessageBoxW(None, "程序已在运行，请查看系统托盘。", APP_NAME, 0)
        kernel32.CloseHandle(mutex)
        return
    try:
        BookingWindow().root.mainloop()
    finally:
        kernel32.CloseHandle(mutex)


if __name__ == "__main__":
    if sys.argv[1:] == ["--run-now"]:
        run_booking()
    elif sys.argv[1:] == ["--check-package"]:
        configure_child_output()
        import main as booking_main  # noqa: F401
        from mouse_recorder import ACTION_FILE

        for file in (Path(__file__).with_name("booking_template.png"), ACTION_FILE):
            if not file.is_file():
                raise FileNotFoundError(file)
        print("中文日志编码检查通过")
    else:
        main()
