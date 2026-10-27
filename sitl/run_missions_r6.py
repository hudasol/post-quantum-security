"""Round 6: scripted ArduPilot SITL missions through the emulated link with an executing gateway pair.

The flight stack, mission script, command stream, link profile and outage design are those of round 5
(sitl/run_missions.py, whose helpers are reused unchanged). Differences: the relay is the gateway relay of
sitl/gwrelay.py, which executes the cryptography with pinned libraries; the seeds are paired across
configurations (mission i on a profile uses the same seed in every configuration, so outage start, outage
duration, command phases and the channel loss generator start from the same state); vehicle side compute delays
come from the RTL simulated cycles of the round 6 RTL runs at the mission study clock.

Usage (repository root, flight stack built by sitl/fetch.sh, libraries by sitl/pqlib/build.sh):
  SITL_PQLIB=<folder> python3 -m sitl.run_missions_r6 --config hybrid_strict --profile sik --rtl <rtl results folder>
Outputs in sitl/raw_r6/: <profile>_<config>_{missions,commands,events,arrivals}.csv and _run.json.
"""
import argparse
import csv
import json
import os
import random
import subprocess
import sys
import time

from pymavlink import mavutil

from mission import model

from . import config as cfgmod
from . import config_r6 as c6
from . import gwrelay
from . import pqcrypto
from .run_missions import AP_DEFAULT, MODE_AUTO, MODE_GUIDED, Gcs, dbg, mission_items, set_param

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)


def library_versions():
    import cryptography
    info = dict(cryptography=cryptography.__version__)
    p = os.path.join(pqcrypto.LIB_DIR, 'build_info.txt')
    if os.path.exists(p):
        with open(p) as f:
            for line in f:
                k, _, v = line.strip().partition('=')
                info[k] = v
    return info


def main(argv=None):
    ap = argparse.ArgumentParser()
    ap.add_argument('--config', choices=c6.CONFIGS, required=True)
    ap.add_argument('--profile', choices=c6.PROFILES, default='sik')
    ap.add_argument('--missions', type=int, default=None)
    ap.add_argument('--first', type=int, default=0, help='index of the first mission (for split runs)')
    ap.add_argument('--instance', type=int, default=0)
    ap.add_argument('--ardupilot', default=AP_DEFAULT)
    ap.add_argument('--rtl', required=True, help='folder with proto_sessions.csv and proto_primitives.csv')
    ap.add_argument('--out', default=os.path.join(HERE, 'raw_r6'))
    ap.add_argument('--workdir', default=None)
    args = ap.parse_args(argv)
    s5 = cfgmod.load_settings()
    s = c6.load_settings()
    n_missions = args.missions or int(s['missions_per_config_r6'])
    a = model.load_assumptions()
    prof = cfgmod.link_profile(args.profile)
    delays = c6.rtl_delays(args.rtl, s['rtl_core'], a['clock_hz'], s['rtl_statistic'])
    other = {}
    for core in ('ibex', 'cv32e40p'):
        if core != s['rtl_core']:
            try:
                other[core] = c6.rtl_delays(args.rtl, core, a['clock_hz'], s['rtl_statistic'])
            except (KeyError, ValueError):
                pass
    sec = c6.security_config(args.config, delays)
    rate = model.command_rate('drone')
    deadline = a['deadline_s']
    os.makedirs(args.out, exist_ok=True)
    wd = args.workdir or os.path.join(os.path.dirname(args.ardupilot), 'wp2_sitl_runs', f'r6_{args.profile}_{args.config}')
    os.makedirs(wd, exist_ok=True)
    inst = args.instance
    binary = os.path.join(args.ardupilot, 'build', 'sitl', 'bin', 'arducopter')
    defaults = os.path.join(args.ardupilot, 'Tools', 'autotest', 'default_params', 'copter.parm')
    base_seed = c6.run_seed(s, args.profile, args.first)
    params = {'SERIAL1_PROTOCOL': 2, 'FS_GCS_ENABLE': 0, 'AUTO_OPTIONS': 3, 'MIS_RESTART': 1,
              'LAND_SPD_MS': s5['land_speed_m_s'], 'WP_SPD': s5['wp_speed_m_s'],
              'MAV1_POSITION': 2, 'MAV1_EXT_STAT': 2,
              'MAV2_EXTRA1': s5['sr_extra1_hz'], 'MAV2_POSITION': s5['sr_position_hz'], 'MAV2_EXTRA2': s5['sr_extra2_hz'],
              'MAV2_EXT_STAT': s5['sr_ext_stat_hz'], 'MAV2_EXTRA3': s5['sr_extra3_hz'],
              'MAV2_RAW_SENS': s5['sr_other_hz'], 'MAV2_RC_CHAN': s5['sr_other_hz'], 'MAV2_RAW_CTRL': s5['sr_other_hz'],
              'MAV2_ADSB': s5['sr_other_hz'], 'MAV2_PARAMS': s5['sr_other_hz']}
    parm = os.path.join(wd, 'sitl_study.parm')
    with open(parm, 'w') as fh:
        for k, v in params.items():
            fh.write(f'{k} {float(v):g}\n')
    log = open(os.path.join(wd, 'arducopter.log'), 'w')
    proc = subprocess.Popen([binary, '-w', '--model', '+', '--speedup', '1', '--defaults', defaults + ',' + parm,
                             '-I', str(inst)], cwd=wd, stdout=log, stderr=subprocess.STDOUT)
    relay = None
    try:
        time.sleep(3)
        obs = mavutil.mavlink_connection(f'tcp:127.0.0.1:{5760 + 10 * inst}', source_system=250, source_component=191,
                                         autoreconnect=True)
        obs.wait_heartbeat(timeout=60)
        param_ok = {k: set_param(obs, k, v) for k, v in params.items()}
        key = None
        if args.config == 'signing':
            key = random.Random(base_seed).randbytes(32)
            ts = int((time.time() - 1420070400) * 100000)
            obs.mav.setup_signing_send(1, 1, key, ts)
            time.sleep(1.0)
        relay = gwrelay.GatewayRelay(prof, sec, base_seed, 14600 + inst, ('127.0.0.1', 5762 + 10 * inst),
                                     queue_limit_bytes=int(s5['queue_limit_bytes']))
        relay.stream_cmd_id = int(s5['stream_cmd_id'])
        relay.start()
        time.sleep(0.5)
        link = mavutil.mavlink_connection(f'udpout:127.0.0.1:{14600 + inst}', source_system=255, source_component=190)
        if key is not None:
            link.setup_signing(key, sign_outgoing=True)
        gcs = Gcs(link, obs, relay, s5, rate)
        dbg(f'params {param_ok}')
        missions = []
        for i in range(args.first, args.first + n_missions):
            seed = c6.run_seed(s, args.profile, i)
            rng = random.Random(seed)
            o_start = rng.uniform(s5['outage_window_start_s'], s5['outage_window_end_s'])
            o_dur = rng.expovariate(1.0 / a['outage_mean_s'])
            with relay.lock:
                relay.chan.rng.seed(seed)
            gcs.mission = i
            rec = dict(profile=args.profile, config=args.config, mission=i, seed=seed, outage_start_after_arm_s=o_start,
                       outage_duration_s=o_dur, handshake_s=float('nan'), completed=0, t_arm=float('nan'),
                       t_disarm=float('nan'), upload_ok=0, arm_ok=0, t_mission_start=time.monotonic())
            gcs.pump(1.0)
            dbg(f'mission {i} start')
            if sec['session']:
                relay.auto_rehandshake = False
                n_done = len(relay.hs_times)
                t_hs = time.monotonic()
                relay.start_session()
                while not relay.session_up() and time.monotonic() - t_hs < 60:
                    gcs.pump(0.01)
                if len(relay.hs_times) > n_done:
                    hid, hs0, hs1 = relay.hs_times[-1]
                    rec['handshake_s'] = hs1 - hs0
                relay.auto_rehandshake = True
            t_w = time.monotonic()
            while time.monotonic() - gcs.link_hb > 2.0 and time.monotonic() - t_w < 30:
                gcs.pump(0.05)
            gcs.pos = None
            t_w = time.monotonic()
            while gcs.pos is None or gcs.pos[0] == 0 or not any('using GPS' in x for _, x in gcs.statustext):
                gcs.pump(0.1)
                if time.monotonic() - t_w > 20:
                    dbg('no position yet')
                    t_w = time.monotonic()
            items = mission_items(gcs.pos[0], gcs.pos[1], s5)
            rec['upload_ok'] = int(gcs.upload(items))
            gcs.command(mavutil.mavlink.MAV_CMD_DO_SET_MODE, [1, MODE_GUIDED])
            gcs.command(mavutil.mavlink.MAV_CMD_DO_SET_MODE, [1, MODE_AUTO])
            t_a = time.monotonic()
            armed = False
            while time.monotonic() - t_a < 180 and not armed:
                gcs.link.mav.command_long_send(1, 1, mavutil.mavlink.MAV_CMD_COMPONENT_ARM_DISARM, 0, 1, 0, 0, 0, 0, 0, 0)
                t_c = time.monotonic()
                while time.monotonic() - t_c < 2.0:
                    gcs.pump(0.02)
                    if gcs.armed_obs:
                        armed = True
                        break
            rec['arm_ok'] = int(armed)
            if not armed:
                missions.append(rec)
                continue
            t_arm = time.monotonic()
            rec['t_arm'] = t_arm
            relay.add_outage(t_arm + o_start, t_arm + o_start + o_dur)
            gcs.phase_rng = random.Random(seed * 7 + 1)
            gcs.t_stream0 = t_arm
            gcs.k_cmd = 0
            gcs.next_cmd = t_arm + gcs.phase_rng.random() * gcs.period
            gcs.streaming = True
            max_seq = 0
            while time.monotonic() - t_arm < s5['mission_timeout_s']:
                gcs.pump(0.05)
                max_seq = max(max_seq, gcs.mission_current_obs)
                if not gcs.armed_obs:
                    break
            gcs.streaming = False
            rec['t_disarm'] = time.monotonic()
            rec['max_mission_seq'] = max_seq
            rec['completed'] = int((not gcs.armed_obs) and max_seq >= len(items) - 1)
            gcs.pump(2.0)
            missions.append(rec)
            print(f'{args.profile} {args.config} mission {i} completed={rec["completed"]} '
                  f'flight={rec["t_disarm"] - t_arm:.1f}s hs={rec["handshake_s"]:.3f}', flush=True)
        gcs.pump(3.0)
        relay.stop()
        relay.join(timeout=5)
        write_outputs(args, relay, gcs, missions, prof, sec, delays, base_seed, param_ok, deadline, rate, other)
    finally:
        if relay is not None:
            relay.stop()
        proc.terminate()
        try:
            proc.wait(timeout=10)
        except subprocess.TimeoutExpired:
            proc.kill()
        log.close()


def rtl_hashes(rtl_dir):
    import hashlib
    out = {}
    for fn in ('proto_sessions.csv', 'proto_primitives.csv'):
        with open(os.path.join(rtl_dir, fn), 'rb') as f:
            out[fn] = hashlib.sha256(f.read()).hexdigest()
    return out


def _f(x):
    return '' if x is None else f'{x:.6f}'


def write_outputs(args, relay, gcs, missions, prof, sec, delays, base_seed, param_ok, deadline, rate, other):
    tag = f'{args.profile}_{args.config}'
    if args.first:
        tag += f'_from{args.first}'
    cmds = relay.cmds
    sends = gcs.sends
    n = min(len(cmds), len(sends))
    with open(os.path.join(args.out, f'{tag}_commands.csv'), 'w', newline='') as f:
        w = csv.writer(f)
        w.writerow(['profile', 'config', 'mission', 'idx', 't_send', 't_relay_in', 't_gateway', 't_vehicle',
                    't_vehicle_ack', 't_ground_ack', 'result', 'dropped', 'link_up_at_send', 'counter', 'epoch'])
        for k in range(n):
            c = cmds[k]
            w.writerow([args.profile, args.config, sends[k][1], k, f'{sends[k][0]:.6f}', f'{c["t_relay_in"]:.6f}',
                        _f(c.get('t_gateway')), _f(c['t_vehicle']), _f(c['t_vehicle_ack']), _f(c['t_ground_ack']),
                        '' if c['result'] is None else c['result'], c['dropped'] or '', int(c['link_up_at_send']),
                        '' if c.get('counter') is None else c['counter'], '' if c.get('epoch') is None else c['epoch']])
    keys = ['profile', 'config', 'mission', 'seed', 'outage_start_after_arm_s', 'outage_duration_s', 'handshake_s',
            'completed', 't_mission_start', 't_arm', 't_disarm', 'upload_ok', 'arm_ok', 'max_mission_seq']
    with open(os.path.join(args.out, f'{tag}_missions.csv'), 'w', newline='') as f:
        w = csv.DictWriter(f, fieldnames=keys, extrasaction='ignore')
        w.writeheader()
        for r in missions:
            w.writerow({k: r.get(k, '') for k in keys})
    with open(os.path.join(args.out, f'{tag}_events.csv'), 'w', newline='') as f:
        w = csv.writer(f)
        w.writerow(['event', 't', 'handshake_id'])
        for e in relay.session_events:
            w.writerow([e[0], f'{e[1]:.6f}', e[2]])
        for s_, e_ in relay.chan.outages:
            w.writerow(['outage_start', f'{s_:.6f}', ''])
            w.writerow(['outage_end', f'{e_:.6f}', ''])
    with open(os.path.join(args.out, f'{tag}_arrivals.csv'), 'w', newline='') as f:
        w = csv.writer(f)
        w.writerow(['t', 'epoch', 'counter', 'accepted', 'reason', 'msgid'])
        for r in relay.arrivals:
            w.writerow([f'{r[0]:.6f}', r[1], r[2], r[3], r[4], r[5]])
    sec_out = {k: v for k, v in sec.items() if k != 'delays'}
    info = dict(profile=args.profile, config=args.config, base_seed=base_seed, link_profile=prof, security=sec_out,
                rtl_delays=delays, rtl_delays_other_cores=other or {}, rtl_files_sha256=rtl_hashes(args.rtl), params_ok=param_ok, deadline_s=deadline, command_rate_hz=rate,
                commands_sent=len(sends), commands_seen_by_relay=len(cmds), channel_stats=relay.chan.stats,
                relay_drops=dict(relay.drops), frame_counts=dict(relay.frame_counts), gateway=relay.gateway_stats(),
                libraries=library_versions(),
                flight_stack='ArduPilot Copter 4.7.2 SITL, built in multicopter model (--model +), speedup 1',
                pymavlink=getattr(__import__('pymavlink'), '__version__', 'unknown'), python=sys.version.split()[0],
                statustext=[t for _, t in gcs.statustext][-50:], t_relay_start=relay.t0, t_end=time.monotonic())
    with open(os.path.join(args.out, f'{tag}_run.json'), 'w') as f:
        json.dump(info, f, indent=1, default=str)


if __name__ == '__main__':
    sys.exit(main())
