from importlib import import_module
from textwrap import dedent

import typer.rich_utils as ru
from rich.console import Console
from rich.text import Text
from typer import Typer

from dis_cli.constants import PACKAGE_NAME, __version__
from dis_cli.tree import ModuleNode
from dis_cli.tui import DisApp

ru.STYLE_HELPTEXT = ""

console = Console()


cli = Typer(
    name=PACKAGE_NAME,
    no_args_is_help=True,
    rich_markup_mode="rich",
    help=dedent(
        """\
        """
    ),
)


@cli.command()
def version() -> None:
    """
    Display version information.
    """

    console.print(Text(__version__))


@cli.command()
def tree(module: str) -> None:
    imported = import_module(module)  # TODO: silent import
    root = ModuleNode.build(imported)
    console.print(root.rich_tree())


@cli.command()
def browse(module: str) -> None:
    imported = import_module(module)  # TODO: silent import
    root = ModuleNode.build(imported)

    tui = DisApp(root)
    tui.run()
