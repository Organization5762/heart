.cpu cortex-m3
.thumb
.syntax unified

/*
 * One-shot core0 trampoline for the totem3 firmware vector table entry at
 * 0x2000012c.  The observed handler pointer after reboot is 0x20000b19.
 */

.equ HOOK_ADDR,   0x2000012c
.equ HOOK_ORIG,   0x20000b19
.equ HOOK_RETURN, 0x20000b19

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
