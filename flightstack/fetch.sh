#!/usr/bin/env bash
# Fetch PX4-Autopilot and ArduPilot at pinned release tags into a third party
# folder outside the repository, with only the submodules the chosen firmware
# targets need, and install the build dependencies from free packages.
#
# Author: Huda Mueen.
#
# Usage: flightstack/fetch.sh [third_party_dir]   (or set THIRD_PARTY)
# Nothing fetched here is committed. Pinned versions are recorded in
# flightstack/pins.csv; the script stops if a tag resolves to another commit.
set -euo pipefail
TP="${1:-${THIRD_PARTY:?pass the third party folder or set THIRD_PARTY}}"
HERE="$(cd "$(dirname "$0")" && pwd)"
mkdir -p "$TP"

PX4_TAG="v1.17.0"
PX4_COMMIT="d6f12ad1c4f70ad3230afd7d86e971421e02fef4"
AP_TAG="Copter-4.7.2"
AP_COMMIT="fb773567896014da007bca58358704d4a0d8516f"

# Submodules needed for the NuttX firmware targets (simulation, ROS and
# Gazebo submodules are not fetched).
PX4_SUBMODULES=(
  platforms/nuttx/NuttX/nuttx
  platforms/nuttx/NuttX/apps
  src/modules/mavlink/mavlink
  src/lib/events/libevents
  src/drivers/gps/devices
  src/modules/uxrce_dds_client/Micro-XRCE-DDS-Client
  src/lib/heatshrink/heatshrink
  src/drivers/uavcan/libdronecan/dsdl
  src/drivers/uavcan/libdronecan/libuavcan/dsdl_compiler/pydronecan
  src/drivers/actuators/vertiq_io/iq-module-communication-cpp
  src/drivers/ins/microstrain/mip_sdk
  src/drivers/ins/sbgecom/sbgECom
  src/lib/crypto/monocypher
  src/lib/crypto/libtomcrypt
  src/lib/crypto/libtommath
  src/lib/cdrstream/cyclonedds
  src/lib/cdrstream/rosidl
  src/modules/zenoh/zenoh-pico
  src/drivers/cyphal/libcanard
  src/drivers/cyphal/public_regulated_data_types
  src/drivers/cyphal/legacy_data_types
)
AP_SUBMODULES=(
  modules/ChibiOS
  modules/mavlink
  modules/waf
  modules/DroneCAN/DSDL
  modules/DroneCAN/dronecan_dsdlc
  modules/DroneCAN/libcanard
  modules/DroneCAN/pydronecan
  modules/lwip
  modules/littlefs
  modules/CrashDebug
)

clone_pinned () {  # dir url tag commit
  local dir="$1" url="$2" tag="$3" commit="$4"
  if [ ! -d "$dir/.git" ]; then
    git clone -q --depth 1 --branch "$tag" "$url" "$dir"
  fi
  local got
  got="$(git -C "$dir" rev-parse HEAD)"
  if [ "$got" != "$commit" ]; then
    echo "pin mismatch in $dir: $got is not $commit" >&2
    exit 1
  fi
}

sub_init () {  # dir paths...
  local dir="$1"; shift
  for s in "$@"; do
    if git -C "$dir" config -f .gitmodules --get-regexp "submodule\..*\.path" | awk '{print $2}' | grep -qx "$s"; then
      git -C "$dir" submodule update --init --depth 1 --recommend-shallow -q -- "$s" \
        || git -C "$dir" submodule update --init -q -- "$s"
    else
      echo "note: $s is not a submodule at this tag, skipped"
    fi
  done
}

clone_pinned "$TP/PX4-Autopilot" https://github.com/PX4/PX4-Autopilot.git "$PX4_TAG" "$PX4_COMMIT"
sub_init "$TP/PX4-Autopilot" "${PX4_SUBMODULES[@]}"
# The MAVLink submodule holds pymavlink as a nested submodule (message generator).
git -C "$TP/PX4-Autopilot/src/modules/mavlink/mavlink" submodule update --init --depth 1 --recursive -q
# PX4 reads its version from git tags; a shallow clone needs the tag present.
git -C "$TP/PX4-Autopilot" fetch -q --depth 1 origin "refs/tags/$PX4_TAG:refs/tags/$PX4_TAG" || true

clone_pinned "$TP/ardupilot" https://github.com/ArduPilot/ardupilot.git "$AP_TAG" "$AP_COMMIT"
sub_init "$TP/ardupilot" "${AP_SUBMODULES[@]}"
# CrashCatcher is a nested submodule of CrashDebug (needed by the STM32H7 crash dump).
git -C "$TP/ardupilot/modules/CrashDebug" submodule update --init --depth 1 -q -- CrashCatcher

# Toolchain and build tools from free distribution packages.
if ! command -v arm-none-eabi-gcc >/dev/null; then
  sudo apt-get install -y gcc-arm-none-eabi binutils-arm-none-eabi libnewlib-arm-none-eabi
fi
# Python build dependencies in a virtual environment inside the third party folder.
if [ ! -x "$TP/venv_flightstack/bin/python" ]; then
  python3 -m venv "$TP/venv_flightstack"
fi
"$TP/venv_flightstack/bin/pip" install -q "empy==3.3.4" kconfiglib jinja2 pyyaml jsonschema future \
  pyros-genmsg packaging numpy toml lxml pexpect intelhex "setuptools<81"

{
  echo "component,version,commit,source,label"
  echo "PX4-Autopilot,$PX4_TAG,$PX4_COMMIT,https://github.com/PX4/PX4-Autopilot,published"
  echo "ArduPilot,$AP_TAG,$AP_COMMIT,https://github.com/ArduPilot/ardupilot,published"
  echo "arm-none-eabi-gcc,$(arm-none-eabi-gcc -dumpfullversion),,$(dpkg-query -W -f='${Package} ${Version}' gcc-arm-none-eabi 2>/dev/null || echo unknown),host measured"
  echo "python,$("$TP/venv_flightstack/bin/python" -c 'import platform; print(platform.python_version())'),,virtual environment in the third party folder,host measured"
} > "$HERE/pins.csv"
echo "fetch done"
