from __future__ import annotations

import numpy as np

from heart.peripheral.ir_sensor_array import (SPEED_OF_LIGHT, IRArrayDMAQueue,
                                              IRDMAPacket, IRSample,
                                              IRSensorArray,
                                              MultilaterationSolver,
                                              radial_layout)


def _make_packet(samples: list[IRSample]) -> IRDMAPacket:
    queue = IRArrayDMAQueue(buffer_size=len(samples))
    for sample in samples:
        queue.push_sample(sample)
    queue.flush()
    packet = queue.pop()
    assert packet is not None
    return packet


class TestPeripheralIrSensorArray:
    """Group Peripheral Ir Sensor Array tests so peripheral ir sensor array behaviour stays reliable. This preserves confidence in peripheral ir sensor array for end-to-end scenarios."""

    def test_dma_queue_emits_double_buffer_packets(self):
        """Verify that dma queue emits double buffer packets. This ensures event orchestration remains reliable."""
        queue = IRArrayDMAQueue(buffer_size=2)

        samples = [
            IRSample(frame_id=1, sensor_index=0, timestamp=0.001, level=1, duration_us=500),
            IRSample(frame_id=1, sensor_index=1, timestamp=0.0015, level=0, duration_us=750),
            IRSample(frame_id=2, sensor_index=0, timestamp=0.002, level=1, duration_us=900),
        ]

        for sample in samples:
            queue.push_sample(sample)

        first = queue.pop()
        assert first is not None
        assert first.buffer_id == 0
        assert first.samples == tuple(samples[:2])

        queue.flush()
        second = queue.pop()
        assert second is not None
        assert second.buffer_id == 1
        assert second.samples == (samples[2],)



    def test_multilateration_solver_converges_on_known_point(self):
        """Verify that multilateration solver converges on known point. This keeps the system behaviour reliable for operators."""
        sensors = radial_layout(radius=0.2)
        solver = MultilaterationSolver(sensors)
        emitter = np.array([0.05, 0.03, 0.02])

        arrival_times = []
        for sensor in sensors:
            sensor_vec = np.array(sensor)
            distance = np.linalg.norm(emitter - sensor_vec)
            arrival_times.append(distance / SPEED_OF_LIGHT)

        position, confidence, rmse = solver.solve(arrival_times)

        assert np.allclose(position, emitter, atol=1e-3)
        assert confidence > 0.99
        assert rmse < 1e-10



    def test_sensor_array_emits_frame_event(self):
        """Verify that sensor array emits frame event. This keeps rendering behaviour consistent across scenes."""
        sensors = radial_layout(radius=0.16)
        captured: list[dict] = []

        # subscribe(IRSensorArray.EVENT_FRAME, lambda event: captured.append(event.data))

        array = IRSensorArray(sensor_positions=sensors)

        true_position = np.array([0.04, -0.02, 0.01])
        offsets = {0: 2e-6, 1: -1e-6, 2: 3e-6, 3: -2e-6}
        array.apply_calibration(offsets)

        samples: list[IRSample] = []
        for index, sensor in enumerate(sensors):
            sensor_vec = np.array(sensor)
            distance = np.linalg.norm(true_position - sensor_vec)
            nominal = distance / SPEED_OF_LIGHT
            observed = nominal + offsets[index]
            duration = 1200 if index % 2 else 800
            samples.append(
                IRSample(
                    frame_id=42,
                    sensor_index=index,
                    timestamp=observed,
                    level=1,
                    duration_us=duration,
                )
            )

        packet = _make_packet(samples)
        array.ingest_packet(packet)

        assert captured, "Expected event emission"
        event = captured[0]
        assert event["frame_id"] == 42
        assert np.allclose(event["position"], true_position.tolist(), atol=1e-3)
        assert event["confidence"] > 0.95
        assert event["rmse"] < 1e-10
        assert event["bits"] == [0, 1, 0, 1]
