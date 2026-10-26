/* Candidate STM32F411CE memory map: 512 KiB flash, 128 KiB SRAM.
   Not a statement about received hardware; no bootloader region reserved. */
ENTRY(Reset_Handler)
MEMORY {
  FLASH (rx) : ORIGIN = 0x08000000, LENGTH = 512K
  RAM (xrw) : ORIGIN = 0x20000000, LENGTH = 128K
}
_estack = ORIGIN(RAM) + LENGTH(RAM);
_Min_Heap_Size = 0;
_Min_Stack_Size = 8192;
PHDRS {
  code PT_LOAD FLAGS(5);
  initialized_data PT_LOAD FLAGS(6);
  zero_data PT_LOAD FLAGS(6);
}
SECTIONS {
  .isr_vector : { . = ALIGN(4); KEEP(*(.isr_vector)); . = ALIGN(4); } > FLASH :code
  .text : { . = ALIGN(4); *(.text*) *(.rodata*) KEEP(*(.init)) KEEP(*(.fini)) . = ALIGN(4); } > FLASH :code
  .ARM.extab : { *(.ARM.extab* .gnu.linkonce.armextab.*) } > FLASH :code
  .ARM.exidx : { __exidx_start = .; *(.ARM.exidx*) __exidx_end = .; } > FLASH :code
  .preinit_array : { PROVIDE_HIDDEN(__preinit_array_start = .); KEEP(*(.preinit_array*)) PROVIDE_HIDDEN(__preinit_array_end = .); } > FLASH :code
  .init_array : { PROVIDE_HIDDEN(__init_array_start = .); KEEP(*(SORT(.init_array.*))) KEEP(*(.init_array*)) PROVIDE_HIDDEN(__init_array_end = .); } > FLASH :code
  .fini_array : { PROVIDE_HIDDEN(__fini_array_start = .); KEEP(*(SORT(.fini_array.*))) KEEP(*(.fini_array*)) PROVIDE_HIDDEN(__fini_array_end = .); } > FLASH :code
  _sidata = LOADADDR(.data);
  .data : { . = ALIGN(4); _sdata = .; *(.data*) . = ALIGN(4); _edata = .; } > RAM AT> FLASH :initialized_data
  .bss (NOLOAD) : AT(ADDR(.bss)) { . = ALIGN(4); _sbss = .; *(.bss*) *(COMMON) . = ALIGN(4); _ebss = .; } > RAM :zero_data
  .reserved_stack (NOLOAD) : AT(ADDR(.reserved_stack)) { . = ALIGN(8); _end = .; end = .; . += _Min_Heap_Size + _Min_Stack_Size; . = ALIGN(8); } > RAM :zero_data
  /DISCARD/ : { *(.note.GNU-stack) }
}
ASSERT(_ebss + _Min_Heap_Size + _Min_Stack_Size <= _estack, "RAM and reserved stack exceed STM32F411CE")
