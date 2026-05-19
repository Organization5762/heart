/*
 * Fill an RP1 shared-SRAM BAR window with one 32-bit value.
 */

#include <fcntl.h>
#include <stdint.h>
#include <stdio.h>
#include <stdlib.h>
#include <sys/mman.h>
#include <unistd.h>

#define RP1_SRAM_HOST_BASE 0x1f00400000ULL
#define RP1_SRAM_MAP_SIZE 0x10000

int main(int argc, char **argv)
{
	unsigned int offset;
	unsigned int bytes;
	uint32_t value;
	volatile uint32_t *dst;
	void *map;
	int fd;

	if (argc != 4) {
		fprintf(stderr, "usage: %s offset bytes value\n", argv[0]);
		return 2;
	}

	offset = strtoul(argv[1], NULL, 0);
	bytes = strtoul(argv[2], NULL, 0);
	value = strtoul(argv[3], NULL, 0);
	if ((offset & 3) || (bytes & 3) ||
	    offset > RP1_SRAM_MAP_SIZE ||
	    bytes > RP1_SRAM_MAP_SIZE - offset) {
		fprintf(stderr, "offset/bytes must be 32-bit aligned inside SRAM BAR\n");
		return 2;
	}

	fd = open("/dev/mem", O_RDWR | O_SYNC);
	if (fd < 0) {
		perror("/dev/mem");
		return 1;
	}

	map = mmap(NULL, RP1_SRAM_MAP_SIZE, PROT_READ | PROT_WRITE, MAP_SHARED,
		   fd, RP1_SRAM_HOST_BASE);
	close(fd);
	if (map == MAP_FAILED) {
		perror("mmap");
		return 1;
	}

	dst = (volatile uint32_t *)((uint8_t *)map + offset);
	for (unsigned int i = 0; i < bytes / sizeof(*dst); i++)
		dst[i] = value;
	__sync_synchronize();

	printf("fill32 offset=0x%x bytes=%u value=0x%08x words=%u\n",
	       offset, bytes, value, bytes / 4);

	munmap(map, RP1_SRAM_MAP_SIZE);
	return 0;
}
