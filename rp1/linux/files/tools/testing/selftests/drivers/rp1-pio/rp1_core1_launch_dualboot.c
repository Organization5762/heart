/*
 * Load an RP1 core1 payload and write both observed boot scratch register
 * layouts before releasing core1 from reset.
 */

#include <fcntl.h>
#include <stdint.h>
#include <stdio.h>
#include <stdlib.h>
#include <sys/mman.h>
#include <unistd.h>

#define PAYLOAD_ADDR	0x20008000U
#define PAYLOAD_STATUS	0x200080f0U
#define FRAME_COUNTER	0x2000f004U
#define RP1_BOOT_MAGIC	0x4015400cU
#define RP1_BOOT_PC0	0x40154010U
#define RP1_BOOT_PC1	0x40154014U
#define RP1_BOOT_SP0	0x40154018U
#define RP1_BOOT_SP1	0x4015401cU
#define RP1_BOOT_PC_XOR	0x4ff83f2dU
#define RP1_BOOT_MAGIC_VALUE 0xb007c0deU
#define RP1_RESETS_SET	0x40016000U
#define RP1_RESETS_CLR	0x40017000U
#define RP1_CORE1_RESET	(1U << 31)

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

int main(int argc, char **argv)
{
	const char *payload = argc > 1 ? argv[1] : "blink_core1.bin";
	uint32_t sp;
	uint32_t pc;
	uint32_t before;

	setup_io();
	*REG32A(RP1_RESETS_SET) = RP1_CORE1_RESET;
	usleep(100000);

	load_file(payload, PAYLOAD_ADDR);
	*REG32B(PAYLOAD_STATUS) = 0;
	sp = *REG32B(PAYLOAD_ADDR);
	pc = *REG32B(PAYLOAD_ADDR + 4);
	before = *REG32B(FRAME_COUNTER);

	printf("dualboot payload=%s sp=0x%08x pc=0x%08x counter_before=%u\n",
	       payload, sp, pc, before);
	if (!sp || !pc || !(pc & 1U)) {
		fprintf(stderr, "invalid vector\n");
		return 2;
	}

	*REG32A(RP1_BOOT_SP0) = sp;
	*REG32A(RP1_BOOT_SP1) = sp;
	*REG32A(RP1_BOOT_PC0) = pc ^ RP1_BOOT_PC_XOR;
	*REG32A(RP1_BOOT_PC1) = pc ^ RP1_BOOT_PC_XOR;
	*REG32A(RP1_BOOT_MAGIC) = RP1_BOOT_MAGIC_VALUE;
	__sync_synchronize();
	*REG32A(RP1_RESETS_CLR) = RP1_CORE1_RESET;

	for (unsigned int i = 0; i < 200; i++) {
		uint32_t status;
		uint32_t counter;

		usleep(10000);
		status = *REG32B(PAYLOAD_STATUS);
		counter = *REG32B(FRAME_COUNTER);
		if (status || counter != before) {
			printf("started status=0x%08x counter=%u pc0=0x%08x pc1=0x%08x\n",
			       status, counter, *REG32A(RP1_BOOT_PC0),
			       *REG32A(RP1_BOOT_PC1));
			return 0;
		}
	}

	printf("not started status=0x%08x counter=%u pc0=0x%08x pc1=0x%08x\n",
	       *REG32B(PAYLOAD_STATUS), *REG32B(FRAME_COUNTER),
	       *REG32A(RP1_BOOT_PC0), *REG32A(RP1_BOOT_PC1));
	return 1;
}
