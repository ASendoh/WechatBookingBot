import check_verify


def test_verify_appear_timeout():
    now = -0.1

    def monotonic():
        nonlocal now
        now += 0.1
        return now

    check_verify.time.monotonic = monotonic
    check_verify.time.sleep = lambda _seconds: None
    check_verify.keyboard.is_pressed = lambda _key: False
    check_verify.check_verify = lambda: False

    assert check_verify.wait_verify() is True
    assert 2.0 <= now < 2.2


if __name__ == "__main__":
    test_verify_appear_timeout()
    print("验证窗口出现超时检查通过")
