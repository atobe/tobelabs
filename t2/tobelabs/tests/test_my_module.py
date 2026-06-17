# tests/test_my_module.py
from t2.tobelabs.my_module import add


def test_add() -> None:
    assert add(1, 2) == 3
    assert add(-1, 1) == 0
    assert add(0, 0) == 0
