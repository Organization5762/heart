## Using Linux-like stuff on Windows
Windows Subsystem for Linux
https://learn.microsoft.com/en-us/windows/wsl/install

https://github.com/microsoft/WSL/issues/8693#issuecomment-1272203363

## Connecting to KiCad
https://devbisme.github.io/skidl/#kicad-schematics

set KICAD_SYMBOL_DIR=C:\Program Files\KiCad\share\kicad\kicad-symbols

You need to do this so that the parts will be loaded in

# TODO:
 export KICAD8_SYMBOL_DIR="/Applications/KiCad/KiCad.app/Contents/SharedSupport/symbols/"

## Where to get Parts From
"Part" objects require things like 'Lattice_ECP5' to load the actual part in



## KiCad Setup
https://github.com/joanbono/awesome-kicad?tab=readme-ov-file
- KiCost https://github.com/hildogjr/KiCost

# Myriad of issues:
- KiCad9 doesn't work with skidl
- How do I get the right symbols in
- Brew doesn't want to install KiCad8 which works (So skip brew install, install manually)

Import symbols
- Download from SnapMagic

Copy symbols + footprints
- cp ~/Downloads/SnapEDA-Library/SnapEDA-Library.kicad_sym /Applications/KiCad/KiCad.app/Contents/SharedSupport/symbols/
- cp -r ~/Downloads/SnapEDA-Library/Footprints.pretty /Applications/KiCad/KiCad.app/Contents/SharedSupport/footprints/

# Reverse engineering of existing boards
https://github.com/q3k/chubby75/tree/master
https://blog.yosyshq.com/p/colorlight-part-1/?utm_source=chatgpt.com


## Shopping for PCBs
Price Comparison: https://pcbshopper.com


Sierra Circuits
PCB Way
Bay Area Circuits


# Installation
ln -s "/Applications/KiCad/KiCad.app/Contents/Frameworks/Python.framework/Versions/Current/bin/python3" /usr/local/bin/kipython
kipython create_netlist.py
kipython -m pip install --user pcbflow skidl


## Code-based layout:
https://github.com/michaelgale/pcbflow
circuitpainter

## Routing Recommendations
https://sigma.octopart.com/138896719/technical_drawing/Lattice-Semiconductor-LCMXO3LF-2100C-5BG256I.pdf

This example utilizes 4-mil traces and 7-mil via drills for BGA escape
routing. Two internal layers are used as reference planes.