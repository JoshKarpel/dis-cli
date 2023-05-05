import dis
from inspect import getsourcelines
from textwrap import dedent
from types import FunctionType

from rich.rule import Rule
from rich.style import Style
from rich.syntax import Syntax
from rich.table import Table
from rich.text import Text
from textual.app import App, ComposeResult
from textual.containers import Horizontal, Vertical, VerticalScroll
from textual.events import Mount
from textual.reactive import reactive
from textual.widget import Widget
from textual.widgets import Footer, Static, Tree

from dis_cli.tree import FunctionNode, ModuleNode, Node


class DisApp(App):
    CSS_PATH = "dis_cli.css"
    BINDINGS = [
        ("f", "toggle_files", "Toggle Files"),
        ("q", "quit", "Quit"),
    ]

    show_tree = reactive(True)

    def __init__(self, root: ModuleNode):
        super().__init__()

        self.root = root

    def compose(self) -> ComposeResult:
        """Compose our UI."""
        with Horizontal():
            tree = self.root.textual_tree().tree
            tree.root.expand_all()
            tree.id = "tree-view"
            yield tree
            yield CodeWidget(id="code")

        yield Footer()

    def on_mount(self, event: Mount) -> None:
        self.query_one("#tree-view", Tree).focus()

    def watch_show_tree(self, show_tree: bool) -> None:
        """Called when show_tree is modified."""
        self.set_class(show_tree, "-show-tree")

    def action_toggle_files(self) -> None:
        """Called in response to key binding."""
        self.show_tree = not self.show_tree

    def on_tree_node_highlighted(self, event: Tree.NodeHighlighted) -> None:
        event.stop()
        code = self.query_one("#code", CodeWidget)
        # try:
        #     syntax = Syntax.from_path(
        #         event.path,
        #         line_numbers=True,
        #         word_wrap=False,
        #         indent_guides=True,
        #         theme="github-dark",
        #     )
        # except Exception:
        #     code_view.update(Traceback(theme="github-dark", width=None))
        #     self.sub_title = "ERROR"
        # else:
        #     code_view.update(syntax)
        #     self.query_one("#code-view").scroll_home(animate=False)
        #     self.sub_title = event.path
        code.node = event.node.data


class CodeWidget(Widget):
    node: Node | None = reactive(None)

    def compose(self) -> ComposeResult:
        yield Static(id="code-header")
        with Vertical():
            yield Static(id="code-display", expand=True)
            with VerticalScroll():
                with Horizontal():
                    yield Static(id="left")
                    yield Static(id="right")

    def watch_node(self, node: Node | None) -> None:
        if isinstance(node, FunctionNode):
            self.query_one("#code-display", Static).update(Rule(f"{node.qualname}"))

            source, bytecode = make_source_and_bytecode_display_for_function(
                node.obj, theme="monokai"
            )

            self.query_one("#left", Static).update(source)
            self.query_one("#right", Static).update(bytecode)
        else:
            self.query_one("#code-display", Static).update(Text())
            self.query_one("#left", Static).update(Text())
            self.query_one("#right", Static).update(Text())


InstructionRow = tuple[Text, Text, Text, Text]


def make_source_and_bytecode_display_for_function(function: FunctionType, theme: str):
    instructions = list(dis.Bytecode(function))

    source_lines, start_line = getsourcelines(function)

    code_lines, instruction_rows, line_number_lines = align_source_and_instructions(
        instructions, source_lines, start_line
    )

    number_column_width = max(len(line) for line in line_number_lines)

    source_block = make_source_block(code_lines, theme=theme)

    bytecode_block = make_bytecode_block(instruction_rows)

    "\n".join(s.rjust(number_column_width) for s in line_number_lines)

    return source_block, bytecode_block


def align_source_and_instructions(
    instructions: list[dis.Instruction],
    raw_source_lines: list[str],
    start_line: int,
) -> tuple[list[str], list[InstructionRow], list[str]]:
    raw_source_lines = [line.rstrip() for line in raw_source_lines]

    source_lines = raw_source_lines[: (instructions[0].starts_line or 1) - start_line]
    instruction_rows = make_blank_instruction_rows(len(source_lines) - 1)
    nums = [str(start_line)] + ([""] * (len(source_lines) - 1))
    last_line_idx = (instructions[0].starts_line or 1) - 1

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

        instruction_rows.append(make_instruction_row(instr))

    # catch leftover source
    source_lines.extend(raw_source_lines[last_line_idx + 1 - start_line :])

    return source_lines, instruction_rows, nums


def make_instruction_row(instruction: dis.Instruction) -> InstructionRow:
    return (
        make_offset(instruction),
        make_opname(instruction),
        make_arg(instruction),
        make_arg_repr(instruction),
    )


def make_blank_instruction_rows(n: int) -> list[InstructionRow]:
    return [(Text(), Text(), Text(), Text())] * n


def make_offset(instruction: dis.Instruction) -> Text:
    return Text(str(instruction.offset))


def make_opname(instruction: dis.Instruction) -> Text:
    return Text(instruction.opname)


def make_arg(instruction: dis.Instruction) -> Text:
    return Text(str(instruction.arg or ""))


def make_arg_repr(instruction: dis.Instruction) -> Text:
    return Text(f"{instruction.argrepr}")


def make_source_block(code_lines: list[str], theme: str) -> Syntax:
    code_lines = dedent("\n".join(code_lines)).splitlines()
    return Syntax(
        "\n".join(code_lines),
        lexer="python",
        theme=theme,
        line_numbers=False,
    )


INSTRUCTION_GRID_HEADERS = ["OFF", "OPERATION", "ARGS", ""]


def make_bytecode_block(
    instruction_rows: list[InstructionRow],
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
        header_style=Style(color="bright_white", bold=True, underline=True),
    )

    for idx, header in enumerate(INSTRUCTION_GRID_HEADERS):
        grid.add_column(header=header + " ")

    for row in instruction_rows:
        grid.add_row(*row, style=Style(color="bright_white"))

    return grid
