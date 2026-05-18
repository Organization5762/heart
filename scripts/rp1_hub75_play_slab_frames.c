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
#define DEFAULT_OFFSET 0xa000U
#define CONFIG_OFFSET 0xff00U
#define CONFIG_MAGIC 0x48373543U
#define DEFAULT_FRAME_INTERVAL_MS 30U
#define ROWPAIRS 32U
#define COLS 64U
#define ROWS 64U
#define MAX_PWM_BITS 11U
#ifndef PWM_BITS
#define PWM_BITS 11U
#endif
#define RGB_FRAME_BYTES (ROWS * COLS * 3U)
#define SLAB_WORDS (PWM_BITS * COLS)
#define SLAB_BYTES (SLAB_WORDS * sizeof(uint32_t))
#define SLAB_RING_COUNT 8U
#define SLAB_SLOT_WORDS (4U + SLAB_WORDS)
#define SLAB_TOTAL_BYTES (16U + SLAB_RING_COUNT * SLAB_SLOT_WORDS * sizeof(uint32_t))

#define GPIO_R1 5
#define GPIO_G1 13
#define GPIO_B1 6
#define GPIO_R2 12
#define GPIO_G2 16
#define GPIO_B2 23

#define PIN(_gpio) (1U << (_gpio))
#define PIN_R1 PIN(GPIO_R1)
#define PIN_G1 PIN(GPIO_G1)
#define PIN_B1 PIN(GPIO_B1)
#define PIN_R2 PIN(GPIO_R2)
#define PIN_G2 PIN(GPIO_G2)
#define PIN_B2 PIN(GPIO_B2)

struct slab_slot {
	volatile uint32_t row_pair;
	volatile uint32_t frame_id;
	volatile uint32_t flags;
	volatile uint32_t reserved;
	volatile uint32_t data[SLAB_WORDS];
};

struct slab_control {
	volatile uint32_t host_seq;
	volatile uint32_t core_seq;
	volatile uint32_t ring_count;
	volatile uint32_t slab_bytes;
	struct slab_slot slots[SLAB_RING_COUNT];
};

struct hub75_config {
	volatile uint32_t magic;
	volatile uint32_t rows;
	volatile uint32_t cols;
	volatile uint32_t row_pairs;
	volatile uint32_t pwm_bits;
	volatile uint32_t ring_mask;
	volatile uint32_t slab_words;
	volatile uint32_t flags;
};

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

static uint32_t rgb_mask(const uint8_t *top, const uint8_t *bottom,
			 unsigned int plane)
{
	const uint16_t bit = (uint16_t)(1U << (plane + (MAX_PWM_BITS - PWM_BITS)));
	uint32_t mask = 0;

	if (hzeller_luminance_cie1931(top[0]) & bit)
		mask |= PIN_R1;
	if (hzeller_luminance_cie1931(top[1]) & bit)
		mask |= PIN_G1;
	if (hzeller_luminance_cie1931(top[2]) & bit)
		mask |= PIN_B1;
	if (hzeller_luminance_cie1931(bottom[0]) & bit)
		mask |= PIN_R2;
	if (hzeller_luminance_cie1931(bottom[1]) & bit)
		mask |= PIN_G2;
	if (hzeller_luminance_cie1931(bottom[2]) & bit)
		mask |= PIN_B2;
	return mask;
}

static void pack_slab(uint32_t *dst, const uint8_t *frame, unsigned int row)
{
	for (unsigned int plane = 0; plane < PWM_BITS; plane++) {
		for (unsigned int col = 0; col < COLS; col++) {
			const uint8_t *top = use_solid_rgb
				? solid_rgb
				: frame + (row * COLS + col) * 3U;
			const uint8_t *bottom = use_solid_rgb
				? solid_rgb
				: frame + ((row + ROWPAIRS) * COLS + col) * 3U;

			*dst++ = rgb_mask(top, bottom, plane);
		}
	}
}

static void wait_slot_available(const struct slab_control *control, uint32_t seq)
{
	while (seq - control->core_seq >= SLAB_RING_COUNT)
		;
}

static void write_config(void *map)
{
	struct hub75_config *config =
		(struct hub75_config *)((uint8_t *)map + CONFIG_OFFSET);

	config->magic = CONFIG_MAGIC;
	config->rows = ROWS;
	config->cols = COLS;
	config->row_pairs = ROWPAIRS;
	config->pwm_bits = PWM_BITS;
	config->ring_mask = SLAB_RING_COUNT - 1U;
	config->slab_words = SLAB_WORDS;
	config->flags = 0;
	__sync_synchronize();
}

int main(int argc, char **argv)
{
	const char *frames_path;
	double seconds;
	unsigned int frame_interval_ms = DEFAULT_FRAME_INTERVAL_MS;
	uint32_t offset = DEFAULT_OFFSET;
	struct slab_control *control;
	unsigned char *frames;
	long file_size;
	unsigned int frame_count;
	double start;
	double deadline;
	void *map;
	FILE *file;
	int mem_fd;
	const char *brightness_env = getenv("RP1_HUB75_SLAB_BRIGHTNESS");
	const char *fixed_row_env = getenv("RP1_HUB75_SLAB_FIXED_ROW");
	const char *solid_rgb_env = getenv("RP1_HUB75_SLAB_SOLID_RGB");

	if (argc < 3 || argc > 5) {
		fprintf(stderr, "usage: %s frames.rgb seconds [frame_interval_ms] [sram_offset]\n",
			argv[0]);
		return 2;
	}
	if (brightness_env && *brightness_env) {
		unsigned long parsed = strtoul(brightness_env, NULL, 0);

		if (parsed < 1 || parsed > 100) {
			fprintf(stderr, "invalid RP1_HUB75_SLAB_BRIGHTNESS=%s\n",
				brightness_env);
			return 2;
		}
		brightness = (uint8_t)parsed;
	}
	if (fixed_row_env && *fixed_row_env) {
		long parsed = strtol(fixed_row_env, NULL, 0);

		if (parsed < 0 || parsed >= (long)ROWPAIRS) {
			fprintf(stderr, "invalid RP1_HUB75_SLAB_FIXED_ROW=%s\n",
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
			fprintf(stderr, "invalid RP1_HUB75_SLAB_SOLID_RGB=%s\n",
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
	    offset + SLAB_TOTAL_BYTES > RP1_SRAM_MAP_SIZE) {
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

	write_config(map);
	control = (struct slab_control *)((uint8_t *)map + offset);
	control->host_seq = control->core_seq;
	__sync_synchronize();
	control->ring_count = SLAB_RING_COUNT;
	control->slab_bytes = SLAB_BYTES;
	for (unsigned int slot = 0; slot < SLAB_RING_COUNT; slot++) {
		control->slots[slot].row_pair = 0;
		control->slots[slot].frame_id = 0;
		control->slots[slot].flags = 0;
		control->slots[slot].reserved = 0;
		for (unsigned int i = 0; i < SLAB_WORDS; i++)
			control->slots[slot].data[i] = 0;
	}
	__sync_synchronize();

	start = monotonic_seconds();
	deadline = start + seconds;
	for (unsigned int frame_seq = 0; monotonic_seconds() < deadline; frame_seq++) {
		const uint8_t *frame = frames + (frame_seq % frame_count) * RGB_FRAME_BYTES;
		const double next_frame_time = start +
			(double)(frame_seq + 1U) * (double)frame_interval_ms / 1000.0;

		for (unsigned int row = 0; row < ROWPAIRS; row++) {
			const uint32_t seq = control->host_seq;
			const unsigned int slot = seq & (SLAB_RING_COUNT - 1U);
			const unsigned int slab_row = fixed_row >= 0 ? (unsigned int)fixed_row : row;

			wait_slot_available(control, seq);
			pack_slab((uint32_t *)control->slots[slot].data, frame, slab_row);
			control->slots[slot].row_pair = slab_row;
			control->slots[slot].frame_id = frame_seq;
			control->slots[slot].flags = 0;
			__sync_synchronize();
			control->host_seq = seq + 1U;
			__sync_synchronize();
		}
		if (!(frame_seq % 20U)) {
			printf("play-slab frame_seq=%u frame=%u/%u interval_ms=%u brightness=%u pwm_bits=%u ring=%u slab_bytes=%zu total_bytes=%zu offset=0x%x config=0x%x\n",
			       frame_seq, frame_seq % frame_count, frame_count,
			       frame_interval_ms, brightness, PWM_BITS, SLAB_RING_COUNT,
			       (size_t)SLAB_BYTES, (size_t)SLAB_TOTAL_BYTES,
			       offset, CONFIG_OFFSET);
			fflush(stdout);
		}
		sleep_until(next_frame_time);
	}

	munmap(map, RP1_SRAM_MAP_SIZE);
	free(frames);
	return 0;
}
