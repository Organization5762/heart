from __future__ import annotations

from lagom import Container


class RuntimeContainer(Container):
    """Lagom container wrapper with small runtime-specific helpers."""

    def bind_instance(self, key: type[object], value: object) -> None:
        if key in self.defined_types:
            return
        self[key] = value

    def reconfigure(self) -> "RuntimeContainer":
        rebound = RuntimeContainer()
        for defined_type in self.defined_types:
            rebound[defined_type] = self[defined_type]
        return rebound
