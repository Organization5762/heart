#include <errno.h>
#include <fcntl.h>
#include <stdbool.h>
#include <stdint.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <sys/ioctl.h>
#include <unistd.h>

#include "pi5_scan_loop_ioctl.h"

/*
 * This shim is intentionally thin: it translates Rust FFI calls into the
 * session-style ioctl contract exposed by /dev/heart_pi5_scan_loop.
 *
 * The kernel module owns replay state and presentation counting. Userspace only
 * does four things here:
 *   - INIT: allocate/configure one resident frame slot
 *   - LOAD: copy a packed frame into that slot
 *   - START/STOP: toggle replay
 *   - WAIT/STATS: observe kernel-owned presentation progress
 *
 * The shim deliberately does not try to be clever about retrying ioctls,
 * caching extra state, or interpreting kernel counters. The kernel module is
 * the source of truth for replay state; this layer just turns errno-oriented
 * ioctl failures into the string-returning FFI contract the Rust side uses.
 */

struct heart_pi5_scan_loop_handle {
    int fd;
    /* The kernel module allocates one resident frame buffer of this exact size. */
    uint32_t frame_bytes;
};

static void heart_pi5_scan_loop_write_error(char *error_buf, size_t error_buf_len, const char *message) {
    if (error_buf == NULL || error_buf_len == 0) {
        return;
    }
    snprintf(error_buf, error_buf_len, "%s", message);
}

int heart_pi5_scan_loop_open(
    uint32_t frame_bytes,
    struct heart_pi5_scan_loop_handle **out_handle,
    char *error_buf,
    size_t error_buf_len
) {
    struct heart_pi5_scan_loop_handle *handle = NULL;
    struct heart_pi5_scan_loop_init_args init_args;

    if (out_handle == NULL) {
        heart_pi5_scan_loop_write_error(error_buf, error_buf_len, "Output handle pointer is required.");
        return -1;
    }
    *out_handle = NULL;
    if (frame_bytes == 0) {
        heart_pi5_scan_loop_write_error(error_buf, error_buf_len, "Resident scan loop requires a non-zero frame size.");
        return -2;
    }

    handle = calloc(1, sizeof(*handle));
    if (handle == NULL) {
        heart_pi5_scan_loop_write_error(error_buf, error_buf_len, "Failed to allocate resident scan loop handle.");
        return -3;
    }

    handle->fd = open(HEART_PI5_SCAN_LOOP_DEVICE, O_RDWR | O_CLOEXEC);
    if (handle->fd < 0) {
        int saved_errno = errno;
        free(handle);
        snprintf(
            error_buf,
            error_buf_len,
            "Failed to open %s (errno=%d).",
            HEART_PI5_SCAN_LOOP_DEVICE,
            saved_errno
        );
        return -4;
    }
    handle->frame_bytes = frame_bytes;

    memset(&init_args, 0, sizeof(init_args));
    /*
     * INIT is the one-time allocation/configure step for a resident frame slot.
     * The handle keeps frame_bytes so later LOAD calls can fail fast in
     * userspace before paying for an ioctl that the kernel will reject anyway.
     */
    init_args.frame_bytes = frame_bytes;
    errno = 0;
    if (ioctl(handle->fd, HEART_PI5_SCAN_LOOP_IOC_INIT, &init_args) < 0) {
        int saved_errno = errno;
        close(handle->fd);
        free(handle);
        snprintf(
            error_buf,
            error_buf_len,
            "Failed to initialize resident scan loop (errno=%d, frame_bytes=%u).",
            saved_errno,
            frame_bytes
        );
        return -5;
    }

    *out_handle = handle;
    heart_pi5_scan_loop_write_error(error_buf, error_buf_len, "");
    return 0;
}

int heart_pi5_scan_loop_load(
    struct heart_pi5_scan_loop_handle *handle,
    const uint8_t *data,
    uint32_t data_bytes,
    char *error_buf,
    size_t error_buf_len
) {
    struct heart_pi5_scan_loop_load_args load_args;

    if (handle == NULL || data == NULL) {
        heart_pi5_scan_loop_write_error(error_buf, error_buf_len, "Resident scan loop handle and data are required.");
        return -1;
    }
    if (data_bytes == 0 || data_bytes > handle->frame_bytes) {
        snprintf(
            error_buf,
            error_buf_len,
            "Resident scan loop expected at most %u bytes but received %u.",
            handle->frame_bytes,
            data_bytes
        );
        return -2;
    }

    memset(&load_args, 0, sizeof(load_args));
    /*
     * LOAD copies a fully packed frame into the resident kernel buffer once.
     * Subsequent resident refreshes do not resend these bytes from userspace.
     *
     * The pointed-to bytes only need to remain valid for the duration of this
     * ioctl. The kernel copies them into its own coherent resident buffer.
     */
    load_args.data_bytes = data_bytes;
    load_args.data_ptr = (uintptr_t)data;
    errno = 0;
    if (ioctl(handle->fd, HEART_PI5_SCAN_LOOP_IOC_LOAD, &load_args) < 0) {
        int saved_errno = errno;
        snprintf(
            error_buf,
            error_buf_len,
            "Failed to load resident scan loop frame (errno=%d, bytes=%u).",
            saved_errno,
            data_bytes
        );
        return -3;
    }

    heart_pi5_scan_loop_write_error(error_buf, error_buf_len, "");
    return 0;
}

int heart_pi5_scan_loop_start(
    struct heart_pi5_scan_loop_handle *handle,
    char *error_buf,
    size_t error_buf_len
) {
    if (handle == NULL) {
        heart_pi5_scan_loop_write_error(error_buf, error_buf_len, "Resident scan loop handle is required.");
        return -1;
    }
    /*
     * START is intentionally separate from LOAD. That separation keeps the
     * session contract obvious: callers may prepare a resident frame, then
     * choose exactly when presentation counting should begin.
     */
    errno = 0;
    if (ioctl(handle->fd, HEART_PI5_SCAN_LOOP_IOC_START) < 0) {
        int saved_errno = errno;
        snprintf(
            error_buf,
            error_buf_len,
            "Failed to start resident scan loop replay (errno=%d).",
            saved_errno
        );
        return -2;
    }
    heart_pi5_scan_loop_write_error(error_buf, error_buf_len, "");
    return 0;
}

int heart_pi5_scan_loop_stop(
    struct heart_pi5_scan_loop_handle *handle,
    char *error_buf,
    size_t error_buf_len
) {
    if (handle == NULL) {
        heart_pi5_scan_loop_write_error(error_buf, error_buf_len, "Resident scan loop handle is required.");
        return -1;
    }
    /*
     * STOP only toggles replay; it does not discard the resident frame. A
     * caller that wants to replace the frame should STOP, LOAD the new bytes,
     * then START again.
     */
    errno = 0;
    if (ioctl(handle->fd, HEART_PI5_SCAN_LOOP_IOC_STOP) < 0) {
        int saved_errno = errno;
        snprintf(
            error_buf,
            error_buf_len,
            "Failed to stop resident scan loop replay (errno=%d).",
            saved_errno
        );
        return -2;
    }
    heart_pi5_scan_loop_write_error(error_buf, error_buf_len, "");
    return 0;
}

int heart_pi5_scan_loop_wait_presentations(
    struct heart_pi5_scan_loop_handle *handle,
    uint64_t target_presentations,
    uint64_t *completed_presentations,
    char *error_buf,
    size_t error_buf_len
) {
    struct heart_pi5_scan_loop_wait_args wait_args;

    if (handle == NULL) {
        heart_pi5_scan_loop_write_error(error_buf, error_buf_len, "Resident scan loop handle is required.");
        return -1;
    }

    memset(&wait_args, 0, sizeof(wait_args));
    /*
     * WAIT blocks until the kernel-owned presentation counter reaches the
     * requested target. Rust uses this for "time to first render" and steady
     * replay accounting without trying to infer refreshes in userspace.
     */
    wait_args.target_presentations = target_presentations;
    errno = 0;
    if (ioctl(handle->fd, HEART_PI5_SCAN_LOOP_IOC_WAIT, &wait_args) < 0) {
        int saved_errno = errno;
        snprintf(
            error_buf,
            error_buf_len,
            "Failed to wait for resident scan loop presentations (errno=%d, target=%llu).",
            saved_errno,
            (unsigned long long)target_presentations
        );
        return -2;
    }
    if (completed_presentations != NULL) {
        *completed_presentations = wait_args.completed_presentations;
    }
    heart_pi5_scan_loop_write_error(error_buf, error_buf_len, "");
    return 0;
}

int heart_pi5_scan_loop_stats(
    struct heart_pi5_scan_loop_handle *handle,
    uint64_t *presentations,
    int32_t *last_error,
    uint32_t *replay_enabled,
    uint64_t *batches_submitted,
    uint64_t *words_written,
    uint64_t *drain_failures,
    uint64_t *stop_requests_seen_during_batch,
    uint64_t *mmio_write_ns,
    uint64_t *drain_ns,
    uint32_t *max_batch_replays,
    uint32_t *worker_cpu,
    uint32_t *worker_priority,
    uint32_t *worker_runnable,
    char *error_buf,
    size_t error_buf_len
) {
    struct heart_pi5_scan_loop_stats_args stats_args;

    if (handle == NULL) {
        heart_pi5_scan_loop_write_error(error_buf, error_buf_len, "Resident scan loop handle is required.");
        return -1;
    }

    memset(&stats_args, 0, sizeof(stats_args));
    /*
     * STATS is intentionally read-only and never changes replay state. It is a
     * snapshot API, not a synchronization primitive; callers that need a replay
     * boundary should use WAIT.
     */
    errno = 0;
    if (ioctl(handle->fd, HEART_PI5_SCAN_LOOP_IOC_STATS, &stats_args) < 0) {
        int saved_errno = errno;
        snprintf(
            error_buf,
            error_buf_len,
            "Failed to read resident scan loop stats (errno=%d).",
            saved_errno
        );
        return -2;
    }
    if (presentations != NULL) {
        *presentations = stats_args.presentations;
    }
    if (last_error != NULL) {
        *last_error = stats_args.last_error;
    }
    if (replay_enabled != NULL) {
        *replay_enabled = stats_args.replay_enabled;
    }
    if (batches_submitted != NULL) {
        *batches_submitted = stats_args.batches_submitted;
    }
    if (words_written != NULL) {
        *words_written = stats_args.words_written;
    }
    if (drain_failures != NULL) {
        *drain_failures = stats_args.drain_failures;
    }
    if (stop_requests_seen_during_batch != NULL) {
        *stop_requests_seen_during_batch = stats_args.stop_requests_seen_during_batch;
    }
    if (mmio_write_ns != NULL) {
        *mmio_write_ns = stats_args.mmio_write_ns;
    }
    if (drain_ns != NULL) {
        *drain_ns = stats_args.drain_ns;
    }
    if (max_batch_replays != NULL) {
        *max_batch_replays = stats_args.max_batch_replays;
    }
    if (worker_cpu != NULL) {
        *worker_cpu = stats_args.worker_cpu;
    }
    if (worker_priority != NULL) {
        *worker_priority = stats_args.worker_priority;
    }
    if (worker_runnable != NULL) {
        *worker_runnable = stats_args.worker_runnable;
    }
    heart_pi5_scan_loop_write_error(error_buf, error_buf_len, "");
    return 0;
}

void heart_pi5_scan_loop_close(struct heart_pi5_scan_loop_handle *handle) {
    if (handle == NULL) {
        return;
    }
    if (handle->fd >= 0) {
        close(handle->fd);
        handle->fd = -1;
    }
    free(handle);
}
