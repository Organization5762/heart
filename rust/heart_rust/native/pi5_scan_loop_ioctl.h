#ifndef HEART_PI5_SCAN_LOOP_IOCTL_H
#define HEART_PI5_SCAN_LOOP_IOCTL_H

#include <linux/ioctl.h>
#include <linux/types.h>

/*
 * Stable ioctl contract shared by:
 *   - the kernel resident replay module
 *   - the Rust/C userspace shim
 *   - standalone debug tools
 *
 * The ABI is session-oriented rather than frame-oriented:
 *   INIT once with the maximum packed frame size
 *   LOAD packed frame bytes whenever content changes
 *   START/STOP replay of the resident frame
 *   WAIT/STATS to observe kernel-owned presentation progress
 *
 * Compatibility rules
 * -------------------
 * This header is the whole userspace/kernel contract for the resident replay
 * path. New fields must be treated like uapi changes:
 *
 *   - keep the fixed-width integer types
 *   - keep struct layout stable for existing ioctl numbers
 *   - prefer additive changes over semantic reinterpretation
 *
 * In particular, LOAD means "replace the resident replay payload while replay
 * is stopped". It does not mean partial patching, scatter/gather updates, or
 * zero-copy mapping of the resident buffer. Those would need explicit new ABI.
 */

#define HEART_PI5_SCAN_LOOP_DEVICE "/dev/heart_pi5_scan_loop"
#define HEART_PI5_SCAN_LOOP_IOCTL_MAGIC 0xB5

struct heart_pi5_scan_loop_init_args {
    /* Capacity of the resident packed frame buffer, in bytes. */
    __u32 frame_bytes;
};

struct heart_pi5_scan_loop_load_args {
	/* Actual byte count copied into the resident frame buffer for this load. */
	__u32 data_bytes;
	/*
	 * Userspace pointer to the packed frame bytes.
	 *
	 * The kernel copies exactly data_bytes from this pointer into its resident
	 * coherent buffer. The pointed-to memory is not retained after ioctl
	 * completion.
	 */
	__u64 data_ptr;
};

struct heart_pi5_scan_loop_wait_args {
    /* Replay count the caller wants to observe before WAIT returns. */
    __u64 target_presentations;
    /* Replay count actually completed when WAIT returns successfully. */
    __u64 completed_presentations;
};

struct heart_pi5_scan_loop_stats_args {
	/* Replay count since the current replay epoch (LOAD/START reset it to 0). */
	__u64 presentations;
    /* Sticky negative errno-style failure from the replay worker, or 0. */
    __s32 last_error;
    /* Current packed frame size loaded into the resident slot. */
    __u32 frame_bytes;
    /* Boolean: replay currently enabled for this session. */
    __u32 replay_enabled;
	/* Completed replay batches since the current replay epoch. */
	__u64 batches_submitted;
	/* Total packed transport words written into the FIFO since the current replay epoch. */
	__u64 words_written;
	/* Number of drain failures seen by the worker since the current replay epoch. */
	__u64 drain_failures;
	/* Number of times STOP/disable interrupted an in-flight replay batch. */
	__u64 stop_requests_seen_during_batch;
	/* Cumulative nanoseconds spent issuing FIFO MMIO writes since the current replay epoch. */
	__u64 mmio_write_ns;
	/* Cumulative nanoseconds spent in the drain completion primitive since the current replay epoch. */
	__u64 drain_ns;
	/* Largest replay batch count actually used since the current replay epoch. */
	__u32 max_batch_replays;
	/* CPU the worker thread is bound to. */
	__u32 worker_cpu;
	/* RT priority requested for the worker thread. */
	__u32 worker_priority;
	/* Boolean: worker currently has enough state to enter a replay batch. */
	__u32 worker_runnable;
};

#define HEART_PI5_SCAN_LOOP_IOC_INIT _IOW(HEART_PI5_SCAN_LOOP_IOCTL_MAGIC, 0, struct heart_pi5_scan_loop_init_args)
#define HEART_PI5_SCAN_LOOP_IOC_LOAD _IOW(HEART_PI5_SCAN_LOOP_IOCTL_MAGIC, 1, struct heart_pi5_scan_loop_load_args)
#define HEART_PI5_SCAN_LOOP_IOC_START _IO(HEART_PI5_SCAN_LOOP_IOCTL_MAGIC, 2)
#define HEART_PI5_SCAN_LOOP_IOC_STOP _IO(HEART_PI5_SCAN_LOOP_IOCTL_MAGIC, 3)
#define HEART_PI5_SCAN_LOOP_IOC_WAIT _IOWR(HEART_PI5_SCAN_LOOP_IOCTL_MAGIC, 4, struct heart_pi5_scan_loop_wait_args)
#define HEART_PI5_SCAN_LOOP_IOC_STATS _IOR(HEART_PI5_SCAN_LOOP_IOCTL_MAGIC, 5, struct heart_pi5_scan_loop_stats_args)

#endif
