import time
import keyboard
import pyautogui

from config import courts, times
from check_selected import check_selected


# 场地横坐标
court_x = {
    1: 112,
    2: 222,
    3: 332,
    4: 432,
    5: 552,
    6: 672,
    7: 792,
    8: 902,
    9: 995,
    10: 1109,
    11: 1212,
    12: 1332,
    13: 1452,
    14: 1572,
    15: 1652,
    16: 1727,
    17: 1837,
}

# 时间纵坐标
time_y = {
    "19:00-20:00": 1189,
    "20:00-21:00": 1250,
}


def select_court() -> bool:
    print("选择场地")

    for court in courts:
        x = court_x[court]

        for t in times:
            y = time_y[t]

            while True:
                if keyboard.is_pressed("esc"):
                    print("检测到按下 Esc，结束选场")
                    return False

                print(f"点击 {court}号场 {t}: ({x},{y})")
                pyautogui.click(x, y)

                # 点击后等待 0.1 秒，再检查颜色。
                time.sleep(0.1)

                if check_selected(x, y):
                    print(f"{court}号场 {t} 选择成功")

                    # 仅退出当前目标的重试循环，继续选择下一个目标。
                    break

                print(f"{court}号场 {t} 未选中，继续尝试")

    # 全部配置项处理完毕后，才返回成功。
    print("所有配置的场地和时段选择完成")
    return True