from config import BADMINTON_POS
from resize_wechat import click_wechat


def move_mouse() -> None:
    print("准备点击羽毛球入口")

    click_wechat(*BADMINTON_POS)

    print("羽毛球入口点击完成")
