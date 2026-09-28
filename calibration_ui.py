"""首次校准向导：用户粗点定位，截图中自动修正并预览。"""

import time
import tkinter as tk
from tkinter import messagebox, ttk

import pyautogui
import win32con
import win32gui
from PIL import ImageTk

from calibration import (PROFILE_VERSION, derive_grid, estimate_slider_start, find_purple_line,
                         save_profile, snap_rectangle, template_score,
                         validate_profile)


STEPS = (
    ("1/4 入口页面", "请先在微信中打开有“羽毛球（南京校区）”入口的页面，再将窗口调窄，直到首页显示该入口；截图后点击该入口。",
     ("BADMINTON_POS",)),
    ("2/4 预约页面", "请手动进入预约页面，保持窗口尺寸不变；截图后点击左上角“体育中心羽毛球”标题，以便确认已进入预约页面。",
     ("HEADER",)),
    ("3/4 场地页面", "请手动调整微信，让 1～17 号场和 07:30、19:00、20:00 行全部显示，并选中第二天；截图后按提示逐项点击。",
     ("TOMORROW_POS", "REFRESH_POS", "SUBMIT_POS", "SUBMIT_STATE_POS",
      "VERIFY_PIXEL_POS", "first", "last", "evening19", "evening20")),
    ("4/4 滑块起点（可选）", "如能打开验证滑块，请保持微信窗口尺寸，出现滑块后截图并点击左端拖动手柄中心；如没有可预约场地，直接使用按窗口比例估算的起点。",
     ("SLIDER_START_POS",)),
)
PROMPTS = {
    "BADMINTON_POS": "在预览图中点击羽毛球入口卡片内有图案或文字的位置；入口在下方时可用滚轮下滚",
    "HEADER": "点击预约页左上角标题文字中心",
    "TOMORROW_POS": "点击顶部“第二天”文字中心（紫线由程序寻找）",
    "REFRESH_POS": "点击微信顶部刷新图标中心",
    "SUBMIT_POS": "点击右下角“提交预约”按钮中心",
    "SUBMIT_STATE_POS": "点击提交按钮内部没有文字的区域",
    "VERIFY_PIXEL_POS": "点击预约页右侧空白处：日后验证弹窗出现时，这里应被灰色遮罩覆盖",
    "first": "点击 1 号场 07:30 格子内部",
    "last": "点击 17 号场 07:30 格子内部",
    "evening19": "点击 1 号场 19:00 格子内部",
    "evening20": "点击 1 号场 20:00 格子内部",
    "SLIDER_START_POS": "点击滑块左端拖动手柄中心；没有滑块时可使用按比例估算的坐标",
}


class CalibrationWindow:
    def __init__(self, parent, on_saved):
        self.parent = parent
        self.on_saved = on_saved
        self.win = tk.Toplevel(parent)
        self.win.title("首次坐标校准")
        self.win.protocol("WM_DELETE_WINDOW", self.win.destroy)
        self.step = 0
        self.points = {}
        self.profile = {"version": PROFILE_VERSION}
        self.screen = None
        self.template = None
        self.entry_template = None
        self.scale = 1
        self.preview_origin = (0, 0)
        self.preview_size = (0, 0)
        self.photo = None
        self.instructions = tk.StringVar()
        self.prompt = tk.StringVar(value="准备好页面后点击“截取当前屏幕”")
        frame = ttk.Frame(self.win, padding=10)
        frame.pack(fill="both", expand=True)
        ttk.Label(frame, textvariable=self.instructions, wraplength=900).pack(anchor="w")
        ttk.Label(frame, textvariable=self.prompt, foreground="purple").pack(anchor="w", pady=(5, 8))
        preview_frame = ttk.Frame(frame)
        preview_frame.pack()
        self.canvas = tk.Canvas(preview_frame, cursor="crosshair", highlightthickness=1)
        self.canvas.pack(side="left")
        scrollbar = ttk.Scrollbar(preview_frame, orient="vertical", command=self.canvas.yview)
        scrollbar.pack(side="right", fill="y")
        self.canvas.configure(yscrollcommand=scrollbar.set)
        self.canvas.bind("<Button-1>", self.pick)
        self.canvas.bind("<MouseWheel>", lambda event: self.canvas.yview_scroll(-int(event.delta / 120), "units"))
        buttons = ttk.Frame(frame)
        buttons.pack(fill="x", pady=(8, 0))
        ttk.Button(buttons, text="截取当前屏幕 / 重来本页", command=self.capture).pack(side="left")
        self.estimate_button = ttk.Button(buttons, text="无滑块，按比例估算", command=self.use_estimated_slider)
        self.next_button = ttk.Button(buttons, text="下一步", command=self.next_step, state="disabled")
        self.next_button.pack(side="right")
        self.show_step()

    def show_step(self):
        title, description, _ = STEPS[self.step]
        extra = " 若按钮自动定位偏离，可按住 Shift 点击使用原始点。" if self.step < 3 else ""
        self.instructions.set(f"{title}：{description}{extra}")
        self.prompt.set("准备好页面后点击“截取当前屏幕”")
        self.next_button.configure(text="确认并保存" if self.step == 3 else "下一步", state="disabled")
        if self.step == 3:
            self.profile["SLIDER_START_POS"] = estimate_slider_start(self.profile["BOOKING_WINDOW_RECT"])
            self.estimate_button.pack(side="left", padx=(8, 0))
        else:
            self.estimate_button.pack_forget()
        self.canvas.delete("all")

    def use_estimated_slider(self):
        if self.step != 3:
            return
        point = estimate_slider_start(self.profile["BOOKING_WINDOW_RECT"])
        self.profile["SLIDER_START_POS"] = point
        try:
            validate_profile(self.profile)
        except ValueError as error:
            self.prompt.set(f"比例估算失败：{error}。请在滑块出现后手动校准。")
            return
        self.points.pop("SLIDER_START_POS", None)
        if self.screen is not None:
            self.canvas.delete("all")
            self.canvas.create_image(0, 0, anchor="nw", image=self.photo)
            self.mark(point, "#ff9900", "滑块估算")
        self.prompt.set(f"滑块起点按比例估算为 {point}；这是估计值，请在首次实际运行时核对。")
        self.next_button.configure(state="normal")

    def capture(self):
        self.points = {}
        self.screen = None
        self.canvas.delete("all")
        self.next_button.configure(state="disabled")
        self.parent.withdraw()
        self.win.withdraw()
        self.win.after(500, self.finish_capture)

    def finish_capture(self):
        try:
            hwnd = win32gui.FindWindow(None, "微信")
            if not hwnd:
                raise ValueError("找不到标题为“微信”的窗口")
            if win32gui.IsIconic(hwnd):
                raise ValueError("微信窗口已最小化，请先恢复窗口再截图")
            try:
                win32gui.SetForegroundWindow(hwnd)
            except Exception as error:
                raise ValueError("无法将微信置于最前方，请先激活微信再重试") from error
            time.sleep(0.2)
            if win32gui.GetForegroundWindow() != hwnd:
                raise ValueError("微信没有位于最前方，请先激活微信再重试")
            left, top, right, bottom = win32gui.GetWindowRect(hwnd)
            self.screen = pyautogui.screenshot()
            size = pyautogui.size()
            if self.screen.size != tuple(size):
                raise ValueError("屏幕截图与鼠标坐标尺寸不一致，请检查显示缩放")
            rect = [left, top, right - left, bottom - top]
            self.profile["SCREEN_SIZE"] = list(self.screen.size)
            if self.step == 0:
                self.profile["ENTRY_WINDOW_RECT"] = rect
            elif self.step in (1, 2):
                self.profile["BOOKING_WINDOW_RECT"] = rect
            if self.step == 2:
                self.profile["BOOKING_WINDOW_MAXIMIZED"] = (
                    win32gui.GetWindowPlacement(hwnd)[1] == win32con.SW_SHOWMAXIMIZED
                )
            clip_left, clip_top = max(0, left), max(0, top)
            clip_right = min(self.screen.width, right)
            clip_bottom = min(self.screen.height, bottom)
            if clip_right <= clip_left or clip_bottom <= clip_top:
                raise ValueError("微信窗口没有显示在当前屏幕上")
            self.preview_origin = (clip_left, clip_top)
            self.preview_size = (clip_right - clip_left, clip_bottom - clip_top)
            window_image = self.screen.crop((clip_left, clip_top, clip_right, clip_bottom))
            max_w = min(1100, self.screen.width - 70)
            max_h = min(760, self.screen.height - 190)
            self.scale = min(1, max_w / window_image.width)
            preview = window_image.resize((round(window_image.width * self.scale),
                                           round(window_image.height * self.scale)))
            self.photo = ImageTk.PhotoImage(preview)
            self.canvas.configure(width=preview.width, height=min(preview.height, max_h),
                                  scrollregion=(0, 0, preview.width, preview.height))
            self.canvas.delete("all")
            self.canvas.create_image(0, 0, anchor="nw", image=self.photo)
            self.canvas.yview_moveto(0)
            self.prompt.set(PROMPTS[STEPS[self.step][2][0]])
        except (ValueError, OSError) as error:
            messagebox.showerror("无法截图", str(error), parent=self.parent)
        finally:
            self.parent.deiconify()
            self.win.deiconify()
            self.win.lift()

    def pick(self, event):
        if self.screen is None or len(self.points) >= len(STEPS[self.step][2]):
            return
        x, y = self.preview_to_screen(self.canvas.canvasx(event.x), self.canvas.canvasy(event.y))
        if not (self.preview_origin[0] <= x < self.preview_origin[0] + self.preview_size[0]
                and self.preview_origin[1] <= y < self.preview_origin[1] + self.preview_size[1]):
            return
        name = STEPS[self.step][2][len(self.points)]
        point = (x, y)
        if name in ("BADMINTON_POS", "REFRESH_POS", "SUBMIT_POS") and not event.state & 0x0001:
            point, _ = snap_rectangle(self.screen, point)
        elif name in ("first", "last", "evening19", "evening20"):
            point, _ = snap_rectangle(self.screen, point, cell=True)
        self.points[name] = point
        self.mark(point, "#ff3333", name)
        if len(self.points) < len(STEPS[self.step][2]):
            self.prompt.set(PROMPTS[STEPS[self.step][2][len(self.points)]])
        else:
            self.complete_step()

    def mark(self, point, colour, label=""):
        x = round((point[0] - self.preview_origin[0]) * self.scale)
        y = round((point[1] - self.preview_origin[1]) * self.scale)
        self.canvas.create_oval(x - 3, y - 3, x + 3, y + 3, fill=colour, outline="white")
        if label:
            self.canvas.create_text(x + 5, y - 6, text=label, anchor="sw", fill=colour)

    def preview_to_screen(self, x, y):
        return (self.preview_origin[0] + round(x / self.scale),
                self.preview_origin[1] + round(y / self.scale))

    def complete_step(self):
        try:
            if self.step == 0:
                x, y = self.points["BADMINTON_POS"]
                self.profile["BADMINTON_POS"] = (x, y)
                self.entry_template = self.screen.crop((max(0, x - 75), max(0, y - 40),
                                                        min(self.screen.width, x + 76),
                                                        min(self.screen.height, y + 41)))
                left, top = max(0, x - 140), max(0, y - 70)
                self.profile["ENTRY_CHECK_REGION"] = [left, top,
                    min(self.screen.width - left, 280), min(self.screen.height - top, 140)]
                if template_score(self.screen.crop((left, top, left + self.profile["ENTRY_CHECK_REGION"][2],
                                                   top + self.profile["ENTRY_CHECK_REGION"][3])),
                                  self.entry_template) < 0.95:
                    raise ValueError("羽毛球入口附近图像太单一；请点击卡片上有图案或文字的位置")
            elif self.step == 1:
                left, top, width, height = self.profile["ENTRY_CHECK_REGION"]
                if template_score(self.screen.crop((left, top, left + width, top + height)),
                                  self.entry_template) > 0.85:
                    raise ValueError("截图仍像入口首页，请先进入预约页面")
                x, y = self.points["HEADER"]
                left, top = max(0, x - 90), max(0, y - 16)
                right = min(self.screen.width, x + 90)
                bottom = min(self.screen.height, y + 17)
                self.template = self.screen.crop((left, top, right, bottom))
                region_left, region_top = max(0, x - 150), max(0, y - 50)
                self.profile["PAGE_CHECK_REGION"] = [
                    region_left, region_top,
                    min(self.screen.width - region_left, 300),
                    min(self.screen.height - region_top, 100),
                ]
                if template_score(self.screen.crop((region_left, region_top,
                                                    region_left + self.profile["PAGE_CHECK_REGION"][2],
                                                    region_top + self.profile["PAGE_CHECK_REGION"][3])),
                                  self.template) < 0.95:
                    raise ValueError("预约页标题图像太单一，无法用于确认页面；请重新选择标题")
            elif self.step == 2:
                self.profile.update(derive_grid(self.screen, self.points))
                self.profile["TOMORROW_POS"] = self.points["TOMORROW_POS"]
                self.profile["TOMORROW_SELECTED_POS"] = find_purple_line(
                    self.screen, self.points["TOMORROW_POS"]
                )
                for name in ("REFRESH_POS", "SUBMIT_POS", "SUBMIT_STATE_POS", "VERIFY_PIXEL_POS"):
                    self.profile[name] = self.points[name]
                self.draw_grid()
                validate_profile(self.profile)
            else:
                self.profile["SLIDER_START_POS"] = self.points["SLIDER_START_POS"]
                validate_profile(self.profile)
        except (ValueError, KeyError) as error:
            self.prompt.set(f"识别未通过：{error}。请点击“重来本页”重新截图、选择。")
            return
        if self.step == 0:
            self.prompt.set("入口位置已标记。请核对红点在羽毛球卡片内，再点“下一步”。")
        elif self.step == 1:
            self.prompt.set("预约页标题已标记。请核对红点在标题上，再点“下一步”并手动调整微信窗口。")
        elif self.step == 2:
            self.prompt.set("请核对全部 17 列三行的点击点，以及青色的代表性颜色采样点，确认均避开数字。")
        else:
            self.prompt.set("请核对红点位于滑块左端拖动手柄中心，确认后保存；也可改用比例估算。")
        self.next_button.configure(state="normal")

    def draw_grid(self):
        offset_x, offset_y = self.profile["COURT_CLICK_OFFSET"]
        for time_name, colour in (("07:30-08:30", "#0088ff"),
                                  ("19:00-20:00", "#ff7700"),
                                  ("20:00-21:00", "#dd00dd")):
            y = self.profile["TIME_Y"][time_name] + offset_y
            for court in range(1, 18):
                self.mark((self.profile["COURT_X"][str(court)] + offset_x, y), colour)
        for court, time_name in ((1, "07:30-08:30"), (17, "07:30-08:30"),
                                 (1, "19:00-20:00"), (1, "20:00-21:00")):
            x = self.profile["COURT_X"][str(court)]
            y = self.profile["TIME_Y"][time_name]
            for dx, dy in self.profile["STATE_SAMPLE_OFFSETS"]:
                self.mark((x + dx, y + dy), "#00bbbb")
        self.mark(self.profile["TOMORROW_SELECTED_POS"], "#00cc44", "紫线")

    def next_step(self):
        if self.step < 3:
            self.step += 1
            self.screen = None
            self.show_step()
            return
        if not messagebox.askyesno(
            "保存校准", "请确认场地点击点、采样点及滑块起点（实测或比例估算）。保存本机校准结果？",
            parent=self.win,
        ):
            return
        try:
            save_profile(self.profile, self.template, self.entry_template)
        except (ValueError, OSError) as error:
            messagebox.showerror("保存失败", str(error), parent=self.win)
            return
        self.on_saved()
        self.win.destroy()
