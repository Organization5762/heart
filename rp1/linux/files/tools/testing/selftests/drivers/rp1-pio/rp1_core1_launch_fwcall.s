.cpu cortex-m3
.thumb
.syntax unified

/*
 * Core0 firmware-callback launch stub.
 *
 * The host temporarily points the RP1 firmware feature-dispatch callback at
 * this function, sends a direct shared-SRAM mailbox request, then restores the
 * original feature table.  The callback wakes core1 with SEV and returns
 * success to the firmware dispatcher.
 */

.equ LAUNCH_COUNT, 0x20007020

.section .text
.align 2
.thumb_func
.globl _entry
_entry:
    push {r1, r2}

    ldr r1, =LAUNCH_COUNT
    ldr r2, [r1]
    add r2, #1
    str r2, [r1]

    sev
    movs r0, #0

    pop {r1, r2}
    bx lr

.align 4
