/*
 * Dump the RP1 shared SRAM BAR window for local reverse-engineering helpers.
 */

#include <errno.h>
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
	unsigned int offset = 0;
	unsigned int length = RP1_SRAM_MAP_SIZE;
	const uint8_t *src;
	ssize_t ret;
	void *map;
	int fd;

	if (argc > 1)
		offset = strtoul(argv[1], NULL, 0);
	if (argc > 2)
		length = strtoul(argv[2], NULL, 0);
	if (offset > RP1_SRAM_MAP_SIZE || length > RP1_SRAM_MAP_SIZE ||
	    offset + length > RP1_SRAM_MAP_SIZE) {
		fprintf(stderr, "range outside RP1 SRAM BAR window\n");
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

	src = (const uint8_t *)map + offset;
	while (length) {
		ret = write(STDOUT_FILENO, src, length);
		if (ret < 0) {
			if (errno == EINTR)
				continue;
			perror("write");
			munmap(map, RP1_SRAM_MAP_SIZE);
			return 1;
		}
		src += ret;
		length -= ret;
	}

	munmap(map, RP1_SRAM_MAP_SIZE);
	return 0;
}
