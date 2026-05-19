#!/usr/bin/env bash
#
# Run the regular P0/P1 chain2 scanner from a pre-packed state32 frame, bypassing
# the kernel RGB888 packer. This is an audit helper for isolating packer bugs
# from RP1 scanner/transport bugs.

set -euo pipefail

target="${1:-${RP1_HUB75_TARGET:-michael@totem3.local}}"
seconds="${RP1_HUB75_SECONDS:-120}"
pwm_bits="${RP1_HUB75_PWM_BITS:-8}"
direct_pattern="${RP1_HUB75_DIRECT_PATTERN:-row-tail}"
sram_slot_offset="${RP1_HUB75_FRAME_SLOT_OFFSET:-0xb800}"
slot_offset_dec="$((sram_slot_offset))"
slot_offset_4=$((slot_offset_dec + 4))
slot_offset_8=$((slot_offset_dec + 8))
slot_offset_12=$((slot_offset_dec + 12))
candidate="${RP1_HUB75_SCANNER_CANDIDATE:-state32-regular-p0p1-chain2-oeoffshift-preclk1-unroll8-addr8-lat2}"
remote_dir="${RP1_HUB75_REMOTE_DIR:-/home/michael/rp1-pio}"

repo_root="$(CDPATH= cd -- "$(dirname -- "${BASH_SOURCE[0]}")/.." && pwd)"
publisher_src="$repo_root/scripts/rp1_hub75_publish_direct_state32_regular.c"

if [[ ! -f "$publisher_src" ]]; then
	echo "missing publisher source: $publisher_src" >&2
	exit 2
fi

echo "target=$target"
echo "remote_dir=$remote_dir"
echo "candidate=$candidate"
echo "pwm_bits=$pwm_bits"
echo "direct_pattern=$direct_pattern"
echo "sram_slot_offset=$sram_slot_offset"

scp "$publisher_src" "$target:/tmp/rp1_hub75_publish_direct_state32_regular.c"

ssh "$target" "set -eu
	cd '$remote_dir'
	cp /tmp/rp1_hub75_publish_direct_state32_regular.c .
	cc -Wall -Wextra -Werror -O2 \
		-o rp1_hub75_publish_direct_state32_regular \
		rp1_hub75_publish_direct_state32_regular.c
	pids=\$(pidof rp1_hub75_publish_direct_state32_regular 2>/dev/null || true)
	if [ -n \"\$pids\" ]; then sudo kill \$pids || true; fi
	pids=\$(pidof rp1_sram_counter 2>/dev/null || true)
	if [ -n \"\$pids\" ]; then sudo kill \$pids || true; fi
	pids=\$(pidof rp1_core1_launch_mem 2>/dev/null || true)
	if [ -n \"\$pids\" ]; then sudo kill \$pids || true; fi
	sudo pkill -f '^/bin/sh ./rp1_hub75_run_candidate.sh' 2>/dev/null || true
	for off in '$slot_offset_dec' '$slot_offset_4' '$slot_offset_8' '$slot_offset_12'; do
		sudo ./rp1_sram_poke32 \"\$off\" 0x00000000
	done
	RP1_HUB75_PRE_START_COMMAND=\"cd '$remote_dir' && sudo ./rp1_hub75_publish_direct_state32_regular 0 '$sram_slot_offset' '$pwm_bits' '$direct_pattern'\" \
	RP1_HUB75_PWM_BITS='$pwm_bits' \
	RP1_HUB75_WAIT_FRAME_SLOT_AFTER_LAUNCH=1 \
	RP1_HUB75_FRAME_SLOT_OFFSET='$sram_slot_offset' \
	RP1_HUB75_FRAME_SLOT_EXPECTED_HIGH=0x00000010 \
	RP1_HUB75_FRAME_SLOT_TIMEOUT_SECONDS=10 \
		./rp1_hub75_run_candidate.sh '$candidate' '$seconds'
"
