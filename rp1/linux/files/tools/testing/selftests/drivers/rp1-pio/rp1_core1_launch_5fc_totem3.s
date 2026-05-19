.cpu cortex-m3
.thumb
.syntax unified

/*
 * One-shot core0 trampoline for the RP1 firmware PIO_SM_RESTART handler shape
 * observed on totem3.  This is the same launch mechanism as launch_5fc, but it
 * restores the totem3 handler word before returning to the original code path.
 */

.equ HOOK_ADDR,   0x200005fc
.equ HOOK_ORIG,   0x46bd371c
.equ HOOK_RETURN, 0x200005fd

.section .text
.align 2
.thumb_func
.globl _entry
_entry:
    push {r0, r1, r6, r7}

    adr r6, count
    ldr r7, [r6]
    add r7, #1
    str r7, [r6]

    sev

    ldr r6, =HOOK_ADDR
    ldr r7, =HOOK_ORIG
    str r7, [r6]

    pop {r0, r1, r6, r7}
    ldr r6, =HOOK_RETURN
    bx r6

.align 4
count:
    .word 0
