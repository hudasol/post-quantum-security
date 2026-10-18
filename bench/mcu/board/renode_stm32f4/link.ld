/* Minimal linker script for the STM32F4 Discovery (STM32F407VG, Cortex-M4F) as modelled by Renode.
 * Flash at 0x08000000. RAM is limited to the 128 KB of contiguous SRAM of the real STM32F407
 * (Renode's model maps more), so a build that fits here also fits the board. Heap is kept small (8 KB). */
ENTRY(Reset_Handler)
MEMORY
{
  CODE (rx)  : ORIGIN = 0x08000000, LENGTH = 1M
  RAM  (rwx) : ORIGIN = 0x20000000, LENGTH = 128K
}
_estack = ORIGIN(RAM) + LENGTH(RAM);
SECTIONS
{
  .text : { KEEP(*(.vectors)) *(.text*) *(.rodata*) . = ALIGN(4); } > CODE
  .ARM.exidx : { *(.ARM.exidx*) } > CODE
  _sidata = LOADADDR(.data);
  .data : { _sdata = .; *(.data*) . = ALIGN(4); _edata = .; } > RAM AT > CODE
  .bss (NOLOAD) : { _sbss = .; *(.bss*) *(COMMON) . = ALIGN(4); _ebss = .; } > RAM
  .heap (NOLOAD) : { . = ALIGN(8); _heap_start = .; . = . + 8K; _heap_end = .; } > RAM
}
