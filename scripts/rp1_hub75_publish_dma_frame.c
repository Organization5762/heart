#include <fcntl.h>
#include <linux/ioctl.h>
#include <stdint.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <sys/ioctl.h>
#include <sys/mman.h>
#include <unistd.h>

#define RP1H_MAGIC 0x52314837U
#define RP1H_MAX_PWM_BITS 11
#define RP1H_MAX_SLOTS 2
#define RP1H_MAPPING_ADAFRUIT_HAT_PWM 0U
#define RP1H_MAPPING_ELECTRODRAGON_P0 1U
#define RP1H_STREAM_STATE32 3U
#define RP1H_DEVICE_PATH "/dev/rp1-hub75"
#define RP1H_IOC_MAGIC 'H'
#define RP1H_CONFIG _IOWR(RP1H_IOC_MAGIC, 0x40, struct rp1h_config)
#define RP1H_QUEUE_FRAME _IOWR(RP1H_IOC_MAGIC, 0x43, struct rp1h_queue_frame)

#define ROWS 64U
#define COLS 256U
#define PWM_BITS 6U
#define RP1_SRAM_HOST_BASE 0x1f00400000ULL
#define RP1_SRAM_MAP_SIZE 0x10000U
#define DEFAULT_SRAM_OFFSET 0xc000U

static unsigned int env_pwm_bits(void)
{
	const char *value = getenv("RP1_HUB75_PWM_BITS");
	unsigned long parsed;

	if (!value || !*value)
		return PWM_BITS;
	parsed = strtoul(value, NULL, 0);
	if (parsed < 1 || parsed > RP1H_MAX_PWM_BITS) {
		fprintf(stderr, "invalid RP1_HUB75_PWM_BITS=%s\n", value);
		exit(2);
	}
	return (unsigned int)parsed;
}

static unsigned int env_mapping(void)
{
	const char *value = getenv("RP1_HUB75_MAPPING");

	if (!value || !*value || !strcmp(value, "adafruit_hat_pwm") ||
	    !strcmp(value, "adafruit-hat-pwm"))
		return RP1H_MAPPING_ADAFRUIT_HAT_PWM;
	if (!strcmp(value, "electrodragon") ||
	    !strcmp(value, "electrodragon_p0") ||
	    !strcmp(value, "electrodragon-p0") ||
	    !strcmp(value, "three-port-active") ||
	    !strcmp(value, "three_port_active") ||
	    !strcmp(value, "regular"))
		return RP1H_MAPPING_ELECTRODRAGON_P0;
	fprintf(stderr, "invalid RP1_HUB75_MAPPING=%s\n", value);
	exit(2);
}

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
	uint32_t reserved1[2];
};

struct rp1h_queue_frame {
	uint32_t size;
	uint32_t length;
	uint32_t flags;
	uint32_t slot_index;
	uint64_t data;
	uint32_t seq;
	uint32_t reserved0;
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

static void write32(volatile void *base, uint32_t off, uint32_t value)
{
	*(volatile uint32_t *)((volatile uint8_t *)base + off) = value;
}

int main(int argc, char **argv)
{
	uint32_t sram_offset = argc > 1 ?
		(uint32_t)strtoul(argv[1], NULL, 0) : DEFAULT_SRAM_OFFSET;
	const char *rgb = argc > 2 ? argv[2] : "255,0,0";
	struct rp1h_config cfg = {
		.size = sizeof(cfg),
		.cols = COLS,
		.rows = ROWS,
		.pwm_bits = env_pwm_bits(),
		.mapping = env_mapping(),
		.stream_format = RP1H_STREAM_STATE32,
		.panel_count = 1,
		.chain_length = 1,
		.slot_count = RP1H_MAX_SLOTS,
	};
	struct rp1h_queue_frame queue = {
		.size = sizeof(queue),
	};
	struct rp1h_mmap_header *hdr;
	unsigned int r;
	unsigned int g;
	unsigned int b;
	uint64_t slot_dma;
	uint8_t *frame;
	void *hub_map;
	void *sram_map;
	int dev_fd;
	int mem_fd;

	if (sscanf(rgb, "%u,%u,%u", &r, &g, &b) != 3 ||
	    r > 255 || g > 255 || b > 255) {
		fprintf(stderr, "usage: %s [sram_offset] [r,g,b]\n", argv[0]);
		return 2;
	}

	dev_fd = open(RP1H_DEVICE_PATH, O_RDWR | O_CLOEXEC);
	if (dev_fd < 0) {
		perror(RP1H_DEVICE_PATH);
		return 1;
	}
	if (ioctl(dev_fd, RP1H_CONFIG, &cfg)) {
		perror("RP1H_CONFIG");
		return 1;
	}

	frame = malloc(cfg.frame_bytes);
	if (!frame) {
		perror("malloc frame");
		return 1;
	}
	for (uint32_t i = 0; i < cfg.frame_bytes; i += 3) {
		frame[i] = (uint8_t)r;
		frame[i + 1] = (uint8_t)g;
		frame[i + 2] = (uint8_t)b;
	}
	queue.length = cfg.frame_bytes;
	queue.data = (uint64_t)(uintptr_t)frame;
	if (ioctl(dev_fd, RP1H_QUEUE_FRAME, &queue)) {
		perror("RP1H_QUEUE_FRAME");
		return 1;
	}

	hub_map = mmap(NULL, cfg.mmap_size, PROT_READ, MAP_SHARED, dev_fd, 0);
	if (hub_map == MAP_FAILED) {
		perror("mmap hub75");
		return 1;
	}
	hdr = hub_map;
	if (hdr->magic != RP1H_MAGIC || queue.slot_index >= hdr->slot_count) {
		fprintf(stderr, "bad header magic=0x%08x slot=%u slot_count=%u\n",
			hdr->magic, queue.slot_index, hdr->slot_count);
		return 1;
	}
	slot_dma = ((uint64_t)hdr->slot_dma_addr_hi[queue.slot_index] << 32) |
		   hdr->slot_dma_addr_lo[queue.slot_index];
	if (!slot_dma) {
		fprintf(stderr,
			"queued slot has no DMA address; update/reload rp1-hub75.ko before host-DMA tests\n");
		return 1;
	}

	mem_fd = open("/dev/mem", O_RDWR | O_SYNC | O_CLOEXEC);
	if (mem_fd < 0) {
		perror("/dev/mem");
		return 1;
	}
	sram_map = mmap(NULL, RP1_SRAM_MAP_SIZE, PROT_READ | PROT_WRITE,
			MAP_SHARED, mem_fd, RP1_SRAM_HOST_BASE);
	close(mem_fd);
	if (sram_map == MAP_FAILED) {
		perror("mmap rp1 sram");
		return 1;
	}

	write32(sram_map, sram_offset + 0, (uint32_t)slot_dma);
	write32(sram_map, sram_offset + 4, (uint32_t)(slot_dma >> 32));
	write32(sram_map, sram_offset + 8, 0);

	printf("published_dma_frame slot=%u seq=%u slot_dma=0x%016llx"
	       " sram_offset=0x%x rgb=%u,%u,%u\n",
	       queue.slot_index, queue.seq, (unsigned long long)slot_dma,
	       sram_offset, r, g, b);
	fflush(stdout);
	pause();
	return 0;
}
