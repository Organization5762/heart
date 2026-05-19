// SPDX-License-Identifier: GPL-2.0
/*
 * RP1 HUB75 frame packer.
 *
 * This driver converts RGB888 frames into full RP1 RIO output words or compact
 * row-major worker streams using a selected HUB75 GPIO mapping. RGB888
 * channels are expanded through the same 11-bit CIE1931 curve
 * used by hzeller/rpi-rgb-led-matrix so selected PWM planes have comparable
 * bit significance. A separate RP1-side worker can mmap the packed output
 * stream and drive the GPIO timing without per-pixel host involvement.
 */

#include <linux/bits.h>
#include <linux/compat.h>
#include <linux/dma-mapping.h>
#include <linux/fs.h>
#include <linux/jiffies.h>
#include <linux/ktime.h>
#include <linux/log2.h>
#include <linux/math.h>
#include <linux/miscdevice.h>
#include <linux/mm.h>
#include <linux/module.h>
#include <linux/mutex.h>
#include <linux/of.h>
#include <linux/of_platform.h>
#include <linux/platform_device.h>
#include <linux/poll.h>
#include <linux/sizes.h>
#include <linux/slab.h>
#include <linux/uaccess.h>
#include <linux/wait.h>

#if IS_ENABLED(CONFIG_KUNIT)
#include <kunit/test.h>
#endif

#include <uapi/misc/rp1_hub75_if.h>

#define DRIVER_NAME	"rp1-hub75"

#define RP1H_DEFAULT_COLS	64
#define RP1H_DEFAULT_ROWS	64
#define RP1H_DEFAULT_PWM_BITS	11
#define RP1H_MAX_COLS		256
#define RP1H_MAX_ROWS		64
#define RP1H_MAX_PANELS		4
#define RP1H_WORDS_PER_PIXEL	2
#define RP1H_TRAILER_WORDS	2
#define RP1H_RGB6_BITS_PER_PIXEL	6
#define RP1H_RGB333_BITS_PER_PIXEL	18
#define RP1H_RGB333_BITS_PER_COLOR	3
#define RP1H_TRANSPORT_ALIGN	256
#define RP1H_DEFAULT_WORKER_TIMEOUT_MS	100

#define RP1H_GPIO_R1	5
#define RP1H_GPIO_G1	13
#define RP1H_GPIO_B1	6
#define RP1H_GPIO_R2	12
#define RP1H_GPIO_G2	16
#define RP1H_GPIO_B2	23
#define RP1H_GPIO_CLK	17
#define RP1H_GPIO_LAT	21
#define RP1H_GPIO_OE	18
#define RP1H_GPIO_A	22
#define RP1H_GPIO_B	26
#define RP1H_GPIO_C	27
#define RP1H_GPIO_D	20
#define RP1H_GPIO_E	24
#define RP1H_HZELLER_REGULAR_P0_R1	11
#define RP1H_HZELLER_REGULAR_P0_G1	27
#define RP1H_HZELLER_REGULAR_P0_B1	7
#define RP1H_HZELLER_REGULAR_P0_R2	8
#define RP1H_HZELLER_REGULAR_P0_G2	9
#define RP1H_HZELLER_REGULAR_P0_B2	10
#define RP1H_HZELLER_REGULAR_CLK	17
#define RP1H_HZELLER_REGULAR_LAT	4
#define RP1H_HZELLER_REGULAR_OE		18
#define RP1H_HZELLER_REGULAR_A		22
#define RP1H_HZELLER_REGULAR_B		23
#define RP1H_HZELLER_REGULAR_C		24
#define RP1H_HZELLER_REGULAR_D		25
#define RP1H_HZELLER_REGULAR_E		15
#define RP1H_REGULAR_P1_R1	12
#define RP1H_REGULAR_P1_G1	5
#define RP1H_REGULAR_P1_B1	6
#define RP1H_REGULAR_P1_R2	19
#define RP1H_REGULAR_P1_G2	13
#define RP1H_REGULAR_P1_B2	20

#define RP1H_PIN(_gpio)	BIT(_gpio)

struct rp1h_pinout {
	u8 r1;
	u8 g1;
	u8 b1;
	u8 r2;
	u8 g2;
	u8 b2;
	u8 clk;
	u8 lat;
	u8 oe;
	u8 a;
	u8 b;
	u8 c;
	u8 d;
	u8 e;
};

static const struct rp1h_pinout rp1h_adafruit_hat_pwm_pinout = {
	.r1 = RP1H_GPIO_R1,
	.g1 = RP1H_GPIO_G1,
	.b1 = RP1H_GPIO_B1,
	.r2 = RP1H_GPIO_R2,
	.g2 = RP1H_GPIO_G2,
	.b2 = RP1H_GPIO_B2,
	.clk = RP1H_GPIO_CLK,
	.lat = RP1H_GPIO_LAT,
	.oe = RP1H_GPIO_OE,
	.a = RP1H_GPIO_A,
	.b = RP1H_GPIO_B,
	.c = RP1H_GPIO_C,
	.d = RP1H_GPIO_D,
	.e = RP1H_GPIO_E,
};

/*
 * Hzeller's "regular" mapping as used by the ElectroDragon board, P0 output
 * only. P1/P2 are intentionally not exposed through this single-lane packer.
 */
static const struct rp1h_pinout rp1h_electrodragon_p0_pinout = {
	.r1 = RP1H_HZELLER_REGULAR_P0_R1,
	.g1 = RP1H_HZELLER_REGULAR_P0_G1,
	.b1 = RP1H_HZELLER_REGULAR_P0_B1,
	.r2 = RP1H_HZELLER_REGULAR_P0_R2,
	.g2 = RP1H_HZELLER_REGULAR_P0_G2,
	.b2 = RP1H_HZELLER_REGULAR_P0_B2,
	.clk = RP1H_HZELLER_REGULAR_CLK,
	.lat = RP1H_HZELLER_REGULAR_LAT,
	.oe = RP1H_HZELLER_REGULAR_OE,
	.a = RP1H_HZELLER_REGULAR_A,
	.b = RP1H_HZELLER_REGULAR_B,
	.c = RP1H_HZELLER_REGULAR_C,
	.d = RP1H_HZELLER_REGULAR_D,
	.e = RP1H_HZELLER_REGULAR_E,
};

static const struct rp1h_pinout *rp1h_pinout_for_mapping(u8 mapping)
{
	switch (mapping) {
	case RP1H_MAPPING_ADAFRUIT_HAT_PWM:
		return &rp1h_adafruit_hat_pwm_pinout;
	case RP1H_MAPPING_ELECTRODRAGON_P0:
		return &rp1h_electrodragon_p0_pinout;
	case RP1H_MAPPING_REGULAR:
		return &rp1h_electrodragon_p0_pinout;
	default:
		return NULL;
	}
}

static const u16 rp1h_cie1931_11bit[256] = {
	   0,    1,    2,    3,    4,    4,    5,    6,
	   7,    8,    9,   10,   11,   12,   12,   13,
	  14,   15,   16,   17,   18,   19,   20,   21,
	  22,   23,   24,   25,   26,   27,   28,   29,
	  31,   32,   33,   34,   36,   37,   39,   40,
	  42,   43,   45,   47,   48,   50,   52,   54,
	  55,   57,   59,   61,   63,   65,   67,   70,
	  72,   74,   76,   79,   81,   83,   86,   88,
	  91,   94,   96,   99,  102,  105,  108,  111,
	 114,  117,  120,  123,  126,  129,  133,  136,
	 139,  143,  146,  150,  154,  157,  161,  165,
	 169,  173,  177,  181,  185,  189,  194,  198,
	 202,  207,  211,  216,  221,  226,  230,  235,
	 240,  245,  250,  255,  261,  266,  271,  277,
	 282,  288,  293,  299,  305,  311,  317,  323,
	 329,  335,  341,  348,  354,  360,  367,  374,
	 380,  387,  394,  401,  408,  415,  422,  430,
	 437,  445,  452,  460,  467,  475,  483,  491,
	 499,  507,  516,  524,  532,  541,  549,  558,
	 567,  576,  585,  594,  603,  612,  621,  631,
	 640,  650,  660,  669,  679,  689,  699,  710,
	 720,  730,  741,  751,  762,  773,  784,  795,
	 806,  817,  828,  840,  851,  863,  875,  887,
	 898,  911,  923,  935,  947,  960,  972,  985,
	 998, 1011, 1024, 1037, 1050, 1064, 1077, 1091,
	1104, 1118, 1132, 1146, 1160, 1175, 1189, 1203,
	1218, 1233, 1248, 1263, 1278, 1293, 1308, 1324,
	1339, 1355, 1371, 1387, 1403, 1419, 1435, 1452,
	1469, 1485, 1502, 1519, 1536, 1553, 1571, 1588,
	1606, 1623, 1641, 1659, 1677, 1696, 1714, 1732,
	1751, 1770, 1789, 1808, 1827, 1846, 1866, 1885,
	1905, 1925, 1945, 1965, 1985, 2006, 2026, 2047,
};

struct rp1h_dev {
	struct miscdevice miscdev;
	/* Protects configuration, packed buffer replacement and statistics. */
	struct mutex lock;
	wait_queue_head_t waitq;
	struct rp1h_config cfg;
	struct device *dma_dev;
	void *buf;
	dma_addr_t buf_dma;
	size_t buf_size;
	unsigned int map_count;
	u32 frames_packed;
	u64 bytes_packed;
	u32 last_error;
	u32 frames_queued;
	u32 frames_presented;
	u32 frames_dropped;
	u32 vsync_count;
	u32 queued_seq;
	u32 presented_seq;
	int displayed_slot;
	int pending_slot;
	u32 pending_seq;
	u32 worker_state;
	u32 worker_flags;
	u32 worker_timeout_ms;
	u32 worker_seq;
	u64 worker_start_ns;
	u64 last_vsync_ns;
};

static struct rp1h_dev *g_rp1h;
static const struct vm_operations_struct rp1h_vm_ops;

static struct device *rp1h_find_dma_device(void)
{
	struct platform_device *pdev;
	struct device_node *np;
	struct device *dev = NULL;

	np = of_find_compatible_node(NULL, NULL, "snps,axi-dma-1.01a");
	if (!np)
		return NULL;

	pdev = of_find_device_by_node(np);
	of_node_put(np);
	if (!pdev)
		return NULL;

	dev = get_device(&pdev->dev);
	put_device(&pdev->dev);
	return dev;
}

static void rp1h_free_buffer(struct rp1h_dev *hub)
{
	if (!hub->buf)
		return;

	dma_free_coherent(hub->dma_dev, hub->buf_size, hub->buf, hub->buf_dma);
	hub->buf = NULL;
	hub->buf_dma = 0;
	hub->buf_size = 0;
}

static const char *rp1h_stream_name(u32 stream_format)
{
	switch (stream_format) {
	case RP1H_STREAM_RIO32:
		return "rio32";
	case RP1H_STREAM_RGB6_PACKED:
		return "rgb6-packed";
	case RP1H_STREAM_RGB6_BYTE:
		return "rgb6-byte";
	case RP1H_STREAM_STATE32:
		return "state32";
	case RP1H_STREAM_RGB333_WORD:
		return "rgb333-word";
	default:
		return "unknown";
	}
}

static const char *rp1h_worker_state_name(u32 state)
{
	switch (state) {
	case RP1H_WORKER_STOPPED:
		return "stopped";
	case RP1H_WORKER_STARTING:
		return "starting";
	case RP1H_WORKER_RUNNING:
		return "running";
	case RP1H_WORKER_STALE:
		return "stale";
	case RP1H_WORKER_ERROR:
		return "error";
	default:
		return "unknown";
	}
}

static u32 rp1h_observed_worker_state_locked(struct rp1h_dev *hub)
{
	u64 timeout_ns;
	u64 now;

	if (hub->worker_state == RP1H_WORKER_STOPPED ||
	    hub->worker_state == RP1H_WORKER_ERROR)
		return hub->worker_state;
	if (!hub->worker_timeout_ms)
		return hub->worker_state;

	timeout_ns = (u64)hub->worker_timeout_ms * NSEC_PER_MSEC;
	now = ktime_get_ns();
	if (!hub->last_vsync_ns) {
		if (hub->worker_start_ns && now > hub->worker_start_ns &&
		    now - hub->worker_start_ns > timeout_ns)
			return RP1H_WORKER_STALE;

		return RP1H_WORKER_STARTING;
	}
	if (now > hub->last_vsync_ns && now - hub->last_vsync_ns > timeout_ns)
		return RP1H_WORKER_STALE;

	return hub->worker_state;
}

static void rp1h_worker_heartbeat_locked(struct rp1h_dev *hub)
{
	if (hub->worker_state == RP1H_WORKER_STOPPED ||
	    hub->worker_state == RP1H_WORKER_ERROR)
		return;

	hub->worker_state = RP1H_WORKER_RUNNING;
	hub->last_vsync_ns = ktime_get_ns();
}

static struct rp1h_mmap_header *rp1h_header(struct rp1h_dev *hub)
{
	return hub->buf;
}

static u32 rp1h_addr_mask_for_pinout(const struct rp1h_pinout *pinout,
				     unsigned int row)
{
	u32 mask = 0;

	if (row & BIT(0))
		mask |= RP1H_PIN(pinout->a);
	if (row & BIT(1))
		mask |= RP1H_PIN(pinout->b);
	if (row & BIT(2))
		mask |= RP1H_PIN(pinout->c);
	if (row & BIT(3))
		mask |= RP1H_PIN(pinout->d);
	if (row & BIT(4))
		mask |= RP1H_PIN(pinout->e);

	return mask;
}

static u32 __maybe_unused rp1h_addr_mask(unsigned int row)
{
	return rp1h_addr_mask_for_pinout(&rp1h_adafruit_hat_pwm_pinout, row);
}

static void rp1h_publish_header_state(struct rp1h_dev *hub)
{
	struct rp1h_mmap_header *hdr = rp1h_header(hub);

	WRITE_ONCE(hdr->frame_seq, hub->frames_packed);
	/*
	 * Publish the queue indices with release ordering so mmap readers can
	 * treat them as the SPSC publication points for slot contents.
	 */
	/* Retire fully consumed slot state before publishing the tail. */
	smp_store_release(&hdr->consumer_tail, hub->presented_seq);
	/* Publish filled slot contents before advancing the producer head. */
	smp_store_release(&hdr->producer_head, hub->queued_seq);
}

static void rp1h_write_header(struct rp1h_dev *hub)
{
	struct rp1h_mmap_header *hdr = rp1h_header(hub);
	const struct rp1h_pinout *pinout =
		rp1h_pinout_for_mapping(hub->cfg.mapping);
	unsigned int i;

	memset(hdr, 0, sizeof(*hdr));
	hdr->magic = RP1H_MAGIC;
	hdr->version = RP1H_VERSION;
	hdr->header_size = sizeof(*hdr);
	hdr->cols = hub->cfg.cols;
	hdr->rows = hub->cfg.rows;
	hdr->pwm_bits = hub->cfg.pwm_bits;
	hdr->mapping = hub->cfg.mapping;
	hdr->format = hub->cfg.format;
	hdr->flags = hub->cfg.flags;
	hdr->frame_seq = hub->frames_packed;
	hdr->words_offset = hub->cfg.words_offset;
	hdr->words_per_frame = hub->cfg.words_per_frame;
	hdr->stream_format = hub->cfg.stream_format;
	hdr->bits_per_pixel = hub->cfg.bits_per_pixel;
	hdr->row_pairs = hub->cfg.rows / 2;
	hdr->plane_count = hub->cfg.pwm_bits;
	hdr->panel_count = hub->cfg.panel_count;
	hdr->words_per_row_plane = hub->cfg.words_per_row_plane;
	hdr->bytes_per_row_plane = hub->cfg.bytes_per_row_plane;
	hdr->words_per_row_plane_aligned = hub->cfg.words_per_row_plane_aligned;
	hdr->bytes_per_row_plane_aligned = hub->cfg.bytes_per_row_plane_aligned;
	hdr->lane_count = hub->cfg.lane_count;
	hdr->chain_length = hub->cfg.chain_length;
	hdr->addr_line_count = hub->cfg.addr_line_count;
	hdr->slot_count = hub->cfg.slot_count;
	hdr->slot_stride_bytes = hub->cfg.slot_stride_bytes;
	hdr->buffer_dma_addr_lo = lower_32_bits(hub->buf_dma);
	hdr->buffer_dma_addr_hi = upper_32_bits(hub->buf_dma);
	for (i = 0; i < hub->cfg.slot_count && i < RP1H_MAX_SLOTS; i++) {
		dma_addr_t slot_dma = hub->buf_dma + hub->cfg.words_offset +
				      (dma_addr_t)i *
				      hub->cfg.slot_stride_bytes;

		hdr->slot_dma_addr_lo[i] = lower_32_bits(slot_dma);
		hdr->slot_dma_addr_hi[i] = upper_32_bits(slot_dma);
	}
	hdr->pin_r1 = RP1H_PIN(pinout->r1);
	hdr->pin_g1 = RP1H_PIN(pinout->g1);
	hdr->pin_b1 = RP1H_PIN(pinout->b1);
	hdr->pin_r2 = RP1H_PIN(pinout->r2);
	hdr->pin_g2 = RP1H_PIN(pinout->g2);
	hdr->pin_b2 = RP1H_PIN(pinout->b2);
	hdr->pin_clk = RP1H_PIN(pinout->clk);
	hdr->pin_lat = RP1H_PIN(pinout->lat);
	hdr->pin_oe = RP1H_PIN(pinout->oe);
	hdr->pin_a = RP1H_PIN(pinout->a);
	hdr->pin_b = RP1H_PIN(pinout->b);
	hdr->pin_c = RP1H_PIN(pinout->c);
	hdr->pin_d = RP1H_PIN(pinout->d);
	hdr->pin_e = RP1H_PIN(pinout->e);

	for (i = 0; i < hub->cfg.pwm_bits; i++)
		hdr->dwell[i] = BIT(min_t(u32, i, hub->cfg.dwell_shift_limit));

	rp1h_publish_header_state(hub);
}

static int rp1h_validate_config(struct rp1h_config *cfg)
{
	u32 row_pairs;
	u32 expected_addr_lines;
	u32 words_per_row_plane;
	u32 bytes_per_row_plane;
	u64 words;
	u64 mmap_size;

	if (!cfg->cols)
		cfg->cols = RP1H_DEFAULT_COLS;
	if (!cfg->rows)
		cfg->rows = RP1H_DEFAULT_ROWS;
	if (!cfg->pwm_bits) {
		cfg->pwm_bits = cfg->stream_format == RP1H_STREAM_RGB333_WORD ?
				RP1H_RGB333_BITS_PER_COLOR :
				RP1H_DEFAULT_PWM_BITS;
	}
	if (!cfg->panel_count)
		cfg->panel_count = 1;
	if (!cfg->lane_count)
		cfg->lane_count = cfg->panel_count;
	if (!cfg->chain_length)
		cfg->chain_length = 1;
	if (!cfg->size ||
	    cfg->size < offsetofend(struct rp1h_config, dwell_shift_limit))
		cfg->dwell_shift_limit = RP1H_DEFAULT_DWELL_SHIFT_LIMIT;

	if (!rp1h_pinout_for_mapping(cfg->mapping) ||
	    cfg->format != RP1H_FORMAT_RGB888)
		return -EINVAL;
	if (cfg->stream_format != RP1H_STREAM_RIO32 &&
	    cfg->stream_format != RP1H_STREAM_RGB6_PACKED &&
	    cfg->stream_format != RP1H_STREAM_RGB6_BYTE &&
	    cfg->stream_format != RP1H_STREAM_STATE32 &&
	    cfg->stream_format != RP1H_STREAM_RGB333_WORD)
		return -EINVAL;
	if (!is_power_of_2(cfg->cols) || cfg->cols > RP1H_MAX_COLS)
		return -EINVAL;
	if (cfg->rows < 16 || cfg->rows > RP1H_MAX_ROWS ||
	    !is_power_of_2(cfg->rows))
		return -EINVAL;
	if (cfg->pwm_bits < 1 || cfg->pwm_bits > RP1H_MAX_PWM_BITS)
		return -EINVAL;
	if (cfg->reserved1 || cfg->dwell_shift_limit >= RP1H_MAX_PWM_BITS)
		return -EINVAL;
	if (cfg->panel_count < 1 || cfg->panel_count > RP1H_MAX_PANELS)
		return -EINVAL;
	if (cfg->lane_count < 1 || cfg->lane_count > cfg->panel_count)
		return -EINVAL;
	if (cfg->chain_length < 1 || cfg->chain_length > cfg->panel_count)
		return -EINVAL;
	if (cfg->lane_count * cfg->chain_length != cfg->panel_count)
		return -EINVAL;
	if (cfg->panel_count > 1 &&
	    cfg->stream_format != RP1H_STREAM_RGB6_PACKED &&
	    cfg->stream_format != RP1H_STREAM_RGB6_BYTE &&
	    !(cfg->mapping == RP1H_MAPPING_REGULAR &&
	      cfg->stream_format == RP1H_STREAM_STATE32 &&
	      cfg->lane_count == 2 &&
	      cfg->chain_length == 2 &&
	      cfg->panel_count == 4))
		return -EINVAL;
	if (cfg->stream_format == RP1H_STREAM_RGB333_WORD &&
	    cfg->pwm_bits != RP1H_RGB333_BITS_PER_COLOR)
		return -EINVAL;
	if ((cfg->flags & ~RP1H_F_E_LINE_PRESENT) ||
	    ((cfg->flags & RP1H_F_E_LINE_PRESENT) && cfg->rows < 64))
		return -EINVAL;

	row_pairs = cfg->rows / 2;
	expected_addr_lines = ilog2(row_pairs);
	if (expected_addr_lines >= 5)
		cfg->flags |= RP1H_F_E_LINE_PRESENT;
	if (!cfg->addr_line_count)
		cfg->addr_line_count = expected_addr_lines;
	if (cfg->addr_line_count != expected_addr_lines)
		return -EINVAL;
	if (cfg->slot_count &&
	    (!is_power_of_2(cfg->slot_count) || cfg->slot_count != RP1H_MAX_SLOTS))
		return -EINVAL;
	if (cfg->slot_stride_bytes)
		return -EINVAL;
	if (cfg->chain_length != 1 &&
	    !(cfg->mapping == RP1H_MAPPING_REGULAR &&
	      cfg->stream_format == RP1H_STREAM_STATE32 &&
	      cfg->lane_count == 2 &&
	      cfg->chain_length == 2 &&
	      cfg->panel_count == 4))
		return -EINVAL;
	if (cfg->stream_format == RP1H_STREAM_RGB6_PACKED) {
		cfg->bits_per_pixel = RP1H_RGB6_BITS_PER_PIXEL;
		words_per_row_plane = DIV_ROUND_UP(cfg->cols * cfg->panel_count *
						   RP1H_RGB6_BITS_PER_PIXEL,
						   32);
	} else if (cfg->stream_format == RP1H_STREAM_RGB6_BYTE) {
		cfg->bits_per_pixel = 8;
		words_per_row_plane = DIV_ROUND_UP(cfg->cols * cfg->panel_count,
						   sizeof(u32));
	} else if (cfg->stream_format == RP1H_STREAM_RGB333_WORD) {
		cfg->bits_per_pixel = RP1H_RGB333_BITS_PER_PIXEL;
		words_per_row_plane = cfg->cols;
	} else if (cfg->stream_format == RP1H_STREAM_STATE32) {
		cfg->bits_per_pixel = 1;
		words_per_row_plane = cfg->cols * cfg->chain_length;
	} else {
		cfg->bits_per_pixel = 1;
		words_per_row_plane = cfg->cols * RP1H_WORDS_PER_PIXEL +
				      RP1H_TRAILER_WORDS;
	}
	if (cfg->stream_format == RP1H_STREAM_RGB333_WORD)
		words = (u64)row_pairs * words_per_row_plane;
	else
		words = (u64)row_pairs * cfg->pwm_bits * words_per_row_plane;
	cfg->slot_stride_bytes = cfg->slot_count ?
		PAGE_ALIGN(words * sizeof(u32)) : 0;
	mmap_size = PAGE_ALIGN(sizeof(struct rp1h_mmap_header)) +
		    (cfg->slot_count ?
		     (u64)cfg->slot_count * cfg->slot_stride_bytes :
		     words * sizeof(u32));
	mmap_size = PAGE_ALIGN(mmap_size);
	if (words > U32_MAX || mmap_size > SZ_8M)
		return -E2BIG;

	bytes_per_row_plane = words_per_row_plane * sizeof(u32);

	cfg->frame_bytes = cfg->cols * cfg->rows * 3 * cfg->panel_count;
	cfg->words_offset = PAGE_ALIGN(sizeof(struct rp1h_mmap_header));
	cfg->words_per_frame = words;
	cfg->words_per_row_plane = words_per_row_plane;
	cfg->bytes_per_row_plane = bytes_per_row_plane;
	cfg->bytes_per_row_plane_aligned = ALIGN(bytes_per_row_plane,
						 RP1H_TRANSPORT_ALIGN);
	cfg->words_per_row_plane_aligned =
		cfg->bytes_per_row_plane_aligned / sizeof(u32);
	cfg->mmap_size = mmap_size;

	return 0;
}

static long rp1h_ioctl_config(struct rp1h_dev *hub, void __user *argp)
{
	struct rp1h_config cfg;
	u32 user_size32;
	size_t user_size;
	size_t copy_size;
	void *buf;
	dma_addr_t buf_dma;
	int ret;

	memset(&cfg, 0, sizeof(cfg));
	if (copy_from_user(&user_size32, argp, sizeof(user_size32)))
		return -EFAULT;
	user_size = user_size32;
	if (!user_size)
		user_size = offsetof(struct rp1h_config, stream_format);
	ret = copy_struct_from_user(&cfg, sizeof(cfg), argp, user_size);
	if (ret)
		return ret;
	if (cfg.size && cfg.size < offsetof(struct rp1h_config, stream_format))
		return -EINVAL;

	ret = rp1h_validate_config(&cfg);
	if (ret)
		return ret;
	if (!hub->dma_dev)
		return -ENODEV;

	buf = dma_alloc_coherent(hub->dma_dev, cfg.mmap_size, &buf_dma,
				 GFP_KERNEL);
	if (!buf)
		return -ENOMEM;

	mutex_lock(&hub->lock);
	if (hub->map_count) {
		mutex_unlock(&hub->lock);
		dma_free_coherent(hub->dma_dev, cfg.mmap_size, buf, buf_dma);
		return -EBUSY;
	}
	rp1h_free_buffer(hub);
	hub->buf = buf;
	hub->buf_dma = buf_dma;
	hub->buf_size = cfg.mmap_size;
	hub->cfg = cfg;
	hub->frames_packed = 0;
	hub->bytes_packed = 0;
	hub->last_error = 0;
	hub->frames_queued = 0;
	hub->frames_presented = 0;
	hub->frames_dropped = 0;
	hub->vsync_count = 0;
	hub->queued_seq = 0;
	hub->presented_seq = 0;
	hub->displayed_slot = cfg.slot_count ? 0 : -1;
	hub->pending_slot = -1;
	hub->pending_seq = 0;
	hub->worker_state = RP1H_WORKER_STOPPED;
	hub->worker_flags = 0;
	hub->worker_timeout_ms = 0;
	hub->worker_seq = 0;
	hub->worker_start_ns = 0;
	hub->last_vsync_ns = 0;
	rp1h_write_header(hub);
	mutex_unlock(&hub->lock);
	wake_up_interruptible(&hub->waitq);

	pr_info(DRIVER_NAME
		": configured %ux%u pwm=%u dwell_limit=%u stream=%s panels=%u lanes=%u chains=%u slots=%u frame_bytes=%u words=%u mmap=%u slot_stride=%u\n",
		cfg.cols, cfg.rows, cfg.pwm_bits,
		cfg.dwell_shift_limit,
		rp1h_stream_name(cfg.stream_format), cfg.panel_count,
		cfg.lane_count, cfg.chain_length, cfg.slot_count,
		cfg.frame_bytes, cfg.words_per_frame, cfg.mmap_size,
		cfg.slot_stride_bytes);

	cfg.size = sizeof(cfg);
	copy_size = min_t(size_t, user_size, sizeof(cfg));
	if (copy_to_user(argp, &cfg, copy_size))
		return -EFAULT;

	return 0;
}

static u32 rp1h_rgb_mask(const struct rp1h_dev *hub, const u8 *top,
			 const u8 *bottom, unsigned int plane)
{
	const struct rp1h_pinout *pinout =
		rp1h_pinout_for_mapping(hub->cfg.mapping);
	u16 bit = BIT(plane + (RP1H_MAX_PWM_BITS - hub->cfg.pwm_bits));
	u32 mask = 0;

	if (rp1h_cie1931_11bit[top[0]] & bit)
		mask |= RP1H_PIN(pinout->r1);
	if (rp1h_cie1931_11bit[top[1]] & bit)
		mask |= RP1H_PIN(pinout->g1);
	if (rp1h_cie1931_11bit[top[2]] & bit)
		mask |= RP1H_PIN(pinout->b1);
	if (rp1h_cie1931_11bit[bottom[0]] & bit)
		mask |= RP1H_PIN(pinout->r2);
	if (rp1h_cie1931_11bit[bottom[1]] & bit)
		mask |= RP1H_PIN(pinout->g2);
	if (rp1h_cie1931_11bit[bottom[2]] & bit)
		mask |= RP1H_PIN(pinout->b2);

	return mask;
}

static u32 rp1h_regular_p1_rgb_mask(const struct rp1h_dev *hub, const u8 *top,
				    const u8 *bottom, unsigned int plane)
{
	u16 bit = BIT(plane + (RP1H_MAX_PWM_BITS - hub->cfg.pwm_bits));
	u32 mask = 0;

	if (rp1h_cie1931_11bit[top[0]] & bit)
		mask |= RP1H_PIN(RP1H_REGULAR_P1_R1);
	if (rp1h_cie1931_11bit[top[1]] & bit)
		mask |= RP1H_PIN(RP1H_REGULAR_P1_G1);
	if (rp1h_cie1931_11bit[top[2]] & bit)
		mask |= RP1H_PIN(RP1H_REGULAR_P1_B1);
	if (rp1h_cie1931_11bit[bottom[0]] & bit)
		mask |= RP1H_PIN(RP1H_REGULAR_P1_R2);
	if (rp1h_cie1931_11bit[bottom[1]] & bit)
		mask |= RP1H_PIN(RP1H_REGULAR_P1_G2);
	if (rp1h_cie1931_11bit[bottom[2]] & bit)
		mask |= RP1H_PIN(RP1H_REGULAR_P1_B2);

	return mask;
}

static u32 rp1h_rgb6_bits(const struct rp1h_dev *hub, const u8 *top,
			  const u8 *bottom, unsigned int plane)
{
	u16 bit = BIT(plane + (RP1H_MAX_PWM_BITS - hub->cfg.pwm_bits));
	u32 rgb = 0;

	if (rp1h_cie1931_11bit[top[0]] & bit)
		rgb |= BIT(0);
	if (rp1h_cie1931_11bit[top[1]] & bit)
		rgb |= BIT(1);
	if (rp1h_cie1931_11bit[top[2]] & bit)
		rgb |= BIT(2);
	if (rp1h_cie1931_11bit[bottom[0]] & bit)
		rgb |= BIT(3);
	if (rp1h_cie1931_11bit[bottom[1]] & bit)
		rgb |= BIT(4);
	if (rp1h_cie1931_11bit[bottom[2]] & bit)
		rgb |= BIT(5);

	return rgb;
}

static u32 rp1h_pack_rgb333_word(const u8 *top, const u8 *bottom)
{
	u32 top_r = top[0] >> 5;
	u32 top_g = top[1] >> 5;
	u32 top_b = top[2] >> 5;
	u32 bottom_r = bottom[0] >> 5;
	u32 bottom_g = bottom[1] >> 5;
	u32 bottom_b = bottom[2] >> 5;

	return top_r | (top_g << 3) | (top_b << 6) |
	       (bottom_r << 16) | (bottom_g << 19) | (bottom_b << 22);
}

static void rp1h_pack_rgb888(struct rp1h_dev *hub, void *dst, const u8 *frame)
{
	const struct rp1h_pinout *pinout =
		rp1h_pinout_for_mapping(hub->cfg.mapping);
	u32 *words = dst;
	u32 clk = RP1H_PIN(pinout->clk);
	u32 lat = RP1H_PIN(pinout->lat);
	u32 oe = RP1H_PIN(pinout->oe);
	unsigned int row_pairs = hub->cfg.rows / 2;
	unsigned int row, plane, col;

	for (row = 0; row < row_pairs; row++) {
		u32 addr = rp1h_addr_mask_for_pinout(pinout, row);

		for (plane = 0; plane < hub->cfg.pwm_bits; plane++) {
			u32 base = addr | oe;

			for (col = 0; col < hub->cfg.cols; col++) {
				const u8 *top;
				const u8 *bottom;
				u32 out;

				top = frame + (row * hub->cfg.cols + col) * 3;
				bottom = frame + ((row + row_pairs) *
						  hub->cfg.cols + col) * 3;
				out = base | rp1h_rgb_mask(hub, top, bottom,
							   plane);
				*words++ = out;
				*words++ = out | clk;
			}

			*words++ = base | lat;
			*words++ = base;
		}
	}
}

static void rp1h_pack_rgb888_rgb333_word(struct rp1h_dev *hub, void *dst,
					 const u8 *frame)
{
	u32 *words = dst;
	unsigned int row_pairs = hub->cfg.rows / 2;
	unsigned int row, col;

	for (row = 0; row < row_pairs; row++) {
		for (col = 0; col < hub->cfg.cols; col++) {
			const u8 *top;
			const u8 *bottom;

			top = frame + (row * hub->cfg.cols + col) * 3;
			bottom = frame + ((row + row_pairs) *
					  hub->cfg.cols + col) * 3;
			*words++ = rp1h_pack_rgb333_word(top, bottom);
		}
	}
}

static void rp1h_pack_rgb888_state32(struct rp1h_dev *hub, void *dst,
				     const u8 *frame)
{
	const struct rp1h_pinout *pinout =
		rp1h_pinout_for_mapping(hub->cfg.mapping);
	u32 *words = dst;
	u32 oe = RP1H_PIN(pinout->oe);
	unsigned int row_pairs = hub->cfg.rows / 2;
	unsigned int row, plane, col;
	unsigned int active_cols;

	for (row = 0; row < row_pairs; row++) {
		for (plane = 0; plane < hub->cfg.pwm_bits; plane++) {
			u32 base = rp1h_addr_mask_for_pinout(pinout, row) | oe;
			bool regular_chain2 = hub->cfg.mapping == RP1H_MAPPING_REGULAR &&
				hub->cfg.lane_count == 2 &&
				hub->cfg.chain_length == 2;

			active_cols = hub->cfg.cols * hub->cfg.chain_length;
			for (col = 0; col < active_cols; col++) {
				const u8 *top;
				const u8 *bottom;
				const u8 *lane1_top;
				const u8 *lane1_bottom;
				unsigned int input_cols;

				input_cols = regular_chain2 ?
					active_cols * hub->cfg.lane_count :
					active_cols;
				top = frame + (row * input_cols + col) * 3;
				bottom = frame + ((row + row_pairs) *
						  input_cols + col) * 3;
				if (regular_chain2) {
					lane1_top = frame +
						    (row * input_cols +
						     active_cols + col) * 3;
					lane1_bottom = frame +
						       ((row + row_pairs) *
							input_cols +
							active_cols + col) * 3;
					*words++ = base |
						   rp1h_rgb_mask(hub, top, bottom, plane) |
						   rp1h_regular_p1_rgb_mask(hub, lane1_top,
									     lane1_bottom,
									     plane);
				} else {
					*words++ = base |
						   rp1h_rgb_mask(hub, top, bottom, plane);
				}
			}
		}
	}
}

static void rp1h_pack_rgb888_rgb6_packed(struct rp1h_dev *hub, void *dst,
					 const u8 *frame)
{
	u32 *base = dst;
	unsigned int row_pairs = hub->cfg.rows / 2;
	unsigned int frame_stride = hub->cfg.cols * hub->cfg.rows * 3;
	unsigned int row, plane, col, panel;

	for (row = 0; row < row_pairs; row++) {
		for (plane = 0; plane < hub->cfg.pwm_bits; plane++) {
			u32 *words = base + (row * hub->cfg.pwm_bits + plane) *
				     hub->cfg.words_per_row_plane;
			u64 acc = 0;
			unsigned int bits = 0;

			for (col = 0; col < hub->cfg.cols; col++) {
				for (panel = 0; panel < hub->cfg.panel_count; panel++) {
					const u8 *panel_frame;
					const u8 *top;
					const u8 *bottom;
					u32 rgb;

					panel_frame = frame + panel * frame_stride;
					top = panel_frame + (row * hub->cfg.cols + col) * 3;
					bottom = panel_frame + ((row + row_pairs) *
								hub->cfg.cols + col) * 3;
					rgb = rp1h_rgb6_bits(hub, top, bottom, plane);
					acc |= (u64)rgb << bits;
					bits += RP1H_RGB6_BITS_PER_PIXEL;

					if (bits >= 32) {
						*words++ = (u32)acc;
						acc >>= 32;
						bits -= 32;
					}
				}
			}

			if (bits)
				*words++ = (u32)acc;
		}
	}
}

static void rp1h_pack_rgb888_rgb6_byte(struct rp1h_dev *hub, void *dst,
				       const u8 *frame)
{
	u8 *base = dst;
	unsigned int bytes_per_payload = hub->cfg.cols * hub->cfg.panel_count;
	unsigned int row_pairs = hub->cfg.rows / 2;
	unsigned int frame_stride = hub->cfg.cols * hub->cfg.rows * 3;
	unsigned int row, plane, col, panel;

	for (row = 0; row < row_pairs; row++) {
		for (plane = 0; plane < hub->cfg.pwm_bits; plane++) {
			u8 *bytes = base + (row * hub->cfg.pwm_bits + plane) *
				    hub->cfg.bytes_per_row_plane;

			for (col = 0; col < hub->cfg.cols; col++) {
				for (panel = 0; panel < hub->cfg.panel_count; panel++) {
					const u8 *panel_frame;
					const u8 *top;
					const u8 *bottom;

					panel_frame = frame + panel * frame_stride;
					top = panel_frame + (row * hub->cfg.cols + col) * 3;
					bottom = panel_frame + ((row + row_pairs) *
								hub->cfg.cols + col) * 3;
					*bytes++ = rp1h_rgb6_bits(hub, top, bottom, plane);
				}
			}
			memset(bytes, 0, hub->cfg.bytes_per_row_plane - bytes_per_payload);
		}
	}
}

static void *rp1h_frame_slot(struct rp1h_dev *hub, unsigned int slot)
{
	return hub->buf + hub->cfg.words_offset +
	       (size_t)slot * hub->cfg.slot_stride_bytes;
}

static void *rp1h_legacy_frame(struct rp1h_dev *hub)
{
	return hub->buf + hub->cfg.words_offset;
}

static void rp1h_pack_to(struct rp1h_dev *hub, void *dst, const u8 *frame)
{
	if (hub->cfg.stream_format == RP1H_STREAM_RGB6_PACKED)
		rp1h_pack_rgb888_rgb6_packed(hub, dst, frame);
	else if (hub->cfg.stream_format == RP1H_STREAM_RGB6_BYTE)
		rp1h_pack_rgb888_rgb6_byte(hub, dst, frame);
	else if (hub->cfg.stream_format == RP1H_STREAM_RGB333_WORD)
		rp1h_pack_rgb888_rgb333_word(hub, dst, frame);
	else if (hub->cfg.stream_format == RP1H_STREAM_STATE32)
		rp1h_pack_rgb888_state32(hub, dst, frame);
	else
		rp1h_pack_rgb888(hub, dst, frame);
}

static int rp1h_find_free_slot_locked(struct rp1h_dev *hub)
{
	unsigned int slot;

	for (slot = 0; slot < hub->cfg.slot_count; slot++) {
		if ((int)slot != hub->displayed_slot &&
		    (int)slot != hub->pending_slot)
			return slot;
	}

	return -1;
}

static int rp1h_choose_queue_slot_locked(struct rp1h_dev *hub, u32 flags,
					 bool *replaced_pending)
{
	int slot = rp1h_find_free_slot_locked(hub);

	*replaced_pending = false;
	if (slot < 0 && (flags & RP1H_QUEUE_F_REPLACE_PENDING) &&
	    hub->pending_slot >= 0) {
		slot = hub->pending_slot;
		*replaced_pending = true;
	}

	return slot;
}

static void rp1h_signal_vsync_locked(struct rp1h_dev *hub,
				     struct rp1h_vsync *vsync)
{
	hub->vsync_count++;
	if (hub->pending_slot >= 0) {
		hub->displayed_slot = hub->pending_slot;
		hub->presented_seq = hub->pending_seq;
		hub->pending_slot = -1;
		hub->pending_seq = 0;
		hub->frames_presented++;
	}
	if (vsync) {
		vsync->presented_seq = hub->presented_seq;
		vsync->displayed_slot = hub->displayed_slot < 0 ? U32_MAX :
					(u32)hub->displayed_slot;
	}
}

static bool rp1h_queue_has_space(struct rp1h_dev *hub)
{
	bool has_space;

	mutex_lock(&hub->lock);
	has_space = !hub->buf || !hub->cfg.slot_count ||
		    rp1h_find_free_slot_locked(hub) >= 0;
	mutex_unlock(&hub->lock);

	return has_space;
}

static bool rp1h_ready(struct rp1h_dev *hub, u32 seq)
{
	bool ready;

	mutex_lock(&hub->lock);
	ready = !hub->buf || !hub->cfg.slot_count || hub->presented_seq >= seq;
	mutex_unlock(&hub->lock);

	return ready;
}

static long rp1h_ioctl_pack_frame(struct rp1h_dev *hub, void __user *argp)
{
	struct rp1h_pack_frame pack;
	u8 *frame;
	int ret = 0;

	memset(&pack, 0, sizeof(pack));
	ret = copy_struct_from_user(&pack, sizeof(pack), argp, sizeof(pack));
	if (ret)
		return ret;
	if (pack.size && pack.size < sizeof(pack))
		return -EINVAL;

	mutex_lock(&hub->lock);
	if (!hub->buf) {
		ret = -EINVAL;
		goto out_unlock;
	}
	if (hub->cfg.slot_count) {
		ret = -EINVAL;
		goto out_unlock;
	}
	if (pack.length != hub->cfg.frame_bytes) {
		ret = -EINVAL;
		goto out_unlock;
	}
	mutex_unlock(&hub->lock);

	frame = memdup_user(u64_to_user_ptr(pack.data), pack.length);
	if (IS_ERR(frame))
		return PTR_ERR(frame);

	mutex_lock(&hub->lock);
	if (!hub->buf || hub->cfg.slot_count ||
	    pack.length != hub->cfg.frame_bytes) {
		ret = -EINVAL;
		goto out_free_unlock;
	}

	rp1h_pack_to(hub, rp1h_legacy_frame(hub), frame);
	hub->frames_packed++;
	hub->bytes_packed += pack.length;
	hub->last_error = 0;
	rp1h_write_header(hub);

out_free_unlock:
	mutex_unlock(&hub->lock);
	kfree(frame);
	return ret;

out_unlock:
	hub->last_error = ret;
	mutex_unlock(&hub->lock);
	return ret;
}

static long rp1h_ioctl_queue_frame(struct rp1h_dev *hub, void __user *argp)
{
	struct rp1h_queue_frame queue;
	bool replaced_pending;
	u8 *frame;
	int slot;
	int ret = 0;

	memset(&queue, 0, sizeof(queue));
	ret = copy_struct_from_user(&queue, sizeof(queue), argp, sizeof(queue));
	if (ret)
		return ret;
	if (queue.size && queue.size < sizeof(queue))
		return -EINVAL;
	if (queue.flags & ~(RP1H_QUEUE_F_NONBLOCK |
			    RP1H_QUEUE_F_REPLACE_PENDING))
		return -EINVAL;

	mutex_lock(&hub->lock);
	if (!hub->buf || !hub->cfg.slot_count) {
		ret = -EINVAL;
		goto out_unlock;
	}
	if (queue.length != hub->cfg.frame_bytes) {
		ret = -EINVAL;
		goto out_unlock;
	}
	slot = rp1h_find_free_slot_locked(hub);
	if (slot < 0 && !(queue.flags & RP1H_QUEUE_F_REPLACE_PENDING) &&
	    (queue.flags & RP1H_QUEUE_F_NONBLOCK)) {
		ret = -EBUSY;
		goto out_unlock;
	}
	mutex_unlock(&hub->lock);

	if (slot < 0 && !(queue.flags & RP1H_QUEUE_F_REPLACE_PENDING)) {
		ret = wait_event_interruptible(hub->waitq,
					       rp1h_queue_has_space(hub));
		if (ret)
			return ret;
	}

	frame = memdup_user(u64_to_user_ptr(queue.data), queue.length);
	if (IS_ERR(frame))
		return PTR_ERR(frame);

	mutex_lock(&hub->lock);
	if (!hub->buf || !hub->cfg.slot_count ||
	    queue.length != hub->cfg.frame_bytes) {
		ret = -EINVAL;
		goto out_free_unlock;
	}
	slot = rp1h_choose_queue_slot_locked(hub, queue.flags,
					     &replaced_pending);
	if (replaced_pending) {
		hub->frames_dropped++;
		pr_debug(DRIVER_NAME
			 ": replacing pending frame seq=%u slot=%d drops=%u\n",
			 hub->pending_seq, slot, hub->frames_dropped);
	}
	if (slot < 0) {
		ret = -EBUSY;
		goto out_free_unlock;
	}

	rp1h_pack_to(hub, rp1h_frame_slot(hub, slot), frame);
	hub->frames_packed++;
	hub->frames_queued++;
	hub->bytes_packed += queue.length;
	hub->last_error = 0;
	hub->queued_seq++;
	hub->pending_seq = hub->queued_seq;
	hub->pending_slot = slot;
	queue.seq = hub->queued_seq;
	queue.slot_index = slot;
	rp1h_write_header(hub);
	pr_debug(DRIVER_NAME
		 ": queued seq=%u slot=%u flags=0x%x displayed=%d pending=%d\n",
		 queue.seq, queue.slot_index, queue.flags,
		 hub->displayed_slot, hub->pending_slot);

out_free_unlock:
	mutex_unlock(&hub->lock);
	kfree(frame);
	if (ret)
		return ret;

	queue.size = sizeof(queue);
	if (copy_to_user(argp, &queue, sizeof(queue)))
		return -EFAULT;

	wake_up_interruptible(&hub->waitq);
	return 0;

out_unlock:
	hub->last_error = ret;
	mutex_unlock(&hub->lock);
	return ret;
}

static long rp1h_ioctl_wait_present(struct rp1h_dev *hub, void __user *argp)
{
	struct rp1h_wait_present wait;
	long tmo;
	int ret = 0;

	memset(&wait, 0, sizeof(wait));
	ret = copy_struct_from_user(&wait, sizeof(wait), argp, sizeof(wait));
	if (ret)
		return ret;
	if (wait.size && wait.size < sizeof(wait))
		return -EINVAL;

	mutex_lock(&hub->lock);
	if (!hub->buf || !hub->cfg.slot_count) {
		mutex_unlock(&hub->lock);
		return -EINVAL;
	}
	if (!wait.seq)
		wait.seq = hub->presented_seq + 1;
	if (hub->presented_seq >= wait.seq) {
		wait.presented_seq = hub->presented_seq;
		mutex_unlock(&hub->lock);
		goto out_copy;
	}
	mutex_unlock(&hub->lock);

	if (!wait.timeout_ns)
		return -EAGAIN;
	if (wait.timeout_ns < 0) {
		ret = wait_event_interruptible(hub->waitq,
					       rp1h_ready(hub, wait.seq));
		if (ret)
			return ret;
	} else {
		tmo = nsecs_to_jiffies(wait.timeout_ns);
		if (!tmo)
			tmo = 1;
		tmo = wait_event_interruptible_timeout(hub->waitq, rp1h_ready(hub, wait.seq), tmo);
		if (tmo < 0)
			return tmo;
		if (!tmo)
			return -ETIMEDOUT;
	}

	mutex_lock(&hub->lock);
	wait.presented_seq = hub->presented_seq;
	mutex_unlock(&hub->lock);

out_copy:
	wait.size = sizeof(wait);
	if (copy_to_user(argp, &wait, sizeof(wait)))
		return -EFAULT;
	return 0;
}

static long rp1h_ioctl_signal_vsync(struct rp1h_dev *hub, void __user *argp)
{
	struct rp1h_vsync vsync;
	int ret;

	memset(&vsync, 0, sizeof(vsync));
	ret = copy_struct_from_user(&vsync, sizeof(vsync), argp, sizeof(vsync));
	if (ret)
		return ret;
	if (vsync.size && vsync.size < sizeof(vsync))
		return -EINVAL;
	if (vsync.flags)
		return -EINVAL;

	mutex_lock(&hub->lock);
	if (!hub->buf || !hub->cfg.slot_count) {
		mutex_unlock(&hub->lock);
		return -EINVAL;
	}

	rp1h_signal_vsync_locked(hub, &vsync);
	rp1h_worker_heartbeat_locked(hub);
	rp1h_write_header(hub);
	pr_debug(DRIVER_NAME
		 ": vsync=%u presented_seq=%u displayed_slot=%u pending_slot=%d\n",
		 hub->vsync_count, vsync.presented_seq, vsync.displayed_slot,
		 hub->pending_slot);
	mutex_unlock(&hub->lock);

	wake_up_interruptible(&hub->waitq);

	vsync.size = sizeof(vsync);
	if (copy_to_user(argp, &vsync, sizeof(vsync)))
		return -EFAULT;
	return 0;
}

static long rp1h_ioctl_get_stats(struct rp1h_dev *hub, void __user *argp)
{
	struct rp1h_stats stats;

	memset(&stats, 0, sizeof(stats));
	mutex_lock(&hub->lock);
	stats.size = sizeof(stats);
	stats.frames_packed = hub->frames_packed;
	stats.bytes_packed = hub->bytes_packed;
	stats.last_error = hub->last_error;
	stats.words_per_frame = hub->cfg.words_per_frame;
	mutex_unlock(&hub->lock);

	if (copy_to_user(argp, &stats, sizeof(stats)))
		return -EFAULT;

	return 0;
}

static long rp1h_ioctl_get_present_stats(struct rp1h_dev *hub, void __user *argp)
{
	struct rp1h_present_stats stats;

	memset(&stats, 0, sizeof(stats));
	mutex_lock(&hub->lock);
	stats.size = sizeof(stats);
	stats.frames_queued = hub->frames_queued;
	stats.frames_presented = hub->frames_presented;
	stats.frames_dropped = hub->frames_dropped;
	stats.vsync_count = hub->vsync_count;
	stats.queued_seq = hub->queued_seq;
	stats.presented_seq = hub->presented_seq;
	stats.displayed_slot = hub->displayed_slot < 0 ? U32_MAX :
			       (u32)hub->displayed_slot;
	stats.pending_slot = hub->pending_slot < 0 ? U32_MAX :
			     (u32)hub->pending_slot;
	mutex_unlock(&hub->lock);

	if (copy_to_user(argp, &stats, sizeof(stats)))
		return -EFAULT;

	return 0;
}

static long rp1h_ioctl_start_worker(struct rp1h_dev *hub, void __user *argp)
{
	struct rp1h_worker_control ctl;
	int ret;

	memset(&ctl, 0, sizeof(ctl));
	ret = copy_struct_from_user(&ctl, sizeof(ctl), argp, sizeof(ctl));
	if (ret)
		return ret;
	if (ctl.size && ctl.size < sizeof(ctl))
		return -EINVAL;
	if (ctl.flags & ~RP1H_WORKER_F_EXTERNAL_VSYNC)
		return -EINVAL;
	if (!(ctl.flags & RP1H_WORKER_F_EXTERNAL_VSYNC))
		return -EOPNOTSUPP;
	if (!ctl.status_timeout_ms)
		ctl.status_timeout_ms = RP1H_DEFAULT_WORKER_TIMEOUT_MS;

	mutex_lock(&hub->lock);
	if (!hub->buf || !hub->cfg.slot_count) {
		mutex_unlock(&hub->lock);
		return -EINVAL;
	}

	hub->worker_state = RP1H_WORKER_STARTING;
	hub->worker_flags = ctl.flags;
	hub->worker_timeout_ms = ctl.status_timeout_ms;
	hub->worker_seq++;
	hub->worker_start_ns = ktime_get_ns();
	hub->last_vsync_ns = 0;
	ctl.reserved0[0] = hub->worker_seq;
	mutex_unlock(&hub->lock);

	pr_info(DRIVER_NAME
		": worker start requested state=%s flags=0x%x timeout_ms=%u seq=%u mode=%s\n",
		rp1h_worker_state_name(RP1H_WORKER_STARTING),
		ctl.flags, ctl.status_timeout_ms, ctl.reserved0[0],
		ctl.flags & RP1H_WORKER_F_EXTERNAL_VSYNC ?
		"external-vsync" : "internal");
	wake_up_interruptible(&hub->waitq);
	return 0;
}

static long rp1h_ioctl_stop_worker(struct rp1h_dev *hub, void __user *argp)
{
	struct rp1h_worker_control ctl;
	int ret;

	memset(&ctl, 0, sizeof(ctl));
	ret = copy_struct_from_user(&ctl, sizeof(ctl), argp, sizeof(ctl));
	if (ret)
		return ret;
	if (ctl.size && ctl.size < sizeof(ctl))
		return -EINVAL;
	if (ctl.flags)
		return -EINVAL;
	if (ctl.status_timeout_ms)
		return -EINVAL;

	mutex_lock(&hub->lock);
	hub->worker_state = RP1H_WORKER_STOPPED;
	hub->worker_flags = 0;
	hub->worker_timeout_ms = 0;
	hub->worker_seq++;
	hub->worker_start_ns = 0;
	hub->last_vsync_ns = 0;
	ctl.reserved0[0] = hub->worker_seq;
	mutex_unlock(&hub->lock);

	pr_info(DRIVER_NAME ": worker stopped state=%s seq=%u\n",
		rp1h_worker_state_name(RP1H_WORKER_STOPPED), ctl.reserved0[0]);
	wake_up_interruptible(&hub->waitq);
	return 0;
}

static long rp1h_ioctl_get_worker_status(struct rp1h_dev *hub, void __user *argp)
{
	struct rp1h_worker_status status;

	memset(&status, 0, sizeof(status));
	mutex_lock(&hub->lock);
	status.size = sizeof(status);
	status.state = rp1h_observed_worker_state_locked(hub);
	status.flags = hub->worker_flags;
	status.status_timeout_ms = hub->worker_timeout_ms;
	status.worker_seq = hub->worker_seq;
	status.vsync_count = hub->vsync_count;
	status.queued_seq = hub->queued_seq;
	status.presented_seq = hub->presented_seq;
	status.displayed_slot = hub->displayed_slot < 0 ? U32_MAX :
				(u32)hub->displayed_slot;
	status.pending_slot = hub->pending_slot < 0 ? U32_MAX :
			      (u32)hub->pending_slot;
	status.frames_queued = hub->frames_queued;
	status.frames_presented = hub->frames_presented;
	status.frames_dropped = hub->frames_dropped;
	status.last_error = hub->last_error;
	status.last_vsync_ns = hub->last_vsync_ns;
	mutex_unlock(&hub->lock);

	if (copy_to_user(argp, &status, sizeof(status)))
		return -EFAULT;

	return 0;
}

static long rp1h_ioctl(struct file *file, unsigned int cmd, unsigned long arg)
{
	struct rp1h_dev *hub = file->private_data;
	void __user *argp = (void __user *)arg;

	switch (cmd) {
	case RP1H_CONFIG:
		return rp1h_ioctl_config(hub, argp);
	case RP1H_PACK_FRAME:
		return rp1h_ioctl_pack_frame(hub, argp);
	case RP1H_GET_STATS:
		return rp1h_ioctl_get_stats(hub, argp);
	case RP1H_QUEUE_FRAME:
		return rp1h_ioctl_queue_frame(hub, argp);
	case RP1H_WAIT_PRESENT:
		return rp1h_ioctl_wait_present(hub, argp);
	case RP1H_SIGNAL_VSYNC:
		return rp1h_ioctl_signal_vsync(hub, argp);
	case RP1H_GET_PRESENT_STATS:
		return rp1h_ioctl_get_present_stats(hub, argp);
	case RP1H_START_WORKER:
		return rp1h_ioctl_start_worker(hub, argp);
	case RP1H_STOP_WORKER:
		return rp1h_ioctl_stop_worker(hub, argp);
	case RP1H_GET_WORKER_STATUS:
		return rp1h_ioctl_get_worker_status(hub, argp);
	default:
		return -ENOTTY;
	}
}

static int rp1h_open(struct inode *inode, struct file *file)
{
	if (!g_rp1h)
		return -ENODEV;

	file->private_data = g_rp1h;
	return nonseekable_open(inode, file);
}

static __poll_t rp1h_poll(struct file *file, poll_table *wait)
{
	struct rp1h_dev *hub = file->private_data;
	__poll_t mask = 0;

	poll_wait(file, &hub->waitq, wait);

	mutex_lock(&hub->lock);
	if (hub->buf && hub->cfg.slot_count) {
		if (rp1h_find_free_slot_locked(hub) >= 0)
			mask |= EPOLLOUT | EPOLLWRNORM;
		if (hub->presented_seq)
			mask |= EPOLLIN | EPOLLRDNORM;
	}
	mutex_unlock(&hub->lock);

	return mask;
}

static int rp1h_mmap(struct file *file, struct vm_area_struct *vma)
{
	struct rp1h_dev *hub = file->private_data;
	unsigned long size = vma->vm_end - vma->vm_start;
	int ret;

	mutex_lock(&hub->lock);
	if (!hub->buf || size > hub->buf_size) {
		ret = -EINVAL;
	} else {
		ret = dma_mmap_coherent(hub->dma_dev, vma, hub->buf,
					 hub->buf_dma, hub->buf_size);
		if (!ret) {
			hub->map_count++;
			vma->vm_private_data = hub;
			vma->vm_ops = &rp1h_vm_ops;
		}
	}
	mutex_unlock(&hub->lock);

	return ret;
}

static void rp1h_vma_open(struct vm_area_struct *vma)
{
	struct rp1h_dev *hub = vma->vm_private_data;

	mutex_lock(&hub->lock);
	hub->map_count++;
	mutex_unlock(&hub->lock);
}

static void rp1h_vma_close(struct vm_area_struct *vma)
{
	struct rp1h_dev *hub = vma->vm_private_data;

	mutex_lock(&hub->lock);
	hub->map_count--;
	mutex_unlock(&hub->lock);
}

static const struct vm_operations_struct rp1h_vm_ops = {
	.open = rp1h_vma_open,
	.close = rp1h_vma_close,
};

static const struct file_operations rp1h_fops = {
	.owner = THIS_MODULE,
	.open = rp1h_open,
	.unlocked_ioctl = rp1h_ioctl,
	.compat_ioctl = compat_ptr_ioctl,
	.poll = rp1h_poll,
	.mmap = rp1h_mmap,
	.llseek = noop_llseek,
};

static int __init rp1h_init(void)
{
	struct rp1h_dev *hub;
	int ret;

	hub = kzalloc(sizeof(*hub), GFP_KERNEL);
	if (!hub)
		return -ENOMEM;

	mutex_init(&hub->lock);
	init_waitqueue_head(&hub->waitq);
	hub->dma_dev = rp1h_find_dma_device();
	if (!hub->dma_dev) {
		pr_err(DRIVER_NAME ": failed to find RP1 DMA device\n");
		kfree(hub);
		return -EPROBE_DEFER;
	}
	hub->displayed_slot = -1;
	hub->pending_slot = -1;
	hub->miscdev.minor = MISC_DYNAMIC_MINOR;
	hub->miscdev.name = RP1H_DEVICE_NAME;
	hub->miscdev.fops = &rp1h_fops;

	g_rp1h = hub;
	ret = misc_register(&hub->miscdev);
	if (ret) {
		put_device(hub->dma_dev);
		g_rp1h = NULL;
		kfree(hub);
		return ret;
	}

	pr_info(DRIVER_NAME ": registered /dev/%s dma_dev=%s\n",
		hub->miscdev.name, dev_name(hub->dma_dev));
	return 0;
}

static void __exit rp1h_exit(void)
{
	struct rp1h_dev *hub = g_rp1h;

	if (!hub)
		return;

	pr_info(DRIVER_NAME
		": unregistering packed=%u queued=%u presented=%u dropped=%u vsync=%u last_error=%d\n",
		hub->frames_packed, hub->frames_queued, hub->frames_presented,
		hub->frames_dropped, hub->vsync_count, (int)hub->last_error);
	misc_deregister(&hub->miscdev);
	rp1h_free_buffer(hub);
	put_device(hub->dma_dev);
	kfree(hub);
	g_rp1h = NULL;
}

module_init(rp1h_init);
module_exit(rp1h_exit);

MODULE_AUTHOR("Raspberry Pi RP1 HUB75 contributors");
MODULE_DESCRIPTION("RP1 HUB75 frame packer");
MODULE_LICENSE("GPL v2");

#if IS_ENABLED(CONFIG_KUNIT)

static void rp1h_kunit_validate_default_rio32_config(struct kunit *test)
{
	struct rp1h_config cfg = {
		.mapping = RP1H_MAPPING_ADAFRUIT_HAT_PWM,
		.format = RP1H_FORMAT_RGB888,
		.stream_format = RP1H_STREAM_RIO32,
	};
	u32 expected_words_per_row_plane = RP1H_DEFAULT_COLS * RP1H_WORDS_PER_PIXEL +
					   RP1H_TRAILER_WORDS;
	u32 expected_words = (RP1H_DEFAULT_ROWS / 2) * RP1H_DEFAULT_PWM_BITS *
			     expected_words_per_row_plane;

	KUNIT_ASSERT_EQ(test, 0, rp1h_validate_config(&cfg));
	KUNIT_EXPECT_EQ(test, (u16)RP1H_DEFAULT_COLS, cfg.cols);
	KUNIT_EXPECT_EQ(test, (u16)RP1H_DEFAULT_ROWS, cfg.rows);
	KUNIT_EXPECT_EQ(test, (u8)RP1H_DEFAULT_PWM_BITS, cfg.pwm_bits);
	KUNIT_EXPECT_EQ(test, 1U, cfg.panel_count);
	KUNIT_EXPECT_EQ(test, 1U, cfg.lane_count);
	KUNIT_EXPECT_EQ(test, 1U, cfg.chain_length);
	KUNIT_EXPECT_EQ(test, 5U, cfg.addr_line_count);
	KUNIT_EXPECT_EQ(test, expected_words_per_row_plane, cfg.words_per_row_plane);
	KUNIT_EXPECT_EQ(test, expected_words_per_row_plane * sizeof(u32),
			cfg.bytes_per_row_plane);
	KUNIT_EXPECT_EQ(test, 768U, cfg.bytes_per_row_plane_aligned);
	KUNIT_EXPECT_EQ(test, 192U, cfg.words_per_row_plane_aligned);
	KUNIT_EXPECT_EQ(test, expected_words, cfg.words_per_frame);
	KUNIT_EXPECT_EQ(test, RP1H_DEFAULT_COLS * RP1H_DEFAULT_ROWS * 3,
			cfg.frame_bytes);
	KUNIT_EXPECT_EQ(test, PAGE_ALIGN(sizeof(struct rp1h_mmap_header)),
			cfg.words_offset);
	KUNIT_EXPECT_EQ(test,
			(u32)PAGE_ALIGN(cfg.words_offset + cfg.words_per_frame *
					 sizeof(u32)),
			cfg.mmap_size);
}

static void rp1h_kunit_validate_rejects_unsupported_panel_stream(struct kunit *test)
{
	struct rp1h_config cfg = {
		.cols = 64,
		.rows = 64,
		.pwm_bits = 8,
		.mapping = RP1H_MAPPING_ADAFRUIT_HAT_PWM,
		.format = RP1H_FORMAT_RGB888,
		.stream_format = RP1H_STREAM_RIO32,
		.panel_count = 2,
	};

	KUNIT_EXPECT_EQ(test, -EINVAL, rp1h_validate_config(&cfg));

	cfg.stream_format = RP1H_STREAM_RGB6_PACKED;
	KUNIT_EXPECT_EQ(test, 0, rp1h_validate_config(&cfg));
	KUNIT_EXPECT_EQ(test, 2U, cfg.lane_count);
	KUNIT_EXPECT_EQ(test, 1U, cfg.chain_length);
}

static void rp1h_kunit_validate_rejects_ambiguous_topology(struct kunit *test)
{
	struct rp1h_config cfg = {
		.cols = 64,
		.rows = 64,
		.pwm_bits = 8,
		.mapping = RP1H_MAPPING_ADAFRUIT_HAT_PWM,
		.format = RP1H_FORMAT_RGB888,
		.stream_format = RP1H_STREAM_RGB6_PACKED,
		.panel_count = 4,
		.lane_count = 2,
		.chain_length = 2,
	};

	KUNIT_EXPECT_EQ(test, -EINVAL, rp1h_validate_config(&cfg));

	cfg.chain_length = 1;
	KUNIT_EXPECT_EQ(test, -EINVAL, rp1h_validate_config(&cfg));

	cfg.lane_count = 4;
	cfg.addr_line_count = 4;
	KUNIT_EXPECT_EQ(test, -EINVAL, rp1h_validate_config(&cfg));
}

static void rp1h_kunit_validate_e_line_requires_64_rows(struct kunit *test)
{
	struct rp1h_config cfg = {
		.cols = 64,
		.rows = 32,
		.pwm_bits = 8,
		.mapping = RP1H_MAPPING_ADAFRUIT_HAT_PWM,
		.format = RP1H_FORMAT_RGB888,
		.stream_format = RP1H_STREAM_STATE32,
		.flags = RP1H_F_E_LINE_PRESENT,
	};

	KUNIT_EXPECT_EQ(test, -EINVAL, rp1h_validate_config(&cfg));
}

static void rp1h_kunit_validate_rejects_unknown_flags(struct kunit *test)
{
	struct rp1h_config cfg = {
		.cols = 64,
		.rows = 64,
		.pwm_bits = 8,
		.mapping = RP1H_MAPPING_ADAFRUIT_HAT_PWM,
		.format = RP1H_FORMAT_RGB888,
		.stream_format = RP1H_STREAM_STATE32,
		.flags = BIT(1),
	};

	KUNIT_EXPECT_EQ(test, -EINVAL, rp1h_validate_config(&cfg));
}

static void rp1h_kunit_validate_queue_slots(struct kunit *test)
{
	struct rp1h_config cfg = {
		.cols = 64,
		.rows = 64,
		.pwm_bits = 8,
		.mapping = RP1H_MAPPING_ADAFRUIT_HAT_PWM,
		.format = RP1H_FORMAT_RGB888,
		.stream_format = RP1H_STREAM_STATE32,
	};
	u32 dense_mmap_size;

	KUNIT_ASSERT_EQ(test, 0, rp1h_validate_config(&cfg));
	dense_mmap_size = cfg.mmap_size;

	memset(&cfg, 0, sizeof(cfg));
	cfg.cols = 64;
	cfg.rows = 64;
	cfg.pwm_bits = 8;
	cfg.mapping = RP1H_MAPPING_ADAFRUIT_HAT_PWM;
	cfg.format = RP1H_FORMAT_RGB888;
	cfg.stream_format = RP1H_STREAM_STATE32;
	cfg.slot_count = 2;
	KUNIT_ASSERT_EQ(test, 0, rp1h_validate_config(&cfg));
	KUNIT_EXPECT_EQ(test, 2U, cfg.slot_count);
	KUNIT_EXPECT_EQ(test, (u32)PAGE_ALIGN(cfg.words_per_frame * sizeof(u32)),
			cfg.slot_stride_bytes);
	KUNIT_EXPECT_TRUE(test, cfg.mmap_size > dense_mmap_size);

	cfg.slot_stride_bytes = 256;
	KUNIT_EXPECT_EQ(test, -EINVAL, rp1h_validate_config(&cfg));

	cfg.slot_stride_bytes = 0;
	cfg.slot_count = 3;
	KUNIT_EXPECT_EQ(test, -EINVAL, rp1h_validate_config(&cfg));

	cfg.slot_count = 4;
	KUNIT_EXPECT_EQ(test, -EINVAL, rp1h_validate_config(&cfg));

	cfg.slot_count = 2;
	cfg.dwell_shift_limit = RP1H_MAX_PWM_BITS;
	KUNIT_EXPECT_EQ(test, -EINVAL, rp1h_validate_config(&cfg));
}

static void rp1h_kunit_validate_rejects_unknown_abi_selectors(struct kunit *test)
{
	struct rp1h_config cfg = {
		.cols = 64,
		.rows = 64,
		.pwm_bits = 8,
		.mapping = RP1H_MAPPING_ADAFRUIT_HAT_PWM,
		.format = RP1H_FORMAT_RGB888,
		.stream_format = RP1H_STREAM_STATE32,
	};

	cfg.mapping = 99;
	KUNIT_EXPECT_EQ(test, -EINVAL, rp1h_validate_config(&cfg));

	cfg.mapping = RP1H_MAPPING_ADAFRUIT_HAT_PWM;
	cfg.format = 1;
	KUNIT_EXPECT_EQ(test, -EINVAL, rp1h_validate_config(&cfg));

	cfg.format = RP1H_FORMAT_RGB888;
	cfg.stream_format = 99;
	KUNIT_EXPECT_EQ(test, -EINVAL, rp1h_validate_config(&cfg));
}

static void rp1h_kunit_validate_rgb6_byte_multi_panel_geometry(struct kunit *test)
{
	struct rp1h_config cfg = {
		.cols = 64,
		.rows = 64,
		.pwm_bits = 11,
		.mapping = RP1H_MAPPING_ADAFRUIT_HAT_PWM,
		.format = RP1H_FORMAT_RGB888,
		.stream_format = RP1H_STREAM_RGB6_BYTE,
		.panel_count = 4,
		.flags = RP1H_F_E_LINE_PRESENT,
	};
	u32 expected_words_per_row_plane = 64;
	u32 expected_words = (cfg.rows / 2) * cfg.pwm_bits *
			     expected_words_per_row_plane;

	KUNIT_ASSERT_EQ(test, 0, rp1h_validate_config(&cfg));
	KUNIT_EXPECT_EQ(test, 8U, cfg.bits_per_pixel);
	KUNIT_EXPECT_EQ(test, 4U, cfg.panel_count);
	KUNIT_EXPECT_EQ(test, 4U, cfg.lane_count);
	KUNIT_EXPECT_EQ(test, 1U, cfg.chain_length);
	KUNIT_EXPECT_EQ(test, 5U, cfg.addr_line_count);
	KUNIT_EXPECT_EQ(test, expected_words_per_row_plane,
			cfg.words_per_row_plane);
	KUNIT_EXPECT_EQ(test, expected_words_per_row_plane * sizeof(u32),
			cfg.bytes_per_row_plane);
	KUNIT_EXPECT_EQ(test, 256U, cfg.bytes_per_row_plane_aligned);
	KUNIT_EXPECT_EQ(test, 64U, cfg.words_per_row_plane_aligned);
	KUNIT_EXPECT_EQ(test, expected_words, cfg.words_per_frame);
	KUNIT_EXPECT_EQ(test, 64U * 64U * 3U * 4U, cfg.frame_bytes);
}

static void rp1h_kunit_validate_rgb6_packed_multi_panel_geometry(struct kunit *test)
{
	struct rp1h_config cfg = {
		.cols = 64,
		.rows = 64,
		.pwm_bits = 11,
		.mapping = RP1H_MAPPING_ADAFRUIT_HAT_PWM,
		.format = RP1H_FORMAT_RGB888,
		.stream_format = RP1H_STREAM_RGB6_PACKED,
		.panel_count = 4,
		.flags = RP1H_F_E_LINE_PRESENT,
	};
	u32 expected_words_per_row_plane = 48;
	u32 expected_words = (cfg.rows / 2) * cfg.pwm_bits *
			     expected_words_per_row_plane;

	KUNIT_ASSERT_EQ(test, 0, rp1h_validate_config(&cfg));
	KUNIT_EXPECT_EQ(test, 6U, cfg.bits_per_pixel);
	KUNIT_EXPECT_EQ(test, 4U, cfg.panel_count);
	KUNIT_EXPECT_EQ(test, 4U, cfg.lane_count);
	KUNIT_EXPECT_EQ(test, 1U, cfg.chain_length);
	KUNIT_EXPECT_EQ(test, 5U, cfg.addr_line_count);
	KUNIT_EXPECT_EQ(test, expected_words_per_row_plane,
			cfg.words_per_row_plane);
	KUNIT_EXPECT_EQ(test, expected_words_per_row_plane * sizeof(u32),
			cfg.bytes_per_row_plane);
	KUNIT_EXPECT_EQ(test, 256U, cfg.bytes_per_row_plane_aligned);
	KUNIT_EXPECT_EQ(test, 64U, cfg.words_per_row_plane_aligned);
	KUNIT_EXPECT_EQ(test, expected_words, cfg.words_per_frame);
	KUNIT_EXPECT_EQ(test, 64U * 64U * 3U * 4U, cfg.frame_bytes);
}

static void rp1h_kunit_validate_rejects_invalid_geometry(struct kunit *test)
{
	struct rp1h_config cfg = {
		.cols = 48,
		.rows = 64,
		.pwm_bits = 8,
		.mapping = RP1H_MAPPING_ADAFRUIT_HAT_PWM,
		.format = RP1H_FORMAT_RGB888,
		.stream_format = RP1H_STREAM_STATE32,
	};

	KUNIT_EXPECT_EQ(test, -EINVAL, rp1h_validate_config(&cfg));

	cfg.cols = 64;
	cfg.rows = 48;
	KUNIT_EXPECT_EQ(test, -EINVAL, rp1h_validate_config(&cfg));

	cfg.rows = 64;
	cfg.pwm_bits = RP1H_MAX_PWM_BITS + 1;
	KUNIT_EXPECT_EQ(test, -EINVAL, rp1h_validate_config(&cfg));

	cfg.pwm_bits = 8;
	cfg.panel_count = RP1H_MAX_PANELS + 1;
	KUNIT_EXPECT_EQ(test, -EINVAL, rp1h_validate_config(&cfg));
}

static void rp1h_kunit_addr_mask_sets_e_for_upper_rows(struct kunit *test)
{
	KUNIT_EXPECT_EQ(test, RP1H_PIN(RP1H_GPIO_E), rp1h_addr_mask(16));
	KUNIT_EXPECT_EQ(test,
			RP1H_PIN(RP1H_GPIO_A) |
			RP1H_PIN(RP1H_GPIO_B) |
			RP1H_PIN(RP1H_GPIO_C) |
			RP1H_PIN(RP1H_GPIO_D) |
			RP1H_PIN(RP1H_GPIO_E),
			rp1h_addr_mask(31));
}

static void rp1h_kunit_rgb_helpers_apply_cie1931_bitplanes(struct kunit *test)
{
	struct rp1h_dev hub = {
		.cfg = {
			.pwm_bits = 11,
		},
	};
	u8 top[3] = { 0x80, 0x80, 0x80 };
	u8 bottom[3] = { 0x80, 0x80, 0x80 };

	KUNIT_EXPECT_EQ(test, 380U, (u32)rp1h_cie1931_11bit[0x80]);
	KUNIT_EXPECT_EQ(test,
			RP1H_PIN(RP1H_GPIO_R1) |
			RP1H_PIN(RP1H_GPIO_G1) |
			RP1H_PIN(RP1H_GPIO_B1) |
			RP1H_PIN(RP1H_GPIO_R2) |
			RP1H_PIN(RP1H_GPIO_G2) |
			RP1H_PIN(RP1H_GPIO_B2),
			rp1h_rgb_mask(&hub, top, bottom, 8));
	KUNIT_EXPECT_EQ(test, 0x3fU,
			rp1h_rgb6_bits(&hub, top, bottom, 8));
	KUNIT_EXPECT_EQ(test, 0U,
			rp1h_rgb6_bits(&hub, top, bottom, 9));
}

static void rp1h_kunit_write_header_exports_geometry(struct kunit *test)
{
	struct rp1h_dev hub = {
		.cfg = {
			.cols = 64,
			.rows = 64,
			.pwm_bits = 4,
			.mapping = RP1H_MAPPING_ADAFRUIT_HAT_PWM,
			.format = RP1H_FORMAT_RGB888,
			.stream_format = RP1H_STREAM_RGB6_PACKED,
			.panel_count = 2,
		},
		.frames_packed = 7,
	};
	struct rp1h_mmap_header *hdr;
	int ret;

	ret = rp1h_validate_config(&hub.cfg);
	KUNIT_ASSERT_EQ(test, 0, ret);

	hub.buf = kunit_kzalloc(test, hub.cfg.mmap_size, GFP_KERNEL);
	KUNIT_ASSERT_NOT_ERR_OR_NULL(test, hub.buf);

	rp1h_write_header(&hub);
	hdr = hub.buf;

	KUNIT_EXPECT_EQ(test, RP1H_MAGIC, hdr->magic);
	KUNIT_EXPECT_EQ(test, RP1H_VERSION, hdr->version);
	KUNIT_EXPECT_EQ(test, (u16)sizeof(*hdr), hdr->header_size);
	KUNIT_EXPECT_EQ(test, hub.frames_packed, hdr->frame_seq);
	KUNIT_EXPECT_EQ(test, hub.cfg.words_offset, hdr->words_offset);
	KUNIT_EXPECT_EQ(test, hub.cfg.words_per_frame, hdr->words_per_frame);
	KUNIT_EXPECT_EQ(test, hub.cfg.stream_format, hdr->stream_format);
	KUNIT_EXPECT_EQ(test, hub.cfg.bits_per_pixel, hdr->bits_per_pixel);
	KUNIT_EXPECT_EQ(test, hub.cfg.panel_count, hdr->panel_count);
	KUNIT_EXPECT_EQ(test, hub.cfg.lane_count, hdr->lane_count);
	KUNIT_EXPECT_EQ(test, hub.cfg.chain_length, hdr->chain_length);
	KUNIT_EXPECT_EQ(test, hub.cfg.addr_line_count, hdr->addr_line_count);
	KUNIT_EXPECT_EQ(test, hub.cfg.words_per_row_plane, hdr->words_per_row_plane);
	KUNIT_EXPECT_EQ(test, hub.cfg.bytes_per_row_plane, hdr->bytes_per_row_plane);
	KUNIT_EXPECT_EQ(test, hub.cfg.words_per_row_plane_aligned,
			hdr->words_per_row_plane_aligned);
	KUNIT_EXPECT_EQ(test, hub.cfg.bytes_per_row_plane_aligned,
			hdr->bytes_per_row_plane_aligned);
	KUNIT_EXPECT_EQ(test, 0U, hdr->slot_count);
	KUNIT_EXPECT_EQ(test, 0U, hdr->slot_stride_bytes);
	KUNIT_EXPECT_EQ(test, 0U, hdr->producer_head);
	KUNIT_EXPECT_EQ(test, 0U, hdr->consumer_tail);
	KUNIT_EXPECT_EQ(test, RP1H_PIN(RP1H_GPIO_A), hdr->pin_a);
	KUNIT_EXPECT_EQ(test, RP1H_PIN(RP1H_GPIO_E), hdr->pin_e);
	KUNIT_EXPECT_EQ(test, 1U, hdr->dwell[0]);
	KUNIT_EXPECT_EQ(test, 2U, hdr->dwell[1]);
	KUNIT_EXPECT_EQ(test, 4U, hdr->dwell[2]);
	KUNIT_EXPECT_EQ(test, 8U, hdr->dwell[3]);
}

static void rp1h_kunit_choose_queue_slot_prefers_free_slot(struct kunit *test)
{
	struct rp1h_dev hub = {
		.displayed_slot = 0,
		.pending_slot = -1,
	};
	bool replaced_pending;
	int slot;

	hub.cfg.slot_count = 2;
	slot = rp1h_choose_queue_slot_locked(&hub, 0, &replaced_pending);

	KUNIT_EXPECT_EQ(test, 1, slot);
	KUNIT_EXPECT_FALSE(test, replaced_pending);
}

static void rp1h_kunit_choose_queue_slot_reuses_pending_when_requested(struct kunit *test)
{
	struct rp1h_dev hub = {
		.displayed_slot = 0,
		.pending_slot = 1,
	};
	bool replaced_pending;
	int slot;

	hub.cfg.slot_count = 2;
	slot = rp1h_choose_queue_slot_locked(&hub,
					     RP1H_QUEUE_F_REPLACE_PENDING,
					     &replaced_pending);

	KUNIT_EXPECT_EQ(test, 1, slot);
	KUNIT_EXPECT_TRUE(test, replaced_pending);
}

static void rp1h_kunit_choose_queue_slot_does_not_replace_displayed_frame(struct kunit *test)
{
	struct rp1h_dev hub = {
		.displayed_slot = 0,
		.pending_slot = -1,
	};
	bool replaced_pending;
	int slot;

	hub.cfg.slot_count = 1;
	slot = rp1h_choose_queue_slot_locked(&hub,
					     RP1H_QUEUE_F_REPLACE_PENDING,
					     &replaced_pending);

	KUNIT_EXPECT_EQ(test, -1, slot);
	KUNIT_EXPECT_FALSE(test, replaced_pending);
}

static void rp1h_kunit_signal_vsync_promotes_pending_frame(struct kunit *test)
{
	struct rp1h_dev hub = {
		.displayed_slot = 0,
		.pending_slot = 1,
		.pending_seq = 9,
		.presented_seq = 7,
	};
	struct rp1h_vsync vsync;

	memset(&vsync, 0, sizeof(vsync));
	rp1h_signal_vsync_locked(&hub, &vsync);

	KUNIT_EXPECT_EQ(test, 1U, hub.vsync_count);
	KUNIT_EXPECT_EQ(test, 1U, hub.frames_presented);
	KUNIT_EXPECT_EQ(test, 1, hub.displayed_slot);
	KUNIT_EXPECT_EQ(test, -1, hub.pending_slot);
	KUNIT_EXPECT_EQ(test, 0U, hub.pending_seq);
	KUNIT_EXPECT_EQ(test, 9U, hub.presented_seq);
	KUNIT_EXPECT_EQ(test, 9U, vsync.presented_seq);
	KUNIT_EXPECT_EQ(test, 1U, vsync.displayed_slot);
}

static void rp1h_kunit_signal_vsync_without_pending_preserves_display_state(struct kunit *test)
{
	struct rp1h_dev hub = {
		.displayed_slot = -1,
		.pending_slot = -1,
		.pending_seq = 0,
		.presented_seq = 7,
		.frames_presented = 3,
	};
	struct rp1h_vsync vsync;

	memset(&vsync, 0, sizeof(vsync));
	rp1h_signal_vsync_locked(&hub, &vsync);

	KUNIT_EXPECT_EQ(test, 1U, hub.vsync_count);
	KUNIT_EXPECT_EQ(test, 3U, hub.frames_presented);
	KUNIT_EXPECT_EQ(test, -1, hub.displayed_slot);
	KUNIT_EXPECT_EQ(test, -1, hub.pending_slot);
	KUNIT_EXPECT_EQ(test, 0U, hub.pending_seq);
	KUNIT_EXPECT_EQ(test, 7U, hub.presented_seq);
	KUNIT_EXPECT_EQ(test, 7U, vsync.presented_seq);
	KUNIT_EXPECT_EQ(test, U32_MAX, vsync.displayed_slot);
}

static void rp1h_kunit_queue_has_space_tracks_slot_availability(struct kunit *test)
{
	struct rp1h_dev hub = {
		.displayed_slot = 0,
		.pending_slot = -1,
	};

	mutex_init(&hub.lock);

	KUNIT_EXPECT_TRUE(test, rp1h_queue_has_space(&hub));

	hub.buf = &hub;
	hub.cfg.slot_count = 2;
	KUNIT_EXPECT_TRUE(test, rp1h_queue_has_space(&hub));

	hub.pending_slot = 1;
	KUNIT_EXPECT_FALSE(test, rp1h_queue_has_space(&hub));

	hub.cfg.slot_count = 0;
	KUNIT_EXPECT_TRUE(test, rp1h_queue_has_space(&hub));
}

static void rp1h_kunit_ready_tracks_presented_sequence(struct kunit *test)
{
	struct rp1h_dev hub = {
		.presented_seq = 4,
	};

	mutex_init(&hub.lock);

	KUNIT_EXPECT_TRUE(test, rp1h_ready(&hub, 5));

	hub.buf = &hub;
	hub.cfg.slot_count = 2;
	KUNIT_EXPECT_TRUE(test, rp1h_ready(&hub, 4));
	KUNIT_EXPECT_FALSE(test, rp1h_ready(&hub, 5));

	hub.presented_seq = 5;
	KUNIT_EXPECT_TRUE(test, rp1h_ready(&hub, 5));

	hub.cfg.slot_count = 0;
	KUNIT_EXPECT_TRUE(test, rp1h_ready(&hub, 6));
}

static void rp1h_kunit_write_header_exports_queue_progress(struct kunit *test)
{
	struct rp1h_dev hub = {
		.cfg = {
			.cols = 64,
			.rows = 64,
			.pwm_bits = 4,
			.mapping = RP1H_MAPPING_ADAFRUIT_HAT_PWM,
			.format = RP1H_FORMAT_RGB888,
			.stream_format = RP1H_STREAM_STATE32,
			.slot_count = 2,
		},
		.frames_packed = 12,
		.queued_seq = 11,
		.presented_seq = 10,
		.pending_slot = 1,
		.displayed_slot = 0,
	};
	struct rp1h_mmap_header *hdr;
	int ret;

	ret = rp1h_validate_config(&hub.cfg);
	KUNIT_ASSERT_EQ(test, 0, ret);

	hub.buf = kunit_kzalloc(test, hub.cfg.mmap_size, GFP_KERNEL);
	KUNIT_ASSERT_NOT_ERR_OR_NULL(test, hub.buf);

	rp1h_write_header(&hub);
	hdr = hub.buf;

	KUNIT_EXPECT_EQ(test, 2U, hdr->slot_count);
	KUNIT_EXPECT_EQ(test, hub.cfg.slot_stride_bytes, hdr->slot_stride_bytes);
	KUNIT_EXPECT_EQ(test, 12U, hdr->frame_seq);
	KUNIT_EXPECT_EQ(test, 11U, hdr->producer_head);
	KUNIT_EXPECT_EQ(test, 10U, hdr->consumer_tail);
}

static void rp1h_kunit_pack_rio32_toggles_clk_and_lat(struct kunit *test)
{
	struct rp1h_dev hub = {
		.cfg = {
			.cols = 4,
			.rows = 16,
			.pwm_bits = 1,
			.mapping = RP1H_MAPPING_ADAFRUIT_HAT_PWM,
			.format = RP1H_FORMAT_RGB888,
			.stream_format = RP1H_STREAM_RIO32,
		},
	};
	u8 *frame;
	u32 *words;
	u32 base = RP1H_PIN(RP1H_GPIO_OE);
	u32 rgb = RP1H_PIN(RP1H_GPIO_R1) | RP1H_PIN(RP1H_GPIO_B2);
	int ret;

	ret = rp1h_validate_config(&hub.cfg);
	KUNIT_ASSERT_EQ(test, 0, ret);

	hub.buf = kunit_kzalloc(test, hub.cfg.mmap_size, GFP_KERNEL);
	frame = kunit_kzalloc(test, hub.cfg.frame_bytes, GFP_KERNEL);
	KUNIT_ASSERT_NOT_ERR_OR_NULL(test, hub.buf);
	KUNIT_ASSERT_NOT_ERR_OR_NULL(test, frame);

	frame[0] = 0xff;
	frame[((hub.cfg.rows / 2) * hub.cfg.cols * 3) + 2] = 0xff;

	rp1h_pack_rgb888(&hub, rp1h_legacy_frame(&hub), frame);
	words = hub.buf + hub.cfg.words_offset;

	KUNIT_EXPECT_EQ(test, base | rgb, words[0]);
	KUNIT_EXPECT_EQ(test, base | rgb | RP1H_PIN(RP1H_GPIO_CLK), words[1]);
	KUNIT_EXPECT_EQ(test, base | RP1H_PIN(RP1H_GPIO_LAT), words[8]);
	KUNIT_EXPECT_EQ(test, base, words[9]);
}

static void rp1h_kunit_pack_rio32_row16_sets_e_addr_bit(struct kunit *test)
{
	struct rp1h_dev hub = {
		.cfg = {
			.cols = 2,
			.rows = 64,
			.pwm_bits = 1,
			.mapping = RP1H_MAPPING_ADAFRUIT_HAT_PWM,
			.format = RP1H_FORMAT_RGB888,
			.stream_format = RP1H_STREAM_RIO32,
			.flags = RP1H_F_E_LINE_PRESENT,
		},
	};
	u8 *frame;
	u32 *words;
	u32 row16_base = RP1H_PIN(RP1H_GPIO_OE) | RP1H_PIN(RP1H_GPIO_E);
	u32 row16_offset;
	int ret;

	ret = rp1h_validate_config(&hub.cfg);
	KUNIT_ASSERT_EQ(test, 0, ret);

	hub.buf = kunit_kzalloc(test, hub.cfg.mmap_size, GFP_KERNEL);
	frame = kunit_kzalloc(test, hub.cfg.frame_bytes, GFP_KERNEL);
	KUNIT_ASSERT_NOT_ERR_OR_NULL(test, hub.buf);
	KUNIT_ASSERT_NOT_ERR_OR_NULL(test, frame);

	rp1h_pack_rgb888(&hub, rp1h_legacy_frame(&hub), frame);
	words = hub.buf + hub.cfg.words_offset;
	row16_offset = 16 * hub.cfg.words_per_row_plane;

	KUNIT_EXPECT_EQ(test, row16_base, words[row16_offset]);
	KUNIT_EXPECT_EQ(test, row16_base | RP1H_PIN(RP1H_GPIO_CLK),
			words[row16_offset + 1]);
	KUNIT_EXPECT_EQ(test, row16_base | RP1H_PIN(RP1H_GPIO_LAT),
			words[row16_offset + 4]);
	KUNIT_EXPECT_EQ(test, row16_base, words[row16_offset + 5]);
}

static void rp1h_kunit_pack_state32_is_data_only(struct kunit *test)
{
	struct rp1h_dev hub = {
		.cfg = {
			.cols = 4,
			.rows = 16,
			.pwm_bits = 1,
			.mapping = RP1H_MAPPING_ADAFRUIT_HAT_PWM,
			.format = RP1H_FORMAT_RGB888,
			.stream_format = RP1H_STREAM_STATE32,
		},
	};
	u8 *frame;
	u32 *words;
	u32 base = RP1H_PIN(RP1H_GPIO_OE);
	u32 rgb = RP1H_PIN(RP1H_GPIO_G1) | RP1H_PIN(RP1H_GPIO_R2);
	int ret;

	ret = rp1h_validate_config(&hub.cfg);
	KUNIT_ASSERT_EQ(test, 0, ret);

	hub.buf = kunit_kzalloc(test, hub.cfg.mmap_size, GFP_KERNEL);
	frame = kunit_kzalloc(test, hub.cfg.frame_bytes, GFP_KERNEL);
	KUNIT_ASSERT_NOT_ERR_OR_NULL(test, hub.buf);
	KUNIT_ASSERT_NOT_ERR_OR_NULL(test, frame);

	frame[1] = 0xff;
	frame[(hub.cfg.rows / 2) * hub.cfg.cols * 3] = 0xff;

	rp1h_pack_rgb888_state32(&hub, rp1h_legacy_frame(&hub), frame);
	words = hub.buf + hub.cfg.words_offset;

	KUNIT_EXPECT_EQ(test, base | rgb, words[0]);
	KUNIT_EXPECT_EQ(test, base, words[1]);
	KUNIT_EXPECT_EQ(test, base, words[2]);
	KUNIT_EXPECT_EQ(test, base, words[3]);
}

static void rp1h_kunit_pack_state32_is_row_major(struct kunit *test)
{
	struct rp1h_dev hub = {
		.cfg = {
			.cols = 2,
			.rows = 4,
			.pwm_bits = 2,
			.mapping = RP1H_MAPPING_ADAFRUIT_HAT_PWM,
			.format = RP1H_FORMAT_RGB888,
			.stream_format = RP1H_STREAM_STATE32,
		},
	};
	u8 *frame;
	u32 *words;
	u32 oe = RP1H_PIN(RP1H_GPIO_OE);
	u32 row1 = oe | RP1H_PIN(RP1H_GPIO_A);
	int ret;

	ret = rp1h_validate_config(&hub.cfg);
	KUNIT_ASSERT_EQ(test, 0, ret);

	hub.buf = kunit_kzalloc(test, hub.cfg.mmap_size, GFP_KERNEL);
	frame = kunit_kzalloc(test, hub.cfg.frame_bytes, GFP_KERNEL);
	KUNIT_ASSERT_NOT_ERR_OR_NULL(test, hub.buf);
	KUNIT_ASSERT_NOT_ERR_OR_NULL(test, frame);

	frame[0] = 1;
	frame[3] = 2;
	frame[(hub.cfg.cols * 3) + 1] = 1;
	frame[(hub.cfg.cols * 3) + 4] = 2;

	rp1h_pack_rgb888_state32(&hub, rp1h_legacy_frame(&hub), frame);
	words = hub.buf + hub.cfg.words_offset;

	KUNIT_EXPECT_EQ(test, oe | RP1H_PIN(RP1H_GPIO_R1), words[0]);
	KUNIT_EXPECT_EQ(test, oe, words[1]);
	KUNIT_EXPECT_EQ(test, oe, words[2]);
	KUNIT_EXPECT_EQ(test, oe | RP1H_PIN(RP1H_GPIO_R1), words[3]);
	KUNIT_EXPECT_EQ(test, row1 | RP1H_PIN(RP1H_GPIO_G1), words[4]);
	KUNIT_EXPECT_EQ(test, row1, words[5]);
	KUNIT_EXPECT_EQ(test, row1, words[6]);
	KUNIT_EXPECT_EQ(test, row1 | RP1H_PIN(RP1H_GPIO_G1), words[7]);
}

static void rp1h_kunit_pack_regular_state32_uses_two_active_lanes(struct kunit *test)
{
	struct rp1h_dev hub = {
		.cfg = {
			.cols = 2,
			.rows = 4,
			.pwm_bits = 1,
			.mapping = RP1H_MAPPING_REGULAR,
			.format = RP1H_FORMAT_RGB888,
			.stream_format = RP1H_STREAM_STATE32,
			.panel_count = 4,
			.lane_count = 2,
			.chain_length = 2,
		},
	};
	u8 *frame;
	u32 *words;
	u32 oe = RP1H_PIN(rp1h_electrodragon_p0_pinout.oe);
	u32 active_cols;
	u32 input_cols;
	int ret;

	ret = rp1h_validate_config(&hub.cfg);
	KUNIT_ASSERT_EQ(test, 0, ret);
	KUNIT_EXPECT_EQ(test, 4U, hub.cfg.words_per_row_plane);

	hub.buf = kunit_kzalloc(test, hub.cfg.mmap_size, GFP_KERNEL);
	frame = kunit_kzalloc(test, hub.cfg.frame_bytes, GFP_KERNEL);
	KUNIT_ASSERT_NOT_ERR_OR_NULL(test, hub.buf);
	KUNIT_ASSERT_NOT_ERR_OR_NULL(test, frame);

	active_cols = hub.cfg.cols * hub.cfg.chain_length;
	input_cols = active_cols * hub.cfg.lane_count;
	frame[0] = 0xff;
	frame[((hub.cfg.rows / 2) * input_cols + 1) * 3 + 1] = 0xff;
	frame[(active_cols + 2) * 3 + 2] = 0xff;
	frame[((hub.cfg.rows / 2) * input_cols + active_cols + 3) * 3] = 0xff;

	rp1h_pack_rgb888_state32(&hub, rp1h_legacy_frame(&hub), frame);
	words = hub.buf + hub.cfg.words_offset;

	KUNIT_EXPECT_EQ(test, oe | RP1H_PIN(rp1h_electrodragon_p0_pinout.r1),
			words[0]);
	KUNIT_EXPECT_EQ(test, oe | RP1H_PIN(rp1h_electrodragon_p0_pinout.g2),
			words[1]);
	KUNIT_EXPECT_EQ(test, oe | RP1H_PIN(RP1H_REGULAR_P1_B1), words[2]);
	KUNIT_EXPECT_EQ(test, oe | RP1H_PIN(RP1H_REGULAR_P1_R2), words[3]);
}

static void rp1h_kunit_regular_mapping_matches_hzeller(struct kunit *test)
{
	const struct rp1h_pinout *regular =
		rp1h_pinout_for_mapping(RP1H_MAPPING_REGULAR);

	KUNIT_ASSERT_NOT_ERR_OR_NULL(test, regular);

	KUNIT_EXPECT_EQ(test, RP1H_HZELLER_REGULAR_P0_R1, regular->r1);
	KUNIT_EXPECT_EQ(test, RP1H_HZELLER_REGULAR_P0_G1, regular->g1);
	KUNIT_EXPECT_EQ(test, RP1H_HZELLER_REGULAR_P0_B1, regular->b1);
	KUNIT_EXPECT_EQ(test, RP1H_HZELLER_REGULAR_P0_R2, regular->r2);
	KUNIT_EXPECT_EQ(test, RP1H_HZELLER_REGULAR_P0_G2, regular->g2);
	KUNIT_EXPECT_EQ(test, RP1H_HZELLER_REGULAR_P0_B2, regular->b2);
	KUNIT_EXPECT_EQ(test, RP1H_HZELLER_REGULAR_CLK, regular->clk);
	KUNIT_EXPECT_EQ(test, RP1H_HZELLER_REGULAR_LAT, regular->lat);
	KUNIT_EXPECT_EQ(test, RP1H_HZELLER_REGULAR_OE, regular->oe);
	KUNIT_EXPECT_EQ(test, RP1H_HZELLER_REGULAR_A, regular->a);
	KUNIT_EXPECT_EQ(test, RP1H_HZELLER_REGULAR_B, regular->b);
	KUNIT_EXPECT_EQ(test, RP1H_HZELLER_REGULAR_C, regular->c);
	KUNIT_EXPECT_EQ(test, RP1H_HZELLER_REGULAR_D, regular->d);
	KUNIT_EXPECT_EQ(test, RP1H_HZELLER_REGULAR_E, regular->e);

	KUNIT_EXPECT_EQ(test, 12, RP1H_REGULAR_P1_R1);
	KUNIT_EXPECT_EQ(test, 5, RP1H_REGULAR_P1_G1);
	KUNIT_EXPECT_EQ(test, 6, RP1H_REGULAR_P1_B1);
	KUNIT_EXPECT_EQ(test, 19, RP1H_REGULAR_P1_R2);
	KUNIT_EXPECT_EQ(test, 13, RP1H_REGULAR_P1_G2);
	KUNIT_EXPECT_EQ(test, 20, RP1H_REGULAR_P1_B2);
}

static void rp1h_kunit_pack_regular_state32_maps_256x64_abcd_strip(struct kunit *test)
{
	struct rp1h_dev hub = {
		.cfg = {
			.cols = 64,
			.rows = 64,
			.pwm_bits = 6,
			.mapping = RP1H_MAPPING_REGULAR,
			.format = RP1H_FORMAT_RGB888,
			.stream_format = RP1H_STREAM_STATE32,
			.panel_count = 4,
			.lane_count = 2,
			.chain_length = 2,
		},
	};
	u8 *frame;
	u32 *words;
	u32 oe = RP1H_PIN(rp1h_electrodragon_p0_pinout.oe);
	u32 row1 = oe | RP1H_PIN(rp1h_electrodragon_p0_pinout.a);
	u32 a_c_transport;
	u32 b_d_transport;
	u32 input_cols = 256;
	int ret;

	ret = rp1h_validate_config(&hub.cfg);
	KUNIT_ASSERT_EQ(test, 0, ret);
	KUNIT_EXPECT_EQ(test, 49152U, hub.cfg.frame_bytes);
	KUNIT_EXPECT_EQ(test, 128U, hub.cfg.words_per_row_plane);
	KUNIT_EXPECT_EQ(test, 24576U, hub.cfg.words_per_frame);

	hub.buf = kunit_kzalloc(test, hub.cfg.mmap_size, GFP_KERNEL);
	frame = kunit_kzalloc(test, hub.cfg.frame_bytes, GFP_KERNEL);
	KUNIT_ASSERT_NOT_ERR_OR_NULL(test, hub.buf);
	KUNIT_ASSERT_NOT_ERR_OR_NULL(test, frame);

	/* Logical strip is A B C D across x; transport emits [A,C], then [B,D]. */
	frame[(0 * input_cols + 0) * 3 + 0] = 0xff;
	frame[(32 * input_cols + 0) * 3 + 1] = 0xff;
	frame[(0 * input_cols + 128) * 3 + 2] = 0xff;
	frame[(32 * input_cols + 128) * 3 + 0] = 0xff;
	frame[(0 * input_cols + 64) * 3 + 1] = 0xff;
	frame[(32 * input_cols + 64) * 3 + 2] = 0xff;
	frame[(0 * input_cols + 192) * 3 + 0] = 0xff;
	frame[(32 * input_cols + 192) * 3 + 1] = 0xff;
	frame[(1 * input_cols + 0) * 3 + 2] = 0xff;

	a_c_transport = oe |
		RP1H_PIN(rp1h_electrodragon_p0_pinout.r1) |
		RP1H_PIN(rp1h_electrodragon_p0_pinout.g2) |
		RP1H_PIN(RP1H_REGULAR_P1_B1) |
		RP1H_PIN(RP1H_REGULAR_P1_R2);
	b_d_transport = oe |
		RP1H_PIN(rp1h_electrodragon_p0_pinout.g1) |
		RP1H_PIN(rp1h_electrodragon_p0_pinout.b2) |
		RP1H_PIN(RP1H_REGULAR_P1_R1) |
		RP1H_PIN(RP1H_REGULAR_P1_G2);

	rp1h_pack_rgb888_state32(&hub, rp1h_legacy_frame(&hub), frame);
	words = hub.buf + hub.cfg.words_offset;

	KUNIT_EXPECT_EQ(test, a_c_transport, words[0]);
	KUNIT_EXPECT_EQ(test, oe, words[1]);
	KUNIT_EXPECT_EQ(test, b_d_transport, words[64]);
	KUNIT_EXPECT_EQ(test, a_c_transport, words[128]);
	KUNIT_EXPECT_EQ(test, row1 | RP1H_PIN(rp1h_electrodragon_p0_pinout.b1),
			words[256]);
}

static void rp1h_kunit_pack_regular_state32_all_green_has_no_p1_red(struct kunit *test)
{
	struct rp1h_dev hub = {
		.cfg = {
			.cols = 64,
			.rows = 64,
			.pwm_bits = 8,
			.mapping = RP1H_MAPPING_REGULAR,
			.format = RP1H_FORMAT_RGB888,
			.stream_format = RP1H_STREAM_STATE32,
			.panel_count = 4,
			.lane_count = 2,
			.chain_length = 2,
		},
	};
	u8 *frame;
	u32 *words;
	u32 green = RP1H_PIN(rp1h_electrodragon_p0_pinout.g1) |
		    RP1H_PIN(rp1h_electrodragon_p0_pinout.g2) |
		    RP1H_PIN(RP1H_REGULAR_P1_G1) |
		    RP1H_PIN(RP1H_REGULAR_P1_G2);
	u32 red = RP1H_PIN(RP1H_REGULAR_P1_R1) |
		  RP1H_PIN(RP1H_REGULAR_P1_R2);
	u32 i;
	int ret;

	ret = rp1h_validate_config(&hub.cfg);
	KUNIT_ASSERT_EQ(test, 0, ret);
	KUNIT_ASSERT_EQ(test, 32768U, hub.cfg.words_per_frame);

	hub.buf = kunit_kzalloc(test, hub.cfg.mmap_size, GFP_KERNEL);
	frame = kunit_kzalloc(test, hub.cfg.frame_bytes, GFP_KERNEL);
	KUNIT_ASSERT_NOT_ERR_OR_NULL(test, hub.buf);
	KUNIT_ASSERT_NOT_ERR_OR_NULL(test, frame);

	for (i = 0; i < hub.cfg.frame_bytes; i += 3)
		frame[i + 1] = 0xff;

	rp1h_pack_rgb888_state32(&hub, rp1h_legacy_frame(&hub), frame);
	words = hub.buf + hub.cfg.words_offset;

	for (i = 0; i < hub.cfg.words_per_frame; i++) {
		KUNIT_EXPECT_EQ(test, green, words[i] & green);
		KUNIT_EXPECT_EQ(test, 0U, words[i] & red);
	}
}

static void rp1h_kunit_pack_rgb6_packed_spans_words(struct kunit *test)
{
	struct rp1h_dev hub = {
		.cfg = {
			.cols = 4,
			.rows = 16,
			.pwm_bits = 1,
			.mapping = RP1H_MAPPING_ADAFRUIT_HAT_PWM,
			.format = RP1H_FORMAT_RGB888,
			.stream_format = RP1H_STREAM_RGB6_PACKED,
			.panel_count = 2,
		},
	};
	u8 *frame;
	u32 *words;
	int ret;

	ret = rp1h_validate_config(&hub.cfg);
	KUNIT_ASSERT_EQ(test, 0, ret);

	hub.buf = kunit_kzalloc(test, hub.cfg.mmap_size, GFP_KERNEL);
	frame = kunit_kzalloc(test, hub.cfg.frame_bytes, GFP_KERNEL);
	KUNIT_ASSERT_NOT_ERR_OR_NULL(test, hub.buf);
	KUNIT_ASSERT_NOT_ERR_OR_NULL(test, frame);

	frame[0] = 0xff;
	frame[((hub.cfg.rows / 2) * hub.cfg.cols * 3) + 1] = 0xff;
	frame[hub.cfg.cols * hub.cfg.rows * 3] = 0xff;
	frame[hub.cfg.cols * hub.cfg.rows * 3 +
	      ((hub.cfg.rows / 2) * hub.cfg.cols * 3) + 2] = 0xff;

	rp1h_pack_rgb888_rgb6_packed(&hub, rp1h_legacy_frame(&hub), frame);
	words = hub.buf + hub.cfg.words_offset;

	KUNIT_EXPECT_EQ(test, 0x851U, words[0]);
	KUNIT_EXPECT_EQ(test, 0U, words[1]);
}

static void rp1h_kunit_pack_rgb6_byte_interleaves_panels_per_column(struct kunit *test)
{
	struct rp1h_dev hub = {
		.cfg = {
			.cols = 2,
			.rows = 16,
			.pwm_bits = 1,
			.mapping = RP1H_MAPPING_ADAFRUIT_HAT_PWM,
			.format = RP1H_FORMAT_RGB888,
			.stream_format = RP1H_STREAM_RGB6_BYTE,
			.panel_count = 2,
		},
	};
	u8 *frame;
	u8 *bytes;
	u32 frame_stride;
	int ret;

	ret = rp1h_validate_config(&hub.cfg);
	KUNIT_ASSERT_EQ(test, 0, ret);

	hub.buf = kunit_kzalloc(test, hub.cfg.mmap_size, GFP_KERNEL);
	frame = kunit_kzalloc(test, hub.cfg.frame_bytes, GFP_KERNEL);
	KUNIT_ASSERT_NOT_ERR_OR_NULL(test, hub.buf);
	KUNIT_ASSERT_NOT_ERR_OR_NULL(test, frame);

	frame_stride = hub.cfg.cols * hub.cfg.rows * 3;
	frame[0] = 0xff;
	frame[frame_stride + ((hub.cfg.rows / 2) * hub.cfg.cols * 3) + 2] = 0xff;

	rp1h_pack_rgb888_rgb6_byte(&hub, rp1h_legacy_frame(&hub), frame);
	bytes = hub.buf + hub.cfg.words_offset;

	KUNIT_EXPECT_EQ(test, 0x01, bytes[0]);
	KUNIT_EXPECT_EQ(test, 0x20, bytes[1]);
	KUNIT_EXPECT_EQ(test, 0x00, bytes[2]);
	KUNIT_EXPECT_EQ(test, 0x00, bytes[3]);
}

static void rp1h_kunit_pack_rgb6_byte_zero_pads_tail(struct kunit *test)
{
	struct rp1h_dev hub = {
		.cfg = {
			.cols = 2,
			.rows = 16,
			.pwm_bits = 1,
			.mapping = RP1H_MAPPING_ADAFRUIT_HAT_PWM,
			.format = RP1H_FORMAT_RGB888,
			.stream_format = RP1H_STREAM_RGB6_BYTE,
		},
	};
	u8 *frame;
	u8 *bytes;
	int ret;

	ret = rp1h_validate_config(&hub.cfg);
	KUNIT_ASSERT_EQ(test, 0, ret);

	hub.buf = kunit_kzalloc(test, hub.cfg.mmap_size, GFP_KERNEL);
	frame = kunit_kzalloc(test, hub.cfg.frame_bytes, GFP_KERNEL);
	KUNIT_ASSERT_NOT_ERR_OR_NULL(test, hub.buf);
	KUNIT_ASSERT_NOT_ERR_OR_NULL(test, frame);

	frame[0] = 0xff;
	frame[((hub.cfg.rows / 2) * hub.cfg.cols * 3) + 2] = 0xff;

	rp1h_pack_rgb888_rgb6_byte(&hub, rp1h_legacy_frame(&hub), frame);
	bytes = hub.buf + hub.cfg.words_offset;

	KUNIT_EXPECT_EQ(test, 0x21, bytes[0]);
	KUNIT_EXPECT_EQ(test, 0x00, bytes[1]);
	KUNIT_EXPECT_EQ(test, 0x00, bytes[2]);
	KUNIT_EXPECT_EQ(test, 0x00, bytes[3]);
}

static void rp1h_kunit_worker_state_tracks_heartbeat_and_stale(struct kunit *test)
{
	struct rp1h_dev hub = {
		.worker_state = RP1H_WORKER_STARTING,
		.worker_timeout_ms = 1,
		.worker_start_ns = ktime_get_ns(),
	};

	KUNIT_EXPECT_EQ(test, RP1H_WORKER_STARTING,
			rp1h_observed_worker_state_locked(&hub));

	hub.worker_start_ns = ktime_get_ns() - 2 * NSEC_PER_MSEC;
	KUNIT_EXPECT_EQ(test, RP1H_WORKER_STALE,
			rp1h_observed_worker_state_locked(&hub));

	hub.worker_start_ns = ktime_get_ns();
	rp1h_worker_heartbeat_locked(&hub);
	KUNIT_EXPECT_EQ(test, RP1H_WORKER_RUNNING, hub.worker_state);
	KUNIT_EXPECT_EQ(test, RP1H_WORKER_RUNNING,
			rp1h_observed_worker_state_locked(&hub));

	hub.last_vsync_ns = ktime_get_ns() - 2 * NSEC_PER_MSEC;
	KUNIT_EXPECT_EQ(test, RP1H_WORKER_STALE,
			rp1h_observed_worker_state_locked(&hub));
}

static void rp1h_kunit_worker_heartbeat_ignores_stopped_worker(struct kunit *test)
{
	struct rp1h_dev hub = {
		.worker_state = RP1H_WORKER_STOPPED,
	};

	rp1h_worker_heartbeat_locked(&hub);
	KUNIT_EXPECT_EQ(test, RP1H_WORKER_STOPPED, hub.worker_state);
	KUNIT_EXPECT_EQ(test, 0ULL, hub.last_vsync_ns);
}

static struct kunit_case rp1h_kunit_cases[] = {
	KUNIT_CASE(rp1h_kunit_validate_default_rio32_config),
	KUNIT_CASE(rp1h_kunit_validate_rejects_unsupported_panel_stream),
	KUNIT_CASE(rp1h_kunit_validate_rejects_ambiguous_topology),
	KUNIT_CASE(rp1h_kunit_validate_e_line_requires_64_rows),
	KUNIT_CASE(rp1h_kunit_validate_rejects_unknown_flags),
	KUNIT_CASE(rp1h_kunit_validate_queue_slots),
	KUNIT_CASE(rp1h_kunit_validate_rejects_unknown_abi_selectors),
	KUNIT_CASE(rp1h_kunit_validate_rgb6_byte_multi_panel_geometry),
	KUNIT_CASE(rp1h_kunit_validate_rgb6_packed_multi_panel_geometry),
	KUNIT_CASE(rp1h_kunit_validate_rejects_invalid_geometry),
	KUNIT_CASE(rp1h_kunit_addr_mask_sets_e_for_upper_rows),
	KUNIT_CASE(rp1h_kunit_rgb_helpers_apply_cie1931_bitplanes),
	KUNIT_CASE(rp1h_kunit_write_header_exports_geometry),
	KUNIT_CASE(rp1h_kunit_choose_queue_slot_prefers_free_slot),
	KUNIT_CASE(rp1h_kunit_choose_queue_slot_reuses_pending_when_requested),
	KUNIT_CASE(rp1h_kunit_choose_queue_slot_does_not_replace_displayed_frame),
	KUNIT_CASE(rp1h_kunit_signal_vsync_promotes_pending_frame),
	KUNIT_CASE(rp1h_kunit_signal_vsync_without_pending_preserves_display_state),
	KUNIT_CASE(rp1h_kunit_queue_has_space_tracks_slot_availability),
	KUNIT_CASE(rp1h_kunit_ready_tracks_presented_sequence),
	KUNIT_CASE(rp1h_kunit_write_header_exports_queue_progress),
	KUNIT_CASE(rp1h_kunit_pack_rio32_toggles_clk_and_lat),
	KUNIT_CASE(rp1h_kunit_pack_rio32_row16_sets_e_addr_bit),
	KUNIT_CASE(rp1h_kunit_pack_state32_is_data_only),
	KUNIT_CASE(rp1h_kunit_pack_state32_is_row_major),
	KUNIT_CASE(rp1h_kunit_pack_regular_state32_uses_two_active_lanes),
	KUNIT_CASE(rp1h_kunit_regular_mapping_matches_hzeller),
	KUNIT_CASE(rp1h_kunit_pack_regular_state32_maps_256x64_abcd_strip),
	KUNIT_CASE(rp1h_kunit_pack_regular_state32_all_green_has_no_p1_red),
	KUNIT_CASE(rp1h_kunit_pack_rgb6_packed_spans_words),
	KUNIT_CASE(rp1h_kunit_pack_rgb6_byte_interleaves_panels_per_column),
	KUNIT_CASE(rp1h_kunit_pack_rgb6_byte_zero_pads_tail),
	KUNIT_CASE(rp1h_kunit_worker_state_tracks_heartbeat_and_stale),
	KUNIT_CASE(rp1h_kunit_worker_heartbeat_ignores_stopped_worker),
	{}
};

static struct kunit_suite rp1h_kunit_suite = {
	.name = "rp1_hub75",
	.test_cases = rp1h_kunit_cases,
};

kunit_test_suite(rp1h_kunit_suite);

#endif
