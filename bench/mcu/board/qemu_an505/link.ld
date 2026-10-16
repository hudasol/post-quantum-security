/* Minimal linker script for QEMU mps2-an505 (Cortex-M33 with the security extension).
 * The core resets in the secure state with its vector table at 0x10000000, the secure alias of the
 * 4 MB code SSRAM. Data and stack use the secure alias 0x38000000 of the 2 MB data SSRAM.
 * Board support only; start up code is shared with mps2-an386 (board/qemu/startup.c). */
ENTRY(Reset_Handler)
MEMORY
{
  CODE (rx)  : ORIGIN = 0x10000000, LENGTH = 2M
  RAM  (rwx) : ORIGIN = 0x38000000, LENGTH = 2M
}
_estack = ORIGIN(RAM) + LENGTH(RAM);
SECTIONS
{
  .text : { KEEP(*(.vectors)) *(.text*) *(.rodata*) . = ALIGN(4); } > CODE
  .ARM.exidx : { *(.ARM.exidx*) } > CODE
  _sidata = LOADADDR(.data);
  .data : { _sdata = .; *(.data*) . = ALIGN(4); _edata = .; } > RAM AT > CODE
  .bss (NOLOAD) : { _sbss = .; *(.bss*) *(COMMON) . = ALIGN(4); _ebss = .; } > RAM
  .heap (NOLOAD) : { . = ALIGN(8); _heap_start = .; . = . + 64K; _heap_end = .; } > RAM
}
