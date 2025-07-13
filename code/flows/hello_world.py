"""This module provides a simple hello function."""

from prefect import flow


@flow
def hello_world():
    """
    A simple flow that prints "Hello, World!".
    """
    print("Hello, World!")


if __name__ == "__main__":
    hello_world()
