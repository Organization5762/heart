/*
 * Write one 32-bit word into the host-visible RP1 MMIO window.
 */

#include <fcntl.h>
#include <stdint.h>
#include <stdio.h>
#include <stdlib.h>
#include <sys/mman.h>
#include <unistd.h>

#define RP1_HOST_BASE	0x1f00000000ULL
#define RP1_HOST_SIZE	0x10000000ULL

int main(int argc, char **argv)
{
	volatile uint32_t *word;
	unsigned int offset;
	uint32_t value;
	void *map;
	int fd;

	if (argc != 3) {
		fprintf(stderr, "usage: %s offset value\n", argv[0]);
		return 2;
	}

	offset = strtoul(argv[1], NULL, 0);
	value = strtoul(argv[2], NULL, 0);
	if (offset > RP1_HOST_SIZE - sizeof(*word) || offset & 3) {
		fprintf(stderr, "offset out of mapped RP1 MMIO range\n");
		return 2;
	}

	fd = open("/dev/mem", O_RDWR | O_SYNC);
	if (fd < 0) {
		perror("/dev/mem");
		return 1;
	}

	map = mmap(NULL, RP1_HOST_SIZE, PROT_READ | PROT_WRITE, MAP_SHARED, fd,
		   RP1_HOST_BASE);
	close(fd);
	if (map == MAP_FAILED) {
		perror("mmap");
		return 1;
	}

	word = (volatile uint32_t *)((uint8_t *)map + offset);
	*word = value;
	printf("poke32 offset=0x%x value=0x%08x\n", offset, value);

	munmap(map, RP1_HOST_SIZE);
	return 0;
}
