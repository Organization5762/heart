from lagom import Container as RuntimeContainer

from heart.runtime.container.initialize import \
    build_runtime_container as build_runtime_container
from heart.runtime.container.initialize import \
    configure_runtime_container as configure_runtime_container

container = RuntimeContainer()
