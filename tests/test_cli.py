from pathlib import Path

import pytest


def test_smoke(cli):
    assert cli(["dis.dis"]).exit_code == 0


FUNC_NAME = "func"
FUNC = f"""
def {FUNC_NAME}():
    pass
"""


@pytest.fixture
def source_path_with_func(test_dir, filename) -> Path:
    source_path = test_dir / f"{filename}.py"
    source_path.write_text(FUNC)

    return source_path


def test_runs_successfully_on_func_source(cli, source_path_with_func):
    result = cli([f"{source_path_with_func.stem}.{FUNC_NAME}"])

    assert result.exit_code == 0


def test_func_source_in_output(cli, source_path_with_func):
    result = cli([f"{source_path_with_func.stem}.{FUNC_NAME}"])

    assert all([line in result.output for line in FUNC.splitlines()])


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
