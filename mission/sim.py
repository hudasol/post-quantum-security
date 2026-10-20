"""Seeded discrete event mission simulation of an authenticated command channel (label: estimated).

One run = one mission of a drone or a ground robot over one link with one architecture.
Events: link outages (Poisson starts, exponential durations), session handshakes, rekeys,
teardown after long outages, and a periodic stream of commands. Each command is checked for
(i) a valid session key at issue, (ii) an unbroken link during delivery, (iii) delivery and
check within the deadline. Link transfers use a selective repeat style model with independent
frame loss. All inputs are labelled in mission/assumptions.csv, linksim/params.csv and
data/evidence.csv.
"""
import math
import zlib

import numpy as np

from . import model

SEED = 20261020


def rng_for(key, seed=SEED):
    """Deterministic generator for a configuration key (seed 20261020, spawn key from CRC32 of the key)."""
    return np.random.default_rng(np.random.SeedSequence(seed, spawn_key=(zlib.crc32(key.encode()),)))


def merge_intervals(iv):
    """Merge overlapping (start, end) intervals; returns two arrays (starts, ends)."""
    iv = sorted((s, e) for s, e in iv if e > s)
    out = []
    for s, e in iv:
        if out and s <= out[-1][1]:
            out[-1][1] = max(out[-1][1], e)
        else:
            out.append([s, e])
    if not out:
        return np.zeros(0), np.zeros(0)
    a = np.array(out)
    return a[:, 0], a[:, 1]


def overlaps(starts, ends, t0, t1):
    """Boolean array: does [t0, t1] overlap any merged interval (vectorised over t0, t1)."""
    t0 = np.asarray(t0, float)
    t1 = np.asarray(t1, float)
    if len(starts) == 0:
        return np.zeros(t0.shape, bool)
    idx = np.searchsorted(starts, t1, side='right') - 1
    ok = idx >= 0
    res = np.zeros(t0.shape, bool)
    res[ok] = ends[idx[ok]] > t0[ok]
    return res


def sample_outages(rng, T, rate_per_h, mean_s):
    n = rng.poisson(rate_per_h * T / 3600.0) if rate_per_h > 0 else 0
    s = np.sort(rng.uniform(0, T, n))
    d = rng.exponential(mean_s, n)
    return merge_intervals(list(zip(s, s + d)))


def sample_flight(rng, frames, link, loss, ack_air, rto_factor=2.0, max_rounds=20):
    """Time and air time to move one flight (list of frame air times) with selective repeat rounds.

    Each round sends all outstanding frames, then waits turnaround plus an acknowledgement;
    a lost acknowledgement costs a retransmission timeout. On duty cycled links every frame
    except the last is followed by the transmitter's silence (air x (1/duty - 1)).
    """
    frames = np.asarray(frames, float)
    left = np.ones(len(frames), bool)
    t = 0.0
    air = 0.0
    tt = link['turnaround']
    rto = rto_factor * (tt + ack_air)
    for _ in range(max_rounds):
        if not left.any():
            break
        f = frames[left]
        air += f.sum()
        t += f.sum() / link['duty'] - f[-1] * (1 / link['duty'] - 1)
        lost = rng.random(len(f)) < loss
        idx = np.flatnonzero(left)
        left[:] = False
        left[idx[lost]] = True
        t += tt + ack_air
        air += ack_air
        if rng.random() < loss:
            t += rto
    return t, air


def sample_handshake(rng, cfg):
    """Return (duration s, {direction: air s}) of one handshake or rekey for a session architecture."""
    t = 0.0
    air = {'up': 0.0, 'down': 0.0}
    for direction, nbytes in cfg['ap']['flights']:
        dt, da = sample_flight(rng, model.object_frames(nbytes, cfg['link'], cfg['a'], cfg['p']), cfg['link'],
                               cfg['loss'], cfg['ack_air'], cfg['p']['rto_factor'], int(cfg['p']['max_retries']))
        t += dt
        air[direction] += da
    t += cfg['ap']['hs_cycles'] * cfg['ws'] / cfg['clock']
    return t, air


def transfer_through_outages(start, dur, o_s, o_e):
    """End time of a transfer of duration dur that pauses during outages."""
    end = start + dur
    for s, e in zip(o_s, o_e):
        if e <= start:
            continue
        if s >= end:
            break
        end += e - max(s, start)
    return end


def session_timeline(rng, cfg, T, o_s, o_e):
    """Return dict with invalid intervals, busy intervals, recovery times and transfer air time."""
    invalid, busy, ttra = [], [], []
    air_total = {'up': 0.0, 'down': 0.0}
    n_hs = 0

    def transfer(start):
        nonlocal air_total, n_hs
        d, air = sample_handshake(rng, cfg)
        air_total['up'] += air['up']
        air_total['down'] += air['down']
        n_hs += 1
        return transfer_through_outages(start, d, o_s, o_e)

    end0 = transfer(0.0)
    invalid.append((0.0, end0))
    busy.append((0.0, end0))
    cursor = end0
    R = cfg['rekey']
    next_rk = cursor + R
    timeout = cfg['timeout']
    G = cfg['grace']
    while cursor < T:
        td_idx = None
        for i in range(len(o_s)):
            if o_s[i] >= cursor and o_e[i] - o_s[i] > timeout:
                td_idx = i
                break
        td = o_s[td_idx] + timeout if td_idx is not None else math.inf
        while next_rk < min(td, T):
            rk_end = transfer(next_rk)
            busy.append((next_rk, rk_end))
            if rk_end - next_rk > G:
                invalid.append((next_rk + G, rk_end))
            next_rk = rk_end + R
        if td >= T:
            break
        e = o_e[td_idx]
        h_end = transfer(e)
        invalid.append((td, h_end))
        busy.append((e, h_end))
        ttra.append(h_end - e)
        cursor = h_end
        next_rk = h_end + R
    return dict(invalid=merge_intervals(invalid), busy=merge_intervals(busy), ttra=ttra, air=air_total, n_hs=n_hs)


def _retry_time(rng, frames, n, loss, link, ack_air, rto_factor):
    """Per command extra time from frame retransmissions and the frame air time (vectorised over n commands)."""
    frames = np.asarray(frames, float)
    if loss > 0:
        att = rng.geometric(1 - loss, size=(n, len(frames)))
    else:
        att = np.ones((n, len(frames)), int)
    rto = rto_factor * (link['turnaround'] + ack_air)
    air = (att * frames).sum(axis=1)
    retry_wait = ((att - 1) * rto).sum(axis=1)
    # silence between frames of one command on duty cycled links
    silence = (att.sum(axis=1) - 1) * frames.mean() * (1 / link['duty'] - 1)
    return air, retry_wait + silence, att.sum(axis=1)


def lindley(arrivals, service):
    """Start times of FIFO service: start_k = max(arrival_k, start_{k-1} + service_{k-1})."""
    S = np.concatenate([[0.0], np.cumsum(service)[:-1]])
    return S + np.maximum.accumulate(arrivals - S)


def build_config(vehicle, arch, link_name, params=None, **over):
    """Assemble a configuration dict. Keyword overrides replace assumption values."""
    p = model.load_link_params()
    a = dict(model.load_assumptions())
    a.update({k: v for k, v in over.items() if k in a})
    link = model.link_profile(link_name, p)
    ap = model.arch_profile(arch, p)
    cmd_auth, cmd_base = model.command_frames(vehicle, arch, link, p=p, a=a)
    tel_air, tel_msgs, tel_frame = model.telemetry_load(vehicle, arch, link, p=p)
    by_dir = model.telemetry_load_by_dir(vehicle, arch, link, p=p)
    ack_air = sum(model.link_frames(model.mav_frame_bytes(p['ack_payload_bytes'], 0, p), link))
    phases = model.mission_phases(vehicle, a)
    ts = float(over.get('tel_scale', 1.0))  # scales all non command traffic (0 = commands only)
    return dict(vehicle=vehicle, arch=arch, link_name=link_name, p=p, a=a, link=link, ap=ap,
                cmd_auth=cmd_auth, cmd_base=cmd_base, tel_air=tel_air * ts, tel_msgs=tel_msgs * ts, tel_frame=tel_frame,
                tel_up=by_dir['up'] * ts, tel_down=by_dir['down'] * ts, ack_air=ack_air, tel_scale=ts,
                loss=a['frame_loss'], rekey=a['rekey_interval_s'], timeout=a['session_timeout_s'],
                grace=a['grace_s'], clock=a['clock_hz'], ws=a['wait_state_factor'], mac=a['mac_cycles'],
                outage_rate=a['outage_rate_per_h'], outage_mean=a['outage_mean_s'], deadline=a['deadline_s'],
                T=phases[-1][2], t_meas=phases[0][2],
                cmd_rate=float(over.get('cmd_rate', model.command_rate(vehicle))))


def run_once(rng, cfg, deadlines):
    """Simulate one mission. Returns a dict of per run metrics; availability for each deadline."""
    T, t0 = cfg['T'], cfg['t_meas']
    link = cfg['link']
    o_s, o_e = sample_outages(rng, T, cfg['outage_rate'], cfg['outage_mean'])
    if cfg['ap']['session']:
        st = session_timeline(rng, cfg, T, o_s, o_e)
    else:
        st = dict(invalid=(np.zeros(0), np.zeros(0)), busy=(np.zeros(0), np.zeros(0)), ttra=[], air={'up': 0.0, 'down': 0.0}, n_hs=0)
    inv_s, inv_e = st['invalid']
    bus_s, bus_e = st['busy']
    n = int(math.floor((T - t0) * cfg['cmd_rate']))
    t = t0 + np.arange(n) / cfg['cmd_rate']
    duty = link['duty']
    # contention with other traffic from the same transmitter (shared channel: all traffic)
    if link['shared']:
        u = min(1.0, cfg['tel_air'])
        resid = cfg['tel_frame']
    else:
        u = min(1.0, cfg['tel_up'] / duty)
        resid = cfg['tel_frame'] / duty
    in_busy = overlaps(bus_s, bus_e, t, t)
    wait = np.where(rng.random(n) < u, rng.uniform(0, resid, n), 0.0)
    hs_frame = max(model.object_frames(239, link, cfg['a'], cfg['p'])) if cfg['ap']['session'] else 0.0
    if link['shared']:
        wait = np.where(in_busy, rng.uniform(0, hs_frame, n), wait)
        arrivals = t + wait
    else:
        # duty cycled transmitter: a command waits until the handshake transfer in progress finishes
        idx = np.searchsorted(bus_s, t, side='right') - 1
        blocked = in_busy & (idx >= 0)
        arrivals = np.where(blocked, np.maximum(t, bus_e[np.clip(idx, 0, None)] if len(bus_e) else t), t) + wait
    state = rng.bit_generator.state
    air_a, extra_a, nfa = _retry_time(rng, cfg['cmd_auth'], n, cfg['loss'], link, cfg['ack_air'], cfg['p']['rto_factor'])
    rng.bit_generator.state = state
    air_b, extra_b, _ = _retry_time(rng, cfg['cmd_base'], n, cfg['loss'], link, cfg['ack_air'], cfg['p']['rto_factor'])
    mac = cfg['mac'] if cfg['ap']['tag_bytes'] else 0.0
    comp = (cfg['ap']['cmd_cycles'] + mac) * cfg['ws'] / cfg['clock']
    occ_a = air_a + extra_a + (air_a / duty - air_a) * (1 if duty < 1 else 0)
    occ_b = air_b + extra_b + (air_b / duty - air_b) * (1 if duty < 1 else 0)
    start_a = lindley(arrivals, occ_a)
    start_b = lindley(arrivals, occ_b)
    lat_a = start_a - t + air_a + extra_a + comp
    lat_b = start_b - t + air_b + extra_b
    valid = ~overlaps(inv_s, inv_e, t, t)
    link_ok = ~overlaps(o_s, o_e, t, t + lat_a)
    link_ok_b = ~overlaps(o_s, o_e, t, t + lat_b)
    out = {}
    for d in deadlines:
        ok = valid & link_ok & (lat_a <= d)
        out[f'avail_{d:g}'] = ok.mean() if n else float('nan')
        okb = link_ok_b & (lat_b <= d)
        out[f'avail_base_{d:g}'] = okb.mean() if n else float('nan')
    dl = cfg['deadline']
    okd = valid & link_ok & (lat_a <= dl)
    out['avail'] = okd.mean() if n else float('nan')
    out['added_latency_ms'] = float(np.median((lat_a - lat_b)[okd]) * 1e3) if okd.any() else float('nan')
    out['latency_ms'] = float(np.median(lat_a[valid & link_ok]) * 1e3) if (valid & link_ok).any() else float('nan')
    # utilisation
    n_all = n
    cmd_air_total = air_a.sum()
    hs_air = st['air']['up'] + st['air']['down']
    if link['shared']:
        out['utilisation'] = (cfg['tel_air'] * T + cmd_air_total + hs_air) / T
        out['utilisation_down'] = float('nan')
    else:
        # share of each transmitter's duty cycle budget (ground transmitter carries the commands)
        out['utilisation'] = (cfg['tel_up'] * T + cmd_air_total + st['air']['up']) / (T * duty)
        out['utilisation_down'] = (cfg['tel_down'] * T + st['air']['down']) / (T * duty)
    cyc = (st['n_hs'] * cfg['ap']['hs_cycles'] + cfg['ap']['boot_cycles'] + n_all * cfg['ap']['cmd_cycles'])
    if cfg['ap']['tag_bytes']:
        cyc += (n_all + cfg['tel_msgs'] * T) * cfg['mac']
    out['compute_share'] = cyc * cfg['ws'] / (T * cfg['clock'])
    out['n_handshakes'] = st['n_hs']
    out['n_teardowns'] = len(st['ttra'])
    out['ttra_s'] = float(np.mean(st['ttra'])) if st['ttra'] else float('nan')
    out['first_session_s'] = float(inv_e[0]) if cfg['ap']['session'] and len(inv_e) else 0.0
    out['n_outages'] = len(o_s)
    return out


def run_config(vehicle, arch, link_name, runs, deadlines, key_extra='', **over):
    """Run a configuration `runs` times with its own seeded generator; returns (list of dicts, cfg)."""
    cfg = build_config(vehicle, arch, link_name, **over)
    key = f'{vehicle}|{arch}|{link_name}|{key_extra}'
    rng = rng_for(key)
    res = [run_once(rng, cfg, deadlines) for _ in range(runs)]
    return res, cfg
