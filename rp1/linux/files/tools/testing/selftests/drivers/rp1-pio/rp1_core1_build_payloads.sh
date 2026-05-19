#!/bin/sh
# Build RP1 core1 assembly payloads into raw .bin images.

set -eu

usage()
{
	cat >&2 <<'EOF'
usage: rp1_core1_build_payloads.sh [--all | payload.s ...]

Builds each Cortex-M3 Thumb assembly payload to payload.bin in the current
directory.  Run this from tools/testing/selftests/drivers/rp1-pio.

Toolchain preference:
  1. arm-none-eabi-as + arm-none-eabi-ld + arm-none-eabi-objcopy
  2. clang --target=arm-none-eabi + ld.lld + llvm-objcopy
EOF
}

have()
{
	command -v "$1" >/dev/null 2>&1
}

build_gnu()
{
	src="$1"
	base="${src%.s}"
	arm-none-eabi-as -mcpu=cortex-m3 -mthumb "$src" -o "$base.o"
	arm-none-eabi-ld -Ttext=0x20008000 "$base.o" -o "$base.elf"
	arm-none-eabi-objcopy -O binary "$base.elf" "$base.bin"
}

build_llvm()
{
	src="$1"
	base="${src%.s}"
	clang --target=arm-none-eabi -mcpu=cortex-m3 -mthumb -c "$src" -o "$base.o"
	ld.lld -Ttext=0x20008000 "$base.o" -o "$base.elf"
	llvm-objcopy -O binary "$base.elf" "$base.bin"
}

if [ "$#" -eq 0 ]; then
	usage
	exit 2
fi

if [ "$1" = "--help" ] || [ "$1" = "-h" ]; then
	usage
	exit 0
fi

if have arm-none-eabi-as && have arm-none-eabi-ld && have arm-none-eabi-objcopy; then
	toolchain=gnu
elif have clang && have ld.lld && have llvm-objcopy; then
	toolchain=llvm
else
	echo "missing payload toolchain: need arm-none-eabi-* or clang+ld.lld+llvm-objcopy" >&2
	exit 1
fi

if [ "$1" = "--all" ]; then
	set -- rp1_core1_*.s
fi

for src in "$@"; do
	if [ ! -f "$src" ]; then
		echo "missing source: $src" >&2
		exit 1
	fi
	case "$src" in
		*.s) ;;
		*)
			echo "not an assembly source: $src" >&2
			exit 1
			;;
	esac

	echo "building $src with $toolchain"
	if [ "$toolchain" = "gnu" ]; then
		build_gnu "$src"
	else
		build_llvm "$src"
	fi
done
