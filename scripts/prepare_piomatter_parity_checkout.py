"""Prepare a Piomatter source checkout to use Heart's parity .pio program."""

from __future__ import annotations

import argparse
import re
import shutil
import subprocess
from pathlib import Path

from heart.utilities.logging import get_logger

LOGGER = get_logger(__name__)

REPO_ROOT = Path(__file__).resolve().parents[1]
DEFAULT_PIO_HEADER_RELATIVE_PATH = Path("src/include/piomatter/protomatter.pio.h")
DEFAULT_MATRIXMAP_HEADER_RELATIVE_PATH = Path("src/include/piomatter/matrixmap.h")
DEFAULT_PINS_HEADER_RELATIVE_PATH = Path("src/include/piomatter/pins.h")
DEFAULT_PIOMATTER_HEADER_RELATIVE_PATH = Path("src/include/piomatter/piomatter.h")
DEFAULT_RENDER_HEADER_RELATIVE_PATH = Path("src/include/piomatter/render.h")
DEFAULT_SETUP_PY_RELATIVE_PATH = Path("setup.py")
DEFAULT_OUTPUT_PATH = (
    REPO_ROOT
    / "docs"
    / "research"
    / "generated"
    / "piomatter_override"
    / "protomatter.pio.h"
)
SLAB_DEFINE_PREFIX = "#define HEART_PIOMATTER_SLAB_COPIES "
DEFAULT_TARGET_FREQ_HZ = 27_000_000
DEFAULT_MAX_XFER_BYTES = 262_140
DEFAULT_POST_ADDR_DELAY = 5
DEFAULT_POST_LATCH_DELAY = 0
DEFAULT_POST_OE_DELAY = 0
DEFAULT_RESCALE_MODE = "stock"
RESCALE_MODE_CHOICES = ("stock", "none")
TARGET_FREQ_PATTERN = re.compile(
    r"constexpr double target_freq =\s*\n\s*\d+; // .*"
)
MAX_XFER_PATTERN = re.compile(r"constexpr size_t MAX_XFER = \d+;")
PIOMATTER_THREAD_INCLUDE_PATTERN = re.compile(r'#include <thread>\n')
PIOMATTER_SCHED_INCLUDE_PATTERN = re.compile(r'#include <sched.h>\n')
PIO_XFER_HELPER_PATTERN = re.compile(
    r"static int pio_sm_xfer_data_large\(PIO pio, int sm, int direction, size_t size,\n"
    r"\s+uint32_t \*databuf\) \{.*?\n\}",
    re.DOTALL,
)
POST_ADDR_DELAY_PATTERN = re.compile(r"static constexpr uint32_t post_addr_delay = \d+;")
POST_LATCH_DELAY_PATTERN = re.compile(r"static constexpr uint32_t post_latch_delay = \d+;")
POST_OE_DELAY_PATTERN = re.compile(r"static constexpr uint32_t post_oe_delay = \d+;")
RESCALE_SCHEDULE_PATTERN = re.compile(
    r"schedule_sequence rescale_schedule\(schedule_sequence ss, size_t pixels_across\) \{.*?\n\}",
    re.DOTALL,
)
SETUP_EXTRA_COMPILE_ARGS_PATTERN = re.compile(
    r'extra_compile_args\s*=\s*\[[^\]]*\],'
)
PIOMATTER_DESTRUCTOR_PATTERN = re.compile(
    r"    ~piomatter\(\) \{\n.*?\n    \}\n",
    re.DOTALL,
)
PIO_ADD_PROGRAM_PATTERN = re.compile(
    r"        uint offset = pio_add_program\(pio, &protomatter_program\);\n"
    r"        if \(offset == PIO_ORIGIN_INVALID\) \{\n"
    r'            throw std::runtime_error\("pio_add_program"\);\n'
    r"        \}\n"
)
PIO_MEMBER_PATTERN = re.compile(r"    PIO pio = NULL;\n    int sm = -1;\n")
STOCK_RESCALE_SCHEDULE_BLOCK = """schedule_sequence rescale_schedule(schedule_sequence ss, size_t pixels_across) {
    uint32_t max_active_time = 0;
    for (auto &s : ss) {
        for (auto &ent : s) {
            max_active_time = std::max(ent.active_time, max_active_time);
        }
    }
    if (max_active_time == 0 || max_active_time >= pixels_across) {
        return ss;
    }
    int scale = (pixels_across + max_active_time - 1) / max_active_time;
    for (auto &s : ss) {
        for (auto &ent : s) {
            ent.active_time *= scale;
        }
    }
    return ss;
}"""
NO_RESCALE_SCHEDULE_BLOCK = """schedule_sequence rescale_schedule(schedule_sequence ss, size_t pixels_across) {
    (void)pixels_across;
    return ss;
}"""


def default_generator_path() -> Path:
    candidates = (
        REPO_ROOT
        / "rust"
        / "heart_rgb_matrix_driver"
        / "tools"
        / "generate_piomatter_parity_header.py",
        REPO_ROOT
        / "rust"
        / "heart_rust"
        / "tools"
        / "generate_piomatter_parity_header.py",
    )
    for candidate in candidates:
        if candidate.exists():
            return candidate
    return candidates[0]


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Replace a Piomatter checkout's protomatter.pio.h with Heart's parity header."
    )
    parser.add_argument(
        "--checkout",
        type=Path,
        required=True,
        help="Path to a Piomatter source checkout.",
    )
    parser.add_argument(
        "--generator",
        type=Path,
        default=default_generator_path(),
        help="Path to the parity header generator script.",
    )
    parser.add_argument(
        "--generated-header",
        type=Path,
        default=DEFAULT_OUTPUT_PATH,
        help="Path where the generated parity header should be written before copying.",
    )
    parser.add_argument(
        "--pio-source",
        type=Path,
        help="Optional .pio source to assemble instead of the generator default.",
    )
    parser.add_argument(
        "--render-override",
        type=Path,
        help="Optional replacement render.h to copy into the Piomatter checkout.",
    )
    parser.add_argument(
        "--slab-copies",
        type=int,
        default=1,
        help="Optional slab duplication count to inject into the render override.",
    )
    parser.add_argument(
        "--target-freq-hz",
        type=int,
        default=DEFAULT_TARGET_FREQ_HZ,
        help="PIO state-machine target frequency to write into piomatter.h.",
    )
    parser.add_argument(
        "--max-xfer-bytes",
        type=int,
        default=DEFAULT_MAX_XFER_BYTES,
        help="Configured Piomatter transfer chunk size to write into piomatter.h.",
    )
    parser.add_argument(
        "--post-addr-delay",
        type=int,
        default=DEFAULT_POST_ADDR_DELAY,
        help="Pinout post-address delay to write into pins.h.",
    )
    parser.add_argument(
        "--post-latch-delay",
        type=int,
        default=DEFAULT_POST_LATCH_DELAY,
        help="Pinout post-latch delay to write into pins.h.",
    )
    parser.add_argument(
        "--post-oe-delay",
        type=int,
        default=DEFAULT_POST_OE_DELAY,
        help="Pinout post-OE delay to write into pins.h.",
    )
    parser.add_argument(
        "--rescale-mode",
        type=str,
        default=DEFAULT_RESCALE_MODE,
        choices=RESCALE_MODE_CHOICES,
        help="How Piomatter rescales active_time relative to row width.",
    )
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    destination = args.checkout / DEFAULT_PIO_HEADER_RELATIVE_PATH
    if not destination.parent.exists():
        raise FileNotFoundError(
            f"Piomatter checkout does not look valid; missing {destination.parent}."
        )

    run_generator(args.generator, args.generated_header, args.pio_source)
    shutil.copy2(args.generated_header, destination)
    LOGGER.info("Copied parity header into %s", destination)
    patch_target_frequency(
        args.checkout / DEFAULT_PIOMATTER_HEADER_RELATIVE_PATH,
        args.target_freq_hz,
    )
    patch_max_xfer_bytes(
        args.checkout / DEFAULT_PIOMATTER_HEADER_RELATIVE_PATH,
        args.max_xfer_bytes,
    )
    patch_pinout_delays(
        args.checkout / DEFAULT_PINS_HEADER_RELATIVE_PATH,
        post_addr_delay=args.post_addr_delay,
        post_latch_delay=args.post_latch_delay,
        post_oe_delay=args.post_oe_delay,
    )
    patch_rescale_mode(
        args.checkout / DEFAULT_MATRIXMAP_HEADER_RELATIVE_PATH,
        rescale_mode=args.rescale_mode,
    )
    patch_setup_compile_args(args.checkout / DEFAULT_SETUP_PY_RELATIVE_PATH)
    patch_program_lifecycle(args.checkout / DEFAULT_PIOMATTER_HEADER_RELATIVE_PATH)
    patch_fifo_mode_support(args.checkout / DEFAULT_PIOMATTER_HEADER_RELATIVE_PATH)
    if args.render_override is not None:
        render_destination = args.checkout / DEFAULT_RENDER_HEADER_RELATIVE_PATH
        copy_render_override(args.render_override, render_destination, args.slab_copies)
        LOGGER.info("Copied render override into %s", render_destination)
    return 0


def run_generator(generator_path: Path, output_path: Path, pio_source: Path | None) -> None:
    command = [
        "python3",
        str(generator_path),
        "--output",
        str(output_path),
    ]
    if pio_source is not None:
        command.extend(["--source", str(pio_source)])
    LOGGER.info("Generating Piomatter parity header with %s", command)
    subprocess.run(command, check=True, cwd=REPO_ROOT)


def copy_render_override(source: Path, destination: Path, slab_copies: int) -> None:
    content = source.read_text(encoding="utf-8")
    if slab_copies < 1:
        raise ValueError("slab_copies must be at least 1")
    content = f"{SLAB_DEFINE_PREFIX}{slab_copies}\n{content}"
    destination.write_text(content, encoding="utf-8")


def patch_target_frequency(destination: Path, target_freq_hz: int) -> None:
    if target_freq_hz < 1:
        raise ValueError("target_freq_hz must be positive")
    content = destination.read_text(encoding="utf-8")
    replacement = (
        "constexpr double target_freq =\n"
        f"            {target_freq_hz}; // configurable SM clock target"
    )
    updated_content, replacement_count = TARGET_FREQ_PATTERN.subn(replacement, content, count=1)
    if replacement_count != 1:
        raise ValueError(f"Could not patch target frequency in {destination}")
    destination.write_text(updated_content, encoding="utf-8")
    LOGGER.info("Patched Piomatter target frequency to %s Hz in %s", target_freq_hz, destination)


def patch_max_xfer_bytes(destination: Path, max_xfer_bytes: int) -> None:
    if max_xfer_bytes < 4:
        raise ValueError("max_xfer_bytes must be at least 4")
    if max_xfer_bytes % 4 != 0:
        raise ValueError("max_xfer_bytes must stay 32-bit aligned")
    content = destination.read_text(encoding="utf-8")
    replacement = f"constexpr size_t MAX_XFER = {max_xfer_bytes};"
    updated_content, replacement_count = MAX_XFER_PATTERN.subn(replacement, content)
    if replacement_count < 1:
        raise ValueError(f"Could not patch any MAX_XFER constants in {destination}")
    destination.write_text(updated_content, encoding="utf-8")
    LOGGER.info(
        "Patched %s Piomatter MAX_XFER constant(s) to %s bytes in %s",
        replacement_count,
        max_xfer_bytes,
        destination,
    )


def patch_pinout_delays(
    destination: Path,
    *,
    post_addr_delay: int,
    post_latch_delay: int,
    post_oe_delay: int,
) -> None:
    if min(post_addr_delay, post_latch_delay, post_oe_delay) < 0:
        raise ValueError("Piomatter delays must be non-negative")
    content = destination.read_text(encoding="utf-8")
    replacements = (
        (
            POST_ADDR_DELAY_PATTERN,
            f"static constexpr uint32_t post_addr_delay = {post_addr_delay};",
            "post_addr_delay",
        ),
        (
            POST_LATCH_DELAY_PATTERN,
            f"static constexpr uint32_t post_latch_delay = {post_latch_delay};",
            "post_latch_delay",
        ),
        (
            POST_OE_DELAY_PATTERN,
            f"static constexpr uint32_t post_oe_delay = {post_oe_delay};",
            "post_oe_delay",
        ),
    )
    updated_content = content
    for pattern, replacement, label in replacements:
        updated_content, replacement_count = pattern.subn(replacement, updated_content)
        if replacement_count < 1:
            raise ValueError(f"Could not patch {label} in {destination}")
    destination.write_text(updated_content, encoding="utf-8")
    LOGGER.info(
        "Patched Piomatter delays in %s: post_addr=%s post_latch=%s post_oe=%s",
        destination,
        post_addr_delay,
        post_latch_delay,
        post_oe_delay,
    )


def patch_rescale_mode(destination: Path, *, rescale_mode: str) -> None:
    if rescale_mode not in RESCALE_MODE_CHOICES:
        raise ValueError(f"Unknown rescale mode: {rescale_mode}")
    content = destination.read_text(encoding="utf-8")
    replacement = (
        STOCK_RESCALE_SCHEDULE_BLOCK
        if rescale_mode == "stock"
        else NO_RESCALE_SCHEDULE_BLOCK
    )
    updated_content, replacement_count = RESCALE_SCHEDULE_PATTERN.subn(
        replacement,
        content,
        count=1,
    )
    if replacement_count != 1:
        raise ValueError(f"Could not patch rescale schedule in {destination}")
    destination.write_text(updated_content, encoding="utf-8")
    LOGGER.info("Patched Piomatter rescale mode to %s in %s", rescale_mode, destination)


def patch_setup_compile_args(destination: Path) -> None:
    content = destination.read_text(encoding="utf-8")
    updated_content, replacement_count = SETUP_EXTRA_COMPILE_ARGS_PATTERN.subn(
        'extra_compile_args = ["-g0", "-O2"],',
        content,
        count=1,
    )
    if replacement_count != 1:
        raise ValueError(f"Could not patch setup.py compile flags in {destination}")
    destination.write_text(updated_content, encoding="utf-8")
    LOGGER.info("Patched Piomatter setup.py compile flags in %s", destination)


def patch_program_lifecycle(destination: Path) -> None:
    content = destination.read_text(encoding="utf-8")
    updated_content = content
    if "program_offset = offset;" not in updated_content:
        updated_content, add_program_replacements = PIO_ADD_PROGRAM_PATTERN.subn(
            "        uint offset = pio_add_program(pio, &protomatter_program);\n"
            "        if (offset == PIO_ORIGIN_INVALID) {\n"
            '            throw std::runtime_error("pio_add_program");\n'
            "        }\n"
            "        program_offset = offset;\n",
            updated_content,
            count=1,
        )
        if add_program_replacements != 1:
            raise ValueError(f"Could not patch pio_add_program lifecycle in {destination}")

    if "uint program_offset = PIO_ORIGIN_INVALID;" not in updated_content:
        updated_content, member_replacements = PIO_MEMBER_PATTERN.subn(
            "    PIO pio = NULL;\n"
            "    int sm = -1;\n"
            "    uint program_offset = PIO_ORIGIN_INVALID;\n",
            updated_content,
            count=1,
        )
        if member_replacements != 1:
            raise ValueError(f"Could not add program_offset member in {destination}")

    if "pio_remove_program(pio, &protomatter_program, program_offset);" not in updated_content:
        updated_content, destructor_replacements = PIOMATTER_DESTRUCTOR_PATTERN.subn(
            """    ~piomatter() {
        manager.request_exit();
        if (blitter_thread.joinable()) {
            blitter_thread.join();
        }

        if (pio != NULL && sm >= 0) {
            pio_sm_set_enabled(pio, sm, false);
            pio_sm_clear_fifos(pio, sm);

            pin_deinit_one(pinout::PIN_OE);
            pin_deinit_one(pinout::PIN_CLK);
            pin_deinit_one(pinout::PIN_LAT);

            for (const auto p : pinout::PIN_RGB)
                pin_deinit_one(p);

            for (size_t i = 0; i < geometry.n_addr_lines; i++) {
                pin_deinit_one(pinout::PIN_ADDR[i]);
            }
            pio_sm_unclaim(pio, sm);
            sm = -1;
        }

        if (pio != NULL && program_offset != PIO_ORIGIN_INVALID) {
            static const struct pio_program protomatter_program = {
                .instructions = protomatter,
                .length = 32,
                .origin = -1,
            };
            pio_remove_program(pio, &protomatter_program, program_offset);
            program_offset = PIO_ORIGIN_INVALID;
        }
    }
""",
            updated_content,
            count=1,
        )
        if destructor_replacements != 1:
            raise ValueError(f"Could not patch destructor lifecycle in {destination}")

    destination.write_text(updated_content, encoding="utf-8")
    LOGGER.info("Patched Piomatter program lifecycle in %s", destination)


def patch_fifo_mode_support(destination: Path) -> None:
    content = destination.read_text(encoding="utf-8")
    updated_content = content

    if '#include <sys/ioctl.h>' not in updated_content:
        updated_content, include_replacements = PIOMATTER_THREAD_INCLUDE_PATTERN.subn(
            '#include <thread>\n#include <cerrno>\n#include <cstdlib>\n#include <cstring>\n'
            '#include <sched.h>\n'
            '#include "rp1_pio_if.h"\n'
            '#include <sys/ioctl.h>\n#include <sys/mman.h>\n#include <unistd.h>\n',
            updated_content,
            count=1,
        )
        if include_replacements != 1:
            raise ValueError(f"Could not patch Piomatter includes in {destination}")
    elif '#include "rp1_pio_if.h"' not in updated_content:
        updated_content, include_replacements = PIOMATTER_SCHED_INCLUDE_PATTERN.subn(
            '#include <sched.h>\n#include "rp1_pio_if.h"\n',
            updated_content,
            count=1,
        )
        if include_replacements != 1:
            raise ValueError(f"Could not patch Piomatter rp1_pio_if include in {destination}")

    replacement = r'''#ifndef PIO_IOC_SM_GET_FIFO_MAP_INFO
#define PIO_IOC_MAGIC 102
struct rp1_pio_sm_fifo_state_args {
    uint16_t sm;
    uint8_t tx;
    uint8_t rsvd;
    uint16_t level;
    uint8_t empty;
    uint8_t full;
};
struct rp1_pio_sm_clear_fifos_args {
    uint16_t sm;
};
struct rp1_pio_sm_fifo_map_info_args {
    uint16_t sm;
    uint16_t dir;
    uint32_t mmap_offset;
    uint32_t mmap_bytes;
    uint32_t fifo_offset;
    uint32_t reserved;
};
#define PIO_IOC_SM_FIFO_STATE _IOW(PIO_IOC_MAGIC, 44, struct rp1_pio_sm_fifo_state_args)
#define PIO_IOC_SM_DRAIN_TX _IOW(PIO_IOC_MAGIC, 45, struct rp1_pio_sm_clear_fifos_args)
#define PIO_IOC_SM_GET_FIFO_MAP_INFO _IOWR(PIO_IOC_MAGIC, 58, struct rp1_pio_sm_fifo_map_info_args)
#define PIO_IOC_SM_TX_FENCE _IOW(PIO_IOC_MAGIC, 59, struct rp1_pio_sm_clear_fifos_args)
#endif

static int pio_sm_xfer_data_large(PIO pio, int sm, int direction, size_t size,
                                  uint32_t *databuf) {
    enum fifo_mode {
        FIFO_MODE_DEFAULT = -1,
        FIFO_MODE_RAW = 0,
        FIFO_MODE_FENCE,
        FIFO_MODE_DRAIN,
        FIFO_MODE_GUARD,
    };

    struct heart_rp1_pio_handle {
        pio_instance base;
        const char *devname;
        int fd;
    };

    auto fifo_mode_from_env = []() -> fifo_mode {
        const char *s = std::getenv("RP1_PIO_FIFO_MODE");
        if (!s || !*s) {
            return FIFO_MODE_DEFAULT;
        }
        if (std::strcmp(s, "raw") == 0) {
            return FIFO_MODE_RAW;
        }
        if (std::strcmp(s, "fence") == 0) {
            return FIFO_MODE_FENCE;
        }
        if (std::strcmp(s, "drain") == 0) {
            return FIFO_MODE_DRAIN;
        }
        if (std::strcmp(s, "guard") == 0) {
            return FIFO_MODE_GUARD;
        }
        return FIFO_MODE_DEFAULT;
    };

    auto env_u32 = [](const char *name, unsigned int fallback) -> unsigned int {
        const char *raw = std::getenv(name);
        char *end = nullptr;
        unsigned long parsed;
        if (!raw || !*raw) {
            return fallback;
        }
        errno = 0;
        parsed = std::strtoul(raw, &end, 0);
        if (errno != 0 || !end || *end != 0) {
            return fallback;
        }
        return static_cast<unsigned int>(parsed);
    };

    auto ioctl_errno = [&](unsigned long request, void *arg) -> int {
        auto *rp = reinterpret_cast<heart_rp1_pio_handle *>(pio);
        int r = ioctl(rp->fd, request, arg);
        return (r < 0) ? -errno : r;
    };

    auto default_chunked_xfer = [&]() -> int {
        constexpr size_t MAX_XFER = 262140;
        while (size) {
            size_t xfersize = std::min(size_t{MAX_XFER}, size);
            int r = pio_sm_xfer_data(pio, sm, direction, xfersize, databuf);
            if (r != 0) {
                return r;
            }
            size -= xfersize;
            databuf += xfersize / sizeof(*databuf);
        }
        return 0;
    };

    fifo_mode mode = fifo_mode_from_env();
    if (mode == FIFO_MODE_DEFAULT || direction != PIO_DIR_TO_SM || size == 0 || (size & 3)) {
        return default_chunked_xfer();
    }

    static void *fifo_map = MAP_FAILED;
    static size_t fifo_map_bytes = 0;
    static uint32_t fifo_offset = 0;
    static int fifo_map_fd = -1;
    static int fifo_map_sm = -1;
    static uint64_t call_count = 0;

    auto *rp = reinterpret_cast<heart_rp1_pio_handle *>(pio);
    if (fifo_map == MAP_FAILED || fifo_map_fd != rp->fd || fifo_map_sm != sm) {
        struct rp1_pio_sm_fifo_map_info_args info = {};
        info.sm = static_cast<uint16_t>(sm);
        info.dir = static_cast<uint16_t>(PIO_DIR_TO_SM);
        int r = ioctl_errno(PIO_IOC_SM_GET_FIFO_MAP_INFO, &info);
        if (r < 0) {
            return default_chunked_xfer();
        }
        if (fifo_map != MAP_FAILED) {
            (void)munmap(fifo_map, fifo_map_bytes);
        }
        fifo_map = mmap(NULL, info.mmap_bytes, PROT_READ | PROT_WRITE, MAP_SHARED, rp->fd, info.mmap_offset);
        if (fifo_map == MAP_FAILED) {
            fifo_map_bytes = 0;
            fifo_offset = 0;
            fifo_map_fd = -1;
            fifo_map_sm = -1;
            return default_chunked_xfer();
        }
        fifo_map_bytes = info.mmap_bytes;
        fifo_offset = info.fifo_offset;
        fifo_map_fd = rp->fd;
        fifo_map_sm = sm;
    }

    volatile uint32_t *fifo = reinterpret_cast<volatile uint32_t *>(
        reinterpret_cast<uint8_t *>(fifo_map) + fifo_offset);
    const uint32_t *words = databuf;
    size_t word_count = size / sizeof(*databuf);

    if (mode == FIFO_MODE_GUARD) {
        unsigned int guard_max_words =
            env_u32("RP1_PIO_FIFO_GUARD_MAX_WORDS", 8U);
        unsigned int guard_poll_usec =
            env_u32("RP1_PIO_FIFO_GUARD_POLL_USEC", 0U);
        size_t idx = 0;
        if (!guard_max_words) {
            guard_max_words = 8U;
        }
        while (idx < word_count) {
            struct rp1_pio_sm_fifo_state_args state = {};
            state.sm = static_cast<uint16_t>(sm);
            state.tx = 1;
            int r = ioctl_errno(PIO_IOC_SM_FIFO_STATE, &state);
            if (r < 0) {
                return r;
            }
            unsigned int free_words = 8U - state.level;
            if (!free_words) {
                if (guard_poll_usec) {
                    usleep(guard_poll_usec);
                } else {
                    sched_yield();
                }
                continue;
            }
            if (free_words > guard_max_words) {
                free_words = guard_max_words;
            }
            size_t burst = word_count - idx;
            if (burst > free_words) {
                burst = free_words;
            }
            while (burst--) {
                *fifo = words[idx++];
            }
        }
    } else {
        for (size_t i = 0; i < word_count; ++i) {
            *fifo = words[i];
        }
    }

    call_count++;
    unsigned int sync_every_calls =
        env_u32("RP1_PIO_FIFO_SYNC_EVERY_CALLS", 1U);
    if (sync_every_calls && (call_count % sync_every_calls) == 0) {
        struct rp1_pio_sm_clear_fifos_args args = {};
        args.sm = static_cast<uint16_t>(sm);
        if (mode == FIFO_MODE_FENCE) {
            int r = ioctl_errno(PIO_IOC_SM_TX_FENCE, &args);
            if (r < 0) {
                return r;
            }
        } else if (mode == FIFO_MODE_DRAIN) {
            int r = ioctl_errno(PIO_IOC_SM_DRAIN_TX, &args);
            if (r < 0) {
                return r;
            }
        }
    }
    return 0;
}'''
    updated_content, helper_replacements = PIO_XFER_HELPER_PATTERN.subn(
        replacement,
        updated_content,
        count=1,
    )
    if helper_replacements != 1:
        raise ValueError(f"Could not patch Piomatter FIFO mode support in {destination}")

    destination.write_text(updated_content, encoding="utf-8")
    LOGGER.info("Patched Piomatter FIFO mode support in %s", destination)


if __name__ == "__main__":
    raise SystemExit(main())
