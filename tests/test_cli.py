import sys
import textwrap
from pathlib import Path

import pytest

from dis_cli import calculate_column_widths

from .conftest import T_CLI


def test_smoke(cli: T_CLI) -> None:
    assert cli(["dis.dis"]).exit_code == 0


ATTR_NAME = "wiz"
CLASS_NAME = "Foo"
CONST_NAME = "BANG"
FUNC_NAME = "func"
METHOD_NAME = "bar"
NONE_NAME = "noon"

SOURCE = f"""
{CONST_NAME} = "string"
{NONE_NAME} = None

def {FUNC_NAME}():
    pass

class {CLASS_NAME}:
    {ATTR_NAME} = True

    def {METHOD_NAME}(self):
        pass
"""


@pytest.fixture
def source_path(test_dir: Path, filename: str) -> Path:
    source_path = test_dir / f"{filename}.py"
    source_path.write_text(SOURCE)

    return source_path


def test_runs_successfully_on_func_source(cli: T_CLI, source_path: Path) -> None:
    result = cli([f"{source_path.stem}.{FUNC_NAME}"])

    assert result.exit_code == 0


def test_func_source_in_output(cli: T_CLI, source_path: Path) -> None:
    result = cli([f"{source_path.stem}.{FUNC_NAME}"])

    assert f"def {FUNC_NAME}():" in result.output


def test_handle_missing_target_gracefully(cli: T_CLI, source_path: Path) -> None:
    result = cli([f"{source_path.stem}.{FUNC_NAME}osidjafoa"])

    assert result.exit_code == 1
    assert "osidjafoa" in result.output
    assert "No attribute named" in result.output


@pytest.mark.parametrize(
    "extra_source", ["print('hi')", "import sys\nprint('hi', file=sys.stderr)"]
)
def test_module_level_output_is_not_shown(
    cli: T_CLI, test_dir: Path, filename: str, extra_source: str
) -> None:
    source_path = test_dir / f"{filename}.py"
    source_path.write_text(f"{extra_source}\n{SOURCE}")
    print(source_path.read_text())

    result = cli([f"{source_path.stem}.{FUNC_NAME}"])

    assert result.exit_code == 0
    assert "hi" not in result.output


@pytest.mark.parametrize("extra_source", ["raise Exception", "syntax error"])
def test_module_level_error_is_handled_gracefully(
    cli: T_CLI, test_dir: Path, filename: str, extra_source: str
) -> None:
    source_path = test_dir / f"{filename}.py"
    source_path.write_text(f"{extra_source}\n{SOURCE}")
    print(source_path.read_text())

    result = cli([f"{source_path.stem}.{FUNC_NAME}"])

    assert result.exit_code == 1
    assert "during import" in result.output


def test_targeting_a_class_targets_all_of_its_methods(
    cli: T_CLI, test_dir: Path, filename: str
) -> None:
    source_path = test_dir / f"{filename}.py"
    source_path.write_text(
        textwrap.dedent(
            """\
    class Foo:
        def __init__(self):
            print("foobar")

        def method(self):
            print("wizbang")
    """
        )
    )
    print(source_path.read_text())

    result = cli([f"{source_path.stem}.Foo"])

    assert result.exit_code == 0
    assert "foobar" in result.output
    assert "wizbang" in result.output


@pytest.mark.skipif(
    sys.version_info < (3, 7), reason="Non-native dataclasses don't behave the same"
)
def test_can_dis_dataclass(cli: T_CLI, test_dir: Path, filename: str) -> None:
    """
    Dataclasses have generated methods with no matching source that we need a special case for.
    """
    source_path = test_dir / f"{filename}.py"
    source_path.write_text(
        textwrap.dedent(
            """\
    from dataclasses import dataclass

    @dataclass
    class Foo:
        attr: int
    """
        )
    )
    print(source_path.read_text())

    result = cli([f"{source_path.stem}.Foo"])

    assert result.exit_code == 0
    assert "NO SOURCE CODE FOUND" in result.output


def test_targeting_a_module_targets_its_members(cli: T_CLI, test_dir: Path, filename: str) -> None:
    source_path = test_dir / f"{filename}.py"
    source_path.write_text(
        textwrap.dedent(
            """\
    import itertools
    from os.path import join

    def func():
        print("hello")

    class Foo:
        def __init__(self):
            print("foobar")

        def method(self):
            print("wizbang")
    """
        )
    )
    print(source_path.read_text())

    result = cli([f"{source_path.stem}"])

    assert "combinations" not in result.output  # doesn't see imported functions
    assert "join" not in result.output  # doesn't see imported functions
    assert "hello" in result.output
    assert "foobar" in result.output
    assert "wizbang" in result.output


def test_can_target_method(cli: T_CLI, source_path: Path) -> None:
    result = cli([f"{source_path.stem}.{CLASS_NAME}.{METHOD_NAME}"])

    assert result.exit_code == 0
    assert METHOD_NAME in result.output


def test_module_not_found(cli: T_CLI) -> None:
    target = "fidsjofoiasjoifdj"
    result = cli([target])

    assert result.exit_code == 1
    assert "No module named" in result.output
    assert target in result.output


@pytest.mark.parametrize(
    "target_path",
    [
        f"{CONST_NAME}",
        f"{CLASS_NAME}.{ATTR_NAME}",
        f"{NONE_NAME}",
    ],
)
def test_cannot_be_disassembled(cli: T_CLI, source_path: Path, target_path: str) -> None:
    result = cli([f"{source_path.stem}.{target_path}"])

    assert result.exit_code == 1
    assert "cannot be disassembled" in result.output


@pytest.mark.parametrize(
    "terminal_width, line_num_width, ratio, expected",
    [
        (81, 1, 0.5, (38, 38)),
        (80, 1, 0.5, (38, 37)),
        (79, 1, 0.5, (37, 37)),
        (79, 1, 1, (74, 0)),
        (79, 1, 0, (0, 74)),
        (79, 2, 0.5, (36, 36)),
        (79, 3, 0.5, (35, 35)),
        (79, 4, 0.5, (34, 34)),
        (79, 4, 0.75, (51, 17)),
        (80, 4, 0.75, (52, 17)),
    ],
)
def test_column_width(
    terminal_width: int, line_num_width: int, ratio: float, expected: int
) -> None:
    assert (
        calculate_column_widths(line_num_width, ratio=ratio, terminal_width=terminal_width)
        == expected
    )


def test_no_targets_prints_help(cli: T_CLI) -> None:
    result = cli([])

    assert result.exit_code == 0
    assert "TARGET" in result.output
