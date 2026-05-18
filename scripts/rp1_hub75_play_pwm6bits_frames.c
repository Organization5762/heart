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
#define DEFAULT_OFFSET 0xd000U
#define DEFAULT_FRAME_INTERVAL_MS 30U
#define ROWPAIRS 32U
#define COLS 64U
#define ROWS 64U
#define GROUPS (COLS / 8U)
#define CHANNELS 6U
#define MAX_PWM_BITS 11U
#define PWM_BITS 6U
#define RGB_FRAME_BYTES (ROWS * COLS * 3U)
#define PWM6_BITS_BYTES (ROWPAIRS * PWM_BITS * GROUPS * CHANNELS)
#define PWM6_BITS_WORDS (PWM6_BITS_BYTES / sizeof(uint32_t))

static uint8_t brightness = 100;
static int fixed_row = -1;
static int use_solid_rgb;
static uint8_t solid_rgb[3];

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

static double monotonic_seconds(void)
{
	struct timespec ts;

	if (clock_gettime(CLOCK_MONOTONIC, &ts) != 0) {
		perror("clock_gettime");
		exit(1);
	}
	return (double)ts.tv_sec + (double)ts.tv_nsec / 1000000000.0;
}

static void sleep_until(double deadline)
{
	for (;;) {
		const double now = monotonic_seconds();
		struct timespec ts;

		if (now >= deadline)
			return;
		ts.tv_sec = (time_t)(deadline - now);
		ts.tv_nsec = (long)((deadline - now - (double)ts.tv_sec) * 1000000000.0);
		while (nanosleep(&ts, &ts) != 0 && errno == EINTR)
			;
	}
}

static int component_on(const uint8_t *pixel, unsigned int channel,
			unsigned int plane)
{
	const uint16_t bit = (uint16_t)(1U << (plane + (MAX_PWM_BITS - PWM_BITS)));

	return (hzeller_luminance_cie1931(pixel[channel]) & bit) != 0;
}

static void pack_pwm6_bits(uint32_t *dst_words, const uint8_t *frame)
{
	uint8_t *dst = (uint8_t *)dst_words;

	memset(dst, 0, PWM6_BITS_BYTES);
	for (unsigned int row = 0; row < ROWPAIRS; row++) {
		const unsigned int src_row = fixed_row >= 0 ? (unsigned int)fixed_row : row;

		for (unsigned int plane = 0; plane < PWM_BITS; plane++) {
			for (unsigned int group = 0; group < GROUPS; group++) {
				uint8_t channel_bytes[CHANNELS] = {0};

				for (unsigned int bit = 0; bit < 8; bit++) {
					const unsigned int col = group * 8U + bit;
					const uint8_t *top = use_solid_rgb
						? solid_rgb
						: frame + (src_row * COLS + col) * 3U;
					const uint8_t *bottom = use_solid_rgb
						? solid_rgb
						: frame + ((src_row + ROWPAIRS) * COLS + col) * 3U;
					const uint8_t mask = (uint8_t)(1U << bit);

					if (component_on(top, 0, plane))
						channel_bytes[0] |= mask;
					if (component_on(top, 1, plane))
						channel_bytes[1] |= mask;
					if (component_on(top, 2, plane))
						channel_bytes[2] |= mask;
					if (component_on(bottom, 0, plane))
						channel_bytes[3] |= mask;
					if (component_on(bottom, 1, plane))
						channel_bytes[4] |= mask;
					if (component_on(bottom, 2, plane))
						channel_bytes[5] |= mask;
				}
				memcpy(dst, channel_bytes, sizeof(channel_bytes));
				dst += sizeof(channel_bytes);
			}
		}
	}
}

static void write_pwm6_bits(volatile uint32_t *dst, const uint32_t *src)
{
	for (unsigned int i = 0; i < PWM6_BITS_WORDS; i++)
		dst[i] = src[i];
}

int main(int argc, char **argv)
{
	const char *frames_path;
	double seconds;
	unsigned int frame_interval_ms = DEFAULT_FRAME_INTERVAL_MS;
	uint32_t offset = DEFAULT_OFFSET;
	uint32_t *packed_words;
	unsigned char *frames;
	long file_size;
	unsigned int frame_count;
	double start;
	double deadline;
	void *map;
	FILE *file;
	int mem_fd;
	const char *brightness_env = getenv("RP1_HUB75_PWM6BITS_BRIGHTNESS");
	const char *fixed_row_env = getenv("RP1_HUB75_PWM6BITS_FIXED_ROW");
	const char *solid_rgb_env = getenv("RP1_HUB75_PWM6BITS_SOLID_RGB");

	if (argc < 3 || argc > 5) {
		fprintf(stderr, "usage: %s frames.rgb seconds [frame_interval_ms] [sram_offset]\n",
			argv[0]);
		return 2;
	}
	if (brightness_env && *brightness_env) {
		unsigned long parsed = strtoul(brightness_env, NULL, 0);

		if (parsed < 1 || parsed > 100) {
			fprintf(stderr, "invalid RP1_HUB75_PWM6BITS_BRIGHTNESS=%s\n",
				brightness_env);
			return 2;
		}
		brightness = (uint8_t)parsed;
	}
	if (fixed_row_env && *fixed_row_env) {
		long parsed = strtol(fixed_row_env, NULL, 0);

		if (parsed < 0 || parsed >= (long)ROWPAIRS) {
			fprintf(stderr, "invalid RP1_HUB75_PWM6BITS_FIXED_ROW=%s\n",
				fixed_row_env);
			return 2;
		}
		fixed_row = (int)parsed;
	}
	if (solid_rgb_env && *solid_rgb_env) {
		unsigned int r;
		unsigned int g;
		unsigned int b;

		if (sscanf(solid_rgb_env, "%u,%u,%u", &r, &g, &b) != 3 ||
		    r > 255 || g > 255 || b > 255) {
			fprintf(stderr, "invalid RP1_HUB75_PWM6BITS_SOLID_RGB=%s\n",
				solid_rgb_env);
			return 2;
		}
		use_solid_rgb = 1;
		solid_rgb[0] = (uint8_t)r;
		solid_rgb[1] = (uint8_t)g;
		solid_rgb[2] = (uint8_t)b;
	}

	frames_path = argv[1];
	seconds = strtod(argv[2], NULL);
	if (argc > 3)
		frame_interval_ms = (unsigned int)strtoul(argv[3], NULL, 0);
	if (argc > 4)
		offset = (uint32_t)strtoul(argv[4], NULL, 0);
	if (seconds <= 0.0 || !frame_interval_ms ||
	    offset + PWM6_BITS_BYTES > RP1_SRAM_MAP_SIZE) {
		fprintf(stderr, "invalid seconds, frame interval, or offset\n");
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
	packed_words = calloc(PWM6_BITS_WORDS, sizeof(*packed_words));
	if (!frames || !packed_words) {
		perror("malloc");
		free(frames);
		free(packed_words);
		fclose(file);
		return 1;
	}
	if (fread(frames, 1, (size_t)file_size, file) != (size_t)file_size) {
		perror("fread");
		free(frames);
		free(packed_words);
		fclose(file);
		return 1;
	}
	fclose(file);
	frame_count = (unsigned int)((size_t)file_size / RGB_FRAME_BYTES);

	mem_fd = open("/dev/mem", O_RDWR | O_SYNC);
	if (mem_fd < 0) {
		perror("/dev/mem");
		free(frames);
		free(packed_words);
		return 1;
	}
	map = mmap(NULL, RP1_SRAM_MAP_SIZE, PROT_READ | PROT_WRITE, MAP_SHARED,
		   mem_fd, RP1_SRAM_HOST_BASE);
	close(mem_fd);
	if (map == MAP_FAILED) {
		perror("mmap");
		free(frames);
		free(packed_words);
		return 1;
	}

	start = monotonic_seconds();
	deadline = start + seconds;
	for (unsigned int frame_seq = 0; monotonic_seconds() < deadline; frame_seq++) {
		const uint8_t *frame = frames + (frame_seq % frame_count) * RGB_FRAME_BYTES;
		const double next_frame_time = start +
			(double)(frame_seq + 1U) * (double)frame_interval_ms / 1000.0;

		pack_pwm6_bits(packed_words, frame);
		write_pwm6_bits((volatile uint32_t *)((uint8_t *)map + offset),
				packed_words);
		if (!(frame_seq % 20U)) {
			printf("play-pwm6bits frame_seq=%u frame=%u/%u interval_ms=%u brightness=%u pwm_bits=%u bytes=%u offset=0x%x\n",
			       frame_seq, frame_seq % frame_count, frame_count,
			       frame_interval_ms, brightness, PWM_BITS,
			       PWM6_BITS_BYTES, offset);
			fflush(stdout);
		}
		sleep_until(next_frame_time);
	}

	munmap(map, RP1_SRAM_MAP_SIZE);
	free(frames);
	free(packed_words);
	return 0;
}
