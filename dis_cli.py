#!/usr/bin/env python3

import dis
import importlib
import io
import sys

import click


@click.command()
@click.argument("target")
def cli(target) -> None:
    module_path, object = target.rsplit(".", 1)

    mod = importlib.import_module(module_path)
    obj = getattr(mod, object)

    out = io.StringIO()
    dis.dis(obj, file=out)
    out = out.getvalue()

    print(out)


if __name__ == "__main__":
    sys.exit(cli(prog_name="dis"))
