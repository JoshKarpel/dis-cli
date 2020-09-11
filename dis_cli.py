#!/usr/bin/env python3

import dis
import importlib
import inspect
import itertools
import shutil
import sys
from pathlib import Path

import click
from rich.columns import Columns
from rich.console import Console
from rich.style import Style
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

    code_lines = []
    instruction_lines = [" ".join(["JMP", " OFF", "OPCODE", "ARG".rjust(dis._OPNAME_WIDTH - 1)])]
    nums = [str(start_line)]
    source_lines = [l.rstrip() for l in source_lines]

    instructions = list(bytecode)
    code_lines.extend(source_lines[: instructions[0].starts_line - start_line])
    nums.extend([" "] * (len(code_lines) - 1))
    instruction_lines.extend([" "] * (len(code_lines) - 1))
    last_line = start_line + 1
    for instr in instructions:
        if instr.starts_line is not None:
            nums.extend(map(str, range(last_line + 1, instr.starts_line + 1)))
            leftover_code_lines = source_lines[
                last_line + 1 - start_line : instr.starts_line - start_line + 1
            ]
            code_lines.extend(leftover_code_lines)
            spacer = [" "] * (len(leftover_code_lines) - 1)
            instruction_lines.extend(spacer)
            last_line = instr.starts_line
        else:
            nums.append("")
            code_lines.append("")

        instruction_lines.append(fmt_instruction(instr))

    nums = "\n".join(nums)

    full_width = shutil.get_terminal_size().columns - 10
    half_width = (full_width - (max(map(len, nums)) * 2)) // 2

    code_lines = [line[:half_width] for line in code_lines]
    instruction_lines = [line[:half_width] for line in instruction_lines]
    code = "\n".join(code_lines)
    instructions = "\n".join(instruction_lines)

    console.print(
        Columns(
            renderables=(
                Text(nums, justify="right"),
                Syntax(
                    code,
                    "python",
                    line_numbers=False,
                    code_width=max(map(len, code_lines)) + 2,
                    start_line=start_line,
                ),
                Text(nums, justify="right"),
                Syntax(instructions, "text", code_width=max(map(len, instruction_lines)) + 2),
            )
        )
    )


def fmt_instruction(instruction: dis.Instruction) -> str:
    fields = []

    # Column: Source code line number
    # lineno_width = 4
    # if lineno_width:
    #     if instruction.starts_line is not None:
    #         lineno_fmt = "%%%dd" % lineno_width
    #         fields.append(lineno_fmt % instruction.starts_line)
    #     else:
    #         fields.append(" " * lineno_width)

    # Column: Jump target marker
    if instruction.is_jump_target:
        fields.append(" 🎯")
    else:
        fields.append("   ")

    # Column: Instruction offset from start of code sequence
    offset_width = 4
    fields.append(repr(instruction.offset).rjust(offset_width))

    # Column: Opcode name
    fields.append(instruction.opname.ljust(dis._OPNAME_WIDTH))

    # Column: Opcode argument
    if instruction.arg is not None:
        fields.append(repr(instruction.arg).rjust(dis._OPARG_WIDTH))

        # Column: Opcode argument details
        if instruction.argrepr:
            fields.append(f"({instruction.argrepr})")

    return " ".join(fields).rstrip()


if __name__ == "__main__":
    sys.exit(cli(prog_name="dis"))
