#!/usr/bin/env python3

import dis
import importlib
import inspect
import itertools
import sys
from pathlib import Path

import click
from rich.columns import Columns
from rich.console import Console
from rich.syntax import Syntax
from rich.text import Text


@click.command()
@click.argument("target")
def cli(target) -> None:
    sys.path.append(str(Path.cwd()))

    console = Console(highlight=True, tab_size=4)

    module_path, object = target.rsplit(".", 1)

    mod = importlib.import_module(module_path)
    obj = getattr(mod, object)

    bytecode = dis.Bytecode(obj)
    source_lines, start_line = inspect.getsourcelines(obj)

    left, right = [], []
    source_iter = (l.rstrip() for l in source_lines)

    instructions = list(bytecode)
    left.extend(itertools.islice(source_iter, instructions[0].starts_line - start_line))
    right.extend([""] * len(left))

    for instr in instructions:
        if instr.starts_line is not None:
            left.append(next(source_iter))
        else:
            left.append("")

        right.append(instr._disassemble().rstrip())

    code = "\n".join(left)
    instructions = "\n".join(right)

    console.print(
        Columns(
            renderables=(
                Syntax(
                    code,
                    "python",
                    theme="monokai",
                    line_numbers=True,
                    code_width=80,
                    start_line=start_line,
                ),
                Text(instructions),
            )
        )
    )


if __name__ == "__main__":
    sys.exit(cli(prog_name="dis"))
