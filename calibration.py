"""校准数据与截图内的局部定位；所有坐标均为屏幕像素。"""

import json
import os
from pathlib import Path
from statistics import median

import cv2
import numpy as np


DATA_DIR = Path(os.environ.get("LOCALAPPDATA", Path.home())) / "WechatBookingBot"
PROFILE_PATH = DATA_DIR / "calibration.json"
TEMPLATE_PATH = DATA_DIR / "booking_header.png"
ENTRY_TEMPLATE_PATH = DATA_DIR / "booking_entry.png"
PROFILE_VERSION = 2
OLD_TIME_NAMES = ("07:30-08:30", "19:00-20:00", "20:00-21:00")
TIME_NAMES = ("07:30-08:30", "10:30-11:30", "11:30-12:30", "19:00-20:00", "20:00-21:00")


def estimate_slider_start(window_rect):
    """按实测 2086×1399 窗口内 (816, 684) 的比例估算滑块起点。"""
    left, top, width, height = window_rect
    return (left + round(width * 816 / 2086),
            top + round(height * 684 / 1399))


def validate_profile(profile):
    """只接受完整且仍位于校准屏幕内的点击坐标。"""
    if profile.get("version") != PROFILE_VERSION:
        raise ValueError("校准文件版本不受支持，请重新校准")
    width, height = profile["SCREEN_SIZE"]
    if min(width, height) <= 0:
        raise ValueError("校准文件的屏幕尺寸无效")

    points = ("BADMINTON_POS", "TOMORROW_POS", "TOMORROW_SELECTED_POS",
              "REFRESH_POS", "SUBMIT_POS", "SUBMIT_STATE_POS", "VERIFY_PIXEL_POS")
    if "SLIDER_START_POS" in profile:  # 兼容先前没有滑块坐标的校准文件。
        points += ("SLIDER_START_POS",)
    if "PAGE_BACKGROUND_POINT" in profile:  # 旧校准文件可继续使用推算采样点。
        points += ("PAGE_BACKGROUND_POINT",)
    for name in points:
        x, y = profile[name]
        if not (0 <= x < width and 0 <= y < height):
            raise ValueError(f"{name} 超出校准屏幕")

    court_x = profile["COURT_X"]
    if sorted(map(int, court_x)) != list(range(1, 18)):
        raise ValueError("必须包含 1～17 号场地")
    xs = [court_x[str(number)] for number in range(1, 18)]
    if not all(0 <= x < width for x in xs) or xs != sorted(set(xs)):
        raise ValueError("场地列坐标无效或顺序错误")
    if set(profile["TIME_Y"]) not in (set(OLD_TIME_NAMES), set(TIME_NAMES)):
        raise ValueError("缺少目标时段行坐标")
    if not all(0 <= y < height for y in profile["TIME_Y"].values()):
        raise ValueError("时段行坐标超出校准屏幕")

    for name in ("ENTRY_WINDOW_RECT", "BOOKING_WINDOW_RECT", "ENTRY_CHECK_REGION",
                 "PAGE_CHECK_REGION"):
        x, y, w, h = profile[name]
        if w <= 0 or h <= 0 or x + w <= 0 or y + h <= 0 or x >= width or y >= height:
            raise ValueError(f"{name} 无效")
        if name.endswith("CHECK_REGION") and (x < 0 or y < 0 or x + w > width or y + h > height):
            raise ValueError(f"{name} 超出屏幕")
    if not isinstance(profile.get("BOOKING_WINDOW_MAXIMIZED", False), bool):
        raise ValueError("预约页面窗口状态无效")
    if len(profile["STATE_SAMPLE_OFFSETS"]) != 6:
        raise ValueError("颜色采样点必须有 6 个")
    if profile["STATE_SAMPLE_SIZE"] < 1 or profile["STATE_SAMPLE_SIZE"] % 2 != 1:
        raise ValueError("颜色采样区域边长必须为正奇数")
    if len(profile["CELL_BORDER_DISTANCE"]) != 2:
        raise ValueError("场地边框检测范围无效")
    if len(profile["COURT_CLICK_OFFSET"]) != 2 or len(profile["CELL_SIZE"]) != 2:
        raise ValueError("格子尺寸或点击偏移无效")
    return profile


def load_profile(path=PROFILE_PATH):
    profile = validate_profile(json.loads(Path(path).read_text(encoding="utf-8")))
    for name in ("booking_header.png", "booking_entry.png"):
        template = Path(path).with_name(name)
        if not template.is_file():
            raise FileNotFoundError(f"找不到校准用页面模板：{template}")
    return profile


def save_profile(profile, template_image=None, entry_image=None):
    validate_profile(profile)
    DATA_DIR.mkdir(parents=True, exist_ok=True)
    if entry_image is not None:
        temporary_entry = ENTRY_TEMPLATE_PATH.with_suffix(".png.tmp")
        entry_image.save(temporary_entry, format="PNG")
        temporary_entry.replace(ENTRY_TEMPLATE_PATH)
    if template_image is not None:
        temporary_template = TEMPLATE_PATH.with_suffix(".png.tmp")
        template_image.save(temporary_template, format="PNG")
        temporary_template.replace(TEMPLATE_PATH)
    temporary_profile = PROFILE_PATH.with_suffix(".json.tmp")
    temporary_profile.write_text(
        json.dumps(profile, ensure_ascii=False, indent=2), encoding="utf-8"
    )
    temporary_profile.replace(PROFILE_PATH)


def template_score(screen, template):
    """计算截图区域与模板的相似度；空白模板不视为有效页面标识。"""
    source = np.asarray(screen.convert("RGB"))
    target = np.asarray(template.convert("RGB"))
    if target.shape[0] > source.shape[0] or target.shape[1] > source.shape[1]:
        return 0.0
    source = cv2.cvtColor(source, cv2.COLOR_RGB2GRAY)
    target = cv2.cvtColor(target, cv2.COLOR_RGB2GRAY)
    if target.std() < 8:
        return 0.0
    return float(cv2.minMaxLoc(cv2.matchTemplate(source, target, cv2.TM_CCOEFF_NORMED))[1])


def snap_rectangle(image, point, radius=(80, 55), cell=False):
    """在粗点附近寻找矩形控件；找不到时返回原点供用户预览确认。"""
    x, y = point
    left = max(0, x - radius[0])
    top = max(0, y - radius[1])
    right = min(image.width, x + radius[0] + 1)
    bottom = min(image.height, y + radius[1] + 1)
    rgb = np.asarray(image.crop((left, top, right, bottom)).convert("RGB"))
    gray = cv2.cvtColor(rgb, cv2.COLOR_RGB2GRAY)
    edges = cv2.Canny(gray, 12, 40)  # 浅灰边框与白底对比很低。
    edges = cv2.morphologyEx(edges, cv2.MORPH_CLOSE, np.ones((3, 3), np.uint8))
    contours, _ = cv2.findContours(edges, cv2.RETR_LIST, cv2.CHAIN_APPROX_SIMPLE)
    candidates = []
    for contour in contours:
        bx, by, bw, bh = cv2.boundingRect(contour)
        min_width, min_height = (35, 20) if cell else (24, 15)
        if bw < min_width or bh < min_height or bw >= right - left - 2 or bh >= bottom - top - 2:
            continue
        aspect = bw / bh
        if cell and not 1.2 <= aspect <= 4.0:
            continue
        if not cell and not 0.6 <= aspect <= 8.0:
            continue
        cx = left + bx + bw // 2
        cy = top + by + bh // 2
        if abs(cx - x) > radius[0] * 0.65 or abs(cy - y) > radius[1] * 0.65:
            continue
        contains = bx + left <= x <= bx + left + bw and by + top <= y <= by + top + bh
        score = ((0 if contains else 1) + abs(cx - x) / radius[0]
                 + abs(cy - y) / radius[1] - min(0.5, bw * bh / 12000))
        candidates.append((score, (cx, cy), (left + bx, top + by, bw, bh)))
    if not candidates:
        return point, None
    _, center, bounds = min(candidates, key=lambda item: item[0])
    return center, bounds


def find_purple_line(image, near):
    """在“第二天”文字下方找最长的紫色水平线。"""
    x, y = near
    box = (max(0, x - 110), max(0, y - 5),
           min(image.width, x + 111), min(image.height, y + 65))
    rgb = np.asarray(image.crop(box).convert("RGB"))
    purple = (
        (rgb[:, :, 0] >= 110) & (rgb[:, :, 0] <= 200)
        & (rgb[:, :, 1] <= 65)
        & (rgb[:, :, 2] >= 110) & (rgb[:, :, 2] <= 200)
    )
    best = None
    for row_index, row in enumerate(purple):
        starts = np.flatnonzero(np.diff(np.r_[False, row, False].astype(np.int8)) == 1)
        ends = np.flatnonzero(np.diff(np.r_[False, row, False].astype(np.int8)) == -1)
        for start, end in zip(starts, ends):
            line_x = box[0] + (start + end) // 2
            if abs(line_x - x) <= 45 and (best is None or end - start > best[0]):
                best = (end - start, line_x, box[1] + row_index)
    if best is None or best[0] < 18:
        raise ValueError("未在点击位置下方找到紫色横线；请先选中第二天并重新截图")
    return int(best[1]), int(best[2])


def derive_grid(image, rough_points):
    """由首末列和五行粗点生成 17 列及格内安全点击、采样偏移。"""
    snapped = {}
    bounds = []
    for name in ("first", "last", "morning10", "morning11", "evening19", "evening20"):
        snapped[name], box = snap_rectangle(image, rough_points[name], cell=True)
        if not box:
            raise ValueError(f"{name} 附近未识别到完整格子，请重新截图或点击格子内部")
        bounds.append(box)
    first_x, morning_y = snapped["first"]
    last_x, last_y = snapped["last"]
    if last_x - first_x < 16 * 25 or abs(last_y - morning_y) > 30:
        raise ValueError("首列、末列应处于同一行，且须完整显示 17 列")
    if any(abs(snapped[name][0] - first_x) > 30
           for name in ("morning10", "morning11", "evening19", "evening20")):
        raise ValueError("五行的左端应为同一列场地")
    step = (last_x - first_x) / 16
    if not (morning_y < snapped["morning10"][1] < snapped["morning11"][1]
            < snapped["evening19"][1] < snapped["evening20"][1]):
        raise ValueError("五个时段行的顺序不正确")
    cell_width = round(median(box[2] for box in bounds)) if bounds else round(step * 0.84)
    cell_height = round(median(box[3] for box in bounds)) if bounds else round(
        (snapped["evening20"][1] - snapped["evening19"][1]) * 0.7
    )
    if not (20 <= cell_width < step * 1.15 and 18 <= cell_height <= 100):
        raise ValueError("格子尺寸识别异常，请重新选择格子中心")
    court_x = {}
    for index in range(1, 18):
        predicted = round(first_x + (index - 1) * step)
        center, box = snap_rectangle(image, (predicted, morning_y), cell=True)
        if box is None or abs(center[0] - predicted) > step * 0.25 or abs(center[1] - morning_y) > 12:
            raise ValueError(f"未识别到 07:30 行的 {index} 号场完整格子")
        court_x[str(index)] = center[0]
    if list(court_x.values()) != sorted(set(court_x.values())):
        raise ValueError("17 个场地列未能分别定位")
    times_y = {
        "07:30-08:30": morning_y,
        "10:30-11:30": snapped["morning10"][1],
        "11:30-12:30": snapped["morning11"][1],
        "19:00-20:00": snapped["evening19"][1],
        "20:00-21:00": snapped["evening20"][1],
    }
    for time_name in TIME_NAMES[1:]:
        for index, x in court_x.items():
            center, box = snap_rectangle(image, (x, times_y[time_name]), cell=True)
            if box is None or abs(center[0] - x) > 15 or abs(center[1] - times_y[time_name]) > 12:
                raise ValueError(f"未识别到 {time_name} 行的 {index} 号场完整格子")
    if (last_x + cell_width // 2 >= image.width
            or times_y["20:00-21:00"] + cell_height // 2 >= image.height):
        raise ValueError("末列或 20 点格子未完整显示，请放大或调整微信窗口")
    sample_x = max(4, round(cell_width * 0.27))
    sample_y = max(4, round(cell_height * 0.28))
    return {
        "COURT_X": court_x,
        "TIME_Y": times_y,
        "COURT_CLICK_OFFSET": [0, -max(4, round(cell_height * 0.3))],
        "STATE_SAMPLE_OFFSETS": [
            [dx, dy] for dy in (-sample_y, sample_y)
            for dx in (-sample_x, 0, sample_x)
        ],
        "STATE_SAMPLE_SIZE": 5,
        "CELL_BORDER_DISTANCE": [
            max(3, round(cell_height * 0.38)),
            max(4, round(cell_height * 0.72)),
        ],
        "CELL_SIZE": [cell_width, cell_height],
    }


def add_morning_rows(image, profile, rough_points):
    """只定位新增两行；沿用旧场地列和全部其他校准数据。"""
    rows = {}
    for key, time_name in (("morning10", "10:30-11:30"),
                           ("morning11", "11:30-12:30")):
        center, box = snap_rectangle(image, rough_points[key], cell=True)
        if box is None or abs(center[0] - profile["COURT_X"]["1"]) > 15:
            raise ValueError(f"{time_name} 请点击 1 号场格子内部")
        y = center[1]
        for court, x in profile["COURT_X"].items():
            cell_center, box = snap_rectangle(image, (x, y), cell=True)
            if box is None or abs(cell_center[0] - x) > 15 or abs(cell_center[1] - y) > 12:
                raise ValueError(f"{time_name} 行的 {court} 号场未找到完整格子")
        rows[time_name] = y
    old = profile["TIME_Y"]
    if not (old["07:30-08:30"] < rows["10:30-11:30"]
            < rows["11:30-12:30"] < old["19:00-20:00"]):
        raise ValueError("新增两行顺序不正确，请重新截图、点击")
    return rows


def check_layout(image, profile):
    """运行时抽查目标行的首、中、末列；失败报告但不阻断预约。"""
    for time_name in profile["TIME_Y"]:
        y = profile["TIME_Y"][time_name]
        for court in (1, 9, 17):
            x = profile["COURT_X"][str(court)]
            center, box = snap_rectangle(image, (x, y), cell=True)
            if box is None or abs(center[0] - x) > 15 or abs(center[1] - y) > 12:
                return f"{time_name} 行的 {court} 号场与校准坐标不符；本轮继续，停止后请重新校准。"
    return None
