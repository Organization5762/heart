// SPDX-License-Identifier: GPL-2.0
#define _GNU_SOURCE

#include <errno.h>
#include <fcntl.h>
#include <stdint.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <asm-generic/ioctl.h>
#include <sys/ioctl.h>
#include <sys/mman.h>
#include <unistd.h>

#include <misc/rp1_hub75_if.h>

#define DEFAULT_DEV "/dev/" RP1H_DEVICE_NAME
#define DEFAULT_CTRL_OFFSET 0xb800U
#define DEFAULT_PWM_BITS 6U
#define DEFAULT_SOLID_COLOR "blue"
#define DEFAULT_ACTIVE_LANES "all"
#define DEFAULT_STREAM_FORMAT "state32"
#define RP1_SRAM_HOST_BASE 0x1f00400000ULL
#define RP1_SRAM_MAP_SIZE 0x10000U

#define REGULAR_PIN_R1 (1U << 11)
#define REGULAR_PIN_G1 (1U << 27)
#define REGULAR_PIN_B1 (1U << 7)
#define REGULAR_PIN_R2 (1U << 8)
#define REGULAR_PIN_G2 (1U << 9)
#define REGULAR_PIN_B2 (1U << 10)
#define REGULAR_PIN_P1_R1 (1U << 12)
#define REGULAR_PIN_P1_G1 (1U << 5)
#define REGULAR_PIN_P1_B1 (1U << 6)
#define REGULAR_PIN_P1_R2 (1U << 19)
#define REGULAR_PIN_P1_G2 (1U << 13)
#define REGULAR_PIN_P1_B2 (1U << 20)

static uint32_t getenv_u32(const char *name, uint32_t fallback)
{
	const char *value = getenv(name);

	if (!value || !*value)
		return fallback;

	return strtoul(value, NULL, 0);
}

enum active_lanes {
	ACTIVE_LANES_ALL,
	ACTIVE_LANES_P0,
	ACTIVE_LANES_P1,
};

struct solid_color {
	const char *name;
	uint8_t red;
	uint8_t green;
	uint8_t blue;
};

static int parse_solid_color(const char *name, struct solid_color *color)
{
	if (!name || !strcmp(name, "blue")) {
		*color = (struct solid_color) {
			.name = "blue",
			.blue = 0xff,
		};
		return 0;
	}
	if (!strcmp(name, "green")) {
		*color = (struct solid_color) {
			.name = "green",
			.green = 0xff,
		};
		return 0;
	}
	if (!strcmp(name, "red")) {
		*color = (struct solid_color) {
			.name = "red",
			.red = 0xff,
		};
		return 0;
	}
	if (!strcmp(name, "white")) {
		*color = (struct solid_color) {
			.name = "white",
			.red = 0xff,
			.green = 0xff,
			.blue = 0xff,
		};
		return 0;
	}

	fprintf(stderr, "solid color must be blue, green, red, or white\n");
	return 2;
}

static int parse_active_lanes(const char *name, enum active_lanes *lanes)
{
	if (!name || !strcmp(name, "all")) {
		*lanes = ACTIVE_LANES_ALL;
		return 0;
	}
	if (!strcmp(name, "p0")) {
		*lanes = ACTIVE_LANES_P0;
		return 0;
	}
	if (!strcmp(name, "p1")) {
		*lanes = ACTIVE_LANES_P1;
		return 0;
	}

	fprintf(stderr, "active lanes must be all, p0, or p1\n");
	return 2;
}

static int parse_stream_format(const char *name, uint32_t *stream_format)
{
	if (!name || !strcmp(name, "state32")) {
		*stream_format = RP1H_STREAM_STATE32;
		return 0;
	}
	if (!strcmp(name, "u8") || !strcmp(name, "rgb6-byte")) {
		*stream_format = RP1H_STREAM_RGB6_BYTE;
		return 0;
	}

	fprintf(stderr, "stream format must be state32, u8, or rgb6-byte\n");
	return 2;
}

static int publish_slot(uint32_t ctrl_offset, uint32_t slot_dma_lo,
			uint32_t slot_dma_hi, uint32_t dwell_shift_limit)
{
	volatile uint32_t *ctrl;
	void *map;
	int fd;

	if (ctrl_offset > RP1_SRAM_MAP_SIZE - 16 || ctrl_offset & 3) {
		fprintf(stderr, "control offset must be 32-bit aligned inside SRAM BAR\n");
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
		perror("mmap /dev/mem");
		return 1;
	}

	ctrl = (volatile uint32_t *)((uint8_t *)map + ctrl_offset);
	ctrl[0] = slot_dma_lo;
	ctrl[1] = slot_dma_hi;
	ctrl[2] = 0;
	ctrl[3] = dwell_shift_limit;
	__sync_synchronize();

	printf("published ctrl=0x%x slot_dma=0x%08x%08x dwell_shift_limit=%u\n",
	       ctrl_offset, slot_dma_hi, slot_dma_lo, dwell_shift_limit);

	munmap(map, RP1_SRAM_MAP_SIZE);
	return 0;
}

static void print_pin_if_set(uint32_t word, const char *name, uint32_t pin)
{
	if (word & pin)
		printf(" %s", name);
}

static void dump_regular_state32_words(const struct rp1h_mmap_header *hdr,
				       uint32_t slot_index, uint32_t word_count)
{
	const uint8_t *base = (const uint8_t *)hdr;
	const uint32_t *words;
	uint32_t row_words;
	uint32_t slot_offset;
	uint32_t available;
	uint32_t i;

	if (!word_count)
		return;
	if (!hdr->slot_count || slot_index >= hdr->slot_count ||
	    !hdr->slot_stride_bytes) {
		words = (const uint32_t *)(base + hdr->words_offset);
		available = hdr->words_per_frame;
	} else {
		slot_offset = hdr->words_offset + slot_index * hdr->slot_stride_bytes;
		words = (const uint32_t *)(base + slot_offset);
		available = hdr->slot_stride_bytes / sizeof(uint32_t);
		if (available > hdr->words_per_frame)
			available = hdr->words_per_frame;
	}
	if (word_count > available)
		word_count = available;
	row_words = hdr->words_per_row_plane ? hdr->words_per_row_plane : 1;

	printf("dump slot=%u words=%u row_words=%u pwm=%u stream=%u pins:",
	       slot_index, word_count, row_words, hdr->pwm_bits,
	       hdr->stream_format);
	printf(" r1=0x%08x g1=0x%08x b1=0x%08x r2=0x%08x g2=0x%08x b2=0x%08x\n",
	       hdr->pin_r1, hdr->pin_g1, hdr->pin_b1,
	       hdr->pin_r2, hdr->pin_g2, hdr->pin_b2);

	for (i = 0; i < word_count; i++) {
		uint32_t word = words[i];

		printf("word[%04u] row_word=%03u 0x%08x :", i, i % row_words, word);
		print_pin_if_set(word, "P0_R1", REGULAR_PIN_R1);
		print_pin_if_set(word, "P0_G1", REGULAR_PIN_G1);
		print_pin_if_set(word, "P0_B1", REGULAR_PIN_B1);
		print_pin_if_set(word, "P0_R2", REGULAR_PIN_R2);
		print_pin_if_set(word, "P0_G2", REGULAR_PIN_G2);
		print_pin_if_set(word, "P0_B2", REGULAR_PIN_B2);
		print_pin_if_set(word, "P1_R1", REGULAR_PIN_P1_R1);
		print_pin_if_set(word, "P1_G1", REGULAR_PIN_P1_G1);
		print_pin_if_set(word, "P1_B1", REGULAR_PIN_P1_B1);
		print_pin_if_set(word, "P1_R2", REGULAR_PIN_P1_R2);
		print_pin_if_set(word, "P1_G2", REGULAR_PIN_P1_G2);
		print_pin_if_set(word, "P1_B2", REGULAR_PIN_P1_B2);
		printf("\n");
	}
}

static int load_rgb_frame(const char *path, uint8_t *frame, uint32_t frame_bytes)
{
	FILE *fp;
	size_t got;
	int extra;

	fp = fopen(path, "rb");
	if (!fp) {
		perror(path);
		return 1;
	}

	got = fread(frame, 1, frame_bytes, fp);
	if (got != frame_bytes) {
		fprintf(stderr, "%s: expected %u bytes, got %zu\n",
			path, frame_bytes, got);
		fclose(fp);
		return 2;
	}

	extra = fgetc(fp);
	fclose(fp);
	if (extra != EOF) {
		fprintf(stderr, "%s: expected exactly %u bytes\n",
			path, frame_bytes);
		return 2;
	}

	return 0;
}

static void apply_active_lanes(uint8_t *frame, uint32_t frame_bytes,
			       enum active_lanes active_lanes)
{
	uint32_t lane_span = frame_bytes / 2;

	if (active_lanes == ACTIVE_LANES_ALL)
		return;

	if (active_lanes == ACTIVE_LANES_P0)
		memset(frame + lane_span, 0, frame_bytes - lane_span);
	else
		memset(frame, 0, lane_span);
}

static int queue_frame(const char *dev, uint32_t ctrl_offset,
		       uint32_t dwell_shift_limit, uint32_t pwm_bits,
		       uint32_t stream_format,
		       const struct solid_color *color,
		       enum active_lanes active_lanes, const char *frame_path)
{
	struct rp1h_config cfg = {
		.size = sizeof(cfg),
		.cols = 64,
		.rows = 64,
		.pwm_bits = pwm_bits,
		.mapping = RP1H_MAPPING_REGULAR,
		.format = RP1H_FORMAT_RGB888,
		.flags = RP1H_F_E_LINE_PRESENT,
		.stream_format = stream_format,
		.panel_count = 4,
		.lane_count = stream_format == RP1H_STREAM_RGB6_BYTE ? 4 : 2,
		.chain_length = stream_format == RP1H_STREAM_RGB6_BYTE ? 1 : 2,
		.slot_count = 2,
		.dwell_shift_limit = dwell_shift_limit,
	};
	struct rp1h_queue_frame queue = {
		.size = sizeof(queue),
		.flags = RP1H_QUEUE_F_NONBLOCK | RP1H_QUEUE_F_REPLACE_PENDING,
	};
	struct rp1h_mmap_header *hdr;
	uint8_t *frame;
	uint8_t *map;
	uint64_t slot_dma;
	uint32_t dump_words = getenv_u32("HEART_RP1_HUB75_DUMP_WORDS", 0);
	const char *frame_label = frame_path ? frame_path : color->name;
	int fd;
	int ret = 1;

	fd = open(dev, O_RDWR | O_CLOEXEC);
	if (fd < 0) {
		perror(dev);
		return 1;
	}

	if (ioctl(fd, RP1H_CONFIG, &cfg)) {
		perror("RP1H_CONFIG");
		goto out_close;
	}

	frame = calloc(1, cfg.frame_bytes);
	if (!frame) {
		perror("calloc");
		goto out_close;
	}

	if (frame_path) {
		ret = load_rgb_frame(frame_path, frame, cfg.frame_bytes);
		if (ret)
			goto out_free;
	} else {
		for (uint32_t i = 0; i + 2 < cfg.frame_bytes; i += 3) {
			frame[i] = color->red;
			frame[i + 1] = color->green;
			frame[i + 2] = color->blue;
		}
	}
	apply_active_lanes(frame, cfg.frame_bytes, active_lanes);

	queue.length = cfg.frame_bytes;
	queue.data = (uintptr_t)frame;
	if (ioctl(fd, RP1H_QUEUE_FRAME, &queue)) {
		perror("RP1H_QUEUE_FRAME");
		goto out_free;
	}

	map = mmap(NULL, cfg.mmap_size, PROT_READ, MAP_SHARED, fd, 0);
	if (map == MAP_FAILED) {
		perror("mmap " DEFAULT_DEV);
		goto out_free;
	}

	hdr = (struct rp1h_mmap_header *)map;
	if (queue.slot_index >= hdr->slot_count || queue.slot_index >= RP1H_MAX_SLOTS) {
		fprintf(stderr, "invalid queued slot %u of %u\n",
			queue.slot_index, hdr->slot_count);
		goto out_munmap;
	}

	slot_dma = ((uint64_t)hdr->slot_dma_addr_hi[queue.slot_index] << 32) |
		   hdr->slot_dma_addr_lo[queue.slot_index];
	printf("queued %s stream=%s lanes=%s seq=%u slot=%u frame_bytes=%u words=%u slot_dma=0x%016llx\n",
	       frame_label,
	       stream_format == RP1H_STREAM_RGB6_BYTE ? "u8" : "state32",
	       active_lanes == ACTIVE_LANES_P0 ? "p0" :
	       active_lanes == ACTIVE_LANES_P1 ? "p1" : "all",
	       queue.seq, queue.slot_index, cfg.frame_bytes,
	       cfg.words_per_frame, (unsigned long long)slot_dma);
	dump_regular_state32_words(hdr, queue.slot_index, dump_words);
	ret = publish_slot(ctrl_offset, hdr->slot_dma_addr_lo[queue.slot_index],
			   hdr->slot_dma_addr_hi[queue.slot_index],
			   dwell_shift_limit);

out_munmap:
	munmap(map, cfg.mmap_size);
out_free:
	free(frame);
out_close:
	close(fd);
	return ret;
}

int main(int argc, char **argv)
{
	const char *dev = DEFAULT_DEV;
	const char *solid = DEFAULT_SOLID_COLOR;
	const char *lanes_text = DEFAULT_ACTIVE_LANES;
	const char *stream_text = DEFAULT_STREAM_FORMAT;
	uint32_t ctrl_offset = DEFAULT_CTRL_OFFSET;
	uint32_t dwell_shift_limit = RP1H_DEFAULT_DWELL_SHIFT_LIMIT;
	uint32_t pwm_bits = DEFAULT_PWM_BITS;
	uint32_t stream_format;
	struct solid_color color;
	enum active_lanes active_lanes;
	const char *env_solid = getenv("HEART_RP1_HUB75_SOLID");
	const char *env_lanes = getenv("HEART_RP1_HUB75_ACTIVE_LANES");
	const char *env_pwm_bits = getenv("HEART_RP1_HUB75_PWM_BITS");
	const char *env_stream = getenv("HEART_RP1_HUB75_STREAM_FORMAT");
	const char *frame_path = getenv("HEART_RP1_HUB75_FRAME_RGB");

	if (env_solid)
		solid = env_solid;
	if (env_lanes)
		lanes_text = env_lanes;
	if (env_pwm_bits)
		pwm_bits = strtoul(env_pwm_bits, NULL, 0);
	if (env_stream)
		stream_text = env_stream;
	if (argc > 1)
		ctrl_offset = strtoul(argv[1], NULL, 0);
	if (argc > 2)
		dwell_shift_limit = strtoul(argv[2], NULL, 0);
	if (argc > 3)
		pwm_bits = strtoul(argv[3], NULL, 0);
	if (argc > 4)
		dev = argv[4];
	if (argc > 5)
		solid = argv[5];
	if (argc > 6)
		lanes_text = argv[6];
	if (argc > 7)
		stream_text = argv[7];
	if (argc > 8)
		frame_path = argv[8];
	if (argc > 9) {
		fprintf(stderr, "usage: %s [ctrl_offset] [dwell_shift_limit] [pwm_bits] [dev] [solid] [lanes] [stream] [frame_rgb]\n",
			argv[0]);
		return 2;
	}
	if (pwm_bits < 1 || pwm_bits > RP1H_MAX_PWM_BITS) {
		fprintf(stderr, "pwm_bits must be in 1..%u\n", RP1H_MAX_PWM_BITS);
		return 2;
	}
	if (parse_solid_color(solid, &color))
		return 2;
	if (parse_active_lanes(lanes_text, &active_lanes))
		return 2;
	if (parse_stream_format(stream_text, &stream_format))
		return 2;

	return queue_frame(dev, ctrl_offset, dwell_shift_limit, pwm_bits,
			   stream_format, &color, active_lanes, frame_path);
}
