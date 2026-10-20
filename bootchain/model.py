"""Signed boot and update chain model. Author: Huda Mueen.

Arithmetic only. Verification time = hash time over the image + signature verification time.
Transfer time = bytes x 8 / effective link rate. No cryptographic code is run or implemented.
Cycle counts are read from data/evidence.csv by id through energy/cycle_map.csv.
"""
import os

from energy import model as em

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = em.ROOT
SEED = em.SEED


def load_inputs():
    return {r["name"]: r for r in em.read_csv(os.path.join(HERE, "inputs.csv"))}


def inval(inputs, name):
    return float(inputs[name]["value"])


def load_schemes():
    return em.read_csv(os.path.join(HERE, "schemes.csv"))


def hash_time_s(image_bytes, cycles_per_byte, clock_mhz):
    return image_bytes * cycles_per_byte / (clock_mhz * 1e6)


def verify_time_s(image_bytes, cycles_per_byte, sig_cycles, clock_mhz):
    """Hash over the image plus one signature verification, in seconds."""
    return hash_time_s(image_bytes, cycles_per_byte, clock_mhz) + sig_cycles / (clock_mhz * 1e6)


def ab_layout_bytes(image_bytes, header_bytes, bootloader_bytes, swap_bytes):
    """Flash needed for an A and B slot layout: bootloader + two slots of (image + header) + swap state."""
    return bootloader_bytes + 2 * (image_bytes + header_bytes) + swap_bytes


def max_image_ab(flash_bytes, header_bytes, bootloader_bytes, swap_bytes):
    """Largest image that fits two slots in the given flash."""
    return (flash_bytes - bootloader_bytes - swap_bytes) / 2 - header_bytes


def transfer_time_s(nbytes, rate_bps, usable_fraction=1.0, duty_cycle=1.0):
    """Simple bytes over rate. No loss, retries, framing or acknowledgements."""
    return nbytes * 8.0 / (rate_bps * usable_fraction * duty_cycle)


def pct_increase(base, new):
    return 100.0 * (new - base) / base


def link_rates(params):
    """Effective rates (bit/s) for a few links from linksim/params.csv (cited and assumption rows)."""
    p = {r["name"]: r for r in params}
    v = lambda k: float(p[k]["value"])
    return {
        "SiK 64 kbit/s air rate, 90 percent usable": (v("sik_air_rate_bps") * v("sik_usable_fraction"), "cited"),
        "IEEE 802.15.4 250 kbit/s": (v("ieee802154_rate_bps"), "cited"),
        "BLE 1 Mbit/s raw": (v("ble_rate_bps"), "assumption"),
        "LoRaWAN DR0 250 bit/s at 1 percent duty cycle": (v("lorawan_dr0_bitrate_bps") * v("lorawan_duty_cycle"), "cited"),
    }
