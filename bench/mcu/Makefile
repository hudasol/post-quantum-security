# Benchmark harness build. Two modes:
#   make host       - build on a PC with -DBENCH_HOST (timer = ns). HOST MEASUREMENT / self-test only.
#   make arm        - cross-build for a Cortex-M board. Needs YOUR board files (startup, linker script,
#                     UART printf). UNTESTED: see README "Board bring-up".
# Libraries must be fetched first:  ./fetch_libs.sh
EXT      ?= ext
MLK_DIR  := $(EXT)/mlkem-native/mlkem
MLD_DIR  := $(EXT)/mldsa-native/mldsa
BUILD    ?= build
ITERS    ?= 100
CC       ?= gcc

COMMON_CFLAGS := -std=c99 -O2 -Wall -Wextra -Wno-unused-parameter -DBENCH_ITERS=$(ITERS) -Isrc

KEM_SETS := 512 768 1024
DSA_SETS := 44 65 87
HOST_BINS := $(addprefix $(BUILD)/host/bench_mlkem_,$(KEM_SETS)) $(addprefix $(BUILD)/host/bench_mldsa_,$(DSA_SETS))

.PHONY: host clean arm
host: $(HOST_BINS)

$(BUILD)/host/bench_mlkem_%: src/bench_mlkem.c src/bench_rng.c $(MLK_DIR)/mlkem_native.c
	@mkdir -p $(dir $@)
	$(CC) $(COMMON_CFLAGS) -D_POSIX_C_SOURCE=200809L -DBENCH_HOST -DMLK_CONFIG_PARAMETER_SET=$* -DMLK_CONFIG_NAMESPACE_PREFIX=mlkem \
	  -DBENCH_OPT_NOTE='"-O2 host gcc, portable C backend"' -I$(MLK_DIR) $^ -o $@

$(BUILD)/host/bench_mldsa_%: src/bench_mldsa.c src/bench_rng.c $(MLD_DIR)/mldsa_native.c
	@mkdir -p $(dir $@)
	$(CC) $(COMMON_CFLAGS) -D_POSIX_C_SOURCE=200809L -DBENCH_HOST -DMLD_CONFIG_PARAMETER_SET=$* -DMLD_CONFIG_NAMESPACE_PREFIX=mldsa \
	  -DBENCH_OPT_NOTE='"-O2 host gcc, portable C backend"' -I$(MLD_DIR) $^ -o $@

# ---- ARM template (UNTESTED) -------------------------------------------------------------
# Example:  make arm CPU=cortex-m33 FPU=fpv5-sp-d16 ALG=mldsa SET=44 CLOCK_HZ=160000000 \
#                    LDSCRIPT=board/link.ld STARTUP=board/startup.c
ARM_CC   ?= arm-none-eabi-gcc
CPU      ?= cortex-m4
FPU      ?= fpv4-sp-d16
ALG      ?= mlkem
SET      ?= 768
CLOCK_HZ ?= 0
RUN_ID   ?= 0
STACK_SPAN ?= 16384
LDSCRIPT ?=
STARTUP  ?=
ARM_OPT  ?= -O2
ARM_EXTRA ?=
ARM_FLAGS := -mcpu=$(CPU) -mthumb -mfpu=$(FPU) -mfloat-abi=hard -ffunction-sections -fdata-sections \
  $(ARM_OPT) -std=c99 -Wall -DBENCH_ITERS=$(ITERS) -DBENCH_CLOCK_HZ=$(CLOCK_HZ) -DBENCH_RUN_ID=$(RUN_ID) -DBENCH_STACK_SPAN=$(STACK_SPAN) \
  -DBENCH_DISABLE_IRQ -DBENCH_OPT_NOTE='"$(ARM_OPT)"' $(ARM_EXTRA) -Isrc
ifeq ($(ALG),mlkem)
  ARM_SRC := src/bench_mlkem.c $(MLK_DIR)/mlkem_native.c
  ARM_DEF := -DMLK_CONFIG_NAMESPACE_PREFIX=mlkem -DMLK_CONFIG_PARAMETER_SET=$(SET) -I$(MLK_DIR)
else
  ARM_SRC := src/bench_mldsa.c $(MLD_DIR)/mldsa_native.c
  ARM_DEF := -DMLD_CONFIG_NAMESPACE_PREFIX=mldsa -DMLD_CONFIG_PARAMETER_SET=$(SET) -I$(MLD_DIR)
endif
arm:
	@test -n "$(LDSCRIPT)" -a -n "$(STARTUP)" || { echo "Set LDSCRIPT= and STARTUP= (board files you must provide)"; exit 2; }
	@mkdir -p $(BUILD)/arm
	$(ARM_CC) $(ARM_FLAGS) $(ARM_DEF) $(ARM_SRC) src/bench_rng.c $(STARTUP) \
	  -T$(LDSCRIPT) -Wl,--gc-sections -Wl,-Map=$(BUILD)/arm/$(ALG)_$(SET).map --specs=nano.specs --specs=nosys.specs \
	  -o $(BUILD)/arm/$(ALG)_$(SET).elf
	arm-none-eabi-size $(BUILD)/arm/$(ALG)_$(SET).elf

clean:
	rm -rf $(BUILD)
