#include <errno.h>
#include <fcntl.h>
#include <linux/ioctl.h>
#include <stdint.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <sys/ioctl.h>
#include <sys/mman.h>
#include <time.h>
#include <unistd.h>

#define RP1H_MAGIC 0x52314837U
#define RP1H_MAX_PWM_BITS 11U
#define RP1H_MAX_SLOTS 2U
#define RP1H_MAPPING_REGULAR 2U
#define RP1H_FORMAT_RGB888 0U
#define RP1H_STREAM_STATE32 3U
#define RP1H_F_E_LINE_PRESENT (1U << 0)
#define RP1H_DEVICE_PATH "/dev/rp1-hub75"
#define RP1H_IOC_MAGIC 'H'
#define RP1H_CONFIG _IOWR(RP1H_IOC_MAGIC, 0x40, struct rp1h_config)

#define ROWS 64U
#define COLS 64U
#define INPUT_COLS 256U
#define ACTIVE_COLS 128U
#define ROWPAIRS 32U
#define PANEL_SIZE 64U
#define RP1_SRAM_HOST_BASE 0x1f00400000ULL
#define RP1_SRAM_MAP_SIZE 0x10000U
#define RP1H_EXTERNAL_SLOT_META_MAGIC 0x48500000U
#define RP1H_EXTERNAL_SLOT_META_OFFSET 16U
#define DEFAULT_SRAM_OFFSET 0xb800U
#define DEFAULT_PWM_BITS 8U
#define DEFAULT_SECONDS 120U
#define DEFAULT_DWELL_SHIFT_LIMIT 7U

enum pattern {
	PATTERN_ROW_TAIL,
	PATTERN_RGB_BLACK,
	PATTERN_SOLID_RED,
	PATTERN_SOLID_GREEN,
	PATTERN_SOLID_BLUE,
	PATTERN_BLEED,
	PATTERN_HLINES,
};

#define GPIO_OE 18
#define GPIO_A 22
#define GPIO_B 23
#define GPIO_C 24
#define GPIO_D 25
#define GPIO_E 15
#define GPIO_P0_R1 11
#define GPIO_P0_G1 27
#define GPIO_P0_B1 7
#define GPIO_P0_R2 8
#define GPIO_P0_G2 9
#define GPIO_P0_B2 10
#define GPIO_P1_R1 12
#define GPIO_P1_G1 5
#define GPIO_P1_B1 6
#define GPIO_P1_R2 19
#define GPIO_P1_G2 13
#define GPIO_P1_B2 20

#define PIN(gpio) (1U << (gpio))

struct rp1h_config {
	uint32_t size;
	uint16_t cols;
	uint16_t rows;
	uint8_t pwm_bits;
	uint8_t mapping;
	uint8_t format;
	uint8_t reserved0;
	uint32_t flags;
	uint32_t frame_bytes;
	uint32_t mmap_size;
	uint32_t words_offset;
	uint32_t words_per_frame;
	uint32_t stream_format;
	uint32_t bits_per_pixel;
	uint32_t panel_count;
	uint32_t words_per_row_plane;
	uint32_t bytes_per_row_plane;
	uint32_t words_per_row_plane_aligned;
	uint32_t bytes_per_row_plane_aligned;
	uint32_t lane_count;
	uint32_t chain_length;
	uint32_t addr_line_count;
	uint32_t slot_count;
	uint32_t slot_stride_bytes;
	uint32_t reserved1;
	uint32_t dwell_shift_limit;
};

struct rp1h_mmap_header {
	uint32_t magic;
	uint16_t version;
	uint16_t header_size;
	uint16_t cols;
	uint16_t rows;
	uint8_t pwm_bits;
	uint8_t mapping;
	uint8_t format;
	uint8_t reserved0;
	uint32_t flags;
	uint32_t frame_seq;
	uint32_t words_offset;
	uint32_t words_per_frame;
	uint32_t pins[14];
	uint32_t dwell[RP1H_MAX_PWM_BITS];
	uint32_t stream_format;
	uint32_t bits_per_pixel;
	uint32_t row_pairs;
	uint32_t plane_count;
	uint32_t panel_count;
	uint32_t words_per_row_plane;
	uint32_t bytes_per_row_plane;
	uint32_t words_per_row_plane_aligned;
	uint32_t bytes_per_row_plane_aligned;
	uint32_t lane_count;
	uint32_t chain_length;
	uint32_t addr_line_count;
	uint32_t slot_count;
	uint32_t slot_stride_bytes;
	uint32_t producer_head;
	uint32_t consumer_tail;
	uint32_t buffer_dma_addr_lo;
	uint32_t buffer_dma_addr_hi;
	uint32_t slot_dma_addr_lo[RP1H_MAX_SLOTS];
	uint32_t slot_dma_addr_hi[RP1H_MAX_SLOTS];
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

static uint32_t addr_mask(unsigned int row)
{
	uint32_t mask = 0;

	if (row & 1U)
		mask |= PIN(GPIO_A);
	if (row & 2U)
		mask |= PIN(GPIO_B);
	if (row & 4U)
		mask |= PIN(GPIO_C);
	if (row & 8U)
		mask |= PIN(GPIO_D);
	if (row & 16U)
		mask |= PIN(GPIO_E);
	return mask;
}

static enum pattern parse_pattern(const char *name)
{
	if (!name || strcmp(name, "row-tail") == 0)
		return PATTERN_ROW_TAIL;
	if (strcmp(name, "rgb-black") == 0)
		return PATTERN_RGB_BLACK;
	if (strcmp(name, "red") == 0 || strcmp(name, "solid-red") == 0)
		return PATTERN_SOLID_RED;
	if (strcmp(name, "green") == 0 || strcmp(name, "solid-green") == 0)
		return PATTERN_SOLID_GREEN;
	if (strcmp(name, "blue") == 0 || strcmp(name, "solid-blue") == 0)
		return PATTERN_SOLID_BLUE;
	if (strcmp(name, "bleed") == 0 || strcmp(name, "channel-bleed") == 0)
		return PATTERN_BLEED;
	if (strcmp(name, "hlines") == 0 || strcmp(name, "horizontal-lines") == 0)
		return PATTERN_HLINES;
	fprintf(stderr, "unknown pattern '%s'; using row-tail\n", name);
	return PATTERN_ROW_TAIL;
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
	if (pattern == PATTERN_SOLID_RED)
		return (struct rgb){ 255, 0, 0 };
	if (pattern == PATTERN_SOLID_GREEN)
		return (struct rgb){ 0, 255, 0 };
	if (pattern == PATTERN_SOLID_BLUE)
		return (struct rgb){ 0, 0, 255 };
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
		unsigned int line = y % 8U;
		unsigned int phase = (line + panel) % 8U;

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
	if (pattern == PATTERN_ROW_TAIL &&
	    ((y >= 24U && y <= 31U) || (y >= 56U && y <= 63U)))
		color = tail_colors[panel];
	if (local_x == 0U || local_x == 63U || y == 31U || y == 32U)
		return (struct rgb){ 0, 0, 0 };
	if (pattern == PATTERN_ROW_TAIL &&
	    ((y >= 24U && y <= 31U) || (y >= 56U && y <= 63U)) &&
	    local_x >= 8U && (local_x - 8U) % 16U == 0U)
		return (struct rgb){ 0, 0, 0 };
	return color;
}

static uint32_t lane_mask(struct rgb top, struct rgb bottom,
			  unsigned int r1, unsigned int g1, unsigned int b1,
			  unsigned int r2, unsigned int g2, unsigned int b2)
{
	uint32_t mask = 0;

	if (top.r)
		mask |= PIN(r1);
	if (top.g)
		mask |= PIN(g1);
	if (top.b)
		mask |= PIN(b1);
	if (bottom.r)
		mask |= PIN(r2);
	if (bottom.g)
		mask |= PIN(g2);
	if (bottom.b)
		mask |= PIN(b2);
	return mask;
}

static void fill_direct_regular_state32(uint32_t *words, unsigned int pwm_bits,
					enum pattern pattern)
{
	for (unsigned int row = 0; row < ROWPAIRS; row++) {
		for (unsigned int plane = 0; plane < pwm_bits; plane++) {
			uint32_t base = addr_mask(row) | PIN(GPIO_OE);

			for (unsigned int col = 0; col < ACTIVE_COLS; col++) {
				struct rgb p0_top = source_pixel(col, row, pattern);
				struct rgb p0_bottom =
					source_pixel(col, row + ROWPAIRS, pattern);
				struct rgb p1_top =
					source_pixel(ACTIVE_COLS + col, row, pattern);
				struct rgb p1_bottom =
					source_pixel(ACTIVE_COLS + col, row + ROWPAIRS,
						     pattern);

				*words++ = base |
					   lane_mask(p0_top, p0_bottom,
						     GPIO_P0_R1, GPIO_P0_G1, GPIO_P0_B1,
						     GPIO_P0_R2, GPIO_P0_G2, GPIO_P0_B2) |
					   lane_mask(p1_top, p1_bottom,
						     GPIO_P1_R1, GPIO_P1_G1, GPIO_P1_B1,
						     GPIO_P1_R2, GPIO_P1_G2, GPIO_P1_B2);
			}
		}
	}
}

int main(int argc, char **argv)
{
	unsigned int seconds = argc > 1 ? (unsigned int)strtoul(argv[1], NULL, 0) :
					 DEFAULT_SECONDS;
	uint32_t sram_offset = argc > 2 ? (uint32_t)strtoul(argv[2], NULL, 0) :
					 DEFAULT_SRAM_OFFSET;
	unsigned int pwm_bits = argc > 3 ? (unsigned int)strtoul(argv[3], NULL, 0) :
					  DEFAULT_PWM_BITS;
	const char *pattern_name = argc > 4 ? argv[4] : getenv("RP1_HUB75_DIRECT_PATTERN");
	enum pattern pattern = parse_pattern(pattern_name);
	struct rp1h_config cfg = {
		.size = sizeof(cfg),
		.cols = COLS,
		.rows = ROWS,
		.pwm_bits = (uint8_t)pwm_bits,
		.mapping = RP1H_MAPPING_REGULAR,
		.format = RP1H_FORMAT_RGB888,
		.flags = RP1H_F_E_LINE_PRESENT,
		.stream_format = RP1H_STREAM_STATE32,
		.panel_count = 4,
		.lane_count = 2,
		.chain_length = 2,
		.slot_count = RP1H_MAX_SLOTS,
		.dwell_shift_limit = DEFAULT_DWELL_SHIFT_LIMIT,
	};
	struct rp1h_mmap_header *hdr;
	uint64_t slot_dma;
	uint32_t *slot_words;
	void *hub_map;
	void *sram_map;
	int dev_fd;
	int mem_fd;

	if (!pwm_bits || pwm_bits > RP1H_MAX_PWM_BITS) {
		fprintf(stderr, "usage: %s [seconds] [sram_offset] [pwm_bits] [pattern]\n",
			argv[0]);
		return 2;
	}

	dev_fd = open(RP1H_DEVICE_PATH, O_RDWR | O_CLOEXEC);
	if (dev_fd < 0) {
		perror(RP1H_DEVICE_PATH);
		return 1;
	}
	if (ioctl(dev_fd, RP1H_CONFIG, &cfg)) {
		perror("RP1H_CONFIG");
		close(dev_fd);
		return 1;
	}
	hub_map = mmap(NULL, cfg.mmap_size, PROT_READ | PROT_WRITE, MAP_SHARED, dev_fd, 0);
	if (hub_map == MAP_FAILED) {
		perror("mmap hub75");
		close(dev_fd);
		return 1;
	}
	hdr = hub_map;
	if (hdr->magic != RP1H_MAGIC || hdr->slot_count < 1U ||
	    hdr->words_per_row_plane != ACTIVE_COLS ||
	    hdr->words_per_frame != ROWPAIRS * pwm_bits * ACTIVE_COLS) {
		fprintf(stderr,
			"unexpected header magic=0x%08x slots=%u words_per_row_plane=%u words_per_frame=%u\n",
			hdr->magic, hdr->slot_count, hdr->words_per_row_plane,
			hdr->words_per_frame);
		munmap(hub_map, cfg.mmap_size);
		close(dev_fd);
		return 1;
	}

	slot_words = (uint32_t *)((uint8_t *)hub_map + hdr->words_offset);
	memset(slot_words, 0, hdr->slot_stride_bytes);
	fill_direct_regular_state32(slot_words, pwm_bits, pattern);
	__sync_synchronize();

	slot_dma = ((uint64_t)hdr->slot_dma_addr_hi[0] << 32) | hdr->slot_dma_addr_lo[0];
	if (!slot_dma) {
		fprintf(stderr, "slot 0 has no DMA address\n");
		munmap(hub_map, cfg.mmap_size);
		close(dev_fd);
		return 1;
	}

	mem_fd = open("/dev/mem", O_RDWR | O_SYNC | O_CLOEXEC);
	if (mem_fd < 0) {
		perror("/dev/mem");
		munmap(hub_map, cfg.mmap_size);
		close(dev_fd);
		return 1;
	}
	sram_map = mmap(NULL, RP1_SRAM_MAP_SIZE, PROT_READ | PROT_WRITE,
			MAP_SHARED, mem_fd, RP1_SRAM_HOST_BASE);
	close(mem_fd);
	if (sram_map == MAP_FAILED) {
		perror("mmap rp1 sram");
		munmap(hub_map, cfg.mmap_size);
		close(dev_fd);
		return 1;
	}

	write32(sram_map, sram_offset + 0, (uint32_t)slot_dma);
	write32(sram_map, sram_offset + 4, (uint32_t)(slot_dma >> 32));
	write32(sram_map, sram_offset + 8, 0);
	write32(sram_map, sram_offset + 12, DEFAULT_DWELL_SHIFT_LIMIT);
	write32(sram_map, sram_offset + RP1H_EXTERNAL_SLOT_META_OFFSET,
		RP1H_EXTERNAL_SLOT_META_MAGIC | pwm_bits);
	__sync_synchronize();

	printf("published_direct_state32_regular slot=0 slot_dma=0x%016llx words=%u"
	       " words_per_row_plane=%u pwm_bits=%u sram_offset=0x%x seconds=%u pattern=%s\n",
	       (unsigned long long)slot_dma, hdr->words_per_frame,
	       hdr->words_per_row_plane, pwm_bits, sram_offset, seconds,
	       pattern_name ? pattern_name : "row-tail");
	fflush(stdout);
	if (seconds)
		sleep_seconds(seconds);

	munmap(sram_map, RP1_SRAM_MAP_SIZE);
	munmap(hub_map, cfg.mmap_size);
	close(dev_fd);
	return 0;
}
