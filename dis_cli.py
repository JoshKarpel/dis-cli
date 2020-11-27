#!/usr/bin/env python3

import contextlib
import dis
import functools
import importlib
import inspect
import itertools
import math
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
from typing import Dict, Iterable, Iterator, List, Optional, Tuple, Union

import click
from rich.color import ANSI_COLOR_NAMES
from rich.columns import Columns
from rich.console import Console
from rich.rule import Rule
from rich.style import Style
from rich.syntax import Syntax
from rich.table import Table
from rich.text import Text

if sys.version_info >= (3, 8):
    from functools import cached_property
else:
    cached_property = lambda func: property(functools.lru_cache(maxsize=None)(func))

T_JUMP_COLOR_MAP = Dict[int, str]
JUMP_COLORS = [
    c for c in ANSI_COLOR_NAMES.keys() if not any(("grey" in c, "black" in c, "white" in c))
]
RE_JUMP = re.compile(r"to (\d+)")

INSTRUCTION_GRID_HEADERS = ["OFF", "OPERATION", "ARGS", ""]
T_INSTRUCTION_ROW = Union[Tuple[Text, ...], str]

T_CLASS_OR_MODULE = Union[type, ModuleType]
T_FUNCTION_OR_CLASS_OR_MODULE = Union[FunctionType, T_CLASS_OR_MODULE]

DEFAULT_THEME = "monokai"


@click.command()
@click.argument(
    "target",
    nargs=-1,
)
@click.option(
    "--theme",
    default=DEFAULT_THEME,
    help=f"Choose the syntax highlighting theme (any Pygments theme). Default: {DEFAULT_THEME!r}.",
)
@click.option(
    "-p/-P",
    "--paging/--no-paging",
    "--pager/--no-pager",
    default=None,
    help="Enable/disable displaying output using the system pager. Default: enabled if the output is taller than your terminal window.",
)
@click.version_option()
def cli(
    target: Tuple[str],
    theme: str,
    paging: Optional[bool],
) -> None:
    """
    Display the source and bytecode of the TARGET Python functions.

    If you TARGET a class, all of its methods will be targeted.
    If you TARGET a module, all of its functions and classes (and therefore their methods) will be targeted.

    Any number of TARGETs may be passed; they will be displayed sequentially.
    """
    if len(target) == 0:
        ctx = click.get_current_context()
        click.echo(ctx.get_help())
        return

    # Make sure the cwd (implicit starting point for the import path) is actually on PYTHONPATH.
    # Since Python automatically adds the cwd on startup, this is only really necessary in the test suite,
    # but it's convenient to do it here for sanity.
    sys.path.append(os.getcwd())

    console = Console(highlight=True, tab_size=4)

    displays = list(make_source_and_bytecode_displays_for_targets(target_paths=target, theme=theme))
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


@dataclass(frozen=True)
class Target:
    obj: T_FUNCTION_OR_CLASS_OR_MODULE
    path: str
    imported_from: Optional[ModuleType] = None

    @cached_property
    def module(self) -> Optional[ModuleType]:
        return self.imported_from or (self.obj if self.is_module else inspect.getmodule(self.obj))

    @cached_property
    def is_module(self) -> bool:
        return inspect.ismodule(self.obj)

    @cached_property
    def is_class(self) -> bool:
        return inspect.isclass(self.obj)

    @cached_property
    def is_class_or_module(self) -> bool:
        return self.is_class or self.is_module

    @cached_property
    def is_function(self) -> bool:
        return inspect.isfunction(self.obj)

    def make_display(self, theme: str) -> Display:
        return make_source_and_bytecode_display_for_function(self.obj, theme)

    @classmethod
    def from_path(cls, path: str) -> "Target":
        parts = path.split(".")

        if len(parts) == 1:
            try:
                module = silent_import(parts[0])
                return cls(obj=module, path=path)
            except ModuleNotFoundError as e:
                # target was not *actually* a module
                raise click.ClickException(str(e))

        # Walk backwards along the split parts and try to do the import.
        # This makes the import go as deep as possible.
        for split_point in range(len(parts) - 1, 0, -1):
            module_path, obj_path = ".".join(parts[:split_point]), ".".join(parts[split_point:])

            try:
                module = obj = silent_import(module_path)
                break
            except ModuleNotFoundError:
                pass

        for target_path_part in obj_path.split("."):
            try:
                obj = getattr(obj, target_path_part)
            except AttributeError:
                raise click.ClickException(
                    f"No attribute named {target_path_part!r} found on {type(obj).__name__} {obj!r}."
                )

        return cls(obj=obj, path=path, imported_from=module)


def make_source_and_bytecode_displays_for_targets(
    target_paths: Iterable[str], theme: str
) -> Iterator[Display]:
    for path in target_paths:
        target = Target.from_path(path)

        if target.is_class_or_module:
            yield from (t.make_display(theme) for t in find_child_targets(target))
        elif target.is_function:
            yield target.make_display(theme)
        else:
            cannot_be_disassembled(target)


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


def cannot_be_disassembled(target: Target) -> None:
    msg = f"The target {target.path} = {target.obj} is a {type(target.obj).__name__}, which cannot be disassembled. Target a specific function"

    possible_targets = find_child_targets(target)
    if len(possible_targets) == 0:
        possible_targets = find_child_targets(
            Target(obj=target.module, path=".".join(target.path.split(".")[:-1]))
        )

    if len(possible_targets) == 0:
        raise click.ClickException(f"{msg}.")
    else:
        choice = random.choice(possible_targets)
        suggestion = click.style(choice.path, bold=True)
        raise click.ClickException(f"{msg}, like {suggestion}")


def find_child_targets(target: Target) -> List[Target]:
    return list(_find_child_targets(target, top_module=target.module))


def _find_child_targets(target: Target, top_module: Optional[ModuleType]) -> Iterable[Target]:
    try:
        children = vars(target.obj)
    except TypeError:  # vars() argument must have __dict__ attribute
        return

    for child in children.values():
        if inspect.getmodule(child) != top_module:  # Do not go outside of the top module
            continue
        elif inspect.isclass(child):  # Recurse into classes
            yield from _find_child_targets(
                Target(obj=child, path=f"{target.path}.{child.__name__}"),
                top_module=top_module,
            )
        elif inspect.isfunction(child):
            yield Target(obj=child, path=f"{target.path}.{child.__name__}")


def make_source_and_bytecode_display_for_function(function: FunctionType, theme: str) -> Display:
    instructions = list(dis.Bytecode(function))

    try:
        source_lines, start_line = inspect.getsourcelines(function)
    except OSError:  # This might happen if the source code is generated
        source_lines = ["NO SOURCE CODE FOUND"]
        start_line = -1

    jump_color_map = find_jump_colors(instructions)

    code_lines, instruction_rows, line_number_lines = align_source_and_instructions(
        instructions, jump_color_map, source_lines, start_line
    )

    number_column_width = max(len(l) for l in line_number_lines)
    left_col_width, right_col_width = calculate_column_widths(number_column_width)

    source_block = make_source_block(code_lines, block_width=left_col_width, theme=theme)

    bytecode_block = make_bytecode_block(
        instruction_rows,
        block_width=right_col_width,
        bgcolor=Syntax.get_theme(theme).get_background_style().bgcolor.name,
    )

    line_numbers = "\n".join(s.rjust(number_column_width) for s in line_number_lines)
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


def make_title(function: FunctionType, start_line: int) -> Text:
    source_file_path = Path(inspect.getmodule(function).__file__)
    try:
        source_file_path = source_file_path.relative_to(Path.cwd())
    except ValueError:  # path is not under the cwd
        pass

    return Text.from_markup(
        f"{type(function).__name__} [bold]{function.__module__}.{function.__qualname__}[/bold] from {source_file_path}:{start_line}"
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


def calculate_column_widths(
    line_number_width: int, ratio: float = 0.5, terminal_width: Optional[int] = None
) -> Tuple[int, int]:
    if terminal_width is None:
        terminal_width = shutil.get_terminal_size().columns
    usable_width = terminal_width - 3  # account for the border rich adds between columns
    combined_column_width = usable_width - (line_number_width * 2)  # two line number columns
    left_column_width = math.ceil(combined_column_width * ratio)
    return left_column_width, combined_column_width - left_column_width


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


if __name__ == "__main__":
    sys.exit(cli(prog_name="dis"))
