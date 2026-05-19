/*
 * HUB75 GPIO defaults and derived pin masks for the RP1 core1 scanner.
 *
 * Wrappers may override any GPIO_* value before including the worker.  Keep the
 * active scan loops out of this file; it only defines the GPIO contract that the
 * scanner consumes.
 */

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
.equ HAVE_P1_RGB_PINS, 0
.if USE_P1_RGB
.ifndef GPIO_P1_R1
.error "USE_P1_RGB requires wrapper-defined GPIO_P1_R1"
.endif
.ifndef GPIO_P1_G1
.error "USE_P1_RGB requires wrapper-defined GPIO_P1_G1"
.endif
.ifndef GPIO_P1_B1
.error "USE_P1_RGB requires wrapper-defined GPIO_P1_B1"
.endif
.ifndef GPIO_P1_R2
.error "USE_P1_RGB requires wrapper-defined GPIO_P1_R2"
.endif
.ifndef GPIO_P1_G2
.error "USE_P1_RGB requires wrapper-defined GPIO_P1_G2"
.endif
.ifndef GPIO_P1_B2
.error "USE_P1_RGB requires wrapper-defined GPIO_P1_B2"
.endif
.ifdef GPIO_P1_R1
.ifdef GPIO_P1_G1
.ifdef GPIO_P1_B1
.ifdef GPIO_P1_R2
.ifdef GPIO_P1_G2
.ifdef GPIO_P1_B2
.equ HAVE_P1_RGB_PINS, 1
.endif
.endif
.endif
.endif
.endif
.endif
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
.equ RGB_P0_PINS,  (PIN_R1 | PIN_G1 | PIN_B1 | PIN_R2 | PIN_G2 | PIN_B2)
.if USE_P1_RGB && HAVE_P1_RGB_PINS
.equ PIN_P1_R1,    (1 << GPIO_P1_R1)
.equ PIN_P1_G1,    (1 << GPIO_P1_G1)
.equ PIN_P1_B1,    (1 << GPIO_P1_B1)
.equ PIN_P1_R2,    (1 << GPIO_P1_R2)
.equ PIN_P1_G2,    (1 << GPIO_P1_G2)
.equ PIN_P1_B2,    (1 << GPIO_P1_B2)
.equ RGB_P1_PINS,  (PIN_P1_R1 | PIN_P1_G1 | PIN_P1_B1 | PIN_P1_R2 | PIN_P1_G2 | PIN_P1_B2)
.if (RGB_P0_PINS & RGB_P1_PINS)
.error "USE_P1_RGB requires P1 GPIO pins not to alias P0 RGB pins"
.endif
.else
.equ RGB_P1_PINS,  0
.endif
.equ KEY_PINS,     (PIN_CLK | PIN_LAT | PIN_OE_ALL | PIN_A | PIN_B | PIN_C | PIN_D | PIN_E)
.equ ADDR_OE_PINS, (PIN_OE_ALL | PIN_A | PIN_B | PIN_C | PIN_D | PIN_E)
.if USE_P1_RGB
.equ RGB_PINS,     (RGB_P0_PINS | RGB_P1_PINS)
.else
.equ RGB_PINS,     RGB_P0_PINS
.endif
.equ ALL_PINS,     (KEY_PINS | RGB_PINS)
.equ RGB_CLK_PINS, (RGB_PINS | PIN_CLK)
