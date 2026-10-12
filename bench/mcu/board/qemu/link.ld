/* Minimal linker script for QEMU mps2-an386 (Cortex-M4). Code in the 4 MB SSRAM1 at 0x0, data in SSRAM2/3 at 0x20000000. */
ENTRY(Reset_Handler)
MEMORY
{
  CODE (rx)  : ORIGIN = 0x00000000, LENGTH = 2M
  RAM  (rwx) : ORIGIN = 0x20000000, LENGTH = 2M
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
