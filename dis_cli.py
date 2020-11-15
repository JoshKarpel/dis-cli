#!/usr/bin/env python3

import contextlib
import dis
import importlib
import inspect
import itertools
import os
import random
import re
import shutil
import sys
import textwrap
import traceback
from dataclasses import dataclass
from pathlib import Path
from types import FunctionType, ModuleType
from typing import Any, Dict, Iterable, List, Optional, Tuple, Union

import click
from rich.color import ANSI_COLOR_NAMES
from rich.columns import Columns
from rich.console import Console
from rich.rule import Rule
from rich.style import Style
from rich.syntax import Syntax
from rich.table import Table
from rich.text import Text

T_JUMP_COLOR_MAP = Dict[int, str]
JUMP_COLORS = [
    c for c in ANSI_COLOR_NAMES.keys() if not any(("grey" in c, "black" in c, "white" in c))
]
RE_JUMP = re.compile(r"to (\d+)")

INSTRUCTION_GRID_HEADERS = ["OFF", "OPERATION", "ARGS", ""]
T_INSTRUCTION_ROW = Tuple[Text, ...]


NUMBER_COLUMN_WIDTH = 4


@click.command()
@click.argument("target", nargs=-1)
@click.option(
    "--theme", default="monokai", help="Choose the syntax highlighting theme (any Pygments theme)."
)
@click.option(
    "-p/-P",
    "--paging/--no-paging",
    default=None,
    help="Enable/disable displaying output using the system pager. If not passed explicitly, the pager will automatically be used if the output is taller than your terminal.",
)
@click.version_option()
def cli(
    target: Tuple[str],
    theme: str,
    paging: Optional[bool],
) -> None:
    """
    Display the source and bytecode of the TARGET Python functions.

    If you TARGET a class, its __init__ method will be displayed.

    Any number of TARGETs may be passed; they will be displayed sequentially.
    """
    # Make sure the cwd (implicit starting point for the import path) is actually on PYTHONPATH.
    # Since Python automatically adds the cwd on startup, this is only really necessary in the test suite,
    # but it's convenient to do it here for sanity.
    sys.path.append(os.getcwd())

    console = Console(highlight=True, tab_size=4)

    displays = list(make_source_and_bytecode_displays_for_targets(targets=target, theme=theme))
    parts = itertools.chain.from_iterable(display.parts for display in displays)
    total_height = sum(display.height for display in displays)

    if paging is None:  # pragma: no cover
        paging = total_height > (shutil.get_terminal_size((80, 20)).lines - 5)

    if paging:  # pragma: no cover
        with console.pager(styles=True):
            console.print(*parts)
    else:
        console.print(*parts)


@dataclass(frozen=True)
class Display:
    parts: List[Union[Rule, Columns]]
    height: int


def make_source_and_bytecode_displays_for_targets(
    targets: Iterable[str], theme: str
) -> Iterable[Display]:
    for func in map(find_function, targets):
        yield make_source_and_bytecode_display(func, theme)


def find_function(target: str) -> FunctionType:
    parts = target.split(".")

    if len(parts) == 1:
        try:
            module = silent_import(parts[0])
            raise bad_target(target, module, module)
        except ModuleNotFoundError as e:
            # target was not *actually* a module
            raise click.ClickException(str(e))

    # Walk backwards along the split parts and try to do the import.
    # This makes the import go as deep as possible.
    for split_point in range(len(parts) - 1, 0, -1):
        module_path, target_path = ".".join(parts[:split_point]), ".".join(parts[split_point:])

        try:
            module = obj = silent_import(module_path)
            break
        except ModuleNotFoundError:
            pass

    for target_path_part in target_path.split("."):
        try:
            obj = getattr(obj, target_path_part)
        except AttributeError:
            raise click.ClickException(
                f"No attribute named {target_path_part!r} found on {type(obj).__name__} {obj!r}."
            )

    # If the target is a class, display its __init__ method
    if inspect.isclass(obj):
        obj = obj.__init__  # type: ignore

    if not inspect.isfunction(obj):
        raise bad_target(target, obj, module)

    return obj


def silent_import(module_path: str) -> ModuleType:
    with open(os.devnull, "w") as f, contextlib.redirect_stdout(f), contextlib.redirect_stderr(f):
        try:
            return importlib.import_module(module_path)
        except ImportError:
            # Let ImportError propagate, since it represents normal behavior of a bad import path,
            # not something going wrong in the imported module itself.
            raise
        except Exception:
            raise click.ClickException(
                f"Encountered an exception during import of module {module_path}:\n{traceback.format_exc()}"
            )


def bad_target(target: str, obj: Any, module: ModuleType) -> click.ClickException:
    possible_targets = find_possible_targets(module)

    msg = f"The target {target} = {obj} is a {type(obj).__name__}, which cannot be disassembled. Target a specific function"

    if len(possible_targets) == 0:
        return click.ClickException(f"{msg}.")
    else:
        choice = random.choice(possible_targets)
        suggestion = click.style(f"{choice.__module__}.{choice.__qualname__}", bold=True)
        return click.ClickException(f"{msg}, like {suggestion}")


def find_possible_targets(obj: ModuleType) -> List[FunctionType]:
    return list(_find_possible_targets(obj))


def _find_possible_targets(
    module: ModuleType, top_module: Optional[ModuleType] = None
) -> Iterable[FunctionType]:
    for obj in vars(module).values():
        if (inspect.ismodule(module) and inspect.getmodule(obj) != module) or (
            inspect.isclass(module) and inspect.getmodule(module) != top_module
        ):
            continue

        if inspect.isfunction(obj):
            yield obj
        elif inspect.isclass(obj):
            yield from _find_possible_targets(obj, top_module=top_module or module)


def make_source_and_bytecode_display(function: FunctionType, theme: str) -> Display:
    instructions = list(dis.Bytecode(function))
    source_lines, start_line = inspect.getsourcelines(function)

    jump_color_map = find_jump_colors(instructions)

    code_lines, instruction_rows, line_number_lines = align_source_and_instructions(
        instructions, jump_color_map, source_lines, start_line
    )

    line_numbers = "\n".join(line_number_lines)

    half_width = calculate_half_width(line_numbers)

    source_block = make_source_block(code_lines, block_width=half_width, theme=theme)
    bytecode_block = make_bytecode_block(
        instruction_rows,
        block_width=half_width,
        bgcolor=Syntax.get_theme(theme).get_background_style().bgcolor.name,
    )
    line_numbers_block = make_nums_block(line_numbers)

    return Display(
        parts=[
            Rule(title=make_title(function, start_line), style=random.choice(JUMP_COLORS)),
            Columns(
                renderables=(line_numbers_block, source_block, line_numbers_block, bytecode_block)
            ),
        ],
        height=max(len(code_lines), len(instruction_rows)) + 1,  # the 1 is from the Rule
    )


def make_title(function, start_line: int) -> Text:
    path = Path(inspect.getmodule(function).__file__)
    try:
        path = path.relative_to(Path.cwd())
    except ValueError:  # path is not under the cwd
        pass

    return Text.from_markup(
        f"{type(function).__name__} [bold]{function.__module__}.{function.__qualname__}[/bold] from {path}:{start_line}"
    )


def align_source_and_instructions(
    instructions: List[dis.Instruction],
    jump_color_map: T_JUMP_COLOR_MAP,
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
                    str(n).rjust(NUMBER_COLUMN_WIDTH) if not len(line.strip()) == 0 else ""
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

        instruction_rows.append(make_instruction_row(instr, jump_color_map))

    # catch leftover source
    source_lines.extend(raw_source_lines[last_line_idx + 1 - start_line :])

    return source_lines, instruction_rows, nums


def make_instruction_row(
    instruction: dis.Instruction, jump_color_map: T_JUMP_COLOR_MAP
) -> T_INSTRUCTION_ROW:
    return (
        make_offset(instruction, jump_color_map),
        make_opname(instruction),
        make_arg(instruction, jump_color_map),
        make_arg_repr(instruction, jump_color_map),
    )


def make_blank_instruction_rows(n: int) -> List[T_INSTRUCTION_ROW]:
    return [(Text(),) * len(INSTRUCTION_GRID_HEADERS)] * n


def find_jump_colors(instructions: List[dis.Instruction]) -> T_JUMP_COLOR_MAP:
    jump_targets = [i.offset for i in instructions if i.is_jump_target]
    jump_colors = {
        j: color for j, color in zip(jump_targets, random.sample(JUMP_COLORS, len(jump_targets)))
    }
    return jump_colors


def calculate_half_width(line_numbers: str) -> int:
    full_width = shutil.get_terminal_size().columns - (2 + (NUMBER_COLUMN_WIDTH * 2))
    half_width = (full_width - (max(map(len, line_numbers)) * 2)) // 2
    return half_width


def make_offset(instruction: dis.Instruction, jump_color_map: T_JUMP_COLOR_MAP) -> Text:
    return Text(
        str(instruction.offset), style=Style(color=jump_color_map.get(instruction.offset, None))
    )


def make_opname(instruction: dis.Instruction) -> Text:
    return Text(instruction.opname + "  ")


def make_arg(instruction: dis.Instruction, jump_color_map: T_JUMP_COLOR_MAP) -> Text:
    return Text(
        str(instruction.arg) if instruction.arg is not None else "",
        style=Style(color=jump_color_map.get(instruction.arg)),
    )


def make_arg_repr(instruction: dis.Instruction, jump_color_map: T_JUMP_COLOR_MAP) -> Text:
    match = RE_JUMP.match(instruction.argrepr)
    return Text(
        f"{instruction.argrepr}",
        style=Style(color=jump_color_map.get(int(match.group(1)))) if match else None,
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
    return Syntax(
        "\n".join(code_lines),
        lexer_name="python",
        theme=theme,
        line_numbers=False,
        code_width=block_width,
    )


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


def get_own_version() -> str:  # pragma: versioned
    if sys.version_info < (3, 8):
        import importlib_metadata
    else:
        import importlib.metadata as importlib_metadata

    return importlib_metadata.version("dis_cli")


if __name__ == "__main__":
    sys.exit(cli(prog_name="dis"))
