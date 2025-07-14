"""This module provides a simple hello function."""

from prefect import flow


@flow(log_prints=True)
def hello_world():
    """
    A simple Prefect flow that prints "Hello, World!".
    """
    print("Hello, World!")


# If this script is run directly, execute the hello_world flow
if __name__ == "__main__":
    hello_world()
