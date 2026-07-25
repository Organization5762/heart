from __future__ import annotations

import json

from heart.runtime.manyfold_node import (EXTERNAL_SENSOR_STATE_TOPIC,
                                         FRAME_TICK_TOPIC,
                                         HEART_MANYFOLD_STATUS_TOPIC,
                                         HEART_TOPIC_POLICIES,
                                         INPUT_EVENT_TOPIC,
                                         MICROPHONE_SAMPLE_STREAM,
                                         NAVIGATION_TOPIC,
                                         RENDERED_FRAME_STREAM,
                                         ManyfoldNodeConfig,
                                         ManyfoldNodeRuntime, TopicDelivery,
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

    def test_topic_policy_keeps_hot_paths_local_and_all_topics_non_durable(
        self,
    ) -> None:
        policy_by_topic = {policy.topic: policy for policy in HEART_TOPIC_POLICIES}

        assert policy_by_topic[HEART_MANYFOLD_STATUS_TOPIC].delivery is (
            TopicDelivery.MESH_BEST_EFFORT
        )
        assert policy_by_topic[NAVIGATION_TOPIC].delivery is (
            TopicDelivery.MESH_BEST_EFFORT
        )
        assert policy_by_topic[EXTERNAL_SENSOR_STATE_TOPIC].delivery is (
            TopicDelivery.MESH_COALESCED
        )
        for topic in (
            FRAME_TICK_TOPIC,
            RENDERED_FRAME_STREAM,
            MICROPHONE_SAMPLE_STREAM,
            INPUT_EVENT_TOPIC,
        ):
            assert policy_by_topic[topic].delivery is TopicDelivery.LOCAL
        assert all(not policy.durable for policy in HEART_TOPIC_POLICIES)
        assert all(not policy.raft for policy in HEART_TOPIC_POLICIES)

    def test_topic_policy_manifest_is_stable_machine_readable_json(self) -> None:
        manifest = topic_policy_manifest()

        encoded = json.dumps(manifest, sort_keys=True)

        assert '"delivery": "local"' in encoded
        assert '"delivery": "mesh_best_effort"' in encoded
        assert '"delivery": "mesh_coalesced"' in encoded
