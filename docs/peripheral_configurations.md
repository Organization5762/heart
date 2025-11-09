# Peripheral detection configurations

Peripheral detection is now controlled through modules in
`heart/peripheral/configurations`. Each module must expose a `configure`
function that receives a `PeripheralManager` instance and returns a
`PeripheralConfiguration`. The configuration contains the callable detectors that
are executed during `PeripheralManager.detect()` and optional
`VirtualPeripheralDefinition` objects that should be registered on the input
`EventBus`.

## Selecting a configuration

`PeripheralManager` looks up the desired configuration from the
`PERIPHERAL_CONFIGURATION` environment variable. When the variable is unset, the
`default` configuration is used. Tests and tools can also inject a custom
`PeripheralConfigurationRegistry` when constructing a manager, which makes it
possible to provide bespoke detector sets without modifying global state.

## Virtual peripherals

Configurations may include virtual peripherals alongside physical detectors. The
manager stores the declared definitions and registers them with the attached
`EventBus.virtual_peripherals` coordinator whenever bus propagation is enabled.
This allows virtual inputs—such as gesture recognisers or playlist triggers—to
be declared next to the physical hardware detectors that they augment.
