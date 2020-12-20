import sys

from tests.conftest import T_CLI


def get_own_version() -> str:
    if sys.version_info < (3, 8):
        import importlib_metadata
    else:
        import importlib.metadata as importlib_metadata

    return importlib_metadata.version("dis_cli")


def test_version(cli: T_CLI) -> None:
    result = cli(["--version"])

    assert get_own_version() in result.output
