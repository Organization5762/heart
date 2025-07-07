find KiCad -type f -name "*.kicad_mod" -exec cp {} /Applications/KiCad/KiCad.app/Contents/SharedSupport/footprints/ \;
find KiCad -type d -name "*.pretty" -exec sudo cp -R {} /Applications/KiCad/KiCad.app/Contents/SharedSupport/footprints/ \;
find KiCad -type f -name "*.kicad_sym" -exec cp {} /Applications/KiCad/KiCad.app/Contents/SharedSupport/symbols/ \;
