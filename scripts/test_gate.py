import gate


def test_retry_control():
    low = {'fault': 0, 'vi': 1699}
    assert gate.retry_control(0, low, 1700)
    assert not gate.retry_control(1, low, 1700)
    assert not gate.retry_control(0, None, 1700)
    assert not gate.retry_control(0, {'fault': 0, 'vi': -1}, 1700)
    assert not gate.retry_control(0, {'fault': 1, 'vi': 1}, 1700)
    assert not gate.retry_control(0, {'fault': 0, 'vi': 1700}, 1700)


if __name__ == '__main__':
    test_retry_control()
    print('gate retry eligibility passed')
