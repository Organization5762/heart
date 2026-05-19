#include <errno.h>
#include <fcntl.h>
#include <math.h>
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
#define RGB111_OFFSET 0xa000U
#define DEFAULT_INTERVAL_MS 30U
#define ROWPAIRS 32U
#define COLS 64U
#define ROWS 64U
#define RGB_FRAME_BYTES (ROWS * COLS * 3U)
#define RGB888_WORDS (ROWPAIRS * COLS * 2U)
#define RGB888_BYTES (RGB888_WORDS * sizeof(uint32_t))
#define RGB111_WORDS (ROWPAIRS * COLS * 3U)
#define RGB111_BYTES (RGB111_WORDS * sizeof(uint32_t))

enum color_profile {
	COLOR_PROFILE_LINEAR,
	COLOR_PROFILE_GAMMA22,
	COLOR_PROFILE_HZELLER8,
};

enum output_format {
	OUTPUT_FORMAT_RGB888,
	OUTPUT_FORMAT_RGB111,
};

static enum color_profile profile = COLOR_PROFILE_HZELLER8;
static const char *profile_name = "hzeller8";
static enum output_format output_format = OUTPUT_FORMAT_RGB888;
static const char *output_format_name = "rgb888";
static uint8_t brightness = 100;

static uint16_t hzeller_luminance_cie1931(uint8_t channel)
{
	const float out_factor = 2047.0f;
	const float value = (float)channel * (float)brightness / 255.0f;
	const float luminance = value <= 8.0f
		? value / 902.3f
		: powf((value + 16.0f) / 116.0f, 3.0f);
	long mapped = lroundf(out_factor * luminance);

	if (mapped < 0)
		return 0;
	if (mapped > 2047)
		return 2047;
	return (uint16_t)mapped;
}

static uint8_t apply_profile(uint8_t channel)
{
	unsigned int value = channel;

	switch (profile) {
	case COLOR_PROFILE_LINEAR:
		return channel;
	case COLOR_PROFILE_HZELLER8:
		return (uint8_t)(hzeller_luminance_cie1931(channel) >> 3);
	case COLOR_PROFILE_GAMMA22:
	default:
		value = (value * value * 255U + 32512U) / 65025U;
		break;
	}

	return value > 255U ? 255U : (uint8_t)value;
}

static uint16_t apply_profile_11(uint8_t channel)
{
	unsigned int value = channel;

	switch (profile) {
	case COLOR_PROFILE_LINEAR:
		return (uint16_t)value << 3;
	case COLOR_PROFILE_GAMMA22:
		value = (value * value * 255U + 32512U) / 65025U;
		return (uint16_t)value << 3;
	case COLOR_PROFILE_HZELLER8:
	default:
		return hzeller_luminance_cie1931(channel);
	}
}

static int color_profile_from_env(void)
{
	const char *name = getenv("RP1_HUB75_RGB888_COLOR_PROFILE");
	const char *brightness_env = getenv("RP1_HUB75_RGB888_BRIGHTNESS");
	const char *format_env = getenv("RP1_HUB75_RGB888_FORMAT");

	if (brightness_env && *brightness_env) {
		unsigned long parsed = strtoul(brightness_env, NULL, 0);

		if (parsed < 1 || parsed > 100) {
			fprintf(stderr,
				"invalid RP1_HUB75_RGB888_BRIGHTNESS=%s "
				"(use 1..100)\n",
				brightness_env);
			return -1;
		}
		brightness = (uint8_t)parsed;
	}
	if (format_env && *format_env) {
		if (!strcmp(format_env, "rgb111") || !strcmp(format_env, "hzeller11")) {
			output_format = OUTPUT_FORMAT_RGB111;
			output_format_name = "rgb111";
		} else if (!strcmp(format_env, "rgb888")) {
			output_format = OUTPUT_FORMAT_RGB888;
			output_format_name = "rgb888";
		} else {
			fprintf(stderr,
				"unknown RP1_HUB75_RGB888_FORMAT=%s "
				"(use rgb888 or rgb111)\n",
				format_env);
			return -1;
		}
	}

	if (!name || !*name || !strcmp(name, "gamma22") || !strcmp(name, "vivid")) {
		profile = COLOR_PROFILE_GAMMA22;
		profile_name = "gamma22";
		return 0;
	}
	if (!strcmp(name, "cie1931") || !strcmp(name, "hzeller")) {
		profile = COLOR_PROFILE_HZELLER8;
		profile_name = "hzeller8";
		return 0;
	}
	if (!strcmp(name, "hzeller8")) {
		profile = COLOR_PROFILE_HZELLER8;
		profile_name = "hzeller8";
		return 0;
	}
	if (!strcmp(name, "linear")) {
		profile = COLOR_PROFILE_LINEAR;
		profile_name = "linear";
		return 0;
	}

	fprintf(stderr,
		"unknown RP1_HUB75_RGB888_COLOR_PROFILE=%s "
		"(use hzeller8, gamma22, cie1931, or linear)\n",
		name);
	return -1;
}

static void sleep_ms(unsigned int ms)
{
	struct timespec ts = {
		.tv_sec = ms / 1000U,
		.tv_nsec = (long)(ms % 1000U) * 1000000L,
	};

	while (nanosleep(&ts, &ts) != 0 && errno == EINTR)
		;
}

static uint32_t pack_pixel(const uint8_t *pixel)
{
	return (uint32_t)apply_profile(pixel[0]) |
	       ((uint32_t)apply_profile(pixel[1]) << 8) |
	       ((uint32_t)apply_profile(pixel[2]) << 16);
}

static void pack_frame(uint32_t *dst, const uint8_t *src)
{
	unsigned int row;
	unsigned int col;

	for (row = 0; row < ROWPAIRS; row++) {
		for (col = 0; col < COLS; col++) {
			unsigned int out = row * COLS * 2U + col * 2U;
			const uint8_t *upper = src + (row * COLS + col) * 3U;
			const uint8_t *lower = src + ((row + ROWPAIRS) * COLS + col) * 3U;

			dst[out + 0] = pack_pixel(upper);
			dst[out + 1] = pack_pixel(lower);
		}
	}
}

static void pack_frame_rgb111(uint32_t *dst, const uint8_t *src)
{
	unsigned int row;
	unsigned int col;

	for (row = 0; row < ROWPAIRS; row++) {
		for (col = 0; col < COLS; col++) {
			unsigned int out = row * COLS * 3U + col * 3U;
			const uint8_t *upper = src + (row * COLS + col) * 3U;
			const uint8_t *lower = src + ((row + ROWPAIRS) * COLS + col) * 3U;
			uint32_t ur = apply_profile_11(upper[0]);
			uint32_t ug = apply_profile_11(upper[1]);
			uint32_t ub = apply_profile_11(upper[2]);
			uint32_t lr = apply_profile_11(lower[0]);
			uint32_t lg = apply_profile_11(lower[1]);
			uint32_t lb = apply_profile_11(lower[2]);

			dst[out + 0] = ur | (ug << 11) | ((ub & 0x3ffU) << 22);
			dst[out + 1] = ((ub >> 10) & 0x1U) | (lr << 1) |
				       (lg << 12) | ((lb & 0x1ffU) << 23);
			dst[out + 2] = (lb >> 9) & 0x3U;
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
	uint32_t packed[RGB111_WORDS];
	size_t packed_bytes = RGB888_BYTES;
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
	if (color_profile_from_env())
		return 2;
	if (output_format == OUTPUT_FORMAT_RGB111) {
		packed_bytes = RGB111_BYTES;
		if (argc <= 4)
			offset = RGB111_OFFSET;
	}
	if (argc > 4)
		offset = (uint32_t)strtoul(argv[4], NULL, 0);
	if (seconds <= 0.0 || !interval_ms || offset + packed_bytes > RP1_SRAM_MAP_SIZE) {
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

		if (output_format == OUTPUT_FORMAT_RGB111)
			pack_frame_rgb111(packed, frame);
		else
			pack_frame(packed, frame);
		memcpy((void *)(sram + offset), packed, packed_bytes);
		__sync_synchronize();
		if (!(seq % 60U)) {
			printf("play-rgb888 seq=%u frame=%u/%u interval_ms=%u "
			       "color_profile=%s brightness=%u format=%s bytes=%zu\n",
			       seq, seq % frame_count, frame_count, interval_ms,
			       profile_name, brightness, output_format_name,
			       packed_bytes);
			fflush(stdout);
		}
		sleep_ms(interval_ms);
	}

	munmap(map, RP1_SRAM_MAP_SIZE);
	free(frames);
	return 0;
}
