#!/usr/bin/env python3

import dis
import importlib
import inspect
import random
import re
import shutil
import sys
import textwrap
from typing import Any, Dict, Iterable, List, Optional, Tuple

import click
from rich.color import ANSI_COLOR_NAMES
from rich.columns import Columns
from rich.console import Console
from rich.style import Style
from rich.syntax import Syntax
from rich.table import Table
from rich.text import Text

T_JUMP_COLORS = Dict[int, str]
JUMP_COLORS = set(
    c for c in ANSI_COLOR_NAMES.keys() if not any(("grey" in c, "black" in c, "white" in c))
)
RE_JUMP = re.compile(r"to (\d+)")

INSTRUCTION_GRID_HEADERS = ["OFF", "OPERATION", "ARGS", ""]
T_INSTRUCTION_ROW = Tuple[Text, ...]


@click.command()
@click.argument("target", nargs=-1)
@click.option(
    "--theme", default="monokai", help="Choose the syntax highlighting theme (any Pygments theme)."
)
def cli(target: Tuple[str], theme: str) -> None:
    console = Console(highlight=True, tab_size=4)

    for idx, disp in enumerate(
        make_source_and_bytecode_display_for_targets(targets=target, theme=theme)
    ):
        if idx > 0:
            console.print()
        console.print(disp)


def make_source_and_bytecode_display_for_targets(
    targets: Iterable[str], theme: str
) -> Iterable[Columns]:
    for func in map(find_function, targets):
        yield make_source_and_bytecode_display(func, theme)


def find_function(target: str) -> Any:
    parts = target.split(".")

    # Walk backwards along the split parts and try to do the import.
    # This makes the import go as deep as possible.
    for split_point in range(len(parts) - 1, 0, -1):
        module_path, object = ".".join(parts[:split_point]), ".".join(parts[split_point:])

        try:
            obj = importlib.import_module(module_path)
            break
        except ModuleNotFoundError:
            pass

    for o in object.split("."):
        try:
            obj = getattr(obj, o)
        except AttributeError as e:
            raise click.ClickException(
                f"No function named {o!r} found in {type(obj).__name__} {obj!r}."
            )

    if inspect.ismodule(obj):
        raise click.ClickException("Cannot disassemble modules. Target a specific function.")

    # If the target is a class, display its __init__ method
    if inspect.isclass(obj):
        obj = obj.__init__  # type: ignore

    return obj


def make_source_and_bytecode_display(function: Any, theme: str) -> Columns:
    bytecode = dis.Bytecode(function)
    source_lines, start_line = inspect.getsourcelines(function)

    instructions = list(bytecode)
    jump_colors = find_jump_colors(instructions)

    code_lines, instruction_rows, line_number_lines = align_source_and_instructions(
        instructions, jump_colors, source_lines, start_line
    )

    line_numbers = "\n".join(line_number_lines)

    half_width = calculate_half_width(line_numbers)

    source_block = make_source_block(code_lines, block_width=half_width, theme=theme)
    bytecode_block = make_bytecode_block(
        instruction_rows, block_width=half_width, bgcolor=source_block._background_color
    )
    line_numbers_block = make_nums_block(line_numbers)

    return Columns(
        renderables=(line_numbers_block, source_block, line_numbers_block, bytecode_block)
    )


def align_source_and_instructions(
    instructions: List[dis.Instruction],
    jump_colors: T_JUMP_COLORS,
    raw_source_lines: List[str],
    start_line: int,
) -> Tuple[List[str], List[T_INSTRUCTION_ROW], List[str]]:
    raw_source_lines = [line.rstrip() for line in raw_source_lines]

    source_lines = raw_source_lines[: instructions[0].starts_line - start_line]
    instruction_rows = make_blank_instruction_rows(len(source_lines) - 1)
    nums = [str(start_line)] + ([""] * (len(source_lines) - 1))
    last_line_idx = instructions[0].starts_line - 1

    for instr in instructions:
        if instr.starts_line is not None and instr.starts_line > last_line_idx:
            new_code_lines = raw_source_lines[
                last_line_idx + 1 - start_line : instr.starts_line - start_line + 1
            ]
            nums.extend(
                (
                    str(n) if not len(line.strip()) == 0 else ""
                    for n, line in enumerate(new_code_lines, start=last_line_idx + 1)
                )
            )
            source_lines.extend(new_code_lines)
            spacer = [""] * (len(new_code_lines) - 1)
            instruction_rows.extend(spacer)
            last_line_idx = instr.starts_line
        else:
            nums.append("")
            source_lines.append("")

        instruction_rows.append(make_instruction_row(instr, jump_colors))

    # catch leftover source
    source_lines.extend(raw_source_lines[last_line_idx + 1 - start_line :])

    return source_lines, instruction_rows, nums


def make_instruction_row(
    instruction: dis.Instruction, jump_colors: T_JUMP_COLORS
) -> T_INSTRUCTION_ROW:
    return (
        make_offset(instruction, jump_colors),
        make_opname(instruction),
        make_arg(instruction, jump_colors),
        make_arg_repr(instruction, jump_colors),
    )


def make_blank_instruction_rows(n: int) -> List[T_INSTRUCTION_ROW]:
    return [(Text(),) * len(INSTRUCTION_GRID_HEADERS)] * n


def find_jump_colors(instructions: List[dis.Instruction]) -> T_JUMP_COLORS:
    jump_targets = [i.offset for i in instructions if i.is_jump_target]
    jump_colors = {
        j: color for j, color in zip(jump_targets, random.sample(JUMP_COLORS, len(jump_targets)))
    }
    return jump_colors


def calculate_half_width(line_numbers: str) -> int:
    full_width = shutil.get_terminal_size().columns - 6
    half_width = (full_width - (max(map(len, line_numbers)) * 2)) // 2
    return half_width


def make_offset(instruction: dis.Instruction, jump_colors: T_JUMP_COLORS) -> Text:
    return Text(
        str(instruction.offset), style=Style(color=jump_colors.get(instruction.offset, None))
    )


def make_opname(instruction: dis.Instruction) -> Text:
    return Text(instruction.opname + "  ")


def make_arg(instruction: dis.Instruction, jump_colors: T_JUMP_COLORS) -> Text:
    return Text(
        str(instruction.arg) if instruction.arg is not None else "",
        style=Style(color=jump_colors.get(instruction.arg)),
    )


def make_arg_repr(instruction: dis.Instruction, jump_colors: T_JUMP_COLORS) -> Text:
    match = RE_JUMP.match(instruction.argrepr)
    return Text(
        f"{instruction.argrepr}",
        style=Style(color=jump_colors.get(int(match.group(1)))) if match else None,
        no_wrap=True,
    )


def make_nums_block(nums: str) -> Text:
    return Text(nums, justify="right")


def make_source_block(
    code_lines: List[str],
    block_width: int,
    theme: Optional[str] = None,
) -> Syntax:
    code_lines = textwrap.dedent("\n".join(code_lines)).splitlines()
    code_lines = [
        line[: block_width - 1] + "…" if len(line) > block_width else line for line in code_lines
    ]
    code = Syntax(
        "\n".join(code_lines),
        lexer_name="python",
        theme=theme,
        line_numbers=False,
        code_width=block_width,
    )
    return code


def make_bytecode_block(
    instruction_rows: List[T_INSTRUCTION_ROW], block_width: int, bgcolor: str
) -> Table:
    grid = Table(
        box=None,
        padding=0,
        collapse_padding=True,
        show_header=True,
        show_footer=False,
        show_edge=False,
        pad_edge=False,
        expand=False,
        style=Style(bgcolor=bgcolor),
        width=block_width,
        header_style=Style(color="bright_white", bold=True, underline=True),
    )

    for idx, header in enumerate(INSTRUCTION_GRID_HEADERS):
        grid.add_column(header=header + " ")

    for row in instruction_rows:
        grid.add_row(*row, style=Style(color="bright_white"))

    return grid


if __name__ == "__main__":
    sys.exit(cli(prog_name="dis"))
