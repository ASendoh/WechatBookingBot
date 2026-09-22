import pyautogui
from statistics import median

from config import (
    PURPLE_BLUE_RANGE,
    PURPLE_GREEN_MAX,
    PURPLE_RED_RANGE,
    STATE_SAMPLE_OFFSETS,
    STATE_SAMPLE_SIZE,
    WHITE_MIN,
)

AVAILABLE = "可预约"
SELECTED = "已选中"
UNAVAILABLE = "不可预约"


def classify_color(rgb):
    r, g, b = rgb
    if min(rgb) >= WHITE_MIN:
        return AVAILABLE
    if (
        PURPLE_RED_RANGE[0] <= r <= PURPLE_RED_RANGE[1]
        and g <= PURPLE_GREEN_MAX
        and PURPLE_BLUE_RANGE[0] <= b <= PURPLE_BLUE_RANGE[1]
    ):
        return SELECTED
    return UNAVAILABLE


def classify_samples(colours):
    states = [classify_color(rgb) for rgb in colours]
    if all(state == AVAILABLE for state in states):
        return AVAILABLE
    if all(state == SELECTED for state in states):
        return SELECTED
    return UNAVAILABLE


def has_cell_border(screenshot, x, y):
    for distance in range(18, 34):
        for sample_y in (y - distance, y + distance):
            r, g, b = screenshot.getpixel((x, sample_y))
            if max((r, g, b)) - min((r, g, b)) <= 5 and 220 <= r <= 245:
                return True
    return False


def get_state(
    x,
    y,
    screenshot=None,
    offsets=STATE_SAMPLE_OFFSETS,
    require_cell_border=True,
):
    screenshot = screenshot or pyautogui.screenshot()
    half = STATE_SAMPLE_SIZE // 2
    colours = []
    for offset_x, offset_y in offsets:
        centre_x = x + offset_x
        centre_y = y + offset_y
        patch = [
            screenshot.getpixel((sample_x, sample_y))
            for sample_x in range(centre_x - half, centre_x + half + 1)
            for sample_y in range(centre_y - half, centre_y + half + 1)
        ]
        colours.append(tuple(round(median(channel)) for channel in zip(*patch)))

    state = classify_samples(colours)
    if state == AVAILABLE and require_cell_border and not has_cell_border(screenshot, x, y):
        state = UNAVAILABLE
    return state, colours


def check_selected(x, y):
    state, rgb = get_state(x, y)
    print(f"当前颜色: {rgb}，状态: {state}")
    return state == SELECTED


if __name__ == "__main__":
    assert classify_color((255, 255, 255)) == AVAILABLE
    assert classify_color((153, 0, 153)) == SELECTED
    assert classify_color((235, 235, 235)) == UNAVAILABLE
    assert classify_samples([(255, 255, 255)] * 6) == AVAILABLE
    assert classify_samples([(255, 255, 255)] * 5 + [(235, 235, 235)]) == UNAVAILABLE
    print("颜色分类自检通过")
