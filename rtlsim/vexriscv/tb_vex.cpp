// Verilator testbench for the VexRiscv core of rtlsim/vexriscv/GenRtlsimVex.scala (round 5).
// Author: Huda Mueen. SPDX-License-Identifier: Apache-2.0
//
// STATUS (2026-10-21): not run. The sbt launcher could not retrieve sbt 1.6.0 (the version in
// VexRiscv project/build.properties): Maven Central answered HTTP 429 to its requests, and
// no mirror was used. VexRiscv was cut (first in the round 5 cut order); this file was never
// built or run.
// Memory and devices copy the CV32E40P example testbench map (example_tb/core/mm_ram.sv at the
// pinned commit), so the same program images run on both cores:
//   RAM 4 MB at address 0, loaded from an objcopy "verilog" hex file (+firmware=<file>);
//   a word written to 0x1000_0000 prints its low byte; a word written to 0x2000_0004 ends the run.
// Bus timing: instruction and data commands are always accepted; a read answers in the cycle
// after the command (one cycle latency, no wait states), as the Ibex and CV32E40P testbench RAMs.
// Data writes take effect at the command. No cache. Usage: VVexRiscv +firmware=<hex> [+maxcycles=N]
#include <cstdint>
#include <cstdio>
#include <cstdlib>
#include <cstring>
#include <fstream>
#include <string>
#include <vector>

#include "VVexRiscv.h"
#include "verilated.h"

static const uint32_t RAM_SIZE = 1u << 22;
static std::vector<uint8_t> ram(RAM_SIZE, 0);

static bool load_hex(const char *path)
{
  std::ifstream in(path);
  if (!in) return false;
  std::string tok;
  uint32_t addr = 0;
  while (in >> tok) {
    if (tok[0] == '@') {
      addr = (uint32_t)strtoul(tok.c_str() + 1, nullptr, 16);
    } else {
      if (addr < RAM_SIZE) ram[addr] = (uint8_t)strtoul(tok.c_str(), nullptr, 16);
      addr++;
    }
  }
  return true;
}

static uint32_t rd32(uint32_t a)
{
  a &= ~3u;
  if (a + 3 >= RAM_SIZE) return 0;
  return ram[a] | (ram[a + 1] << 8) | (ram[a + 2] << 16) | ((uint32_t)ram[a + 3] << 24);
}

int main(int argc, char **argv)
{
  Verilated::commandArgs(argc, argv);
  const char *fw = Verilated::commandArgsPlusMatch("firmware=");
  if (!fw || !*fw) { printf("No firmware specified\n"); return 2; }
  if (!load_hex(fw + strlen("+firmware="))) { printf("cannot read firmware\n"); return 2; }
  uint64_t maxcycles = 20000000000ull;
  const char *mc = Verilated::commandArgsPlusMatch("maxcycles=");
  if (mc && *mc) maxcycles = strtoull(mc + strlen("+maxcycles="), nullptr, 10);

  VVexRiscv *top = new VVexRiscv;
  top->timerInterrupt = 0;
  top->externalInterrupt = 0;
  top->softwareInterrupt = 0;
  top->iBus_cmd_ready = 1;
  top->dBus_cmd_ready = 1;
  top->iBus_rsp_valid = 0;
  top->iBus_rsp_payload_error = 0;
  top->dBus_rsp_ready = 0;
  top->dBus_rsp_error = 0;
  top->reset = 1;
  for (int i = 0; i < 8; i++) {
    top->clk = 0; top->eval();
    top->clk = 1; top->eval();
  }
  top->reset = 0;

  bool ipend = false, dpend = false;
  uint32_t iinst = 0, ddata = 0;
  int exit_code = -1;
  uint64_t cycles = 0;
  while (exit_code < 0 && cycles < maxcycles) {
    top->clk = 0;
    top->iBus_rsp_valid = ipend;
    top->iBus_rsp_payload_inst = iinst;
    top->dBus_rsp_ready = dpend;
    top->dBus_rsp_data = ddata;
    top->eval();
    bool ireq = top->iBus_cmd_valid;
    uint32_t pc = top->iBus_cmd_payload_pc;
    bool dreq = top->dBus_cmd_valid;
    bool wr = top->dBus_cmd_payload_wr;
    uint32_t addr = top->dBus_cmd_payload_address;
    uint32_t data = top->dBus_cmd_payload_data;
    uint32_t size = top->dBus_cmd_payload_size;
    top->clk = 1;
    top->eval();
    cycles++;
    ipend = ireq;
    if (ireq) iinst = rd32(pc);
    dpend = false;
    if (dreq) {
      if (!wr) {
        dpend = true;
        ddata = rd32(addr);
      } else if (addr == 0x10000000u) {
        putchar((int)(data & 0xFF));
      } else if (addr == 0x20000004u) {
        exit_code = (int)data;
      } else if (addr < RAM_SIZE) {
        // VexRiscv's simple data bus replicates byte and half word data across the word lanes.
        if (size == 0) {
          ram[addr] = (uint8_t)(data >> (8 * (addr & 3)));
        } else if (size == 1) {
          uint32_t v = data >> (8 * (addr & 2));
          ram[addr] = (uint8_t)v;
          ram[addr + 1] = (uint8_t)(v >> 8);
        } else {
          for (int b = 0; b < 4; b++) ram[(addr & ~3u) + b] = (uint8_t)(data >> (8 * b));
        }
      }
    }
  }
  fflush(stdout);
  if (exit_code == 0) printf("EXIT SUCCESS\n");
  else if (exit_code > 0) printf("EXIT FAILURE: %d\n", exit_code);
  else printf("TIMEOUT after %llu cycles\n", (unsigned long long)cycles);
  printf("testbench cycles: %llu\n", (unsigned long long)cycles);
  top->final();
  delete top;
  return exit_code == 0 ? 0 : 1;
}
