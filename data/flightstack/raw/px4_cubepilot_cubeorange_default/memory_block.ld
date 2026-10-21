MEMORY
{
	ITCM_RAM  (rwx) : ORIGIN = 0x00000000, LENGTH =   64K
	FLASH      (rx) : ORIGIN = 0x08020000, LENGTH = 1920K

	DTCM1_RAM (rwx) : ORIGIN = 0x20000000, LENGTH =   64K
	DTCM2_RAM (rwx) : ORIGIN = 0x20010000, LENGTH =   64K
	AXI_SRAM  (rwx) : ORIGIN = 0x24000000, LENGTH =  512K /* D1 domain AXI bus */
	SRAM1     (rwx) : ORIGIN = 0x30000000, LENGTH =  128K /* D2 domain AHB bus */
	SRAM2     (rwx) : ORIGIN = 0x30020000, LENGTH =  128K /* D2 domain AHB bus */
	SRAM3     (rwx) : ORIGIN = 0x30040000, LENGTH =   32K /* D2 domain AHB bus */
	SRAM4     (rwx) : ORIGIN = 0x38000000, LENGTH =   64K /* D3 domain */
	BKPRAM    (rwx) : ORIGIN = 0x38800000, LENGTH =    4K
}
