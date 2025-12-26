from __future__ import annotations

import sys
import types

import pytest
from google.protobuf import (descriptor_pb2, descriptor_pool, message_factory,
                             symbol_database)

from heart.peripheral.core.protobuf_registry import (protobuf_registry,
                                                     protobuf_symbol_database)

FAKE_PROTO_FILE = "heart/test/proto/fake.proto"
FAKE_PROTO_PACKAGE = "heart.test.proto"
FAKE_PROTO_MESSAGE = "FakeMessage"
FAKE_PROTO_MODULE = "heart.test_support.fake_protobuf_module"


class TestProtobufTypeRegistry:
    """Verify protobuf registry behavior so payload decoding remains resilient."""

    def test_imports_module_to_resolve_symbol(self) -> None:
        """Verify module imports register symbols so protobuf payloads decode without manual setup."""
        payload_type = f"{FAKE_PROTO_PACKAGE}.{FAKE_PROTO_MESSAGE}"

        try:
            protobuf_symbol_database.GetSymbol(payload_type)
        except KeyError:
            pass
        else:
            pytest.fail(
                "Fake protobuf symbol is already registered, invalidating the test."
            )

        module = types.ModuleType(FAKE_PROTO_MODULE)

        def register_protobuf_types() -> None:
            pool = descriptor_pool.Default()
            try:
                pool.FindFileByName(FAKE_PROTO_FILE)
            except KeyError:
                file_descriptor = descriptor_pb2.FileDescriptorProto()
                file_descriptor.name = FAKE_PROTO_FILE
                file_descriptor.package = FAKE_PROTO_PACKAGE
                message_descriptor = file_descriptor.message_type.add()
                message_descriptor.name = FAKE_PROTO_MESSAGE
                field_descriptor = message_descriptor.field.add()
                field_descriptor.name = "value"
                field_descriptor.number = 1
                field_descriptor.type = descriptor_pb2.FieldDescriptorProto.TYPE_STRING
                field_descriptor.label = (
                    descriptor_pb2.FieldDescriptorProto.LABEL_OPTIONAL
                )
                pool.Add(file_descriptor)

            message_descriptor = pool.FindMessageTypeByName(payload_type)
            message_class = message_factory.GetMessageClass(message_descriptor)
            symbol_database.Default().RegisterMessage(message_class)

        module.register_protobuf_types = register_protobuf_types
        sys.modules[FAKE_PROTO_MODULE] = module

        protobuf_registry.register_type_prefix(FAKE_PROTO_PACKAGE, FAKE_PROTO_MODULE)

        message_class = protobuf_registry.get_message_class(payload_type)

        assert message_class is not None
        message = message_class(value="ready")
        assert message.value == "ready"
