/*
 * Padding ahead of the kernel text. Never executed.
 * The link sorts text sections by alignment, then by input order. Aligned to 4,
 * this section comes first among the 4-aligned kernel functions and moves them.
 */
#include <zephyr/autoconf.h>

	.syntax unified
	.thumb
	.section .text.bench_pad, "ax", %progbits
	.balign 4
	.global bench_pad
bench_pad:
	.rept (CONFIG_BENCH_PAD_BYTES / 2)
	nop
	.endr
