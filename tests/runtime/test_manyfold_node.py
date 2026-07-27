from __future__ import annotations

import json

from manyfold.architecture import TopicDeliveryClass

from heart.peripheral.core.input.events import (FRAME_TICK_TOPIC,
                                                INPUT_EVENT_TOPIC)
from heart.peripheral.core.input.external_sensors import \
    EXTERNAL_SENSOR_STATE_TOPIC
from heart.peripheral.core.input.profiles.navigation import NAVIGATION_TOPIC
from heart.peripheral.led_matrix import HEART_RENDERED_FRAME_TOPIC
from heart.peripheral.microphone import HEART_MICROPHONE_SAMPLE_TOPIC
from heart.runtime.manyfold_node import (HEART_TOPIC_POLICIES,
                                         ManyfoldNodeConfig,
                                         ManyfoldNodeRuntime,
                                         topic_policy_manifest)


class TestManyfoldNodeRuntime:
    def test_unconfigured_runtime_is_an_idempotent_disabled_boundary(self) -> None:
        runtime = ManyfoldNodeRuntime(ManyfoldNodeConfig(bootstrap=None))

        first = runtime.start()
        second = runtime.start()
        runtime.poll()
        runtime.close()
        runtime.close()

        assert first == second
        assert not first.is_enabled
        assert not first.is_started
        assert first.node is None
        assert first.lifecycle is None
        assert first.topics == ()

    def test_topic_policy_uses_durable_commands_latest_and_live_latest(self) -> None:
        policy_by_topic = {
            contract.topic: contract.policy for contract in HEART_TOPIC_POLICIES
        }

        assert policy_by_topic[NAVIGATION_TOPIC].delivery_class is (
            TopicDeliveryClass.DURABLE_APPEND
        )
        assert policy_by_topic[EXTERNAL_SENSOR_STATE_TOPIC].delivery_class is (
            TopicDeliveryClass.DURABLE_LATEST
        )
        for topic in (
            FRAME_TICK_TOPIC,
            HEART_RENDERED_FRAME_TOPIC,
            HEART_MICROPHONE_SAMPLE_TOPIC,
            INPUT_EVENT_TOPIC,
        ):
            assert policy_by_topic[topic].delivery_class is (
                TopicDeliveryClass.LIVE_LATEST
            )
            assert not policy_by_topic[topic].retains_journal_rows
        assert all(not contract.raft for contract in HEART_TOPIC_POLICIES)

    def test_topic_policy_matches_measured_payload_and_expiry_bounds(self) -> None:
        manifest = {
            contract["topic"]: contract for contract in topic_policy_manifest()
        }

        assert manifest[FRAME_TICK_TOPIC]["max_message_bytes"] == 1024
        assert manifest[HEART_RENDERED_FRAME_TOPIC]["max_message_bytes"] == (
            128 * 1024
        )
        assert manifest[HEART_MICROPHONE_SAMPLE_TOPIC]["max_message_bytes"] == 4096
        assert manifest[INPUT_EVENT_TOPIC]["max_message_bytes"] == 16 * 1024
        assert manifest[EXTERNAL_SENSOR_STATE_TOPIC]["ttl_ms"] == 2000
        assert manifest[NAVIGATION_TOPIC]["ttl_ms"] == 10_000

    def test_topic_policy_manifest_is_stable_machine_readable_json(self) -> None:
        encoded = json.dumps(topic_policy_manifest(), sort_keys=True)

        assert encoded.count('"delivery_class": "durable_append"') == 7
        assert '"delivery_class": "durable_latest"' in encoded
        assert encoded.count('"delivery_class": "volatile_latest"') == 4
        assert '"raft": false' in encoded
