#include <linux/device/bus.h>
#include <linux/dma-mapping.h>
#include <linux/fs.h>
#include <linux/io.h>
#include <linux/ktime.h>
#include <linux/kthread.h>
#include <linux/minmax.h>
#include <linux/miscdevice.h>
#include <linux/module.h>
#include <linux/mutex.h>
#include <linux/platform_device.h>
#include <linux/pio_rp1.h>
#include <linux/sched.h>
#include <linux/slab.h>
#include <linux/uaccess.h>
#include <linux/wait.h>
#include <uapi/linux/sched/types.h>

#include "../../native/pi5_scan_loop_ioctl.h"

/*
 * heart_pi5_scan_loop
 * -------------------
 *
 * This module is the Pi 5-specific "resident packed frame" transport.
 *
 * Problem statement
 * -----------------
 * The stock rp1-pio userspace API is adequate for one-shot submissions, but it
 * does not express the mode this project cares about most: keep one already
 * packed HUB75 scan program resident and replay it until userspace has a newer
 * frame. Re-submitting the same packed bytes from userspace every refresh adds
 * avoidable syscall and copy overhead, and it blurs the boundary between
 * "userspace packed a frame" and "hardware replayed that frame N times."
 *
 * Design
 * ------
 * Userspace still owns packing. Rust reduces RGBA input into a compact stream
 * of control words, blank spans, and packed GPIO spans. The kernel then owns
 * only three things:
 *
 *   1. the lifetime of one resident coherent frame buffer
 *   2. one replay worker per open session
 *   3. the presentation counter used by WAIT/STATS
 *
 * Once a frame is loaded, the worker replays that exact byte stream into the
 * RP1 PIO TX FIFO. The worker does not reinterpret the protocol, rebuild the
 * frame, or make content decisions. That separation keeps correctness review
 * tractable:
 *
 *   - Rust decides *which* bytes describe the frame
 *   - the kernel decides *when* those bytes are replayed
 *
 * Comparison rules
 * ----------------
 * The PIO program here intentionally matches the raw userspace rp1-pio path in
 * native/pi5_pio_scan_shim.c. Benchmark deltas between the two paths should
 * therefore be read as transport differences, not protocol drift.
 *
 * Scope
 * -----
 * This is intentionally not a general-purpose display or KMS/DRM driver. The
 * ioctl ABI is deliberately narrow and session-oriented:
 *
 *   INIT -> LOAD -> START -> WAIT/STATS -> STOP
 *
 * If a future feature cannot be explained in those terms, it should be treated
 * as a new protocol/design discussion rather than quietly folded into this
 * driver.
 */

#define HEART_PI5_SCAN_LOOP_DEVICE_NAME "heart_pi5_scan_loop"
#define HEART_PI5_SCAN_LOOP_PIO_DEVICE_NAME "1f00178000.pio"
#define HEART_PI5_SCAN_LOOP_PROGRAM_LENGTH 25u
#define HEART_PI5_SCAN_LOOP_OUTPUT_PIN_BASE 5u
#define HEART_PI5_SCAN_LOOP_OUTPUT_PIN_COUNT 23u
#define HEART_PI5_SCAN_LOOP_CONTROL_WORD_BITS 32u
#define HEART_PI5_SCAN_LOOP_PIN_WORD_BITS 23u
#define HEART_PI5_SCAN_LOOP_OE_GPIO 18u
#define HEART_PI5_SCAN_LOOP_LAT_GPIO 21u
#define HEART_PI5_SCAN_LOOP_CLOCK_GPIO 17u
#define HEART_PI5_SCAN_LOOP_POST_ADDR_TICKS 5u
#define HEART_PI5_SCAN_LOOP_LATCH_TICKS 1u
#define HEART_PI5_SCAN_LOOP_POST_LATCH_TICKS 1u
#define HEART_PI5_SCAN_LOOP_LAT_SET_LOW 0u
#define HEART_PI5_SCAN_LOOP_LAT_SET_HIGH 1u
#define HEART_PI5_SCAN_LOOP_SIDESET_ACTIVE 0x0u
#define HEART_PI5_SCAN_LOOP_SIDESET_BLANK_LOW 0x2u
#define HEART_PI5_SCAN_LOOP_SIDESET_BLANK_HIGH 0x3u
#define HEART_PI5_SCAN_LOOP_DEFAULT_DMACTRL 0x80000104u
#define HEART_PI5_SCAN_LOOP_DEFAULT_BATCH_TARGET_BYTES (4u * 1024u * 1024u)
#define HEART_PI5_SCAN_LOOP_DEFAULT_WORKER_CPU 0u
#define HEART_PI5_SCAN_LOOP_DEFAULT_WORKER_PRIORITY 80u
#define HEART_PI5_SCAN_LOOP_MAX_BATCH_REPLAYS 1024u

struct heart_pi5_scan_loop_replay_batch {
	/*
	 * The resident frame is immutable while replay is enabled. The worker can
	 * therefore snapshot just the active prefix and consume it without holding
	 * session->lock across the MMIO burst.
	 */
	const uint32_t *words;
	u32 __iomem *fifo_mmio;
	u32 frame_bytes;
	u32 word_count;
	u32 replay_count;
};

struct heart_pi5_scan_loop_session {
	struct mutex lock;
	wait_queue_head_t wait_queue;
	wait_queue_head_t quiesce_wait_queue;
	struct task_struct *worker;
	/* Write-combined alias of the per-SM TX FIFO data register. */
	void __iomem *fifo_mmio;
	/* Lifetime-owned PIO context for this session. */
	PIO pio;
	int sm;
	/* Resident packed frame storage shared between ioctl LOAD and replay. */
	dma_addr_t frame_dma;
	void *frame_cpu;
	u32 frame_capacity_bytes;
	/* replay_bytes may be smaller than frame_capacity_bytes after compression. */
	u32 replay_bytes;
	bool configured;
	bool frame_loaded;
	bool replay_enabled;
	bool stop_worker;
	/*
	 * Lifecycle state, from userspace's point of view:
	 *
	 *   configured     => INIT has established the PIO program, GPIO ownership,
	 *                     FIFO mapping, and resident coherent buffer.
	 *   frame_loaded   => LOAD has copied a complete packed frame into the
	 *                     resident buffer and replay_bytes describes its valid
	 *                     prefix.
	 *   replay_enabled => START has published that resident frame to the worker
	 *                     as eligible for replay.
	 *   stop_worker    => file teardown is in progress and the kthread should
	 *                     exit permanently rather than merely stop replay.
	 *
	 * These flags are intentionally not a generic enum state machine because
	 * userspace is allowed to observe or wait on several overlapping notions of
	 * state:
	 *   - configured vs not configured
	 *   - has a resident frame vs does not
	 *   - replay currently enabled vs stopped
	 *   - kthread still owns a replay snapshot vs quiescent
	 *
	 * The comments and helpers below treat them as one coherent lifecycle even
	 * though the representation is several booleans.
	 */
	/*
	 * worker_active means the kthread has snapshotted frame_cpu/replay_bytes and
	 * may still be reading from that resident buffer outside session->lock.
	 * STOP waits for this bit to clear before LOAD is allowed to replace the
	 * resident payload.
	 */
	bool worker_active;
	/*
	 * worker_runnable is the lock-protected "can the worker enter a replay
	 * batch right now?" summary bit. The worker's wait predicate uses this
	 * single flag instead of repeatedly sampling several shared booleans.
	 */
	bool worker_runnable;
	/* program_loaded gates pio_remove_program() during teardown. */
	bool program_loaded;
	/* Number of full scan-program replays completed since the last START. */
	atomic64_t presentations;
	atomic64_t batches_submitted;
	atomic64_t words_written;
	atomic64_t drain_failures;
	atomic64_t stop_requests_seen_during_batch;
	atomic64_t mmio_write_ns;
	atomic64_t drain_ns;
	u32 max_batch_replays;
	u32 worker_cpu;
	u32 worker_priority;
	int last_error;
	uint program_offset;
	uint16_t instructions[HEART_PI5_SCAN_LOOP_PROGRAM_LENGTH];
	pio_program_t program;
};

/*
 * Session invariants
 * ------------------
 *
 * lock protects:
 *   - replay_enabled/frame_loaded/configured/stop_worker/worker_active
 *   - replay_bytes
 *   - last_error
 *   - all PIO/program/buffer lifetime transitions
 *
 * presentations is atomic because WAIT/STATS need to observe replay progress
 * without holding the lock for the duration of a replay batch.
 *
 * frame_cpu/frame_dma always describe one coherent allocation of
 * frame_capacity_bytes. replay_bytes is the currently valid prefix of that
 * allocation. The worker only ever replays replay_bytes bytes from frame_cpu.
 */

static struct device *heart_pi5_scan_loop_pio_device;
static uint heart_pi5_scan_loop_dmactrl = HEART_PI5_SCAN_LOOP_DEFAULT_DMACTRL;
static uint heart_pi5_scan_loop_batch_target_bytes =
	HEART_PI5_SCAN_LOOP_DEFAULT_BATCH_TARGET_BYTES;
static uint heart_pi5_scan_loop_worker_cpu = HEART_PI5_SCAN_LOOP_DEFAULT_WORKER_CPU;
static uint heart_pi5_scan_loop_worker_priority =
	HEART_PI5_SCAN_LOOP_DEFAULT_WORKER_PRIORITY;

module_param_named(dmactrl, heart_pi5_scan_loop_dmactrl, uint, 0644);
MODULE_PARM_DESC(dmactrl, "PIO DMACTRL value used for the resident TX FIFO pacing.");
module_param_named(
	batch_target_bytes,
	heart_pi5_scan_loop_batch_target_bytes,
	uint,
	0644
);
MODULE_PARM_DESC(
	batch_target_bytes,
	"Target bytes per resident replay batch after the first completed presentation."
);
module_param_named(worker_cpu, heart_pi5_scan_loop_worker_cpu, uint, 0644);
MODULE_PARM_DESC(
	worker_cpu,
	"CPU the resident replay kthread is bound to. Invalid values fall back to CPU 0."
);
module_param_named(worker_priority, heart_pi5_scan_loop_worker_priority, uint, 0644);
MODULE_PARM_DESC(
	worker_priority,
	"SCHED_FIFO priority used for the resident replay kthread."
);

static const u32 HEART_PI5_SCAN_LOOP_RGB_GPIOS[] = {5, 13, 6, 12, 16, 23};
static const u32 HEART_PI5_SCAN_LOOP_ADDR_GPIOS[] = {22, 26, 27, 20, 24};

static int heart_pi5_scan_loop_worker(void *context);

static void heart_pi5_scan_loop_pin_release(PIO pio, u32 gpio)
{
	pio_gpio_set_function(pio, gpio, GPIO_FUNC_NULL);
}

static bool heart_pi5_scan_loop_is_worker_runnable_locked(
	const struct heart_pi5_scan_loop_session *session
)
{
	/*
	 * This helper answers one narrow question only:
	 *   "may the worker enter a new replay batch right now?"
	 *
	 * It deliberately excludes the "worker is already in a batch" case. That is
	 * what lets STOP/LOAD distinguish between:
	 *   - replay is merely enabled and could begin again
	 *   - replay is actively consuming the resident buffer right now
	 */
	return session->configured && session->replay_enabled && session->frame_loaded &&
	       session->replay_bytes > 0 && !session->worker_active;
}

static void heart_pi5_scan_loop_update_worker_runnable_locked(
	struct heart_pi5_scan_loop_session *session
)
{
	WRITE_ONCE(
		session->worker_runnable,
		heart_pi5_scan_loop_is_worker_runnable_locked(session)
	);
}

static void heart_pi5_scan_loop_reset_stats_locked(struct heart_pi5_scan_loop_session *session)
{
	/*
	 * Reset one presentation-accounting epoch. START and LOAD both use this so
	 * "frame N has been presented M times" always means "since the most recent
	 * successful START of the current resident payload."
	 */
	atomic64_set(&session->presentations, 0);
	atomic64_set(&session->batches_submitted, 0);
	atomic64_set(&session->words_written, 0);
	atomic64_set(&session->drain_failures, 0);
	atomic64_set(&session->stop_requests_seen_during_batch, 0);
	atomic64_set(&session->mmio_write_ns, 0);
	atomic64_set(&session->drain_ns, 0);
	WRITE_ONCE(session->max_batch_replays, 0);
}

static u32 heart_pi5_scan_loop_compute_batch_replays(
	u32 frame_bytes,
	u64 completed_presentations,
	u32 batch_target_bytes
)
{
	u32 replay_batch_count = 1;

	/*
	 * Batch sizing is a throughput/latency tradeoff, not just a throughput
	 * knob. The first completed presentation is always left unbatched so the
	 * "time to first visible frame" metric remains honest. After that, the
	 * worker may replay the same resident payload multiple times before one
	 * drain/completion round.
	 *
	 * The target is expressed in bytes rather than "replays" because payload
	 * size changes as the Rust packer evolves. That keeps the batching policy
	 * stable across protocol improvements: smaller packed frames naturally batch
	 * more, larger dense frames batch less.
	 */
	if (completed_presentations > 0 && frame_bytes > 0 && batch_target_bytes > 0) {
		replay_batch_count = max_t(u32, 1, batch_target_bytes / frame_bytes);
		replay_batch_count = min_t(
			u32,
			replay_batch_count,
			HEART_PI5_SCAN_LOOP_MAX_BATCH_REPLAYS
		);
	}

	return replay_batch_count;
}

static void heart_pi5_scan_loop_prepare_replay_batch_locked(
	struct heart_pi5_scan_loop_session *session,
	u64 completed_presentations,
	u32 batch_target_bytes,
	struct heart_pi5_scan_loop_replay_batch *batch
)
{
	/*
	 * Snapshot exactly the inputs the worker needs after dropping the lock.
	 * This keeps the unlocked MMIO phase honest: no hidden reads back into the
	 * mutable session state, and therefore a smaller race surface to audit.
	 *
	 * In particular, the worker does not look back at replay_bytes or frame_cpu
	 * once this snapshot is taken. STOP/LOAD synchronization is built around
	 * that property.
	 */
	batch->frame_bytes = session->replay_bytes;
	batch->word_count = batch->frame_bytes / sizeof(uint32_t);
	batch->words = session->frame_cpu;
	batch->fifo_mmio = session->fifo_mmio;
	batch->replay_count = heart_pi5_scan_loop_compute_batch_replays(
		batch->frame_bytes,
		completed_presentations,
		batch_target_bytes
	);
}

static u32 heart_pi5_scan_loop_resolve_worker_cpu(void)
{
	u32 requested_cpu = READ_ONCE(heart_pi5_scan_loop_worker_cpu);

	if (requested_cpu >= nr_cpu_ids || !cpu_online((int)requested_cpu)) {
		return 0;
	}

	return requested_cpu;
}

static u32 heart_pi5_scan_loop_resolve_worker_priority(void)
{
	return clamp_t(
		u32,
		READ_ONCE(heart_pi5_scan_loop_worker_priority),
		1,
		MAX_RT_PRIO - 1
	);
}

static int heart_pi5_scan_loop_start_worker(struct heart_pi5_scan_loop_session *session)
{
	struct sched_attr scheduler = { 0 };
	u32 worker_cpu = heart_pi5_scan_loop_resolve_worker_cpu();
	u32 worker_priority = heart_pi5_scan_loop_resolve_worker_priority();
	int result;

	session->worker = kthread_create(
		heart_pi5_scan_loop_worker,
		session,
		"heart-pi5-scan-loop"
	);
	if (IS_ERR(session->worker)) {
		result = PTR_ERR(session->worker);
		session->worker = NULL;
		return result;
	}

	/*
	 * The replay loop is intentionally pinned and run as FIFO RT because the
	 * hot path is a tight MMIO burst into the RP1 FIFO. Keeping it on one CPU
	 * removes migration noise, and RT scheduling keeps drain latency stable.
	 *
	 * The worker itself remains responsive because the inner replay loop checks
	 * stop/disable state between replays and bounds the batch size.
	 */
	session->worker_cpu = worker_cpu;
	session->worker_priority = worker_priority;
	kthread_bind(session->worker, (unsigned int)worker_cpu);

	scheduler.size = sizeof(scheduler);
	scheduler.sched_policy = SCHED_FIFO;
	scheduler.sched_priority = worker_priority;
	result = sched_setattr_nocheck(session->worker, &scheduler);
	if (result) {
		kthread_stop(session->worker);
		session->worker = NULL;
		return result;
	}

	wake_up_process(session->worker);
	return 0;
}

/*
 * The Rust packer already reduces the frame to the exact sequence of TX words
 * the state machine must consume. The fastest stable path on Pi 5 turned out to
 * be a write-combined FIFO mapping fed by an eight-wide writel_relaxed() loop.
 * Keeping this helper simple makes the remaining transport cost easy to reason
 * about: every call below directly becomes FIFO traffic.
 */
static void heart_pi5_scan_loop_mmio_write_words(
	uint32_t __iomem *fifo_mmio,
	const uint32_t *words,
	u32 word_count
)
{
	u32 index = 0;

	/*
	 * This is the steady-state hot loop.
	 *
	 * The eight-wide unroll is deliberate and empirical: it was the fastest
	 * stable shape found for this WC FIFO mapping without resorting to harder-
	 * to-audit raw store tricks. The goal here is not cleverness; it is to keep
	 * the generated code close to "one relaxed MMIO store per transport word"
	 * with minimal loop overhead.
	 *
	 * Two constraints are worth keeping in mind if this is revisited:
	 *   - the transport is already pre-packed in Rust, so there is no useful
	 *     per-word computation left to hide here
	 *   - apparent wins from more aggressive write patterns need measurement
	 *     against real drain completion, not just host-side store timing
	 */
	for (; index + 8 <= word_count; index += 8) {
		writel_relaxed(words[index + 0], fifo_mmio);
		writel_relaxed(words[index + 1], fifo_mmio);
		writel_relaxed(words[index + 2], fifo_mmio);
		writel_relaxed(words[index + 3], fifo_mmio);
		writel_relaxed(words[index + 4], fifo_mmio);
		writel_relaxed(words[index + 5], fifo_mmio);
		writel_relaxed(words[index + 6], fifo_mmio);
		writel_relaxed(words[index + 7], fifo_mmio);
	}
	for (; index < word_count; ++index) {
		writel_relaxed(words[index], fifo_mmio);
	}
}

static void heart_pi5_scan_loop_teardown_locked(struct heart_pi5_scan_loop_session *session)
{
	size_t index;

	/*
	 * The teardown order matters:
	 *   1. stop publishing the session as active
	 *   2. unmap the FIFO window so no more MMIO writes can happen
	 *   3. disable and unclaim the SM
	 *   4. return GPIO ownership
	 *   5. free the resident frame buffer
	 *
	 * This keeps teardown idempotent and makes repeated INIT/close cycles safe.
	 *
	 * Importantly, this helper assumes the caller has already stopped the
	 * worker or prevented it from entering a new replay batch. It does not try
	 * to synchronize with an in-flight worker on its own.
	 */
	session->configured = false;
	session->frame_loaded = false;
	session->replay_enabled = false;
	session->last_error = 0;
	session->replay_bytes = 0;
	heart_pi5_scan_loop_reset_stats_locked(session);
	heart_pi5_scan_loop_update_worker_runnable_locked(session);

	if (session->fifo_mmio) {
		iounmap(session->fifo_mmio);
		session->fifo_mmio = NULL;
	}

	if (session->pio && session->sm >= 0) {
		pio_sm_set_enabled(session->pio, (uint)session->sm, false);
		pio_sm_unclaim(session->pio, (uint)session->sm);
	}
	if (session->pio && session->program_loaded) {
		pio_remove_program(session->pio, &session->program, session->program_offset);
		session->program_loaded = false;
	}
	if (session->pio) {
		heart_pi5_scan_loop_pin_release(session->pio, HEART_PI5_SCAN_LOOP_OE_GPIO);
		heart_pi5_scan_loop_pin_release(session->pio, HEART_PI5_SCAN_LOOP_LAT_GPIO);
		heart_pi5_scan_loop_pin_release(session->pio, HEART_PI5_SCAN_LOOP_CLOCK_GPIO);
		for (index = 0; index < ARRAY_SIZE(HEART_PI5_SCAN_LOOP_RGB_GPIOS); ++index) {
			heart_pi5_scan_loop_pin_release(session->pio, HEART_PI5_SCAN_LOOP_RGB_GPIOS[index]);
		}
		for (index = 0; index < ARRAY_SIZE(HEART_PI5_SCAN_LOOP_ADDR_GPIOS); ++index) {
			heart_pi5_scan_loop_pin_release(session->pio, HEART_PI5_SCAN_LOOP_ADDR_GPIOS[index]);
		}
		pio_close(session->pio);
		session->pio = NULL;
	}
	session->sm = -1;

	if (session->frame_cpu) {
		dma_free_coherent(
			heart_pi5_scan_loop_pio_device,
			session->frame_capacity_bytes,
			session->frame_cpu,
			session->frame_dma
		);
		session->frame_cpu = NULL;
		session->frame_dma = 0;
	}
	session->frame_capacity_bytes = 0;
}

static int heart_pi5_scan_loop_worker(void *context)
{
	struct heart_pi5_scan_loop_session *session = context;

	/*
	 * One kthread owns all hardware traffic for a session. That gives us a
	 * single serialization point for:
	 *   - replay_enabled transitions
	 *   - the current resident frame contents
	 *   - presentation counting
	 *
	 * The worker deliberately drops the mutex before issuing MMIO stores so
	 * userspace can call WAIT/STATS/STOP without being blocked behind a long
	 * replay batch.
	 */
	while (!kthread_should_stop()) {
		struct heart_pi5_scan_loop_replay_batch batch;
		ktime_t write_started;
		ktime_t write_finished;
		ktime_t drain_finished;
		u32 batch_target_bytes;
		u64 completed_presentations;
		u32 completed_replays = 0;
		u32 replay_index;
		bool batch_interrupted = false;
		int transfer_result;

		wait_event(
			session->wait_queue,
			kthread_should_stop() ||
			READ_ONCE(session->stop_worker) ||
			READ_ONCE(session->worker_runnable)
		);
		if (kthread_should_stop()) {
			break;
		}

		mutex_lock(&session->lock);
		if (session->stop_worker) {
			mutex_unlock(&session->lock);
			break;
		}
		if (!session->worker_runnable) {
			mutex_unlock(&session->lock);
			continue;
		}

		completed_presentations = (u64)atomic64_read(&session->presentations);
		batch_target_bytes = READ_ONCE(heart_pi5_scan_loop_batch_target_bytes);
		heart_pi5_scan_loop_prepare_replay_batch_locked(
			session,
			completed_presentations,
			batch_target_bytes,
			&batch
		);
		session->worker_active = true;
		heart_pi5_scan_loop_update_worker_runnable_locked(session);

		/*
		 * The first replay of a newly loaded frame is intentionally unbatched so
		 * "time to first render" stays honest. After that, unchanged resident
		 * frames can be replayed several times before the next drain to amortize
		 * the completion bookkeeping.
		 */
		mutex_unlock(&session->lock);

		/*
		 * At this point the worker owns an immutable snapshot of the replay
		 * inputs for this batch:
		 *   - words/frame_bytes come from the resident coherent buffer
		 *   - fifo_mmio is the mapped TX FIFO window
		 *   - replay_batch_count is fixed for this batch
		 *
		 * LOAD is forbidden while replay_enabled is true, and STOP does not
		 * return until worker_active drops again. That keeps frame_cpu immutable
		 * for the full lifetime of this replay snapshot.
		 */
		write_started = ktime_get();
		for (replay_index = 0; replay_index < batch.replay_count; ++replay_index) {
			/*
			 * Stop/disable responsiveness is checked between whole-frame
			 * replays, not between transport words. That is intentional:
			 * per-word checks would lengthen the hottest loop in the driver,
			 * while per-replay checks keep STOP latency bounded by one packed
			 * frame plus one drain.
			 */
			if (unlikely(
				    kthread_should_stop() || READ_ONCE(session->stop_worker) ||
				    !READ_ONCE(session->replay_enabled)
			    )) {
				batch_interrupted = true;
				break;
			}

			heart_pi5_scan_loop_mmio_write_words(
				batch.fifo_mmio,
				batch.words,
				batch.word_count
			);
			++completed_replays;
		}
		write_finished = ktime_get();

		if (batch_interrupted) {
			atomic64_inc(&session->stop_requests_seen_during_batch);
		}
		if (completed_replays == 0) {
			mutex_lock(&session->lock);
			session->worker_active = false;
			heart_pi5_scan_loop_update_worker_runnable_locked(session);
			mutex_unlock(&session->lock);
			wake_up_all(&session->quiesce_wait_queue);
			continue;
		}

		/*
		 * WC writes are posted. The barrier orders the MMIO write burst before
		 * the subsequent drain/completion check; pio_sm_drain_tx_fifo() remains
		 * the primitive that tells us the state machine has consumed the batch.
		 *
		 * The drain call is the synchronization primitive that matters for
		 * correctness here: once it returns, the state machine has consumed the
		 * submitted batch and the presentation counter can advance without
		 * over-reporting.
		 *
		 * This completion point is intentionally conservative. It does not try
		 * to report "visible photons left the panel"; it reports that the PIO TX
		 * path consumed the submitted batch. That is the contract WAIT/STATS are
		 * built around, and it is the same style of accounting used by the raw
		 * userspace transport.
		 */
		wmb();
		transfer_result = pio_sm_drain_tx_fifo(session->pio, (uint)session->sm);
		drain_finished = ktime_get();
		atomic64_add(
			ktime_to_ns(ktime_sub(write_finished, write_started)),
			&session->mmio_write_ns
		);
		atomic64_add(
			ktime_to_ns(ktime_sub(drain_finished, write_finished)),
			&session->drain_ns
		);
		if (transfer_result < 0) {
			pr_warn(
				"heart_pi5_scan_loop: pio_sm_drain_tx_fifo failed after MMIO replay: %d\n",
				transfer_result
			);
			atomic64_inc(&session->drain_failures);
			mutex_lock(&session->lock);
			session->last_error = transfer_result;
			session->replay_enabled = false;
			session->worker_active = false;
			heart_pi5_scan_loop_update_worker_runnable_locked(session);
			mutex_unlock(&session->lock);
			wake_up_all(&session->quiesce_wait_queue);
			wake_up_all(&session->wait_queue);
			continue;
		}

		atomic64_inc(&session->batches_submitted);
		/*
		 * words_written counts actual FIFO transport words, not logical pixels
		 * or groups. That makes it the right quantity to compare against Rust-
		 * side packer changes: if resident_refresh_hz moves but words_written
		 * per second stays flat, the bottleneck is still this MMIO burst path.
		 */
		atomic64_add((s64)((u64)batch.word_count * completed_replays), &session->words_written);
		atomic64_add(completed_replays, &session->presentations);
		if (completed_replays > READ_ONCE(session->max_batch_replays)) {
			WRITE_ONCE(session->max_batch_replays, completed_replays);
		}
		mutex_lock(&session->lock);
		session->worker_active = false;
		heart_pi5_scan_loop_update_worker_runnable_locked(session);
		mutex_unlock(&session->lock);
		wake_up_all(&session->quiesce_wait_queue);
		wake_up(&session->wait_queue);
	}

	return 0;
}

static int heart_pi5_scan_loop_configure_locked(
	struct heart_pi5_scan_loop_session *session,
	u32 frame_bytes
)
{
	pio_sm_config config;
	struct platform_device *pdev;
	struct resource *resource;
	resource_size_t fifo_offset;
	int result;
	size_t index;

	if (session->configured) {
		/*
		 * INIT is intentionally one-shot per session. Reusing the same frame size
		 * is harmless and keeps the ABI convenient for callers that probe/init on
		 * startup, but changing the capacity mid-session would invalidate the
		 * resident buffer contract and is rejected.
		 */
		if (session->frame_capacity_bytes == frame_bytes) {
			return 0;
		}
		return -EBUSY;
	}
	if (frame_bytes == 0) {
		return -EINVAL;
	}

	/*
	 * Configuration is ordered so every later resource depends on earlier ones:
	 *
	 *   1. open/claim PIO + SM
	 *   2. build and load the shared parser program
	 *   3. claim/configure GPIOs and initialize the SM
	 *   4. allocate the resident coherent frame buffer
	 *   5. map the one-word FIFO aperture with WC semantics
	 *   6. enable the SM and publish the session as configured
	 *
	 * This ordering keeps failure unwinding simple. Anything that fails can
	 * fall into heart_pi5_scan_loop_teardown_locked(), which tears resources
	 * down in the reverse order and leaves the session back in an unconfigured
	 * state.
	 */
	session->pio = pio_open();
	if (!session->pio) {
		return -ENODEV;
	}

	session->sm = pio_claim_unused_sm(session->pio, true);
	if (session->sm < 0) {
		result = session->sm;
		heart_pi5_scan_loop_teardown_locked(session);
		return result;
	}

	config = pio_get_default_sm_config();
	sm_config_set_fifo_join(&config, PIO_FIFO_JOIN_TX);
	/*
	 * The resident-loop parser currently runs at the RP1 PIO base clock with a
	 * fixed 1.0 divider. Keeping the kernel path on an invariant clock makes
	 * the resident benchmark numbers attributable to packed payload size and
	 * FIFO feed behavior instead of per-session timing choices. If this ever
	 * becomes tunable, the matching userspace parser and benchmark assumptions
	 * need the same review because dwell counts and throughput comparisons are
	 * all interpreted against this clock.
	 */
	sm_config_set_clkdiv(&config, make_fp24_8(1, 1));

	/*
	 * The state machine consumes the compact span format emitted by the Rust
	 * packer:
	 *   - instruction 0 loads the blank/address word for this row pair
	 *   - instructions 3..11 decode one packed repeat span
	 *   - instructions 12..18 decode one raw span or detect end-of-spans
	 *   - instructions 19..24 pulse LAT, dwell with OE active, then return to 0
	 *
	 * Both span types now inline the first/only 23-bit GPIO word in their
	 * control word. That is the dense-path win:
	 *
	 *   - raw spans stop paying a separate packed word for their first column
	 *   - repeat spans still collapse long constant runs to one control word
	 *
	 * The packed payload that follows a raw span therefore only carries the
	 * remaining columns after the first one.
	 *
	 * A maintainer reading only this file should treat the protocol like this:
	 *   word 0:
	 *     row-addressed blank word
	 *   repeated:
	 *     raw word     => raw span:
	 *                       bit 0      = 0
	 *                       bits 1..8  = raw_len - 1
	 *                       bits 9..31 = first 23-bit GPIO word
	 *                       packed words for the remaining columns follow
	 *     repeat word  => repeat span:
	 *                       bit 0      = 1
	 *                       bits 1..8  = repeat_len - 1
	 *                       bits 9..31 = repeated 23-bit GPIO word
	 *   terminator:
	 *     x == 0
	 *   trailer:
	 *     dwell counter
	 *
	 * Two maintenance rules matter here:
	 *
	 *   - The parser contract must stay byte-for-byte aligned with the comments
	 *     in rust/src/runtime/pi5_scan.rs and native/pi5_pio_scan_shim.c.
	 *   - If a protocol change would require the raw userspace path and this
	 *     resident path to diverge, that should be treated as a format version
	 *     change, not a silent local optimization.
	 */
	/*
	 * OE now rides on sideset together with the clock, and LAT is generated
	 * internally through SET PINS on GPIO 21. That keeps the trailer short even
	 * after teaching both raw and repeat spans to inline GPIO data.
	 */
	session->instructions[0] = (uint16_t)pio_encode_pull(false, true);
	session->instructions[1] = (uint16_t)(
		pio_encode_out(pio_pins, HEART_PI5_SCAN_LOOP_PIN_WORD_BITS) |
		pio_encode_sideset_opt(2, HEART_PI5_SCAN_LOOP_SIDESET_BLANK_LOW)
	);
	session->instructions[2] = (uint16_t)(
		pio_encode_nop() |
		pio_encode_delay(HEART_PI5_SCAN_LOOP_POST_ADDR_TICKS - 1) |
		pio_encode_sideset_opt(2, HEART_PI5_SCAN_LOOP_SIDESET_BLANK_LOW)
	);
	session->instructions[3] = (uint16_t)pio_encode_pull(false, true);
	session->instructions[4] = (uint16_t)pio_encode_out(pio_x, 1);
	session->instructions[5] = (uint16_t)pio_encode_jmp_not_x(12);
	session->instructions[6] = (uint16_t)pio_encode_out(pio_y, 8);
	session->instructions[7] = (uint16_t)pio_encode_mov(pio_x, pio_osr);
	session->instructions[8] = (uint16_t)(
		pio_encode_mov(pio_osr, pio_x) |
		pio_encode_sideset_opt(2, HEART_PI5_SCAN_LOOP_SIDESET_BLANK_LOW)
	);
	session->instructions[9] = (uint16_t)(
		pio_encode_out(pio_pins, HEART_PI5_SCAN_LOOP_PIN_WORD_BITS) |
		pio_encode_sideset_opt(2, HEART_PI5_SCAN_LOOP_SIDESET_BLANK_LOW)
	);
	session->instructions[10] = (uint16_t)(
		pio_encode_jmp_y_dec(8) |
		pio_encode_sideset_opt(2, HEART_PI5_SCAN_LOOP_SIDESET_BLANK_HIGH)
	);
	session->instructions[11] = (uint16_t)(
		pio_encode_jmp(3) |
		pio_encode_sideset_opt(2, HEART_PI5_SCAN_LOOP_SIDESET_BLANK_LOW)
	);
	session->instructions[12] = (uint16_t)pio_encode_out(pio_y, 8);
	session->instructions[13] = (uint16_t)pio_encode_out(pio_x, HEART_PI5_SCAN_LOOP_PIN_WORD_BITS);
	session->instructions[14] = (uint16_t)pio_encode_jmp_not_x(19);
	session->instructions[15] = (uint16_t)(
		pio_encode_mov(pio_osr, pio_x) |
		pio_encode_sideset_opt(2, HEART_PI5_SCAN_LOOP_SIDESET_BLANK_LOW)
	);
	session->instructions[16] = (uint16_t)(
		pio_encode_out(pio_pins, HEART_PI5_SCAN_LOOP_PIN_WORD_BITS) |
		pio_encode_sideset_opt(2, HEART_PI5_SCAN_LOOP_SIDESET_BLANK_LOW)
	);
	session->instructions[17] = (uint16_t)(
		pio_encode_jmp_y_dec(16) |
		pio_encode_sideset_opt(2, HEART_PI5_SCAN_LOOP_SIDESET_BLANK_HIGH)
	);
	session->instructions[18] = (uint16_t)(
		pio_encode_jmp(3) |
		pio_encode_sideset_opt(2, HEART_PI5_SCAN_LOOP_SIDESET_BLANK_LOW)
	);
	session->instructions[19] = (uint16_t)(
		pio_encode_set(pio_pins, HEART_PI5_SCAN_LOOP_LAT_SET_HIGH) |
		pio_encode_delay(HEART_PI5_SCAN_LOOP_LATCH_TICKS - 1) |
		pio_encode_sideset_opt(2, HEART_PI5_SCAN_LOOP_SIDESET_BLANK_LOW)
	);
	session->instructions[20] = (uint16_t)(
		pio_encode_set(pio_pins, HEART_PI5_SCAN_LOOP_LAT_SET_LOW) |
		pio_encode_delay(HEART_PI5_SCAN_LOOP_POST_LATCH_TICKS - 1) |
		pio_encode_sideset_opt(2, HEART_PI5_SCAN_LOOP_SIDESET_BLANK_LOW)
	);
	session->instructions[21] = (uint16_t)(
		pio_encode_pull(false, true) |
		pio_encode_sideset_opt(2, HEART_PI5_SCAN_LOOP_SIDESET_ACTIVE)
	);
	session->instructions[22] = (uint16_t)(
		pio_encode_out(pio_y, HEART_PI5_SCAN_LOOP_CONTROL_WORD_BITS) |
		pio_encode_sideset_opt(2, HEART_PI5_SCAN_LOOP_SIDESET_ACTIVE)
	);
	session->instructions[23] = (uint16_t)(
		pio_encode_jmp_y_dec(23) |
		pio_encode_sideset_opt(2, HEART_PI5_SCAN_LOOP_SIDESET_ACTIVE)
	);
	session->instructions[24] = (uint16_t)(
		pio_encode_jmp(0) |
		pio_encode_sideset_opt(2, HEART_PI5_SCAN_LOOP_SIDESET_BLANK_LOW)
	);

	session->program.instructions = session->instructions;
	session->program.length = HEART_PI5_SCAN_LOOP_PROGRAM_LENGTH;
	session->program.origin = -1;
	session->program_offset = pio_add_program(session->pio, &session->program);
	if (pio_get_error(session->pio)) {
		heart_pi5_scan_loop_teardown_locked(session);
		return -EINVAL;
	}
	session->program_loaded = true;

	sm_config_set_wrap(
		&config,
		session->program_offset,
		session->program_offset + HEART_PI5_SCAN_LOOP_PROGRAM_LENGTH - 1
	);
	sm_config_set_sideset(&config, 3, true, false);
	sm_config_set_out_shift(&config, false, true, HEART_PI5_SCAN_LOOP_PIN_WORD_BITS);
	sm_config_set_set_pins(&config, HEART_PI5_SCAN_LOOP_LAT_GPIO, 1);
	sm_config_set_out_pins(
		&config,
		HEART_PI5_SCAN_LOOP_OUTPUT_PIN_BASE,
		HEART_PI5_SCAN_LOOP_OUTPUT_PIN_COUNT
	);
	sm_config_set_sideset_pins(&config, HEART_PI5_SCAN_LOOP_CLOCK_GPIO);
	/*
	 * The parser writes one contiguous 23-bit output window rooted at GPIO 5.
	 * The bonnet's actual RGB/address pins are sparse within that window, but
	 * the rebased Rust transport has already packed them into the corresponding
	 * bit positions. That is why the state machine can treat the span data as a
	 * plain OUT PINS stream here.
	 */

	result = pio_gpio_init(session->pio, HEART_PI5_SCAN_LOOP_OE_GPIO);
	if (result) {
		heart_pi5_scan_loop_teardown_locked(session);
		return result;
	}
	result = pio_gpio_init(session->pio, HEART_PI5_SCAN_LOOP_LAT_GPIO);
	if (result) {
		heart_pi5_scan_loop_teardown_locked(session);
		return result;
	}
	result = pio_gpio_init(session->pio, HEART_PI5_SCAN_LOOP_CLOCK_GPIO);
	if (result) {
		heart_pi5_scan_loop_teardown_locked(session);
		return result;
	}
	for (index = 0; index < ARRAY_SIZE(HEART_PI5_SCAN_LOOP_RGB_GPIOS); ++index) {
		result = pio_gpio_init(session->pio, HEART_PI5_SCAN_LOOP_RGB_GPIOS[index]);
		if (result) {
			heart_pi5_scan_loop_teardown_locked(session);
			return result;
		}
	}
	for (index = 0; index < ARRAY_SIZE(HEART_PI5_SCAN_LOOP_ADDR_GPIOS); ++index) {
		result = pio_gpio_init(session->pio, HEART_PI5_SCAN_LOOP_ADDR_GPIOS[index]);
		if (result) {
			heart_pi5_scan_loop_teardown_locked(session);
			return result;
		}
	}

	pio_sm_set_consecutive_pindirs(session->pio, (uint)session->sm, HEART_PI5_SCAN_LOOP_OE_GPIO, 1, true);
	pio_sm_set_consecutive_pindirs(session->pio, (uint)session->sm, HEART_PI5_SCAN_LOOP_LAT_GPIO, 1, true);
	pio_sm_set_consecutive_pindirs(session->pio, (uint)session->sm, HEART_PI5_SCAN_LOOP_CLOCK_GPIO, 1, true);
	for (index = 0; index < ARRAY_SIZE(HEART_PI5_SCAN_LOOP_RGB_GPIOS); ++index) {
		pio_sm_set_consecutive_pindirs(
			session->pio,
			(uint)session->sm,
			HEART_PI5_SCAN_LOOP_RGB_GPIOS[index],
			1,
			true
		);
	}
	for (index = 0; index < ARRAY_SIZE(HEART_PI5_SCAN_LOOP_ADDR_GPIOS); ++index) {
		pio_sm_set_consecutive_pindirs(
			session->pio,
			(uint)session->sm,
			HEART_PI5_SCAN_LOOP_ADDR_GPIOS[index],
			1,
			true
		);
	}

	result = pio_sm_init(session->pio, (uint)session->sm, session->program_offset, &config);
	if (result) {
		heart_pi5_scan_loop_teardown_locked(session);
		return result;
	}

	session->frame_cpu = dma_alloc_coherent(
		heart_pi5_scan_loop_pio_device,
		frame_bytes,
		&session->frame_dma,
		GFP_KERNEL
	);
	if (!session->frame_cpu) {
		/*
		 * The replay path depends on stable coherent storage. Earlier
		 * experiments with cached source memory looked faster but produced
		 * unreliable completion accounting, so we fail rather than quietly
		 * falling back to a harder-to-reason-about buffer type.
		 *
		 * This is one of the core trade-offs of the design: correctness and
		 * auditability of the replay completion point take priority over a
		 * faster-but-ambiguous source-buffer mapping.
		 */
		heart_pi5_scan_loop_teardown_locked(session);
		return -ENOMEM;
	}
	session->frame_capacity_bytes = frame_bytes;

	result = pio_sm_set_dmactrl(
		session->pio,
		(uint)session->sm,
		true,
		heart_pi5_scan_loop_dmactrl
	);
	if (result) {
		heart_pi5_scan_loop_teardown_locked(session);
		return result;
	}

	pdev = to_platform_device(heart_pi5_scan_loop_pio_device);
	resource = platform_get_resource(pdev, IORESOURCE_MEM, 0);
	if (!resource) {
		heart_pi5_scan_loop_teardown_locked(session);
		return -ENODEV;
	}
	fifo_offset = (resource_size_t)session->sm * sizeof(uint32_t);
	/*
	 * The RP1 PIO driver exposes the FIFO data window in the device BAR. The
	 * write-combined mapping is the critical optimization: it lets the CPU turn
	 * each replay into a posted store stream instead of a slower device-mapped
	 * write per word.
	 *
	 * The mapping is deliberately only one 32-bit FIFO aperture, not a larger
	 * register block. The worker should have exactly one performance-sensitive
	 * operation available here: write the next TX word.
	 */
	session->fifo_mmio = ioremap_wc(resource->start + fifo_offset, sizeof(uint32_t));
	if (!session->fifo_mmio) {
		heart_pi5_scan_loop_teardown_locked(session);
		return -ENOMEM;
	}

	result = pio_sm_set_enabled(session->pio, (uint)session->sm, true);
	if (result) {
		heart_pi5_scan_loop_teardown_locked(session);
		return result;
	}

	session->configured = true;
	session->frame_loaded = false;
	session->replay_enabled = false;
	session->replay_bytes = 0;
	session->last_error = 0;
	heart_pi5_scan_loop_reset_stats_locked(session);
	heart_pi5_scan_loop_update_worker_runnable_locked(session);
	return 0;
}

static long heart_pi5_scan_loop_ioctl(struct file *file, unsigned int command, unsigned long arg)
{
	struct heart_pi5_scan_loop_session *session = file->private_data;
	void __user *argp = (void __user *)arg;
	long result = 0;

	if (!session) {
		return -ENODEV;
	}

	switch (command) {
	case HEART_PI5_SCAN_LOOP_IOC_INIT: {
		struct heart_pi5_scan_loop_init_args init_args;

		/*
		 * INIT establishes per-open-session ownership of the transport. It does
		 * not load a frame or start replay; it only creates the fixed-capacity
		 * resident environment into which later LOAD/START commands operate.
		 */
		if (copy_from_user(&init_args, argp, sizeof(init_args))) {
			return -EFAULT;
		}
		mutex_lock(&session->lock);
		result = heart_pi5_scan_loop_configure_locked(session, init_args.frame_bytes);
		mutex_unlock(&session->lock);
		return result;
	}
	case HEART_PI5_SCAN_LOOP_IOC_LOAD: {
		struct heart_pi5_scan_loop_load_args load_args;

		if (copy_from_user(&load_args, argp, sizeof(load_args))) {
			return -EFAULT;
		}

		mutex_lock(&session->lock);
		if (!session->configured) {
			result = -EINVAL;
		} else if (session->replay_enabled || session->worker_active) {
			/*
			 * LOAD replaces the resident payload between replay epochs. The
			 * worker snapshots frame_cpu outside the mutex, so STOP must reach
			 * quiescence before LOAD is allowed to overwrite that buffer.
			 */
			result = -EBUSY;
		} else if (load_args.data_bytes == 0 ||
			   load_args.data_bytes > session->frame_capacity_bytes) {
			result = -EINVAL;
		} else if (copy_from_user(
				   session->frame_cpu,
				   u64_to_user_ptr(load_args.data_ptr),
				   load_args.data_bytes
			   )) {
			result = -EFAULT;
		} else {
			/*
			 * A successful LOAD completely replaces the resident replay
			 * payload. There is no partial update contract here: replay_bytes
			 * is the new authoritative frame length, presentations reset, and
			 * the next START begins a new accounting epoch.
			 *
			 * The coherent buffer remains the same allocation across LOADs.
			 * Only its valid prefix changes. That is intentional: fixed
			 * capacity keeps the worker's replay path and teardown logic
			 * simple, and it means LOAD has exactly one mutating operation:
			 * overwrite the resident payload between replay epochs.
			 */
			session->frame_loaded = true;
			session->replay_bytes = load_args.data_bytes;
			session->last_error = 0;
			heart_pi5_scan_loop_reset_stats_locked(session);
			heart_pi5_scan_loop_update_worker_runnable_locked(session);
		}
		mutex_unlock(&session->lock);
		return result;
	}
	case HEART_PI5_SCAN_LOOP_IOC_START:
		mutex_lock(&session->lock);
		if (!session->configured || !session->frame_loaded || session->replay_bytes == 0) {
			result = -EINVAL;
		} else {
			/*
			 * START publishes the already-loaded resident frame to the worker.
			 * It does not copy data or reset hardware state beyond the
			 * presentation-accounting epoch. The worker begins replay lazily
			 * after the wait queue is kicked below.
			 */
			heart_pi5_scan_loop_reset_stats_locked(session);
			session->last_error = 0;
			session->replay_enabled = true;
			heart_pi5_scan_loop_update_worker_runnable_locked(session);
		}
		mutex_unlock(&session->lock);
		wake_up_all(&session->wait_queue);
		return result;
	case HEART_PI5_SCAN_LOOP_IOC_STOP:
	{
		bool wait_for_quiesce;

		mutex_lock(&session->lock);
		/*
		 * STOP is intentionally simple and idempotent. It does not tear down
		 * the PIO program or resident buffer; it only stops future replay
		 * batches. STOP now waits for any in-flight replay snapshot to quiesce
		 * before returning so a following LOAD cannot race resident-buffer
		 * replacement against MMIO replay.
		 */
		session->replay_enabled = false;
		heart_pi5_scan_loop_update_worker_runnable_locked(session);
		wait_for_quiesce = session->worker_active;
		mutex_unlock(&session->lock);
		wake_up_all(&session->wait_queue);
		if (wait_for_quiesce) {
			wait_event(
				session->quiesce_wait_queue,
				READ_ONCE(session->stop_worker) || !READ_ONCE(session->worker_active)
			);
		}
		return 0;
	}
	case HEART_PI5_SCAN_LOOP_IOC_WAIT: {
		struct heart_pi5_scan_loop_wait_args wait_args;

		if (copy_from_user(&wait_args, argp, sizeof(wait_args))) {
			return -EFAULT;
		}
		result = wait_event_interruptible(
			session->wait_queue,
			READ_ONCE(session->stop_worker) ||
			READ_ONCE(session->last_error) != 0 ||
			atomic64_read(&session->presentations) >= wait_args.target_presentations ||
			!READ_ONCE(session->replay_enabled)
		);
		/*
		 * WAIT is level-triggered against the presentation counter. It is not a
		 * "wait for one more interrupt" primitive; callers provide the absolute
		 * presentation count they care about, and WAIT returns once that count
		 * has been reached, replay has been stopped, or the worker reported an
		 * error. That keeps the userspace contract deterministic even if batches
		 * complete faster than the caller can round-trip through ioctl calls.
		 */
		if (result) {
			return result;
		}

		mutex_lock(&session->lock);
		if (session->last_error) {
			result = session->last_error;
		} else {
			/*
			 * WAIT reports the kernel-owned presentation counter. Userspace does
			 * not infer refreshes on its own, which keeps benchmark accounting
			 * tied to the actual replay completion point.
			 */
			wait_args.completed_presentations =
				(u64)atomic64_read(&session->presentations);
		}
		mutex_unlock(&session->lock);
		if (result) {
			return result;
		}
		if (copy_to_user(argp, &wait_args, sizeof(wait_args))) {
			return -EFAULT;
		}
		return 0;
	}
	case HEART_PI5_SCAN_LOOP_IOC_STATS: {
		struct heart_pi5_scan_loop_stats_args stats_args;

		/*
		 * STATS is a snapshot, not a synchronization point. It returns the most
		 * recent kernel-owned accounting state and never waits for a replay
		 * boundary.
		 *
		 * This is the ioctl used by the benchmark path to separate:
		 *   - steady-state replay throughput (presentations / words written)
		 *   - control-path latency (first render / WAIT)
		 *   - failure accounting (last_error / drain_failures)
		 *
		 * In other words, STATS exists so userspace does not have to infer
		 * replay behavior from wall-clock timings alone.
		 */
		mutex_lock(&session->lock);
		memset(&stats_args, 0, sizeof(stats_args));
		stats_args.presentations = (u64)atomic64_read(&session->presentations);
		stats_args.last_error = session->last_error;
		stats_args.frame_bytes = session->replay_bytes;
		stats_args.replay_enabled = session->replay_enabled ? 1 : 0;
		stats_args.batches_submitted = (u64)atomic64_read(&session->batches_submitted);
		stats_args.words_written = (u64)atomic64_read(&session->words_written);
		stats_args.drain_failures = (u64)atomic64_read(&session->drain_failures);
		stats_args.stop_requests_seen_during_batch =
			(u64)atomic64_read(&session->stop_requests_seen_during_batch);
		stats_args.mmio_write_ns = (u64)atomic64_read(&session->mmio_write_ns);
		stats_args.drain_ns = (u64)atomic64_read(&session->drain_ns);
		stats_args.max_batch_replays = READ_ONCE(session->max_batch_replays);
		stats_args.worker_cpu = session->worker_cpu;
		stats_args.worker_priority = session->worker_priority;
		stats_args.worker_runnable = READ_ONCE(session->worker_runnable) ? 1 : 0;
		mutex_unlock(&session->lock);
		if (copy_to_user(argp, &stats_args, sizeof(stats_args))) {
			return -EFAULT;
		}
		return 0;
	}
	default:
		return -ENOTTY;
	}
}

static int heart_pi5_scan_loop_open(struct inode *inode, struct file *file)
{
	struct heart_pi5_scan_loop_session *session;
	int result;

	/*
	 * One open file gets one independent session and one worker. That keeps the
	 * lifetime rules easy to state: close(fd) owns worker shutdown, teardown,
	 * and resident-buffer release for exactly that session.
	 */
	session = kzalloc(sizeof(*session), GFP_KERNEL);
	if (!session) {
		return -ENOMEM;
	}

	mutex_init(&session->lock);
	init_waitqueue_head(&session->wait_queue);
	init_waitqueue_head(&session->quiesce_wait_queue);
	session->sm = -1;
	heart_pi5_scan_loop_reset_stats_locked(session);
	heart_pi5_scan_loop_update_worker_runnable_locked(session);
	result = heart_pi5_scan_loop_start_worker(session);
	if (result) {
		kfree(session);
		return result;
	}

	file->private_data = session;
	return 0;
}

static int heart_pi5_scan_loop_release(struct inode *inode, struct file *file)
{
	struct heart_pi5_scan_loop_session *session = file->private_data;

	if (!session) {
		return 0;
	}

	mutex_lock(&session->lock);
	WRITE_ONCE(session->stop_worker, true);
	session->replay_enabled = false;
	heart_pi5_scan_loop_update_worker_runnable_locked(session);
	mutex_unlock(&session->lock);
	wake_up_all(&session->wait_queue);
	/*
	 * kthread_stop() is the serialization point between release() and the
	 * worker. Only after it returns is teardown_locked() allowed to tear down
	 * the FIFO mapping, PIO state machine, and resident frame buffer.
	 */
	if (session->worker) {
		kthread_stop(session->worker);
		session->worker = NULL;
	}

	mutex_lock(&session->lock);
	heart_pi5_scan_loop_teardown_locked(session);
	mutex_unlock(&session->lock);
	kfree(session);
	file->private_data = NULL;
	return 0;
}

static const struct file_operations heart_pi5_scan_loop_fops = {
	.owner = THIS_MODULE,
	.open = heart_pi5_scan_loop_open,
	.release = heart_pi5_scan_loop_release,
	.unlocked_ioctl = heart_pi5_scan_loop_ioctl,
	.llseek = noop_llseek,
};

static struct miscdevice heart_pi5_scan_loop_miscdevice = {
	.minor = MISC_DYNAMIC_MINOR,
	.name = HEART_PI5_SCAN_LOOP_DEVICE_NAME,
	.fops = &heart_pi5_scan_loop_fops,
	.mode = 0666,
};

static int __init heart_pi5_scan_loop_init(void)
{
	int result;

	/*
	 * The miscdevice is registered first so failures later in init only need to
	 * unwind one user-visible node. The platform-device lookup then locates the
	 * RP1 PIO block we borrow for DMA mapping and FIFO BAR access.
	 */
	result = misc_register(&heart_pi5_scan_loop_miscdevice);
	if (result) {
		return result;
	}

	heart_pi5_scan_loop_pio_device = bus_find_device_by_name(
		&platform_bus_type,
		NULL,
		HEART_PI5_SCAN_LOOP_PIO_DEVICE_NAME
	);
	if (!heart_pi5_scan_loop_pio_device) {
		misc_deregister(&heart_pi5_scan_loop_miscdevice);
		return -ENODEV;
	}

	result = dma_set_mask_and_coherent(heart_pi5_scan_loop_pio_device, DMA_BIT_MASK(64));
	if (result) {
		result = dma_set_mask_and_coherent(heart_pi5_scan_loop_pio_device, DMA_BIT_MASK(40));
	}
	if (result) {
		pr_warn(
			"heart_pi5_scan_loop: dma_set_mask_and_coherent failed for %s: %d\n",
			dev_name(heart_pi5_scan_loop_pio_device),
			result
		);
	}

	return 0;
}

static void __exit heart_pi5_scan_loop_exit(void)
{
	/*
	 * Sessions own their own workers and buffers, so module exit only needs to
	 * drop the borrowed platform-device reference and deregister the miscdevice.
	 */
	if (heart_pi5_scan_loop_pio_device) {
		put_device(heart_pi5_scan_loop_pio_device);
		heart_pi5_scan_loop_pio_device = NULL;
	}
	misc_deregister(&heart_pi5_scan_loop_miscdevice);
}

module_init(heart_pi5_scan_loop_init);
module_exit(heart_pi5_scan_loop_exit);

MODULE_DESCRIPTION("Heart Pi 5 HUB75 resident scan loop benchmark module");
MODULE_LICENSE("GPL");
