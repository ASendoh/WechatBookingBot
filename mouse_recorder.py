"""F8 开始录制，Esc 停止保存；导入 play() 可回放。"""

import json
import time
from pathlib import Path

try:
    from pynput import keyboard, mouse
except ImportError as error:
    raise SystemExit("请先安装依赖：python -m pip install pynput") from error


ACTION_FILE = Path(__file__).with_name("mouse_actions.json")


def record():
    """等待 F8，然后录制鼠标操作，直到按下 Esc。"""
    print("按 F8 开始录制……")
    with keyboard.Listener(
        on_press=lambda key: False if key == keyboard.Key.f8 else None
    ) as listener:
        listener.join()

    events = []
    started = time.perf_counter()

    def now():
        return time.perf_counter() - started

    def on_move(x, y):
        events.append([now(), "move", x, y])

    def on_click(x, y, button, pressed):
        events.append([now(), "click", x, y, button.name, pressed])

    print("正在录制；按 Esc 结束并保存。")
    mouse_listener = mouse.Listener(on_move=on_move, on_click=on_click)
    mouse_listener.start()
    with keyboard.Listener(
        on_press=lambda key: False if key == keyboard.Key.esc else None
    ) as listener:
        listener.join()
    mouse_listener.stop()
    mouse_listener.join()

    ACTION_FILE.write_text(json.dumps(events), encoding="utf-8")
    print(f"已保存到 {ACTION_FILE}")


def play():
    """以录制的首次左键按下为起点，按校准窗口比例回放。"""
    from config import SLIDER_START_POS, WINDOW_SIZE

    events = json.loads(ACTION_FILE.read_text(encoding="utf-8"))
    start = next(((event[2], event[3]) for event in events
                  if event[1] == "click" and event[4:] == ["left", True]), None)
    if start is None:
        raise ValueError("录制轨迹缺少滑块起点的左键按下操作")
    scale_x, scale_y = WINDOW_SIZE[0] / 2000, WINDOW_SIZE[1] / 1400
    controller = mouse.Controller()
    previous = 0.0

    for event in events:
        recorded_time, event_type, x, y, *details = event
        time.sleep(max(0.0, recorded_time - previous))
        controller.position = (
            round(SLIDER_START_POS[0] + (x - start[0]) * scale_x),
            round(SLIDER_START_POS[1] + (y - start[1]) * scale_y),
        )
        if event_type == "click":
            button_name, pressed = details
            button = getattr(mouse.Button, button_name)
            (controller.press if pressed else controller.release)(button)
        previous = recorded_time


if __name__ == "__main__":
    record()
