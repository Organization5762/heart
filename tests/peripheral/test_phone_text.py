from __future__ import annotations

from collections.abc import Iterator

from manyfold import Graph

from heart.peripheral.phone_text import (PhoneText, phone_text_detection_route,
                                         phone_text_message_route)


class TestManyfoldPhoneText:
    """Cover graph-native BLE text detection and message publication."""

    def test_detection_node_publishes_phone_text_to_manyfold_route(
        self,
        monkeypatch,
    ) -> None:
        detected = PhoneText()

        def _detect(cls) -> Iterator[PhoneText]:
            yield detected

        monkeypatch.setattr(PhoneText, "detect", classmethod(_detect))
        graph = Graph()
        registered: list[PhoneText] = []

        handle = PhoneText.detection_node(
            on_detect=lambda peripheral, _access: registered.append(peripheral),
            start_immediately=False,
        ).install(graph)

        handle.loop_handle.loop.run(handle.loop_handle.token)

        latest = graph.latest(phone_text_detection_route())
        assert registered == [detected]
        assert latest is not None
        assert latest.value.event_type == "peripheral.phone_text.detected"
        assert latest.value.data == {
            "local_name": "PhoneText",
            "service_uuid": "1235",
            "characteristic_uuid": "5679",
        }
        assert latest.value.identity.id == "phone_text"

    def test_install_node_publishes_text_messages_to_manyfold_route(
        self,
        monkeypatch,
    ) -> None:
        phone_text = PhoneText()

        def _run(self: PhoneText) -> None:
            self._handle_message_bytes(b"hello")

        monkeypatch.setattr(PhoneText, "run", _run)
        graph = Graph()

        handle = phone_text.install_node(graph, start_immediately=False)
        handle.loop_handle.loop.run(handle.loop_handle.token)

        latest = graph.latest(phone_text_message_route())
        assert latest is not None
        assert latest.value.event_type == "peripheral.phone_text.message"
        assert latest.value.data == {"text": "hello"}
        assert latest.value.identity.id == "phone_text"
