# dis-cli

![PyPI](https://img.shields.io/pypi/v/dis-cli)

`dis-cli` is a command line tool for displaying Python source and bytecode.

![dis.dis](https://github.com/JoshKarpel/dis-cli/raw/master/examples/dis.dis.png)

## Usage

`dis-cli` provides a command line program, `dis`,
which takes a "import-like" path to a function to display information about.
For example, if you have a package `a`, with a submodule `b`, containing a function `c`,
you could run `dis` on it like this:
```console
$ dis a.b.c
```
Just like you could import `c` in a script:
```python
import a.b.c
```

`dis` takes a few other options.
Try running `dis --help` to see what's available!
