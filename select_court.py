import pyautogui
import time
import keyboard
from config import courts, times
from check_selected import check_selected


# 场地横坐标
court_x = {
    1:112,
    2:222,
    3:332,
    4:432,
    5:552,
    6:672,
    7:792,
    8:902,
    9:995,
    10:1109,
    11:1212,
    12:1332,
    13:1452,
    14:1572,
    15:1652,
    16:1752,
    17:1862,
}


# 时间纵坐标
time_y = {
    "19:00-20:00":1189,
    "20:00-21:00":1250,
}


def select_court():

    print("选择场地")

    for court in courts:

        x = court_x[court]

        for t in times:

            y = time_y[t]

            while True:

                if keyboard.is_pressed("esc"):
                    print("检测到按下esc，退出程序")
                    return False

                print(
                    f"点击 {court}号场 {t}: ({x},{y})"
                )

                #点击场地
                pyautogui.click(x,y)

                #检测是否选中
                if check_selected(x, y):
                    print(
                        f"{court}号场 {t} 选择成功"
                    )
                    return True

                else:

                    print(
                        f"{court}号场 {t} 未选中，继续尝试"
                    )
                time.sleep(0.1)