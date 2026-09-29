from unittest.mock import patch
from types import SimpleNamespace
import pytest
from browser_sessions import SESSIONS, ROOT, command, endpoint, matches_profile, check


def test_profiles_and_ports_are_separate():
    assert len({port for port, _ in SESSIONS.values()}) == 3
    assert len({profile for _, profile in SESSIONS.values()}) == 3
    for name in SESSIONS:
        assert f'--remote-debugging-port={SESSIONS[name][0]}' in command(name)
        assert endpoint(name).startswith('http://127.0.0.1:')
        args = command(name)
        if name == 'product-hunt':
            assert any(a.startswith('--load-extension=') for a in args)
        else:
            assert '--disable-extensions' in args


def test_refuse_other_profile_on_same_port():
    wrong = f'Chrome --remote-debugging-port=9230 --user-data-dir={ROOT}/runtime/trend-radar-test-profile'
    assert not matches_profile(wrong, 'product-hunt')
    with patch('browser_sessions.subprocess.run', return_value=SimpleNamespace(returncode=0, stdout='123\n')), patch('browser_sessions.subprocess.check_output', return_value=wrong):
        with pytest.raises(RuntimeError, match='another profile'):
            check('product-hunt')


def test_stopped_check_never_starts_chrome():
    with patch('browser_sessions.subprocess.run', return_value=SimpleNamespace(returncode=1, stdout='')), patch('browser_sessions.subprocess.Popen') as start:
        assert check('keywords') is False
        start.assert_not_called()
