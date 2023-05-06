def add(x: float, y: float) -> float:
    return x + y


class Class:
    def method(self) -> None:
        print("Hi!")

    class Inner:
        def inner_method(self) -> None:
            pass


def multiline_func() -> None:
    a = 2
    b = 4 + a
    c = a * b**2
    return c


def inner_func() -> None:
    def inner() -> None:
        pass


def anon() -> None:
    def foo(a):
        return print(a)

    return foo


def very_long_func() -> None:
    print("Hi!")
    print("Hi!")
    print("Hi!")
    print("Hi!")
    print("Hi!")
    print("Hi!")
    print("Hi!")
    print("Hi!")
    print("Hi!")
    print("Hi!")
    print("Hi!")
    print("Hi!")
    print("Hi!")
    print("Hi!")
    print("Hi!")
    print("Hi!")
    print("Hi!")
    print("Hi!")
    print("Hi!")
    print("Hi!")
    print("Hi!")
    print("Hi!")
    print("Hi!")
    print("Hi!")
