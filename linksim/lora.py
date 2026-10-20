"""LoRa time on air and a LoRaWAN EU868 link whose air time follows it.

Author: Huda Mueen.

Formula (data/raw/S12_link_sources.md lines 47 to 49, a secondary source that
attributes it to the Semtech SX1276 data sheet):
  Ts = 2^SF / BW
  n_payload = 8 + max(ceil((8 PL - 4 SF + 28 + 16 CRC - 20 IH) / (4 (SF - 2 DE))) (CR + 4), 0)
  T = Ts ((n_preamble + 4.25) + n_payload)
Size and timing arithmetic only; no cryptographic operation.
"""
import math

from . import model


def symbol_s(sf, bw_hz):
    return (2 ** int(sf)) / float(bw_hz)


def payload_symbols(pl, sf, cr=1, crc=1, ih=0, de=0):
    num = 8 * int(pl) - 4 * int(sf) + 28 + 16 * int(crc) - 20 * int(ih)
    den = 4 * (int(sf) - 2 * int(de))
    return 8 + max(math.ceil(num / den) * (int(cr) + 4), 0)


def time_on_air_s(pl, sf, bw_hz=125000, cr=1, n_preamble=8, crc=1, ih=0, de=None,
                  header_extra=4.25):
    """Time on air of one LoRa packet of pl PHY payload bytes. de defaults to
    on for SF11 and SF12 at 125 kHz (data/raw/S12_link_sources.md line 56)."""
    if de is None:
        de = 1 if (int(sf) >= 11 and float(bw_hz) <= 125000) else 0
    ts = symbol_s(sf, bw_hz)
    return ts * ((n_preamble + header_extra) + payload_symbols(pl, sf, cr, crc, ih, de))


class LoraLink(model.Link):
    """LoRaWAN EU868 link. wire bytes passed to air_s are application bytes
    (fragment data plus any fragment header); the 13 B LoRaWAN frame overhead
    is added inside air_s, and the LoRa PHY overhead comes from the formula."""

    def __init__(self, p, dr=0, duty=None):
        sf = int(p["lora_dr0_sf"] if dr == 0 else p["lora_dr5_sf"])
        cap = int(p["lorawan_dr0_payload_bytes"] if dr == 0 else p["lorawan_dr5_payload_bytes"])
        rate = p["lorawan_dr0_bitrate_bps"] if dr == 0 else p["lorawan_dr5_bitrate_bps"]
        model.Link.__init__(self, "lora_dr%d" % dr, "LoRaWAN EU868 DR%d (time on air model)" % dr,
                            "packet", rate, cap, 0,
                            p["lorawan_duty_cycle"] if duty is None else duty,
                            p["turnaround_lorawan_s"])
        self.sf = sf
        self.bw = p["lora_bw_hz"]
        self.cr = int(p["lora_coding_rate_index"])
        self.npre = p["lora_preamble_symbols"]
        self.hdr_extra = p["lora_header_extra_symbols"]
        self.mac = int(p["lorawan_frame_overhead_bytes"])

    def air_s(self, wire_bytes):
        return time_on_air_s(int(wire_bytes) + self.mac, self.sf, self.bw, self.cr,
                             self.npre, 1, 0, None, self.hdr_extra)
