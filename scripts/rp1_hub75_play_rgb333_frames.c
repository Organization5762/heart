#include <errno.h>
#include <fcntl.h>
#include <stdint.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <sys/mman.h>
#include <time.h>
#include <unistd.h>

#define RP1_SRAM_HOST_BASE 0x1f00400000ULL
#define RP1_SRAM_MAP_SIZE 0x10000U
#define DEFAULT_OFFSET 0xc000U
#define DEFAULT_INTERVAL_MS 30U
#define ROWPAIRS 32U
#define COLS 64U
#define ROWS 64U
#define RGB_FRAME_BYTES (ROWS * COLS * 3U)
#define RGB333_WORDS (ROWPAIRS * COLS)
#define RGB333_BYTES (RGB333_WORDS * sizeof(uint32_t))

static void sleep_ms(unsigned int ms)
{
	struct timespec ts = {
		.tv_sec = ms / 1000U,
		.tv_nsec = (long)(ms % 1000U) * 1000000L,
	};

	while (nanosleep(&ts, &ts) != 0 && errno == EINTR)
		;
}

static uint8_t gamma22_level(uint8_t channel)
{
	static const uint8_t threshold[7] = {
		77, 127, 160, 187, 209, 229, 247,
	};
	uint8_t level = 0;

	while (level < 7 && channel >= threshold[level])
		level++;

	return level;
}

static uint16_t pack_pixel(const uint8_t *pixel)
{
	return gamma22_level(pixel[0]) |
	       (uint16_t)(gamma22_level(pixel[1]) << 3) |
	       (uint16_t)(gamma22_level(pixel[2]) << 6);
}

static void pack_frame(uint32_t *dst, const uint8_t *src)
{
	unsigned int row;
	unsigned int col;

	for (row = 0; row < ROWPAIRS; row++) {
		for (col = 0; col < COLS; col++) {
			const uint8_t *upper = src + (row * COLS + col) * 3U;
			const uint8_t *lower = src + ((row + ROWPAIRS) * COLS + col) * 3U;

			dst[row * COLS + col] =
				pack_pixel(upper) | ((uint32_t)pack_pixel(lower) << 16);
		}
	}
}

static double monotonic_seconds(void)
{
	struct timespec ts;

	if (clock_gettime(CLOCK_MONOTONIC, &ts) != 0) {
		perror("clock_gettime");
		exit(1);
	}

	return (double)ts.tv_sec + (double)ts.tv_nsec / 1000000000.0;
}

int main(int argc, char **argv)
{
	const char *frames_path;
	double seconds;
	unsigned int interval_ms = DEFAULT_INTERVAL_MS;
	uint32_t offset = DEFAULT_OFFSET;
	uint32_t packed[RGB333_WORDS];
	volatile uint8_t *sram;
	unsigned char *frames;
	long file_size;
	unsigned int frame_count;
	double deadline;
	void *map;
	FILE *file;
	int mem_fd;

	if (argc < 3 || argc > 5) {
		fprintf(stderr, "usage: %s frames.rgb seconds [interval_ms] [sram_offset]\n",
			argv[0]);
		return 2;
	}

	frames_path = argv[1];
	seconds = strtod(argv[2], NULL);
	if (argc > 3)
		interval_ms = (unsigned int)strtoul(argv[3], NULL, 0);
	if (argc > 4)
		offset = (uint32_t)strtoul(argv[4], NULL, 0);
	if (seconds <= 0.0 || !interval_ms || offset + RGB333_BYTES > RP1_SRAM_MAP_SIZE) {
		fprintf(stderr, "invalid seconds, interval, or offset\n");
		return 2;
	}

	file = fopen(frames_path, "rb");
	if (!file) {
		perror(frames_path);
		return 1;
	}
	if (fseek(file, 0, SEEK_END) != 0) {
		perror("fseek");
		fclose(file);
		return 1;
	}
	file_size = ftell(file);
	if (file_size <= 0 || file_size % RGB_FRAME_BYTES) {
		fprintf(stderr, "frame file size %ld is not a multiple of %u\n",
			file_size, RGB_FRAME_BYTES);
		fclose(file);
		return 2;
	}
	rewind(file);

	frames = malloc((size_t)file_size);
	if (!frames) {
		perror("malloc");
		fclose(file);
		return 1;
	}
	if (fread(frames, 1, (size_t)file_size, file) != (size_t)file_size) {
		perror("fread");
		free(frames);
		fclose(file);
		return 1;
	}
	fclose(file);
	frame_count = (unsigned int)((size_t)file_size / RGB_FRAME_BYTES);

	mem_fd = open("/dev/mem", O_RDWR | O_SYNC);
	if (mem_fd < 0) {
		perror("/dev/mem");
		free(frames);
		return 1;
	}
	map = mmap(NULL, RP1_SRAM_MAP_SIZE, PROT_READ | PROT_WRITE, MAP_SHARED,
		   mem_fd, RP1_SRAM_HOST_BASE);
	close(mem_fd);
	if (map == MAP_FAILED) {
		perror("mmap");
		free(frames);
		return 1;
	}

	sram = map;
	deadline = monotonic_seconds() + seconds;
	for (unsigned int seq = 0; monotonic_seconds() < deadline; seq++) {
		const uint8_t *frame = frames + (seq % frame_count) * RGB_FRAME_BYTES;

		pack_frame(packed, frame);
		memcpy((void *)(sram + offset), packed, RGB333_BYTES);
		__sync_synchronize();
		if (!(seq % 60U)) {
			printf("play-rgb333 seq=%u frame=%u/%u interval_ms=%u\n",
			       seq, seq % frame_count, frame_count, interval_ms);
			fflush(stdout);
		}
		sleep_ms(interval_ms);
	}

	munmap(map, RP1_SRAM_MAP_SIZE);
	free(frames);
	return 0;
}
