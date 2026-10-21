// VexRiscv configuration for the rtlsim timing program (round 5). Author: Huda Mueen.
// Based on vexriscv.demo.GenFullNoMmuNoCache at the pinned VexRiscv commit, with three changes:
// compressed instructions on (RV32IMC, the ISA of the Ibex and CV32E40P runs), reset vector 0x180
// (the boot address of the CV32E40P example testbench start up code, so that the same program
// image runs unchanged), mcycle and mcycleh readable, and no debug plugin. Simple instruction
// and data buses, no cache, no MMU. The CSR plugin ignores accesses to CSRs it does not implement
// (catchIllegalAccess = false in CsrPluginConfig.small), so the program's write to mcountinhibit
// has no effect and mcycle counts from reset.
// STATUS (2026-10-21): not run. The sbt launcher could not retrieve sbt 1.6.0 (the version in
// VexRiscv project/build.properties): Maven Central answered HTTP 429 to its requests, and
// no mirror was used. VexRiscv was cut (first in the round 5 cut order); this file was never
// built or run.
package vexriscv.demo

import vexriscv.plugin._
import vexriscv.{plugin, VexRiscv, VexRiscvConfig}
import spinal.core._

object GenRtlsimVex extends App {
  def cpu() = new VexRiscv(
    config = VexRiscvConfig(
      plugins = List(
        new IBusSimplePlugin(
          resetVector = 0x00000180l,
          cmdForkOnSecondStage = false,
          cmdForkPersistence = false,
          prediction = STATIC,
          catchAccessFault = false,
          compressedGen = true
        ),
        new DBusSimplePlugin(
          catchAddressMisaligned = false,
          catchAccessFault = false
        ),
        new DecoderSimplePlugin(
          catchIllegalInstruction = true
        ),
        new RegFilePlugin(
          regFileReadyKind = plugin.SYNC,
          zeroBoot = false
        ),
        new IntAluPlugin,
        new SrcPlugin(
          separatedAddSub = false,
          executeInsertion = true
        ),
        new FullBarrelShifterPlugin,
        new HazardSimplePlugin(
          bypassExecute           = true,
          bypassMemory            = true,
          bypassWriteBack         = true,
          bypassWriteBackBuffer   = true,
          pessimisticUseSrc       = false,
          pessimisticWriteRegFile = false,
          pessimisticAddressMatch = false
        ),
        new MulPlugin,
        new DivPlugin,
        new CsrPlugin(CsrPluginConfig.small(0x00000000l).copy(mcycleAccess = CsrAccess.READ_ONLY)),
        new BranchPlugin(
          earlyBranch = false,
          catchAddressMisaligned = true
        ),
        new YamlPlugin("cpu0.yaml")
      )
    )
  )

  SpinalVerilog(cpu())
}
