#!/usr/bin/env python3

import click


@click.command
def cli() -> None:
    pass


if __name__ == "__main__":
    exit(cli(prog_name="dis"))
