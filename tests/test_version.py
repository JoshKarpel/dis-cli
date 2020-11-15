import sys


def get_own_version() -> str:  # pragma: versioned
    if sys.version_info < (3, 8):
        import importlib_metadata
    else:
        import importlib.metadata as importlib_metadata

    return importlib_metadata.version("dis_cli")


def test_version(cli):
    result = cli(["--version"])

    assert get_own_version() in result.output
