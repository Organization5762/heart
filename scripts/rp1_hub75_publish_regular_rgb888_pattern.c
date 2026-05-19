// SPDX-License-Identifier: GPL-2.0
#define _GNU_SOURCE

#include <errno.h>
#include <fcntl.h>
#include <stdint.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <sys/ioctl.h>
#include <sys/mman.h>
#include <time.h>
#include <unistd.h>

#include <misc/rp1_hub75_if.h>

#define DEFAULT_DEV "/dev/" RP1H_DEVICE_NAME
#define DEFAULT_CTRL_OFFSET 0xb800U
#define DEFAULT_DWELL_SHIFT_LIMIT RP1H_DEFAULT_DWELL_SHIFT_LIMIT
#define DEFAULT_PWM_BITS 8U
#define DEFAULT_SECONDS 120U
#define ROWS 64U
#define COLS 64U
#define INPUT_COLS 256U
#define PANEL_SIZE 64U
#define RP1_SRAM_HOST_BASE 0x1f00400000ULL
#define RP1_SRAM_MAP_SIZE 0x10000U
#define RP1H_EXTERNAL_SLOT_META_MAGIC 0x48500000U
#define RP1H_EXTERNAL_SLOT_META_OFFSET 16U

enum pattern {
	PATTERN_BLEED,
	PATTERN_HLINES,
	PATTERN_ROW_TAIL,
	PATTERN_PANELS,
	PATTERN_CHECKERS,
	PATTERN_RED,
	PATTERN_GREEN,
	PATTERN_BLUE,
	PATTERN_BLACK,
};

struct rgb {
	uint8_t r;
	uint8_t g;
	uint8_t b;
};

static void sleep_seconds(unsigned int seconds)
{
	struct timespec ts = {
		.tv_sec = seconds,
		.tv_nsec = 0,
	};

	while (nanosleep(&ts, &ts) != 0 && errno == EINTR)
		;
}

static void write32(volatile void *base, uint32_t off, uint32_t value)
{
	*(volatile uint32_t *)((volatile uint8_t *)base + off) = value;
}

static enum pattern parse_pattern(const char *name)
{
	if (!name || !strcmp(name, "bleed") || !strcmp(name, "channel-bleed"))
		return PATTERN_BLEED;
	if (!strcmp(name, "hlines") || !strcmp(name, "horizontal-lines"))
		return PATTERN_HLINES;
	if (!strcmp(name, "row-tail"))
		return PATTERN_ROW_TAIL;
	if (!strcmp(name, "panels") || !strcmp(name, "rgb-black"))
		return PATTERN_PANELS;
	if (!strcmp(name, "checkers") || !strcmp(name, "checker"))
		return PATTERN_CHECKERS;
	if (!strcmp(name, "red") || !strcmp(name, "solid-red"))
		return PATTERN_RED;
	if (!strcmp(name, "green") || !strcmp(name, "solid-green"))
		return PATTERN_GREEN;
	if (!strcmp(name, "blue") || !strcmp(name, "solid-blue"))
		return PATTERN_BLUE;
	if (!strcmp(name, "black") || !strcmp(name, "rgb-black"))
		return PATTERN_BLACK;
	fprintf(stderr, "unknown pattern '%s'; using bleed\n", name);
	return PATTERN_BLEED;
}

static struct rgb source_pixel(unsigned int x, unsigned int y, enum pattern pattern)
{
	static const struct rgb panel_colors[4] = {
		{ 220, 0, 0 },
		{ 0, 210, 0 },
		{ 0, 70, 255 },
		{ 0, 0, 0 },
	};
	static const struct rgb tail_colors[4] = {
		{ 255, 190, 0 },
		{ 0, 255, 190 },
		{ 255, 0, 255 },
		{ 255, 255, 255 },
	};
	unsigned int panel = x / PANEL_SIZE;
	unsigned int local_x = x % PANEL_SIZE;
	struct rgb color;

	if (panel >= 4U)
		return (struct rgb){ 0, 0, 0 };
	if (pattern == PATTERN_RED)
		return (struct rgb){ 255, 0, 0 };
	if (pattern == PATTERN_GREEN)
		return (struct rgb){ 0, 255, 0 };
	if (pattern == PATTERN_BLUE)
		return (struct rgb){ 0, 0, 255 };
	if (pattern == PATTERN_BLACK)
		return (struct rgb){ 0, 0, 0 };
	if (pattern == PATTERN_PANELS)
		return panel_colors[panel];
	if (pattern == PATTERN_CHECKERS) {
		static const struct rgb checker_colors[4][2] = {
			{ { 255, 0, 0 }, { 0, 0, 0 } },
			{ { 0, 255, 0 }, { 0, 0, 0 } },
			{ { 0, 0, 255 }, { 0, 0, 0 } },
			{ { 255, 255, 255 }, { 0, 0, 0 } },
		};
		unsigned int cell = ((local_x / 8U) + (y / 8U)) & 1U;

		return checker_colors[panel][cell];
	}
	if (pattern == PATTERN_BLEED) {
		unsigned int band = (x / 8U) % 4U;

		if (y >= 48U && y < 56U)
			band = x % 4U;
		if (y >= 56U)
			band = (x + y) % 4U;
		if (band == 0U)
			return (struct rgb){ 255, 0, 0 };
		if (band == 1U)
			return (struct rgb){ 0, 255, 0 };
		if (band == 2U)
			return (struct rgb){ 0, 0, 255 };
		return (struct rgb){ 0, 0, 0 };
	}
	if (pattern == PATTERN_HLINES) {
		unsigned int phase = (y + panel) % 8U;

		if (local_x < 4U || local_x >= 60U)
			return panel_colors[panel];
		if (phase == 0U)
			return (struct rgb){ 255, 0, 0 };
		if (phase == 1U)
			return (struct rgb){ 0, 255, 0 };
		if (phase == 2U)
			return (struct rgb){ 0, 0, 255 };
		if (phase == 4U)
			return (struct rgb){ 255, 255, 255 };
		return (struct rgb){ 0, 0, 0 };
	}

	color = panel_colors[panel];
	if ((y >= 24U && y <= 31U) || (y >= 56U && y <= 63U))
		color = tail_colors[panel];
	if (local_x == 0U || local_x == 63U || y == 31U || y == 32U)
		return (struct rgb){ 0, 0, 0 };
	if (((y >= 24U && y <= 31U) || (y >= 56U && y <= 63U)) &&
	    local_x >= 8U && (local_x - 8U) % 16U == 0U)
		return (struct rgb){ 0, 0, 0 };
	return color;
}

static void fill_rgb888(uint8_t *frame, enum pattern pattern)
{
	for (unsigned int y = 0; y < ROWS; y++) {
		for (unsigned int x = 0; x < INPUT_COLS; x++) {
			struct rgb pixel = source_pixel(x, y, pattern);
			uint8_t *dst = frame + ((y * INPUT_COLS + x) * 3U);

			dst[0] = pixel.r;
			dst[1] = pixel.g;
			dst[2] = pixel.b;
		}
	}
}

int main(int argc, char **argv)
{
	const char *pattern_name = argc > 1 ? argv[1] : "bleed";
	unsigned int seconds = argc > 2 ? (unsigned int)strtoul(argv[2], NULL, 0) :
					 DEFAULT_SECONDS;
	uint32_t ctrl_offset = argc > 3 ? (uint32_t)strtoul(argv[3], NULL, 0) :
					 DEFAULT_CTRL_OFFSET;
	uint32_t pwm_bits = argc > 4 ? (uint32_t)strtoul(argv[4], NULL, 0) :
				       DEFAULT_PWM_BITS;
	uint32_t dwell_shift_limit = argc > 5 ? (uint32_t)strtoul(argv[5], NULL, 0) :
						DEFAULT_DWELL_SHIFT_LIMIT;
	enum pattern pattern = parse_pattern(pattern_name);
	struct rp1h_config cfg = {
		.size = sizeof(cfg),
		.cols = COLS,
		.rows = ROWS,
		.pwm_bits = pwm_bits,
		.mapping = RP1H_MAPPING_REGULAR,
		.format = RP1H_FORMAT_RGB888,
		.flags = RP1H_F_E_LINE_PRESENT,
		.stream_format = RP1H_STREAM_STATE32,
		.panel_count = 4,
		.lane_count = 2,
		.chain_length = 2,
		.slot_count = RP1H_MAX_SLOTS,
		.dwell_shift_limit = dwell_shift_limit,
	};
	struct rp1h_queue_frame queue = {
		.size = sizeof(queue),
		.flags = RP1H_QUEUE_F_REPLACE_PENDING,
	};
	struct rp1h_mmap_header *hdr;
	uint64_t slot_dma;
	uint8_t *frame;
	void *hub_map;
	void *sram_map;
	int dev_fd;
	int mem_fd;

	if (pwm_bits < 1 || pwm_bits > RP1H_MAX_PWM_BITS) {
		fprintf(stderr, "usage: %s [pattern] [seconds] [ctrl_offset] [pwm_bits] [dwell_shift_limit]\n",
			argv[0]);
		return 2;
	}

	dev_fd = open(DEFAULT_DEV, O_RDWR | O_CLOEXEC);
	if (dev_fd < 0) {
		perror(DEFAULT_DEV);
		return 1;
	}
	if (ioctl(dev_fd, RP1H_CONFIG, &cfg)) {
		perror("RP1H_CONFIG");
		close(dev_fd);
		return 1;
	}
	if (cfg.frame_bytes != INPUT_COLS * ROWS * 3U) {
		fprintf(stderr, "unexpected frame_bytes=%u expected=%u\n",
			cfg.frame_bytes, INPUT_COLS * ROWS * 3U);
		close(dev_fd);
		return 1;
	}
	frame = calloc(1, cfg.frame_bytes);
	if (!frame) {
		perror("calloc frame");
		close(dev_fd);
		return 1;
	}
	fill_rgb888(frame, pattern);
	queue.length = cfg.frame_bytes;
	queue.data = (uint64_t)(uintptr_t)frame;
	if (ioctl(dev_fd, RP1H_QUEUE_FRAME, &queue)) {
		perror("RP1H_QUEUE_FRAME");
		free(frame);
		close(dev_fd);
		return 1;
	}
	hub_map = mmap(NULL, cfg.mmap_size, PROT_READ, MAP_SHARED, dev_fd, 0);
	if (hub_map == MAP_FAILED) {
		perror("mmap hub75");
		free(frame);
		close(dev_fd);
		return 1;
	}
	hdr = hub_map;
	if (hdr->magic != RP1H_MAGIC || queue.slot_index >= hdr->slot_count ||
	    queue.slot_index >= RP1H_MAX_SLOTS) {
		fprintf(stderr, "bad header magic=0x%08x slot=%u slot_count=%u\n",
			hdr->magic, queue.slot_index, hdr->slot_count);
		munmap(hub_map, cfg.mmap_size);
		free(frame);
		close(dev_fd);
		return 1;
	}
	slot_dma = ((uint64_t)hdr->slot_dma_addr_hi[queue.slot_index] << 32) |
		   hdr->slot_dma_addr_lo[queue.slot_index];
	if (!slot_dma) {
		fprintf(stderr, "queued slot has no DMA address\n");
		munmap(hub_map, cfg.mmap_size);
		free(frame);
		close(dev_fd);
		return 1;
	}

	mem_fd = open("/dev/mem", O_RDWR | O_SYNC | O_CLOEXEC);
	if (mem_fd < 0) {
		perror("/dev/mem");
		munmap(hub_map, cfg.mmap_size);
		free(frame);
		close(dev_fd);
		return 1;
	}
	sram_map = mmap(NULL, RP1_SRAM_MAP_SIZE, PROT_READ | PROT_WRITE,
			MAP_SHARED, mem_fd, RP1_SRAM_HOST_BASE);
	close(mem_fd);
	if (sram_map == MAP_FAILED) {
		perror("mmap rp1 sram");
		munmap(hub_map, cfg.mmap_size);
		free(frame);
		close(dev_fd);
		return 1;
	}

	write32(sram_map, ctrl_offset + 0, (uint32_t)slot_dma);
	write32(sram_map, ctrl_offset + 4, (uint32_t)(slot_dma >> 32));
	write32(sram_map, ctrl_offset + 8, 0);
	write32(sram_map, ctrl_offset + 12, dwell_shift_limit);
	write32(sram_map, ctrl_offset + RP1H_EXTERNAL_SLOT_META_OFFSET,
		RP1H_EXTERNAL_SLOT_META_MAGIC | pwm_bits);
	__sync_synchronize();

	printf("published_regular_rgb888_pattern pattern=%s seq=%u slot=%u slot_dma=0x%016llx"
	       " cfg_pwm=%u hdr_pwm=%u stream=%u panel_count=%u lanes=%u chain=%u"
	       " frame_bytes=%u words=%u words_per_row_plane=%u dwell_shift_limit=%u seconds=%u\n",
	       pattern_name, queue.seq, queue.slot_index, (unsigned long long)slot_dma,
	       cfg.pwm_bits, hdr->pwm_bits, hdr->stream_format, hdr->panel_count,
	       hdr->lane_count, hdr->chain_length, cfg.frame_bytes,
	       hdr->words_per_frame, hdr->words_per_row_plane, dwell_shift_limit,
	       seconds);
	fflush(stdout);
	if (seconds)
		sleep_seconds(seconds);

	munmap(sram_map, RP1_SRAM_MAP_SIZE);
	munmap(hub_map, cfg.mmap_size);
	free(frame);
	close(dev_fd);
	return 0;
}
