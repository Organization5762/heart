// SPDX-License-Identifier: GPL-2.0
#define _GNU_SOURCE

#include <errno.h>
#include <fcntl.h>
#include <signal.h>
#include <stdint.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <sys/mman.h>
#include <time.h>
#include <unistd.h>

#define RP1_GPIO_BASE 0x1f000d0000ULL
#define RP1_GPIO_MAP_SIZE 0x40000U
#define GPIO_FUNC_SYS_RIO 5U
#define PAD_FAST_DRIVE 0x15U
#define PAD_SLOW_DRIVE 0x01U

#define GPIO_CTRL_WORDS 0x00000U / 4U
#define RIO_WORDS 0x10000U / 4U
#define RIO_SET_WORDS (0x10000U + 0x2000U) / 4U
#define RIO_CLR_WORDS (0x10000U + 0x3000U) / 4U
#define PAD_WORDS 0x20000U / 4U

#define GPIO_CLK 17U
#define GPIO_LAT 4U
#define GPIO_OE 18U
#define GPIO_A 22U
#define GPIO_B 23U
#define GPIO_C 24U
#define GPIO_D 25U
#define GPIO_E 15U
#define GPIO_P0_B1 7U
#define GPIO_P0_B2 10U
#define GPIO_P1_B1 6U
#define GPIO_P1_B2 20U
#define GPIO_P0_R1 11U
#define GPIO_P0_G1 27U
#define GPIO_P0_R2 8U
#define GPIO_P0_G2 9U
#define GPIO_P1_R1 12U
#define GPIO_P1_G1 5U
#define GPIO_P1_R2 19U
#define GPIO_P1_G2 13U

#define PIN(_gpio) (1U << (_gpio))
#define ROW_COUNT 32U
#define COL_COUNT 128U

struct gpio_ctrl_regs {
	uint32_t status;
	uint32_t ctrl;
};

struct rio_regs {
	uint32_t out;
	uint32_t oe;
	uint32_t in;
	uint32_t in_sync;
};

static volatile sig_atomic_t keep_running = 1;
static volatile uint32_t *map_base;
static volatile struct gpio_ctrl_regs *gpio_regs;
static volatile uint32_t *pad_regs;
static volatile struct rio_regs *rio_out;
static volatile struct rio_regs *rio_set;
static volatile struct rio_regs *rio_clr;
static unsigned int clock_nops = 1;
static unsigned int dwell_ns = 50000;
static uint32_t color_mask;

static void handle_signal(int sig)
{
	(void)sig;
	keep_running = 0;
}

static void store_barrier(void)
{
#if defined(__arm__) || defined(__aarch64__)
	asm volatile("dmb ishst" ::: "memory");
#endif
}

static void delay_nops(unsigned int count)
{
	for (unsigned int i = 0; i < count; i++)
		asm volatile("nop; nop" ::: "memory");
}

static void delay_ns(unsigned int ns)
{
	struct timespec ts = {
		.tv_sec = ns / 1000000000U,
		.tv_nsec = ns % 1000000000U,
	};

	if (ns)
		nanosleep(&ts, NULL);
}

static void map_rio(void)
{
	int fd = open("/dev/mem", O_RDWR | O_SYNC);
	void *mapped;

	if (fd < 0) {
		perror("/dev/mem");
		exit(1);
	}
	mapped = mmap(NULL, RP1_GPIO_MAP_SIZE, PROT_READ | PROT_WRITE,
		      MAP_SHARED, fd, RP1_GPIO_BASE);
	close(fd);
	if (mapped == MAP_FAILED) {
		perror("mmap RP1 RIO");
		exit(1);
	}

	map_base = mapped;
	gpio_regs = (volatile struct gpio_ctrl_regs *)(map_base + GPIO_CTRL_WORDS);
	pad_regs = map_base + PAD_WORDS + 1;
	rio_out = (volatile struct rio_regs *)(map_base + RIO_WORDS);
	rio_set = (volatile struct rio_regs *)(map_base + RIO_SET_WORDS);
	rio_clr = (volatile struct rio_regs *)(map_base + RIO_CLR_WORDS);
}

static uint32_t row_bits(unsigned int row)
{
	uint32_t bits = 0;

	if (row & 1U)
		bits |= PIN(GPIO_A);
	if (row & 2U)
		bits |= PIN(GPIO_B);
	if (row & 4U)
		bits |= PIN(GPIO_C);
	if (row & 8U)
		bits |= PIN(GPIO_D);
	if (row & 16U)
		bits |= PIN(GPIO_E);
	return bits;
}

static void configure_pins(uint32_t used_mask)
{
	for (unsigned int pin = 0; pin < 28; pin++) {
		uint32_t bit = PIN(pin);

		if (!(used_mask & bit))
			continue;
		gpio_regs[pin].ctrl = GPIO_FUNC_SYS_RIO;
		pad_regs[pin] = (pin == GPIO_CLK || pin == GPIO_LAT) ?
				PAD_SLOW_DRIVE : PAD_FAST_DRIVE;
		rio_set->oe = bit;
	}
	store_barrier();
	rio_out->out = PIN(GPIO_OE);
}

static void clock_word(uint32_t pins)
{
	rio_out->out = pins;
	delay_nops(clock_nops);
	rio_out->out = pins | PIN(GPIO_CLK);
	delay_nops(clock_nops);
	rio_out->out = pins;
}

static void render_row(unsigned int row)
{
	uint32_t addr = row_bits(row);
	uint32_t shift_pins = addr | color_mask | PIN(GPIO_OE);

	rio_out->out = addr | PIN(GPIO_OE);
	for (unsigned int col = 0; col < COL_COUNT; col++)
		clock_word(shift_pins);

	rio_out->out = addr | PIN(GPIO_OE) | PIN(GPIO_LAT);
	delay_nops(clock_nops);
	rio_out->out = addr | PIN(GPIO_OE);
	delay_nops(clock_nops);
	rio_out->out = addr;
	delay_ns(dwell_ns);
	rio_out->out = addr | PIN(GPIO_OE);
}

int main(int argc, char **argv)
{
	uint32_t used_mask = PIN(GPIO_CLK) | PIN(GPIO_LAT) | PIN(GPIO_OE) |
			     PIN(GPIO_A) | PIN(GPIO_B) | PIN(GPIO_C) |
			     PIN(GPIO_D) | PIN(GPIO_E) | PIN(GPIO_P0_B1) |
			     PIN(GPIO_P0_B2) | PIN(GPIO_P1_B1) |
			     PIN(GPIO_P1_B2) | PIN(GPIO_P0_R1) |
			     PIN(GPIO_P0_G1) | PIN(GPIO_P0_R2) |
			     PIN(GPIO_P0_G2) | PIN(GPIO_P1_R1) |
			     PIN(GPIO_P1_G1) | PIN(GPIO_P1_R2) |
			     PIN(GPIO_P1_G2);
	uint64_t frames = 0;
	time_t last = time(NULL);
	const char *mask_name = argc > 3 ? argv[3] : "blue";

	if (argc > 1)
		dwell_ns = strtoul(argv[1], NULL, 0);
	if (argc > 2)
		clock_nops = strtoul(argv[2], NULL, 0);
	if (argc > 4) {
		fprintf(stderr, "usage: %s [row_dwell_ns] [clock_nops] [mask]\n",
			argv[0]);
		return 2;
	}
	if (!strcmp(mask_name, "blue")) {
		color_mask = PIN(GPIO_P0_B1) | PIN(GPIO_P0_B2) |
			     PIN(GPIO_P1_B1) | PIN(GPIO_P1_B2);
	} else if (!strcmp(mask_name, "p0-top-blue")) {
		color_mask = PIN(GPIO_P0_B1);
	} else if (!strcmp(mask_name, "p0-bottom-blue")) {
		color_mask = PIN(GPIO_P0_B2);
	} else if (!strcmp(mask_name, "p1-top-blue")) {
		color_mask = PIN(GPIO_P1_B1);
	} else if (!strcmp(mask_name, "p1-bottom-blue")) {
		color_mask = PIN(GPIO_P1_B2);
	} else if (!strcmp(mask_name, "red")) {
		color_mask = PIN(GPIO_P0_R1) | PIN(GPIO_P0_R2) |
			     PIN(GPIO_P1_R1) | PIN(GPIO_P1_R2);
	} else if (!strcmp(mask_name, "green")) {
		color_mask = PIN(GPIO_P0_G1) | PIN(GPIO_P0_G2) |
			     PIN(GPIO_P1_G1) | PIN(GPIO_P1_G2);
	} else {
		color_mask = strtoul(mask_name, NULL, 0);
	}

	signal(SIGINT, handle_signal);
	signal(SIGTERM, handle_signal);
	map_rio();
	configure_pins(used_mask);
	printf("heart RIO static regular mask=%s color_mask=0x%08x dwell_ns=%u clock_nops=%u\n",
	       mask_name, color_mask, dwell_ns, clock_nops);
	fflush(stdout);

	while (keep_running) {
		for (unsigned int row = 0; row < ROW_COUNT; row++)
			render_row(row);
		frames++;
		if (time(NULL) != last) {
			printf("frames=%llu\n", (unsigned long long)frames);
			fflush(stdout);
			last = time(NULL);
		}
	}

	rio_out->out = PIN(GPIO_OE);
	store_barrier();
	rio_clr->oe = used_mask;
	munmap((void *)map_base, RP1_GPIO_MAP_SIZE);
	return 0;
}
