from textual.app import App, ComposeResult

from dis_cli.tree import ModuleNode


class DisApp(App):
    def __init__(self, root: ModuleNode):
        super().__init__()
        self.root = root

    def compose(self) -> ComposeResult:
        tree = self.root.textual_tree().tree
        tree.root.expand_all()
        tree.focus()
        yield tree
