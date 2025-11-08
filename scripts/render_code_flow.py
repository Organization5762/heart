#!/usr/bin/env python3
"""Render the runtime service-level diagram as an SVG without external CLIs."""


import argparse
import pathlib
import sys
from dataclasses import dataclass
from typing import Iterable, Optional
from xml.etree import ElementTree as ET


@dataclass(frozen=True)
class NodeDef:
    """Definition of a service node in the diagram."""

    identifier: str
    label: str
    role: str


@dataclass(frozen=True)
class ColumnDef:
    """Definition of a service column grouping."""

    title: str
    nodes: tuple[NodeDef, ...]


@dataclass(frozen=True)
class EdgeDef:
    """Definition of a directional relationship between services."""

    source: str
    target: str
    label: Optional[str] = None


ROLE_STYLES: dict[str, tuple[str, str]] = {
    "service": ("#0f172a", "#f8fafc"),
    "orchestrator": ("#1d4ed8", "#f8fafc"),
    "input": ("#0369a1", "#f8fafc"),
    "output": ("#7c3aed", "#f8fafc"),
}

COLUMNS: tuple[ColumnDef, ...] = (
    ColumnDef(
        "Launch & Configuration Services",
        (
            NodeDef("cli", "CLI (Typer `totem run`)", "service"),
            NodeDef("registry", "Configuration Registry", "service"),
            NodeDef(
                "configurer", "Program Configuration\n`configure(loop)`", "service"
            ),
        ),
    ),
    ColumnDef(
        "GameLoop Orchestration",
        (
            NodeDef("loop", "GameLoop Service\n(start + main loop)", "orchestrator"),
            NodeDef("app_router", "AppController / Mode Router", "orchestrator"),
            NodeDef("mode_services", "Mode Services & Renderers", "service"),
            NodeDef(
                "frame_composer", "Frame Composer\n(surface merge + timing)", "service"
            ),
        ),
    ),
    ColumnDef(
        "Peripheral & Signal Services",
        (
            NodeDef(
                "peripheral_manager", "PeripheralManager\n(background threads)", "input"
            ),
            NodeDef("switch", "Switch / BluetoothSwitch", "input"),
            NodeDef("gamepad", "Gamepad", "input"),
            NodeDef("sensors", "Accelerometer / Phyphox", "input"),
            NodeDef("heart_rate", "HeartRateManager", "input"),
            NodeDef("phone_text", "PhoneText", "input"),
        ),
    ),
    ColumnDef(
        "Display & Device Services",
        (
            NodeDef(
                "display_service", "Display Service\npygame.display.flip", "output"
            ),
            NodeDef("local_screen", "LocalScreen Window", "output"),
            NodeDef("capture", "Frame Capture\n(share surface)", "service"),
            NodeDef("device_bridge", "Device Bridge", "service"),
            NodeDef("led_matrix", "LEDMatrix Driver\n(rgbmatrix)", "output"),
        ),
    ),
)

EDGES: tuple[EdgeDef, ...] = (
    EdgeDef("cli", "registry"),
    EdgeDef("registry", "configurer"),
    EdgeDef("configurer", "loop"),
    EdgeDef("configurer", "app_router", "adds modes & scenes"),
    EdgeDef("loop", "app_router"),
    EdgeDef("loop", "frame_composer"),
    EdgeDef("app_router", "mode_services"),
    EdgeDef("mode_services", "frame_composer"),
    EdgeDef("frame_composer", "display_service"),
    EdgeDef("display_service", "local_screen"),
    EdgeDef("display_service", "capture"),
    EdgeDef("capture", "device_bridge"),
    EdgeDef("device_bridge", "led_matrix"),
    EdgeDef("loop", "peripheral_manager"),
    EdgeDef("peripheral_manager", "switch"),
    EdgeDef("peripheral_manager", "gamepad"),
    EdgeDef("peripheral_manager", "sensors"),
    EdgeDef("peripheral_manager", "heart_rate"),
    EdgeDef("peripheral_manager", "phone_text"),
    EdgeDef("switch", "app_router"),
    EdgeDef("gamepad", "app_router"),
    EdgeDef("sensors", "app_router"),
    EdgeDef("heart_rate", "app_router"),
    EdgeDef("phone_text", "app_router"),
)


@dataclass
class NodeLayout:
    """Positioning metadata for a service node."""

    node: NodeDef
    center_x: float
    center_y: float
    width: float
    height: float
    lines: tuple[str, ...]
    column_index: int


@dataclass
class ColumnLayout:
    """Positioning metadata for a column."""

    definition: ColumnDef
    x: float
    width: float
    top: float
    bottom: float


class DiagramLayout:
    """Layout container with helper lookups for edges."""

    def __init__(
        self,
        nodes: dict[str, NodeLayout],
        columns: tuple[ColumnLayout, ...],
        size: tuple[float, float],
    ):
        self.nodes = nodes
        self.columns = columns
        self.width, self.height = size

    def get_node(self, identifier: str) -> NodeLayout:
        try:
            return self.nodes[identifier]
        except KeyError as exc:  # pragma: no cover - defensive only
            raise KeyError(f"Unknown node '{identifier}' in edge definition") from exc


def _measure_node(
    node: NodeDef, line_height: float
) -> tuple[float, float, tuple[str, ...]]:
    lines = tuple(node.label.split("\n"))
    height = max(line_height * len(lines) + 22.0, 64.0)
    width = 224.0
    return width, height, lines


def compute_layout(columns: tuple[ColumnDef, ...]) -> DiagramLayout:
    margin_x = 64.0
    margin_y = 48.0
    column_gap = 80.0
    column_padding_x = 18.0
    column_padding_y_top = 18.0
    column_padding_y_bottom = 28.0
    header_height = 44.0
    node_gap = 18.0
    line_height = 18.0

    nodes: dict[str, NodeLayout] = {}
    column_layouts: list[ColumnLayout] = []
    current_x = margin_x
    max_bottom = 0.0

    for index, column in enumerate(columns):
        node_width, _, _ = _measure_node(column.nodes[0], line_height)
        column_width = node_width + column_padding_x * 2.0
        center_x = current_x + column_width / 2.0
        y_cursor = margin_y + header_height + column_padding_y_top

        column_top = margin_y
        column_bottom = column_top + header_height  # initial bottom before nodes

        for node in column.nodes:
            width, height, lines = _measure_node(node, line_height)
            center_y = y_cursor + height / 2.0
            layout = NodeLayout(
                node=node,
                center_x=center_x,
                center_y=center_y,
                width=width,
                height=height,
                lines=lines,
                column_index=index,
            )
            if node.identifier in nodes:
                raise SystemExit(
                    f"Duplicate node identifier detected: {node.identifier}"
                )
            nodes[node.identifier] = layout
            y_cursor += height + node_gap
            column_bottom = max(column_bottom, center_y + height / 2.0)

        column_bottom += column_padding_y_bottom
        column_layouts.append(
            ColumnLayout(
                definition=column,
                x=current_x,
                width=column_width,
                top=column_top,
                bottom=column_bottom,
            )
        )
        max_bottom = max(max_bottom, column_bottom)
        current_x += column_width + column_gap

    svg_width = current_x - column_gap + margin_x
    svg_height = max_bottom + margin_y
    return DiagramLayout(nodes, tuple(column_layouts), (svg_width, svg_height))


def _edge_path(
    source: NodeLayout, target: NodeLayout
) -> tuple[str, tuple[float, float]]:
    """Compute a cubic bezier path for the given edge."""

    same_column = source.column_index == target.column_index

    if same_column:
        start_x = source.center_x
        start_y = source.center_y + source.height / 2.0
        end_x = target.center_x
        end_y = target.center_y - target.height / 2.0
        delta = end_y - start_y
        control1 = (start_x, start_y + delta * 0.5)
        control2 = (end_x, end_y - delta * 0.5)
        label_pos = ((start_x + end_x) / 2.0, start_y + delta * 0.5 - 12.0)
    elif source.column_index < target.column_index:
        start_x = source.center_x + source.width / 2.0
        start_y = source.center_y
        end_x = target.center_x - target.width / 2.0
        end_y = target.center_y
        control1 = (start_x + 40.0, start_y)
        control2 = (end_x - 40.0, end_y)
        label_pos = ((start_x + end_x) / 2.0, (start_y + end_y) / 2.0 - 14.0)
    else:
        start_x = source.center_x - source.width / 2.0
        start_y = source.center_y
        end_x = target.center_x + target.width / 2.0
        end_y = target.center_y
        control1 = (start_x - 40.0, start_y)
        control2 = (end_x + 40.0, end_y)
        label_pos = ((start_x + end_x) / 2.0, (start_y + end_y) / 2.0 - 14.0)

    path = (
        f"M {start_x:.2f} {start_y:.2f} "
        f"C {control1[0]:.2f} {control1[1]:.2f} "
        f"{control2[0]:.2f} {control2[1]:.2f} "
        f"{end_x:.2f} {end_y:.2f}"
    )
    return path, label_pos


def build_svg(layout: DiagramLayout) -> ET.Element:
    svg = ET.Element(
        "svg",
        {
            "xmlns": "http://www.w3.org/2000/svg",
            "width": f"{layout.width:.0f}",
            "height": f"{layout.height:.0f}",
            "viewBox": f"0 0 {layout.width:.0f} {layout.height:.0f}",
        },
    )

    defs = ET.SubElement(svg, "defs")
    style = ET.SubElement(defs, "style")
    style.text = (
        "text { font-family: 'Inter', 'Helvetica Neue', Arial, sans-serif; fill: #0f172a; }\n"
        ".column-title { font-size: 16px; font-weight: 600; }\n"
        ".edge-label { font-size: 12px; fill: #1f2937; background: #ffffff; }\n"
    )

    marker = ET.SubElement(
        defs,
        "marker",
        {
            "id": "arrowhead",
            "markerWidth": "10",
            "markerHeight": "7",
            "refX": "10",
            "refY": "3.5",
            "orient": "auto",
            "markerUnits": "strokeWidth",
        },
    )
    ET.SubElement(marker, "path", {"d": "M 0 0 L 10 3.5 L 0 7 z", "fill": "#1f2937"})

    # Column backgrounds and titles
    for column_layout in layout.columns:
        column_group = ET.SubElement(svg, "g")
        height = column_layout.bottom - column_layout.top
        ET.SubElement(
            column_group,
            "rect",
            {
                "x": f"{column_layout.x:.2f}",
                "y": f"{column_layout.top:.2f}",
                "width": f"{column_layout.width:.2f}",
                "height": f"{height:.2f}",
                "rx": "18",
                "fill": "#e2e8f0",
                "stroke": "#cbd5f5",
            },
        )
        title_x = column_layout.x + column_layout.width / 2.0
        title_y = column_layout.top + 26.0
        title = ET.SubElement(
            column_group,
            "text",
            {
                "x": f"{title_x:.2f}",
                "y": f"{title_y:.2f}",
                "text-anchor": "middle",
                "class": "column-title",
            },
        )
        title.text = column_layout.definition.title

    # Edge paths
    edges_group = ET.SubElement(
        svg, "g", {"fill": "none", "stroke": "#1f2937", "stroke-width": "1.6"}
    )
    for edge in EDGES:
        source = layout.get_node(edge.source)
        target = layout.get_node(edge.target)
        path_d, label_pos = _edge_path(source, target)
        ET.SubElement(
            edges_group, "path", {"d": path_d, "marker-end": "url(#arrowhead)"}
        )
        if edge.label:
            label_width = max(86.0, len(edge.label) * 7.0 + 16.0)
            label_height = 20.0
            label_x = label_pos[0] - label_width / 2.0
            label_y = label_pos[1] - label_height / 2.0
            label_bg = ET.SubElement(
                svg,
                "rect",
                {
                    "x": f"{label_x:.2f}",
                    "y": f"{label_y:.2f}",
                    "width": f"{label_width:.2f}",
                    "height": f"{label_height:.2f}",
                    "rx": "4",
                    "fill": "#ffffff",
                    "stroke": "#d1d5db",
                },
            )
            label_bg.set("opacity", "0.95")
            label = ET.SubElement(
                svg,
                "text",
                {
                    "x": f"{label_pos[0]:.2f}",
                    "y": f"{label_pos[1]:.2f}",
                    "text-anchor": "middle",
                    "dominant-baseline": "middle",
                    "class": "edge-label",
                },
            )
            label.text = edge.label

    # Nodes
    nodes_group = ET.SubElement(svg, "g")
    for column_layout in layout.columns:
        for node in column_layout.definition.nodes:
            node_layout = layout.get_node(node.identifier)
            fill, text_color = ROLE_STYLES.get(node.role, ("#0f172a", "#f8fafc"))
            rect_x = node_layout.center_x - node_layout.width / 2.0
            rect_y = node_layout.center_y - node_layout.height / 2.0
            ET.SubElement(
                nodes_group,
                "rect",
                {
                    "x": f"{rect_x:.2f}",
                    "y": f"{rect_y:.2f}",
                    "width": f"{node_layout.width:.2f}",
                    "height": f"{node_layout.height:.2f}",
                    "rx": "12",
                    "fill": fill,
                    "stroke": fill,
                },
            )
            text_start_y = node_layout.center_y - (len(node_layout.lines) - 1) * 9.0
            text_element = ET.SubElement(
                nodes_group,
                "text",
                {
                    "x": f"{node_layout.center_x:.2f}",
                    "y": f"{text_start_y:.2f}",
                    "fill": text_color,
                    "text-anchor": "middle",
                },
            )
            for index, line in enumerate(node_layout.lines):
                tspan_attrib = {"x": f"{node_layout.center_x:.2f}"}
                if index != 0:
                    tspan_attrib["dy"] = "18"
                tspan = ET.SubElement(text_element, "tspan", tspan_attrib)
                tspan.text = line

    return svg


def render(output_path: pathlib.Path) -> None:
    layout = compute_layout(COLUMNS)
    svg = build_svg(layout)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    tree = ET.ElementTree(svg)
    ET.indent(tree)
    tree.write(output_path, encoding="utf-8", xml_declaration=True)


def parse_args(argv: Iterable[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--output",
        type=pathlib.Path,
        default=pathlib.Path("docs/code_flow.svg"),
        help="Where to write the generated SVG diagram.",
    )
    parser.add_argument(
        "--format",
        choices=["svg"],
        default="svg",
        help="Output format (only SVG is currently supported).",
    )
    return parser.parse_args(list(argv) if argv is not None else None)


def main(argv: Iterable[str] | None = None) -> int:
    args = parse_args(argv)
    if args.format != "svg":
        raise SystemExit("Only SVG output is supported at this time.")
    render(args.output)
    return 0


if __name__ == "__main__":
    sys.exit(main())