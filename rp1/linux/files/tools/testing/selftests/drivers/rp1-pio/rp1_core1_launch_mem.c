/*
 * Load and start an RP1 core1 payload using only the host-visible RP1 MMIO
 * window and the RP1 core1 boot registers.  The optional firmware callback
 * probe is diagnostic only; payload start is determined from the payload
 * status word, not from the callback count.
 * This deliberately does not touch /dev/pio0, PIO ioctls, or PIO state
 * machines.
 */

#include <errno.h>
#include <fcntl.h>
#include <stdbool.h>
#include <stdint.h>
#include <stdio.h>
#include <stdlib.h>
#include <sys/mman.h>
#include <unistd.h>

#define RP1_HOST_BASE		0x1f00000000ULL
#define RP1_HOST_SIZE		0x10000000ULL
#define RP1_PERI_BASE		0x40000000U
#define RP1_SRAM_BASE		0x20000000U
#define RP1_SRAM_HOST_OFF	0x00400000U

#define RP1_SYSCFG_BASE		0x40008000U
#define RP1_SYSCFG_PROC_EVENTS	0x00000008U
#define RP1_SYSCFG_FW_EVENT	BIT(0)

#define RP1_RESETS_BASE		0x40014000U
#define RP1_RESETS_SET		0x2000U
#define RP1_RESETS_CLR		0x3000U
#define RP1_CORE1_RESET	BIT(31)

#define RP1_BOOT_SP		0x4015401cU
#define RP1_BOOT_PC		0x40154014U
#define RP1_BOOT_MAGIC		0x4015400cU
#define RP1_BOOT_PC_XOR		0x4ff83f2dU
#define RP1_BOOT_MAGIC_VALUE	0xb007c0deU

#define RP1_HW_SET_BITS		0x2000U
#define RP1_HW_CLR_BITS		0x3000U

#define DEFAULT_LAUNCH_ADDR	0x20007000U
#define DEFAULT_PAYLOAD_ADDR	0x20008000U
#define RP1_LOCAL_SRAM_BASE	0x10000000U
#define RP1_LOCAL_SRAM_END	0x10004000U
#define RP1_SHARED_SRAM_END	0x20010000U
#define DEFAULT_LAUNCH_FILE	"rp1_core1_launch_fwcall.bin"
#define DEFAULT_HOOK_ADDR	0x2000012cU
#define DEFAULT_HOOK_ORIG	0x20000ac5U
#define DEFAULT_HOOK_PATCH	0x20007001U
#define LAUNCH_COUNT_ADDR	0x20007020U
#define PAYLOAD_STATUS_ADDR	0x200080f0U
#define RP1_FW_SHMEM_ADDR	0x2000ff00U
#define RP1_FW_SHMEM_SIZE	0x100U
#define RP1_FW_FEATURE_TABLE	0x20005928U
#define RP1_FW_HOOK_FOURCC	0x52315354U
#define RP1_FW_HOOK_OP_BASE	3U
#define RP1_FW_HOOK_OP_COUNT	1U

#define RP1_FW_GET_VERSION	0x0001U
#define RP1_FW_GET_FEATURE	0x0002U
#define RP1_FOURCC_PIO		0x50494f20U
#define RP1_FOURCC_PIO_LE	0x204f4950U
#define RP1_FW_READ_HW		32U

#ifndef BIT
#define BIT(n)			(1U << (n))
#endif

static uint8_t *rp1;
static uint16_t pio_op_base;

static volatile uint32_t *rp1_peri32(uint32_t addr)
{
	return (volatile uint32_t *)(rp1 + addr - RP1_PERI_BASE);
}

static volatile uint32_t *rp1_sram32(uint32_t addr)
{
	return (volatile uint32_t *)(rp1 + addr - RP1_SRAM_BASE + RP1_SRAM_HOST_OFF);
}

static uint32_t read_sram32(uint32_t addr)
{
	return *rp1_sram32(addr);
}

static uint32_t read_peri32(uint32_t addr)
{
	return *rp1_peri32(addr);
}

static void write_peri32(uint32_t addr, uint32_t value)
{
	*rp1_peri32(addr) = value;
}

static void write_sram32(uint32_t addr, uint32_t value)
{
	*rp1_sram32(addr) = value;
}

static void ring_fw_doorbell(void)
{
	write_peri32(RP1_SYSCFG_BASE + RP1_SYSCFG_PROC_EVENTS +
		     RP1_HW_SET_BITS, RP1_SYSCFG_FW_EVENT);
}

static void map_rp1(void)
{
	int fd = open("/dev/mem", O_RDWR | O_SYNC);

	if (fd < 0) {
		perror("/dev/mem");
		exit(1);
	}

	rp1 = mmap(NULL, RP1_HOST_SIZE, PROT_READ | PROT_WRITE, MAP_SHARED, fd,
		   RP1_HOST_BASE);
	close(fd);
	if (rp1 == MAP_FAILED) {
		perror("mmap RP1");
		exit(1);
	}
}

static void load_file(const char *path, uint32_t addr)
{
	FILE *f = fopen(path, "rb");

	if (!f) {
		perror(path);
		exit(1);
	}

	for (;;) {
		uint32_t value = 0;
		size_t n = fread(&value, 1, sizeof(value), f);

		if (!n)
			break;
		write_sram32(addr, value);
		addr += sizeof(value);
		if (n != sizeof(value))
			break;
	}

	if (ferror(f)) {
		perror(path);
		fclose(f);
		exit(1);
	}

	fclose(f);
}

static bool valid_core1_vector(uint32_t payload_addr, uint32_t sp, uint32_t pc)
{
	if (!sp || !pc || !(pc & 1U))
		return false;
	if (sp < RP1_LOCAL_SRAM_BASE || sp > RP1_LOCAL_SRAM_END)
		return false;

	/* Payloads either start from shared SRAM or branch into local ISRAM. */
	pc &= ~1U;
	if (pc >= RP1_LOCAL_SRAM_BASE && pc < RP1_LOCAL_SRAM_END)
		return true;
	if (pc >= payload_addr && pc < RP1_SHARED_SRAM_END)
		return true;

	return false;
}

static int fw_message(uint16_t op, const uint32_t *data, unsigned int data_len,
		      uint32_t *resp, unsigned int resp_space)
{
	uint32_t hdr = ((uint32_t)op << 16) | data_len;
	uint32_t rc;

	if (data_len + sizeof(uint32_t) > RP1_FW_SHMEM_SIZE)
		return -EINVAL;

	for (unsigned int i = 0; i < data_len / sizeof(uint32_t); i++)
		write_sram32(RP1_FW_SHMEM_ADDR + sizeof(uint32_t) * (i + 1),
			     data ? data[i] : 0);

	write_sram32(RP1_FW_SHMEM_ADDR, hdr);
	__sync_synchronize();
	ring_fw_doorbell();

	for (unsigned int i = 0; i < 1000; i++) {
		rc = read_sram32(RP1_FW_SHMEM_ADDR);
		if (rc != hdr)
			goto done;
		usleep(1000);
	}

	return -ETIMEDOUT;

done:
	if (rc & 0x80000000U)
		return (int32_t)rc;

	if (resp && resp_space) {
		unsigned int ret = rc < resp_space ? rc : resp_space;

		for (unsigned int i = 0; i < ret / sizeof(uint32_t); i++)
			resp[i] = read_sram32(RP1_FW_SHMEM_ADDR +
					      sizeof(uint32_t) * (i + 1));
	}

	return rc;
}

static int fw_get_pio_base(void)
{
	uint32_t candidates[] = {
		RP1_FOURCC_PIO,
		RP1_FOURCC_PIO_LE,
	};
	uint32_t resp[2] = {};
	int last_ret = -EOPNOTSUPP;

	for (unsigned int i = 0; i < sizeof(candidates) / sizeof(candidates[0]); i++) {
		uint32_t data = candidates[i];
		int ret;

		resp[0] = 0;
		resp[1] = 0;
		ret = fw_message(RP1_FW_GET_FEATURE, &data, sizeof(data),
				 resp, sizeof(resp));
		printf("GET_FEATURE candidate=0x%08x ret=%d op_base=0x%08x op_count=%u\n",
		       data, ret, resp[0], resp[1]);
		if (ret >= (int)sizeof(resp) && resp[0]) {
			pio_op_base = resp[0];
			printf("firmware PIO feature base=%u count=%u\n",
			       resp[0], resp[1]);
			return 0;
		}
		last_ret = ret < 0 ? ret : -EOPNOTSUPP;
	}

	return last_ret;
}

static int fw_trigger_read_hw(void)
{
	uint32_t req[2] = { 0xf0000000U, 4U };
	uint32_t resp = 0;
	int ret;

	ret = fw_message(pio_op_base + RP1_FW_READ_HW, req, sizeof(req),
			 &resp, sizeof(resp));
	printf("direct firmware READ_HW ret=%d resp=0x%08x proc_events=0x%08x host_irq=0x%08x\n",
	       ret, resp,
	       read_peri32(RP1_SYSCFG_BASE + RP1_SYSCFG_PROC_EVENTS),
	       read_peri32(RP1_SYSCFG_BASE + 0x14));
	return ret;
}

static int fw_trigger_callback_hook(void)
{
	uint32_t saved[4];
	int ret;

	for (unsigned int i = 0; i < 4; i++)
		saved[i] = read_sram32(RP1_FW_FEATURE_TABLE +
				       i * sizeof(uint32_t));

	printf("feature table old fourcc=0x%08x count=%u fn=0x%08x base=%u\n",
	       saved[0], saved[1], saved[2], saved[3]);

	write_sram32(RP1_FW_FEATURE_TABLE + 0, RP1_FW_HOOK_FOURCC);
	write_sram32(RP1_FW_FEATURE_TABLE + 4, RP1_FW_HOOK_OP_COUNT);
	write_sram32(RP1_FW_FEATURE_TABLE + 8, DEFAULT_LAUNCH_ADDR | 1U);
	write_sram32(RP1_FW_FEATURE_TABLE + 12, RP1_FW_HOOK_OP_BASE);
	__sync_synchronize();

	ret = fw_message(RP1_FW_HOOK_OP_BASE, NULL, 0, NULL, 0);

	for (unsigned int i = 0; i < 4; i++)
		write_sram32(RP1_FW_FEATURE_TABLE + i * sizeof(uint32_t),
			     saved[i]);
	__sync_synchronize();

	printf("direct firmware callback hook ret=%d proc_events=0x%08x host_irq=0x%08x\n",
	       ret,
	       read_peri32(RP1_SYSCFG_BASE + RP1_SYSCFG_PROC_EVENTS),
	       read_peri32(RP1_SYSCFG_BASE + 0x14));

	return ret;
}

static void usage(const char *prog)
{
	fprintf(stderr,
		"usage: %s [-n] [-P] [-a payload_addr] [-l launch.bin] payload.bin\n"
		"  -n  dry-run: load payload and validate vector, but do not release core1\n"
		"  -P  use legacy direct PIO-feature READ_HW trigger\n",
		prog);
}

int main(int argc, char **argv)
{
	uint32_t payload_addr = DEFAULT_PAYLOAD_ADDR;
	const char *launch = DEFAULT_LAUNCH_FILE;
	const char *payload = NULL;
	uint32_t initial_sp;
	uint32_t initial_pc;
	uint32_t old;
	int dry_run = 0;
	int legacy_pio_trigger = 0;
	int no_legacy_status = getenv("RP1_CORE1_LAUNCH_NO_LEGACY_STATUS") != NULL;
	int opt;

	while ((opt = getopt(argc, argv, "nPa:l:")) != -1) {
		switch (opt) {
		case 'n':
			dry_run = 1;
			break;
		case 'P':
			legacy_pio_trigger = 1;
			break;
		case 'a':
			payload_addr = strtoul(optarg, NULL, 0);
			break;
		case 'l':
			launch = optarg;
			break;
		default:
			usage(argv[0]);
			return 2;
		}
	}

	if (optind + 1 != argc) {
		usage(argv[0]);
		return 2;
	}
	payload = argv[optind];

	map_rp1();
	if (legacy_pio_trigger && fw_get_pio_base() < 0)
		return 5;

	write_peri32(RP1_RESETS_BASE | RP1_RESETS_SET, RP1_CORE1_RESET);
	usleep(100000);

	load_file(launch, DEFAULT_LAUNCH_ADDR);
	load_file(payload, payload_addr);
	write_sram32(LAUNCH_COUNT_ADDR, 0);
	if (!no_legacy_status)
		write_sram32(PAYLOAD_STATUS_ADDR, 0);
	initial_sp = read_sram32(payload_addr);
	initial_pc = read_sram32(payload_addr + sizeof(uint32_t));

	printf("loading %s to 0x%08x and starting core1 pc=0x%08x sp=0x%08x\n",
	       payload, payload_addr, initial_pc, initial_sp);
	if (!valid_core1_vector(payload_addr, initial_sp, initial_pc)) {
		fprintf(stderr,
			"refusing to start core1: invalid payload vector pc=0x%08x sp=0x%08x after SRAM load\n",
			initial_pc, initial_sp);
		fprintf(stderr,
			"this usually means RP1 shared SRAM state is corrupted or unavailable; manually power cycle before retrying\n");
		return 6;
	}
	if (dry_run) {
		printf("dry-run payload vector valid pc=0x%08x sp=0x%08x; core1 remains in reset\n",
		       initial_pc, initial_sp);
		return 0;
	}

	write_peri32(RP1_BOOT_SP, initial_sp);
	write_peri32(RP1_BOOT_PC, initial_pc ^ RP1_BOOT_PC_XOR);
	write_peri32(RP1_BOOT_MAGIC, RP1_BOOT_MAGIC_VALUE);
	write_peri32(RP1_RESETS_BASE | RP1_RESETS_CLR, RP1_CORE1_RESET);
	usleep(100000);

	if (legacy_pio_trigger) {
		old = read_sram32(DEFAULT_HOOK_ADDR);
		printf("hook old 0x%08x at 0x%08x\n", old, DEFAULT_HOOK_ADDR);
		if (old != DEFAULT_HOOK_ORIG) {
			fprintf(stderr, "not patching: expected 0x%08x\n",
				DEFAULT_HOOK_ORIG);
			return 3;
		}
		write_sram32(DEFAULT_HOOK_ADDR, DEFAULT_HOOK_PATCH);
		fw_trigger_read_hw();
	} else {
		fw_trigger_callback_hook();
	}
	if (no_legacy_status) {
		printf("no-pio payload launched without legacy 0x80f0 status polling hook_now=0x%08x\n",
		       read_sram32(DEFAULT_HOOK_ADDR));
		return 0;
	}
	for (unsigned int i = 0; i < 200; i++) {
		uint32_t count = read_sram32(LAUNCH_COUNT_ADDR);
		uint32_t status = read_sram32(PAYLOAD_STATUS_ADDR);

		if (count || status) {
			printf("no-pio payload started callback_count=%u status=0x%08x hook_now=0x%08x\n",
			       count, status, read_sram32(DEFAULT_HOOK_ADDR));
			return 0;
		}
		usleep(10000);
	}

	write_sram32(DEFAULT_HOOK_ADDR, DEFAULT_HOOK_ORIG);
	fprintf(stderr,
		"no-pio payload did not start; restored hook/table callback_count=%u status=0x%08x\n",
		read_sram32(LAUNCH_COUNT_ADDR), read_sram32(PAYLOAD_STATUS_ADDR));
	return 4;
}
