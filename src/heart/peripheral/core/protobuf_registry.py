from __future__ import annotations

import sys
from dataclasses import dataclass, field
from importlib import import_module
from importlib.util import find_spec

from google.protobuf import symbol_database
from google.protobuf.message import Message

from heart.peripheral.core import protobuf_catalog
from heart.peripheral.core.protobuf_types import PeripheralPayloadType
from heart.utilities.logging import get_logger

logger = get_logger(__name__)
protobuf_symbol_database = symbol_database.Default()


@dataclass(slots=True)
class ProtobufTypeRegistry:
    _prefix_to_module: dict[str, str] = field(default_factory=dict)

    def register_type_prefix(self, prefix: str, module_path: str) -> None:
        self._prefix_to_module[prefix] = module_path

    def get_message_class(
        self, payload_type: str | PeripheralPayloadType
    ) -> type[Message] | None:
        payload_type_value = _normalize_payload_type(payload_type)
        try:
            return protobuf_symbol_database.GetSymbol(payload_type_value)
        except KeyError:
            module_path = self._resolve_module_path(payload_type_value)
            if module_path is None:
                return None
            if module_path in sys.modules:
                module = sys.modules[module_path]
            elif find_spec(module_path) is None:
                logger.warning(
                    "Failed to import protobuf module '%s' for payload type '%s'.",
                    module_path,
                    payload_type_value,
                )
                return None
            else:
                module = import_module(module_path)
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
                return protobuf_symbol_database.GetSymbol(payload_type_value)
            except KeyError:
                logger.warning(
                    "Protobuf payload type '%s' is still unknown after importing '%s'.",
                    payload_type_value,
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


def _normalize_payload_type(payload_type: str | PeripheralPayloadType) -> str:
    if isinstance(payload_type, PeripheralPayloadType):
        return payload_type.value
    return payload_type


protobuf_registry = ProtobufTypeRegistry()
protobuf_catalog.register_protobuf_catalog(protobuf_registry)
