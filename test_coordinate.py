import pyautogui
import time


START_X = 120
START_Y = 1188

COURT_GAP = 110
TIME_GAP = 65


def move_test(x, y):
    print("移动到:", x, y)
    pyautogui.moveTo(x, y, duration=0.5)
    time.sleep(2)


print("5秒后开始")
time.sleep(5)


# 19:00 一号场
move_test(
    START_X,
    START_Y
)


# 19:00 十七号场
move_test(
    START_X + 16 * COURT_GAP,
    START_Y
)


# 20:00 一号场
move_test(
    START_X,
    START_Y + TIME_GAP
)


print("测试结束")