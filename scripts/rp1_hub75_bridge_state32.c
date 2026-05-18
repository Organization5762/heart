#include <errno.h>
#include <fcntl.h>
#include <inttypes.h>
#include <stdint.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <sys/ioctl.h>
#include <sys/mman.h>
#include <time.h>
#include <unistd.h>

#define RP1H_DEVICE_NAME "rp1-hub75"
#define RP1H_MAGIC 0x52314837U
#define RP1H_VERSION 1
#define RP1H_MAX_PWM_BITS 11
#define RP1H_MAX_SLOTS 2

#define RP1H_WORKER_F_EXTERNAL_VSYNC (1U << 0)
#define RP1H_STREAM_STATE32 3U

#define RP1H_IOC_MAGIC 'H'
#define RP1H_SIGNAL_VSYNC _IOWR(RP1H_IOC_MAGIC, 0x45, struct rp1h_vsync)
#define RP1H_GET_PRESENT_STATS _IOR(RP1H_IOC_MAGIC, 0x46, struct rp1h_present_stats)
#define RP1H_START_WORKER _IOW(RP1H_IOC_MAGIC, 0x47, struct rp1h_worker_control)

#define RP1_SRAM_HOST_BASE 0x1f00400000ULL
#define RP1_SRAM_MAP_SIZE 0x30000U

#define DEFAULT_DEVICE_PATH "/dev/rp1-hub75"
#define DEFAULT_RUN_SECONDS 10.0
#define DEFAULT_ROWS 64U
#define DEFAULT_COLS 64U
#define DEFAULT_PWM_BITS 11U
#define DEFAULT_SLOT_COUNT 2U
#define DEFAULT_SRAM_OFFSET 0xc000U
#define DEFAULT_STATUS_TIMEOUT_MS 250U

struct rp1h_worker_control {
	uint32_t size;
	uint32_t flags;
	uint32_t status_timeout_ms;
	uint32_t reserved0[5];
};

struct rp1h_vsync {
	uint32_t size;
	uint32_t flags;
	uint32_t presented_seq;
	uint32_t displayed_slot;
	uint32_t reserved0[2];
};

struct rp1h_present_stats {
	uint32_t size;
	uint32_t frames_queued;
	uint32_t frames_presented;
	uint32_t frames_dropped;
	uint32_t vsync_count;
	uint32_t queued_seq;
	uint32_t presented_seq;
	uint32_t displayed_slot;
	uint32_t pending_slot;
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
	uint32_t pin_r1;
	uint32_t pin_g1;
	uint32_t pin_b1;
	uint32_t pin_r2;
	uint32_t pin_g2;
	uint32_t pin_b2;
	uint32_t pin_clk;
	uint32_t pin_lat;
	uint32_t pin_oe;
	uint32_t pin_a;
	uint32_t pin_b;
	uint32_t pin_c;
	uint32_t pin_d;
	uint32_t pin_e;
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

static uint32_t page_align_u32(uint32_t value)
{
	const uint32_t page_size = 4096U;

	return (value + page_size - 1U) & ~(page_size - 1U);
}

static uint32_t expected_mmap_size(uint32_t rows, uint32_t cols,
				   uint32_t pwm_bits, uint32_t slot_count)
{
	uint32_t row_pairs = rows / 2U;
	uint32_t words_per_frame = row_pairs * pwm_bits * cols;
	uint32_t slot_stride = page_align_u32(words_per_frame * sizeof(uint32_t));
	uint32_t words_offset = page_align_u32((uint32_t)sizeof(struct rp1h_mmap_header));

	return page_align_u32(words_offset + slot_count * slot_stride);
}

static double monotonic_seconds(void)
{
	struct timespec ts;

	if (clock_gettime(CLOCK_MONOTONIC, &ts) != 0) {
		perror("clock_gettime");
		exit(1);
	}

	return (double)ts.tv_sec + (double)ts.tv_nsec / 1e9;
}

static uint32_t read_u32_acquire(const uint32_t *value)
{
	return __atomic_load_n(value, __ATOMIC_ACQUIRE);
}

static void usage(const char *argv0)
{
	fprintf(stderr,
		"usage: %s [run_seconds] [device_path] [sram_offset_hex] [pwm_bits]\n",
		argv0);
}

int main(int argc, char **argv)
{
	const char *device_path = DEFAULT_DEVICE_PATH;
	double run_seconds = DEFAULT_RUN_SECONDS;
	uint32_t rows = DEFAULT_ROWS;
	uint32_t cols = DEFAULT_COLS;
	uint32_t pwm_bits = DEFAULT_PWM_BITS;
	uint32_t slot_count = DEFAULT_SLOT_COUNT;
	uint32_t sram_offset = DEFAULT_SRAM_OFFSET;
	uint32_t configured_slot_count;
	uint32_t configured_slot_stride_bytes;
	uint32_t configured_words_offset;
	uint32_t mmap_size;
	uint32_t bytes_per_frame;
	struct rp1h_worker_control worker_ctl = {
		.size = sizeof(worker_ctl),
		.flags = RP1H_WORKER_F_EXTERNAL_VSYNC,
		.status_timeout_ms = DEFAULT_STATUS_TIMEOUT_MS,
	};
	struct rp1h_present_stats stats = {
		.size = sizeof(stats),
	};
	struct rp1h_vsync vsync = {
		.size = sizeof(vsync),
	};
	struct rp1h_mmap_header *hdr;
	volatile uint8_t *rp1_sram;
	void *map;
	void *sram_map;
	double start;
	double deadline;
	uint32_t last_queued_seq = 0;
	uint64_t copies = 0;
	uint64_t idle_loops = 0;
	int dev_fd;
	int mem_fd;

	if (argc > 5) {
		usage(argv[0]);
		return 2;
	}
	if (argc > 1) {
		run_seconds = strtod(argv[1], NULL);
		if (run_seconds <= 0.0) {
			fprintf(stderr, "run_seconds must be > 0\n");
			return 2;
		}
	}
	if (argc > 2)
		device_path = argv[2];
	if (argc > 3)
		sram_offset = (uint32_t)strtoul(argv[3], NULL, 0);
	if (argc > 4) {
		pwm_bits = (uint32_t)strtoul(argv[4], NULL, 0);
		if (!pwm_bits || pwm_bits > RP1H_MAX_PWM_BITS) {
			fprintf(stderr, "pwm_bits must be in 1..%u\n", RP1H_MAX_PWM_BITS);
			return 2;
		}
	}

	mmap_size = expected_mmap_size(rows, cols, pwm_bits, slot_count);
	bytes_per_frame = (rows / 2U) * pwm_bits * cols * sizeof(uint32_t);
	if (sram_offset + bytes_per_frame > RP1_SRAM_MAP_SIZE) {
		fprintf(stderr,
			"sram window too small for bytes_per_frame=%u offset=0x%x\n",
			bytes_per_frame, sram_offset);
		return 2;
	}

	dev_fd = open(device_path, O_RDWR | O_CLOEXEC);
	if (dev_fd < 0) {
		perror(device_path);
		return 1;
	}

	map = mmap(NULL, mmap_size, PROT_READ, MAP_SHARED, dev_fd, 0);
	if (map == MAP_FAILED) {
		perror("mmap hub75");
		close(dev_fd);
		return 1;
	}
	hdr = map;

	if (hdr->magic != RP1H_MAGIC || hdr->version != RP1H_VERSION) {
		fprintf(stderr,
			"unexpected HUB75 header magic=0x%08x version=%u\n",
			hdr->magic, hdr->version);
		munmap(map, mmap_size);
		close(dev_fd);
		return 1;
	}
	if (hdr->stream_format != RP1H_STREAM_STATE32) {
		fprintf(stderr,
			"unexpected stream_format=%u, expected STATE32\n",
			hdr->stream_format);
		munmap(map, mmap_size);
		close(dev_fd);
		return 1;
	}
	if (hdr->slot_count != slot_count) {
		fprintf(stderr,
			"unexpected slot_count=%u, expected %u\n",
			hdr->slot_count, slot_count);
		munmap(map, mmap_size);
		close(dev_fd);
		return 1;
	}
	if (hdr->rows != rows || hdr->cols != cols || hdr->pwm_bits != pwm_bits) {
		fprintf(stderr,
			"unexpected geometry rows=%u cols=%u pwm_bits=%u\n",
			hdr->rows, hdr->cols, hdr->pwm_bits);
		munmap(map, mmap_size);
		close(dev_fd);
		return 1;
	}
	if (hdr->slot_stride_bytes < bytes_per_frame) {
		fprintf(stderr,
			"slot_stride_bytes=%u smaller than bytes_per_frame=%u\n",
			hdr->slot_stride_bytes, bytes_per_frame);
		munmap(map, mmap_size);
		close(dev_fd);
		return 1;
	}
	configured_slot_count = hdr->slot_count;
	configured_slot_stride_bytes = hdr->slot_stride_bytes;
	configured_words_offset = hdr->words_offset;

	if (ioctl(dev_fd, RP1H_START_WORKER, &worker_ctl) != 0) {
		perror("RP1H_START_WORKER");
		munmap(map, mmap_size);
		close(dev_fd);
		return 1;
	}

	mem_fd = open("/dev/mem", O_RDWR | O_SYNC | O_CLOEXEC);
	if (mem_fd < 0) {
		perror("/dev/mem");
		munmap(map, mmap_size);
		close(dev_fd);
		return 1;
	}

	sram_map = mmap(NULL, RP1_SRAM_MAP_SIZE, PROT_READ | PROT_WRITE,
			MAP_SHARED, mem_fd, RP1_SRAM_HOST_BASE);
	close(mem_fd);
	if (sram_map == MAP_FAILED) {
		perror("mmap rp1 sram");
		munmap(map, mmap_size);
		close(dev_fd);
		return 1;
	}
	rp1_sram = sram_map;

	start = monotonic_seconds();
	deadline = start + run_seconds;

	while (monotonic_seconds() < deadline) {
		const uint8_t *slot_base;
		uint32_t pending_slot;
		uint32_t queued_seq;

		if (ioctl(dev_fd, RP1H_GET_PRESENT_STATS, &stats) != 0) {
			perror("RP1H_GET_PRESENT_STATS");
			munmap(sram_map, RP1_SRAM_MAP_SIZE);
			munmap(map, mmap_size);
			close(dev_fd);
			return 1;
		}

		pending_slot = stats.pending_slot;
		queued_seq = stats.queued_seq;
		if (pending_slot == UINT32_MAX || queued_seq == last_queued_seq) {
			idle_loops++;
			usleep(500);
			continue;
		}
		if (pending_slot >= configured_slot_count) {
			fprintf(stderr, "invalid pending_slot=%u slot_count=%u\n",
				pending_slot, configured_slot_count);
			munmap(sram_map, RP1_SRAM_MAP_SIZE);
			munmap(map, mmap_size);
			close(dev_fd);
			return 1;
		}

		slot_base = (const uint8_t *)map + configured_words_offset +
			    pending_slot * configured_slot_stride_bytes;
		memcpy((void *)(rp1_sram + sram_offset), slot_base, bytes_per_frame);

		if (ioctl(dev_fd, RP1H_SIGNAL_VSYNC, &vsync) != 0) {
			perror("RP1H_SIGNAL_VSYNC");
			munmap(sram_map, RP1_SRAM_MAP_SIZE);
			munmap(map, mmap_size);
			close(dev_fd);
			return 1;
		}

		last_queued_seq = queued_seq;
		copies++;
	}

	printf("bridge_result copies=%" PRIu64 " idle_loops=%" PRIu64
	       " queued_seq=%u presented_seq=%u displayed_slot=%u"
	       " bytes_per_frame=%u sram_offset=0x%x worker_timeout_ms=%u"
	       " producer_head=%u consumer_tail=%u\n",
	       copies, idle_loops, stats.queued_seq, vsync.presented_seq,
	       vsync.displayed_slot, bytes_per_frame, sram_offset,
	       worker_ctl.status_timeout_ms,
	       read_u32_acquire(&hdr->producer_head),
	       read_u32_acquire(&hdr->consumer_tail));

	munmap(sram_map, RP1_SRAM_MAP_SIZE);
	munmap(map, mmap_size);
	close(dev_fd);
	return 0;
}
