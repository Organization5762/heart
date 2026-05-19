.cpu cortex-m3
.thumb
.syntax unified

/*
 * Generic one-shot vector trampoline.  The host writes hook_addr, hook_orig and
 * hook_return into the data words before patching a firmware vector to _entry.
 */

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

    adr r6, hook_addr
    ldr r6, [r6]
    adr r7, hook_orig
    ldr r7, [r7]
    str r7, [r6]

    pop {r0, r1, r6, r7}
    adr r6, hook_return
    ldr r6, [r6]
    bx r6

.align 4
count:
    .word 0
hook_addr:
    .word 0
hook_orig:
    .word 0
hook_return:
    .word 0
