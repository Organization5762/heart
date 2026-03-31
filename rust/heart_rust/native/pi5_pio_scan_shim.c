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

#define HEART_PI5_PIO_SCAN_DEVICE "/dev/pio0"
#define HEART_PI5_PIO_SCAN_MAX_TRANSFER_BYTES 65532u
#define HEART_PI5_PIO_SCAN_PROGRAM_LENGTH 9
#define HEART_PI5_PIO_SCAN_OUTPUT_PIN_BASE 0u
#define HEART_PI5_PIO_SCAN_OUTPUT_PIN_COUNT 28u
#define HEART_PI5_PIO_SCAN_WORD_PIN_COUNT 32u

struct heart_pi5_pio_scan_handle {
    PIO pio;
    int sm;
    int ioctl_fd;
    uint32_t oe_gpio;
    uint32_t lat_gpio;
    uint32_t clock_gpio;
    uint32_t dma_buffer_size;
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
    handle->dma_buffer_size = dma_buffer_size;
    handle->instructions[0] = (uint16_t)pio_encode_out(pio_x, 1);
    handle->instructions[1] = (uint16_t)pio_encode_out(pio_y, 31);
    handle->instructions[2] = (uint16_t)pio_encode_jmp_not_x(6);
    handle->instructions[3] = (uint16_t)(pio_encode_out(pio_pins, HEART_PI5_PIO_SCAN_WORD_PIN_COUNT) | pio_encode_sideset_opt(1, 0));
    handle->instructions[4] = (uint16_t)(pio_encode_jmp_y_dec(3) | pio_encode_sideset_opt(1, 1));
    handle->instructions[5] = (uint16_t)pio_encode_jmp(0);
    handle->instructions[6] = (uint16_t)(pio_encode_out(pio_pins, HEART_PI5_PIO_SCAN_WORD_PIN_COUNT) | pio_encode_sideset_opt(1, 0));
    handle->instructions[7] = (uint16_t)pio_encode_jmp_y_dec(6);
    handle->instructions[8] = (uint16_t)pio_encode_jmp(0);
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
    sm_config_set_sideset(&config, 2, true, false);
    sm_config_set_out_shift(&config, false, true, 32);
    sm_config_set_fifo_join(&config, PIO_FIFO_JOIN_TX);
    sm_config_set_clkdiv(&config, clock_divider);
    sm_config_set_out_pins(&config, HEART_PI5_PIO_SCAN_OUTPUT_PIN_BASE, HEART_PI5_PIO_SCAN_OUTPUT_PIN_COUNT);
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

int heart_pi5_pio_scan_stream(
    struct heart_pi5_pio_scan_handle *handle,
    const uint8_t *data,
    uint32_t data_bytes,
    char *error_buf,
    size_t error_buf_len
) {
    uint32_t remaining_bytes;
    const uint8_t *cursor;

    if (handle == NULL || data == NULL) {
        heart_pi5_pio_scan_write_error(error_buf, error_buf_len, "PIO scan transport handle and data are required.");
        return -1;
    }

    pio_select(handle->pio);
    remaining_bytes = data_bytes;
    cursor = data;
    while (remaining_bytes > 0) {
        uint32_t transfer_bytes = remaining_bytes;
        uint32_t max_transfer_bytes = handle->dma_buffer_size;
        if (max_transfer_bytes > HEART_PI5_PIO_SCAN_MAX_TRANSFER_BYTES) {
            max_transfer_bytes = HEART_PI5_PIO_SCAN_MAX_TRANSFER_BYTES;
        }
        if (transfer_bytes > max_transfer_bytes) {
            transfer_bytes = max_transfer_bytes;
        }
        int transfer_result;
        if (transfer_bytes <= UINT16_MAX) {
            struct rp1_pio_sm_xfer_data_args args;
            memset(&args, 0, sizeof(args));
            args.sm = (uint16_t)handle->sm;
            args.dir = RP1_PIO_DIR_TO_SM;
            args.data_bytes = (uint16_t)transfer_bytes;
            args.data = (void *)cursor;
            errno = 0;
            transfer_result = ioctl(handle->ioctl_fd, PIO_IOC_SM_XFER_DATA, &args);
        } else {
            struct rp1_pio_sm_xfer_data32_args args;
            memset(&args, 0, sizeof(args));
            args.sm = (uint16_t)handle->sm;
            args.dir = RP1_PIO_DIR_TO_SM;
            args.data_bytes = transfer_bytes;
            args.data = (void *)cursor;
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
                transfer_bytes
            );
            return -2;
        }
        struct rp1_pio_sm_clear_fifos_args drain_args;
        memset(&drain_args, 0, sizeof(drain_args));
        drain_args.sm = (uint16_t)handle->sm;
        ioctl(handle->ioctl_fd, PIO_IOC_SM_DRAIN_TX, &drain_args);
        remaining_bytes -= transfer_bytes;
        cursor += transfer_bytes;
    }
    heart_pi5_pio_scan_write_error(error_buf, error_buf_len, "");
    return 0;
}

void heart_pi5_pio_scan_close(struct heart_pi5_pio_scan_handle *handle) {
    heart_pi5_pio_scan_release(handle);
}
