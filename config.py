# ==================== 预约目标 ====================

import os
from pathlib import Path

# 首选场地编号。当前选场逻辑使用列表中的第一个编号作为中心，
# 再按“目标、右1、左1、右2、左2……”寻找可预约场地。
courts = [int(os.environ.get("WECHAT_BOOKING_COURT", "17"))]

# 扫描的目标时段。正式点击顺序固定为先20点、后19点，以避开底部信息框遮挡。
times = os.environ.get(
    "WECHAT_BOOKING_TIMES", "19:00-20:00,20:00-21:00"
).split(",")

# 测试回退开关。True表示所选时段均不可预约时，改选07:30–08:30并继续提交；
# 这会产生真实预约操作，完成测试后请改回False。
ENABLE_MORNING_TEST_FALLBACK = (
    os.environ.get("WECHAT_BOOKING_MORNING_FALLBACK", "0") == "1"
)
MORNING_TEST_TIME = "07:30-08:30"


# ==================== 窗口和场地坐标 ====================

# 微信窗口调整后的左上角位置和外框尺寸。修改后，下面所有“调整窗口后”的坐标都要重测。
WINDOW_POS = (0, 0)
WINDOW_SIZE = (2000, 1400)

# 17个场地格子的横向中心坐标，已根据2000×1400整屏截图逐格核对。
COURT_X = {
    1: 118,
    2: 228,
    3: 338,
    4: 448,
    5: 558,
    6: 668,
    7: 778,
    8: 888,
    9: 998,
    10: 1108,
    11: 1218,
    12: 1328,
    13: 1438,
    14: 1548,
    15: 1658,
    16: 1768,
    17: 1878,
}

# 未校准时的旧版时段坐标。新增的 10:30、11:30 必须经校准后写入 TIME_Y。
TIME_Y = {
    "07:30-08:30": 380,
    "19:00-20:00": 1189,
    "20:00-21:00": 1257,
}

# 点击场地时相对格子中心的偏移量。
# (0, -15) 表示点击中心上方15像素的无文字区域，避免点在“15元”数字上。
COURT_CLICK_OFFSET = (0, -15)

# 启动时“羽毛球馆”入口的点击坐标；该坐标用于调整窗口尺寸之前的初始页面。
BADMINTON_POS = (194, 1135)

# 调整窗口后，顶部“第二天（星期X/月日）”文字区域的中心点击坐标，已现场确认。
TOMORROW_POS = (1065, 190)

# 调整窗口后，“第二天”标签下方紫色横线的中心坐标，已现场确认。
TOMORROW_SELECTED_POS = (1065, 229)

# 页面右下角“提交预约”按钮的点击坐标。
SUBMIT_POS = (1911, 1357)

# “提交预约”按钮内部无文字区域的颜色检测坐标，用于辅助确认20点场地已选中。
SUBMIT_STATE_POS = (1850, 1357)

# 未校准时按实测新比例映射到默认 2000×1400 窗口；校准后优先使用实测点。
SLIDER_START_POS = (782, 684)

# 验证弹窗外灰色遮罩的检测坐标，用于判断验证窗口出现和消失。
VERIFY_PIXEL_POS = (1949, 907)

# 调整窗口后，微信最顶部导航栏“圆形箭头刷新图标”的中心坐标，已现场确认。
REFRESH_POS = (124, 36)


# ==================== 场地颜色检测 ====================

# 颜色采样点相对格子中心的偏移量，共6个点。
# 横向±25、纵向±15均位于格子内部并避开中央价格数字；全部符合才判定状态。
STATE_SAMPLE_OFFSETS = (
    (-25, -15),
    (0, -15),
    (25, -15),
    (-25, 15),
    (0, 15),
    (25, 15),
)

# 每个采样点读取的正方形区域边长，单位为像素；必须使用奇数以保证有中心点。
STATE_SAMPLE_SIZE = 5

# 白色可预约格子的RGB三通道最低值。实测为(255,255,255)，250用于容忍少量显示误差。
WHITE_MIN = 250

# 紫色已选中格子的RGB范围。实测为(153,0,153)，当前范围保留少量显示误差。
PURPLE_RED_RANGE = (120, 190)
PURPLE_GREEN_MAX = 30
PURPLE_BLUE_RANGE = (120, 190)

# 验证弹窗出现时，遮罩检测点的目标灰色值和允许误差。
# 当前表示RGB三个通道都处于122～132时，认为灰色遮罩存在。
VERIFY_GREY = 127
VERIFY_TOLERANCE = 5


# ==================== 等待和重试参数 ====================
# 所有带 SECONDS、WAIT 或 INTERVAL 的数值单位均为秒；带 RETRIES 的数值为次数。

# 验证遮罩消失后必须连续保持无遮罩的时间，防止页面闪烁导致误判验证结束。
VERIFY_STABLE_SECONDS = 0.8

# 点击提交后等待验证窗口出现的最长时间；超时视为异常并刷新重选。
VERIFY_APPEAR_TIMEOUT_SECONDS = 2.0

# 验证遮罩消失后，最多等待付款页面出现的时间；超时则刷新重选。
PAYMENT_APPEAR_TIMEOUT_SECONDS = 1.0

# 检测到验证窗口后，执行一次已录制操作前的等待时间，确保弹窗完成显示。
VERIFY_PLAY_START_DELAY_SECONDS = 0.1

# 一次已录制操作结束后，等待多久再检查验证遮罩是否仍然存在。
VERIFY_AFTER_PLAY_WAIT_SECONDS = 1.0

# 首次提示需要手动完成验证后，每隔多久再次检查并重复打印提醒。
VERIFY_MANUAL_REMINDER_SECONDS = 2.0

# 点击场地后等待页面变色的时间；第一次未成功时，还会再等待一次后补检，但不会重复点击。
CLICK_WAIT = 0.2

# 各等待循环读取页面状态的间隔；越小响应越快，但截图和CPU占用会增加。
POLL_INTERVAL = 0.1

# 连续两次点击“第二天”之间的间隔；需要调整双击速度时修改这里。
TOMORROW_DOUBLE_CLICK_INTERVAL = 0.2

# 每轮双击“第二天”后，最多等待紫色横线和晚间可预约格子同时出现的时间。
TOMORROW_LOAD_SECONDS = 1.8

# 目标时段所有格子持续呈灰色多久才判定已抢空；防止把加载占位格误判为结果。
SOLD_OUT_CONFIRM_SECONDS = 1.0

# 刷新页面之前，最多重新双击“第二天”的次数；本阶段最长检测约为次数×上面的等待时间。
TOMORROW_RETRIES = 5

# 点击顶部刷新按钮后固定等待的时间。刷新只点击一次；
# 等待结束后检查预约页左上角标题，若已回到入口页则尝试重新进入。
REFRESH_WAIT_SECONDS = 0.1

# 每次点击羽毛球入口后，最多等待预约页面模板出现的时间；不影响顶部刷新等待。
PAGE_LOAD_SECONDS = 0.1

# 入口点击后页面短暂切换，以及刷新回退后重新进入预约页的最长等待；超时则停止。
ENTRY_UNKNOWN_GRACE_SECONDS = 1.0

# 调整微信窗口位置和尺寸后，等待页面完成重新排版的时间。
RESIZE_LAYOUT_WAIT = 0.1


# 首次校准后由本机文件覆盖上面的默认坐标；未校准时保留原脚本坐标，方便旧版直接运行。
ENTRY_WINDOW_RECT = None
BOOKING_WINDOW_MAXIMIZED = False
ENTRY_CHECK_REGION = None
ENTRY_TEMPLATE_PATH = None
PAGE_CHECK_REGION = (0, 70, 400, 100)
PAGE_TEMPLATE_PATH = Path(__file__).with_name("booking_template.png")
PAGE_BACKGROUND_POINT = None
CELL_BORDER_DISTANCE = (18, 34)

from calibration import PROFILE_PATH, estimate_slider_start, load_profile

_calibration_path = Path(os.environ.get("WECHAT_BOOKING_CALIBRATION", PROFILE_PATH))
CALIBRATION_PATH = _calibration_path if _calibration_path.is_file() else None
if "WECHAT_BOOKING_CALIBRATION" in os.environ and not _calibration_path.is_file():
    raise FileNotFoundError(f"找不到本机校准文件：{_calibration_path}")
if _calibration_path.exists():
    _profile = load_profile(_calibration_path)
    ENTRY_WINDOW_RECT = tuple(_profile["ENTRY_WINDOW_RECT"])
    BOOKING_WINDOW_MAXIMIZED = _profile.get("BOOKING_WINDOW_MAXIMIZED", False)
    ENTRY_CHECK_REGION = tuple(_profile["ENTRY_CHECK_REGION"])
    ENTRY_TEMPLATE_PATH = _calibration_path.with_name("booking_entry.png")
    WINDOW_POS = tuple(_profile["BOOKING_WINDOW_RECT"][:2])
    WINDOW_SIZE = tuple(_profile["BOOKING_WINDOW_RECT"][2:])
    COURT_X = {int(number): x for number, x in _profile["COURT_X"].items()}
    TIME_Y = _profile["TIME_Y"]
    COURT_CLICK_OFFSET = tuple(_profile["COURT_CLICK_OFFSET"])
    STATE_SAMPLE_OFFSETS = tuple(map(tuple, _profile["STATE_SAMPLE_OFFSETS"]))
    STATE_SAMPLE_SIZE = _profile["STATE_SAMPLE_SIZE"]
    CELL_BORDER_DISTANCE = tuple(_profile["CELL_BORDER_DISTANCE"])
    PAGE_CHECK_REGION = tuple(_profile["PAGE_CHECK_REGION"])
    PAGE_TEMPLATE_PATH = _calibration_path.with_name("booking_header.png")
    if "PAGE_BACKGROUND_POINT" in _profile:
        PAGE_BACKGROUND_POINT = tuple(_profile["PAGE_BACKGROUND_POINT"])
    SLIDER_START_POS = tuple(_profile.get(
        "SLIDER_START_POS", estimate_slider_start(_profile["BOOKING_WINDOW_RECT"])
    ))
    for _name in ("BADMINTON_POS", "TOMORROW_POS", "TOMORROW_SELECTED_POS",
                  "REFRESH_POS", "SUBMIT_POS", "SUBMIT_STATE_POS", "VERIFY_PIXEL_POS"):
        globals()[_name] = tuple(_profile[_name])
