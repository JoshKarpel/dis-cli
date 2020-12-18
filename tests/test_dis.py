from typing import Any

import dis_cli
import pytest


class cls:
    pass


@pytest.mark.parametrize(
    "obj",
    [pytest, cls, None, "foobar"],
)
def test_cant_make_display_for_target_that_is_not_function(obj: Any) -> None:
    target = dis_cli.Target(obj, "")
    with pytest.raises(TypeError):
        target.make_display()
