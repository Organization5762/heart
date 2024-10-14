from typing import Generic, TypeVar


class RunnableIO:
    def run():
        pass


A = TypeVar("A", bound=RunnableIO)


class Subscriber(Generic[A]):
    @classmethod
    def get(cls) -> A:
        raise NotImplementedError("")
