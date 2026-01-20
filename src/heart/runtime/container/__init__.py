from lagom import Container

RuntimeContainer = Container

container = RuntimeContainer()


def build_runtime_container(*args, **kwargs):  # type: ignore[override]
    from heart.runtime.container.initialize import build_runtime_container as build

    return build(*args, **kwargs)


def configure_runtime_container(*args, **kwargs) -> None:  # type: ignore[override]
    from heart.runtime.container.initialize import (
        configure_runtime_container as configure,
    )

    configure(*args, **kwargs)
