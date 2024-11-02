
wget https://downloads.circuitpython.org/bin/adafruit_rotary_trinkey_m0/en_US/adafruit-circuitpython-adafruit_rotary_trinkey_m0-en_US-9.2.0.uf2
cp adafruit-circuitpython-adafruit_rotary_trinkey_m0-en_US-9.2.0.uf2 /media/michael/TRINKEYBOOT || echo "Error: Please make sure to hit reset on your button."
# Wait 10 seconds as the button might need to reboot (untested if this is long enough)
echo "Waiting for reboot..."
sleep 10
echo "Copying code.py to CIRCUITPY..."
for mount_point in $(ls /media/michael | grep CIRCUITPY); do
    if [ -f /media/michael/$mount_point/boot_out.txt ]; then
        echo "Copying to /media/michael/$mount_point"
        cp Desktop/heart/drivers/rotary_encoder/code.py /media/michael/$mount_point/code.py
    else
        echo "boot_out.txt not found in /media/michael/$mount_point, skipping..."
    fi
done