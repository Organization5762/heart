/*
 * Read a 32-bit word from the RP1 shared-SRAM BAR window.
 */

#include <fcntl.h>
#include <stdint.h>
#include <stdio.h>
#include <stdlib.h>
#include <sys/mman.h>
#include <unistd.h>

#define RP1_SRAM_HOST_BASE	0x1f00400000ULL
#define RP1_SRAM_MAP_SIZE	0x10000

int main(int argc, char **argv)
{
	unsigned int offset;
	volatile uint32_t *word;
	void *map;
	int fd;

	if (argc != 2) {
		fprintf(stderr, "usage: %s offset\n", argv[0]);
		return 2;
	}

	offset = strtoul(argv[1], NULL, 0);
	if (offset > RP1_SRAM_MAP_SIZE - sizeof(uint32_t) || offset & 3) {
		fprintf(stderr, "offset out of mapped SRAM range\n");
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

	word = (volatile uint32_t *)((volatile uint8_t *)map + offset);
	printf("0x%08x\n", *word);
	munmap(map, RP1_SRAM_MAP_SIZE);
	return 0;
}
