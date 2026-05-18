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
#define RP1_SRAM_MAP_SIZE 0x30000U
#define DEFAULT_OFFSET 0xc000U
#define DEFAULT_INTERVAL_MS 30U
#define ROWPAIRS 32U
#define COLS 64U
#define ROWS 64U
#define MAX_PWM_BITS 11U
#define DEFAULT_PWM_BITS 11U
#define RGB_FRAME_BYTES (ROWS * COLS * 3U)
#define STATE32_WORDS (ROWPAIRS * MAX_PWM_BITS * COLS)
#define STATE32_BYTES (STATE32_WORDS * sizeof(uint32_t))

#define GPIO_OE 18
#define GPIO_OE_LEGACY 4
#define GPIO_A 22
#define GPIO_B 26
#define GPIO_C 27
#define GPIO_D 20
#define GPIO_E 24
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

static uint8_t brightness = 100;
static uint8_t pwm_bits = DEFAULT_PWM_BITS;

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

static void sleep_ms(unsigned int ms)
{
	struct timespec ts = {
		.tv_sec = ms / 1000U,
		.tv_nsec = (long)(ms % 1000U) * 1000000L,
	};

	while (nanosleep(&ts, &ts) != 0 && errno == EINTR)
		;
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

static uint32_t rgb_mask(const uint8_t *top, const uint8_t *bottom,
			 unsigned int plane)
{
	const uint16_t bit = (uint16_t)(1U << (plane + (MAX_PWM_BITS - pwm_bits)));
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

static void pack_frame(uint32_t *dst, const uint8_t *src)
{
	unsigned int row;
	unsigned int plane;
	unsigned int col;

	for (row = 0; row < ROWPAIRS; row++) {
		for (plane = 0; plane < pwm_bits; plane++) {
			for (col = 0; col < COLS; col++) {
				const uint8_t *top = src + (row * COLS + col) * 3U;
				const uint8_t *bottom = src + ((row + ROWPAIRS) * COLS + col) * 3U;
				*dst++ = rgb_mask(top, bottom, plane);
			}
		}
	}
}

int main(int argc, char **argv)
{
	const char *frames_path;
	double seconds;
	unsigned int interval_ms = DEFAULT_INTERVAL_MS;
	uint32_t offset = DEFAULT_OFFSET;
	uint32_t packed[STATE32_WORDS];
	volatile uint8_t *sram;
	unsigned char *frames;
	long file_size;
	unsigned int frame_count;
	double deadline;
	void *map;
	FILE *file;
	int mem_fd;
	const char *brightness_env = getenv("RP1_HUB75_STATE32_BRIGHTNESS");

	if (argc < 3 || argc > 6) {
		fprintf(stderr, "usage: %s frames.rgb seconds [interval_ms] [sram_offset] [pwm_bits]\n",
			argv[0]);
		return 2;
	}
	if (brightness_env && *brightness_env) {
		unsigned long parsed = strtoul(brightness_env, NULL, 0);

		if (parsed < 1 || parsed > 100) {
			fprintf(stderr, "invalid RP1_HUB75_STATE32_BRIGHTNESS=%s\n",
				brightness_env);
			return 2;
		}
		brightness = (uint8_t)parsed;
	}

	frames_path = argv[1];
	seconds = strtod(argv[2], NULL);
	if (argc > 3)
		interval_ms = (unsigned int)strtoul(argv[3], NULL, 0);
	if (argc > 4)
		offset = (uint32_t)strtoul(argv[4], NULL, 0);
	if (argc > 5)
		pwm_bits = (uint8_t)strtoul(argv[5], NULL, 0);
	if (!pwm_bits || pwm_bits > MAX_PWM_BITS) {
		fprintf(stderr, "pwm_bits must be in 1..%u\n", MAX_PWM_BITS);
		return 2;
	}

	const size_t packed_bytes = ROWPAIRS * (size_t)pwm_bits * COLS * sizeof(uint32_t);
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

		pack_frame(packed, frame);
		memcpy((void *)(sram + offset), packed, packed_bytes);
		__sync_synchronize();
		if (!(seq % 20U)) {
			printf("play-state32 seq=%u frame=%u/%u interval_ms=%u brightness=%u pwm_bits=%u bytes=%zu\n",
			       seq, seq % frame_count, frame_count, interval_ms,
			       brightness, pwm_bits, packed_bytes);
			fflush(stdout);
		}
		sleep_ms(interval_ms);
	}

	munmap(map, RP1_SRAM_MAP_SIZE);
	free(frames);
	return 0;
}
