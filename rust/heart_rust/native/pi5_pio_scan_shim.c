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

/*
 * This shim is the "honest baseline" transport for Pi 5 scanout:
 * userspace opens one RP1 PIO state machine, loads the shared 25-instruction
 * parser, and then submits entire packed frames through the stock rp1-pio
 * ioctls. It intentionally mirrors the kernel resident-loop parser so the two
 * backends can be compared without protocol differences.
 *
 * This file is therefore maintained with two priorities:
 *   1. keep behavior explicit and easy to measure
 *   2. keep its parser/protocol contract aligned with the resident-loop path
 *
 * It is not trying to hide transport costs. In particular, submit and drain
 * are separate observable operations because benchmarking needs to distinguish
 * "frame was accepted for transfer" from "TX path consumed the submitted data."
 */

#define HEART_PI5_PIO_SCAN_DEVICE "/dev/pio0"
#define HEART_PI5_PIO_SCAN_PROGRAM_LENGTH 25
#define HEART_PI5_PIO_SCAN_OUTPUT_PIN_BASE 5u
#define HEART_PI5_PIO_SCAN_OUTPUT_PIN_COUNT 23u
#define HEART_PI5_PIO_SCAN_CONTROL_WORD_BITS 32u
#define HEART_PI5_PIO_SCAN_PIN_WORD_BITS 23u
#define HEART_PI5_PIO_SCAN_LAT_SET_LOW 0u
#define HEART_PI5_PIO_SCAN_LAT_SET_HIGH 1u
#define HEART_PI5_PIO_SCAN_SIDESET_ACTIVE 0x0u
#define HEART_PI5_PIO_SCAN_SIDESET_BLANK_LOW 0x2u
#define HEART_PI5_PIO_SCAN_SIDESET_BLANK_HIGH 0x3u

struct heart_pi5_pio_scan_handle {
    PIO pio;
    int sm;
    /* Raw /dev/pio0 fd used for CONFIG_XFER, XFER_DATA, and DRAIN_TX ioctls. */
    int ioctl_fd;
    uint32_t oe_gpio;
    uint32_t lat_gpio;
    uint32_t clock_gpio;
    uint program_offset;
    uint16_t instructions[HEART_PI5_PIO_SCAN_PROGRAM_LENGTH];
    pio_program_t program;
};

static const uint32_t HEART_PI5_RGB_GPIOS[] = {5, 13, 6, 12, 16, 23};
static const uint32_t HEART_PI5_ADDR_GPIOS[] = {22, 26, 27, 20, 24};

static void heart_pi5_pio_scan_write_error(char *error_buf, size_t error_buf_len, const char *message) {
    if (error_buf == NULL || error_buf_len == 0) {
        return;
    }
    snprintf(error_buf, error_buf_len, "%s", message);
}

static void heart_pi5_pio_scan_pin_init(PIO pio, uint sm, uint pin) {
    pio_gpio_init(pio, pin);
    gpio_set_function(pin, GPIO_FUNC_PIO0);
    pio_sm_set_consecutive_pindirs(pio, sm, pin, 1, true);
}

static void heart_pi5_pio_scan_pin_release(uint pin) {
    gpio_set_function(pin, GPIO_FUNC_NULL);
}

static void heart_pi5_pio_scan_release(struct heart_pi5_pio_scan_handle *handle) {
    size_t index;

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
    pio_sm_unclaim(handle->pio, (uint)handle->sm);
    pio_remove_program(handle->pio, &handle->program, handle->program_offset);

    heart_pi5_pio_scan_pin_release(handle->oe_gpio);
    heart_pi5_pio_scan_pin_release(handle->lat_gpio);
    heart_pi5_pio_scan_pin_release(handle->clock_gpio);
    for (index = 0; index < (sizeof(HEART_PI5_RGB_GPIOS) / sizeof(HEART_PI5_RGB_GPIOS[0])); ++index) {
        heart_pi5_pio_scan_pin_release(HEART_PI5_RGB_GPIOS[index]);
    }
    for (index = 0; index < (sizeof(HEART_PI5_ADDR_GPIOS) / sizeof(HEART_PI5_ADDR_GPIOS[0])); ++index) {
        heart_pi5_pio_scan_pin_release(HEART_PI5_ADDR_GPIOS[index]);
    }
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
    if (post_addr_ticks == 0 || post_addr_ticks > 32 || latch_ticks == 0 || latch_ticks > 32 || post_latch_ticks == 0 || post_latch_ticks > 32) {
        heart_pi5_pio_scan_write_error(error_buf, error_buf_len, "PIO scan transport timing ticks must be in the range 1..32.");
        return -2;
    }
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
    handle->oe_gpio = oe_gpio;
    handle->lat_gpio = lat_gpio;
    handle->clock_gpio = clock_gpio;
    /*
     * The userspace transport and the kernel resident loop share the same
     * 25-instruction parser. The Rust packer emits:
     *   - one blank/address word
     *   - zero or more spans:
     *       * raw span: one packed control word
     *           bit 0      => raw opcode
     *           bits 1..8  => raw_len - 1
     *           bits 9..31 => first 23-bit GPIO word
     *           packed words for the remaining columns follow
     *       * repeat span: one packed control word
     *           bit 0      => repeat opcode
     *           bits 1..8  => repeat_len - 1
     *           bits 9..31 => repeated 23-bit GPIO word
     *   - a single zero terminator
     *   - dwell counter
     *
     * Keeping the parser identical across both backends lets us benchmark the
     * same packed frame format against raw rp1-pio DMA and the custom resident
     * loop without changing the Rust side.
     *
     * If this parser changes, maintainers should assume the kernel resident
     * loop parser needs the same update unless the change is explicitly called
     * out as a format fork.
     *
     * The trailer no longer ships explicit latch/active words. Instead:
     *   - OE rides on sideset together with the clock (GPIO 17/18)
     *   - LAT is pulsed internally via SET PINS on GPIO 21
     *
     * That keeps the resident payload focused on row-addressed setup, span
     * descriptions, and dwell. The dense-path win is that both span types now
     * inline the first/only GPIO word in the control word:
     *   - raw spans pay packed payload words only for columns after the first
     *   - repeat spans still collapse long constant runs to one control word
     *
     * Instruction layout:
     *   0..2   load and apply the row-addressed blank word
     *   3..11  decode one packed repeat span
     *   12..18 decode one raw span or detect end-of-spans
     *   19..24 pulse LAT, dwell with OE active, then blank for the next group
     */
    handle->instructions[0] = (uint16_t)pio_encode_pull(false, true);
    handle->instructions[1] = (uint16_t)(
        pio_encode_out(pio_pins, HEART_PI5_PIO_SCAN_PIN_WORD_BITS) |
        pio_encode_sideset_opt(2, HEART_PI5_PIO_SCAN_SIDESET_BLANK_LOW)
    );
    handle->instructions[2] = (uint16_t)(
        pio_encode_nop() |
        pio_encode_delay(post_addr_ticks - 1) |
        pio_encode_sideset_opt(2, HEART_PI5_PIO_SCAN_SIDESET_BLANK_LOW)
    );
    handle->instructions[3] = (uint16_t)pio_encode_pull(false, true);
    handle->instructions[4] = (uint16_t)pio_encode_out(pio_x, 1);
    handle->instructions[5] = (uint16_t)pio_encode_jmp_not_x(12);
    handle->instructions[6] = (uint16_t)pio_encode_out(pio_y, 8);
    handle->instructions[7] = (uint16_t)pio_encode_mov(pio_x, pio_osr);
    handle->instructions[8] = (uint16_t)(
        pio_encode_mov(pio_osr, pio_x) |
        pio_encode_sideset_opt(2, HEART_PI5_PIO_SCAN_SIDESET_BLANK_LOW)
    );
    handle->instructions[9] = (uint16_t)(
        pio_encode_out(pio_pins, HEART_PI5_PIO_SCAN_PIN_WORD_BITS) |
        pio_encode_sideset_opt(2, HEART_PI5_PIO_SCAN_SIDESET_BLANK_LOW)
    );
    handle->instructions[10] = (uint16_t)(
        pio_encode_jmp_y_dec(8) |
        pio_encode_sideset_opt(2, HEART_PI5_PIO_SCAN_SIDESET_BLANK_HIGH)
    );
    handle->instructions[11] = (uint16_t)(
        pio_encode_jmp(3) |
        pio_encode_sideset_opt(2, HEART_PI5_PIO_SCAN_SIDESET_BLANK_LOW)
    );
    handle->instructions[12] = (uint16_t)pio_encode_out(pio_y, 8);
    handle->instructions[13] = (uint16_t)pio_encode_out(pio_x, HEART_PI5_PIO_SCAN_PIN_WORD_BITS);
    handle->instructions[14] = (uint16_t)pio_encode_jmp_not_x(19);
    handle->instructions[15] = (uint16_t)(
        pio_encode_mov(pio_osr, pio_x) |
        pio_encode_sideset_opt(2, HEART_PI5_PIO_SCAN_SIDESET_BLANK_LOW)
    );
    handle->instructions[16] = (uint16_t)(
        pio_encode_out(pio_pins, HEART_PI5_PIO_SCAN_PIN_WORD_BITS) |
        pio_encode_sideset_opt(2, HEART_PI5_PIO_SCAN_SIDESET_BLANK_LOW)
    );
    handle->instructions[17] = (uint16_t)(
        pio_encode_jmp_y_dec(16) |
        pio_encode_sideset_opt(2, HEART_PI5_PIO_SCAN_SIDESET_BLANK_HIGH)
    );
    handle->instructions[18] = (uint16_t)(
        pio_encode_jmp(3) |
        pio_encode_sideset_opt(2, HEART_PI5_PIO_SCAN_SIDESET_BLANK_LOW)
    );
    handle->instructions[19] = (uint16_t)(
        pio_encode_set(pio_pins, HEART_PI5_PIO_SCAN_LAT_SET_HIGH) |
        pio_encode_delay(latch_ticks - 1) |
        pio_encode_sideset_opt(2, HEART_PI5_PIO_SCAN_SIDESET_BLANK_LOW)
    );
    handle->instructions[20] = (uint16_t)(
        pio_encode_set(pio_pins, HEART_PI5_PIO_SCAN_LAT_SET_LOW) |
        pio_encode_delay(post_latch_ticks - 1) |
        pio_encode_sideset_opt(2, HEART_PI5_PIO_SCAN_SIDESET_BLANK_LOW)
    );
    handle->instructions[21] = (uint16_t)(
        pio_encode_pull(false, true) |
        pio_encode_sideset_opt(2, HEART_PI5_PIO_SCAN_SIDESET_ACTIVE)
    );
    handle->instructions[22] = (uint16_t)(
        pio_encode_out(pio_y, HEART_PI5_PIO_SCAN_CONTROL_WORD_BITS) |
        pio_encode_sideset_opt(2, HEART_PI5_PIO_SCAN_SIDESET_ACTIVE)
    );
    handle->instructions[23] = (uint16_t)(
        pio_encode_jmp_y_dec(23) |
        pio_encode_sideset_opt(2, HEART_PI5_PIO_SCAN_SIDESET_ACTIVE)
    );
    handle->instructions[24] = (uint16_t)(
        pio_encode_jmp(0) |
        pio_encode_sideset_opt(2, HEART_PI5_PIO_SCAN_SIDESET_BLANK_LOW)
    );
    handle->program.instructions = handle->instructions;
    handle->program.length = HEART_PI5_PIO_SCAN_PROGRAM_LENGTH;
    handle->program.origin = -1;
    handle->program.pio_version = 0;
    handle->program_offset = pio_add_program(pio, &handle->program);
    if (pio_get_error(pio)) {
        heart_pi5_pio_scan_release(handle);
        heart_pi5_pio_scan_write_error(error_buf, error_buf_len, "Failed to load the Pi 5 scan PIO program.");
        return -7;
    }

    config = pio_get_default_sm_config();
    sm_config_set_wrap(&config, handle->program_offset, handle->program_offset + HEART_PI5_PIO_SCAN_PROGRAM_LENGTH - 1);
    sm_config_set_sideset(&config, 3, true, false);
    sm_config_set_out_shift(&config, false, true, HEART_PI5_PIO_SCAN_PIN_WORD_BITS);
    sm_config_set_fifo_join(&config, PIO_FIFO_JOIN_TX);
    sm_config_set_clkdiv(&config, clock_divider);
    sm_config_set_out_pins(&config, HEART_PI5_PIO_SCAN_OUTPUT_PIN_BASE, HEART_PI5_PIO_SCAN_OUTPUT_PIN_COUNT);
    sm_config_set_set_pins(&config, lat_gpio, 1);
    sm_config_set_sideset_pins(&config, clock_gpio);

    heart_pi5_pio_scan_pin_init(pio, (uint)sm, oe_gpio);
    heart_pi5_pio_scan_pin_init(pio, (uint)sm, lat_gpio);
    heart_pi5_pio_scan_pin_init(pio, (uint)sm, clock_gpio);
    for (size_t index = 0; index < (sizeof(HEART_PI5_RGB_GPIOS) / sizeof(HEART_PI5_RGB_GPIOS[0])); ++index) {
        heart_pi5_pio_scan_pin_init(pio, (uint)sm, HEART_PI5_RGB_GPIOS[index]);
    }
    for (size_t index = 0; index < (sizeof(HEART_PI5_ADDR_GPIOS) / sizeof(HEART_PI5_ADDR_GPIOS[0])); ++index) {
        heart_pi5_pio_scan_pin_init(pio, (uint)sm, HEART_PI5_ADDR_GPIOS[index]);
    }

    pio_sm_init(pio, (uint)sm, handle->program_offset, &config);
    handle->ioctl_fd = open(HEART_PI5_PIO_SCAN_DEVICE, O_RDWR | O_CLOEXEC);
    if (handle->ioctl_fd < 0) {
        heart_pi5_pio_scan_release(handle);
        heart_pi5_pio_scan_write_error(error_buf, error_buf_len, "Failed to open /dev/pio0 for raw scan DMA ioctls.");
        return -8;
    }
    /*
     * CONFIG_XFER programs the rp1-pio side DMA ring that backs XFER_DATA. The
     * packed scan protocol is independent of this buffer sizing; these values
     * only affect how the kernel moves one submitted frame into the FIFO path.
     *
     * This distinction matters when reading benchmarks: changing buffer sizing
     * may alter transport throughput without implying any change in the packed
     * protocol or the scan program itself.
     */
    int config_xfer_result;
    if (dma_buffer_size <= UINT16_MAX && dma_buffer_count <= UINT16_MAX) {
        struct rp1_pio_sm_config_xfer_args args;
        memset(&args, 0, sizeof(args));
        args.sm = (uint16_t)sm;
        args.dir = RP1_PIO_DIR_TO_SM;
        args.buf_size = (uint16_t)dma_buffer_size;
        args.buf_count = (uint16_t)dma_buffer_count;
        errno = 0;
        config_xfer_result = ioctl(handle->ioctl_fd, PIO_IOC_SM_CONFIG_XFER, &args);
    } else {
        struct rp1_pio_sm_config_xfer32_args args;
        memset(&args, 0, sizeof(args));
        args.sm = (uint16_t)sm;
        args.dir = RP1_PIO_DIR_TO_SM;
        args.buf_size = dma_buffer_size;
        args.buf_count = dma_buffer_count;
        errno = 0;
        config_xfer_result = ioctl(handle->ioctl_fd, PIO_IOC_SM_CONFIG_XFER32, &args);
    }
    if (config_xfer_result < 0) {
        int saved_errno = errno;
        heart_pi5_pio_scan_release(handle);
        snprintf(
            error_buf,
            error_buf_len,
            "Failed to configure Pi 5 scan DMA transfer buffers (code=%d, errno=%d, size=%u, count=%u).",
            config_xfer_result,
            saved_errno,
            dma_buffer_size,
            dma_buffer_count
        );
        return -9;
    }
    pio_sm_set_enabled(pio, (uint)sm, true);
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

    pio_select(handle->pio);
    int transfer_result;
    /*
     * The whole packed frame is submitted with a single ioctl. This keeps the
     * transport cost easy to compare against the resident-loop backend: one
     * submit to hand the buffer to rp1-pio, one wait to block until the TX path
     * drains the frame.
     *
     * Nothing in this shim re-chunks the frame. If the packed payload is
     * 43,936 words, that exact byte range is what rp1-pio sees here.
     */
    if (data_bytes <= UINT16_MAX) {
        struct rp1_pio_sm_xfer_data_args args;
        memset(&args, 0, sizeof(args));
        args.sm = (uint16_t)handle->sm;
        args.dir = RP1_PIO_DIR_TO_SM;
        args.data_bytes = (uint16_t)data_bytes;
        args.data = (void *)data;
        errno = 0;
        transfer_result = ioctl(handle->ioctl_fd, PIO_IOC_SM_XFER_DATA, &args);
    } else {
        struct rp1_pio_sm_xfer_data32_args args;
        memset(&args, 0, sizeof(args));
        args.sm = (uint16_t)handle->sm;
        args.dir = RP1_PIO_DIR_TO_SM;
        args.data_bytes = data_bytes;
        args.data = (void *)data;
        errno = 0;
        transfer_result = ioctl(handle->ioctl_fd, PIO_IOC_SM_XFER_DATA32, &args);
    }
    if (transfer_result < 0) {
        int saved_errno = errno;
        snprintf(
            error_buf,
            error_buf_len,
            "PIO scan DMA transfer submission failed (code=%d, errno=%d, bytes=%u).",
            transfer_result,
            saved_errno,
            data_bytes
        );
        return -2;
    }
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

    /*
     * The rp1-pio UAPI does not expose a DMA-channel handle we can wait on
     * directly, so draining the TX path is the only completion primitive
     * available here. That means "wait complete" is defined as "the state
     * machine has consumed all submitted TX data", not as a separate IRQ from a
     * host-visible DMA engine.
     */
    struct rp1_pio_sm_clear_fifos_args drain_args;
    memset(&drain_args, 0, sizeof(drain_args));
    drain_args.sm = (uint16_t)handle->sm;
    errno = 0;
    int drain_result = ioctl(handle->ioctl_fd, PIO_IOC_SM_DRAIN_TX, &drain_args);
    if (drain_result < 0) {
        int saved_errno = errno;
        snprintf(
            error_buf,
            error_buf_len,
            "PIO scan DMA drain failed (code=%d, errno=%d).",
            drain_result,
            saved_errno
        );
        return -2;
    }

    heart_pi5_pio_scan_write_error(error_buf, error_buf_len, "");
    return 0;
}

void heart_pi5_pio_scan_close(struct heart_pi5_pio_scan_handle *handle) {
    heart_pi5_pio_scan_release(handle);
}
