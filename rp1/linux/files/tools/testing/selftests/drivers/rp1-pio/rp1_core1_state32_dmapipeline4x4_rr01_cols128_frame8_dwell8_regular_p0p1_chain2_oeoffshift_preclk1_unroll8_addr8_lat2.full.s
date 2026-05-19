@ BEGIN inlined from rp1_core1_state32_dmapipeline4x4_rr01_cols128_frame8_dwell8_regular_p0p1_chain2_oeoffshift_preclk1_unroll8_addr8_lat2.s
.equ REGULAR_P0P1_WRAP_PREFETCH, 1
.equ REGULAR_P0P1_OE_ACTIVE_DURING_SHIFT, 0
.equ REGULAR_P0P1_PRECLK_NOPS, 1
.equ REGULAR_P0P1_UNROLL, 8
.equ REGULAR_P0P1_ROW_ADDR_STAGE_NOPS, 8
.equ REGULAR_P0P1_LAT_PULSE_NOPS, 2
.equ REGULAR_P0P1_PLANE_COUNT, 8
@ INLINE include rp1_core1_state32_regular_p0p1_chain2_profile.inc
@ BEGIN inlined from rp1_core1_state32_regular_p0p1_chain2_profile.inc
/*
 * Shared PWM11 hzeller "regular" P0/P1 profile for two populated parallel
 * chains. Variant wrappers set only tuning knobs before including this file.
 */
.equ STATUS_MAGIC,        0x52385032 /* R8P2 */
.equ STATUS_ADDR,         0x2000f000
.equ FRAME_COUNTER,       0x2000f004
.equ CTRL_ADDR,           0x2000f008
.equ LEGACY_STATUS_ADDR,  0x200080f0
.equ USE_STATE32_DMA_ROUND_ROBIN_CH01, 1
.equ DMA_ROUND_ROBIN_CHANNELS, 2
.ifndef REGULAR_P0P1_PLANE_COUNT
.equ REGULAR_P0P1_PLANE_COUNT, 11
.endif
.equ PLANE_COUNT,         REGULAR_P0P1_PLANE_COUNT
.equ DWELL_ITERS,         1
.equ SHARED_SLAB_BASE,    0x2000b800
.equ STATE32_BASE,        0x10002000
.equ DMA_PIPE_SLOT0_BASE, 0x20009000
.equ DMA_PIPE_SLOT1_BASE, 0x2000a000
.equ DMA_PIPE_SLOT2_BASE, 0x2000c000
.equ DMA_PIPE_SLOT3_BASE, 0x2000d000
.equ USE_DSRAM_CACHE,     1
.equ USE_STATE32_DMA_PIPELINE4_CHUNK_STREAM, 1
.equ USE_STATE32_ROW_MAJOR_RECORDS, 1
.equ USE_PLANECOUNT_WEIGHTED_DWELL, 1
.equ WEIGHTED_DWELL_BASE, 6
.equ USE_RUNTIME_DWELL_SHIFT_LIMIT, 1
.equ USE_RGB_ONLY_CACHE,  1
.ifndef REGULAR_P0P1_FULL_RIO_WORDS
.equ REGULAR_P0P1_FULL_RIO_WORDS, 0
.endif
.if REGULAR_P0P1_FULL_RIO_WORDS
.equ USE_FULL_STATE32_RIO_WORDS, 1
.endif
.ifndef REGULAR_P0P1_OE_ACTIVE_DURING_SHIFT
.equ REGULAR_P0P1_OE_ACTIVE_DURING_SHIFT, 1
.endif
.if REGULAR_P0P1_OE_ACTIVE_DURING_SHIFT
.equ USE_OE_ACTIVE_DURING_SHIFT, 1
.endif
.ifndef REGULAR_P0P1_USE_OE_SETCLR
.equ REGULAR_P0P1_USE_OE_SETCLR, 1
.endif
.if REGULAR_P0P1_USE_OE_SETCLR
.equ USE_OE_SETCLR,        1
.endif
.ifndef REGULAR_P0P1_USE_LAT_SETCLR
.equ REGULAR_P0P1_USE_LAT_SETCLR, 1
.endif
.if REGULAR_P0P1_USE_LAT_SETCLR
.equ USE_LAT_SETCLR,       1
.endif
.equ ROW_WORDS,           128
.equ DMA_CHUNK_RECORDS,   4
.equ PAD_CTRL_CLK,        0x42
.equ PAD_CTRL_LAT,        0x42
.equ PAD_CTRL_OE,         0x42
.equ PAD_CTRL_ADDR,       0x42
.equ PAD_CTRL_RGB,        0x42

.ifndef REGULAR_P0P1_WRAP_PREFETCH
.equ REGULAR_P0P1_WRAP_PREFETCH, 0
.endif
.if REGULAR_P0P1_WRAP_PREFETCH
.equ USE_STATE32_DMA_PIPELINE_WRAP_PREFETCH, 1
.endif

.ifndef REGULAR_P0P1_PRECLK_NOPS
.equ REGULAR_P0P1_PRECLK_NOPS, 1
.endif
.if REGULAR_P0P1_PRECLK_NOPS == 1
.equ USE_PRECLK_SETUP_NOP1, 1
.elseif REGULAR_P0P1_PRECLK_NOPS == 2
.equ USE_PRECLK_SETUP_NOP2, 1
.elseif REGULAR_P0P1_PRECLK_NOPS != 0
.error "REGULAR_P0P1_PRECLK_NOPS supports 0, 1, or 2"
.endif

.ifndef REGULAR_P0P1_ROW_ADDR_STAGE_NOPS
.equ REGULAR_P0P1_ROW_ADDR_STAGE_NOPS, 8
.endif
.equ ROW_ADDR_STAGE_NOPS, REGULAR_P0P1_ROW_ADDR_STAGE_NOPS

.ifndef REGULAR_P0P1_LAT_PULSE_NOPS
.equ REGULAR_P0P1_LAT_PULSE_NOPS, 2
.endif
.equ LAT_PULSE_NOPS, REGULAR_P0P1_LAT_PULSE_NOPS

.ifndef REGULAR_P0P1_UNROLL
.equ REGULAR_P0P1_UNROLL, 8
.endif
.if REGULAR_P0P1_UNROLL == 16
.equ USE_ROW_WORD_LOOP_UNROLL16, 1
.elseif REGULAR_P0P1_UNROLL == 8
.equ USE_ROW_WORD_LOOP_UNROLL8, 1
.elseif REGULAR_P0P1_UNROLL == 4
.equ USE_ROW_WORD_LOOP_UNROLL4, 1
.else
.error "REGULAR_P0P1_UNROLL supports 4, 8, or 16"
.endif

.equ GPIO_CLK,            17
.equ GPIO_LAT,            4
.equ GPIO_OE,             18
.equ USE_LEGACY_OE_SYNC,  0
.equ GPIO_A,              22
.equ GPIO_B,              23
.equ GPIO_C,              24
.equ GPIO_D,              25
.equ GPIO_E,              15
.equ GPIO_R1,             11
.equ GPIO_G1,             27
.equ GPIO_B1,             7
.equ GPIO_R2,             8
.equ GPIO_G2,             9
.equ GPIO_B2,             10
.equ USE_P1_RGB,          1
.equ GPIO_P1_R1,          12
.equ GPIO_P1_G1,          5
.equ GPIO_P1_B1,          6
.equ GPIO_P1_R2,          19
.equ GPIO_P1_G2,          13
.equ GPIO_P1_B2,          20

@ INLINE include rp1_core1_sram_procrio_state32_isram_tailfast_unroll16_frame11_dwell28.s
@ BEGIN inlined from rp1_core1_sram_procrio_state32_isram_tailfast_unroll16_frame11_dwell28.s
.cpu cortex-m3
.thumb
.syntax unified

/*
 * RP1 core1 state32 SRAM -> PROC_RIO full PWM11 benchmark.
 *
 * Tail-fast STATE32 candidate.  Each SRAM word already carries row address,
 * OE and RGB.  The row tail reuses the final pixel word as the blanked base
 * state instead of rebuilding row address/OE constants after every row.
 */

.ifndef STATUS_ADDR
.equ STATUS_ADDR,    0x200080f0
.endif
.ifndef FRAME_COUNTER
.equ FRAME_COUNTER,  0x200080f4
.endif
.ifndef CTRL_ADDR
.equ CTRL_ADDR,      0x200080f8
.endif
.ifndef STATUS_MAGIC
.equ STATUS_MAGIC,   0x53335446 /* S3TF */
.endif
.equ STATUS_AFTER_START,     0x53305354 /* S0ST */
.equ STATUS_STATE32_ROW,     0x53365252 /* S6RR */
.equ STATUS_STATE32_COPY,    0x53364350 /* S6CP */
.equ STATUS_STATE32_SHIFT,   0x53365348 /* S6SH */
.equ STATUS_SLAB_WAIT,       0x534c5754 /* SLWT */
.equ STATUS_SLAB_COPY,       0x534c4350 /* SLCP */
.equ STATUS_SLAB_SHIFT,      0x534c5348 /* SLSH */
.equ STATUS_SLAB_PLANE_WAIT, 0x53505754 /* SPWT */
.equ STATUS_SLAB_PLANE_COPY, 0x53504350 /* SPCP */
.equ STATUS_SLAB_PLANE_SHIFT, 0x53505348 /* SPSH */
.equ STATUS_CHUNK_WAIT,      0x43485754 /* CHWT */
.equ STATUS_CHUNK_SHIFT,     0x43485348 /* CHSH */
.equ STATUS_DMA_CHUNK_COPY,  0x444d4350 /* DMCP */
.equ STATUS_DMA_CHUNK_SHIFT, 0x444d5348 /* DMSH */
.equ STATUS_PWM6BITS_ROW,    0x50364252 /* P6BR */
.equ STATUS_PWM6BITS_COPY,   0x50364243 /* P6BC */
.equ STATUS_PWM6BITS_SHIFT,  0x50364253 /* P6BS */
.equ COPY_MAGIC,     0x53334350 /* S3CP */
.equ START_MAGIC,    0x48553537 /* HU57 */
.equ LOCAL_ISRAM,    0x10000000
.equ LOCAL_DSRAM,    0x10002000
.ifndef ROW_CACHE_SRC
.equ ROW_CACHE_SRC,  0x200080d0
.endif
.ifndef ROW_CACHE_COUNT
.equ ROW_CACHE_COUNT, 0x200080d4
.endif
.ifndef ROW_CACHE_PLANE_COUNT
.equ ROW_CACHE_PLANE_COUNT, 0x200080d8
.endif
.ifndef CHUNK_DEBUG_FIRST_INDEX
.equ CHUNK_DEBUG_FIRST_INDEX, 0x200080e0
.endif
.ifndef CHUNK_DEBUG_COUNT
.equ CHUNK_DEBUG_COUNT, 0x200080e4
.endif
.ifndef CHUNK_DEBUG_SEQ
.equ CHUNK_DEBUG_SEQ, 0x200080e8
.endif
.ifndef SHARED_STATE32_BASE
.equ SHARED_STATE32_BASE, 0x2000c000
.endif
.ifndef SHARED_SLAB_BASE
.equ SHARED_SLAB_BASE, 0x2000e000
.endif
.ifndef SHARED_PWM6_BITS_BASE
.equ SHARED_PWM6_BITS_BASE, 0x2000d000
.endif
.ifndef SLAB_SCAN_ROW_ADDR
.equ SLAB_SCAN_ROW_ADDR, 0x2000ff20
.endif
.equ SLAB_HOST_SEQ_OFF, 0
.equ SLAB_CORE_SEQ_OFF, 4
.equ SLAB_RING_COUNT_OFF, 8
.equ SLAB_BYTES_OFF, 12
.equ SLAB_SLOT_BASE_OFF, 16
.ifndef SLAB_SLOT_STRIDE
.equ SLAB_SLOT_STRIDE, 1552
.endif
.ifndef SLAB_RING_MASK
.equ SLAB_RING_MASK, 3
.endif
.equ SLAB_SLOT_ROW_PAIR_OFF, 0
.equ SLAB_SLOT_FRAME_ID_OFF, 4
.equ SLAB_SLOT_FLAGS_OFF, 8
.equ SLAB_SLOT_RESERVED_OFF, 12
.equ SLAB_SLOT_DATA_OFF, 16
.equ CHUNK_HOST_SEQ_OFF, 0
.equ CHUNK_CORE_SEQ_OFF, 4
.equ CHUNK_FIRST_INDEX_OFF, 8
.equ CHUNK_COUNT_OFF, 12
.equ CHUNK_DATA_OFF, 16
.equ DMA_CHUNK_SRC_LO_OFF, 0
.equ DMA_CHUNK_SRC_HI_OFF, 4
.equ DMA_CHUNK_STATUS_OFF, 8
.equ DMA_CHUNK_DWELL_SHIFT_LIMIT_OFF, 12
.equ DMA_CHUNK_DATA_OFF, 16
.ifndef SHARED_RGB6_BASE
.equ SHARED_RGB6_BASE, 0x2000c000
.endif
.ifndef SHARED_RGB333_BASE
.equ SHARED_RGB333_BASE, 0x2000c000
.endif
.ifndef SHARED_RGB444_BASE
.equ SHARED_RGB444_BASE, 0x2000c000
.endif
.ifndef SHARED_RGB888_BASE
.equ SHARED_RGB888_BASE, 0x2000c000
.endif
.ifndef RGB888_DEBUG_BASE
.equ RGB888_DEBUG_BASE, 0x2000b000
.endif
.ifndef RGB888_DEBUG_SOURCE_BASE
.equ RGB888_DEBUG_SOURCE_BASE, 0x2000b080
.endif
.ifndef STATE32_BASE
.equ STATE32_BASE,   0x2000c000
.endif
.ifndef PLANE_COUNT
.equ PLANE_COUNT,    11
.endif
.ifndef DMA_CHUNK_RECORDS
.equ DMA_CHUNK_RECORDS, 8
.endif
.ifndef DMA_CHUNK_DATA_BASE
.equ DMA_CHUNK_DATA_BASE, (SHARED_SLAB_BASE + DMA_CHUNK_DATA_OFF)
.endif
.ifndef DMA_CHUNK_ALT_DATA_BASE
.equ DMA_CHUNK_ALT_DATA_BASE, (DMA_CHUNK_DATA_BASE + (DMA_CHUNK_RECORDS * ROW_WORDS * 4))
.endif
.ifndef DMA_PIPE_SLOT0_BASE
.equ DMA_PIPE_SLOT0_BASE, 0x20002000
.endif
.ifndef DMA_PIPE_SLOT1_BASE
.equ DMA_PIPE_SLOT1_BASE, 0x20004000
.endif
.ifndef DMA_PIPE_SLOT2_BASE
.equ DMA_PIPE_SLOT2_BASE, 0x20006000
.endif
.ifndef DMA_PIPE_SLOT3_BASE
.equ DMA_PIPE_SLOT3_BASE, 0x2000c000
.endif
.ifndef DMA_PIPE_SLOT4_BASE
.equ DMA_PIPE_SLOT4_BASE, 0x2000d000
.endif
.ifndef DMA_PIPE_SLOT5_BASE
.equ DMA_PIPE_SLOT5_BASE, 0x2000e000
.endif
.ifndef DMA_PIPE_SLOT6_BASE
.equ DMA_PIPE_SLOT6_BASE, 0x2000f000
.endif
.ifndef DMA_PIPE_SLOT7_BASE
.equ DMA_PIPE_SLOT7_BASE, 0x2000f800
.endif
.ifndef DMA_PIPE_SLOT_COUNT
.equ DMA_PIPE_SLOT_COUNT, 4
.endif
.ifndef DMA_ASYNC_UNDERRUN_COUNTER
.equ DMA_ASYNC_UNDERRUN_COUNTER, (SHARED_SLAB_BASE + CHUNK_COUNT_OFF)
.endif

.equ IO_CTRL_BASE, 0x400d0004
.equ PAD_BASE,     0x400f0004
.equ RIO_OUT,      0xf0004000
.equ RIO_XOR,      0xf0005000
.equ RIO_SET,      0xf0006000
.equ RIO_CLR,      0xf0007000
.equ FN_PROC_RIO,  0x86
.equ RP1_DMA_BASE, 0x40188000
.ifndef RP1_DMA_CHANNEL
.equ RP1_DMA_CHANNEL, 7
.endif
.ifndef DMA_ROUND_ROBIN_CHANNELS
.ifdef USE_STATE32_DMA_ROUND_ROBIN_CH01
.equ DMA_ROUND_ROBIN_CHANNELS, 2
.else
.equ DMA_ROUND_ROBIN_CHANNELS, 1
.endif
.endif
.equ RP1_DMA_CH7_BASE, (RP1_DMA_BASE + 0x100 + (RP1_DMA_CHANNEL * 0x100))
.equ RP1_DMA_CFG, 0x010
.equ RP1_DMA_CHEN, 0x018
.equ RP1_DMA_COMMON_INTCLEAR, 0x038
.equ RP1_DMA_CH_SAR, 0x000
.equ RP1_DMA_CH_DAR, 0x008
.equ RP1_DMA_CH_BLOCK_TS, 0x010
.equ RP1_DMA_CH_CTL_L, 0x018
.equ RP1_DMA_CH_CTL_H, 0x01c
.equ RP1_DMA_CH_CFG_L, 0x020
.equ RP1_DMA_CH_CFG_H, 0x024
.equ RP1_DMA_CH_LLP, 0x028
.equ RP1_DMA_CH_INTSTATUS_ENA, 0x080
.equ RP1_DMA_CH_INTSTATUS, 0x088
.equ RP1_DMA_CH_INTSIGNAL_ENA, 0x090
.equ RP1_DMA_CH_INTCLEAR, 0x098
.equ RP1_DMA_IRQ_DMA_TRF, 0x00000002
.equ RP1_DMA_IRQ_DONE_OR_ERR, 0x003fff62
.equ RP1_DMA_CH7_ENABLE_WE, ((1 << RP1_DMA_CHANNEL) | (1 << (RP1_DMA_CHANNEL + 8)))
.equ RP1_DMA_CH7_DISABLE_WE, (1 << (RP1_DMA_CHANNEL + 8))
.equ RP1_DMA_CTL_LO_MEMCPY32, 0x40045200
.equ RP1_DMA_CTL_H_MEMCPY32, 0x000783c0
.equ RP1_DMA_CTL_H_MEMCPY32_BURST4, 0x000381c0
.equ RP1_DMA_CFG_H_MEMCPY, 0x000e0018
.equ RP1_DMA_CHUNK_BLOCK_TS_32, ((DMA_CHUNK_RECORDS * ROW_WORDS) - 1)
.equ STATE32_DMA_TOTAL_RECORDS, (32 * PLANE_COUNT)
.ifndef PAD_CTRL
.equ PAD_CTRL,     0x56
.endif
.ifndef PAD_CTRL_CLK
.equ PAD_CTRL_CLK, PAD_CTRL
.endif
.ifndef PAD_CTRL_LAT
.equ PAD_CTRL_LAT, PAD_CTRL
.endif
.ifndef PAD_CTRL_OE
.equ PAD_CTRL_OE, PAD_CTRL
.endif
.ifndef PAD_CTRL_ADDR
.equ PAD_CTRL_ADDR, PAD_CTRL
.endif
.ifndef PAD_CTRL_ADDR_A
.equ PAD_CTRL_ADDR_A, PAD_CTRL_ADDR
.endif
.ifndef PAD_CTRL_ADDR_B
.equ PAD_CTRL_ADDR_B, PAD_CTRL_ADDR
.endif
.ifndef PAD_CTRL_ADDR_C
.equ PAD_CTRL_ADDR_C, PAD_CTRL_ADDR
.endif
.ifndef PAD_CTRL_ADDR_D
.equ PAD_CTRL_ADDR_D, PAD_CTRL_ADDR
.endif
.ifndef PAD_CTRL_ADDR_E
.equ PAD_CTRL_ADDR_E, PAD_CTRL_ADDR
.endif
.ifndef PAD_CTRL_RGB
.equ PAD_CTRL_RGB, PAD_CTRL
.endif

.ifndef GPIO_CLK
.equ GPIO_CLK,     17
.endif
.ifndef GPIO_LAT
.equ GPIO_LAT,     21
.endif
.ifndef GPIO_OE
.equ GPIO_OE,      18
.endif
.ifndef GPIO_OE_LEGACY
.equ GPIO_OE_LEGACY, 4
.endif
.ifndef USE_LEGACY_OE_SYNC
.equ USE_LEGACY_OE_SYNC, 1
.endif
.ifndef GPIO_A
.equ GPIO_A,       22
.endif
.ifndef GPIO_B
.equ GPIO_B,       26
.endif
.ifndef GPIO_C
.equ GPIO_C,       27
.endif
.ifndef GPIO_D
.equ GPIO_D,       20
.endif
.ifndef GPIO_E
.equ GPIO_E,       24
.endif
.ifndef GPIO_R1
.equ GPIO_R1,      5
.endif
.ifndef GPIO_G1
.equ GPIO_G1,      13
.endif
.ifndef GPIO_B1
.equ GPIO_B1,      6
.endif
.ifndef GPIO_R2
.equ GPIO_R2,      12
.endif
.ifndef GPIO_G2
.equ GPIO_G2,      16
.endif
.ifndef GPIO_B2
.equ GPIO_B2,      23
.endif
.ifndef USE_P1_RGB
.equ USE_P1_RGB,   0
.endif
.ifndef GPIO_P1_R1
.equ GPIO_P1_R1,   12
.endif
.ifndef GPIO_P1_G1
.equ GPIO_P1_G1,   5
.endif
.ifndef GPIO_P1_B1
.equ GPIO_P1_B1,   6
.endif
.ifndef GPIO_P1_R2
.equ GPIO_P1_R2,   19
.endif
.ifndef GPIO_P1_G2
.equ GPIO_P1_G2,   13
.endif
.ifndef GPIO_P1_B2
.equ GPIO_P1_B2,   20
.endif

.equ PIN_CLK,      (1 << GPIO_CLK)
.equ PIN_LAT,      (1 << GPIO_LAT)
.equ PIN_OE,       (1 << GPIO_OE)
.if USE_LEGACY_OE_SYNC
.equ PIN_OE_LEGACY, (1 << GPIO_OE_LEGACY)
.equ PIN_OE_ALL,   (PIN_OE | PIN_OE_LEGACY)
.else
.equ PIN_OE_LEGACY, 0
.equ PIN_OE_ALL,   PIN_OE
.endif
.equ PIN_A,        (1 << GPIO_A)
.equ PIN_B,        (1 << GPIO_B)
.equ PIN_C,        (1 << GPIO_C)
.equ PIN_D,        (1 << GPIO_D)
.equ PIN_E,        (1 << GPIO_E)
.equ PIN_R1,       (1 << GPIO_R1)
.equ PIN_G1,       (1 << GPIO_G1)
.equ PIN_B1,       (1 << GPIO_B1)
.equ PIN_R2,       (1 << GPIO_R2)
.equ PIN_G2,       (1 << GPIO_G2)
.equ PIN_B2,       (1 << GPIO_B2)
.equ PIN_P1_R1,    (1 << GPIO_P1_R1)
.equ PIN_P1_G1,    (1 << GPIO_P1_G1)
.equ PIN_P1_B1,    (1 << GPIO_P1_B1)
.equ PIN_P1_R2,    (1 << GPIO_P1_R2)
.equ PIN_P1_G2,    (1 << GPIO_P1_G2)
.equ PIN_P1_B2,    (1 << GPIO_P1_B2)
.equ KEY_PINS,     (PIN_CLK | PIN_LAT | PIN_OE_ALL | PIN_A | PIN_B | PIN_C | PIN_D | PIN_E)
.equ ADDR_OE_PINS, (PIN_OE_ALL | PIN_A | PIN_B | PIN_C | PIN_D | PIN_E)
.if USE_P1_RGB
.equ RGB_PINS,     (PIN_R1 | PIN_G1 | PIN_B1 | PIN_R2 | PIN_G2 | PIN_B2 | PIN_P1_R1 | PIN_P1_G1 | PIN_P1_B1 | PIN_P1_R2 | PIN_P1_G2 | PIN_P1_B2)
.else
.equ RGB_PINS,     (PIN_R1 | PIN_G1 | PIN_B1 | PIN_R2 | PIN_G2 | PIN_B2)
.endif
.equ ALL_PINS,     (KEY_PINS | RGB_PINS)
.equ RGB_CLK_PINS, (RGB_PINS | PIN_CLK)
.ifndef DWELL_ITERS
.equ DWELL_ITERS,  28
.endif

/*
 * Timing knobs accepted by this common worker include.  Wrappers can set these
 * with .equ before including this file; the older USE_*_NOP feature aliases
 * still work for existing candidates.
 *
 *   DWELL_ITERS                    OE-active dwell loop after each LAT
 *   CLK_HIGH_NOPS / CLK_LOW_NOPS   extra in-row CLK high/low hold NOPs
 *   PRECLK_SETUP_NOPS              RGB/data setup before raising CLK
 *   DATA_SETUP_NOPS                CLK-in-OUT path setup before CLK-high word
 *   ROW_ADDR_SETUP_NOPS            first-row-address setup before first CLK
 *   ROW_ADDR_STAGE_NOPS            RGB SET/CLR row-address staging delay
 *   ROW_ADDR_PRIME_DATA_SETUP_NOPS extra setup after address-prime word
 *   ROW_END_HOLD_NOPS              hold after the last row CLK before LAT/OE tail
 *   LAT_PULSE_NOPS                 LAT high pulse width
 *   OE_BLANK_LEAD_NOPS             OE-blank lead before LAT assertion
 *   OE_ENABLE_NOPS                 hold after OE enable before dwell loop
 *   OE_BLANK_HOLD_NOPS             hold after OE blanking before next row work
 *   USE_CTRL_RGB_BLANK             clear RGB pins during direct-control blanking
 */

.macro CONFIG_NOPS count
    .if \count > 0
    .rept \count
    nop
    .endr
    .endif
.endm

.macro PRECLK_SETUP_DELAY
.ifdef PRECLK_SETUP_NOPS
    CONFIG_NOPS PRECLK_SETUP_NOPS
.else
.ifdef USE_PRECLK_SETUP_NOP1
    nop
.endif
.ifdef USE_PRECLK_SETUP_NOP2
    .rept 2
    nop
    .endr
.endif
.endif
.endm

.macro CLK_HIGH_DELAY
.ifdef CLK_HIGH_NOPS
    CONFIG_NOPS CLK_HIGH_NOPS
.else
.ifdef USE_CLK_OUT_NOP
    nop
.endif
.ifdef USE_CLK_SET_NOP
    nop
.endif
.ifdef USE_CLK_SET_NOP2
    .rept 2
    nop
    .endr
.endif
.ifdef USE_CLK_SET_NOP3
    .rept 3
    nop
    .endr
.endif
.ifdef USE_CLK_SET_NOP4
    .rept 4
    nop
    .endr
.endif
.endif
.endm

.macro CLK_LOW_DELAY
.ifdef CLK_LOW_NOPS
    CONFIG_NOPS CLK_LOW_NOPS
.endif
.endm

.macro LAT_PULSE_DELAY
.ifdef LAT_PULSE_NOPS
    CONFIG_NOPS LAT_PULSE_NOPS
.endif
.endm

.macro OE_BLANK_LEAD_DELAY
.ifdef OE_BLANK_LEAD_NOPS
    CONFIG_NOPS OE_BLANK_LEAD_NOPS
.endif
.endm

.macro OE_ENABLE_DELAY
.ifdef OE_ENABLE_NOPS
    CONFIG_NOPS OE_ENABLE_NOPS
.endif
.endm

.macro OE_BLANK_HOLD_DELAY
.ifdef OE_BLANK_HOLD_NOPS
    CONFIG_NOPS OE_BLANK_HOLD_NOPS
.endif
.endm

.macro ROW_ADDR_SETUP_DELAY
.ifdef ROW_ADDR_SETUP_NOPS
    CONFIG_NOPS ROW_ADDR_SETUP_NOPS
.else
.ifdef USE_ROW_ADDR_SETUP_NOP1
    nop
.endif
.ifdef USE_ROW_ADDR_SETUP_NOP2
    .rept 2
    nop
    .endr
.endif
.ifdef USE_ROW_ADDR_SETUP_NOP4
    .rept 4
    nop
    .endr
.endif
.ifdef USE_ROW_ADDR_SETUP_NOP8
    .rept 8
    nop
    .endr
.endif
.endif
.endm

.macro ROW_ADDR_STAGE_DELAY
.ifdef ROW_ADDR_STAGE_NOPS
    CONFIG_NOPS ROW_ADDR_STAGE_NOPS
.else
.ifdef USE_ROW_ADDR_STAGE_NOP4
    .rept 4
    nop
    .endr
.endif
.ifdef USE_ROW_ADDR_STAGE_NOP5
    .rept 5
    nop
    .endr
.endif
.ifdef USE_ROW_ADDR_STAGE_NOP6
    .rept 6
    nop
    .endr
.endif
.ifdef USE_ROW_ADDR_STAGE_NOP7
    .rept 7
    nop
    .endr
.endif
.ifdef USE_ROW_ADDR_STAGE_NOP8
    .rept 8
    nop
    .endr
.endif
.endif
.endm

.macro ROW_ADDR_PRIME_DATA_SETUP_DELAY
.ifdef ROW_ADDR_PRIME_DATA_SETUP_NOPS
    CONFIG_NOPS ROW_ADDR_PRIME_DATA_SETUP_NOPS
.else
.ifdef USE_ROW_ADDR_PRIME_DATA_SETUP_NOP1
    nop
.endif
.ifdef USE_ROW_ADDR_PRIME_DATA_SETUP_NOP2
    .rept 2
    nop
    .endr
.endif
.endif
.endm

.macro ROW_END_HOLD_DELAY
.ifdef ROW_END_HOLD_NOPS
    CONFIG_NOPS ROW_END_HOLD_NOPS
.endif
.endm

.macro DWELL
.ifdef USE_PLANECOUNT_WEIGHTED_DWELL
    .ifndef WEIGHTED_DWELL_BASE
    .equ WEIGHTED_DWELL_BASE, 1
    .endif
    .if WEIGHTED_DWELL_BASE > 0
    movs r1, #PLANE_COUNT
    subs r1, r1, r7
.ifdef USE_RUNTIME_DWELL_SHIFT_LIMIT
    movw r2, #:lower16:SHARED_SLAB_BASE
    movt r2, #:upper16:SHARED_SLAB_BASE
    ldr r2, [r2, #DMA_CHUNK_DWELL_SHIFT_LIMIT_OFF]
    cmp r1, r2
    bls 1f
    mov r1, r2
1:
.else
.ifdef WEIGHTED_DWELL_SHIFT_LIMIT
    cmp r1, #WEIGHTED_DWELL_SHIFT_LIMIT
    bls 1f
    movs r1, #WEIGHTED_DWELL_SHIFT_LIMIT
1:
.endif
.endif
    movs r2, #WEIGHTED_DWELL_BASE
    lsls r1, r2, r1
2:
    subs r1, #1
    bne 2b
    .endif
.else
.ifdef USE_RGB111_WEIGHTED_DWELL
    .ifndef RGB111_DWELL_BASE
    .equ RGB111_DWELL_BASE, 1
    .endif
    .if RGB111_DWELL_BASE > 0
    movs r1, #11
    subs r1, r1, r7
    movs r2, #RGB111_DWELL_BASE
    lsls r1, r2, r1
2:
    subs r1, #1
    bne 2b
    .endif
.else
.ifdef USE_RGB888_WEIGHTED_DWELL
    .ifndef RGB888_DWELL_BASE
    .equ RGB888_DWELL_BASE, 1
    .endif
    .if RGB888_DWELL_BASE > 0
    movs r1, #8
    subs r1, r1, r7
    movs r2, #RGB888_DWELL_BASE
    lsls r1, r2, r1
2:
    subs r1, #1
    bne 2b
    .endif
.else
    .if DWELL_ITERS > 0
    .if DWELL_ITERS > 255
    movw r1, #:lower16:DWELL_ITERS
    .else
    movs r1, #DWELL_ITERS
    .endif
2:
    subs r1, #1
    bne 2b
    .endif
.endif
.endif
.endif
.endm

.macro PIX reg
.ifdef USE_CLK_IN_OUT_R5
.ifdef USE_DATA_SETUP_BEFORE_CLK
    str \reg, [r8]
.ifdef DATA_SETUP_NOPS
    CONFIG_NOPS DATA_SETUP_NOPS
.endif
.endif
.ifdef USE_CLK_OUT_SCRATCH_LR
    orr lr, \reg, #PIN_CLK
    str lr, [r8]
.else
    orr r5, \reg, #PIN_CLK
    str r5, [r8]
.endif
    CLK_HIGH_DELAY
    str \reg, [r8]
    CLK_LOW_DELAY
.else
.ifdef USE_SHIFT_CONSTANT_OE_R5
    str r5, [r8]
.else
    str \reg, [r8]
.endif
    PRECLK_SETUP_DELAY
    str r9, [lr]
    CLK_HIGH_DELAY
.endif
.endm

.macro CLK_LOW
.ifdef USE_CLK_IN_OUT_R5
.else
.ifdef USE_CLK_SETCLR
.ifdef USE_CLK_CLR_R10
    str r9, [r10]
.else
    movw r0, #:lower16:RIO_CLR
    movt r0, #:upper16:RIO_CLR
    str r9, [r0]
.endif
.else
    str r9, [lr]
.endif
    CLK_LOW_DELAY
.endif
.endm

.macro LOAD_CLK_PTRS
    movw r9, #:lower16:PIN_CLK
    movt r9, #:upper16:PIN_CLK
.ifdef USE_SHIFT_CONSTANT_OE_R5
    movw r5, #:lower16:PIN_OE_ALL
    movt r5, #:upper16:PIN_OE_ALL
.endif
.ifdef USE_CLK_SETCLR
    movw lr, #:lower16:RIO_SET
    movt lr, #:upper16:RIO_SET
.ifdef USE_CLK_CLR_R10
    movw r10, #:lower16:RIO_CLR
    movt r10, #:upper16:RIO_CLR
.endif
.else
    movw lr, #:lower16:RIO_XOR
    movt lr, #:upper16:RIO_XOR
.endif
.ifdef USE_SHIFT_LAT_CLR_R11
    movw r11, #:lower16:PIN_LAT
    movt r11, #:upper16:PIN_LAT
.endif
.endm

.macro LOAD_RGB_SETCLR_PTRS
    movw r8, #:lower16:RIO_SET
    movt r8, #:upper16:RIO_SET
    movw r10, #:lower16:RIO_CLR
    movt r10, #:upper16:RIO_CLR
    movw r9, #:lower16:PIN_CLK
    movt r9, #:upper16:PIN_CLK
.ifdef USE_RGB_SETCLR_EXPLICIT_CLKLOW
    movw r5, #:lower16:RGB_PINS
    movt r5, #:upper16:RGB_PINS
.else
    movw r5, #:lower16:RGB_CLK_PINS
    movt r5, #:upper16:RGB_CLK_PINS
.endif
.ifdef USE_RGB_ONLY_CACHE
    movw r2, #:lower16:RGB_PINS
    movt r2, #:upper16:RGB_PINS
.endif
.endm

.macro PIX_RGB_SETCLR reg
.ifdef USE_RGB_SETCLR_EXPLICIT_CLKLOW
    str r5, [r10]
    str \reg, [r8]
    PRECLK_SETUP_DELAY
    str r9, [r8]
    CLK_HIGH_DELAY
    str r9, [r10]
    CLK_LOW_DELAY
.else
    str r5, [r10]
    str \reg, [r8]
    PRECLK_SETUP_DELAY
    str r9, [r8]
    CLK_HIGH_DELAY
.endif
.endm

.macro PIX_RGB_SETCLR_LOAD
    ldr r0, [r12], #4
.ifdef USE_RGB_ONLY_CACHE
    ands r0, r0, r2
.endif
    PIX_RGB_SETCLR r0
.endm

.macro PIX_DIRECT_OUT_LOAD
    ldr r0, [r12], #4
    str r0, [r8]
.endm

.ifndef ROW_WORDS
.equ ROW_WORDS, 64
.endif

.macro SHIFT_ROW_RGB_SETCLR
.ifdef USE_ROW_WORD_LOOP_UNROLL16
    movw r3, #:lower16:(ROW_WORDS / 16)
    movt r3, #:upper16:(ROW_WORDS / 16)
.Lshift_row_rgb_setclr_loop\@:
    .rept 16
    PIX_RGB_SETCLR_LOAD
    .endr
    subs r3, #1
    bne .Lshift_row_rgb_setclr_loop\@
.else
.ifdef USE_ROW_WORD_LOOP_UNROLL8
    movw r3, #:lower16:(ROW_WORDS / 8)
    movt r3, #:upper16:(ROW_WORDS / 8)
.Lshift_row_rgb_setclr_loop\@:
    .rept 8
    PIX_RGB_SETCLR_LOAD
    .endr
    subs r3, #1
    bne .Lshift_row_rgb_setclr_loop\@
.else
.ifdef USE_ROW_WORD_LOOP_UNROLL4
    movw r3, #:lower16:(ROW_WORDS / 4)
    movt r3, #:upper16:(ROW_WORDS / 4)
.Lshift_row_rgb_setclr_loop\@:
    .rept 4
    PIX_RGB_SETCLR_LOAD
    .endr
    subs r3, #1
    bne .Lshift_row_rgb_setclr_loop\@
.else
.ifdef USE_ROW_WORD_LOOP
    movw r3, #:lower16:ROW_WORDS
    movt r3, #:upper16:ROW_WORDS
.Lshift_row_rgb_setclr_loop\@:
    PIX_RGB_SETCLR_LOAD
    subs r3, #1
    bne .Lshift_row_rgb_setclr_loop\@
.else
    .rept ROW_WORDS
    PIX_RGB_SETCLR_LOAD
    .endr
.endif
.endif
.endif
.endif
.endm

.macro SHIFT_ROW_DIRECT_OUT
.ifdef USE_ROW_WORD_LOOP_UNROLL2
    movw r3, #:lower16:(ROW_WORDS / 2)
    movt r3, #:upper16:(ROW_WORDS / 2)
.Lshift_row_direct_out_loop\@:
    PIX_DIRECT_OUT_LOAD
    PIX_DIRECT_OUT_LOAD
    subs r3, #1
    bne .Lshift_row_direct_out_loop\@
.else
.ifdef USE_ROW_WORD_LOOP
    movw r3, #:lower16:ROW_WORDS
    movt r3, #:upper16:ROW_WORDS
.Lshift_row_direct_out_loop\@:
    PIX_DIRECT_OUT_LOAD
    subs r3, #1
    bne .Lshift_row_direct_out_loop\@
.else
    .rept ROW_WORDS
    PIX_DIRECT_OUT_LOAD
    .endr
.endif
.endif
.endm

.macro ROW_DIRECT_OUT
    SHIFT_ROW_DIRECT_OUT
    movw r8, #:lower16:RIO_OUT
    movt r8, #:upper16:RIO_OUT
    OE_ENABLE
    DWELL
    OE_BLANK
    LAT_LOW_GUARD
.endm

.macro SET_ROWMAJOR_ADDR_DWELL_FROM_INDEX index_reg
    mov r0, \index_reg
    movs r9, #0
.Lrowmajor_div_loop\@:
    cmp r0, #PLANE_COUNT
    blo .Lrowmajor_div_done\@
    subs r0, #PLANE_COUNT
    adds r9, #1
    b .Lrowmajor_div_loop\@
.Lrowmajor_div_done\@:
    movs r7, #PLANE_COUNT
    subs r7, r7, r0
.endm

.macro ROW_RGB_SETCLR
.ifdef USE_OE_ACTIVE_DURING_SHIFT
    movw r8, #:lower16:RIO_OUT
    movt r8, #:upper16:RIO_OUT
    PULSE_LAT
    OE_ENABLE
    DWELL
    LOAD_RGB_SETCLR_PTRS
    SHIFT_ROW_RGB_SETCLR
    ROW_END_HOLD_DELAY
    movw r8, #:lower16:RIO_OUT
    movt r8, #:upper16:RIO_OUT
    OE_BLANK
    LAT_LOW_GUARD
.else
    SHIFT_ROW_RGB_SETCLR
    ROW_END_HOLD_DELAY
    movw r8, #:lower16:RIO_OUT
    movt r8, #:upper16:RIO_OUT
    PULSE_LAT
    OE_ENABLE
    DWELL
    OE_BLANK
    LAT_LOW_GUARD
.endif
.endm

.macro ROW_RGB_OUT
    SHIFT_ROW_STATE32
    movw r8, #:lower16:RIO_OUT
    movt r8, #:upper16:RIO_OUT
    PULSE_LAT
    OE_ENABLE
    DWELL
    OE_BLANK
    LAT_LOW_GUARD
.endm

.macro LOAD_CONST_RGB_CLKONLY_PTRS
    movw r8, #:lower16:RIO_SET
    movt r8, #:upper16:RIO_SET
    movw r10, #:lower16:RIO_CLR
    movt r10, #:upper16:RIO_CLR
    movw r9, #:lower16:PIN_CLK
    movt r9, #:upper16:PIN_CLK
.endm

.macro CONST_RGB_CLK_PULSE
    str r9, [r8]
.ifdef CONST_RGB_CLK_HIGH_NOPS
    CONFIG_NOPS CONST_RGB_CLK_HIGH_NOPS
.else
.ifdef CONST_RGB_CLK_HIGH_NOP1
    nop
.endif
.ifdef CONST_RGB_CLK_HIGH_NOP2
    .rept 2
    nop
    .endr
.endif
.endif
    str r9, [r10]
.ifdef CONST_RGB_CLK_LOW_NOPS
    CONFIG_NOPS CONST_RGB_CLK_LOW_NOPS
.else
.ifdef CONST_RGB_CLK_LOW_NOP1
    nop
.endif
.ifdef CONST_RGB_CLK_LOW_NOP2
    .rept 2
    nop
    .endr
.endif
.endif
.endm

.macro SHIFT_ROW_CONST_RGB_CLKONLY
    .rept 64
    CONST_RGB_CLK_PULSE
    .endr
.endm

.macro ROW_CONST_RGB_CLKONLY
    SHIFT_ROW_CONST_RGB_CLKONLY
    movw r8, #:lower16:RIO_OUT
    movt r8, #:upper16:RIO_OUT
    PULSE_LAT
    OE_ENABLE
    DWELL
    OE_BLANK
    LAT_LOW_GUARD
.endm

.macro PIX8
    PIX r0
    PIX r1
    PIX r2
    PIX r3
    PIX r4
    PIX r5
    PIX r6
    PIX r11
.endm

.macro PIX4
    PIX r0
    PIX r1
    PIX r2
    PIX r3
.endm

.macro PIX3
    PIX r0
    PIX r1
    PIX r2
.endm

.macro BATCH8
    ldmia r12!, {r0-r6,r11}
    PIX8
    CLK_LOW
.endm

.macro PIX7
    PIX r0
    PIX r1
    PIX r2
    PIX r3
    PIX r4
    PIX r5
    PIX r6
.endm

.macro BATCH8_LOW_PREFETCH
    PIX7
    str r11, [r8]
    ldmia r12!, {r0-r6,r11}
    str r9, [lr]
.endm

.macro SHIFT_ROW_STATE32_LOW_PREFETCH
    ldmia r12!, {r0-r6,r11}
    .rept 7
    BATCH8_LOW_PREFETCH
    .endr
    PIX8
    CLK_LOW
.endm

.macro BATCH4_LOW_PREFETCH
    PIX3
.ifdef USE_SHIFT_CONSTANT_OE_R5
    str r5, [r8]
.else
.ifdef USE_CLK_IN_OUT_R5
.ifdef USE_CLK_OUT_NOP_EVERY4
    orr r5, r3, #PIN_CLK
    str r5, [r8]
    nop
    str r3, [r8]
.else
    PIX r3
.endif
.else
    str r3, [r8]
.endif
.endif
    ldmia r12!, {r0-r3}
.ifdef USE_SHIFT_LAT_CLR_R11
    str r11, [r10]
.endif
.ifndef USE_CLK_IN_OUT_R5
    str r9, [lr]
.endif
.endm

.macro SHIFT_ROW_STATE32_LOW_PREFETCH4
    ldmia r12!, {r0-r3}
.ifdef USE_ROW_ADDR_SETUP_BEFORE_FIRST_CLK
.ifdef USE_ROW_ADDR_PRIME_BEFORE_FIRST_CLK
    movw r5, #:lower16:ADDR_OE_PINS
    movt r5, #:upper16:ADDR_OE_PINS
    ands r5, r0
    str r5, [r8]
.else
    str r0, [r8]
.endif
    ROW_ADDR_SETUP_DELAY
.ifdef USE_ROW_ADDR_PRIME_BEFORE_FIRST_CLK
    str r0, [r8]
    ROW_ADDR_PRIME_DATA_SETUP_DELAY
.endif
.endif
    .rept 15
    BATCH4_LOW_PREFETCH
    .endr
    PIX r0
    PIX r1
    PIX r2
.ifdef USE_CLK_OUT_NOP_EVERY4
    orr r5, r3, #PIN_CLK
    str r5, [r8]
    nop
    str r3, [r8]
.else
    PIX r3
.endif
    CLK_LOW
    mov r11, r3
.endm

.macro PIX10
    PIX r0
    PIX r1
    PIX r2
    PIX r3
    PIX r4
    PIX r5
    PIX r6
    PIX r7
    PIX r10
    PIX r11
.endm

.macro PIX9
    PIX r0
    PIX r1
    PIX r2
    PIX r3
    PIX r4
    PIX r5
    PIX r6
    PIX r7
    PIX r10
.endm

.macro BATCH10
    ldmia r12!, {r0-r7,r10-r11}
    PIX10
    CLK_LOW
.endm

.macro BATCH10_LOW_PREFETCH
    PIX9
    str r11, [r8]
    ldmia r12!, {r0-r7,r10-r11}
    str r9, [lr]
.endm

.macro SHIFT_ROW_STATE32_LOW_PREFETCH10
    ldmia r12!, {r0-r7,r10-r11}
    .rept 5
    BATCH10_LOW_PREFETCH
    .endr
    PIX9
    str r11, [r8]
    ldmia r12!, {r0-r3}
    str r9, [lr]
    PIX r0
    PIX r1
    PIX r2
    PIX r3
    CLK_LOW
    mov r11, r3
.endm

.macro BATCH4
    ldmia r12!, {r0-r3}
    PIX r0
    PIX r1
    PIX r2
    PIX r3
    CLK_LOW
    mov r11, r3
.endm

.macro PIX_LOAD
    ldr r0, [r12], #4
    mov r11, r0
    PIX r0
.endm

.macro STREAM1_ROW
    .rept 64
    PIX_LOAD
    .endr
    CLK_LOW
.endm

.macro SHIFT_ROW_STATE32
.ifdef USE_STREAM1
    STREAM1_ROW
.else
.ifdef USE_LOW_PREFETCH4
    SHIFT_ROW_STATE32_LOW_PREFETCH4
.else
.ifdef USE_LOW_PREFETCH10
    SHIFT_ROW_STATE32_LOW_PREFETCH10
.else
.ifdef USE_LOW_PREFETCH
    SHIFT_ROW_STATE32_LOW_PREFETCH
.else
.ifdef USE_BATCH10
    .rept 6
    BATCH10
    .endr
    BATCH4
.else
    .rept 8
    BATCH8
    .endr
.endif
.endif
.endif
.endif
.endif
.endm

.macro PULSE_LAT
.ifdef USE_LAT_SETCLR
    movw r0, #:lower16:RIO_SET
    movt r0, #:upper16:RIO_SET
    movw r1, #:lower16:PIN_LAT
    movt r1, #:upper16:PIN_LAT
    OE_BLANK_LEAD_DELAY
    str r1, [r0]
    LAT_PULSE_DELAY
    movw r0, #:lower16:RIO_CLR
    movt r0, #:upper16:RIO_CLR
    str r1, [r0]
.else
    OE_BLANK_LEAD_DELAY
    orr r1, r11, #PIN_LAT
    str r1, [r8]
    LAT_PULSE_DELAY
.ifdef USE_FORCE_LAT_CLEAR
    bic r1, r11, #PIN_LAT
    str r1, [r8]
    mov r11, r1
.else
    str r11, [r8]
.endif
.endif
.endm

.macro LAT_LOW_GUARD
.ifdef USE_LAT_LOW_GUARD
    movw r0, #:lower16:RIO_CLR
    movt r0, #:upper16:RIO_CLR
    movw r1, #:lower16:PIN_LAT
    movt r1, #:upper16:PIN_LAT
    str r1, [r0]
.endif
.endm

.macro ORR_OE_BITS reg
    orr \reg, \reg, #PIN_OE
    orr \reg, \reg, #PIN_OE_LEGACY
.endm

.macro BIC_OE_BITS reg
    bic \reg, \reg, #PIN_OE
    bic \reg, \reg, #PIN_OE_LEGACY
.endm

.macro OE_ENABLE
.ifdef USE_OE_SETCLR
    movw r0, #:lower16:RIO_CLR
    movt r0, #:upper16:RIO_CLR
    movw r1, #:lower16:PIN_OE_ALL
    movt r1, #:upper16:PIN_OE_ALL
    str r1, [r0]
.else
    mov r1, r11
    BIC_OE_BITS r1
    str r1, [r8]
.endif
    OE_ENABLE_DELAY
.endm

.macro OE_BLANK
.ifdef USE_OE_SETCLR
    movw r0, #:lower16:RIO_SET
    movt r0, #:upper16:RIO_SET
    movw r1, #:lower16:PIN_OE_ALL
    movt r1, #:upper16:PIN_OE_ALL
    str r1, [r0]
.else
    str r11, [r8]
.endif
    OE_BLANK_HOLD_DELAY
.endm

.macro DIRECT_CTRL_LATCH_ENABLE
.ifdef USE_DIRECT_CTRL_TAIL_SELFLOAD
    movw r0, #:lower16:RIO_SET
    movt r0, #:upper16:RIO_SET
    movw r1, #:lower16:RIO_CLR
    movt r1, #:upper16:RIO_CLR
    movw r2, #:lower16:PIN_OE_ALL
    movt r2, #:upper16:PIN_OE_ALL
    str r2, [r0]
.ifdef USE_CTRL_RGB_BLANK
    movw r2, #:lower16:RGB_PINS
    movt r2, #:upper16:RGB_PINS
    str r2, [r1]
.endif
    movw r2, #:lower16:PIN_LAT
    movt r2, #:upper16:PIN_LAT
    str r2, [r1]
    OE_BLANK_LEAD_DELAY
    str r2, [r0]
    LAT_PULSE_DELAY
    str r2, [r1]
    movw r2, #:lower16:PIN_OE_ALL
    movt r2, #:upper16:PIN_OE_ALL
    str r2, [r1]
    OE_ENABLE_DELAY
.else
.ifdef USE_OUT_LAT_DIRECT_OE_TAIL
    movw r1, #:lower16:PIN_OE_ALL
    movt r1, #:upper16:PIN_OE_ALL
    str r1, [lr]
    bic r11, r11, #PIN_LAT
    ORR_OE_BITS r11
    str r11, [r8]
    OE_BLANK_LEAD_DELAY
    orr r1, r11, #PIN_LAT
    str r1, [r8]
    LAT_PULSE_DELAY
    str r11, [r8]
.ifdef USE_LAT_CLEAR_DSB
    dsb sy
.endif
    movw r1, #:lower16:PIN_OE_ALL
    movt r1, #:upper16:PIN_OE_ALL
    str r1, [r10]
    OE_ENABLE_DELAY
.else
.ifdef USE_DIRECT_CTRL_TAIL
    movw r1, #:lower16:PIN_OE_ALL
    movt r1, #:upper16:PIN_OE_ALL
    str r1, [lr]
    movw r1, #:lower16:PIN_LAT
    movt r1, #:upper16:PIN_LAT
    str r1, [r10]
    OE_BLANK_LEAD_DELAY
    str r1, [lr]
    LAT_PULSE_DELAY
    str r1, [r10]
    movw r1, #:lower16:PIN_OE_ALL
    movt r1, #:upper16:PIN_OE_ALL
    str r1, [r10]
    OE_ENABLE_DELAY
    movw r1, #:lower16:PIN_LAT
    movt r1, #:upper16:PIN_LAT
    str r1, [r10]
.else
    PULSE_LAT
    mov r1, r11
    BIC_OE_BITS r1
    str r1, [r8]
.endif
.endif
.endif
.endm

.macro DIRECT_CTRL_BLANK
.ifdef USE_DIRECT_CTRL_TAIL_SELFLOAD
    movw r0, #:lower16:RIO_CLR
    movt r0, #:upper16:RIO_CLR
    movw r1, #:lower16:PIN_LAT
    movt r1, #:upper16:PIN_LAT
    str r1, [r0]
    movw r0, #:lower16:RIO_SET
    movt r0, #:upper16:RIO_SET
    movw r1, #:lower16:PIN_OE_ALL
    movt r1, #:upper16:PIN_OE_ALL
    str r1, [r0]
.else
.ifdef USE_OUT_LAT_DIRECT_OE_TAIL
    bic r11, r11, #PIN_LAT
    ORR_OE_BITS r11
    str r11, [r8]
.ifdef USE_LAT_CLEAR_DSB
    dsb sy
.endif
    movw r1, #:lower16:PIN_OE_ALL
    movt r1, #:upper16:PIN_OE_ALL
    str r1, [lr]
.else
.ifdef USE_DIRECT_CTRL_TAIL
    movw r1, #:lower16:PIN_LAT
    movt r1, #:upper16:PIN_LAT
    str r1, [r10]
    movw r1, #:lower16:PIN_OE_ALL
    movt r1, #:upper16:PIN_OE_ALL
    str r1, [lr]
.else
    str r11, [r8]
    LAT_LOW_GUARD
.endif
.endif
.endif
    OE_BLANK_HOLD_DELAY
.endm

.macro ROW
    SHIFT_ROW_STATE32
    ROW_END_HOLD_DELAY
    PULSE_LAT
    OE_ENABLE
    DWELL
    OE_BLANK
    LAT_LOW_GUARD
.endm

.macro ROWS16
    .rept 16
    ROW
    .endr
.endm

.macro ROW_REGCOUNT_RGB_SETCLR_LOOP
    movw r0, #:lower16:ROW_CACHE_PLANE_COUNT
    movt r0, #:upper16:ROW_CACHE_PLANE_COUNT
    str r7, [r0]
    movw r3, #:lower16:local_row_addr_masks
    movt r3, #:upper16:local_row_addr_masks
    movs r6, #0
1:
    ldr.w r11, [r3, r6, lsl #2]
    ORR_OE_BITS r11
.ifdef USE_CONST_RGB_CLKONLY
    orr r11, r11, #CONST_RGB_BITS
.endif
    movw r8, #:lower16:RIO_OUT
    movt r8, #:upper16:RIO_OUT
    str r11, [r8]
    ROW_ADDR_STAGE_DELAY
.ifdef USE_CONST_RGB_CLKONLY
    LOAD_CONST_RGB_CLKONLY_PTRS
    ROW_CONST_RGB_CLKONLY
.else
    LOAD_RGB_SETCLR_PTRS
    ROW_RGB_SETCLR
.endif
    adds r6, #1
    cmp r6, #32
    blo 1b
    movw r0, #:lower16:ROW_CACHE_PLANE_COUNT
    movt r0, #:upper16:ROW_CACHE_PLANE_COUNT
    ldr r7, [r0]
.endm

.macro ROWS8
    .rept 8
    ROW
    .endr
.endm

.macro COPY_SHARED_STATE32_TO_DSRAM
.ifdef USE_PLANE_SRC_PTR
    movw r12, #:lower16:ROW_CACHE_SRC
    movt r12, #:upper16:ROW_CACHE_SRC
    ldr r12, [r12]
.else
    movw r12, #:lower16:SHARED_STATE32_BASE
    movt r12, #:upper16:SHARED_STATE32_BASE
.endif
    movw r8, #:lower16:LOCAL_DSRAM
    movt r8, #:upper16:LOCAL_DSRAM
.ifdef USE_COPY10
    mov lr, r7
    mov.w r4, #204
1:
    ldmia r12!, {r0-r3,r5-r7,r9-r11}
    stmia r8!, {r0-r3,r5-r7,r9-r11}
    subs.w r4, r4, #1
    bne.w 1b
    ldmia r12!, {r0-r3,r5-r7,r9}
    stmia r8!, {r0-r3,r5-r7,r9}
    mov r7, lr
.else
.ifdef USE_COPY11
    movw r0, #:lower16:ROW_CACHE_PLANE_COUNT
    movt r0, #:upper16:ROW_CACHE_PLANE_COUNT
    str r7, [r0]
 .ifdef COPY11_FIRST8_EXTRA_DELAY_NOPS
    ldmia r12!, {r0-r3,r5-r7,r9}
.ifdef COPY11_STORE_DELAY_NOPS
    .rept COPY11_STORE_DELAY_NOPS
    nop
    .endr
.endif
    .rept COPY11_FIRST8_EXTRA_DELAY_NOPS
    nop
    .endr
    stmia r8!, {r0-r3,r5-r7,r9}
    mov.w r4, #185
 .else
 .ifdef COPY11_FIRST_EXTRA_DELAY_NOPS
    ldmia r12!, {r0-r3,r5-r7,r9-r11,lr}
.ifdef COPY11_STORE_DELAY_NOPS
    .rept COPY11_STORE_DELAY_NOPS
    nop
    .endr
.endif
    .rept COPY11_FIRST_EXTRA_DELAY_NOPS
    nop
    .endr
    stmia r8!, {r0-r3,r5-r7,r9-r11,lr}
.ifdef COPY11_FIRST_POST_STORE_NOPS
    .rept COPY11_FIRST_POST_STORE_NOPS
    nop
    .endr
.endif
    mov.w r4, #185
 .else
 .ifdef COPY11_SPLIT_HEAD_EXTRA_DELAY_NOPS
    mov.w r4, #COPY11_SPLIT_HEAD_EXTRA_DELAY_COUNT
.Lcopy11_head_loop\@:
    ldmia r12!, {r0-r3,r5-r7,r9-r11,lr}
.ifdef COPY11_STORE_DELAY_NOPS
    .rept COPY11_STORE_DELAY_NOPS
    nop
    .endr
.endif
    .rept COPY11_SPLIT_HEAD_EXTRA_DELAY_NOPS
    nop
    .endr
    stmia r8!, {r0-r3,r5-r7,r9-r11,lr}
    subs.w r4, r4, #1
    bne.w .Lcopy11_head_loop\@
    mov.w r4, #(186 - COPY11_SPLIT_HEAD_EXTRA_DELAY_COUNT)
.else
    mov.w r4, #186
.endif
.endif
.endif
.Lcopy11_bulk_loop\@:
    ldmia r12!, {r0-r3,r5-r7,r9-r11,lr}
.ifdef USE_COPY_FORCE_OE
    ORR_OE_BITS r0
    ORR_OE_BITS r1
    ORR_OE_BITS r2
    ORR_OE_BITS r3
    ORR_OE_BITS r5
    ORR_OE_BITS r6
    ORR_OE_BITS r7
    ORR_OE_BITS r9
    ORR_OE_BITS r10
    ORR_OE_BITS r11
    ORR_OE_BITS lr
.endif
.ifdef USE_COPY_RGB_ONLY
    BIC_OE_BITS r0
    BIC_OE_BITS r1
    BIC_OE_BITS r2
    BIC_OE_BITS r3
    BIC_OE_BITS r5
    BIC_OE_BITS r6
    BIC_OE_BITS r7
    BIC_OE_BITS r9
    BIC_OE_BITS r10
    BIC_OE_BITS r11
    BIC_OE_BITS lr
    bic r0, r0, #PIN_A
    bic r1, r1, #PIN_A
    bic r2, r2, #PIN_A
    bic r3, r3, #PIN_A
    bic r5, r5, #PIN_A
    bic r6, r6, #PIN_A
    bic r7, r7, #PIN_A
    bic r9, r9, #PIN_A
    bic r10, r10, #PIN_A
    bic r11, r11, #PIN_A
    bic lr, lr, #PIN_A
    bic r0, r0, #PIN_B
    bic r1, r1, #PIN_B
    bic r2, r2, #PIN_B
    bic r3, r3, #PIN_B
    bic r5, r5, #PIN_B
    bic r6, r6, #PIN_B
    bic r7, r7, #PIN_B
    bic r9, r9, #PIN_B
    bic r10, r10, #PIN_B
    bic r11, r11, #PIN_B
    bic lr, lr, #PIN_B
    bic r0, r0, #PIN_C
    bic r1, r1, #PIN_C
    bic r2, r2, #PIN_C
    bic r3, r3, #PIN_C
    bic r5, r5, #PIN_C
    bic r6, r6, #PIN_C
    bic r7, r7, #PIN_C
    bic r9, r9, #PIN_C
    bic r10, r10, #PIN_C
    bic r11, r11, #PIN_C
    bic lr, lr, #PIN_C
    bic r0, r0, #PIN_D
    bic r1, r1, #PIN_D
    bic r2, r2, #PIN_D
    bic r3, r3, #PIN_D
    bic r5, r5, #PIN_D
    bic r6, r6, #PIN_D
    bic r7, r7, #PIN_D
    bic r9, r9, #PIN_D
    bic r10, r10, #PIN_D
    bic r11, r11, #PIN_D
    bic lr, lr, #PIN_D
    bic r0, r0, #PIN_E
    bic r1, r1, #PIN_E
    bic r2, r2, #PIN_E
    bic r3, r3, #PIN_E
    bic r5, r5, #PIN_E
    bic r6, r6, #PIN_E
    bic r7, r7, #PIN_E
    bic r9, r9, #PIN_E
    bic r10, r10, #PIN_E
    bic r11, r11, #PIN_E
    bic lr, lr, #PIN_E
.endif
.ifdef COPY11_STORE_DELAY_NOPS
    .rept COPY11_STORE_DELAY_NOPS
    nop
    .endr
.endif
.ifdef COPY11_HEAD_EXTRA_DELAY_NOPS
    cmp r4, #(186 - COPY11_HEAD_EXTRA_DELAY_COUNT)
    bls .Lcopy11_head_delay_done\@
    .rept COPY11_HEAD_EXTRA_DELAY_NOPS
    nop
    .endr
.Lcopy11_head_delay_done\@:
.endif
.ifdef USE_COPY11_PREDEC_STORE
    subs.w r4, r4, #1
.endif
    stmia r8!, {r0-r3,r5-r7,r9-r11,lr}
.ifndef USE_COPY11_PREDEC_STORE
    subs.w r4, r4, #1
.endif
    bne.w .Lcopy11_bulk_loop\@
.ifdef COPY11_FIRST8_EXTRA_DELAY_NOPS
    ldmia r12!, {r0-r3,r5}
.else
    ldmia r12!, {r0-r1}
.endif
.ifdef USE_COPY_FORCE_OE
    ORR_OE_BITS r0
    ORR_OE_BITS r1
.endif
.ifdef USE_COPY_RGB_ONLY
    BIC_OE_BITS r0
    BIC_OE_BITS r1
    bic r0, r0, #PIN_A
    bic r1, r1, #PIN_A
    bic r0, r0, #PIN_B
    bic r1, r1, #PIN_B
    bic r0, r0, #PIN_C
    bic r1, r1, #PIN_C
    bic r0, r0, #PIN_D
    bic r1, r1, #PIN_D
    bic r0, r0, #PIN_E
    bic r1, r1, #PIN_E
.endif
.ifdef COPY11_STORE_DELAY_NOPS
    .rept COPY11_STORE_DELAY_NOPS
    nop
    .endr
.endif
.ifdef COPY11_FIRST8_EXTRA_DELAY_NOPS
    stmia r8!, {r0-r3,r5}
.else
    stmia r8!, {r0-r1}
.endif
    movw r0, #:lower16:ROW_CACHE_PLANE_COUNT
    movt r0, #:upper16:ROW_CACHE_PLANE_COUNT
    ldr r7, [r0]
.else
    mov.w r10, #256
1:
    ldmia r12!, {r0-r6,r11}
.ifdef USE_COPY_CLEAR_LAT
    bic r0, r0, #PIN_LAT
    bic r1, r1, #PIN_LAT
    bic r2, r2, #PIN_LAT
    bic r3, r3, #PIN_LAT
    bic r4, r4, #PIN_LAT
    bic r5, r5, #PIN_LAT
    bic r6, r6, #PIN_LAT
    bic r11, r11, #PIN_LAT
.endif
    stmia r8!, {r0-r6,r11}
    subs.w r10, r10, #1
    bne.w 1b
.endif
.endif
.ifdef USE_PLANE_SRC_PTR
    movw r0, #:lower16:ROW_CACHE_SRC
    movt r0, #:upper16:ROW_CACHE_SRC
    str r12, [r0]
.endif
.endm

.macro COPY_SHARED_STATE32_ROW_TO_DSRAM
    movw r12, #:lower16:ROW_CACHE_SRC
    movt r12, #:upper16:ROW_CACHE_SRC
    ldr r12, [r12]
    movw r8, #:lower16:LOCAL_DSRAM
    movt r8, #:upper16:LOCAL_DSRAM
    movs r10, #8
1:
    ldmia r12!, {r0-r6,r11}
    stmia r8!, {r0-r6,r11}
    subs r10, #1
    bne 1b
    movw r8, #:lower16:ROW_CACHE_SRC
    movt r8, #:upper16:ROW_CACHE_SRC
    str r12, [r8]
.endm

.macro COPY_SHARED_STATE32_ROW4_TO_DSRAM
    movw r12, #:lower16:ROW_CACHE_SRC
    movt r12, #:upper16:ROW_CACHE_SRC
    ldr r12, [r12]
    movw r8, #:lower16:LOCAL_DSRAM
    movt r8, #:upper16:LOCAL_DSRAM
    movs r10, #16
1:
    ldmia r12!, {r0-r3}
    stmia r8!, {r0-r3}
    subs r10, #1
    bne 1b
    movw r8, #:lower16:ROW_CACHE_SRC
    movt r8, #:upper16:ROW_CACHE_SRC
    str r12, [r8]
.endm

.macro COPY_SHARED_STATE32_ROW8_SAFE_TO_DSRAM
    movw r12, #:lower16:ROW_CACHE_SRC
    movt r12, #:upper16:ROW_CACHE_SRC
    ldr r12, [r12]
    movw r8, #:lower16:LOCAL_DSRAM
    movt r8, #:upper16:LOCAL_DSRAM
    .rept 8
    ldmia r12!, {r0-r6,r10}
.ifdef USE_COPY_CLEAR_LAT_FIRST4
    bic r0, r0, #PIN_LAT
    bic r1, r1, #PIN_LAT
    bic r2, r2, #PIN_LAT
    bic r3, r3, #PIN_LAT
.else
.ifdef USE_COPY_CLEAR_LAT_LAST4
    bic r4, r4, #PIN_LAT
    bic r5, r5, #PIN_LAT
    bic r6, r6, #PIN_LAT
    bic r10, r10, #PIN_LAT
.else
.ifdef USE_COPY_CLEAR_LAT
    bic r0, r0, #PIN_LAT
    bic r1, r1, #PIN_LAT
    bic r2, r2, #PIN_LAT
    bic r3, r3, #PIN_LAT
    bic r4, r4, #PIN_LAT
    bic r5, r5, #PIN_LAT
    bic r6, r6, #PIN_LAT
    bic r10, r10, #PIN_LAT
.endif
.endif
.endif
.ifdef USE_COPY_FORCE_OE
    ORR_OE_BITS r0
    ORR_OE_BITS r1
    ORR_OE_BITS r2
    ORR_OE_BITS r3
    ORR_OE_BITS r4
    ORR_OE_BITS r5
    ORR_OE_BITS r6
    ORR_OE_BITS r10
.endif
.ifdef USE_COPY_DELAY8
    .rept 8
    nop
    .endr
.endif
.ifdef USE_COPY_STR8
    str r0, [r8], #4
    str r1, [r8], #4
    str r2, [r8], #4
    str r3, [r8], #4
    str r4, [r8], #4
    str r5, [r8], #4
    str r6, [r8], #4
    str r10, [r8], #4
.else
    stmia r8!, {r0-r6,r10}
.endif
    .endr
    movw r8, #:lower16:ROW_CACHE_SRC
    movt r8, #:upper16:ROW_CACHE_SRC
    str r12, [r8]
.endm

.macro ROW_REFILL_LOOP
    movw r0, #:lower16:SHARED_STATE32_BASE
    movt r0, #:upper16:SHARED_STATE32_BASE
    movw r1, #:lower16:ROW_CACHE_SRC
    movt r1, #:upper16:ROW_CACHE_SRC
    str r0, [r1]
    movs r0, #32
    movw r1, #:lower16:ROW_CACHE_COUNT
    movt r1, #:upper16:ROW_CACHE_COUNT
    str r0, [r1]
1:
    COPY_SHARED_STATE32_ROW_TO_DSRAM
    movw r8, #:lower16:RIO_OUT
    movt r8, #:upper16:RIO_OUT
    LOAD_CLK_PTRS
    movw r12, #:lower16:LOCAL_DSRAM
    movt r12, #:upper16:LOCAL_DSRAM
    ROW
    movw r1, #:lower16:ROW_CACHE_COUNT
    movt r1, #:upper16:ROW_CACHE_COUNT
    ldr r0, [r1]
    subs r0, #1
    str r0, [r1]
    bne 1b
.endm

.macro ROW_TAIL_REFILL_LOOP
    movw r0, #:lower16:SHARED_STATE32_BASE
    movt r0, #:upper16:SHARED_STATE32_BASE
    movw r1, #:lower16:ROW_CACHE_SRC
    movt r1, #:upper16:ROW_CACHE_SRC
    str r0, [r1]
    COPY_SHARED_STATE32_ROW8_SAFE_TO_DSRAM
    movw r0, #:lower16:ROW_CACHE_PLANE_COUNT
    movt r0, #:upper16:ROW_CACHE_PLANE_COUNT
    str r7, [r0]
    movs r0, #32
    movw r1, #:lower16:ROW_CACHE_COUNT
    movt r1, #:upper16:ROW_CACHE_COUNT
    str r0, [r1]
1:
    movw r8, #:lower16:RIO_OUT
    movt r8, #:upper16:RIO_OUT
    LOAD_CLK_PTRS
    movw r12, #:lower16:LOCAL_DSRAM
    movt r12, #:upper16:LOCAL_DSRAM
    SHIFT_ROW_STATE32
    ROW_END_HOLD_DELAY
    PULSE_LAT
    mov r1, r11
    BIC_OE_BITS r1
    str r1, [r8]

    movw r1, #:lower16:ROW_CACHE_COUNT
    movt r1, #:upper16:ROW_CACHE_COUNT
    ldr r0, [r1]
    subs r0, #1
    str r0, [r1]
    beq 2f
    COPY_SHARED_STATE32_ROW8_SAFE_TO_DSRAM
    movw r8, #:lower16:RIO_OUT
    movt r8, #:upper16:RIO_OUT
    LOAD_CLK_PTRS
2:
    DWELL
    str r11, [r8]
    LAT_LOW_GUARD
    movw r1, #:lower16:ROW_CACHE_COUNT
    movt r1, #:upper16:ROW_CACHE_COUNT
    ldr r0, [r1]
    cmp r0, #0
    bne 1b
    movw r0, #:lower16:ROW_CACHE_PLANE_COUNT
    movt r0, #:upper16:ROW_CACHE_PLANE_COUNT
    ldr r7, [r0]
.endm

.macro ROW_TAIL_REFILL_REGCOUNT_LOOP
    movw r0, #:lower16:SHARED_STATE32_BASE
    movt r0, #:upper16:SHARED_STATE32_BASE
    movw r1, #:lower16:ROW_CACHE_SRC
    movt r1, #:upper16:ROW_CACHE_SRC
    str r0, [r1]
    COPY_SHARED_STATE32_ROW8_SAFE_TO_DSRAM
    movw r0, #:lower16:ROW_CACHE_PLANE_COUNT
    movt r0, #:upper16:ROW_CACHE_PLANE_COUNT
    str r7, [r0]
    movs r7, #31
1:
    movw r8, #:lower16:RIO_OUT
    movt r8, #:upper16:RIO_OUT
    LOAD_CLK_PTRS
    movw r12, #:lower16:LOCAL_DSRAM
    movt r12, #:upper16:LOCAL_DSRAM
    SHIFT_ROW_STATE32
    ROW_END_HOLD_DELAY
    DIRECT_CTRL_LATCH_ENABLE
    COPY_SHARED_STATE32_ROW8_SAFE_TO_DSRAM
    movw r8, #:lower16:RIO_OUT
    movt r8, #:upper16:RIO_OUT
    LOAD_CLK_PTRS
    DWELL
    DIRECT_CTRL_BLANK
    subs r7, #1
    bne 1b

    movw r8, #:lower16:RIO_OUT
    movt r8, #:upper16:RIO_OUT
    LOAD_CLK_PTRS
    movw r12, #:lower16:LOCAL_DSRAM
    movt r12, #:upper16:LOCAL_DSRAM
    SHIFT_ROW_STATE32
    ROW_END_HOLD_DELAY
    DIRECT_CTRL_LATCH_ENABLE
    DWELL
    DIRECT_CTRL_BLANK
    movw r0, #:lower16:ROW_CACHE_PLANE_COUNT
    movt r0, #:upper16:ROW_CACHE_PLANE_COUNT
    ldr r7, [r0]
.endm

.macro EXPAND_RGB6_BYTE
    uxtb r1, r0
    ldr.w r2, [r5, r1, lsl #2]
.ifndef USE_RGB_ONLY_CACHE
    orr r2, r2, r11
.endif
    str r2, [r8], #4
    lsrs r0, r0, #8
.endm

.macro EXPAND_RGB6_WORD
    ldr r0, [r12], #4
    EXPAND_RGB6_BYTE
    EXPAND_RGB6_BYTE
    EXPAND_RGB6_BYTE
    EXPAND_RGB6_BYTE
.endm

.macro EXPAND_SHARED_RGB6_TO_DSRAM
    movw r12, #:lower16:SHARED_RGB6_BASE
    movt r12, #:upper16:SHARED_RGB6_BASE
    movw r8, #:lower16:LOCAL_DSRAM
    movt r8, #:upper16:LOCAL_DSRAM
    movw r3, #:lower16:local_row_addr_masks
    movt r3, #:upper16:local_row_addr_masks
    movw r5, #:lower16:local_rgb6_mask_table
    movt r5, #:upper16:local_rgb6_mask_table
    movs r4, #0
1:
    ldr.w r11, [r3, r4, lsl #2]
    ORR_OE_BITS r11
    .rept 16
    EXPAND_RGB6_WORD
    .endr
    adds r4, #1
    cmp r4, #32
    blo 1b
.endm

.macro RGB333_COMPONENT pin, shift
    mov r1, r6
    lsls r1, r1, #\shift
    tst r0, r1
    it ne
    orrne r2, r2, #\pin
.endm

.macro EXPAND_RGB333_WORD
    ldr r0, [r12], #4
.ifdef USE_RGB_ONLY_CACHE
    movs r2, #0
.else
    mov r2, r11
.endif
    RGB333_COMPONENT PIN_R1, 0
    RGB333_COMPONENT PIN_G1, 3
    RGB333_COMPONENT PIN_B1, 6
    RGB333_COMPONENT PIN_R2, 16
    RGB333_COMPONENT PIN_G2, 19
    RGB333_COMPONENT PIN_B2, 22
    str r2, [r8], #4
.endm

.macro EXPAND_SHARED_RGB333_TO_DSRAM
    /*
     * PLANE_COUNT=7 uses a repeated bit schedule for true 3-bit PWM:
     * bit0 once, bit1 twice, bit2 four times.
     */
    movs r6, #4
    cmp r7, #5
    blo 2f
    movs r6, #2
    cmp r7, #7
    blo 2f
    movs r6, #1
2:
    movw r12, #:lower16:SHARED_RGB333_BASE
    movt r12, #:upper16:SHARED_RGB333_BASE
    movw r8, #:lower16:LOCAL_DSRAM
    movt r8, #:upper16:LOCAL_DSRAM
    movw r3, #:lower16:local_row_addr_masks
    movt r3, #:upper16:local_row_addr_masks
    movs r4, #0
1:
    ldr.w r11, [r3, r4, lsl #2]
    ORR_OE_BITS r11
    .rept 64
    EXPAND_RGB333_WORD
    .endr
    adds r4, #1
    cmp r4, #32
    blo 1b
.endm

.macro RGB444_COMPONENT pin, shift
    mov r1, r6
    lsls r1, r1, #\shift
    tst r0, r1
    it ne
    orrne r2, r2, #\pin
.endm

.macro EXPAND_RGB444_WORD
    ldr r0, [r12], #4
.ifdef USE_RGB_ONLY_CACHE
    movs r2, #0
.else
    mov r2, r11
.endif
    RGB444_COMPONENT PIN_R1, 0
    RGB444_COMPONENT PIN_G1, 4
    RGB444_COMPONENT PIN_B1, 8
    RGB444_COMPONENT PIN_R2, 16
    RGB444_COMPONENT PIN_G2, 20
    RGB444_COMPONENT PIN_B2, 24
    str r2, [r8], #4
.endm

.macro EXPAND_SHARED_RGB444_TO_DSRAM
    /*
     * PLANE_COUNT=15 uses a repeated bit schedule for true 4-bit PWM:
     * bit0 once, bit1 twice, bit2 four times, bit3 eight times.
     */
    movs r6, #8
    cmp r7, #9
    blo 2f
    movs r6, #4
    cmp r7, #13
    blo 2f
    movs r6, #2
    cmp r7, #15
    blo 2f
    movs r6, #1
2:
    movw r12, #:lower16:SHARED_RGB444_BASE
    movt r12, #:upper16:SHARED_RGB444_BASE
    movw r8, #:lower16:LOCAL_DSRAM
    movt r8, #:upper16:LOCAL_DSRAM
    movw r3, #:lower16:local_row_addr_masks
    movt r3, #:upper16:local_row_addr_masks
    movs r4, #0
1:
    ldr.w r11, [r3, r4, lsl #2]
    ORR_OE_BITS r11
    .rept 64
    EXPAND_RGB444_WORD
    .endr
    adds r4, #1
    cmp r4, #32
    blo 1b
.endm

.macro RGB888_COMPONENT pin, shift
    mov r1, r6
    lsls r1, r1, #\shift
    tst r0, r1
    it ne
    orrne r2, r2, #\pin
.endm

.macro RGB888_SHARED_READ_DELAY
.ifdef RGB888_SHARED_READ_NOPS
    CONFIG_NOPS RGB888_SHARED_READ_NOPS
.endif
.endm

.macro RGB888_SOURCE_WARMUP
.ifdef RGB888_SOURCE_WARMUP_WORDS
    movw r0, #:lower16:SHARED_RGB888_BASE
    movt r0, #:upper16:SHARED_RGB888_BASE
    .rept RGB888_SOURCE_WARMUP_WORDS
    ldr r2, [r0], #4
    .endr
.endif
.endm

.macro RGB111_COMPONENT_DIRECT reg, pin, shift
    mov r1, r6
    lsls r1, r1, #\shift
    tst \reg, r1
    it ne
    orrne r2, r2, #\pin
.endm

.macro RGB111_COMPONENT_UPPER_B pin
    cmp r6, #1024
    beq 1f
    mov r1, r6
    lsls r1, r1, #22
    tst r0, r1
    b 2f
1:
    tst r9, #1
2:
    it ne
    orrne r2, r2, #\pin
.endm

.macro RGB111_COMPONENT_LOWER_B pin
    cmp r6, #512
    beq 1f
    cmp r6, #1024
    beq 2f
    mov r1, r6
    lsls r1, r1, #23
    tst r9, r1
    b 3f
1:
    tst r10, #1
    b 3f
2:
    tst r10, #2
3:
    it ne
    orrne r2, r2, #\pin
.endm

.macro EXPAND_RGB111_WORDS
    ldr r0, [r12], #4
    RGB888_SHARED_READ_DELAY
    ldr r9, [r12], #4
    RGB888_SHARED_READ_DELAY
    ldr r10, [r12], #4
    RGB888_SHARED_READ_DELAY
.ifdef USE_RGB_ONLY_CACHE
    movs r2, #0
.else
    mov r2, r11
.endif
    RGB111_COMPONENT_DIRECT r0, PIN_R1, 0
    RGB111_COMPONENT_DIRECT r0, PIN_G1, 11
    RGB111_COMPONENT_UPPER_B PIN_B1
    RGB111_COMPONENT_DIRECT r9, PIN_R2, 1
    RGB111_COMPONENT_DIRECT r9, PIN_G2, 12
    RGB111_COMPONENT_LOWER_B PIN_B2
    str r2, [r8], #4
.endm

.macro EXPAND_SHARED_RGB111_TO_DSRAM
    SELECT_RGB111_MASK
    RGB888_SOURCE_WARMUP
    movw r12, #:lower16:SHARED_RGB111_BASE
    movt r12, #:upper16:SHARED_RGB111_BASE
    movw r8, #:lower16:LOCAL_DSRAM
    movt r8, #:upper16:LOCAL_DSRAM
    movw r3, #:lower16:local_row_addr_masks
    movt r3, #:upper16:local_row_addr_masks
    movs r4, #0
1:
    ldr.w r11, [r3, r4, lsl #2]
    ORR_OE_BITS r11
    .rept 64
    EXPAND_RGB111_WORDS
    .endr
    adds r4, #1
    cmp r4, #32
    blo 1b
.endm

.macro SELECT_RGB111_MASK
    movs r6, #1
    cmp r7, #11
    beq .Lrgb111_mask_done\@
    movs r6, #2
    cmp r7, #10
    beq .Lrgb111_mask_done\@
    movs r6, #4
    cmp r7, #9
    beq .Lrgb111_mask_done\@
    movs r6, #8
    cmp r7, #8
    beq .Lrgb111_mask_done\@
    movs r6, #16
    cmp r7, #7
    beq .Lrgb111_mask_done\@
    movs r6, #32
    cmp r7, #6
    beq .Lrgb111_mask_done\@
    movs r6, #64
    cmp r7, #5
    beq .Lrgb111_mask_done\@
    movs r6, #128
    cmp r7, #4
    beq .Lrgb111_mask_done\@
    movs r6, #1
    lsls r6, r6, #8
    cmp r7, #3
    beq .Lrgb111_mask_done\@
    movs r6, #1
    lsls r6, r6, #9
    cmp r7, #2
    beq .Lrgb111_mask_done\@
    movs r6, #1
    lsls r6, r6, #10
.Lrgb111_mask_done\@:
.endm

.macro EXPAND_SHARED_RGB111_ROW_TO_DSRAM
    SELECT_RGB111_MASK
    RGB888_SOURCE_WARMUP
    movw r12, #:lower16:SHARED_RGB111_BASE
    movt r12, #:upper16:SHARED_RGB111_BASE
    add.w r12, r12, r4, lsl #9
    add.w r12, r12, r4, lsl #8
    movw r8, #:lower16:LOCAL_DSRAM
    movt r8, #:upper16:LOCAL_DSRAM
    movw r3, #:lower16:local_row_addr_masks
    movt r3, #:upper16:local_row_addr_masks
    ldr.w r11, [r3, r4, lsl #2]
    ORR_OE_BITS r11
    movs r5, #64
.Lrgb111_expand_row_loop\@:
    EXPAND_RGB111_WORDS
    subs r5, #1
    bne .Lrgb111_expand_row_loop\@
.endm

.macro EXPAND_RGB888_WORD
    ldr r0, [r12], #4
    RGB888_SHARED_READ_DELAY
.ifdef USE_RGB888_CONST_EXPAND
    ldr r0, [r12], #4
    RGB888_SHARED_READ_DELAY
    .ifndef RGB888_CONST_BITS
    .equ RGB888_CONST_BITS, (PIN_R1 | PIN_R2)
    .endif
    movw r2, #:lower16:RGB888_CONST_BITS
    movt r2, #:upper16:RGB888_CONST_BITS
.else
.ifdef USE_RGB_ONLY_CACHE
    movs r2, #0
.else
    mov r2, r11
.endif
    RGB888_COMPONENT PIN_R1, 0
    RGB888_COMPONENT PIN_G1, 8
    RGB888_COMPONENT PIN_B1, 16
    ldr r0, [r12], #4
    RGB888_SHARED_READ_DELAY
    RGB888_COMPONENT PIN_R2, 0
    RGB888_COMPONENT PIN_G2, 8
    RGB888_COMPONENT PIN_B2, 16
.endif
    str r2, [r8], #4
.endm

.macro EXPAND_SHARED_RGB888_TO_DSRAM
    /*
     * PLANE_COUNT=8 emits one RGB888 bitplane per frame.  The row dwell is
     * weighted by USE_RGB888_WEIGHTED_DWELL, avoiding 255 full shift passes.
     */
    movs r6, #1
    cmp r7, #8
    beq 2f
    movs r6, #2
    cmp r7, #7
    beq 2f
    movs r6, #4
    cmp r7, #6
    beq 2f
    movs r6, #8
    cmp r7, #5
    beq 2f
    movs r6, #16
    cmp r7, #4
    beq 2f
    movs r6, #32
    cmp r7, #3
    beq 2f
    movs r6, #64
    cmp r7, #2
    beq 2f
    movs r6, #128
2:
    RGB888_SOURCE_WARMUP
.ifdef USE_RGB888_DEBUG_SOURCE_DUMP
    movw r0, #:lower16:SHARED_RGB888_BASE
    movt r0, #:upper16:SHARED_RGB888_BASE
    movw r1, #:lower16:RGB888_DEBUG_SOURCE_BASE
    movt r1, #:upper16:RGB888_DEBUG_SOURCE_BASE
    .rept 16
    ldr r2, [r0], #4
    str r2, [r1], #4
    .endr
.endif
    movw r12, #:lower16:SHARED_RGB888_BASE
    movt r12, #:upper16:SHARED_RGB888_BASE
    movw r8, #:lower16:LOCAL_DSRAM
    movt r8, #:upper16:LOCAL_DSRAM
    movw r3, #:lower16:local_row_addr_masks
    movt r3, #:upper16:local_row_addr_masks
    movs r4, #0
1:
    ldr.w r11, [r3, r4, lsl #2]
    ORR_OE_BITS r11
    .rept 64
    EXPAND_RGB888_WORD
    .endr
    adds r4, #1
    cmp r4, #32
    blo 1b
.ifdef USE_RGB888_DEBUG_DUMP
    movw r0, #:lower16:LOCAL_DSRAM
    movt r0, #:upper16:LOCAL_DSRAM
    movw r1, #:lower16:RGB888_DEBUG_BASE
    movt r1, #:upper16:RGB888_DEBUG_BASE
    str r7, [r1], #4
    str r6, [r1], #4
    .rept 16
    ldr r2, [r0], #4
    str r2, [r1], #4
    .endr
.endif
.endm

.macro SELECT_RGB888_MASK
    movs r6, #1
    cmp r7, #8
    beq .Lrgb888_mask_done\@
    movs r6, #2
    cmp r7, #7
    beq .Lrgb888_mask_done\@
    movs r6, #4
    cmp r7, #6
    beq .Lrgb888_mask_done\@
    movs r6, #8
    cmp r7, #5
    beq .Lrgb888_mask_done\@
    movs r6, #16
    cmp r7, #4
    beq .Lrgb888_mask_done\@
    movs r6, #32
    cmp r7, #3
    beq .Lrgb888_mask_done\@
    movs r6, #64
    cmp r7, #2
    beq .Lrgb888_mask_done\@
    movs r6, #128
.Lrgb888_mask_done\@:
.endm

.macro EXPAND_SHARED_RGB888_ROW_TO_DSRAM
    SELECT_RGB888_MASK
    movw r12, #:lower16:SHARED_RGB888_BASE
    movt r12, #:upper16:SHARED_RGB888_BASE
    add.w r12, r12, r4, lsl #9
    movw r8, #:lower16:LOCAL_DSRAM
    movt r8, #:upper16:LOCAL_DSRAM
    movw r3, #:lower16:local_row_addr_masks
    movt r3, #:upper16:local_row_addr_masks
    ldr.w r11, [r3, r4, lsl #2]
    ORR_OE_BITS r11
    movs r5, #64
.Lrgb888_expand_row_loop\@:
    EXPAND_RGB888_WORD
    subs r5, #1
    bne .Lrgb888_expand_row_loop\@
.endm

.macro RGB888_ROW_MAJOR_LOOP
    movs r4, #0
.Lrgb888_row_loop\@:
    movs r7, #PLANE_COUNT
.Lrgb888_plane_loop\@:
    EXPAND_SHARED_RGB888_ROW_TO_DSRAM
    movw r8, #:lower16:RIO_OUT
    movt r8, #:upper16:RIO_OUT
    str r11, [r8]
    ROW_ADDR_STAGE_DELAY
.ifdef USE_RGB888_ROW_MAJOR_OUT
    movw r12, #:lower16:LOCAL_DSRAM
    movt r12, #:upper16:LOCAL_DSRAM
    ROW_RGB_OUT
.else
    LOAD_RGB_SETCLR_PTRS
    movw r12, #:lower16:LOCAL_DSRAM
    movt r12, #:upper16:LOCAL_DSRAM
    ROW_RGB_SETCLR
.endif
    subs r7, #1
    bne .Lrgb888_plane_loop\@
    adds r4, #1
    cmp r4, #32
    blo .Lrgb888_row_loop\@
.endm

.macro RGB111_ROW_MAJOR_LOOP
    movs r4, #0
.Lrgb111_row_loop\@:
    movs r7, #PLANE_COUNT
.Lrgb111_plane_loop\@:
    EXPAND_SHARED_RGB111_ROW_TO_DSRAM
    movw r8, #:lower16:RIO_OUT
    movt r8, #:upper16:RIO_OUT
    str r11, [r8]
    ROW_ADDR_STAGE_DELAY
    LOAD_RGB_SETCLR_PTRS
    movw r12, #:lower16:LOCAL_DSRAM
    movt r12, #:upper16:LOCAL_DSRAM
    ROW_RGB_SETCLR
    subs r7, #1
    bne .Lrgb111_plane_loop\@
    adds r4, #1
    cmp r4, #32
    blo .Lrgb111_row_loop\@
.endm

.macro STATE32_PREEXPANDED_ROW_MAJOR_LOOP
    movw r0, #:lower16:STATUS_ADDR
    movt r0, #:upper16:STATUS_ADDR
    movw r1, #:lower16:STATUS_STATE32_ROW
    movt r1, #:upper16:STATUS_STATE32_ROW
    str r1, [r0]
    movs r4, #0
.Lstate32_pre_row_loop\@:
    movs r7, #PLANE_COUNT
.Lstate32_pre_plane_loop\@:
    movw r12, #:lower16:SHARED_STATE32_BASE
    movt r12, #:upper16:SHARED_STATE32_BASE
.ifdef USE_STATE32_PREEXPANDED_PWM6
    add.w r12, r12, r4, lsl #10
    add.w r12, r12, r4, lsl #9
.else
    add.w r12, r12, r4, lsl #11
    add.w r12, r12, r4, lsl #9
    add.w r12, r12, r4, lsl #8
.endif
    movs r6, #PLANE_COUNT
    subs r6, r6, r7
    add.w r12, r12, r6, lsl #8
    movw r0, #:lower16:ROW_CACHE_SRC
    movt r0, #:upper16:ROW_CACHE_SRC
    str r12, [r0]
    movw r0, #:lower16:STATUS_ADDR
    movt r0, #:upper16:STATUS_ADDR
    movw r1, #:lower16:STATUS_STATE32_COPY
    movt r1, #:upper16:STATUS_STATE32_COPY
    str r1, [r0]
    push {r4, r7}
    COPY_SHARED_STATE32_ROW_TO_DSRAM
    pop {r4, r7}
    movw r3, #:lower16:local_row_addr_masks
    movt r3, #:upper16:local_row_addr_masks
    ldr.w r11, [r3, r4, lsl #2]
    ORR_OE_BITS r11
    movw r8, #:lower16:RIO_OUT
    movt r8, #:upper16:RIO_OUT
    str r11, [r8]
    ROW_ADDR_STAGE_DELAY
    LOAD_RGB_SETCLR_PTRS
    movw r12, #:lower16:LOCAL_DSRAM
    movt r12, #:upper16:LOCAL_DSRAM
    movw r0, #:lower16:STATUS_ADDR
    movt r0, #:upper16:STATUS_ADDR
    movw r1, #:lower16:STATUS_STATE32_SHIFT
    movt r1, #:upper16:STATUS_STATE32_SHIFT
    str r1, [r0]
    ROW_RGB_SETCLR
    subs r7, #1
    bne .Lstate32_pre_plane_loop\@
    adds r4, #1
    cmp r4, #32
    blo .Lstate32_pre_row_loop\@
.endm

.macro COPY_SHARED_SLAB_TO_DSRAM
    movw r8, #:lower16:LOCAL_DSRAM
    movt r8, #:upper16:LOCAL_DSRAM
    movs r10, #(PLANE_COUNT * 8)
1:
    ldmia r12!, {r0-r6,r11}
    stmia r8!, {r0-r6,r11}
    subs r10, #1
    bne 1b
.endm

.macro COPY_SHARED_SLAB_PLANE_TO_DSRAM
    movw r8, #:lower16:LOCAL_DSRAM
    movt r8, #:upper16:LOCAL_DSRAM
    movs r10, #8
1:
    ldmia r12!, {r0-r6,r11}
    stmia r8!, {r0-r6,r11}
    subs r10, #1
    bne 1b
.endm

.macro STATE32_SLAB_STREAM_LOOP
    movw r8, #:lower16:RIO_OUT
    movt r8, #:upper16:RIO_OUT
    LOAD_CLK_PTRS
    movw r2, #:lower16:SHARED_SLAB_BASE
    movt r2, #:upper16:SHARED_SLAB_BASE
    ldr r4, [r2, #SLAB_HOST_SEQ_OFF]
    str r4, [r2, #SLAB_CORE_SEQ_OFF]
    movw r0, #:lower16:SLAB_SCAN_ROW_ADDR
    movt r0, #:upper16:SLAB_SCAN_ROW_ADDR
    movs r1, #0
    str r1, [r0]
    dmb sy
.Lslab_wait\@:
    movw r0, #:lower16:STATUS_ADDR
    movt r0, #:upper16:STATUS_ADDR
    movw r1, #:lower16:STATUS_SLAB_WAIT
    movt r1, #:upper16:STATUS_SLAB_WAIT
    str r1, [r0]
    movw r2, #:lower16:SHARED_SLAB_BASE
    movt r2, #:upper16:SHARED_SLAB_BASE
    ldr r4, [r2, #SLAB_HOST_SEQ_OFF]
    ldr r5, [r2, #SLAB_CORE_SEQ_OFF]
    cmp r5, r4
    bhi .Lslab_tail_ahead\@
    cmp r4, r5
    beq .Lslab_wait\@
    dmb sy
    movs r6, #SLAB_RING_MASK
    ands r6, r5
    movw r12, #:lower16:(SHARED_SLAB_BASE + SLAB_SLOT_BASE_OFF)
    movt r12, #:upper16:(SHARED_SLAB_BASE + SLAB_SLOT_BASE_OFF)
.if SLAB_SLOT_STRIDE == 1552
    lsls r3, r6, #10
    add r12, r12, r3
    lsls r3, r6, #9
    add r12, r12, r3
    lsls r3, r6, #4
    add r12, r12, r3
.elseif SLAB_SLOT_STRIDE == 2832
    lsls r3, r6, #11
    add r12, r12, r3
    lsls r3, r6, #9
    add r12, r12, r3
    lsls r3, r6, #8
    add r12, r12, r3
    lsls r3, r6, #4
    add r12, r12, r3
.else
    .error "unsupported SLAB_SLOT_STRIDE"
.endif
    ldr r6, [r12, #SLAB_SLOT_ROW_PAIR_OFF]
    add r12, r12, #SLAB_SLOT_DATA_OFF
    adds r7, r5, #1
    mov r9, r6
    movw r0, #:lower16:STATUS_ADDR
    movt r0, #:upper16:STATUS_ADDR
    movw r1, #:lower16:STATUS_SLAB_COPY
    movt r1, #:upper16:STATUS_SLAB_COPY
    str r1, [r0]
    COPY_SHARED_SLAB_TO_DSRAM
    dmb sy
    movw r2, #:lower16:SHARED_SLAB_BASE
    movt r2, #:upper16:SHARED_SLAB_BASE
    str r7, [r2, #SLAB_CORE_SEQ_OFF]
    movw r0, #:lower16:STATUS_ADDR
    movt r0, #:upper16:STATUS_ADDR
    movw r1, #:lower16:STATUS_SLAB_SHIFT
    movt r1, #:upper16:STATUS_SLAB_SHIFT
    str r1, [r0]

    movw r3, #:lower16:local_row_addr_masks
    movt r3, #:upper16:local_row_addr_masks
.ifdef USE_SLAB_INTERNAL_ROW_COUNTER
    movw r0, #:lower16:SLAB_SCAN_ROW_ADDR
    movt r0, #:upper16:SLAB_SCAN_ROW_ADDR
    ldr r9, [r0]
    adds r1, r9, #1
    and r1, r1, #31
    str r1, [r0]
.endif
    ldr.w r11, [r3, r9, lsl #2]
    ORR_OE_BITS r11
    movw r8, #:lower16:RIO_OUT
    movt r8, #:upper16:RIO_OUT
    str r11, [r8]
    ROW_ADDR_STAGE_DELAY
    movs r7, #PLANE_COUNT
    movw r12, #:lower16:LOCAL_DSRAM
    movt r12, #:upper16:LOCAL_DSRAM
.Lslab_plane_loop\@:
    LOAD_RGB_SETCLR_PTRS
    ROW_RGB_SETCLR
    subs r7, #1
    bne .Lslab_plane_loop\@
    movw r0, #:lower16:FRAME_COUNTER
    movt r0, #:upper16:FRAME_COUNTER
    ldr r1, [r0]
    adds r1, #1
    str r1, [r0]
    b .Lslab_wait\@
.Lslab_tail_ahead\@:
    str r4, [r2, #SLAB_CORE_SEQ_OFF]
    dmb sy
    b .Lslab_wait\@
.endm

.macro STATE32_SLAB_PLANE_STREAM_LOOP
    movw r8, #:lower16:RIO_OUT
    movt r8, #:upper16:RIO_OUT
    LOAD_CLK_PTRS
    movw r2, #:lower16:SHARED_SLAB_BASE
    movt r2, #:upper16:SHARED_SLAB_BASE
    ldr r4, [r2, #SLAB_HOST_SEQ_OFF]
    str r4, [r2, #SLAB_CORE_SEQ_OFF]
    dmb sy
.Lslab_plane_wait\@:
    movw r0, #:lower16:STATUS_ADDR
    movt r0, #:upper16:STATUS_ADDR
    movw r1, #:lower16:STATUS_SLAB_PLANE_WAIT
    movt r1, #:upper16:STATUS_SLAB_PLANE_WAIT
    str r1, [r0]
    movw r2, #:lower16:SHARED_SLAB_BASE
    movt r2, #:upper16:SHARED_SLAB_BASE
    ldr r4, [r2, #SLAB_HOST_SEQ_OFF]
    ldr r5, [r2, #SLAB_CORE_SEQ_OFF]
    cmp r5, r4
    bhi .Lslab_plane_tail_ahead\@
    cmp r4, r5
    beq .Lslab_plane_wait\@
    dmb sy
    movs r6, #SLAB_RING_MASK
    ands r6, r5
    movw r12, #:lower16:(SHARED_SLAB_BASE + SLAB_SLOT_BASE_OFF)
    movt r12, #:upper16:(SHARED_SLAB_BASE + SLAB_SLOT_BASE_OFF)
.if SLAB_SLOT_STRIDE == 272
    lsls r3, r6, #8
    add r12, r12, r3
    lsls r3, r6, #4
    add r12, r12, r3
.else
    .error "STATE32_SLAB_PLANE_STREAM_LOOP requires SLAB_SLOT_STRIDE=272"
.endif
    ldr r6, [r12, #SLAB_SLOT_ROW_PAIR_OFF]
    add r12, r12, #SLAB_SLOT_DATA_OFF
    adds r7, r5, #1
    movw r0, #:lower16:STATUS_ADDR
    movt r0, #:upper16:STATUS_ADDR
    movw r1, #:lower16:STATUS_SLAB_PLANE_COPY
    movt r1, #:upper16:STATUS_SLAB_PLANE_COPY
    str r1, [r0]
    COPY_SHARED_SLAB_PLANE_TO_DSRAM
    dmb sy
    movw r2, #:lower16:SHARED_SLAB_BASE
    movt r2, #:upper16:SHARED_SLAB_BASE
    str r7, [r2, #SLAB_CORE_SEQ_OFF]

    mov r9, r6
    and r9, r9, #31
    lsrs r7, r6, #5
    movs r0, #PLANE_COUNT
    subs r7, r0, r7

    movw r3, #:lower16:local_row_addr_masks
    movt r3, #:upper16:local_row_addr_masks
    ldr.w r11, [r3, r9, lsl #2]
.ifndef USE_DEFER_OE_BLANK_UNTIL_LATCH
    ORR_OE_BITS r11
.endif
    movw r8, #:lower16:RIO_OUT
    movt r8, #:upper16:RIO_OUT
    str r11, [r8]
    ROW_ADDR_STAGE_DELAY
    LOAD_RGB_SETCLR_PTRS
    movw r12, #:lower16:LOCAL_DSRAM
    movt r12, #:upper16:LOCAL_DSRAM
    movw r0, #:lower16:STATUS_ADDR
    movt r0, #:upper16:STATUS_ADDR
    movw r1, #:lower16:STATUS_SLAB_PLANE_SHIFT
    movt r1, #:upper16:STATUS_SLAB_PLANE_SHIFT
    str r1, [r0]
    ROW_RGB_SETCLR
    movw r0, #:lower16:FRAME_COUNTER
    movt r0, #:upper16:FRAME_COUNTER
    ldr r1, [r0]
    adds r1, #1
    str r1, [r0]
    b .Lslab_plane_wait\@
.Lslab_plane_tail_ahead\@:
    str r4, [r2, #SLAB_CORE_SEQ_OFF]
    dmb sy
    b .Lslab_plane_wait\@
.endm

.macro STATE32_CHUNK_STREAM_LOOP
    movw r8, #:lower16:RIO_OUT
    movt r8, #:upper16:RIO_OUT
    LOAD_CLK_PTRS
    movw r2, #:lower16:SHARED_SLAB_BASE
    movt r2, #:upper16:SHARED_SLAB_BASE
    ldr r4, [r2, #CHUNK_HOST_SEQ_OFF]
    str r4, [r2, #CHUNK_CORE_SEQ_OFF]
    dmb sy
.Lchunk_wait\@:
    movw r0, #:lower16:STATUS_ADDR
    movt r0, #:upper16:STATUS_ADDR
    movw r1, #:lower16:STATUS_CHUNK_WAIT
    movt r1, #:upper16:STATUS_CHUNK_WAIT
    str r1, [r0]
    movw r2, #:lower16:SHARED_SLAB_BASE
    movt r2, #:upper16:SHARED_SLAB_BASE
    ldr r4, [r2, #CHUNK_HOST_SEQ_OFF]
    ldr r5, [r2, #CHUNK_CORE_SEQ_OFF]
    cmp r5, r4
    bhi .Lchunk_tail_ahead\@
    cmp r4, r5
    beq .Lchunk_wait\@
    dmb sy
    ldr r4, [r2, #CHUNK_FIRST_INDEX_OFF]
    ldr r6, [r2, #CHUNK_COUNT_OFF]
    movw r0, #:lower16:CHUNK_DEBUG_SEQ
    movt r0, #:upper16:CHUNK_DEBUG_SEQ
    movs r1, #0
    str r1, [r0]
    movw r0, #:lower16:CHUNK_DEBUG_FIRST_INDEX
    movt r0, #:upper16:CHUNK_DEBUG_FIRST_INDEX
    str r4, [r0]
    movw r0, #:lower16:CHUNK_DEBUG_COUNT
    movt r0, #:upper16:CHUNK_DEBUG_COUNT
    str r6, [r0]
    movw r0, #:lower16:CHUNK_DEBUG_SEQ
    movt r0, #:upper16:CHUNK_DEBUG_SEQ
    str r5, [r0]
    movw r12, #:lower16:(SHARED_SLAB_BASE + CHUNK_DATA_OFF)
    movt r12, #:upper16:(SHARED_SLAB_BASE + CHUNK_DATA_OFF)
    movw r0, #:lower16:STATUS_ADDR
    movt r0, #:upper16:STATUS_ADDR
    movw r1, #:lower16:STATUS_CHUNK_SHIFT
    movt r1, #:upper16:STATUS_CHUNK_SHIFT
    str r1, [r0]
.Lchunk_slab_loop\@:
.ifdef USE_STATE32_ROW_MAJOR_RECORDS
    SET_ROWMAJOR_ADDR_DWELL_FROM_INDEX r4
.else
    mov r9, r4
    and r9, r9, #31
    mov r7, r4
    lsrs r7, r7, #5
    movs r0, #PLANE_COUNT
    subs r7, r0, r7
.endif
    movw r3, #:lower16:local_row_addr_masks
    movt r3, #:upper16:local_row_addr_masks
    ldr.w r11, [r3, r9, lsl #2]
    ORR_OE_BITS r11
    movw r8, #:lower16:RIO_OUT
    movt r8, #:upper16:RIO_OUT
    str r11, [r8]
    ROW_ADDR_STAGE_DELAY
.ifdef USE_FULL_STATE32_RIO_WORDS
    ROW_RGB_OUT
.else
.ifdef USE_FULL_STATE32_RIO_WORDS
    ROW_RGB_OUT
.else
.ifdef USE_DIRECT_RIO_WORDS
    ROW_DIRECT_OUT
.else
    LOAD_RGB_SETCLR_PTRS
    ROW_RGB_SETCLR
.endif
.endif
.endif
    adds r4, #1
    subs r6, #1
    bne .Lchunk_slab_loop\@
    dmb sy
    movw r2, #:lower16:SHARED_SLAB_BASE
    movt r2, #:upper16:SHARED_SLAB_BASE
    ldr r5, [r2, #CHUNK_CORE_SEQ_OFF]
    adds r5, #1
    str r5, [r2, #CHUNK_CORE_SEQ_OFF]
    movw r0, #:lower16:FRAME_COUNTER
    movt r0, #:upper16:FRAME_COUNTER
    ldr r1, [r0]
    adds r1, #1
    str r1, [r0]
    b .Lchunk_wait\@
.Lchunk_tail_ahead\@:
    str r4, [r2, #CHUNK_CORE_SEQ_OFF]
    dmb sy
    b .Lchunk_wait\@
.endm

.macro DMA_SELECT_STATE32_CHUNK_CHANNEL channel_base enable_reg disable_reg
.if DMA_ROUND_ROBIN_CHANNELS > 1
    mov \disable_reg, r4
.if DMA_CHUNK_RECORDS == 8
    lsrs \disable_reg, \disable_reg, #3
.elseif DMA_CHUNK_RECORDS == 4
    lsrs \disable_reg, \disable_reg, #2
.elseif DMA_CHUNK_RECORDS == 2
    lsrs \disable_reg, \disable_reg, #1
.elseif DMA_CHUNK_RECORDS == 1
.else
.error "DMA_ROUND_ROBIN_CHANNELS currently expects DMA_CHUNK_RECORDS=1, 2, 4, or 8"
.endif
.if DMA_ROUND_ROBIN_CHANNELS == 2
    and \disable_reg, \disable_reg, #1
.elseif DMA_ROUND_ROBIN_CHANNELS == 4
    and \disable_reg, \disable_reg, #3
.elseif DMA_ROUND_ROBIN_CHANNELS == 6
.Ldma_channel_mod\@:
    cmp \disable_reg, #6
    blo .Ldma_channel_mod_done\@
    subs \disable_reg, #6
    b .Ldma_channel_mod\@
.Ldma_channel_mod_done\@:
.else
.error "DMA_ROUND_ROBIN_CHANNELS currently expects 1, 2, 4, or 6"
.endif
    movw \channel_base, #:lower16:(RP1_DMA_BASE + 0x100)
    movt \channel_base, #:upper16:(RP1_DMA_BASE + 0x100)
    add \channel_base, \channel_base, \disable_reg, lsl #8
    movs \enable_reg, #1
    lsls \enable_reg, \enable_reg, \disable_reg
    mov \disable_reg, \enable_reg
    lsls \disable_reg, \disable_reg, #8
    orr \enable_reg, \enable_reg, \disable_reg
.else
    movw \channel_base, #:lower16:RP1_DMA_CH7_BASE
    movt \channel_base, #:upper16:RP1_DMA_CH7_BASE
    movw \enable_reg, #:lower16:RP1_DMA_CH7_ENABLE_WE
    movt \enable_reg, #:upper16:RP1_DMA_CH7_ENABLE_WE
    movw \disable_reg, #:lower16:RP1_DMA_CH7_DISABLE_WE
    movt \disable_reg, #:upper16:RP1_DMA_CH7_DISABLE_WE
.endif
.endm

.macro DMA_LOAD_CTL_H_FOR_CHANNEL dest channel_base
.if DMA_ROUND_ROBIN_CHANNELS > 2
    movw \dest, #:lower16:(RP1_DMA_BASE + 0x300)
    movt \dest, #:upper16:(RP1_DMA_BASE + 0x300)
    cmp \channel_base, \dest
    blo .Ldma_ctl_h_burst8\@
    movw \dest, #:lower16:RP1_DMA_CTL_H_MEMCPY32_BURST4
    movt \dest, #:upper16:RP1_DMA_CTL_H_MEMCPY32_BURST4
    b .Ldma_ctl_h_done\@
.Ldma_ctl_h_burst8\@:
    movw \dest, #:lower16:RP1_DMA_CTL_H_MEMCPY32
    movt \dest, #:upper16:RP1_DMA_CTL_H_MEMCPY32
.Ldma_ctl_h_done\@:
.else
    movw \dest, #:lower16:RP1_DMA_CTL_H_MEMCPY32
    movt \dest, #:upper16:RP1_DMA_CTL_H_MEMCPY32
.endif
.endm

.macro DMA_PIPE_LOAD_SLOT_BASE dest
    mov r0, r4
.if DMA_CHUNK_RECORDS == 8
    lsrs r0, r0, #3
.elseif DMA_CHUNK_RECORDS == 4
    lsrs r0, r0, #2
.elseif DMA_CHUNK_RECORDS == 2
    lsrs r0, r0, #1
.elseif DMA_CHUNK_RECORDS == 1
.else
.error "DMA pipeline slot selection currently expects DMA_CHUNK_RECORDS=1, 2, 4, or 8"
.endif
.if DMA_PIPE_SLOT_COUNT == 8
    and r0, r0, #7
.elseif DMA_PIPE_SLOT_COUNT == 4
    and r0, r0, #3
.elseif DMA_PIPE_SLOT_COUNT == 5 || DMA_PIPE_SLOT_COUNT == 6 || DMA_PIPE_SLOT_COUNT == 7
.Lpipe_slot_mod\@:
    cmp r0, #DMA_PIPE_SLOT_COUNT
    blo .Lpipe_slot_mod_done\@
    subs r0, #DMA_PIPE_SLOT_COUNT
    b .Lpipe_slot_mod\@
.Lpipe_slot_mod_done\@:
.else
.error "DMA pipeline slot selection currently expects DMA_PIPE_SLOT_COUNT=4, 5, 6, 7, or 8"
.endif
    cmp r0, #0
    bne .Lpipe_slot_not0\@
    movw \dest, #:lower16:DMA_PIPE_SLOT0_BASE
    movt \dest, #:upper16:DMA_PIPE_SLOT0_BASE
    b .Lpipe_slot_done\@
.Lpipe_slot_not0\@:
    cmp r0, #1
    bne .Lpipe_slot_not1\@
    movw \dest, #:lower16:DMA_PIPE_SLOT1_BASE
    movt \dest, #:upper16:DMA_PIPE_SLOT1_BASE
    b .Lpipe_slot_done\@
.Lpipe_slot_not1\@:
    cmp r0, #2
    bne .Lpipe_slot_3\@
    movw \dest, #:lower16:DMA_PIPE_SLOT2_BASE
    movt \dest, #:upper16:DMA_PIPE_SLOT2_BASE
    b .Lpipe_slot_done\@
.Lpipe_slot_3\@:
    cmp r0, #3
    bne .Lpipe_slot_4\@
    movw \dest, #:lower16:DMA_PIPE_SLOT3_BASE
    movt \dest, #:upper16:DMA_PIPE_SLOT3_BASE
    b .Lpipe_slot_done\@
.Lpipe_slot_4\@:
    cmp r0, #4
    bne .Lpipe_slot_5\@
    movw \dest, #:lower16:DMA_PIPE_SLOT4_BASE
    movt \dest, #:upper16:DMA_PIPE_SLOT4_BASE
    b .Lpipe_slot_done\@
.Lpipe_slot_5\@:
    cmp r0, #5
    bne .Lpipe_slot_6\@
    movw \dest, #:lower16:DMA_PIPE_SLOT5_BASE
    movt \dest, #:upper16:DMA_PIPE_SLOT5_BASE
    b .Lpipe_slot_done\@
.Lpipe_slot_6\@:
    cmp r0, #6
    bne .Lpipe_slot_7\@
    movw \dest, #:lower16:DMA_PIPE_SLOT6_BASE
    movt \dest, #:upper16:DMA_PIPE_SLOT6_BASE
    b .Lpipe_slot_done\@
.Lpipe_slot_7\@:
    movw \dest, #:lower16:DMA_PIPE_SLOT7_BASE
    movt \dest, #:upper16:DMA_PIPE_SLOT7_BASE
.Lpipe_slot_done\@:
.endm

.macro DMA_COPY_STATE32_CHUNK
    movw r0, #:lower16:STATUS_ADDR
    movt r0, #:upper16:STATUS_ADDR
    movw r1, #:lower16:STATUS_DMA_CHUNK_COPY
    movt r1, #:upper16:STATUS_DMA_CHUNK_COPY
    str r1, [r0]

    movw r2, #:lower16:SHARED_SLAB_BASE
    movt r2, #:upper16:SHARED_SLAB_BASE
    ldr r5, [r2, #DMA_CHUNK_SRC_LO_OFF]
    ldr r6, [r2, #DMA_CHUNK_SRC_HI_OFF]
.ifndef USE_STATE32_DMA_REPEAT_SOURCE_CHUNK
    mov r7, r4
.if ROW_WORDS == 256
    lsls r7, r7, #10
.else
    movw r0, #:lower16:(ROW_WORDS * 4)
    movt r0, #:upper16:(ROW_WORDS * 4)
    mul r7, r4, r0
.endif
    adds r5, r5, r7
    movs r0, #0
    adcs r6, r0
.endif

    movw r0, #:lower16:RP1_DMA_BASE
    movt r0, #:upper16:RP1_DMA_BASE
    DMA_SELECT_STATE32_CHUNK_CHANNEL r3, r12, r7
    movs r1, #1
    str r1, [r0, #RP1_DMA_CFG]
    str r7, [r0, #RP1_DMA_CHEN]
    movw r1, #:lower16:0xffffffff
    movt r1, #:upper16:0xffffffff
    str r1, [r0, #RP1_DMA_COMMON_INTCLEAR]

    str r1, [r3, #RP1_DMA_CH_INTCLEAR]
    movw r1, #:lower16:RP1_DMA_IRQ_DONE_OR_ERR
    movt r1, #:upper16:RP1_DMA_IRQ_DONE_OR_ERR
    str r1, [r3, #RP1_DMA_CH_INTSTATUS_ENA]
    movs r1, #0
    str r1, [r3, #RP1_DMA_CH_INTSIGNAL_ENA]

    str r5, [r3, #RP1_DMA_CH_SAR]
    str r6, [r3, #(RP1_DMA_CH_SAR + 4)]
    movw r1, #:lower16:(0xc020000000 + (DMA_CHUNK_DATA_BASE - 0x20000000))
    movt r1, #:upper16:(0xc020000000 + (DMA_CHUNK_DATA_BASE - 0x20000000))
    str r1, [r3, #RP1_DMA_CH_DAR]
    movw r1, #:lower16:((0xc020000000 + (DMA_CHUNK_DATA_BASE - 0x20000000)) >> 32)
    movt r1, #:upper16:((0xc020000000 + (DMA_CHUNK_DATA_BASE - 0x20000000)) >> 32)
    str r1, [r3, #(RP1_DMA_CH_DAR + 4)]
    movw r1, #:lower16:RP1_DMA_CHUNK_BLOCK_TS_32
    movt r1, #:upper16:RP1_DMA_CHUNK_BLOCK_TS_32
    str r1, [r3, #RP1_DMA_CH_BLOCK_TS]
    movs r1, #0
    str r1, [r3, #(RP1_DMA_CH_BLOCK_TS + 4)]
    movw r1, #:lower16:RP1_DMA_CTL_LO_MEMCPY32
    movt r1, #:upper16:RP1_DMA_CTL_LO_MEMCPY32
    str r1, [r3, #RP1_DMA_CH_CTL_L]
    DMA_LOAD_CTL_H_FOR_CHANNEL r1, r3
    str r1, [r3, #RP1_DMA_CH_CTL_H]
    movs r1, #0
    str r1, [r3, #RP1_DMA_CH_CFG_L]
    movw r1, #:lower16:RP1_DMA_CFG_H_MEMCPY
    movt r1, #:upper16:RP1_DMA_CFG_H_MEMCPY
    str r1, [r3, #RP1_DMA_CH_CFG_H]
    movs r1, #0
    str r1, [r3, #RP1_DMA_CH_LLP]
    str r1, [r3, #(RP1_DMA_CH_LLP + 4)]
    dmb sy
    str r12, [r0, #RP1_DMA_CHEN]
.Ldma_chunk_wait\@:
    ldr r1, [r3, #RP1_DMA_CH_INTSTATUS]
    movw r5, #:lower16:RP1_DMA_IRQ_DONE_OR_ERR
    movt r5, #:upper16:RP1_DMA_IRQ_DONE_OR_ERR
    tst r1, r5
    beq .Ldma_chunk_wait\@
    movw r2, #:lower16:SHARED_SLAB_BASE
    movt r2, #:upper16:SHARED_SLAB_BASE
    str r1, [r2, #DMA_CHUNK_STATUS_OFF]
    movw r5, #:lower16:RP1_DMA_IRQ_DMA_TRF
    movt r5, #:upper16:RP1_DMA_IRQ_DMA_TRF
    tst r1, r5
    beq .Ldma_chunk_wait\@
    movw r1, #:lower16:0xffffffff
    movt r1, #:upper16:0xffffffff
    str r1, [r3, #RP1_DMA_CH_INTCLEAR]
.endm

.macro DMA_START_STATE32_CHUNK_DEST_R10
    movw r0, #:lower16:STATUS_ADDR
    movt r0, #:upper16:STATUS_ADDR
    movw r1, #:lower16:STATUS_DMA_CHUNK_COPY
    movt r1, #:upper16:STATUS_DMA_CHUNK_COPY
    str r1, [r0]

    movw r2, #:lower16:SHARED_SLAB_BASE
    movt r2, #:upper16:SHARED_SLAB_BASE
    ldr r5, [r2, #DMA_CHUNK_SRC_LO_OFF]
    ldr r6, [r2, #DMA_CHUNK_SRC_HI_OFF]
.ifndef USE_STATE32_DMA_REPEAT_SOURCE_CHUNK
    mov r7, r4
.if ROW_WORDS == 256
    lsls r7, r7, #10
.else
    movw r0, #:lower16:(ROW_WORDS * 4)
    movt r0, #:upper16:(ROW_WORDS * 4)
    mul r7, r4, r0
.endif
    adds r5, r5, r7
    movs r0, #0
    adcs r6, r0
.endif

    movw r0, #:lower16:RP1_DMA_BASE
    movt r0, #:upper16:RP1_DMA_BASE
    DMA_SELECT_STATE32_CHUNK_CHANNEL r3, r12, r7
    movs r1, #1
    str r1, [r0, #RP1_DMA_CFG]
    str r7, [r0, #RP1_DMA_CHEN]
    movw r1, #:lower16:0xffffffff
    movt r1, #:upper16:0xffffffff
    str r1, [r0, #RP1_DMA_COMMON_INTCLEAR]

    str r1, [r3, #RP1_DMA_CH_INTCLEAR]
    movw r1, #:lower16:RP1_DMA_IRQ_DONE_OR_ERR
    movt r1, #:upper16:RP1_DMA_IRQ_DONE_OR_ERR
    str r1, [r3, #RP1_DMA_CH_INTSTATUS_ENA]
    movs r1, #0
    str r1, [r3, #RP1_DMA_CH_INTSIGNAL_ENA]

    str r5, [r3, #RP1_DMA_CH_SAR]
    str r6, [r3, #(RP1_DMA_CH_SAR + 4)]
    str r10, [r3, #RP1_DMA_CH_DAR]
    movs r1, #0xc0
    str r1, [r3, #(RP1_DMA_CH_DAR + 4)]
.ifdef USE_STATE32_DMA_ASYNC_PARTIAL_FINAL_CHUNK
    movw r7, #:lower16:STATE32_DMA_TOTAL_RECORDS
    movt r7, #:upper16:STATE32_DMA_TOTAL_RECORDS
    subs r7, r7, r4
    cmp r7, #DMA_CHUNK_RECORDS
    bls .Ldma_fast_count_ready\@
    movs r7, #DMA_CHUNK_RECORDS
.Ldma_fast_count_ready\@:
    movw r1, #:lower16:ROW_WORDS
    movt r1, #:upper16:ROW_WORDS
    muls r1, r7, r1
    subs r1, #1
.else
    movw r1, #:lower16:RP1_DMA_CHUNK_BLOCK_TS_32
    movt r1, #:upper16:RP1_DMA_CHUNK_BLOCK_TS_32
.endif
    str r1, [r3, #RP1_DMA_CH_BLOCK_TS]
    movs r1, #0
    str r1, [r3, #(RP1_DMA_CH_BLOCK_TS + 4)]
    movw r1, #:lower16:RP1_DMA_CTL_LO_MEMCPY32
    movt r1, #:upper16:RP1_DMA_CTL_LO_MEMCPY32
    str r1, [r3, #RP1_DMA_CH_CTL_L]
    DMA_LOAD_CTL_H_FOR_CHANNEL r1, r3
    str r1, [r3, #RP1_DMA_CH_CTL_H]
    movs r1, #0
    str r1, [r3, #RP1_DMA_CH_CFG_L]
    movw r1, #:lower16:RP1_DMA_CFG_H_MEMCPY
    movt r1, #:upper16:RP1_DMA_CFG_H_MEMCPY
    str r1, [r3, #RP1_DMA_CH_CFG_H]
    movs r1, #0
    str r1, [r3, #RP1_DMA_CH_LLP]
    str r1, [r3, #(RP1_DMA_CH_LLP + 4)]
    dmb sy
    str r12, [r0, #RP1_DMA_CHEN]
.endm

.macro DMA_START_STATE32_CHUNK_DEST_R10_FAST
    movw r0, #:lower16:STATUS_ADDR
    movt r0, #:upper16:STATUS_ADDR
    movw r1, #:lower16:STATUS_DMA_CHUNK_COPY
    movt r1, #:upper16:STATUS_DMA_CHUNK_COPY
    str r1, [r0]

    movw r2, #:lower16:SHARED_SLAB_BASE
    movt r2, #:upper16:SHARED_SLAB_BASE
    ldr r5, [r2, #DMA_CHUNK_SRC_LO_OFF]
    ldr r6, [r2, #DMA_CHUNK_SRC_HI_OFF]
.ifndef USE_STATE32_DMA_REPEAT_SOURCE_CHUNK
    mov r7, r4
.if ROW_WORDS == 256
    lsls r7, r7, #10
.else
    movw r0, #:lower16:(ROW_WORDS * 4)
    movt r0, #:upper16:(ROW_WORDS * 4)
    mul r7, r4, r0
.endif
    adds r5, r5, r7
    movs r0, #0
    adcs r6, r0
.endif

    movw r0, #:lower16:RP1_DMA_BASE
    movt r0, #:upper16:RP1_DMA_BASE
    DMA_SELECT_STATE32_CHUNK_CHANNEL r3, r12, r7
    str r7, [r0, #RP1_DMA_CHEN]

    movw r1, #:lower16:0xffffffff
    movt r1, #:upper16:0xffffffff
    str r1, [r3, #RP1_DMA_CH_INTCLEAR]

    str r5, [r3, #RP1_DMA_CH_SAR]
    str r6, [r3, #(RP1_DMA_CH_SAR + 4)]
    str r10, [r3, #RP1_DMA_CH_DAR]
    movs r1, #0xc0
    str r1, [r3, #(RP1_DMA_CH_DAR + 4)]
.ifdef USE_STATE32_DMA_ASYNC_PARTIAL_FINAL_CHUNK
    movw r7, #:lower16:STATE32_DMA_TOTAL_RECORDS
    movt r7, #:upper16:STATE32_DMA_TOTAL_RECORDS
    subs r7, r7, r4
    cmp r7, #DMA_CHUNK_RECORDS
    bls .Ldma_fast_dest_count_ready\@
    movs r7, #DMA_CHUNK_RECORDS
.Ldma_fast_dest_count_ready\@:
    movw r1, #:lower16:ROW_WORDS
    movt r1, #:upper16:ROW_WORDS
    muls r1, r7, r1
    subs r1, #1
.else
    movw r1, #:lower16:RP1_DMA_CHUNK_BLOCK_TS_32
    movt r1, #:upper16:RP1_DMA_CHUNK_BLOCK_TS_32
.endif
    str r1, [r3, #RP1_DMA_CH_BLOCK_TS]
    movs r1, #0
    str r1, [r3, #(RP1_DMA_CH_BLOCK_TS + 4)]
    dmb sy
    str r12, [r0, #RP1_DMA_CHEN]
.endm

.macro DMA_WAIT_STATE32_CHUNK
    DMA_SELECT_STATE32_CHUNK_CHANNEL r3, r12, r7
.Ldma_async_wait\@:
    ldr r1, [r3, #RP1_DMA_CH_INTSTATUS]
    movw r5, #:lower16:RP1_DMA_IRQ_DONE_OR_ERR
    movt r5, #:upper16:RP1_DMA_IRQ_DONE_OR_ERR
    tst r1, r5
    beq .Ldma_async_wait\@
    movw r2, #:lower16:SHARED_SLAB_BASE
    movt r2, #:upper16:SHARED_SLAB_BASE
    str r1, [r2, #DMA_CHUNK_STATUS_OFF]
    movw r5, #:lower16:RP1_DMA_IRQ_DMA_TRF
    movt r5, #:upper16:RP1_DMA_IRQ_DMA_TRF
    tst r1, r5
    beq .Ldma_async_wait\@
    movw r1, #:lower16:0xffffffff
    movt r1, #:upper16:0xffffffff
    str r1, [r3, #RP1_DMA_CH_INTCLEAR]
.endm

.macro DMA_POLL_STATE32_CHUNK_READY ready
    DMA_SELECT_STATE32_CHUNK_CHANNEL r3, r12, r7
    ldr r1, [r3, #RP1_DMA_CH_INTSTATUS]
    movw r5, #:lower16:RP1_DMA_IRQ_DONE_OR_ERR
    movt r5, #:upper16:RP1_DMA_IRQ_DONE_OR_ERR
    tst r1, r5
    beq .Ldma_poll_not_ready\@
    movw r2, #:lower16:SHARED_SLAB_BASE
    movt r2, #:upper16:SHARED_SLAB_BASE
    str r1, [r2, #DMA_CHUNK_STATUS_OFF]
    movw r5, #:lower16:RP1_DMA_IRQ_DMA_TRF
    movt r5, #:upper16:RP1_DMA_IRQ_DMA_TRF
    tst r1, r5
    beq .Ldma_poll_not_ready\@
    movw r1, #:lower16:0xffffffff
    movt r1, #:upper16:0xffffffff
    str r1, [r3, #RP1_DMA_CH_INTCLEAR]
    b \ready
.Ldma_poll_not_ready\@:
.endm

.macro STATE32_DMA_CHUNK_STREAM_LOOP
    movw r8, #:lower16:RIO_OUT
    movt r8, #:upper16:RIO_OUT
    LOAD_CLK_PTRS
.Ldma_frame_loop\@:
    movs r4, #0
.Ldma_chunk_loop\@:
    DMA_COPY_STATE32_CHUNK
    movw r12, #:lower16:DMA_CHUNK_DATA_BASE
    movt r12, #:upper16:DMA_CHUNK_DATA_BASE
    movw r0, #:lower16:STATUS_ADDR
    movt r0, #:upper16:STATUS_ADDR
    movw r1, #:lower16:STATUS_DMA_CHUNK_SHIFT
    movt r1, #:upper16:STATUS_DMA_CHUNK_SHIFT
    str r1, [r0]
    movs r6, #DMA_CHUNK_RECORDS
.Ldma_chunk_slab_loop\@:
.ifdef USE_STATE32_ROW_MAJOR_RECORDS
    SET_ROWMAJOR_ADDR_DWELL_FROM_INDEX r4
.else
    mov r9, r4
    and r9, r9, #31
    mov r7, r4
    lsrs r7, r7, #5
    movs r0, #PLANE_COUNT
    subs r7, r0, r7
.endif
    movw r3, #:lower16:local_row_addr_masks
    movt r3, #:upper16:local_row_addr_masks
    ldr.w r11, [r3, r9, lsl #2]
    ORR_OE_BITS r11
    movw r8, #:lower16:RIO_OUT
    movt r8, #:upper16:RIO_OUT
    str r11, [r8]
    ROW_ADDR_STAGE_DELAY
.ifdef USE_FULL_STATE32_RIO_WORDS
    ROW_RGB_OUT
.else
.ifdef USE_FULL_STATE32_RIO_WORDS
    ROW_RGB_OUT
.else
.ifdef USE_DIRECT_RIO_WORDS
    ROW_DIRECT_OUT
.else
    LOAD_RGB_SETCLR_PTRS
    ROW_RGB_SETCLR
.endif
.endif
.endif
    adds r4, #1
    subs r6, #1
    bne .Ldma_chunk_slab_loop\@
    cmp r4, #(32 * PLANE_COUNT)
    blo .Ldma_chunk_loop\@
    movw r0, #:lower16:FRAME_COUNTER
    movt r0, #:upper16:FRAME_COUNTER
    ldr r1, [r0]
    adds r1, #1
    str r1, [r0]
    b .Ldma_frame_loop\@
.endm

.macro STATE32_DMA_ASYNC_CHUNK_STREAM_LOOP
    movw r8, #:lower16:RIO_OUT
    movt r8, #:upper16:RIO_OUT
    LOAD_CLK_PTRS
.Ldma_async_frame_loop\@:
    movs r4, #0
    movw r10, #:lower16:DMA_CHUNK_DATA_BASE
    movt r10, #:upper16:DMA_CHUNK_DATA_BASE
    DMA_START_STATE32_CHUNK_DEST_R10
    DMA_WAIT_STATE32_CHUNK
    movs r4, #DMA_CHUNK_RECORDS
.Ldma_async_chunk_loop\@:
    cmp r4, #(32 * PLANE_COUNT)
    bhs .Ldma_async_no_prefetch\@
.if DMA_CHUNK_RECORDS == 8
    tst r4, #DMA_CHUNK_RECORDS
.else
    mov r0, r4
.Ldma_async_prefetch_mod2chunk\@:
    cmp r0, #(2 * DMA_CHUNK_RECORDS)
    blo .Ldma_async_prefetch_mod2chunk_done\@
    subs r0, #(2 * DMA_CHUNK_RECORDS)
    b .Ldma_async_prefetch_mod2chunk\@
.Ldma_async_prefetch_mod2chunk_done\@:
    cmp r0, #0
.endif
    bne .Ldma_async_prefetch_alt\@
    movw r10, #:lower16:DMA_CHUNK_DATA_BASE
    movt r10, #:upper16:DMA_CHUNK_DATA_BASE
    b .Ldma_async_prefetch_start\@
.Ldma_async_prefetch_alt\@:
    movw r10, #:lower16:DMA_CHUNK_ALT_DATA_BASE
    movt r10, #:upper16:DMA_CHUNK_ALT_DATA_BASE
.Ldma_async_prefetch_start\@:
    DMA_START_STATE32_CHUNK_DEST_R10_FAST
.Ldma_async_no_prefetch\@:
    subs r4, #DMA_CHUNK_RECORDS
.Ldma_async_shift_current\@:
.if DMA_CHUNK_RECORDS == 8
    tst r4, #DMA_CHUNK_RECORDS
.else
    mov r0, r4
.Ldma_async_shift_mod2chunk\@:
    cmp r0, #(2 * DMA_CHUNK_RECORDS)
    blo .Ldma_async_shift_mod2chunk_done\@
    subs r0, #(2 * DMA_CHUNK_RECORDS)
    b .Ldma_async_shift_mod2chunk\@
.Ldma_async_shift_mod2chunk_done\@:
    cmp r0, #0
.endif
    bne .Ldma_async_shift_alt\@
    movw r12, #:lower16:DMA_CHUNK_DATA_BASE
    movt r12, #:upper16:DMA_CHUNK_DATA_BASE
    b .Ldma_async_shift_start\@
.Ldma_async_shift_alt\@:
    movw r12, #:lower16:DMA_CHUNK_ALT_DATA_BASE
    movt r12, #:upper16:DMA_CHUNK_ALT_DATA_BASE
.Ldma_async_shift_start\@:
    movw r0, #:lower16:STATUS_ADDR
    movt r0, #:upper16:STATUS_ADDR
    movw r1, #:lower16:STATUS_DMA_CHUNK_SHIFT
    movt r1, #:upper16:STATUS_DMA_CHUNK_SHIFT
    str r1, [r0]
.ifdef USE_STATE32_DMA_ASYNC_PARTIAL_FINAL_CHUNK
    movw r6, #:lower16:STATE32_DMA_TOTAL_RECORDS
    movt r6, #:upper16:STATE32_DMA_TOTAL_RECORDS
    subs r6, r6, r4
    cmp r6, #DMA_CHUNK_RECORDS
    bls .Ldma_async_shift_count_ready\@
    movs r6, #DMA_CHUNK_RECORDS
.Ldma_async_shift_count_ready\@:
.else
    movs r6, #DMA_CHUNK_RECORDS
.endif
.Ldma_async_chunk_slab_loop\@:
.ifdef USE_STATE32_ROW_MAJOR_RECORDS
    SET_ROWMAJOR_ADDR_DWELL_FROM_INDEX r4
.else
    mov r9, r4
    and r9, r9, #31
    mov r7, r4
    lsrs r7, r7, #5
    movs r0, #PLANE_COUNT
    subs r7, r0, r7
.endif
    movw r3, #:lower16:local_row_addr_masks
    movt r3, #:upper16:local_row_addr_masks
    ldr.w r11, [r3, r9, lsl #2]
    ORR_OE_BITS r11
    movw r8, #:lower16:RIO_OUT
    movt r8, #:upper16:RIO_OUT
    str r11, [r8]
    ROW_ADDR_STAGE_DELAY
.ifdef USE_FULL_STATE32_RIO_WORDS
    ROW_RGB_OUT
.else
.ifdef USE_FULL_STATE32_RIO_WORDS
    ROW_RGB_OUT
.else
.ifdef USE_DIRECT_RIO_WORDS
    ROW_DIRECT_OUT
.else
    LOAD_RGB_SETCLR_PTRS
    ROW_RGB_SETCLR
.endif
.endif
.endif
    adds r4, #1
    subs r6, #1
    bne .Ldma_async_chunk_slab_loop\@
    cmp r4, #(32 * PLANE_COUNT)
    bhs .Ldma_async_frame_done\@
.ifdef USE_STATE32_DMA_ASYNC_REPEAT_ON_UNDERRUN
    DMA_POLL_STATE32_CHUNK_READY .Ldma_async_next_ready\@
    movw r0, #:lower16:DMA_ASYNC_UNDERRUN_COUNTER
    movt r0, #:upper16:DMA_ASYNC_UNDERRUN_COUNTER
    ldr r1, [r0]
    adds r1, #1
    str r1, [r0]
    subs r4, #DMA_CHUNK_RECORDS
    b .Ldma_async_shift_current\@
.Ldma_async_next_ready\@:
.else
    DMA_WAIT_STATE32_CHUNK
.endif
    adds r4, #DMA_CHUNK_RECORDS
    b .Ldma_async_chunk_loop\@
.Ldma_async_frame_done\@:
    movw r0, #:lower16:FRAME_COUNTER
    movt r0, #:upper16:FRAME_COUNTER
    ldr r1, [r0]
    adds r1, #1
    str r1, [r0]
    b .Ldma_async_frame_loop\@
.endm

.macro STATE32_DMA_DUALPAIR_CHUNK_STREAM_LOOP
    movw r8, #:lower16:RIO_OUT
    movt r8, #:upper16:RIO_OUT
    LOAD_CLK_PTRS
.Ldma_dual_frame_loop\@:
    movs r4, #0
.Ldma_dual_pair_loop\@:
    movw r10, #:lower16:DMA_CHUNK_DATA_BASE
    movt r10, #:upper16:DMA_CHUNK_DATA_BASE
    DMA_START_STATE32_CHUNK_DEST_R10
    adds r4, #DMA_CHUNK_RECORDS
    movw r10, #:lower16:DMA_CHUNK_ALT_DATA_BASE
    movt r10, #:upper16:DMA_CHUNK_ALT_DATA_BASE
    DMA_START_STATE32_CHUNK_DEST_R10
    subs r4, #DMA_CHUNK_RECORDS

    DMA_WAIT_STATE32_CHUNK
    movw r12, #:lower16:DMA_CHUNK_DATA_BASE
    movt r12, #:upper16:DMA_CHUNK_DATA_BASE
    movw r0, #:lower16:STATUS_ADDR
    movt r0, #:upper16:STATUS_ADDR
    movw r1, #:lower16:STATUS_DMA_CHUNK_SHIFT
    movt r1, #:upper16:STATUS_DMA_CHUNK_SHIFT
    str r1, [r0]
    movs r6, #DMA_CHUNK_RECORDS
.Ldma_dual_first_slab_loop\@:
.ifdef USE_STATE32_ROW_MAJOR_RECORDS
    SET_ROWMAJOR_ADDR_DWELL_FROM_INDEX r4
.else
    mov r9, r4
    and r9, r9, #31
    mov r7, r4
    lsrs r7, r7, #5
    movs r0, #PLANE_COUNT
    subs r7, r0, r7
.endif
    movw r3, #:lower16:local_row_addr_masks
    movt r3, #:upper16:local_row_addr_masks
    ldr.w r11, [r3, r9, lsl #2]
    ORR_OE_BITS r11
    movw r8, #:lower16:RIO_OUT
    movt r8, #:upper16:RIO_OUT
    str r11, [r8]
    ROW_ADDR_STAGE_DELAY
.ifdef USE_FULL_STATE32_RIO_WORDS
    ROW_RGB_OUT
.else
.ifdef USE_FULL_STATE32_RIO_WORDS
    ROW_RGB_OUT
.else
.ifdef USE_DIRECT_RIO_WORDS
    ROW_DIRECT_OUT
.else
    LOAD_RGB_SETCLR_PTRS
    ROW_RGB_SETCLR
.endif
.endif
.endif
    adds r4, #1
    subs r6, #1
    bne .Ldma_dual_first_slab_loop\@

    DMA_WAIT_STATE32_CHUNK
    movw r12, #:lower16:DMA_CHUNK_ALT_DATA_BASE
    movt r12, #:upper16:DMA_CHUNK_ALT_DATA_BASE
    movw r0, #:lower16:STATUS_ADDR
    movt r0, #:upper16:STATUS_ADDR
    movw r1, #:lower16:STATUS_DMA_CHUNK_SHIFT
    movt r1, #:upper16:STATUS_DMA_CHUNK_SHIFT
    str r1, [r0]
    movs r6, #DMA_CHUNK_RECORDS
.Ldma_dual_second_slab_loop\@:
.ifdef USE_STATE32_ROW_MAJOR_RECORDS
    SET_ROWMAJOR_ADDR_DWELL_FROM_INDEX r4
.else
    mov r9, r4
    and r9, r9, #31
    mov r7, r4
    lsrs r7, r7, #5
    movs r0, #PLANE_COUNT
    subs r7, r0, r7
.endif
    movw r3, #:lower16:local_row_addr_masks
    movt r3, #:upper16:local_row_addr_masks
    ldr.w r11, [r3, r9, lsl #2]
    ORR_OE_BITS r11
    movw r8, #:lower16:RIO_OUT
    movt r8, #:upper16:RIO_OUT
    str r11, [r8]
    ROW_ADDR_STAGE_DELAY
.ifdef USE_FULL_STATE32_RIO_WORDS
    ROW_RGB_OUT
.else
.ifdef USE_DIRECT_RIO_WORDS
    ROW_DIRECT_OUT
.else
    LOAD_RGB_SETCLR_PTRS
    ROW_RGB_SETCLR
.endif
.endif
    adds r4, #1
    subs r6, #1
    bne .Ldma_dual_second_slab_loop\@

    cmp r4, #(32 * PLANE_COUNT)
    blo .Ldma_dual_pair_loop\@
    movw r0, #:lower16:FRAME_COUNTER
    movt r0, #:upper16:FRAME_COUNTER
    ldr r1, [r0]
    adds r1, #1
    str r1, [r0]
    b .Ldma_dual_frame_loop\@
.endm

.macro STATE32_DMA_DUALPAIR_FAST_CHUNK_STREAM_LOOP
    movw r8, #:lower16:RIO_OUT
    movt r8, #:upper16:RIO_OUT
    LOAD_CLK_PTRS
.Ldma_dual_fast_frame_loop\@:
    movs r4, #0
.Ldma_dual_fast_pair_loop\@:
    movw r10, #:lower16:DMA_CHUNK_DATA_BASE
    movt r10, #:upper16:DMA_CHUNK_DATA_BASE
    cmp r4, #0
    bne .Ldma_dual_fast_start_first\@
    DMA_START_STATE32_CHUNK_DEST_R10
    b .Ldma_dual_first_started\@
.Ldma_dual_fast_start_first\@:
    DMA_START_STATE32_CHUNK_DEST_R10_FAST
.Ldma_dual_first_started\@:
    adds r4, #DMA_CHUNK_RECORDS
    movw r10, #:lower16:DMA_CHUNK_ALT_DATA_BASE
    movt r10, #:upper16:DMA_CHUNK_ALT_DATA_BASE
    cmp r4, #DMA_CHUNK_RECORDS
    bne .Ldma_dual_fast_start_second\@
    DMA_START_STATE32_CHUNK_DEST_R10
    b .Ldma_dual_second_started\@
.Ldma_dual_fast_start_second\@:
    DMA_START_STATE32_CHUNK_DEST_R10_FAST
.Ldma_dual_second_started\@:
    subs r4, #DMA_CHUNK_RECORDS

    DMA_WAIT_STATE32_CHUNK
    movw r12, #:lower16:DMA_CHUNK_DATA_BASE
    movt r12, #:upper16:DMA_CHUNK_DATA_BASE
    movw r0, #:lower16:STATUS_ADDR
    movt r0, #:upper16:STATUS_ADDR
    movw r1, #:lower16:STATUS_DMA_CHUNK_SHIFT
    movt r1, #:upper16:STATUS_DMA_CHUNK_SHIFT
    str r1, [r0]
    movs r6, #DMA_CHUNK_RECORDS
.Ldma_dual_fast_first_slab_loop\@:
.ifdef USE_STATE32_ROW_MAJOR_RECORDS
    SET_ROWMAJOR_ADDR_DWELL_FROM_INDEX r4
.else
    mov r9, r4
    and r9, r9, #31
    mov r7, r4
    lsrs r7, r7, #5
    movs r0, #PLANE_COUNT
    subs r7, r0, r7
.endif
    movw r3, #:lower16:local_row_addr_masks
    movt r3, #:upper16:local_row_addr_masks
    ldr.w r11, [r3, r9, lsl #2]
    ORR_OE_BITS r11
    movw r8, #:lower16:RIO_OUT
    movt r8, #:upper16:RIO_OUT
    str r11, [r8]
    ROW_ADDR_STAGE_DELAY
.ifdef USE_FULL_STATE32_RIO_WORDS
    ROW_RGB_OUT
.else
.ifdef USE_DIRECT_RIO_WORDS
    ROW_DIRECT_OUT
.else
    LOAD_RGB_SETCLR_PTRS
    ROW_RGB_SETCLR
.endif
.endif
    adds r4, #1
    subs r6, #1
    bne .Ldma_dual_fast_first_slab_loop\@

    DMA_WAIT_STATE32_CHUNK
    movw r12, #:lower16:DMA_CHUNK_ALT_DATA_BASE
    movt r12, #:upper16:DMA_CHUNK_ALT_DATA_BASE
    movw r0, #:lower16:STATUS_ADDR
    movt r0, #:upper16:STATUS_ADDR
    movw r1, #:lower16:STATUS_DMA_CHUNK_SHIFT
    movt r1, #:upper16:STATUS_DMA_CHUNK_SHIFT
    str r1, [r0]
    movs r6, #DMA_CHUNK_RECORDS
.Ldma_dual_fast_second_slab_loop\@:
.ifdef USE_STATE32_ROW_MAJOR_RECORDS
    SET_ROWMAJOR_ADDR_DWELL_FROM_INDEX r4
.else
    mov r9, r4
    and r9, r9, #31
    mov r7, r4
    lsrs r7, r7, #5
    movs r0, #PLANE_COUNT
    subs r7, r0, r7
.endif
    movw r3, #:lower16:local_row_addr_masks
    movt r3, #:upper16:local_row_addr_masks
    ldr.w r11, [r3, r9, lsl #2]
    ORR_OE_BITS r11
    movw r8, #:lower16:RIO_OUT
    movt r8, #:upper16:RIO_OUT
    str r11, [r8]
    ROW_ADDR_STAGE_DELAY
.ifdef USE_FULL_STATE32_RIO_WORDS
    ROW_RGB_OUT
.else
.ifdef USE_DIRECT_RIO_WORDS
    ROW_DIRECT_OUT
.else
    LOAD_RGB_SETCLR_PTRS
    ROW_RGB_SETCLR
.endif
.endif
    adds r4, #1
    subs r6, #1
    bne .Ldma_dual_fast_second_slab_loop\@

    cmp r4, #(32 * PLANE_COUNT)
    blo .Ldma_dual_fast_pair_loop\@
    movw r0, #:lower16:FRAME_COUNTER
    movt r0, #:upper16:FRAME_COUNTER
    ldr r1, [r0]
    adds r1, #1
    str r1, [r0]
    b .Ldma_dual_fast_frame_loop\@
.endm

.macro STATE32_DMA_PIPELINE4_CHUNK_STREAM_LOOP
    movw r8, #:lower16:RIO_OUT
    movt r8, #:upper16:RIO_OUT
    LOAD_CLK_PTRS
.Ldma_pipe_frame_loop\@:
    movs r4, #0
    DMA_PIPE_LOAD_SLOT_BASE r10
    DMA_START_STATE32_CHUNK_DEST_R10
.if DMA_ROUND_ROBIN_CHANNELS > 1
    movs r4, #DMA_CHUNK_RECORDS
    DMA_PIPE_LOAD_SLOT_BASE r10
    DMA_START_STATE32_CHUNK_DEST_R10
.endif
.if DMA_ROUND_ROBIN_CHANNELS >= 4
    movs r4, #(2 * DMA_CHUNK_RECORDS)
    DMA_PIPE_LOAD_SLOT_BASE r10
    DMA_START_STATE32_CHUNK_DEST_R10
    movs r4, #(3 * DMA_CHUNK_RECORDS)
    DMA_PIPE_LOAD_SLOT_BASE r10
    DMA_START_STATE32_CHUNK_DEST_R10
.endif
.if DMA_ROUND_ROBIN_CHANNELS >= 6
    movs r4, #(4 * DMA_CHUNK_RECORDS)
    DMA_PIPE_LOAD_SLOT_BASE r10
    DMA_START_STATE32_CHUNK_DEST_R10
    movs r4, #(5 * DMA_CHUNK_RECORDS)
    DMA_PIPE_LOAD_SLOT_BASE r10
    DMA_START_STATE32_CHUNK_DEST_R10
.endif
    movs r4, #0
.Ldma_pipe_chunk_loop\@:
    DMA_WAIT_STATE32_CHUNK

    mov r11, r4
.if DMA_ROUND_ROBIN_CHANNELS == 1
    adds r4, #DMA_CHUNK_RECORDS
.elseif DMA_ROUND_ROBIN_CHANNELS == 2
    adds r4, #(2 * DMA_CHUNK_RECORDS)
.elseif DMA_ROUND_ROBIN_CHANNELS == 4
    adds r4, #(4 * DMA_CHUNK_RECORDS)
.elseif DMA_ROUND_ROBIN_CHANNELS == 6
    adds r4, #(6 * DMA_CHUNK_RECORDS)
.else
.error "STATE32_DMA_PIPELINE4_CHUNK_STREAM_LOOP currently expects DMA_ROUND_ROBIN_CHANNELS=1, 2, 4, or 6"
.endif
    cmp r4, #(32 * PLANE_COUNT)
    bhs .Ldma_pipe_no_prefetch\@
    DMA_PIPE_LOAD_SLOT_BASE r10
    DMA_START_STATE32_CHUNK_DEST_R10_FAST
    b .Ldma_pipe_prefetch_done\@
.Ldma_pipe_no_prefetch\@:
.ifdef USE_STATE32_DMA_PIPELINE_WRAP_PREFETCH
    subs r4, #(32 * PLANE_COUNT)
    DMA_PIPE_LOAD_SLOT_BASE r10
    DMA_START_STATE32_CHUNK_DEST_R10_FAST
.endif
.Ldma_pipe_prefetch_done\@:
    mov r4, r11

    DMA_PIPE_LOAD_SLOT_BASE r12
    movw r0, #:lower16:STATUS_ADDR
    movt r0, #:upper16:STATUS_ADDR
    movw r1, #:lower16:STATUS_DMA_CHUNK_SHIFT
    movt r1, #:upper16:STATUS_DMA_CHUNK_SHIFT
    str r1, [r0]
    movs r6, #DMA_CHUNK_RECORDS
.Ldma_pipe_slab_loop\@:
.ifdef USE_STATE32_ROW_MAJOR_RECORDS
    SET_ROWMAJOR_ADDR_DWELL_FROM_INDEX r4
.else
    mov r9, r4
    and r9, r9, #31
    mov r7, r4
    lsrs r7, r7, #5
    movs r0, #PLANE_COUNT
    subs r7, r0, r7
.endif
    movw r3, #:lower16:local_row_addr_masks
    movt r3, #:upper16:local_row_addr_masks
    ldr.w r11, [r3, r9, lsl #2]
    ORR_OE_BITS r11
    movw r8, #:lower16:RIO_OUT
    movt r8, #:upper16:RIO_OUT
    str r11, [r8]
    ROW_ADDR_STAGE_DELAY
.ifdef USE_FULL_STATE32_RIO_WORDS
    ROW_RGB_OUT
.else
.ifdef USE_DIRECT_RIO_WORDS
    ROW_DIRECT_OUT
.else
    LOAD_RGB_SETCLR_PTRS
    ROW_RGB_SETCLR
.endif
.endif
    adds r4, #1
    subs r6, #1
    bne .Ldma_pipe_slab_loop\@

    cmp r4, #(32 * PLANE_COUNT)
    blo .Ldma_pipe_chunk_loop\@
    movw r0, #:lower16:FRAME_COUNTER
    movt r0, #:upper16:FRAME_COUNTER
    ldr r1, [r0]
    adds r1, #1
    str r1, [r0]
.ifdef USE_STATE32_DMA_PIPELINE_WRAP_PREFETCH
    movs r4, #0
    b .Ldma_pipe_chunk_loop\@
.else
    b .Ldma_pipe_frame_loop\@
.endif
.endm

.macro STATE32_STATIC_CHUNK_SCAN_LOOP
    movw r8, #:lower16:RIO_OUT
    movt r8, #:upper16:RIO_OUT
    LOAD_CLK_PTRS
.Lstatic_chunk_frame_loop\@:
    movs r4, #0
.Lstatic_chunk_loop\@:
    movw r12, #:lower16:DMA_CHUNK_DATA_BASE
    movt r12, #:upper16:DMA_CHUNK_DATA_BASE
    movw r0, #:lower16:STATUS_ADDR
    movt r0, #:upper16:STATUS_ADDR
    movw r1, #:lower16:STATUS_DMA_CHUNK_SHIFT
    movt r1, #:upper16:STATUS_DMA_CHUNK_SHIFT
    str r1, [r0]
    movs r6, #DMA_CHUNK_RECORDS
.Lstatic_chunk_slab_loop\@:
.ifdef USE_STATE32_ROW_MAJOR_RECORDS
    SET_ROWMAJOR_ADDR_DWELL_FROM_INDEX r4
.else
    mov r9, r4
    and r9, r9, #31
    mov r7, r4
    lsrs r7, r7, #5
    movs r0, #PLANE_COUNT
    subs r7, r0, r7
.endif
    movw r3, #:lower16:local_row_addr_masks
    movt r3, #:upper16:local_row_addr_masks
    ldr.w r11, [r3, r9, lsl #2]
    ORR_OE_BITS r11
    movw r8, #:lower16:RIO_OUT
    movt r8, #:upper16:RIO_OUT
    str r11, [r8]
    ROW_ADDR_STAGE_DELAY
.ifdef USE_DIRECT_RIO_WORDS
    ROW_DIRECT_OUT
.else
    LOAD_RGB_SETCLR_PTRS
    ROW_RGB_SETCLR
.endif
    adds r4, #1
    subs r6, #1
    bne .Lstatic_chunk_slab_loop\@
    cmp r4, #(32 * PLANE_COUNT)
    blo .Lstatic_chunk_loop\@
    movw r0, #:lower16:FRAME_COUNTER
    movt r0, #:upper16:FRAME_COUNTER
    ldr r1, [r0]
    adds r1, #1
    str r1, [r0]
    b .Lstatic_chunk_frame_loop\@
.endm

.macro STATE32_STATIC_SCAN_DMA_CONTEND_LOOP
    movw r8, #:lower16:RIO_OUT
    movt r8, #:upper16:RIO_OUT
    LOAD_CLK_PTRS
    movs r4, #0
    movw r10, #:lower16:DMA_CHUNK_ALT_DATA_BASE
    movt r10, #:upper16:DMA_CHUNK_ALT_DATA_BASE
    DMA_START_STATE32_CHUNK_DEST_R10
    DMA_WAIT_STATE32_CHUNK
.Lstatic_dma_frame_loop\@:
    movs r4, #0
.Lstatic_dma_chunk_loop\@:
    movw r10, #:lower16:DMA_CHUNK_ALT_DATA_BASE
    movt r10, #:upper16:DMA_CHUNK_ALT_DATA_BASE
    DMA_START_STATE32_CHUNK_DEST_R10_FAST
    movw r12, #:lower16:DMA_CHUNK_DATA_BASE
    movt r12, #:upper16:DMA_CHUNK_DATA_BASE
    movw r0, #:lower16:STATUS_ADDR
    movt r0, #:upper16:STATUS_ADDR
    movw r1, #:lower16:STATUS_DMA_CHUNK_SHIFT
    movt r1, #:upper16:STATUS_DMA_CHUNK_SHIFT
    str r1, [r0]
    movs r6, #DMA_CHUNK_RECORDS
.Lstatic_dma_chunk_slab_loop\@:
.ifdef USE_STATE32_ROW_MAJOR_RECORDS
    SET_ROWMAJOR_ADDR_DWELL_FROM_INDEX r4
.else
    mov r9, r4
    and r9, r9, #31
    mov r7, r4
    lsrs r7, r7, #5
    movs r0, #PLANE_COUNT
    subs r7, r0, r7
.endif
    movw r3, #:lower16:local_row_addr_masks
    movt r3, #:upper16:local_row_addr_masks
    ldr.w r11, [r3, r9, lsl #2]
    ORR_OE_BITS r11
    movw r8, #:lower16:RIO_OUT
    movt r8, #:upper16:RIO_OUT
    str r11, [r8]
    ROW_ADDR_STAGE_DELAY
.ifdef USE_DIRECT_RIO_WORDS
    ROW_DIRECT_OUT
.else
    LOAD_RGB_SETCLR_PTRS
    ROW_RGB_SETCLR
.endif
    adds r4, #1
    subs r6, #1
    bne .Lstatic_dma_chunk_slab_loop\@
    DMA_WAIT_STATE32_CHUNK
    cmp r4, #(32 * PLANE_COUNT)
    blo .Lstatic_dma_chunk_loop\@
    movw r0, #:lower16:FRAME_COUNTER
    movt r0, #:upper16:FRAME_COUNTER
    ldr r1, [r0]
    adds r1, #1
    str r1, [r0]
    b .Lstatic_dma_frame_loop\@
.endm

.macro STATE32_DMA_ONLY_CHUNK_LOOP
    LOAD_CLK_PTRS
.Ldma_only_frame_loop\@:
    movs r4, #0
.Ldma_only_chunk_loop\@:
    movw r10, #:lower16:DMA_CHUNK_DATA_BASE
    movt r10, #:upper16:DMA_CHUNK_DATA_BASE
    DMA_START_STATE32_CHUNK_DEST_R10_FAST
    DMA_WAIT_STATE32_CHUNK
    adds r4, #DMA_CHUNK_RECORDS
    cmp r4, #(32 * PLANE_COUNT)
    blo .Ldma_only_chunk_loop\@
    movw r0, #:lower16:FRAME_COUNTER
    movt r0, #:upper16:FRAME_COUNTER
    ldr r1, [r0]
    adds r1, #1
    str r1, [r0]
    b .Ldma_only_frame_loop\@
.endm

.macro PWM6_BITS_INDEX_COMPONENT byte_reg, bit
    tst \byte_reg, r6
    it ne
    orrne r11, r11, #\bit
.endm

.macro EXPAND_PWM6_BITS_GROUP_TO_DSRAM
    ldrb r0, [r12]
    adds r12, #1
    ldrb r1, [r12]
    adds r12, #1
    ldrb r2, [r12]
    adds r12, #1
    ldrb r3, [r12]
    adds r12, #1
    ldrb r10, [r12]
    adds r12, #1
    ldrb r9, [r12]
    adds r12, #1
    movs r6, #1
    movs r5, #8
    movw lr, #:lower16:local_rgb6_mask_table
    movt lr, #:upper16:local_rgb6_mask_table
.Lpwm6bits_pixel_loop\@:
    movs r11, #0
    PWM6_BITS_INDEX_COMPONENT r0, 1
    PWM6_BITS_INDEX_COMPONENT r1, 2
    PWM6_BITS_INDEX_COMPONENT r2, 4
    PWM6_BITS_INDEX_COMPONENT r3, 8
    PWM6_BITS_INDEX_COMPONENT r10, 16
    PWM6_BITS_INDEX_COMPONENT r9, 32
    ldr.w r11, [lr, r11, lsl #2]
    str r11, [r8], #4
    lsls r6, r6, #1
    subs r5, #1
    bne .Lpwm6bits_pixel_loop\@
.endm

.macro EXPAND_PWM6_BITS_ROWPLANE_TO_DSRAM
    movw r8, #:lower16:LOCAL_DSRAM
    movt r8, #:upper16:LOCAL_DSRAM
    .rept 8
    EXPAND_PWM6_BITS_GROUP_TO_DSRAM
    .endr
.endm

.macro PWM6_BITS_FRAME_LOOP
    movw r0, #:lower16:STATUS_ADDR
    movt r0, #:upper16:STATUS_ADDR
    movw r1, #:lower16:STATUS_PWM6BITS_ROW
    movt r1, #:upper16:STATUS_PWM6BITS_ROW
    str r1, [r0]
    movs r4, #0
.Lpwm6bits_row_loop\@:
    movs r7, #PLANE_COUNT
.Lpwm6bits_plane_loop\@:
    movw r12, #:lower16:SHARED_PWM6_BITS_BASE
    movt r12, #:upper16:SHARED_PWM6_BITS_BASE
    add.w r12, r12, r4, lsl #8
    add.w r12, r12, r4, lsl #5
    movs r6, #PLANE_COUNT
    subs r6, r6, r7
    add.w r12, r12, r6, lsl #5
    add.w r12, r12, r6, lsl #4
    movw r0, #:lower16:STATUS_ADDR
    movt r0, #:upper16:STATUS_ADDR
    movw r1, #:lower16:STATUS_PWM6BITS_COPY
    movt r1, #:upper16:STATUS_PWM6BITS_COPY
    str r1, [r0]
    EXPAND_PWM6_BITS_ROWPLANE_TO_DSRAM
    movw r3, #:lower16:local_row_addr_masks
    movt r3, #:upper16:local_row_addr_masks
    ldr.w r11, [r3, r4, lsl #2]
    ORR_OE_BITS r11
    movw r8, #:lower16:RIO_OUT
    movt r8, #:upper16:RIO_OUT
    str r11, [r8]
    ROW_ADDR_STAGE_DELAY
    LOAD_RGB_SETCLR_PTRS
    movw r12, #:lower16:LOCAL_DSRAM
    movt r12, #:upper16:LOCAL_DSRAM
    movw r0, #:lower16:STATUS_ADDR
    movt r0, #:upper16:STATUS_ADDR
    movw r1, #:lower16:STATUS_PWM6BITS_SHIFT
    movt r1, #:upper16:STATUS_PWM6BITS_SHIFT
    str r1, [r0]
    ROW_RGB_SETCLR
    subs r7, #1
    bne .Lpwm6bits_plane_loop\@
    adds r4, #1
    cmp r4, #32
    blo .Lpwm6bits_row_loop\@
.endm

.macro FILL_CONST_ROW_TO_DSRAM bits
    movw r8, #:lower16:LOCAL_DSRAM
    movt r8, #:upper16:LOCAL_DSRAM
    movw r2, #:lower16:\bits
    movt r2, #:upper16:\bits
    .rept 64
    str r2, [r8], #4
    .endr
.endm

.macro RGB888_ROW_MAJOR_CONST_LOOP
    movw r3, #:lower16:local_row_addr_masks
    movt r3, #:upper16:local_row_addr_masks
    movs r4, #0
.Lrgb888_const_row_loop\@:
    movw r8, #:lower16:RIO_OUT
    movt r8, #:upper16:RIO_OUT
    ldr.w r11, [r3, r4, lsl #2]
    ORR_OE_BITS r11
    str r11, [r8]
    ROW_ADDR_STAGE_DELAY
    movs r7, #PLANE_COUNT
.Lrgb888_const_plane_loop\@:
    .ifndef RGB888_CONST_BITS
    .equ RGB888_CONST_BITS, (PIN_R1 | PIN_R2)
    .endif
    FILL_CONST_ROW_TO_DSRAM RGB888_CONST_BITS
    LOAD_RGB_SETCLR_PTRS
    movw r12, #:lower16:LOCAL_DSRAM
    movt r12, #:upper16:LOCAL_DSRAM
    ROW_RGB_SETCLR
    subs r7, #1
    bne .Lrgb888_const_plane_loop\@
    adds r4, #1
    cmp r4, #32
    blo .Lrgb888_const_row_loop\@
.endm

.section .text
.globl _entry_vec
    .word 0x10003ffc
    .word _entry

.align 2
.thumb_func
.globl _entry
_entry:
.ifdef RUN_FROM_SHARED_TEXT
    b local_entry
.else
    ldr r0, =local_image_start
    ldr r1, =LOCAL_ISRAM
    ldr r2, =local_image_end
1:
    cmp r0, r2
    bhs 2f
    ldr r3, [r0], #4
    str r3, [r1], #4
    b 1b
2:
    dsb
    isb
    ldr r0, =STATUS_ADDR
    ldr r1, =COPY_MAGIC
    str r1, [r0]
    ldr r0, =(LOCAL_ISRAM + 1)
    bx r0
    .ltorg
.endif

.align 2
local_image_start:
.thumb_func
local_entry:
.ifdef USE_DSRAM_CACHE
    cpsid i
.endif
    movw r0, #:lower16:STATUS_ADDR
    movt r0, #:upper16:STATUS_ADDR
    ldr r1, =STATUS_MAGIC
    str r1, [r0]
.ifdef LEGACY_STATUS_ADDR
    movw r0, #:lower16:LEGACY_STATUS_ADDR
    movt r0, #:upper16:LEGACY_STATUS_ADDR
    str r1, [r0]
.endif
    b local_real_entry
    .ltorg

.align 2
local_real_entry:
    bl local_configure_pins

    ldr r0, =RIO_SET
    ldr r1, =ALL_PINS
    str r1, [r0, #4]

    movw r0, #:lower16:FRAME_COUNTER
    movt r0, #:upper16:FRAME_COUNTER
    movs r1, #0
    str r1, [r0]

    movw r0, #:lower16:CTRL_ADDR
    movt r0, #:upper16:CTRL_ADDR
    movs r1, #0
    str r1, [r0]

    b 0f
    .ltorg

0:
local_wait_start:
    movw r0, #:lower16:CTRL_ADDR
    movt r0, #:upper16:CTRL_ADDR
    ldr r1, [r0]
    ldr r2, =START_MAGIC
    cmp r1, r2
    bne local_wait_start
    movw r0, #:lower16:STATUS_ADDR
    movt r0, #:upper16:STATUS_ADDR
    movw r1, #:lower16:STATUS_AFTER_START
    movt r1, #:upper16:STATUS_AFTER_START
    str r1, [r0]

.ifdef USE_DSRAM_CACHE
    movw r0, #:lower16:LOCAL_DSRAM
    movt r0, #:upper16:LOCAL_DSRAM
    msr msp, r0
    isb

.ifndef RECOPY_EACH_PLANE
.ifdef USE_STATE32_PREEXPANDED_ROW_MAJOR
.else
.ifdef USE_STATE32_SLAB_STREAM
.else
.ifdef USE_PWM6_BITS_FRAME
.else
.ifdef USE_ROW_REFILL_CACHE
.else
.ifdef USE_ROW_TAIL_REFILL_CACHE
.else
.ifdef USE_RGB888_EXPAND_CACHE
    EXPAND_SHARED_RGB888_TO_DSRAM
.else
.ifdef USE_RGB444_EXPAND_CACHE
    EXPAND_SHARED_RGB444_TO_DSRAM
.else
.ifdef USE_RGB333_EXPAND_CACHE
    EXPAND_SHARED_RGB333_TO_DSRAM
.else
.ifdef USE_RGB6_EXPAND_CACHE
    EXPAND_SHARED_RGB6_TO_DSRAM
.else
    COPY_SHARED_STATE32_TO_DSRAM
.endif
.endif
.endif
.endif
.endif
.endif
.endif
.endif
.endif
.endif
.endif

    ldr r8, =RIO_OUT
    LOAD_CLK_PTRS
    b 0f
    .ltorg

0:
local_frame_loop:
.ifdef USE_RGB888_ROW_MAJOR_EXPAND_CACHE
    RGB888_ROW_MAJOR_LOOP
    movw r0, #:lower16:FRAME_COUNTER
    movt r0, #:upper16:FRAME_COUNTER
    ldr r1, [r0]
    adds r1, #1
    str r1, [r0]
    b.w local_frame_loop
.endif

.ifdef USE_RGB888_ROW_MAJOR_CONST
    RGB888_ROW_MAJOR_CONST_LOOP
    movw r0, #:lower16:FRAME_COUNTER
    movt r0, #:upper16:FRAME_COUNTER
    ldr r1, [r0]
    adds r1, #1
    str r1, [r0]
    b.w local_frame_loop
.endif

.ifdef USE_RGB111_ROW_MAJOR_EXPAND_CACHE
    RGB111_ROW_MAJOR_LOOP
    movw r0, #:lower16:FRAME_COUNTER
    movt r0, #:upper16:FRAME_COUNTER
    ldr r1, [r0]
    adds r1, #1
    str r1, [r0]
    b.w local_frame_loop
.endif

.ifdef USE_STATE32_PREEXPANDED_ROW_MAJOR
    STATE32_PREEXPANDED_ROW_MAJOR_LOOP
    movw r0, #:lower16:FRAME_COUNTER
    movt r0, #:upper16:FRAME_COUNTER
    ldr r1, [r0]
    adds r1, #1
    str r1, [r0]
    b.w local_frame_loop
.endif

.ifdef USE_PWM6_BITS_FRAME
    PWM6_BITS_FRAME_LOOP
    movw r0, #:lower16:FRAME_COUNTER
    movt r0, #:upper16:FRAME_COUNTER
    ldr r1, [r0]
    adds r1, #1
    str r1, [r0]
    b.w local_frame_loop
.endif

.ifdef USE_STATE32_SLAB_STREAM
    STATE32_SLAB_STREAM_LOOP
.endif

.ifdef USE_STATE32_SLAB_PLANE_STREAM
    STATE32_SLAB_PLANE_STREAM_LOOP
.endif

.ifdef USE_STATE32_CHUNK_STREAM
    STATE32_CHUNK_STREAM_LOOP
.endif

.ifdef USE_STATE32_DMA_CHUNK_STREAM
    STATE32_DMA_CHUNK_STREAM_LOOP
.endif

.ifdef USE_STATE32_DMA_ASYNC_CHUNK_STREAM
    STATE32_DMA_ASYNC_CHUNK_STREAM_LOOP
.endif

.ifdef USE_STATE32_DMA_DUALPAIR_CHUNK_STREAM
    STATE32_DMA_DUALPAIR_CHUNK_STREAM_LOOP
.endif

.ifdef USE_STATE32_DMA_DUALPAIR_FAST_CHUNK_STREAM
    STATE32_DMA_DUALPAIR_FAST_CHUNK_STREAM_LOOP
.endif

.ifdef USE_STATE32_DMA_PIPELINE4_CHUNK_STREAM
    STATE32_DMA_PIPELINE4_CHUNK_STREAM_LOOP
.endif

.ifdef USE_STATE32_STATIC_CHUNK_SCAN
    STATE32_STATIC_CHUNK_SCAN_LOOP
.endif

.ifdef USE_STATE32_STATIC_SCAN_DMA_CONTEND
    STATE32_STATIC_SCAN_DMA_CONTEND_LOOP
.endif

.ifdef USE_STATE32_DMA_ONLY_CHUNK_LOOP
    STATE32_DMA_ONLY_CHUNK_LOOP
.endif

.ifdef USE_PLANE_SRC_PTR
    movw r0, #:lower16:SHARED_STATE32_BASE
    movt r0, #:upper16:SHARED_STATE32_BASE
    movw r1, #:lower16:ROW_CACHE_SRC
    movt r1, #:upper16:ROW_CACHE_SRC
    str r0, [r1]
.endif
.ifdef USE_RECOPY_EACH_FRAME
.ifdef USE_RGB888_EXPAND_CACHE
    EXPAND_SHARED_RGB888_TO_DSRAM
.else
.ifdef USE_RGB444_EXPAND_CACHE
    EXPAND_SHARED_RGB444_TO_DSRAM
.else
.ifdef USE_RGB333_EXPAND_CACHE
    EXPAND_SHARED_RGB333_TO_DSRAM
.else
.ifdef USE_RGB6_EXPAND_CACHE
    EXPAND_SHARED_RGB6_TO_DSRAM
.else
    COPY_SHARED_STATE32_TO_DSRAM
.endif
.endif
.endif
.endif
    movw r8, #:lower16:RIO_OUT
    movt r8, #:upper16:RIO_OUT
    LOAD_CLK_PTRS
.endif
    movs r7, #PLANE_COUNT
local_plane_loop:
.ifdef RECOPY_EACH_PLANE
.ifdef USE_RGB111_EXPAND_CACHE
    EXPAND_SHARED_RGB111_TO_DSRAM
.else
.ifdef USE_RGB888_EXPAND_CACHE
    EXPAND_SHARED_RGB888_TO_DSRAM
.else
.ifdef USE_RGB444_EXPAND_CACHE
    EXPAND_SHARED_RGB444_TO_DSRAM
.else
.ifdef USE_RGB333_EXPAND_CACHE
    EXPAND_SHARED_RGB333_TO_DSRAM
.else
.ifdef USE_RGB6_EXPAND_CACHE
    EXPAND_SHARED_RGB6_TO_DSRAM
.else
    COPY_SHARED_STATE32_TO_DSRAM
.endif
.endif
.endif
.endif
.endif
.ifdef POST_PLANE_COPY_NOPS
    .rept POST_PLANE_COPY_NOPS
    nop
    .endr
.endif
    movw r8, #:lower16:RIO_OUT
    movt r8, #:upper16:RIO_OUT
    LOAD_CLK_PTRS
.ifdef USE_HALT_AFTER_PLANE_COPY
1:
    b 1b
.endif
.endif
    movw r12, #:lower16:STATE32_BASE
    movt r12, #:upper16:STATE32_BASE
.ifdef USE_ROW_TAIL_REFILL_CACHE
.ifdef USE_ROW_TAIL_REFILL_REGCOUNT
    ROW_TAIL_REFILL_REGCOUNT_LOOP
.else
    ROW_TAIL_REFILL_LOOP
.endif
.else
.ifdef USE_ROW_REFILL_CACHE
    ROW_REFILL_LOOP
.else
.ifdef USE_ROW_REGCOUNT_RGB_SETCLR
    movw r12, #:lower16:STATE32_BASE
    movt r12, #:upper16:STATE32_BASE
    ROW_REGCOUNT_RGB_SETCLR_LOOP
.else
.ifdef USE_ROW8_LOOP
    mov.w r10, #4
local_row8_loop:
    ROWS8
    subs.w r10, r10, #1
    bne.w local_row8_loop
.else
.ifdef USE_ROW_REGCOUNT_R7
    movw r0, #:lower16:ROW_CACHE_PLANE_COUNT
    movt r0, #:upper16:ROW_CACHE_PLANE_COUNT
    str r7, [r0]
    movs r7, #32
.ifdef USE_ROW_LOOP_ENTRY_PAD1
    nop
.endif
.ifdef USE_ROW_LOOP_ENTRY_PAD3
    .rept 3
    nop
    .endr
.endif
.ifdef USE_ROW_LOOP_ENTRY_PAD5
    .rept 5
    nop
    .endr
.endif
.ifdef USE_ROW_LOOP_ENTRY_PAD7
    .rept 7
    nop
    .endr
.endif
local_row_r7_loop:
    ROW
    subs r7, #1
    bne.w local_row_r7_loop
    movw r0, #:lower16:ROW_CACHE_PLANE_COUNT
    movt r0, #:upper16:ROW_CACHE_PLANE_COUNT
    ldr r7, [r0]
.else
.ifdef USE_ROW_LOOP
    mov.w r10, #32
local_row_loop:
    ROW
    subs.w r10, r10, #1
    bne.w local_row_loop
.else
.ifdef USE_R10_LOOP
    mov.w r10, #2
local_row16_loop:
    ROWS16
    subs.w r10, r10, #1
    bne.w local_row16_loop
.else
    movs r4, #2
local_row16_loop:
    push {r4, r7}
    ROWS16
    pop {r4, r7}
    subs r4, #1
    bne.w local_row16_loop
.endif
.endif
.endif
.endif
.endif
.endif
.endif

    subs r7, #1
    bne.w local_plane_loop

    movw r0, #:lower16:FRAME_COUNTER
    movt r0, #:upper16:FRAME_COUNTER
    ldr r1, [r0]
    adds r1, #1
    str r1, [r0]
    b.w local_frame_loop
    .ltorg

.thumb_func
local_configure_pins:
    push {r4-r7, lr}

.macro CONFIG_GPIO gpio, padctrl
    ldr r0, =IO_CTRL_BASE
    movs r5, #\gpio
    lsls r6, r5, #3
    add r0, r6
    movs r1, #FN_PROC_RIO
    str r1, [r0]
    ldr r0, =PAD_BASE
    lsls r6, r5, #2
    add r0, r6
    movs r1, #\padctrl
    str r1, [r0]
.endm

    CONFIG_GPIO GPIO_CLK, PAD_CTRL_CLK
    CONFIG_GPIO GPIO_LAT, PAD_CTRL_LAT
    CONFIG_GPIO GPIO_OE, PAD_CTRL_OE
    .if USE_LEGACY_OE_SYNC
    CONFIG_GPIO GPIO_OE_LEGACY, PAD_CTRL_OE
    .endif
    CONFIG_GPIO GPIO_A, PAD_CTRL_ADDR_A
    CONFIG_GPIO GPIO_B, PAD_CTRL_ADDR_B
    CONFIG_GPIO GPIO_C, PAD_CTRL_ADDR_C
    CONFIG_GPIO GPIO_D, PAD_CTRL_ADDR_D
    CONFIG_GPIO GPIO_E, PAD_CTRL_ADDR_E
    CONFIG_GPIO GPIO_R1, PAD_CTRL_RGB
    CONFIG_GPIO GPIO_G1, PAD_CTRL_RGB
    CONFIG_GPIO GPIO_B1, PAD_CTRL_RGB
    CONFIG_GPIO GPIO_R2, PAD_CTRL_RGB
    CONFIG_GPIO GPIO_G2, PAD_CTRL_RGB
    CONFIG_GPIO GPIO_B2, PAD_CTRL_RGB
    .if USE_P1_RGB
    CONFIG_GPIO GPIO_P1_R1, PAD_CTRL_RGB
    CONFIG_GPIO GPIO_P1_G1, PAD_CTRL_RGB
    CONFIG_GPIO GPIO_P1_B1, PAD_CTRL_RGB
    CONFIG_GPIO GPIO_P1_R2, PAD_CTRL_RGB
    CONFIG_GPIO GPIO_P1_G2, PAD_CTRL_RGB
    CONFIG_GPIO GPIO_P1_B2, PAD_CTRL_RGB
    .endif

    pop {r4-r7, pc}
    .ltorg

.ifdef USE_RGB6_EXPAND_CACHE
.equ EMIT_ROW_ADDR_MASKS, 1
.endif
.ifdef USE_RGB888_EXPAND_CACHE
.equ EMIT_ROW_ADDR_MASKS, 1
.endif
.ifdef USE_RGB888_ROW_MAJOR_EXPAND_CACHE
.equ EMIT_ROW_ADDR_MASKS, 1
.endif
.ifdef USE_RGB111_ROW_MAJOR_EXPAND_CACHE
.equ EMIT_ROW_ADDR_MASKS, 1
.endif
.ifdef USE_STATE32_PREEXPANDED_ROW_MAJOR
.equ EMIT_ROW_ADDR_MASKS, 1
.endif
.ifdef USE_STATE32_SLAB_STREAM
.equ EMIT_ROW_ADDR_MASKS, 1
.endif
.ifdef USE_STATE32_SLAB_PLANE_STREAM
.equ EMIT_ROW_ADDR_MASKS, 1
.endif
.ifdef USE_STATE32_CHUNK_STREAM
.equ EMIT_ROW_ADDR_MASKS, 1
.endif
.ifdef USE_STATE32_DMA_CHUNK_STREAM
.equ EMIT_ROW_ADDR_MASKS, 1
.endif
.ifdef USE_STATE32_DMA_ASYNC_CHUNK_STREAM
.equ EMIT_ROW_ADDR_MASKS, 1
.endif
.ifdef USE_STATE32_DMA_DUALPAIR_CHUNK_STREAM
.equ EMIT_ROW_ADDR_MASKS, 1
.endif
.ifdef USE_STATE32_DMA_DUALPAIR_FAST_CHUNK_STREAM
.equ EMIT_ROW_ADDR_MASKS, 1
.endif
.ifdef USE_STATE32_DMA_PIPELINE4_CHUNK_STREAM
.equ EMIT_ROW_ADDR_MASKS, 1
.endif
.ifdef USE_STATE32_STATIC_CHUNK_SCAN
.equ EMIT_ROW_ADDR_MASKS, 1
.endif
.ifdef USE_STATE32_STATIC_SCAN_DMA_CONTEND
.equ EMIT_ROW_ADDR_MASKS, 1
.endif
.ifdef USE_STATE32_DMA_ONLY_CHUNK_LOOP
.equ EMIT_ROW_ADDR_MASKS, 1
.endif
.ifdef USE_PWM6_BITS_FRAME
.equ EMIT_ROW_ADDR_MASKS, 1
.endif
.ifdef USE_RGB888_ROW_MAJOR_CONST
.equ EMIT_ROW_ADDR_MASKS, 1
.endif
.ifdef USE_RGB333_EXPAND_CACHE
.equ EMIT_ROW_ADDR_MASKS, 1
.endif
.ifdef USE_ROW_REGCOUNT_RGB_SETCLR
.equ EMIT_ROW_ADDR_MASKS, 1
.endif

.ifdef EMIT_ROW_ADDR_MASKS
.align 2
local_row_addr_masks:
    .word 0
    .word PIN_A
    .word PIN_B
    .word (PIN_A | PIN_B)
    .word PIN_C
    .word (PIN_A | PIN_C)
    .word (PIN_B | PIN_C)
    .word (PIN_A | PIN_B | PIN_C)
    .word PIN_D
    .word (PIN_A | PIN_D)
    .word (PIN_B | PIN_D)
    .word (PIN_A | PIN_B | PIN_D)
    .word (PIN_C | PIN_D)
    .word (PIN_A | PIN_C | PIN_D)
    .word (PIN_B | PIN_C | PIN_D)
    .word (PIN_A | PIN_B | PIN_C | PIN_D)
    .word PIN_E
    .word (PIN_A | PIN_E)
    .word (PIN_B | PIN_E)
    .word (PIN_A | PIN_B | PIN_E)
    .word (PIN_C | PIN_E)
    .word (PIN_A | PIN_C | PIN_E)
    .word (PIN_B | PIN_C | PIN_E)
    .word (PIN_A | PIN_B | PIN_C | PIN_E)
    .word (PIN_D | PIN_E)
    .word (PIN_A | PIN_D | PIN_E)
    .word (PIN_B | PIN_D | PIN_E)
    .word (PIN_A | PIN_B | PIN_D | PIN_E)
    .word (PIN_C | PIN_D | PIN_E)
    .word (PIN_A | PIN_C | PIN_D | PIN_E)
    .word (PIN_B | PIN_C | PIN_D | PIN_E)
    .word (PIN_A | PIN_B | PIN_C | PIN_D | PIN_E)

.align 2
local_rgb6_mask_table:
.ifdef USE_RGB6_EXPAND_CACHE
.set rgb, 0
.rept 64
.word (((rgb >> 0) & 1) * PIN_R1) | (((rgb >> 1) & 1) * PIN_G1) | (((rgb >> 2) & 1) * PIN_B1) | (((rgb >> 3) & 1) * PIN_R2) | (((rgb >> 4) & 1) * PIN_G2) | (((rgb >> 5) & 1) * PIN_B2)
.set rgb, rgb + 1
.endr
.else
.ifdef USE_PWM6_BITS_FRAME
    .set rgb, 0
    .rept 64
    .word (((rgb >> 0) & 1) * PIN_R1) | (((rgb >> 1) & 1) * PIN_G1) | (((rgb >> 2) & 1) * PIN_B1) | (((rgb >> 3) & 1) * PIN_R2) | (((rgb >> 4) & 1) * PIN_G2) | (((rgb >> 5) & 1) * PIN_B2)
    .set rgb, rgb + 1
    .endr
.endif
.endif
.endif

.align 2
local_image_end:
@ END inlined from rp1_core1_sram_procrio_state32_isram_tailfast_unroll16_frame11_dwell28.s
@ END inline include rp1_core1_sram_procrio_state32_isram_tailfast_unroll16_frame11_dwell28.s
@ END inlined from rp1_core1_state32_regular_p0p1_chain2_profile.inc
@ END inline include rp1_core1_state32_regular_p0p1_chain2_profile.inc
@ END inlined from rp1_core1_state32_dmapipeline4x4_rr01_cols128_frame8_dwell8_regular_p0p1_chain2_oeoffshift_preclk1_unroll8_addr8_lat2.s
