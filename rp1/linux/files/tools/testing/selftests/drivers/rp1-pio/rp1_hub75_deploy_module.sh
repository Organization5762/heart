#!/bin/sh
#
# Build and load the custom rp1-hub75 misc-device module on a Raspberry Pi.

set -eu

target="${1:-michael@totem1.local}"
remote_dir="${RP1_HUB75_REMOTE_MODULE_DIR:-/tmp/rp1-hub75-module}"
root="$(CDPATH= cd -- "$(dirname -- "$0")/../../../../.." && pwd)"

echo "target=$target"
echo "remote_dir=$remote_dir"

ssh "$target" "rm -rf '$remote_dir' && mkdir -p '$remote_dir/include/uapi/misc'"

rsync -av \
	"$root/drivers/misc/rp1-hub75.c" \
	"$root/include/uapi/misc/rp1_hub75_if.h" \
	"$root/tools/testing/selftests/drivers/rp1-pio/rp1_hub75_module/Makefile" \
	"$target:$remote_dir/"

ssh "$target" "set -eu
	cd '$remote_dir'
	mkdir -p include/uapi/misc
	mv rp1_hub75_if.h include/uapi/misc/rp1_hub75_if.h
	echo kernel=\$(uname -r)
	test -d /lib/modules/\$(uname -r)/build
	make
"

ssh "$target" "set -eu
	cd '$remote_dir'
	sudo mkdir -p /lib/modules/\$(uname -r)/extra
	sudo install -m 0644 rp1-hub75.ko /lib/modules/\$(uname -r)/extra/rp1-hub75.ko
	sudo depmod -a
	if grep -q '^rp1_hub75 ' /proc/modules; then
		sudo modprobe -r rp1-hub75
	fi
	sudo modprobe rp1-hub75
	ls -l /dev/rp1-hub75
	grep '^rp1_hub75 ' /proc/modules
	dmesg | grep -Ei 'rp1-hub75|rp1_hub75' | tail -n 12 || true
	if command -v modinfo >/dev/null 2>&1; then
		modinfo rp1-hub75 | sed -n '1,20p'
	fi
"
