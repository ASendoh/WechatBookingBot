"""离线检查入口黄色提示栏不会被误认成预约页。"""

from unittest.mock import patch

import check_page


def test_page_header_color():
    with (patch.object(check_page, "ENTRY_WINDOW_RECT", (-7, 0, 766, 1399)),
          patch.object(check_page, "PAGE_CHECK_REGION", (0, 53, 300, 100)),
          patch.object(check_page, "PAGE_BACKGROUND_POINT", (606, 103)),
          patch.object(check_page, "matches_region", return_value=True),
          patch.object(check_page.win32gui, "FindWindow", return_value=1),
          patch.object(check_page.win32gui, "GetWindowRect",
                       side_effect=[(-7, 0, 759, 1399), (0, 0, 2086, 1399)]),
          patch.object(check_page.pyautogui, "size", return_value=(2560, 1440)),
          patch.object(check_page.pyautogui, "pixel", side_effect=[
              (255, 248, 219), (255, 255, 255),
          ]) as pixel):
        assert not check_page.check_page(verbose=False)
        assert check_page.check_page(verbose=False)
        assert pixel.call_args_list[0].args == (606, 103)
        assert pixel.call_args_list[1].args == (1669, 103)


if __name__ == "__main__":
    test_page_header_color()
    print("页面识别自检通过")
