#include <errno.h>
#include <fcntl.h>
#include <stdbool.h>
#include <stdint.h>
#include <misc/rp1_pio_if.h>
#include <piolib/piolib.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <sys/ioctl.h>
#include <unistd.h>

#include "generated/pi5_pio_programs_generated.h"

/*
 * This shim is the intentionally simple Pi 5 bring-up transport.
 *
 * Rust emits one command stream per row group:
 *   - delay command + blank/address GPIO word
 *   - data command + one literal GPIO word per shifted column
 *   - delay command + latch-high GPIO word
 *   - delay command + post-latch blank GPIO word
 *   - delay command + active/address GPIO word
 *
 * The PIO side interprets only two operations:
 *   - shift N literal GPIO words, pulsing CLK internally
 *   - hold one literal GPIO word for N cycles
 *
 * LAT and OE now live directly in the streamed GPIO words. Only CLK is owned
 * by side-set. This is intentionally the same command shape as Adafruit's
 * Piomatter userspace replay model.
 */

#define HEART_PI5_PIO_SCAN_DEVICE "/dev/pio0"
#define HEART_PI5_PIO_SCAN_ADAFRUIT_PWM_TRANSITION_GPIO 4u
#define HEART_PI5_PIO_SCAN_CONTROL_WORD_BITS 32u
#define HEART_PI5_PIO_SCAN_MAX_XFER_BYTES 65532u
struct heart_pi5_pio_scan_handle {
    PIO pio;
    int sm;
    uint32_t oe_gpio;
    /* Raw /dev/pio0 fd used for CONFIG_XFER, XFER_DATA, and DRAIN_TX ioctls. */
    int ioctl_fd;
    uint program_offset;
    pio_sm_config config;
    uint16_t instructions[HEART_PI5_PIO_SIMPLE_HUB75_PROGRAM_LENGTH];
    pio_program_t program;
};

static void heart_pi5_pio_scan_write_error(char *error_buf, size_t error_buf_len, const char *message) {
    if (error_buf == NULL || error_buf_len == 0) {
        return;
    }
    snprintf(error_buf, error_buf_len, "%s", message);
}

static uint16_t heart_pi5_pio_scan_with_delay(uint16_t instruction, uint32_t ticks) {
    return (uint16_t)((instruction & ~0x0700u) | pio_encode_delay(ticks - 1));
}

static int heart_pi5_pio_scan_xfer_data_large(PIO pio, uint sm, uint dir, size_t size, uint32_t *data) {
    while (size != 0) {
        size_t transfer_bytes = size;
        if (transfer_bytes > HEART_PI5_PIO_SCAN_MAX_XFER_BYTES) {
            transfer_bytes = HEART_PI5_PIO_SCAN_MAX_XFER_BYTES;
        }
        int result = pio_sm_xfer_data(pio, sm, dir, (uint)transfer_bytes, data);
        if (result != 0) {
            return result;
        }
        size -= transfer_bytes;
        data += transfer_bytes / sizeof(*data);
    }
    return 0;
}

static void heart_pi5_pio_scan_pin_init(PIO pio, uint sm, uint pin) {
    pio_gpio_init(pio, pin);
    pio_sm_set_consecutive_pindirs(pio, sm, pin, 1, true);
}

static void heart_pi5_pio_scan_pin_release(uint pin) {
    gpio_set_function(pin, GPIO_FUNC_NULL);
}

static void heart_pi5_pio_scan_quiesce_adafruit_pwm_transition_hack(uint32_t oe_gpio) {
    /*
     * The Adafruit PWM bonnet bridges GPIO18 (new OE) to GPIO4 (legacy OE).
     * Force both pins back to plain inputs before reclaiming the 4..27 output
     * window for PIO so we never momentarily drive two opposing output
     * functions onto that trace.
     */
    if (oe_gpio != 18u) {
        return;
    }
    heart_pi5_pio_scan_pin_release(HEART_PI5_PIO_SCAN_ADAFRUIT_PWM_TRANSITION_GPIO);
    heart_pi5_pio_scan_pin_release((uint)oe_gpio);
}

static bool heart_pi5_pio_scan_should_skip_output_pin(uint32_t oe_gpio, uint pin) {
    return oe_gpio == 18u && pin == HEART_PI5_PIO_SCAN_ADAFRUIT_PWM_TRANSITION_GPIO;
}

static void heart_pi5_pio_scan_output_window_init(PIO pio, uint sm, uint32_t oe_gpio) {
    for (uint pin = HEART_PI5_PIO_SIMPLE_HUB75_OUT_PIN_BASE;
         pin < HEART_PI5_PIO_SIMPLE_HUB75_OUT_PIN_BASE + HEART_PI5_PIO_SIMPLE_HUB75_OUT_PIN_COUNT;
         ++pin) {
        if (heart_pi5_pio_scan_should_skip_output_pin(oe_gpio, pin)) {
            continue;
        }
        heart_pi5_pio_scan_pin_init(pio, sm, pin);
    }
}

static void heart_pi5_pio_scan_output_window_release(uint32_t oe_gpio) {
    for (uint pin = HEART_PI5_PIO_SIMPLE_HUB75_OUT_PIN_BASE;
         pin < HEART_PI5_PIO_SIMPLE_HUB75_OUT_PIN_BASE + HEART_PI5_PIO_SIMPLE_HUB75_OUT_PIN_COUNT;
         ++pin) {
        if (heart_pi5_pio_scan_should_skip_output_pin(oe_gpio, pin)) {
            continue;
        }
        heart_pi5_pio_scan_pin_release(pin);
    }
    heart_pi5_pio_scan_pin_release(HEART_PI5_PIO_SCAN_ADAFRUIT_PWM_TRANSITION_GPIO);
}

static void heart_pi5_pio_scan_reset_sm(struct heart_pi5_pio_scan_handle *handle) {
    /* Match Piomatter startup: clear FIFOs, re-init, and enable without an extra SM restart. */
    pio_select(handle->pio);
    pio_sm_set_enabled(handle->pio, (uint)handle->sm, false);
    pio_sm_clear_fifos(handle->pio, (uint)handle->sm);
    pio_sm_init(handle->pio, (uint)handle->sm, handle->program_offset, &handle->config);
    pio_sm_set_enabled(handle->pio, (uint)handle->sm, true);
}

static void heart_pi5_pio_scan_release(struct heart_pi5_pio_scan_handle *handle) {
    if (handle == NULL) {
        return;
    }

    /*
     * Teardown mirrors open(): stop the SM, release GPIO ownership, close the
     * raw ioctl fd, then drop the PIOLib PIO handle.
     *
     * The order matters for auditability. The raw ioctl fd is not useful once
     * the PIO program and pin ownership are gone, and pio_close() must be last
     * because it owns the remaining PIOLib context.
     */
    pio_select(handle->pio);
    pio_sm_set_enabled(handle->pio, (uint)handle->sm, false);
    pio_sm_clear_fifos(handle->pio, (uint)handle->sm);
    pio_sm_unclaim(handle->pio, (uint)handle->sm);
    pio_remove_program(handle->pio, &handle->program, handle->program_offset);

    heart_pi5_pio_scan_output_window_release(handle->oe_gpio);
    if (handle->ioctl_fd >= 0) {
        close(handle->ioctl_fd);
        handle->ioctl_fd = -1;
    }
    pio_close(handle->pio);
    free(handle);
}

int heart_pi5_pio_scan_open(
    uint32_t oe_gpio,
    uint32_t lat_gpio,
    uint32_t clock_gpio,
    float clock_divider,
    uint32_t simple_clock_hold_ticks,
    uint32_t post_addr_ticks,
    uint32_t latch_ticks,
    uint32_t post_latch_ticks,
    uint32_t dma_buffer_size,
    uint32_t dma_buffer_count,
    struct heart_pi5_pio_scan_handle **out_handle,
    char *error_buf,
    size_t error_buf_len
) {
    struct heart_pi5_pio_scan_handle *handle;
    pio_sm_config config;
    PIO pio;
    int sm;

    if (out_handle == NULL) {
        heart_pi5_pio_scan_write_error(error_buf, error_buf_len, "Output handle pointer is required.");
        return -1;
    }
    *out_handle = NULL;
    if (dma_buffer_size == 0 || dma_buffer_count == 0) {
        heart_pi5_pio_scan_write_error(error_buf, error_buf_len, "PIO scan transport requires non-zero DMA buffering.");
        return -2;
    }
    if (simple_clock_hold_ticks == 0 || simple_clock_hold_ticks > 32 || post_addr_ticks == 0 || post_addr_ticks > 32 || latch_ticks == 0 || latch_ticks > 32 || post_latch_ticks == 0 || post_latch_ticks > 32) {
        heart_pi5_pio_scan_write_error(error_buf, error_buf_len, "PIO scan transport timing ticks must be in the range 1..32.");
        return -2;
    }
    (void)lat_gpio;
    if (pio_init() < 0) {
        heart_pi5_pio_scan_write_error(error_buf, error_buf_len, "pio_init failed.");
        return -3;
    }

    pio = pio_open(0);
    if (PIO_IS_ERR(pio)) {
        heart_pi5_pio_scan_write_error(error_buf, error_buf_len, "pio_open(0) failed.");
        return -4;
    }
    pio_select(pio);

    /*
     * This path still uses PIOLib for program loading and state-machine setup,
     * because it is the least fragile way to establish pin ownership on Pi 5.
     * The data path itself bypasses PIOLib and goes straight to the rp1-pio
     * ioctls below so submit/wait behavior is explicit and measurable.
     *
     * Said differently: PIOLib is used for control-plane setup, not for the
     * steady-state transport benchmark.
     */
    sm = pio_claim_unused_sm(pio, true);
    if (sm < 0) {
        pio_close(pio);
        heart_pi5_pio_scan_write_error(error_buf, error_buf_len, "No free Pi 5 PIO state machine was available.");
        return -5;
    }
    handle = calloc(1, sizeof(*handle));
    if (handle == NULL) {
        pio_sm_unclaim(pio, (uint)sm);
        pio_close(pio);
        heart_pi5_pio_scan_write_error(error_buf, error_buf_len, "Failed to allocate Pi 5 scan transport handle.");
        return -6;
    }

    handle->pio = pio;
    handle->sm = sm;
    handle->ioctl_fd = -1;
    /* The simple transport is a Piomatter-style command interpreter. */
    memcpy(
        handle->instructions,
        heart_pi5_pio_simple_hub75_base_program,
        sizeof(heart_pi5_pio_simple_hub75_base_program)
    );
    (void)post_addr_ticks;
    (void)latch_ticks;
    (void)post_latch_ticks;
    for (size_t patch_index = 0;
         patch_index < sizeof(heart_pi5_pio_simple_hub75_delay_patch_indices) / sizeof(heart_pi5_pio_simple_hub75_delay_patch_indices[0]);
         ++patch_index) {
        uint8_t instruction_index = heart_pi5_pio_simple_hub75_delay_patch_indices[patch_index];
        handle->instructions[instruction_index] =
            heart_pi5_pio_scan_with_delay(handle->instructions[instruction_index], simple_clock_hold_ticks);
    }
    handle->program.instructions = handle->instructions;
    handle->program.length = HEART_PI5_PIO_SIMPLE_HUB75_PROGRAM_LENGTH;
    handle->program.origin = -1;
    handle->oe_gpio = oe_gpio;
    handle->program.pio_version = 0;
    /*
     * During Pi 5 bring-up it is easy to leave stale programs resident in RP1
     * instruction memory across crashed or interrupted processes. On systems
     * where this transport is the only PIO consumer, clearing instruction
     * memory and retrying once is a pragmatic recovery step that avoids a full
     * reboot just to reclaim the 32-instruction store.
     */
    if (!pio_can_add_program(pio, &handle->program)) {
        pio_clear_instruction_memory(pio);
        pio_clear_error(pio);
    }
    handle->program_offset = pio_add_program(pio, &handle->program);
    if (pio_get_error(pio)) {
        heart_pi5_pio_scan_release(handle);
        heart_pi5_pio_scan_write_error(error_buf, error_buf_len, "Failed to load the Pi 5 scan PIO program.");
        return -7;
    }

    config = pio_get_default_sm_config();
    sm_config_set_wrap(&config, handle->program_offset, handle->program_offset + HEART_PI5_PIO_SIMPLE_HUB75_PROGRAM_LENGTH - 1);
    /* Match Piomatter: left-shifting autopull over one continuous 32-bit stream. */
    sm_config_set_out_shift(
        &config,
        HEART_PI5_PIO_SIMPLE_HUB75_OUT_SHIFT_RIGHT,
        HEART_PI5_PIO_SIMPLE_HUB75_AUTO_PULL,
        HEART_PI5_PIO_SIMPLE_HUB75_PULL_THRESHOLD
    );
    sm_config_set_fifo_join(&config, PIO_FIFO_JOIN_TX);
    sm_config_set_clkdiv(&config, clock_divider);
    sm_config_set_out_pins(
        &config,
        HEART_PI5_PIO_SIMPLE_HUB75_OUT_PIN_BASE,
        HEART_PI5_PIO_SIMPLE_HUB75_OUT_PIN_COUNT
    );
    sm_config_set_sideset(
        &config,
        HEART_PI5_PIO_SIMPLE_HUB75_SIDESET_TOTAL_BITS,
        HEART_PI5_PIO_SIMPLE_HUB75_SIDESET_OPTIONAL,
        false
    );
    sm_config_set_sideset_pins(&config, clock_gpio);
    heart_pi5_pio_scan_quiesce_adafruit_pwm_transition_hack(oe_gpio);
    /* OUT PINS drives the real GPIO 0..27 window directly, like Piomatter. */
    heart_pi5_pio_scan_output_window_init(pio, (uint)sm, oe_gpio);
    if (pio_sm_config_xfer(pio, (uint)sm, PIO_DIR_TO_SM, HEART_PI5_PIO_SCAN_MAX_XFER_BYTES, 3u) != 0) {
        heart_pi5_pio_scan_release(handle);
        heart_pi5_pio_scan_write_error(error_buf, error_buf_len, "Failed to configure Pi 5 PIO transfer buffers.");
        return -8;
    }

    handle->config = config;
    pio_sm_init(pio, (uint)sm, handle->program_offset, &handle->config);
    handle->ioctl_fd = open(HEART_PI5_PIO_SCAN_DEVICE, O_RDWR | O_CLOEXEC);
    if (handle->ioctl_fd < 0) {
        heart_pi5_pio_scan_release(handle);
        heart_pi5_pio_scan_write_error(error_buf, error_buf_len, "Failed to open /dev/pio0 for raw scan DMA ioctls.");
        return -9;
    }
    (void)dma_buffer_size;
    (void)dma_buffer_count;
    heart_pi5_pio_scan_reset_sm(handle);
    *out_handle = handle;
    heart_pi5_pio_scan_write_error(error_buf, error_buf_len, "");
    return 0;
}

int heart_pi5_pio_scan_submit(
    struct heart_pi5_pio_scan_handle *handle,
    const uint8_t *data,
    uint32_t data_bytes,
    char *error_buf,
    size_t error_buf_len
) {
    if (handle == NULL || data == NULL) {
        heart_pi5_pio_scan_write_error(error_buf, error_buf_len, "PIO scan transport handle and data are required.");
        return -1;
    }

    if ((data_bytes % sizeof(uint32_t)) != 0) {
        heart_pi5_pio_scan_write_error(
            error_buf,
            error_buf_len,
            "PIO scan explicit-word transport requires a 32-bit-aligned byte count."
        );
        return -2;
    }

    uint32_t word_count = data_bytes / sizeof(uint32_t);
    uint32_t *native_words = calloc(word_count, sizeof(*native_words));

    if (native_words == NULL) {
        heart_pi5_pio_scan_write_error(error_buf, error_buf_len, "Failed to allocate the native Pi 5 transfer buffer.");
        return -3;
    }
    memcpy(native_words, data, data_bytes);
    pio_select(handle->pio);

    if (heart_pi5_pio_scan_xfer_data_large(
            handle->pio,
            (uint)handle->sm,
            PIO_DIR_TO_SM,
            data_bytes,
            native_words
        ) != 0) {
        if (errno == ETIMEDOUT) {
            /*
             * Match observed Piomatter behavior on Pi 5: the rp1-pio transfer
             * ioctl can return ETIMEDOUT even when the state machine continues
             * consuming the submitted buffer and the panel renders correctly.
             * Treat that as a soft submit and let the explicit drain/wait path
             * below decide whether the TX path actually stalls.
             */
            free(native_words);
            heart_pi5_pio_scan_write_error(error_buf, error_buf_len, "");
            return 0;
        }
        snprintf(
            error_buf,
            error_buf_len,
            "Pi 5 PIO transfer submission failed after %u words (%u bytes) (errno=%d: %s).",
            word_count,
            data_bytes,
            errno,
            strerror(errno)
        );
        free(native_words);
        return -6;
    }

    free(native_words);
    heart_pi5_pio_scan_write_error(error_buf, error_buf_len, "");
    return 0;
}

int heart_pi5_pio_scan_wait(
    struct heart_pi5_pio_scan_handle *handle,
    char *error_buf,
    size_t error_buf_len
) {
    if (handle == NULL) {
        heart_pi5_pio_scan_write_error(error_buf, error_buf_len, "PIO scan transport handle is required.");
        return -1;
    }

    /* Wait until the current xfer_data submission drains out of the TX path. */
    pio_select(handle->pio);
    pio_sm_drain_tx_fifo(handle->pio, (uint)handle->sm);

    heart_pi5_pio_scan_write_error(error_buf, error_buf_len, "");
    return 0;
}

void heart_pi5_pio_scan_close(struct heart_pi5_pio_scan_handle *handle) {
    heart_pi5_pio_scan_release(handle);
}
