from __future__ import annotations

from collections.abc import Iterator
from dataclasses import dataclass
from functools import cached_property
from inspect import getsourcefile, getsourcelines, isclass, isfunction, ismodule
from itertools import chain
from types import FunctionType, ModuleType

from rich.syntax import Syntax
from rich.text import Text
from rich.tree import Tree as RichTree
from textual.widgets import Tree as TextualTree
from textual.widgets._tree import TreeNode
from typing_extensions import Self


@dataclass(frozen=True)
class ModuleNode:
    obj: ModuleType
    modules: tuple[ModuleNode, ...]
    classes: tuple[ClassNode, ...]
    functions: tuple[FunctionNode, ...]

    @classmethod
    def build(cls, obj: ModuleType):
        modules = []
        classes = []
        functions = []
        for child in vars(obj).values():
            if ismodule(child) and obj.__name__ in child.__name__.split("."):
                modules.append(ModuleNode.build(child))
            elif isclass(child):
                classes.append(ClassNode.build(child))
            elif isfunction(child):
                functions.append(FunctionNode.build(child))

        return ModuleNode(
            obj=obj,
            modules=tuple(modules),
            classes=tuple(classes),
            functions=tuple(functions),
        )

    @property
    def children(self) -> Iterator[ModuleNode | ClassNode | FunctionNode]:
        yield from chain(self.modules, self.classes, self.functions)

    @cached_property
    def name(self) -> str:
        return self.obj.__name__

    @cached_property
    def qualname(self) -> str:
        return self.obj.__name__

    @cached_property
    def display_name(self) -> Text:
        s = Syntax(code="", lexer="python").highlight(f"import {self.name}")
        s.rstrip()
        return s

    def rich_tree(self, tree: RichTree | None = None) -> RichTree:
        branch = tree.add(self.display_name) if tree else RichTree(self.display_name)

        for child in self.children:
            child.rich_tree(branch)

        return branch

    def textual_tree(self, tree: TreeNode | None = None) -> TreeNode:
        branch = (
            tree.add(self.display_name, data=self)
            if tree
            else TextualTree(self.display_name, data=self).root
        )

        for child in self.children:
            child.textual_tree(branch)

        return branch


@dataclass(frozen=True)
class ClassNode:
    obj: type
    classes: tuple[ClassNode, ...]
    methods: tuple[FunctionNode, ...]

    @classmethod
    def build(cls, obj: type) -> Self:
        classes = []
        methods = []
        for child in vars(obj).values():
            if isclass(child):
                classes.append(ClassNode.build(child))
            elif isfunction(child):
                methods.append(FunctionNode.build(child))

        return ClassNode(obj=obj, classes=tuple(classes), methods=tuple(methods))

    @property
    def children(self) -> Iterator[ModuleNode | ClassNode | FunctionNode]:
        yield from chain(self.classes, self.methods)

    @cached_property
    def name(self) -> str:
        return self.obj.__name__

    @cached_property
    def qualname(self) -> str:
        return self.obj.__qualname__

    @cached_property
    def display_name(self) -> Text:
        s = Syntax(code="", lexer="python").highlight(f"class {self.name}")
        s.rstrip()
        return s

    def rich_tree(self, tree: RichTree | None = None) -> RichTree:
        branch = tree.add(self.display_name) if tree else RichTree(self.display_name)

        for child in self.children:
            child.rich_tree(branch)

        return branch

    def textual_tree(self, tree: TreeNode | None = None) -> TreeNode:
        branch = (
            tree.add(self.display_name, data=self)
            if tree
            else TextualTree(self.display_name, data=self).root
        )

        for child in self.children:
            child.textual_tree(branch)

        return branch


@dataclass(frozen=True)
class FunctionNode:
    obj: FunctionType

    @classmethod
    def build(cls, obj: FunctionType) -> Self:
        return FunctionNode(obj=obj)

    @cached_property
    def name(self) -> str:
        return self.obj.__name__

    @cached_property
    def qualname(self) -> str:
        return f"{self.obj.__module__}.{self.obj.__qualname__}"

    @cached_property
    def loc(self) -> str:
        _, start_line = getsourcelines(self.obj)
        return f"{getsourcefile(self.obj)}:{start_line}"

    @cached_property
    def display_name(self) -> Text:
        s = Syntax(code="", lexer="python").highlight(f"def {self.name}")
        s.rstrip()
        return s

    def rich_tree(self, tree: RichTree | None = None) -> RichTree:
        branch = tree.add(self.display_name) if tree else RichTree(self.display_name)

        return branch

    def textual_tree(self, tree: TreeNode | None = None) -> TreeNode:
        branch = (
            tree.add_leaf(self.display_name, data=self)
            if tree
            else TextualTree(self.display_name, data=self).root
        )

        return branch


Node = ModuleNode | ClassNode | FunctionNode
