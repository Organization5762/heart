##
# Turn off audio
##
CONFIG_FILE="/boot/firmware/config.txt"
TEMP_FILE="$(mktemp)"

awk '
{
  if ($0 ~ /^dtparam=audio=on$/) {
    print "dtparam=audio=off"
  } else {
    print $0
  }
}
' "$CONFIG_FILE" > "$TEMP_FILE"

# Only replace the file if changes were made
if ! cmp -s "$CONFIG_FILE" "$TEMP_FILE"; then
  sudo mv "$TEMP_FILE" "$CONFIG_FILE"
  echo "Updated: dtparam=audio=on → dtparam=audio=off"
else
  rm "$TEMP_FILE"
  echo "No changes made."
fi

##
# Isolate this CPU for rendering
##
grep -q '\bisolcpus=3\b' /boot/firmware/cmdline.txt || sudo sed -i -e 's/$/ isolcpus=3/' /boot/firmware/cmdline.txt


##
# Running magix setup script
###
curl https://raw.githubusercontent.com/adafruit/Raspberry-Pi-Installer-Scripts/master/rgb-matrix.sh >rgb-matrix.sh
sudo bash rgb-matrix.sh