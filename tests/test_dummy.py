import pytest


@pytest.mark.parametrize(
    ("arg1", "arg2"),
    [
        pytest.param(1, 2, id="case 1"),
        pytest.param(2, 3, id="case 2"),
    ],
)
def test_function(arg1: int, arg2: int):
    assert isinstance(arg1, int) and isinstance(arg2, int)
