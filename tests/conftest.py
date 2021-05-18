import functools
import os
import random
import string
import sys
import traceback
from pathlib import Path
from typing import Callable, Iterator, List

import pytest
from click import Command
from click.testing import CliRunner, Result

import dis_cli


@pytest.fixture
def filename() -> str:
    """
    Every source file we read in the test suite needs a unique name,
    because they will be imported as modules,
    and modules are cached by name, not contents.
    Without this, if we run the CLI on two modules with different contents but the same filename during a test session,
    the second run will see the contents of the first module.
    """
    return "_".join(random.choices(string.ascii_uppercase, k=30))


@pytest.fixture(scope="session")
def runner() -> CliRunner:
    return CliRunner()


T_CLI = Callable[[List[str]], Result]


def invoke_with_debug(runner: CliRunner, cli: Command, command: List[str]) -> Result:
    command.append("--no-paging")
    print("command:", command)
    result = runner.invoke(cli=cli, args=command)

    print("result:", result)

    if result.exc_info is not None:
        print("traceback:\n")
        exc_type, exc_val, exc_tb = result.exc_info
        traceback.print_exception(exc_type, exc_val, exc_tb, file=sys.stdout)
        print()

    print("exit code:", result.exit_code)
    print("output:\n", result.output)

    return result


@pytest.fixture(scope="session")
def cli(runner: CliRunner) -> T_CLI:
    return functools.partial(invoke_with_debug, runner, dis_cli.cli)


@pytest.fixture
def test_dir(tmp_path: Path) -> Iterator[Path]:
    cwd = os.getcwd()
    os.chdir(tmp_path)
    try:
        yield tmp_path
    finally:
        os.chdir(cwd)
