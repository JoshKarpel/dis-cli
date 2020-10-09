import functools

import pytest
from click.testing import CliRunner

from dis_cli import cli


@pytest.fixture
def invoke():
    return functools.partial(CliRunner().invoke, cli)
