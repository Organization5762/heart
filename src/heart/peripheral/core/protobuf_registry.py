from __future__ import annotations

from dataclasses import dataclass, field
from importlib import import_module

from google.protobuf import symbol_database
from google.protobuf.message import Message

from heart.utilities.logging import get_logger

logger = get_logger(__name__)
protobuf_symbol_database = symbol_database.Default()


@dataclass(slots=True)
class ProtobufTypeRegistry:
    _prefix_to_module: dict[str, str] = field(default_factory=dict)

    def register_type_prefix(self, prefix: str, module_path: str) -> None:
        self._prefix_to_module[prefix] = module_path

    def get_message_class(self, payload_type: str) -> type[Message] | None:
        try:
            return protobuf_symbol_database.GetSymbol(payload_type)
        except KeyError:
            module_path = self._resolve_module_path(payload_type)
            if module_path is None:
                return None
            try:
                module = import_module(module_path)
            except ModuleNotFoundError:
                logger.warning(
                    "Failed to import protobuf module '%s' for payload type '%s'.",
                    module_path,
                    payload_type,
                )
                return None
            register_hook = getattr(module, "register_protobuf_types", None)
            if callable(register_hook):
                try:
                    register_hook()
                except Exception:
                    logger.exception(
                        "Failed to register protobuf types from module '%s'.",
                        module_path,
                    )
                    return None
            try:
                return protobuf_symbol_database.GetSymbol(payload_type)
            except KeyError:
                logger.warning(
                    "Protobuf payload type '%s' is still unknown after importing '%s'.",
                    payload_type,
                    module_path,
                )
                return None

    def _resolve_module_path(self, payload_type: str) -> str | None:
        matching_prefixes = [
            prefix
            for prefix in self._prefix_to_module
            if payload_type.startswith(prefix)
        ]
        if not matching_prefixes:
            return None
        best_prefix = max(matching_prefixes, key=len)
        return self._prefix_to_module[best_prefix]


protobuf_registry = ProtobufTypeRegistry()

from heart.peripheral.core import \
    protobuf_catalog as _protobuf_catalog  # noqa: E402

_protobuf_catalog.register_protobuf_catalog(protobuf_registry)
