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
#define RP1H_MAX_PWM_BITS 11
#define RP1H_MAX_SLOTS 2
#define RP1H_MAPPING_ADAFRUIT_HAT_PWM 0U
#define RP1H_MAPPING_ELECTRODRAGON_P0 1U
#define RP1H_STREAM_RIO32 0U
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
#define DEFAULT_SRAM_OFFSET 0xb800U
#define DEFAULT_INTERVAL_MS 66U

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

static void sleep_ms(unsigned int ms)
{
	struct timespec ts = {
		.tv_sec = ms / 1000U,
		.tv_nsec = (long)(ms % 1000U) * 1000000L,
	};

	while (nanosleep(&ts, &ts) != 0 && errno == EINTR)
		;
}

static void write32(volatile void *base, uint32_t off, uint32_t value)
{
	*(volatile uint32_t *)((volatile uint8_t *)base + off) = value;
}

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

static long file_size(FILE *file)
{
	long size;

	if (fseek(file, 0, SEEK_END) != 0)
		return -1;
	size = ftell(file);
	rewind(file);
	return size;
}

int main(int argc, char **argv)
{
	const char *frames_path;
	double seconds;
	unsigned int interval_ms = DEFAULT_INTERVAL_MS;
	uint32_t sram_offset = DEFAULT_SRAM_OFFSET;
	uint32_t stream_format = RP1H_STREAM_STATE32;
	const uint32_t frame_bytes = ROWS * COLS * 3U;
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
	struct rp1h_mmap_header *hdr;
	uint8_t *frames;
	long size;
	unsigned int frame_count;
	void *hub_map;
	void *sram_map;
	FILE *file;
	int dev_fd;
	int mem_fd;

	if (argc < 3 || argc > 6) {
		fprintf(stderr, "usage: %s frames.rgb seconds [interval_ms] [sram_offset] [state32|rio32]\n",
			argv[0]);
		return 2;
	}
	frames_path = argv[1];
	seconds = strtod(argv[2], NULL);
	if (argc > 3)
		interval_ms = (unsigned int)strtoul(argv[3], NULL, 0);
	if (argc > 4)
		sram_offset = (uint32_t)strtoul(argv[4], NULL, 0);
	if (argc > 5) {
		if (!strcmp(argv[5], "state32"))
			stream_format = RP1H_STREAM_STATE32;
		else if (!strcmp(argv[5], "rio32"))
			stream_format = RP1H_STREAM_RIO32;
		else {
			fprintf(stderr, "invalid stream format: %s\n", argv[5]);
			return 2;
		}
	}
	if (seconds <= 0.0 || !interval_ms) {
		fprintf(stderr, "invalid seconds or interval\n");
		return 2;
	}

	file = fopen(frames_path, "rb");
	if (!file) {
		perror(frames_path);
		return 1;
	}
	size = file_size(file);
	if (size <= 0 || size % frame_bytes) {
		fprintf(stderr, "frame file size %ld is not a multiple of %u\n",
			size, frame_bytes);
		fclose(file);
		return 2;
	}
	frames = malloc((size_t)size);
	if (!frames) {
		perror("malloc frames");
		fclose(file);
		return 1;
	}
	if (fread(frames, 1, (size_t)size, file) != (size_t)size) {
		perror("fread");
		fclose(file);
		free(frames);
		return 1;
	}
	fclose(file);
	frame_count = (unsigned int)((size_t)size / frame_bytes);

	dev_fd = open(RP1H_DEVICE_PATH, O_RDWR | O_CLOEXEC);
	if (dev_fd < 0) {
		perror(RP1H_DEVICE_PATH);
		free(frames);
		return 1;
	}
	cfg.stream_format = stream_format;
	if (ioctl(dev_fd, RP1H_CONFIG, &cfg)) {
		perror("RP1H_CONFIG");
		free(frames);
		return 1;
	}
	hub_map = mmap(NULL, cfg.mmap_size, PROT_READ, MAP_SHARED, dev_fd, 0);
	if (hub_map == MAP_FAILED) {
		perror("mmap hub75");
		free(frames);
		return 1;
	}
	hdr = hub_map;
	if (hdr->magic != RP1H_MAGIC) {
		fprintf(stderr, "bad header magic=0x%08x\n", hdr->magic);
		free(frames);
		return 1;
	}

	mem_fd = open("/dev/mem", O_RDWR | O_SYNC | O_CLOEXEC);
	if (mem_fd < 0) {
		perror("/dev/mem");
		free(frames);
		return 1;
	}
	sram_map = mmap(NULL, RP1_SRAM_MAP_SIZE, PROT_READ | PROT_WRITE,
			MAP_SHARED, mem_fd, RP1_SRAM_HOST_BASE);
	close(mem_fd);
	if (sram_map == MAP_FAILED) {
		perror("mmap rp1 sram");
		free(frames);
		return 1;
	}

	for (unsigned int seq = 0; (double)seq * interval_ms / 1000.0 < seconds; seq++) {
		struct rp1h_queue_frame queue = {
			.size = sizeof(queue),
			.length = cfg.frame_bytes,
			.data = (uint64_t)(uintptr_t)(frames + (seq % frame_count) * frame_bytes),
		};
		uint64_t slot_dma;

		if (ioctl(dev_fd, RP1H_QUEUE_FRAME, &queue)) {
			perror("RP1H_QUEUE_FRAME");
			free(frames);
			return 1;
		}
		if (queue.slot_index >= hdr->slot_count) {
			fprintf(stderr, "bad queued slot=%u slot_count=%u\n",
				queue.slot_index, hdr->slot_count);
			free(frames);
			return 1;
		}
		slot_dma = ((uint64_t)hdr->slot_dma_addr_hi[queue.slot_index] << 32) |
			   hdr->slot_dma_addr_lo[queue.slot_index];
		if (!slot_dma) {
			fprintf(stderr,
				"queued slot has no DMA address; update/reload rp1-hub75.ko before host-DMA tests\n");
			free(frames);
			return 1;
		}
		write32(sram_map, sram_offset + 0, (uint32_t)slot_dma);
		write32(sram_map, sram_offset + 4, (uint32_t)(slot_dma >> 32));
		write32(sram_map, sram_offset + 8, 0);
		if (!(seq % 20U)) {
			printf("published_dma_frames seq=%u frame=%u/%u slot=%u slot_dma=0x%016llx interval_ms=%u stream=%u words_offset=%u slot_stride=%u\n",
			       seq, seq % frame_count, frame_count, queue.slot_index,
			       (unsigned long long)slot_dma, interval_ms,
			       stream_format, hdr->words_offset,
			       hdr->slot_stride_bytes);
			fflush(stdout);
		}
		sleep_ms(interval_ms);
	}

	free(frames);
	pause();
	return 0;
}
