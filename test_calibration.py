"""离线校准自检，不读取或修改用户的实际校准文件。"""

import importlib
import json
import os
from pathlib import Path
from tempfile import TemporaryDirectory
from unittest.mock import Mock, patch

from PIL import Image, ImageDraw

import calibration
from calibration import (check_layout, derive_grid, estimate_slider_start,
                         find_purple_line, template_score, validate_profile)
from calibration_ui import CalibrationWindow


def synthetic_page():
    image = Image.new("RGB", (2000, 1400), "white")
    draw = ImageDraw.Draw(image)
    for y in (350, 1160, 1228):
        for court in range(17):
            x = 65 + court * 110
            draw.rectangle((x, y, x + 88, y + 46), outline=(239, 239, 239), width=2)
    draw.line((960, 220, 1050, 220), fill=(153, 0, 153), width=3)
    return image


def test_grid_and_profile():
    wizard = CalibrationWindow.__new__(CalibrationWindow)
    wizard.preview_origin = (100, 200)
    wizard.scale = 0.5
    assert wizard.preview_to_screen(50, 100) == (200, 400)

    image = synthetic_page()
    grid = derive_grid(image, {
        "first": (107, 373),
        "last": (1867, 373),
        "evening19": (107, 1183),
        "evening20": (107, 1251),
    })
    assert list(grid["COURT_X"]) == [str(number) for number in range(1, 18)]
    assert abs(grid["COURT_X"]["1"] - 109) <= 3
    assert abs(grid["COURT_X"]["17"] - 1869) <= 3
    assert abs(grid["TIME_Y"]["20:00-21:00"] - 1251) <= 3
    assert find_purple_line(image, (1000, 190)) == (1005, 219)

    missing = synthetic_page()
    ImageDraw.Draw(missing).rectangle((65 + 8 * 110 - 2, 348, 65 + 8 * 110 + 90, 398), fill="white")
    try:
        derive_grid(missing, {
            "first": (107, 373), "last": (1867, 373),
            "evening19": (107, 1183), "evening20": (107, 1251),
        })
    except ValueError:
        pass
    else:
        raise AssertionError("缺少一列时应拒绝校准")

    missing_evening = synthetic_page()
    ImageDraw.Draw(missing_evening).rectangle((65 + 8 * 110 - 2, 1158,
                                               65 + 8 * 110 + 90, 1208), fill="white")
    try:
        derive_grid(missing_evening, {
            "first": (107, 373), "last": (1867, 373),
            "evening19": (107, 1183), "evening20": (107, 1251),
        })
    except ValueError:
        pass
    else:
        raise AssertionError("晚场缺少一列时应拒绝校准")

    blank = Image.new("RGB", (150, 81), "white")
    assert template_score(blank, blank) == 0
    solid_green = Image.new("RGB", (150, 81), (50, 170, 70))
    assert template_score(solid_green, solid_green) == 0
    patterned = image.crop((955, 200, 1055, 240))
    assert template_score(patterned, patterned) > 0.99

    profile = {
        "version": calibration.PROFILE_VERSION,
        "SCREEN_SIZE": [2000, 1400],
        "ENTRY_WINDOW_RECT": [0, 0, 1000, 1200],
        "BOOKING_WINDOW_RECT": [-8, -8, 2016, 1416],
        "BOOKING_WINDOW_MAXIMIZED": True,
        "ENTRY_CHECK_REGION": [0, 500, 300, 140],
        "PAGE_CHECK_REGION": [0, 70, 400, 100],
        "BADMINTON_POS": [194, 1135],
        "TOMORROW_POS": [1000, 190],
        "TOMORROW_SELECTED_POS": find_purple_line(image, (1000, 190)),
        "REFRESH_POS": [124, 36],
        "SUBMIT_POS": [1911, 1357],
        "SUBMIT_STATE_POS": [1850, 1357],
        "VERIFY_PIXEL_POS": [1949, 907],
        "SLIDER_START_POS": [762, 678],
        **grid,
    }
    assert estimate_slider_start([0, 0, 2000, 1400]) == (762, 678)
    assert estimate_slider_start([100, 50, 1000, 700]) == (481, 389)
    assert validate_profile(profile) is profile
    wizard.step = 3
    wizard.profile = dict(profile)
    wizard.points = {}
    wizard.screen = None
    wizard.prompt = Mock()
    wizard.next_button = Mock()
    wizard.use_estimated_slider()
    assert wizard.profile["SLIDER_START_POS"] == estimate_slider_start(profile["BOOKING_WINDOW_RECT"])
    wizard.next_button.configure.assert_called_once_with(state="normal")
    assert check_layout(image, profile) is None
    assert check_layout(missing, profile) is not None
    with TemporaryDirectory() as directory:
        location = Path(directory)
        with (patch.object(calibration, "DATA_DIR", location),
              patch.object(calibration, "PROFILE_PATH", location / "calibration.json"),
              patch.object(calibration, "TEMPLATE_PATH", location / "booking_header.png"),
              patch.object(calibration, "ENTRY_TEMPLATE_PATH", location / "booking_entry.png")):
            calibration.save_profile(profile, patterned, patterned)
            assert calibration.load_profile(location / "calibration.json")["COURT_X"]["17"] == 1869
        with patch.dict(os.environ, {"WECHAT_BOOKING_CALIBRATION": str(location / "calibration.json")}):
            import config
            importlib.reload(config)
            assert config.COURT_X[17] == 1869
            assert config.PAGE_TEMPLATE_PATH == location / "booking_header.png"
            assert config.ENTRY_TEMPLATE_PATH == location / "booking_entry.png"
            assert config.BOOKING_WINDOW_MAXIMIZED is True
            assert config.SLIDER_START_POS == (762, 678)
            old_profile = dict(profile)
            old_profile.pop("SLIDER_START_POS")
            (location / "calibration.json").write_text(
                json.dumps(old_profile), encoding="utf-8"
            )
            importlib.reload(config)
            assert config.SLIDER_START_POS == estimate_slider_start(profile["BOOKING_WINDOW_RECT"])
    profile["COURT_X"].pop("17")
    try:
        validate_profile(profile)
    except ValueError:
        pass
    else:
        raise AssertionError("缺少 17 号场时应拒绝保存")


def test_replay_uses_calibrated_slider_start():
    import config
    import mouse_recorder

    class Controller:
        def __init__(self):
            self.positions = []

        @property
        def position(self):
            return self.positions[-1]

        @position.setter
        def position(self, point):
            self.positions.append(point)

        def press(self, button):
            pass

        def release(self, button):
            pass

    controller = Controller()
    events = [[0, "click", 700, 600, "left", True],
              [0, "move", 800, 620],
              [0, "click", 800, 620, "left", False]]
    with TemporaryDirectory() as directory:
        action_file = Path(directory) / "actions.json"
        action_file.write_text(json.dumps(events), encoding="utf-8")
        with (patch.object(mouse_recorder, "ACTION_FILE", action_file),
              patch.object(mouse_recorder.mouse, "Controller", return_value=controller),
              patch.object(mouse_recorder.time, "sleep"),
              patch.object(config, "SLIDER_START_POS", (400, 300)),
              patch.object(config, "WINDOW_SIZE", (1000, 700))):
            mouse_recorder.play()
    assert controller.positions == [(400, 300), (450, 310), (450, 310)]


if __name__ == "__main__":
    test_grid_and_profile()
    test_replay_uses_calibrated_slider_start()
    print("校准自检通过")
