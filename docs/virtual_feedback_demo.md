# Virtual feedback flow example

`tests/test_virtual_feedback_flow.py` exercises a compact example of two sensor
peripherals feeding a virtual peripheral that aggregates their values before the
result is rendered. The test mirrors `test_multiple_game_loops_can_coexist` by
building the scenario from existing fixtures and helpers rather than introducing
new runtime code.

## Flow summary

| Stage | Implementation | Notes |
| --- | --- | --- |
| Sensor input | `_StaticScalarPeripheral` derives from the base `Peripheral` and provides a `push` helper so tests can emit values without threads. 【F:tests/test_virtual_feedback_flow.py†L19-L38】 |
| Virtual fusion | `_MetricFusionVirtualPeripheral` listens for both scalar streams and publishes mean and spread metrics once both have reported. 【F:tests/test_virtual_feedback_flow.py†L41-L74】 |
| LED matrix hand-off | The test synthesises a colour from the fused metrics and publishes it through the `LEDMatrixDisplay` provided by `GameLoop`. 【F:tests/test_virtual_feedback_flow.py†L108-L121】 |
| Feedback loop | `AverageColorLED` mirrors the LED matrix colour into a `SingleLEDDevice`, demonstrating a second loop sharing the same event bus. 【F:tests/test_virtual_feedback_flow.py†L90-L121】 |

## Running the example

Execute the test with pytest to observe the flow:

```bash
pytest tests/test_virtual_feedback_flow.py -k virtual_feedback_flow -vv
```

The assertions confirm that:

- Both `GameLoop` instances share the same event bus. 【F:tests/test_virtual_feedback_flow.py†L123-L124】
- The mirrored single LED receives the colour derived from the fused metrics. 【F:tests/test_virtual_feedback_flow.py†L118-L124】
