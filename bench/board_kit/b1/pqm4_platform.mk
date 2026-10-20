# pqm4_platform.mk - expose pqm4's platform layer (start up, clock, UART, linker script, libopencm3)
# to the B1 build without copying any pqm4 file. Author: Huda Mueen.
# Run from inside a pqm4 clone at the pinned commit:
#   make -C <pqm4> -f <this file> PLATFORM=nucleo-l4r5zi AIO= NO_RANDOMBYTES=1 kit-prep kit-flags
# kit-prep builds libopencm3, the linker script and pqm4's HAL library with pqm4's own rules;
# kit-flags prints the compiler, flags and libraries pqm4 would use for that platform.
include mupq/mk/config.mk
include mk/config.mk
include mupq/mk/rules.mk

.PHONY: kit-prep kit-flags
kit-prep: $(LINKDEPS)

kit-flags:
	@echo "KIT_CC=$(CC)"
	@echo "KIT_OBJCOPY=$(OBJCOPY)"
	@echo "KIT_CFLAGS=$(CFLAGS)"
	@echo "KIT_LDFLAGS=$(LDFLAGS)"
	@echo "KIT_LDLIBS=$(LDLIBS)"
	@echo "KIT_LDSCRIPT=$(LDSCRIPT)"
