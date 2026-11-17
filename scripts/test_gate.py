import gate


from subprocess import CompletedProcess
from unittest.mock import patch


def test_retry_control():
    low = {'fault': 0, 'vi': 1699}
    assert gate.retry_control(0, low, 1700)
    assert not gate.retry_control(1, low, 1700)
    assert not gate.retry_control(0, None, 1700)
    assert not gate.retry_control(0, {'fault': 0, 'vi': -1}, 1700)
    assert not gate.retry_control(0, {'fault': 1, 'vi': 1}, 1700)
    assert not gate.retry_control(0, {'fault': 0, 'vi': 1700}, 1700)


def test_runtime_starts_after_cli_build():
    cli_built = False
    runtime_started = False

    def run(command, **kwargs):
        nonlocal cli_built, runtime_started
        if command[0] == 'cargo' and command[1] == 'build':
            cli_built = 'plaid' in command
        if command[1] == 'runtime/test_runtime.py':
            assert cli_built, 'runtime started without its CLI'
            runtime_started = True
        return CompletedProcess(command, 0, '', '')

    with (patch('sys.argv', ['gate.py', '--runtime']),
          patch.dict('os.environ', clear=True),
          patch.object(gate, 'doctor', return_value=True),
          patch.object(gate, 'tool', return_value='cargo'),
          patch.object(gate.subprocess, 'run', side_effect=run)):
        try:
            gate.main()
        except SystemExit as stop:
            assert stop.code == 0
    assert runtime_started


if __name__ == '__main__':
    test_retry_control()
    test_runtime_starts_after_cli_build()
    print('gate CLI preparation and retry eligibility passed')
