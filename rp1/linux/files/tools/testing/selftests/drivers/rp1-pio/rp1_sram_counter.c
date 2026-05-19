/*
 * Read an RP1 shared-SRAM u32 counter twice and report its rate.
 */

#include <errno.h>
#include <fcntl.h>
#include <stdint.h>
#include <stdio.h>
#include <stdlib.h>
#include <sys/mman.h>
#include <time.h>
#include <unistd.h>

#define RP1_SRAM_HOST_BASE	0x1f00400000ULL
#define RP1_SRAM_MAP_SIZE	0x10000
#define DEFAULT_OFFSET		0x80f4
#define DEFAULT_SECONDS		2.0
#define NSEC_PER_SEC		1000000000ULL

static uint64_t nsec_now(void)
{
	struct timespec ts;

	if (clock_gettime(CLOCK_MONOTONIC_RAW, &ts)) {
		perror("clock_gettime");
		exit(1);
	}

	return (uint64_t)ts.tv_sec * NSEC_PER_SEC + ts.tv_nsec;
}

int main(int argc, char **argv)
{
	unsigned int offset = DEFAULT_OFFSET;
	double seconds = DEFAULT_SECONDS;
	unsigned int bytes_per_tick = 0;
	unsigned int ticks_per_frame = 0;
	unsigned int panels = 4;
	volatile uint32_t *counter;
	uint64_t t0, t1;
	uint32_t c0, c1;
	uint32_t delta;
	double elapsed;
	double rate;
	void *map;
	int fd;

	if (argc > 1)
		offset = strtoul(argv[1], NULL, 0);
	if (argc > 2)
		seconds = strtod(argv[2], NULL);
	if (argc > 3)
		bytes_per_tick = strtoul(argv[3], NULL, 0);
	if (argc > 4)
		ticks_per_frame = strtoul(argv[4], NULL, 0);
	if (argc > 5)
		panels = strtoul(argv[5], NULL, 0);
	if (offset >= RP1_SRAM_MAP_SIZE || seconds <= 0.0) {
		fprintf(stderr,
			"usage: %s [offset] [seconds] [bytes_per_tick] [ticks_per_frame] [panels]\n",
			argv[0]);
		return 2;
	}

	fd = open("/dev/mem", O_RDONLY | O_SYNC);
	if (fd < 0) {
		perror("/dev/mem");
		return 1;
	}

	map = mmap(NULL, RP1_SRAM_MAP_SIZE, PROT_READ, MAP_SHARED, fd,
		   RP1_SRAM_HOST_BASE);
	close(fd);
	if (map == MAP_FAILED) {
		perror("mmap");
		return 1;
	}

	counter = (volatile uint32_t *)((volatile uint8_t *)map + offset);
	t0 = nsec_now();
	c0 = *counter;
	usleep((useconds_t)(seconds * 1000000.0));
	t1 = nsec_now();
	c1 = *counter;
	delta = c1 - c0;
	elapsed = (double)(t1 - t0) / NSEC_PER_SEC;
	rate = (double)delta / elapsed;

	munmap(map, RP1_SRAM_MAP_SIZE);
	printf("offset=0x%x start=%u end=%u delta=%u seconds=%.6f rate=%.3f/s\n",
	       offset, c0, c1, delta, elapsed, rate);
	if (bytes_per_tick)
		printf("bytes_per_tick=%u MiB_s=%.3f MB_s=%.3f\n",
		       bytes_per_tick,
		       (rate * bytes_per_tick) / (1024.0 * 1024.0),
		       (rate * bytes_per_tick) / 1000000.0);
	if (ticks_per_frame) {
		double fps = rate / ticks_per_frame;
		double aggregate = fps * panels;

		printf("ticks_per_frame=%u panels=%u per_panel_fps=%.3f aggregate_fps=%.3f target_aggregate=1200.000 verdict=%s\n",
		       ticks_per_frame, panels, fps, aggregate,
		       aggregate >= 1200.0 ? "PASS" : "MISS");
	}
	return 0;
}
