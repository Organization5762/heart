#include <piolib/piolib.h>

#include <stdbool.h>
#include <stdint.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>

#define HEART_PI5_PIO_PROGRAM_LENGTH 2

struct heart_pi5_pio_tx_handle {
    PIO pio;
    int sm;
    uint out_base_gpio;
    uint out_pin_count;
    uint clock_gpio;
    uint program_offset;
    uint16_t instructions[HEART_PI5_PIO_PROGRAM_LENGTH];
    pio_program_t program;
};

static void heart_pi5_pio_write_error(char *error_buf, size_t error_buf_len, const char *message) {
    if (error_buf == NULL || error_buf_len == 0) {
        return;
    }
    snprintf(error_buf, error_buf_len, "%s", message);
}

static void heart_pi5_pio_release(struct heart_pi5_pio_tx_handle *handle) {
    if (handle == NULL) {
        return;
    }

    pio_select(handle->pio);
    pio_sm_set_enabled(handle->pio, (uint)handle->sm, false);
    pio_sm_unclaim(handle->pio, (uint)handle->sm);
    pio_remove_program(handle->pio, &handle->program, handle->program_offset);

    for (uint pin = handle->out_base_gpio; pin < handle->out_base_gpio + handle->out_pin_count; ++pin) {
        gpio_set_function(pin, GPIO_FUNC_NULL);
    }
    gpio_set_function(handle->clock_gpio, GPIO_FUNC_NULL);
    pio_close(handle->pio);
    free(handle);
}

int heart_pi5_pio_tx_open(
    uint32_t out_base_gpio,
    uint32_t out_pin_count,
    uint32_t clock_gpio,
    float clock_divider,
    uint32_t dma_buffer_size,
    uint32_t dma_buffer_count,
    struct heart_pi5_pio_tx_handle **out_handle,
    char *error_buf,
    size_t error_buf_len
) {
    if (out_handle == NULL) {
        heart_pi5_pio_write_error(error_buf, error_buf_len, "Output handle pointer is required.");
        return -1;
    }
    *out_handle = NULL;
    if (out_pin_count == 0 || out_pin_count > 32) {
        heart_pi5_pio_write_error(error_buf, error_buf_len, "PIO transport requires 1-32 output pins.");
        return -2;
    }
    if (dma_buffer_size == 0 || dma_buffer_count == 0) {
        heart_pi5_pio_write_error(error_buf, error_buf_len, "PIO DMA transport requires non-zero buffer sizing.");
        return -3;
    }
    if (pio_init() < 0) {
        heart_pi5_pio_write_error(error_buf, error_buf_len, "pio_init failed.");
        return -4;
    }

    PIO pio = pio_open(0);
    if (PIO_IS_ERR(pio)) {
        heart_pi5_pio_write_error(error_buf, error_buf_len, "pio_open(0) failed.");
        return -5;
    }
    pio_select(pio);

    int sm = pio_claim_unused_sm(pio, true);
    if (sm < 0) {
        pio_close(pio);
        heart_pi5_pio_write_error(error_buf, error_buf_len, "No free Pi 5 PIO state machine was available.");
        return -6;
    }

    struct heart_pi5_pio_tx_handle *handle = calloc(1, sizeof(*handle));
    if (handle == NULL) {
        pio_sm_unclaim(pio, (uint)sm);
        pio_close(pio);
        heart_pi5_pio_write_error(error_buf, error_buf_len, "Failed to allocate Pi 5 PIO transport handle.");
        return -7;
    }

    handle->pio = pio;
    handle->sm = sm;
    handle->out_base_gpio = out_base_gpio;
    handle->out_pin_count = out_pin_count;
    handle->clock_gpio = clock_gpio;
    handle->instructions[0] =
        (uint16_t)(pio_encode_out(pio_pins, out_pin_count) | pio_encode_sideset(1, 0));
    handle->instructions[1] = (uint16_t)(pio_encode_nop() | pio_encode_sideset(1, 1));
    handle->program.instructions = handle->instructions;
    handle->program.length = HEART_PI5_PIO_PROGRAM_LENGTH;
    handle->program.origin = -1;
    handle->program.pio_version = 0;
    handle->program_offset = pio_add_program(pio, &handle->program);
    if (pio_get_error(pio)) {
        heart_pi5_pio_release(handle);
        heart_pi5_pio_write_error(error_buf, error_buf_len, "Failed to load the Pi 5 PIO transport program.");
        return -8;
    }

    for (uint pin = out_base_gpio; pin < out_base_gpio + out_pin_count; ++pin) {
        pio_gpio_init(pio, pin);
        gpio_set_function(pin, GPIO_FUNC_PIO0);
    }
    pio_gpio_init(pio, clock_gpio);
    gpio_set_function(clock_gpio, GPIO_FUNC_PIO0);

    pio_sm_config config = pio_get_default_sm_config();
    sm_config_set_out_pins(&config, out_base_gpio, out_pin_count);
    sm_config_set_sideset_pins(&config, clock_gpio);
    sm_config_set_sideset(&config, 1, false, false);
    sm_config_set_out_shift(&config, true, true, 32);
    sm_config_set_fifo_join(&config, PIO_FIFO_JOIN_TX);
    sm_config_set_clkdiv(&config, clock_divider);
    sm_config_set_wrap(
        &config,
        handle->program_offset,
        handle->program_offset + HEART_PI5_PIO_PROGRAM_LENGTH - 1
    );
    pio_sm_set_consecutive_pindirs(pio, (uint)sm, out_base_gpio, out_pin_count, true);
    pio_sm_set_consecutive_pindirs(pio, (uint)sm, clock_gpio, 1, true);
    pio_sm_init(pio, (uint)sm, handle->program_offset, &config);

    if (pio_sm_config_xfer(pio, (uint)sm, PIO_DIR_TO_SM, dma_buffer_size, dma_buffer_count) < 0) {
        heart_pi5_pio_release(handle);
        heart_pi5_pio_write_error(
            error_buf,
            error_buf_len,
            "Failed to configure Pi 5 PIO DMA transfer buffers."
        );
        return -9;
    }

    pio_sm_set_enabled(pio, (uint)sm, true);
    *out_handle = handle;
    heart_pi5_pio_write_error(error_buf, error_buf_len, "");
    return 0;
}

int heart_pi5_pio_tx_stream(
    struct heart_pi5_pio_tx_handle *handle,
    const uint8_t *data,
    uint32_t data_bytes,
    char *error_buf,
    size_t error_buf_len
) {
    if (handle == NULL || data == NULL) {
        heart_pi5_pio_write_error(error_buf, error_buf_len, "PIO transport handle and data are required.");
        return -1;
    }

    pio_select(handle->pio);
    if (pio_sm_xfer_data(handle->pio, (uint)handle->sm, PIO_DIR_TO_SM, data_bytes, (void *)data) < 0) {
        heart_pi5_pio_write_error(error_buf, error_buf_len, "PIO DMA transfer submission failed.");
        return -2;
    }
    pio_sm_drain_tx_fifo(handle->pio, (uint)handle->sm);
    heart_pi5_pio_write_error(error_buf, error_buf_len, "");
    return 0;
}

void heart_pi5_pio_tx_close(struct heart_pi5_pio_tx_handle *handle) {
    heart_pi5_pio_release(handle);
}
