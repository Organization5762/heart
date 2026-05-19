/*
 * Probe RP1 firmware vector entries to find which one handles a firmware event.
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

#define LAUNCH_ADDR	0x20007000U
#define LAUNCH_COUNT	0x20007020U
#define HOOK_ADDR_WORD	0x20007024U
#define HOOK_ORIG_WORD	0x20007028U
#define HOOK_RETURN_WORD 0x2000702cU
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

static void trigger_event(void)
{
	struct rp1_pio_sm_claim_args claim = { .mask = 1 };
	int fd;

	*REG32A(RP1_SYSCFG_PROC_EVENTS_SET) = RP1_SYSCFG_FW_EVENT;

	fd = open("/dev/pio0", O_RDWR | O_CLOEXEC);
	if (fd >= 0) {
		(void)ioctl(fd, PIO_IOC_SM_IS_CLAIMED, &claim);
		close(fd);
	}
}

static int candidate_word(uint32_t value)
{
	if (!(value & 1U))
		return 0;
	if ((value & ~1U) < 0x20000000U || (value & ~1U) >= 0x20010000U)
		return 0;
	return 1;
}

int main(int argc, char **argv)
{
	uint32_t start = argc > 1 ? strtoul(argv[1], NULL, 0) : 0x100U;
	uint32_t end = argc > 2 ? strtoul(argv[2], NULL, 0) : 0x180U;

	setup_io();
	load_file("rp1_core1_launch_vector_probe.bin", LAUNCH_ADDR);

	for (uint32_t off = start; off < end; off += 4) {
		uint32_t addr = 0x20000000U + off;
		uint32_t old = *REG32B(addr);

		if (!candidate_word(old))
			continue;
		*REG32B(LAUNCH_COUNT) = 0;
		*REG32B(HOOK_ADDR_WORD) = addr;
		*REG32B(HOOK_ORIG_WORD) = old;
		*REG32B(HOOK_RETURN_WORD) = old;
		*REG32B(addr) = LAUNCH_ADDR | 1U;
		__sync_synchronize();

		for (int i = 0; i < 5; i++) {
			trigger_event();
			usleep(20000);
			if (*REG32B(LAUNCH_COUNT)) {
				printf("hit off=0x%03x old=0x%08x count=%u now=0x%08x\n",
				       off, old, *REG32B(LAUNCH_COUNT), *REG32B(addr));
				return 0;
			}
		}
		*REG32B(addr) = old;
	}

	printf("no vector hit in 0x%03x..0x%03x\n", start, end);
	return 1;
}
