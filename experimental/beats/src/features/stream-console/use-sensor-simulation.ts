import { useEffect, useRef, useState } from "react";
import { useConnectedPeripherals } from "@/actions/ws/providers/PeripheralProvider";
import { useWS } from "@/actions/ws/websocket";
import { getSensorCommandKey } from "@/features/stream-console/terminal-commands";
import {
  appendSensorHistory,
  defaultSensorOverride,
  extractSensorChannels,
  resolveSensorChannel,
  type SensorHistoryPoint,
  type SensorOverride,
} from "./sensor-simulation";

const HISTORY_LIMIT = 180;
const SENSOR_SAMPLE_INTERVAL_MS = 250;

export function useSensorSimulation(preferredSensorKey?: string | null) {
  const peripherals = useConnectedPeripherals();
  const { sendSensorControl } = useWS();
  const [clockSeconds, setClockSeconds] = useState(0);
  const [requestedSensorId, setRequestedSensorId] = useState<string | null>(
    null,
  );
  const [overrides, setOverrides] = useState<Record<string, SensorOverride>>(
    {},
  );
  const [history, setHistory] = useState<Record<string, SensorHistoryPoint[]>>(
    {},
  );

  const startTimeRef = useRef(0);
  const sensors = extractSensorChannels(peripherals);
  const sensorsRef = useRef(sensors);
  const overridesRef = useRef(overrides);
  const sendSensorControlRef = useRef(sendSensorControl);
  const engagedExternalKeysRef = useRef<Set<string>>(new Set());
  const preferredSensorId = preferredSensorKey
    ? (sensors.find(
        (sensor) => getSensorCommandKey(sensor) === preferredSensorKey,
      )?.id ?? null)
    : null;
  const selectedSensorId =
    requestedSensorId &&
    sensors.some((sensor) => sensor.id === requestedSensorId)
      ? requestedSensorId
      : (preferredSensorId ?? sensors[0]?.id ?? null);

  useEffect(() => {
    sensorsRef.current = sensors;
  }, [sensors]);

  useEffect(() => {
    overridesRef.current = overrides;
  }, [overrides]);

  useEffect(() => {
    sendSensorControlRef.current = sendSensorControl;
  }, [sendSensorControl]);

  useEffect(() => {
    startTimeRef.current = performance.now();

    const interval = window.setInterval(() => {
      const timeSeconds = (performance.now() - startTimeRef.current) / 1000;
      setClockSeconds(timeSeconds);

      const resolved = sensorsRef.current.map((sensor) =>
        resolveSensorChannel(
          sensor,
          overridesRef.current[sensor.id],
          timeSeconds,
        ),
      );
      const activeExternalKeys = new Set<string>();
      const nextEngagedExternalKeys = new Set(engagedExternalKeysRef.current);
      for (const sensor of resolved) {
        const override = overridesRef.current[sensor.id];
        if (!override || override.mode === "live") {
          continue;
        }
        for (const sensorKey of sensor.controlKeys) {
          activeExternalKeys.add(sensorKey);
          if (sendSensorControlRef.current(sensorKey, sensor.effectiveValue)) {
            nextEngagedExternalKeys.add(sensorKey);
          }
        }
      }
      for (const sensorKey of engagedExternalKeysRef.current) {
        if (!activeExternalKeys.has(sensorKey)) {
          if (sendSensorControlRef.current(sensorKey, null)) {
            nextEngagedExternalKeys.delete(sensorKey);
          }
        }
      }
      engagedExternalKeysRef.current = nextEngagedExternalKeys;

      setHistory((previous) => {
        const next: Record<string, SensorHistoryPoint[]> = {};
        for (const sensor of resolved) {
          const prior = previous[sensor.id] ?? [];
          next[sensor.id] = appendSensorHistory(
            prior,
            {
              timeSeconds,
              liveValue: sensor.value,
              effectiveValue: sensor.effectiveValue,
              referenceValue: sensor.referenceValue,
            },
            HISTORY_LIMIT,
          );
        }
        return next;
      });
    }, SENSOR_SAMPLE_INTERVAL_MS);

    return () => window.clearInterval(interval);
  }, []);

  useEffect(
    () => () => {
      for (const sensorKey of engagedExternalKeysRef.current) {
        sendSensorControlRef.current(sensorKey, null);
      }
      engagedExternalKeysRef.current = new Set();
    },
    [],
  );

  const resolvedSensors = sensors.map((sensor) =>
    resolveSensorChannel(sensor, overrides[sensor.id], clockSeconds),
  );
  const selectedSensor =
    resolvedSensors.find((sensor) => sensor.id === selectedSensorId) ?? null;
  const selectedSensorHistory = selectedSensorId
    ? (history[selectedSensorId] ?? [])
    : [];

  function updateSensorOverride(
    sensorId: string,
    patch: Partial<SensorOverride>,
  ) {
    setOverrides((previous) => ({
      ...previous,
      [sensorId]: {
        ...defaultSensorOverride(),
        ...previous[sensorId],
        ...patch,
      },
    }));
  }

  function resetSensorOverride(sensorId: string) {
    setOverrides((previous) => {
      const next = { ...previous };
      delete next[sensorId];
      return next;
    });
  }

  function clearSelectedSensorHistory() {
    if (!selectedSensorId) {
      return;
    }

    setHistory((previous) => ({
      ...previous,
      [selectedSensorId]: [],
    }));
  }

  return {
    clockSeconds,
    history,
    overrides,
    resolvedSensors,
    selectedSensor,
    selectedSensorHistory,
    selectedSensorId,
    setSelectedSensorId: setRequestedSensorId,
    updateSensorOverride,
    resetSensorOverride,
    clearSelectedSensorHistory,
  };
}
