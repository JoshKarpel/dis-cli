#!/usr/bin/env python3

import dis
import importlib
import inspect
import random
import re
import shutil
import sys
import textwrap
from pathlib import Path
from typing import Optional

import click
from rich.color import ANSI_COLOR_NAMES
from rich.columns import Columns
from rich.console import Console
from rich.style import Style
from rich.syntax import Syntax
from rich.table import Table
from rich.text import Text

COLORS = set(
    c for c in ANSI_COLOR_NAMES.keys() if not any(("grey" in c, "black" in c, "white" in c))
)
RE_JUMP = re.compile(r"to (\d+)")

INSTRUCTION_GRID_HEADERS = ["OFF", "OPERATION", "ARGS", ""]


@click.command()
@click.argument("target")
@click.option("--style", default="monokai")
def cli(target: str, style: Optional[str]) -> None:
    sys.path.append(str(Path.cwd()))

    console = Console(highlight=True, tab_size=4)

    parts = target.split(".")
    for split_point in range(len(parts) - 1, 0, -1):
        module_path, object = ".".join(parts[:split_point]), ".".join(parts[split_point:])

        try:
            obj = importlib.import_module(module_path)
            break
        except ModuleNotFoundError:
            pass

    for o in object.split("."):
        obj = getattr(obj, o)

    if inspect.ismodule(obj):
        raise click.ClickException("Cannot disassemble modules. Target a specific function.")

    if inspect.isclass(obj):
        obj = obj.__init__

    bytecode = dis.Bytecode(obj)
    source_lines, start_line = inspect.getsourcelines(obj)

    code_lines = []
    instruction_lines = []
    nums = [str(start_line)]
    source_lines = [l.rstrip() for l in source_lines]

    instructions = list(bytecode)
    code_lines.extend(source_lines[: instructions[0].starts_line - start_line])
    nums.extend([" "] * (len(code_lines) - 1))
    instruction_lines.extend([" "] * (len(code_lines) - 1))
    last_line_idx = instructions[0].starts_line - 1

    jump_targets = [i.offset for i in instructions if i.is_jump_target]
    jump_colors = {
        j: color for j, color in zip(jump_targets, random.sample(COLORS, len(jump_targets)))
    }

    for instr in instructions:
        if instr.starts_line is not None and instr.starts_line > last_line_idx:
            new_code_lines = source_lines[
                last_line_idx + 1 - start_line : instr.starts_line - start_line + 1
            ]
            nums.extend(
                (
                    str(n) if not len(line.strip()) == 0 else ""
                    for n, line in enumerate(new_code_lines, start=last_line_idx + 1)
                )
            )
            code_lines.extend(new_code_lines)
            spacer = [(" ",) * len(INSTRUCTION_GRID_HEADERS)] * (len(new_code_lines) - 1)
            instruction_lines.extend(spacer)
            last_line_idx = instr.starts_line
        else:
            nums.append("")
            code_lines.append("")

        arg = str(instr.arg) if instr.arg is not None else ""
        if "JUMP" in instr.opname:
            arg = Text(arg, style=Style(color=jump_colors.get(instr.arg)))

        match = RE_JUMP.match(instr.argrepr)
        argrepr = Text(
            f"{instr.argrepr}",
            style=Style(color=jump_colors.get(int(match.group(1)))) if match else None,
            no_wrap=True,
        )

        instruction_lines.append(
            (
                Text(str(instr.offset), style=Style(color=jump_colors.get(instr.offset, None)),),
                instr.opname + " ",
                arg,
                argrepr,
            )
        )

    code_lines.extend(source_lines[last_line_idx + 1 - start_line :])

    nums = "\n".join(nums)

    full_width = shutil.get_terminal_size().columns - 6
    half_width = (full_width - (max(map(len, nums)) * 2)) // 2

    code_lines = textwrap.dedent("\n".join(code_lines)).splitlines()
    code_lines = [
        line[: half_width - 1] + "…" if len(line) > half_width else line for line in code_lines
    ]

    code = Syntax(
        "\n".join(code_lines),
        lexer_name="python",
        theme=style,
        line_numbers=False,
        start_line=start_line,
        code_width=half_width,
    )

    grid = Table(
        box=None,
        padding=0,
        collapse_padding=True,
        show_header=True,
        show_footer=False,
        show_edge=False,
        pad_edge=False,
        expand=False,
        style=Style(bgcolor=code._background_color),
        width=half_width,
        header_style=Style(color="bright_white", bold=True),
    )
    for idx, header in enumerate(INSTRUCTION_GRID_HEADERS):
        grid.add_column(header=header + " ")
    for row in instruction_lines:
        grid.add_row(*row, style=Style(color="bright_white"))

    console.print(
        Columns(renderables=(Text(nums, justify="right"), code, Text(nums, justify="right"), grid),)
    )


if __name__ == "__main__":
    sys.exit(cli(prog_name="dis"))
