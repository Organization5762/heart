/* SPDX-License-Identifier: GPL-2.0 WITH Linux-syscall-note */
/*
 * Userspace ABI for RP1 HUB75 frame packing.
 *
 * This ABI does not configure or drive RP1 GPIO by itself. It packs RGB888
 * frames into streams consumed by a dedicated RP1-side worker.
 */

#ifndef _UAPI_MISC_RP1_HUB75_IF_H
#define _UAPI_MISC_RP1_HUB75_IF_H

#include <linux/ioctl.h>
#include <linux/types.h>

#define RP1H_DEVICE_NAME	"rp1-hub75"
#define RP1H_MAGIC		0x52314837 /* "R1H7" */
#define RP1H_VERSION		1
#define RP1H_MAX_PWM_BITS	11
#define RP1H_MAX_SLOTS		2
#define RP1H_DEFAULT_DWELL_SHIFT_LIMIT	7U

enum rp1h_mapping {
	RP1H_MAPPING_ADAFRUIT_HAT_PWM = 0,
	RP1H_MAPPING_ELECTRODRAGON_P0 = 1,
	RP1H_MAPPING_REGULAR = 2,
};

enum rp1h_format {
	RP1H_FORMAT_RGB888 = 0,
};

enum rp1h_stream_format {
	RP1H_STREAM_RIO32 = 0,
	RP1H_STREAM_RGB6_PACKED = 1,
	RP1H_STREAM_RGB6_BYTE = 2,
	RP1H_STREAM_STATE32 = 3,
	RP1H_STREAM_RGB333_WORD = 4,
};

enum rp1h_flags {
	RP1H_F_E_LINE_PRESENT = 1U << 0,
};

enum rp1h_queue_flags {
	RP1H_QUEUE_F_NONBLOCK = 1U << 0,
	RP1H_QUEUE_F_REPLACE_PENDING = 1U << 1,
};

enum rp1h_worker_flags {
	RP1H_WORKER_F_EXTERNAL_VSYNC = 1U << 0,
};

enum rp1h_worker_state {
	RP1H_WORKER_STOPPED = 0,
	RP1H_WORKER_STARTING = 1,
	RP1H_WORKER_RUNNING = 2,
	RP1H_WORKER_STALE = 3,
	RP1H_WORKER_ERROR = 4,
};

struct rp1h_config {
	__u32 size;
	__u16 cols;
	__u16 rows;
	__u8 pwm_bits;
	__u8 mapping;
	__u8 format;
	__u8 reserved0;
	__u32 flags;
	__u32 frame_bytes;
	__u32 mmap_size;
	__u32 words_offset;
	__u32 words_per_frame;
	__u32 stream_format;
	__u32 bits_per_pixel;
	__u32 panel_count;
	__u32 words_per_row_plane;
	__u32 bytes_per_row_plane;
	__u32 words_per_row_plane_aligned;
	__u32 bytes_per_row_plane_aligned;
	__u32 lane_count;
	__u32 chain_length;
	__u32 addr_line_count;
	__u32 slot_count;
	__u32 slot_stride_bytes;
	__u32 reserved1;
	__u32 dwell_shift_limit;
};

struct rp1h_pack_frame {
	__u32 size;
	__u32 length;
	__u64 data;
};

struct rp1h_queue_frame {
	__u32 size;
	__u32 length;
	__u32 flags;
	__u32 slot_index;
	__u64 data;
	__u32 seq;
	__u32 reserved0;
};

struct rp1h_wait_present {
	__u32 size;
	__u32 seq;
	__s64 timeout_ns;
	__u32 presented_seq;
	__u32 reserved0;
};

struct rp1h_vsync {
	__u32 size;
	__u32 flags;
	__u32 presented_seq;
	__u32 displayed_slot;
	__u32 reserved0[2];
};

struct rp1h_stats {
	__u32 size;
	__u32 frames_packed;
	__u64 bytes_packed;
	__u32 last_error;
	__u32 words_per_frame;
};

struct rp1h_present_stats {
	__u32 size;
	__u32 frames_queued;
	__u32 frames_presented;
	__u32 frames_dropped;
	__u32 vsync_count;
	__u32 queued_seq;
	__u32 presented_seq;
	__u32 displayed_slot;
	__u32 pending_slot;
};

struct rp1h_worker_control {
	__u32 size;
	__u32 flags;
	__u32 status_timeout_ms;
	__u32 reserved0[5];
};

struct rp1h_worker_status {
	__u32 size;
	__u32 state;
	__u32 flags;
	__u32 status_timeout_ms;
	__u32 worker_seq;
	__u32 vsync_count;
	__u32 queued_seq;
	__u32 presented_seq;
	__u32 displayed_slot;
	__u32 pending_slot;
	__u32 frames_queued;
	__u32 frames_presented;
	__u32 frames_dropped;
	__u32 last_error;
	__u64 last_vsync_ns;
	__u32 reserved0[4];
};

struct rp1h_mmap_header {
	__u32 magic;
	__u16 version;
	__u16 header_size;
	__u16 cols;
	__u16 rows;
	__u8 pwm_bits;
	__u8 mapping;
	__u8 format;
	__u8 reserved0;
	__u32 flags;
	__u32 frame_seq;
	__u32 words_offset;
	__u32 words_per_frame;
	__u32 pin_r1;
	__u32 pin_g1;
	__u32 pin_b1;
	__u32 pin_r2;
	__u32 pin_g2;
	__u32 pin_b2;
	__u32 pin_clk;
	__u32 pin_lat;
	__u32 pin_oe;
	__u32 pin_a;
	__u32 pin_b;
	__u32 pin_c;
	__u32 pin_d;
	__u32 pin_e;
	__u32 dwell[RP1H_MAX_PWM_BITS];
	__u32 stream_format;
	__u32 bits_per_pixel;
	__u32 row_pairs;
	__u32 plane_count;
	__u32 panel_count;
	__u32 words_per_row_plane;
	__u32 bytes_per_row_plane;
	__u32 words_per_row_plane_aligned;
	__u32 bytes_per_row_plane_aligned;
	__u32 lane_count;
	__u32 chain_length;
	__u32 addr_line_count;
	__u32 slot_count;
	__u32 slot_stride_bytes;
	/*
	 * Queued mode is an SPSC publication contract. producer_head is owned
	 * by the producer and consumer_tail by the consumer. Readers must pair
	 * observations of either field with acquire ordering; writers must
	 * publish updates with release ordering after slot contents are ready
	 * or fully retired.
	 */
	__u32 producer_head;
	__u32 consumer_tail;
	/*
	 * DMA-visible addresses for the packed stream storage. These are the
	 * addresses RP1 bus masters should use when prefetching display slabs
	 * into RP1 SRAM. The values are split into 32-bit words so RP1 firmware
	 * can consume them without relying on C ABI 64-bit alignment.
	 */
	__u32 buffer_dma_addr_lo;
	__u32 buffer_dma_addr_hi;
	__u32 slot_dma_addr_lo[RP1H_MAX_SLOTS];
	__u32 slot_dma_addr_hi[RP1H_MAX_SLOTS];
};

#define RP1H_IOC_MAGIC		'H'

#define RP1H_CONFIG		_IOWR(RP1H_IOC_MAGIC, 0x40, struct rp1h_config)
#define RP1H_PACK_FRAME		_IOW(RP1H_IOC_MAGIC, 0x41, struct rp1h_pack_frame)
#define RP1H_GET_STATS		_IOR(RP1H_IOC_MAGIC, 0x42, struct rp1h_stats)
#define RP1H_QUEUE_FRAME	_IOWR(RP1H_IOC_MAGIC, 0x43, struct rp1h_queue_frame)
#define RP1H_WAIT_PRESENT	_IOWR(RP1H_IOC_MAGIC, 0x44, struct rp1h_wait_present)
#define RP1H_SIGNAL_VSYNC	_IOWR(RP1H_IOC_MAGIC, 0x45, struct rp1h_vsync)
#define RP1H_GET_PRESENT_STATS	_IOR(RP1H_IOC_MAGIC, 0x46, struct rp1h_present_stats)
#define RP1H_START_WORKER	_IOW(RP1H_IOC_MAGIC, 0x47, struct rp1h_worker_control)
#define RP1H_STOP_WORKER	_IOW(RP1H_IOC_MAGIC, 0x48, struct rp1h_worker_control)
#define RP1H_GET_WORKER_STATUS	_IOR(RP1H_IOC_MAGIC, 0x49, struct rp1h_worker_status)

#endif /* _UAPI_MISC_RP1_HUB75_IF_H */
