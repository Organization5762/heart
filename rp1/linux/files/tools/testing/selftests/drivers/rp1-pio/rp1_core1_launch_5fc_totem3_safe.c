/*
 * Launch an RP1 core1 payload by hooking the totem3 RP1 firmware
 * PIO_SM_RESTART handler at 0x200005fc.
 */

#include <fcntl.h>
#include <errno.h>
#include <stdint.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <sys/ioctl.h>
#include <sys/mman.h>
#include <unistd.h>

#include <misc/rp1_pio_if.h>

#define HOOK_ADDR	0x200005fcU
#define HOOK_ORIG	0x46bd371cU
#define HOOK_PATCH	0xbd00f006U
#define LAUNCH_ADDR	0x20007000U
#define PAYLOAD_ADDR	0x20008000U
#define LAUNCH_COUNT	0x20007020U
#define PAYLOAD_STATUS	0x200080f0U

static uint64_t mmio;

static void setup_io(void)
{
	int fd = open("/dev/mem", O_RDWR | O_SYNC);
	void *map;

	if (fd < 0) {
		perror("/dev/mem");
		exit(1);
	}

	map = mmap(NULL, 0x10000000, PROT_READ | PROT_WRITE, MAP_SHARED, fd,
		   0x1f00000000ULL);
	close(fd);
	if (map == MAP_FAILED) {
		perror("mmap");
		exit(1);
	}

	mmio = (uint64_t)map;
}

#define REG32A(addr) ((volatile uint32_t *)(((addr) - 0x40000000U) + mmio))
#define REG32B(addr) ((volatile uint32_t *)(((addr) - 0x20000000U + 0x400000U) + mmio))

static void load_file(const char *path, uint32_t addr)
{
	FILE *f = fopen(path, "rb");

	if (!f) {
		perror(path);
		exit(1);
	}

	for (;;) {
		uint32_t val = 0;
		size_t n = fread(&val, 1, sizeof(val), f);

		if (!n)
			break;
		*REG32B(addr) = val;
		addr += sizeof(val);
		if (n != sizeof(val))
			break;
	}

	fclose(f);
}

static void trigger_restart(void)
{
	struct rp1_pio_sm_restart_args args = { .mask = 1 };
	struct rp1_pio_sm_claim_args claim = { .mask = 1 };
	int fd = open("/dev/pio0", O_RDWR | O_CLOEXEC);
	int ret;

	if (fd < 0) {
		perror("/dev/pio0");
		return;
	}

	ret = ioctl(fd, PIO_IOC_SM_CLAIM, &claim);
	if (ret < 0 && errno != EBUSY)
		fprintf(stderr, "PIO_IOC_SM_CLAIM ret=%d errno=%d (%s)\n",
			ret, errno, strerror(errno));

	ret = ioctl(fd, PIO_IOC_SM_RESTART, &args);
	if (ret < 0)
		fprintf(stderr, "PIO_IOC_SM_RESTART ret=%d errno=%d (%s)\n",
			ret, errno, strerror(errno));

	close(fd);
}

int main(int argc, char **argv)
{
	const char *payload = argc > 1 ? argv[1] : "blink_core1.bin";
	uint32_t old;

	setup_io();
	*REG32A(0x40014000U | 0x2000U) = 1U << 31;
	usleep(100000);

	load_file("rp1_core1_launch_5fc_totem3.bin", LAUNCH_ADDR);
	load_file(payload, PAYLOAD_ADDR);
	*REG32B(LAUNCH_COUNT) = 0;
	*REG32B(PAYLOAD_STATUS) = 0;

	*REG32A(0x4015401cU) = *REG32B(PAYLOAD_ADDR);
	*REG32A(0x40154014U) = *REG32B(PAYLOAD_ADDR + 4) ^ 0x4ff83f2dU;
	*REG32A(0x4015400cU) = 0xb007c0deU;
	*REG32A(0x40014000U | 0x3000U) = 1U << 31;
	usleep(100000);

	old = *REG32B(HOOK_ADDR);
	printf("hook old 0x%08x at 0x%08x\n", old, HOOK_ADDR);
	if (old != HOOK_ORIG) {
		printf("not patching: expected 0x%08x\n", HOOK_ORIG);
		return 2;
	}

	*REG32B(HOOK_ADDR) = HOOK_PATCH;
	printf("patched, triggering SM_RESTART\n");
	for (int i = 0; i < 20; i++) {
		uint32_t count;
		uint32_t status;

		trigger_restart();
		usleep(50000);
		count = *REG32B(LAUNCH_COUNT);
		status = *REG32B(PAYLOAD_STATUS);
		if (count || status) {
			printf("triggered count=%u status=0x%08x hook_now=0x%08x\n",
			       count, status, *REG32B(HOOK_ADDR));
			return 0;
		}
	}

	printf("not triggered, restoring\n");
	*REG32B(HOOK_ADDR) = HOOK_ORIG;
	printf("count=%u status=0x%08x hook_now=0x%08x\n",
	       *REG32B(LAUNCH_COUNT), *REG32B(PAYLOAD_STATUS),
	       *REG32B(HOOK_ADDR));
	return 3;
}
