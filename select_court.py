import time
import keyboard
import pyautogui

from check_selected import AVAILABLE, SELECTED, get_state
from config import (
    CLICK_WAIT,
    COURT_CLICK_OFFSET,
    COURT_X,
    ENABLE_MORNING_TEST_FALLBACK,
    MORNING_TEST_TIME,
    SUBMIT_STATE_POS,
    TIME_Y,
    courts,
    times,
)


def candidate_courts(target):
    result = [target]
    for distance in range(1, len(COURT_X)):
        for court in (target + distance, target - distance):
            if court in COURT_X:
                result.append(court)
    return result


def submit_is_enabled():
    state, rgb = get_state(
        *SUBMIT_STATE_POS,
        offsets=((0, 0),),
        require_cell_border=False,
    )
    print(f"提交按钮检测颜色: {rgb}，状态: {state}")
    return state == SELECTED


def click_succeeded(court, time_name):
    x, y = COURT_X[court], TIME_Y[time_name]
    if time_name == "20:00-21:00" and submit_is_enabled():
        return True
    state, rgb = get_state(x, y)
    print(f"点击后检测 {court}号场 {time_name}: {state} {rgb}")
    return state == SELECTED


def select_court():
    if not courts:
        print("config.py 未配置目标场地")
        return []

    order = candidate_courts(courts[0])
    screenshot = pyautogui.screenshot()
    available = {}

    scan_times = list(times)
    if ENABLE_MORNING_TEST_FALLBACK:
        scan_times.append(MORNING_TEST_TIME)

    print("开始扫描目标时段（此时尚未弹出底部信息框）")
    for time_name in scan_times:
        available[time_name] = []
        for court in order:
            if keyboard.is_pressed("esc"):
                print("检测到 Esc，结束选场")
                return []
            state, rgb = get_state(COURT_X[court], TIME_Y[time_name], screenshot)
            print(f"检测 {court}号场 {time_name}: {state} {rgb}")
            if state == AVAILABLE:
                available[time_name].append(court)

    selection_order = ["20:00-21:00", "19:00-20:00"]
    if ENABLE_MORNING_TEST_FALLBACK and not any(available.get(t) for t in times):
        print(f"晚场均不可预约，改为选择测试时段 {MORNING_TEST_TIME}")
        selection_order.append(MORNING_TEST_TIME)

    selected = []
    for time_name in selection_order:
        for court in available.get(time_name, []):
            if keyboard.is_pressed("esc"):
                print("检测到 Esc，结束选场")
                return []

            x, y = COURT_X[court], TIME_Y[time_name]
            state, rgb = get_state(x, y)
            print(f"点击前复检 {court}号场 {time_name}: {state} {rgb}")
            if state != AVAILABLE:
                continue

            click_x = x + COURT_CLICK_OFFSET[0]
            click_y = y + COURT_CLICK_OFFSET[1]
            print(f"点击 {court}号场 {time_name} 无文字区域: ({click_x}, {click_y})")
            pyautogui.click(click_x, click_y)
            time.sleep(CLICK_WAIT)

            success = click_succeeded(court, time_name)
            if not success:
                time.sleep(CLICK_WAIT)
                success = click_succeeded(court, time_name)
            if success:
                print(f"{court}号场 {time_name} 选择成功")
                selected.append((time_name, court))
                break

            print(f"{court}号场 {time_name} 未选中，切换下一个候选场地")

    if selected:
        print("最终选中：" + "，".join(f"{court}号场 {t}" for t, court in selected))
    else:
        print("目标时段和早场测试时段均未选中")
    return selected


if __name__ == "__main__":
    assert candidate_courts(12)[:7] == [12, 13, 11, 14, 10, 15, 9]
    assert sorted(candidate_courts(1)) == list(COURT_X)
    print("候选场地顺序自检通过")
