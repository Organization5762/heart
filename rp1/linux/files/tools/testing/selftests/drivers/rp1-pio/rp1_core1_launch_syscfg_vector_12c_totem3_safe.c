/*
 * Launch an RP1 core1 payload by patching the totem3 firmware vector entry at
 * 0x2000012c, then poking the firmware/syscfg event path.
 */

#include <errno.h>
#include <fcntl.h>
#include <stdint.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <sys/ioctl.h>
#include <sys/mman.h>
#include <unistd.h>

#include <misc/rp1_pio_if.h>

#define HOOK_ADDR	0x2000012cU
#define HOOK_ORIG	0x20000b19U
#define HOOK_PATCH	0x20007001U
#define LAUNCH_ADDR	0x20007000U
#define PAYLOAD_ADDR	0x20008000U
#define LAUNCH_COUNT	0x20007020U
#define PAYLOAD_STATUS	0x200080f0U

#define RP1_SYSCFG_PROC_EVENTS_SET 0x4000a008U
#define RP1_SYSCFG_FW_EVENT 1U

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

static void trigger_syscfg_event(void)
{
	*REG32A(RP1_SYSCFG_PROC_EVENTS_SET) = RP1_SYSCFG_FW_EVENT;
}

static void trigger_pio_ioctl(void)
{
	struct rp1_pio_sm_claim_args claim = { .mask = 1 };
	int fd = open("/dev/pio0", O_RDWR | O_CLOEXEC);
	int ret;

	if (fd < 0) {
		perror("/dev/pio0");
		return;
	}

	errno = 0;
	ret = ioctl(fd, PIO_IOC_SM_IS_CLAIMED, &claim);
	if (ret < 0)
		fprintf(stderr, "PIO_IOC_SM_IS_CLAIMED ret=%d errno=%d (%s)\n",
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

	load_file("rp1_core1_launch_syscfg_vector_12c_totem3.bin", LAUNCH_ADDR);
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
	printf("patched 12c, triggering syscfg/pio events\n");
	for (int i = 0; i < 20; i++) {
		uint32_t count;
		uint32_t status;

		trigger_syscfg_event();
		trigger_pio_ioctl();
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
