#!/usr/bin/env bash
#
# Reproduce the known-good RP1 HUB75 blue scanner on a totem.

set -euo pipefail

repo_root="$(CDPATH= cd -- "$(dirname -- "${BASH_SOURCE[0]}")/.." && pwd)"
bundle_root="$repo_root/rp1/linux/files"
target="${1:-${RP1_HUB75_TARGET:-michael@totem3.local}}"
remote_dir="${RP1_HUB75_REMOTE_DIR:-/home/michael/rp1-pio}"
remote_module_dir="${RP1_HUB75_REMOTE_MODULE_DIR:-/tmp/rp1-hub75-module}"
seconds="${RP1_HUB75_SECONDS:-5}"
sudo_password="${RP1_HUB75_SUDO_PASSWORD:-}"
strict_hashes="${RP1_HUB75_STRICT_HASHES:-0}"
remote_user="${target%@*}"

candidate="state32-regular-p0p1-chain2-oeoffshift-preclk1-unroll8-addr8-lat2"
payload="rp1_core1_state32_dmapipeline4x4_rr01_cols128_frame6_dwell8_regular_p0p1_chain2_oeoffshift_preclk1_unroll8_addr8_lat2"
expected_module_srcversion="DAC57640AA92F9BAD6C30F9"
expected_module_sha="243a23ffb5195c0196cb117b8530c04aa870c2d0a3aa0867b054a794b3d02141"
expected_payload_sha="f6b9097de3288f093b659b2a15cc7ee9da519349faf96c7badb8a98e4e8a5786"

if [[ ! -d "$bundle_root" ]]; then
	echo "missing Heart RP1 Linux bundle: $bundle_root" >&2
	exit 2
fi

echo "target=$target"
echo "bundle_root=$bundle_root"
echo "remote_dir=$remote_dir"
echo "candidate=$candidate"

if [[ -n "$sudo_password" ]]; then
	ssh -tt "$target" "sudo -S -p '' sh -c 'echo \"$remote_user ALL=(ALL:ALL) NOPASSWD: ALL\" > /etc/sudoers.d/010-$remote_user-nopasswd && chmod 0440 /etc/sudoers.d/010-$remote_user-nopasswd && visudo -cf /etc/sudoers.d/010-$remote_user-nopasswd'" <<<"$sudo_password"
fi

ssh "$target" "rm -rf '$remote_module_dir' && mkdir -p '$remote_module_dir/include/uapi/misc'"
scp \
	"$bundle_root/drivers/misc/rp1-hub75.c" \
	"$bundle_root/tools/testing/selftests/drivers/rp1-pio/rp1_hub75_module/Makefile" \
	"$target:$remote_module_dir/"
scp \
	"$bundle_root/include/uapi/misc/rp1_hub75_if.h" \
	"$target:$remote_module_dir/include/uapi/misc/rp1_hub75_if.h"
ssh "$target" "set -eu
	cd '$remote_module_dir'
	make -C /lib/modules/\$(uname -r)/build M=\$(pwd) modules
	sudo mkdir -p /lib/modules/\$(uname -r)/extra
	sudo install -m 0644 rp1-hub75.ko /lib/modules/\$(uname -r)/extra/rp1-hub75.ko
	sudo depmod -a
	if grep -q '^rp1_hub75 ' /proc/modules; then
		sudo modprobe -r rp1-hub75
	fi
	sudo modprobe rp1-hub75
	ls -l /dev/rp1-hub75
	grep '^rp1_hub75 ' /proc/modules
"

selftest_dir="$bundle_root/tools/testing/selftests/drivers/rp1-pio"
ssh "$target" "mkdir -p '$remote_dir'"
rsync -av \
	--include='*/' \
	--include='*.c' \
	--include='*.h' \
	--include='*.inc' \
	--include='*.s' \
	--include='*.bin' \
	--include='*.sh' \
	--include='Makefile' \
	--exclude='*' \
	"$selftest_dir/" "$target:$remote_dir/"
scp "$bundle_root/include/uapi/misc/rp1_hub75_if.h" "$target:$remote_dir/rp1_hub75_if.h"

ssh "$target" "set -eu
	cd '$remote_dir'
	mkdir -p include/misc
	cp rp1_hub75_if.h include/misc/rp1_hub75_if.h
	for src in \
		rp1_core1_launch_mem.c \
		rp1_hub75_publish_regular_green_slot.c \
		rp1_mmio_poke32.c \
		rp1_mmio_read32.c \
		rp1_sram_counter.c \
		rp1_sram_poke32.c \
		rp1_sram_read32.c
	do
		gcc -O2 -Wall -Wextra -Iinclude -o \"\${src%.c}\" \"\$src\"
	done
	chmod +x rp1_core1_build_payloads.sh rp1_hub75_run_candidate.sh
	if command -v arm-none-eabi-as >/dev/null 2>&1 ||
	   { command -v clang >/dev/null 2>&1 &&
	     command -v ld.lld >/dev/null 2>&1 &&
	     command -v llvm-objcopy >/dev/null 2>&1; }; then
		./rp1_core1_build_payloads.sh rp1_core1_launch_fwcall.s '$payload.s'
	elif [ ! -f rp1_core1_launch_fwcall.bin ] || [ ! -f '$payload.bin' ]; then
		echo 'missing payload toolchain or prebuilt launcher/payload bins' >&2
		exit 1
	fi
	module_srcversion=\$(cat /sys/module/rp1_hub75/srcversion)
	module_sha=\$(sha256sum /lib/modules/\$(uname -r)/extra/rp1-hub75.ko | awk '{print \$1}')
	payload_sha=\$(sha256sum '$payload.bin' | awk '{print \$1}')
	printf 'module_srcversion=%s\n' \"\$module_srcversion\"
	printf 'module_sha=%s\n' \"\$module_sha\"
	printf 'payload_sha=%s\n' \"\$payload_sha\"
	test \"\$payload_sha\" = '$expected_payload_sha'
	if [ '$strict_hashes' = 1 ]; then
		test \"\$module_srcversion\" = '$expected_module_srcversion'
		test \"\$module_sha\" = '$expected_module_sha'
	else
		printf 'expected_module_srcversion=%s\n' '$expected_module_srcversion'
		printf 'expected_module_sha=%s\n' '$expected_module_sha'
	fi
	pids=\$(pidof rp1_hub75_rio_static_regular || true)
	if [ -n \"\$pids\" ]; then sudo kill \$pids || true; fi
	pids=\$(pidof led-image-viewer || true)
	if [ -n \"\$pids\" ]; then sudo kill \$pids || true; fi
	sudo ./rp1_hub75_publish_regular_green_slot 0xb800 7 6 /dev/rp1-hub75 blue
	sudo env RP1_HUB75_PWM_BITS=6 ./rp1_hub75_run_candidate.sh '$candidate' '$seconds'
"
