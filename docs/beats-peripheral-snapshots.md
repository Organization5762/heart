# Beats peripheral snapshot tab

## Overview

The Beats renderer now includes a Peripherals > Snapshots tab that surfaces the most recent data payload captured for each connected peripheral. This fills the gap between the event log and the hierarchical tree view by providing a quick, per-peripheral snapshot of the latest payload, tag metadata, and update timestamp.

## Materials

- `experimental/beats/src/actions/ws/providers/PeripheralProvider.tsx`
- `experimental/beats/src/actions/peripherals/peripheral_snapshots.tsx`
- `experimental/beats/src/routes/peripherals/snapshots.tsx`
- `experimental/beats/src/components/app-sidebar.tsx`
