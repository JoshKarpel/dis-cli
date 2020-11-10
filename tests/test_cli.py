import textwrap
from pathlib import Path

import pytest

from dis_cli import get_own_version


def test_smoke(cli):
    assert cli(["dis.dis"]).exit_code == 0


FUNC_NAME = "func"
FUNC = f"""
def {FUNC_NAME}():
    pass
"""

CLASS_NAME = "Foo"
METHOD_NAME = "bar"
CLASS = f"""
class {CLASS_NAME}:
    def {METHOD_NAME}(self):
        pass
"""


@pytest.fixture
def source_path_with_func(test_dir, filename) -> Path:
    source_path = test_dir / f"{filename}.py"
    source_path.write_text(FUNC)

    return source_path


@pytest.fixture
def source_path_with_class(test_dir, filename) -> Path:
    source_path = test_dir / f"{filename}.py"
    source_path.write_text(CLASS)

    return source_path


def test_runs_successfully_on_func_source(cli, source_path_with_func):
    result = cli([f"{source_path_with_func.stem}.{FUNC_NAME}"])

    assert result.exit_code == 0


def test_func_source_in_output(cli, source_path_with_func):
    result = cli([f"{source_path_with_func.stem}.{FUNC_NAME}"])

    assert all([line in result.output for line in FUNC.splitlines()])


def test_handle_missing_target_gracefully(cli, source_path_with_func):
    result = cli([f"{source_path_with_func.stem}.{FUNC_NAME}osidjafoa"])

    assert result.exit_code == 1
    assert "osidjafoa" in result.output
    assert "No attribute named" in result.output


@pytest.mark.parametrize(
    "extra_source", ["print('hi')", "import sys\nprint('hi', file=sys.stderr)"]
)
def test_module_level_output_is_not_shown(cli, test_dir, filename, extra_source):
    source_path = test_dir / f"{filename}.py"
    source_path.write_text(f"{extra_source}\n{FUNC}")
    print(source_path.read_text())

    result = cli([f"{source_path.stem}.{FUNC_NAME}"])

    assert result.exit_code == 0
    assert "hi" not in result.output


@pytest.mark.parametrize("extra_source", ["raise Exception", "syntax error"])
def test_module_level_error_is_handled_gracefully(cli, test_dir, filename, extra_source):
    source_path = test_dir / f"{filename}.py"
    source_path.write_text(f"{extra_source}\n{FUNC}")
    print(source_path.read_text())

    result = cli([f"{source_path.stem}.{FUNC_NAME}"])

    assert result.exit_code == 1
    assert "during import" in result.output


def test_targetting_a_class_redirects_to_init(cli, test_dir, filename):
    source_path = test_dir / f"{filename}.py"
    source_path.write_text(
        textwrap.dedent(
            """\
    class Foo:
        def __init__(self):
            print("foobar")
    """
        )
    )
    print(source_path.read_text())

    result = cli([f"{source_path.stem}.Foo"])

    assert result.exit_code == 0
    assert "foobar" in result.output


@pytest.mark.parametrize(
    "target",
    [
        "click",  # top-level module
        "click.testing",  # submodule
    ],
)
def test_gracefully_cannot_disassemble_module(cli, target):
    result = cli([target])

    assert result.exit_code == 1
    assert "Cannot disassemble modules" in result.output


def test_can_target_method(cli, source_path_with_class):
    result = cli([f"{source_path_with_class.stem}.{CLASS_NAME}.{METHOD_NAME}"])

    assert result.exit_code == 0


def test_module_not_found(cli):
    target = "fidsjofoiasjoifdj"
    result = cli([target])

    assert result.exit_code == 1
    assert "No module named" in result.output
    assert target in result.output


def test_version(cli):
    result = cli(["--version"])

    assert get_own_version() in result.output
