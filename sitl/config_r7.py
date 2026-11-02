"""Round 7 additions to the software in the loop study with executed cryptography (gateway emulation).

Two configurations are added beside those of round 6 (sitl/config_r6.py, unchanged):
  pqsig_falcon          Falcon-512 signature on every command (ground signs, vehicle verifies); no session
  pqsig_falcon_counter  Falcon-512 signature per command over the frame and a 6 B counter, published rule at the
                        vehicle
Their vehicle side delay is the median Falcon-512 verification of the 15 RTL runs (rtlsim/results/proto_falcon.csv)
on the core of round 6 (settings_r6.csv rtl_core) at the mission study clock, labelled estimated from RTL
simulated cycles. As for ML-DSA-44 with a counter, the 6 B counter is not costed separately.

Three result sets are added, each in its own folder, and none replaces a round 6 file (sitl/raw_r6/ and
sitl/results_r6/ are unchanged):
  falcon20   the two Falcon-512 configurations on the 20 paired seeds of round 6, independent loss
  burst20    the configurations of BURST_SET on the same 20 seeds under the two state loss model of round 7
             (sitl/linkrelay.py; mean frame loss of round 6, mean burst from settings_r7.csv)
  large100   the configurations of BURST_SET on 100 missions (missions 0 to 99 of the round 6 seed block) under the
             independent loss of round 6
Author: Huda Mueen.
"""
import csv
import os

from . import config_r6 as c6

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)

CONFIGS = ['pqsig_falcon', 'pqsig_falcon_counter']
CONFIG_NAMES = {'pqsig_falcon': '11 Falcon-512 signature per command',
                'pqsig_falcon_counter': '12 Falcon-512 signature per command with a counter, published rule'}
SHORT = {'pqsig_falcon': 'Falcon-512 cmd', 'pqsig_falcon_counter': 'Falcon-512 ctr'}
# configurations of the burst loss set and of the larger set (the key configurations named in the round 7 plan)
BURST_SET = ['none', 'classical', 'hybrid_published', 'hybrid_cache', 'hybrid_strict', 'hybrid_strict_inband',
             'kem_auth', 'pqsig_real', 'pqsig_falcon']
SETS = {
    'falcon20': dict(loss='independent', configs=CONFIGS, missions_key='missions_falcon_r7',
                     title='Falcon-512 per command, 20 paired missions, independent loss'),
    'burst20': dict(loss='burst', configs=BURST_SET, missions_key='missions_burst_r7',
                    title='two state (burst) loss, 20 paired missions'),
    'large100': dict(loss='independent', configs=BURST_SET, missions_key='missions_large_r7',
                     title='larger set, 100 paired missions, independent loss'),
}
FALCON_RTL = os.path.join(ROOT, 'rtlsim', 'results', 'proto_falcon.csv')
FALCON_VERIFY_OP = 'vehicle_verify_command'


def load_settings(path=os.path.join(HERE, 'settings_r7.csv')):
    with open(path, newline='', encoding='utf-8') as f:
        return {r['name']: float(r['value']) for r in csv.DictReader(f)}


def burst_params(mean_loss, mean_frames):
    """Transition probabilities of the two state loss model with the given mean loss and mean burst (frames)."""
    p_bg = 1.0 / mean_frames
    p_gb = mean_loss * p_bg / (1.0 - mean_loss)
    return dict(p_gb=p_gb, p_bg=p_bg, mean_loss=mean_loss, mean_burst_frames=mean_frames)


def link_profile(prof, loss_model, s7=None):
    """The round 6 profile, with the two state loss parameters added when loss_model is 'burst'."""
    if loss_model == 'independent':
        return prof
    if loss_model != 'burst':
        raise ValueError(loss_model)
    s7 = s7 or load_settings()
    return dict(prof, burst=burst_params(prof['loss'], s7['burst_mean_frames']))


def falcon_delays(core, clock_hz, path=FALCON_RTL):
    """Vehicle side Falcon-512 verification delay {name: dict(seconds, cycles, source, core, label)}."""
    with open(path, newline='', encoding='utf-8') as f:
        m = [r for r in csv.DictReader(f) if r['core'].lower() == core.lower() and r['operation'] == FALCON_VERIFY_OP]
    if len(m) != 1:
        raise KeyError(f'proto_falcon.csv row for {FALCON_VERIFY_OP}: {len(m)} matches (core {core})')
    cyc = float(m[0]['cycles_median'])
    return {'falcon512_verify_command': dict(seconds=cyc / clock_hz, cycles=cyc,
                                             source=f'proto_falcon.csv {core} {FALCON_VERIFY_OP}', core=core,
                                             label='estimated from RTL simulated cycles')}


def security_config(name, delays=None):
    """Description of a round 7 configuration for the gateway relay (round 6 configurations: config_r6)."""
    if name not in CONFIGS:
        return c6.security_config(name, delays)
    base = c6.security_config('none', delays)
    d = base['delays']
    sig = 666  # padded Falcon-512 signature (sitl/pqcrypto.py FALCON512_SIG, the published size in S15_signature_sizes.csv)
    base.update(name=name, pqsig=True, pqsig_alg='falcon512', pqsig_delay='falcon512_verify_command',
                cmd_extra_bytes=sig, cmd_delay_s=d.get('falcon512_verify_command', 0.0))
    if name == 'pqsig_falcon_counter':
        base.update(pq_counter=True, rule='published', cmd_extra_bytes=sig + 6)
    return base
