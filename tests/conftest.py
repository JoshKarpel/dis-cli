import functools
import os
import random
import string
import sys
import traceback
from pathlib import Path

import pytest
from click.testing import CliRunner, Result

import dis_cli

USED_FILENAMES = set()
FILENAME_LENGTH = 30


@pytest.fixture
def filename() -> str:
    """
    Every source file we read in the test suite needs a unique name,
    because they will be imported as modules,
    and modules are cached by name, not contents.
    Without this, if we run the CLI on two modules with different contents but the same filename during a test session,
    the second run will see the contents of the first module.
    """
    name = "".join(random.choices(string.ascii_letters, k=FILENAME_LENGTH))

    while name in USED_FILENAMES:
        name = "".join(random.choices(string.ascii_letters, k=FILENAME_LENGTH))

    USED_FILENAMES.add(name)

    return name


@pytest.fixture
def runner() -> CliRunner:
    return CliRunner()


def invoke_with_debug(runner: CliRunner, cli, *args, **kwargs) -> Result:
    print("command:", args[0])
    result = runner.invoke(cli, *args, **kwargs)

    print("result:", result)

    if result.exception:
        print("traceback:\n")
        traceback.print_exception(*result.exc_info, file=sys.stdout)
        print()

    print("exit code:", result.exit_code)
    print("output:\n", result.output)

    return result


@pytest.fixture
def cli(runner):
    return functools.partial(invoke_with_debug, runner, dis_cli.cli)


@pytest.fixture
def test_dir(tmp_path) -> Path:
    cwd = os.getcwd()
    os.chdir(tmp_path)
    try:
        yield tmp_path
    finally:
        os.chdir(cwd)
