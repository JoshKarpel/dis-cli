import textwrap
from pathlib import Path

import pytest

from dis_cli import get_own_version


def test_smoke(cli):
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
def source_path(test_dir, filename) -> Path:
    source_path = test_dir / f"{filename}.py"
    source_path.write_text(SOURCE)

    return source_path


def test_runs_successfully_on_func_source(cli, source_path):
    result = cli([f"{source_path.stem}.{FUNC_NAME}"])

    assert result.exit_code == 0


def test_func_source_in_output(cli, source_path):
    result = cli([f"{source_path.stem}.{FUNC_NAME}"])

    assert f"def {FUNC_NAME}():" in result.output


def test_handle_missing_target_gracefully(cli, source_path):
    result = cli([f"{source_path.stem}.{FUNC_NAME}osidjafoa"])

    assert result.exit_code == 1
    assert "osidjafoa" in result.output
    assert "No attribute named" in result.output


@pytest.mark.parametrize(
    "extra_source", ["print('hi')", "import sys\nprint('hi', file=sys.stderr)"]
)
def test_module_level_output_is_not_shown(cli, test_dir, filename, extra_source):
    source_path = test_dir / f"{filename}.py"
    source_path.write_text(f"{extra_source}\n{SOURCE}")
    print(source_path.read_text())

    result = cli([f"{source_path.stem}.{FUNC_NAME}"])

    assert result.exit_code == 0
    assert "hi" not in result.output


@pytest.mark.parametrize("extra_source", ["raise Exception", "syntax error"])
def test_module_level_error_is_handled_gracefully(cli, test_dir, filename, extra_source):
    source_path = test_dir / f"{filename}.py"
    source_path.write_text(f"{extra_source}\n{SOURCE}")
    print(source_path.read_text())

    result = cli([f"{source_path.stem}.{FUNC_NAME}"])

    assert result.exit_code == 1
    assert "during import" in result.output


def test_targeting_a_class_redirects_to_init(cli, test_dir, filename):
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


def test_can_target_method(cli, source_path):
    result = cli([f"{source_path.stem}.{CLASS_NAME}.{METHOD_NAME}"])

    assert result.exit_code == 0
    assert METHOD_NAME in result.output


def test_module_not_found(cli):
    target = "fidsjofoiasjoifdj"
    result = cli([target])

    assert result.exit_code == 1
    assert "No module named" in result.output
    assert target in result.output


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
    assert "cannot be disassembled" in result.output
    assert "module" in result.output


@pytest.mark.parametrize(
    "target",
    [
        f"{CONST_NAME}",
        f"{CLASS_NAME}.{ATTR_NAME}",
        f"{NONE_NAME}",
    ],
)
def test_cannot_be_disassembled(cli, source_path, target):
    result = cli([f"{source_path.stem}.{target}"])

    assert result.exit_code == 1
    assert "cannot be disassembled" in result.output


def test_version(cli):
    result = cli(["--version"])

    assert get_own_version() in result.output
