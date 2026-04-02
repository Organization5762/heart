#include <stdbool.h>
#include <stdint.h>
#include <piolib/piolib.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>

#define HEART_PI5_PIO_HELLO_FIFO_PROGRAM_LENGTH 4
#define HEART_PI5_PIO_HELLO_AUTOBLINK_PROGRAM_LENGTH 3

enum heart_pi5_pio_hello_mode {
    HEART_PI5_PIO_HELLO_MODE_FIFO = 0,
    HEART_PI5_PIO_HELLO_MODE_AUTOBLINK = 1,
};

struct heart_pi5_pio_hello_handle {
    PIO pio;
    int sm;
    uint pin;
    enum heart_pi5_pio_hello_mode mode;
    uint program_offset;
    uint16_t instructions[HEART_PI5_PIO_HELLO_FIFO_PROGRAM_LENGTH];
    pio_program_t program;
};

static void heart_pi5_pio_hello_write_error(char *error_buf, size_t error_buf_len, const char *message) {
    if (error_buf == NULL || error_buf_len == 0) {
        return;
    }
    snprintf(error_buf, error_buf_len, "%s", message);
}

static void heart_pi5_pio_hello_release(struct heart_pi5_pio_hello_handle *handle) {
    if (handle == NULL) {
        return;
    }

    pio_sm_set_enabled(handle->pio, (uint)handle->sm, false);
    pio_sm_unclaim(handle->pio, (uint)handle->sm);
    pio_remove_program(handle->pio, &handle->program, handle->program_offset);
    pio_close(handle->pio);
    free(handle);
}

int heart_pi5_pio_hello_open(
    uint32_t gpio,
    float clock_divider,
    uint32_t mode,
    struct heart_pi5_pio_hello_handle **out_handle,
    char *error_buf,
    size_t error_buf_len
) {
    struct heart_pi5_pio_hello_handle *handle;
    pio_sm_config config;
    PIO pio;
    int sm;

    if (out_handle == NULL) {
        heart_pi5_pio_hello_write_error(error_buf, error_buf_len, "Output handle pointer is required.");
        return -1;
    }
    *out_handle = NULL;

    if (pio_init() < 0) {
        heart_pi5_pio_hello_write_error(error_buf, error_buf_len, "pio_init failed.");
        return -2;
    }

    pio = pio_open(0);
    if (PIO_IS_ERR(pio)) {
        heart_pi5_pio_hello_write_error(error_buf, error_buf_len, "pio_open(0) failed.");
        return -3;
    }

    sm = pio_claim_unused_sm(pio, true);
    if (sm < 0) {
        pio_close(pio);
        heart_pi5_pio_hello_write_error(error_buf, error_buf_len, "No free Pi 5 PIO state machine was available.");
        return -4;
    }

    handle = calloc(1, sizeof(*handle));
    if (handle == NULL) {
        pio_sm_unclaim(pio, (uint)sm);
        pio_close(pio);
        heart_pi5_pio_hello_write_error(error_buf, error_buf_len, "Failed to allocate Pi 5 hello PIO handle.");
        return -5;
    }

    handle->pio = pio;
    handle->sm = sm;
    handle->pin = (uint)gpio;
    handle->mode = mode == HEART_PI5_PIO_HELLO_MODE_AUTOBLINK
        ? HEART_PI5_PIO_HELLO_MODE_AUTOBLINK
        : HEART_PI5_PIO_HELLO_MODE_FIFO;

    if (handle->mode == HEART_PI5_PIO_HELLO_MODE_AUTOBLINK) {
        handle->instructions[0] = (uint16_t)(pio_encode_set(pio_pins, 1) | pio_encode_delay(31));
        handle->instructions[1] = (uint16_t)(pio_encode_set(pio_pins, 0) | pio_encode_delay(31));
        handle->instructions[2] = (uint16_t)pio_encode_jmp(0);
        handle->program.length = HEART_PI5_PIO_HELLO_AUTOBLINK_PROGRAM_LENGTH;
    } else {
        handle->instructions[0] = (uint16_t)pio_encode_pull(false, true);
        handle->instructions[1] = (uint16_t)pio_encode_out(pio_x, 1);
        handle->instructions[2] = (uint16_t)pio_encode_mov(pio_pins, pio_x);
        handle->instructions[3] = (uint16_t)pio_encode_jmp(0);
        handle->program.length = HEART_PI5_PIO_HELLO_FIFO_PROGRAM_LENGTH;
    }
    handle->program.instructions = handle->instructions;
    handle->program.origin = -1;
    handle->program.pio_version = 0;

    pio_select(pio);
    if (!pio_can_add_program(pio, &handle->program)) {
        pio_clear_instruction_memory(pio);
        pio_clear_error(pio);
    }
    handle->program_offset = pio_add_program(pio, &handle->program);
    if (pio_get_error(pio)) {
        heart_pi5_pio_hello_release(handle);
        heart_pi5_pio_hello_write_error(error_buf, error_buf_len, "Failed to load the Pi 5 hello PIO program.");
        return -6;
    }

    config = pio_get_default_sm_config();
    sm_config_set_wrap(&config, handle->program_offset, handle->program_offset + handle->program.length - 1);
    sm_config_set_out_shift(&config, true, false, 1);
    sm_config_set_out_pins(&config, handle->pin, 1);
    sm_config_set_set_pins(&config, handle->pin, 1);
    sm_config_set_clkdiv(&config, clock_divider);
    pio_gpio_init(pio, handle->pin);
    pio_sm_set_consecutive_pindirs(pio, (uint)sm, handle->pin, 1, true);
    pio_sm_init(pio, (uint)sm, handle->program_offset, &config);
    pio_sm_set_enabled(pio, (uint)sm, true);

    *out_handle = handle;
    heart_pi5_pio_hello_write_error(error_buf, error_buf_len, "");
    return 0;
}

int heart_pi5_pio_hello_put(
    struct heart_pi5_pio_hello_handle *handle,
    uint32_t value,
    char *error_buf,
    size_t error_buf_len
) {
    if (handle == NULL) {
        heart_pi5_pio_hello_write_error(error_buf, error_buf_len, "Pi 5 hello PIO handle is required.");
        return -1;
    }
    if (handle->mode == HEART_PI5_PIO_HELLO_MODE_AUTOBLINK) {
        heart_pi5_pio_hello_write_error(error_buf, error_buf_len, "Autoblink mode does not accept FIFO writes.");
        return -2;
    }

    pio_sm_put_blocking(handle->pio, (uint)handle->sm, value & 1u);
    heart_pi5_pio_hello_write_error(error_buf, error_buf_len, "");
    return 0;
}

void heart_pi5_pio_hello_close(struct heart_pi5_pio_hello_handle *handle) {
    heart_pi5_pio_hello_release(handle);
}
