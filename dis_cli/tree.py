from __future__ import annotations

from collections.abc import Iterator
from dataclasses import dataclass
from functools import cached_property
from inspect import isclass, isfunction, ismodule
from itertools import chain
from types import FunctionType, ModuleType

from rich.console import RenderableType
from rich.syntax import Syntax
from rich.tree import Tree
from typing_extensions import Self


@dataclass(frozen=True)
class ModuleNode:
    obj: ModuleType
    modules: tuple[ModuleNode]
    classes: tuple[ClassNode]
    functions: tuple[FunctionNode]

    @classmethod
    def build(cls, obj: ModuleType):
        modules = []
        classes = []
        functions = []
        for child in vars(obj).values():
            if ismodule(child):
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
    def display_name(self) -> RenderableType:
        return Syntax(code=f"import {self.obj.__name__}", lexer="python")

    def tree(self, tree: Tree | None = None) -> Tree:
        branch = tree.add(self.display_name) if tree else Tree(self.display_name)

        for child in self.children:
            child.tree(branch)

        return branch


@dataclass(frozen=True)
class ClassNode:
    obj: type
    methods: tuple[FunctionType]
    # TODO: inner classes?

    @classmethod
    def build(cls, obj: type) -> Self:
        return ClassNode(obj=obj, methods=tuple())

    @property
    def children(self) -> Iterator[ModuleNode | ClassNode | FunctionNode]:
        yield from chain(self.methods)

    @cached_property
    def display_name(self) -> RenderableType:
        return Syntax(code=f"class {self.obj.__name__}", lexer="python")

    def tree(self, tree: Tree | None = None) -> Tree:
        branch = tree.add(self.display_name) if tree else Tree(self.display_name)

        for child in self.children:
            child.tree(branch)

        return branch


@dataclass(frozen=True)
class FunctionNode:
    obj: FunctionType
    # TODO: inner functions?

    @classmethod
    def build(cls, obj: FunctionType) -> Self:
        return FunctionNode(obj=obj)

    @cached_property
    def display_name(self) -> RenderableType:
        return Syntax(code=f"def {self.obj.__name__}", lexer="python")

    def tree(self, tree: Tree | None = None) -> Tree:
        branch = tree.add(self.display_name) if tree else Tree(self.display_name)

        return branch
