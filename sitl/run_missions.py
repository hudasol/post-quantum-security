"""Run scripted missions of an ArduPilot Copter software in the loop vehicle through the emulated link.

One invocation runs one configuration on one link profile: it starts the flight stack headless with
its built in multicopter model, provisions parameters over the wired SERIAL0 port (which is not
emulated and also serves as an observer of the true vehicle state), starts the relay between a
pymavlink ground station and SERIAL1, and flies the requested number of missions:
upload (takeoff, two legs, land), mode AUTO, arm, a stream of COMMAND_LONG commands at the mission
study command rate until the vehicle has landed and disarmed. Each mission has one link outage with
a start drawn uniformly from a window during the legs and an exponential duration with the mission
study mean. All draws use the run seed, which is stored in the output.

Usage (from the repository root, with the flight stack built by sitl/fetch.sh):
  python3 -m sitl.run_missions --config hybrid --profile sik --missions 20 --instance 0
Outputs: sitl/raw/<profile>_<config>_missions.csv, sitl/raw/<profile>_<config>_commands.csv,
sitl/raw/<profile>_<config>_events.csv and sitl/raw/<profile>_<config>_run.json.
"""
import argparse
import csv
import json
import math
import os
import random
import subprocess
import sys
import time

from pymavlink import mavutil

from . import config as cfgmod
from . import linkrelay
from mission import model

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
AP_DEFAULT = os.environ.get('SITL_ARDUPILOT', os.path.join(os.path.dirname(ROOT), 'third_party', 'wp2_ardupilot'))

MODE_AUTO = 3
MODE_GUIDED = 4


def dbg(msg):
    print(f'[{time.strftime("%H:%M:%S")}] {msg}', file=sys.stderr, flush=True)


def run_seed(settings, profile, config, i):
    return int(settings['seed']) + 1000 * cfgmod.PROFILES.index(profile) + 100 * cfgmod.CONFIGS.index(config) + i


class Gcs:
    """Ground station state machine helpers around a pymavlink link (emulated) and an observer link (wired)."""

    def __init__(self, link, obs, relay, settings, rate_hz):
        self.link = link
        self.obs = obs
        self.relay = relay
        self.s = settings
        self.period = 1.0 / rate_hz
        self.next_hb = 0.0
        self.streaming = False
        self.next_cmd = None
        self.sends = []  # (send time, mission index)
        self.mission = -1
        self.acks = []
        self.armed_obs = False
        self.mission_current_obs = 0
        self.pos = None
        self.link_hb = 0.0
        self.mission_req = None
        self.mission_ack = None
        self.statustext = []
        self.obs_types = set()
        self.link_types = set()

    def pump(self, dt):
        """Process both links for dt seconds, sending ground heartbeats and the command stream when due."""
        end = time.monotonic() + dt
        while True:
            now = time.monotonic()
            if now >= self.next_hb:
                self.link.mav.heartbeat_send(mavutil.mavlink.MAV_TYPE_GCS, mavutil.mavlink.MAV_AUTOPILOT_INVALID, 0, 0, 0)
                self.next_hb = now + 1.0
            if self.streaming and now >= self.next_cmd:
                self.k_cmd += 1
                self.next_cmd = self.t_stream0 + (self.k_cmd + self.phase_rng.random()) * self.period
                self.sends.append((time.monotonic(), self.mission))
                self.link.mav.command_long_send(1, 1, int(self.s['stream_cmd_id']), 0, self.s['stream_servo'],
                                                self.s['stream_pwm_us'], 0, 0, 0, 0, 0)
            while True:
                m = self.link.recv_match(blocking=False)
                if m is None:
                    break
                self._on_link(m)
            while True:
                m = self.obs.recv_match(blocking=False)
                if m is None:
                    break
                self._on_obs(m)
            if now >= end:
                return
            time.sleep(min(0.002, max(0.0, end - now)))

    def _on_link(self, m):
        t = m.get_type()
        self.link_types.add(t)
        if t == 'HEARTBEAT' and m.get_srcSystem() == 1:
            self.link_hb = time.monotonic()
        elif t == 'COMMAND_ACK':
            self.acks.append((time.monotonic(), m.command, m.result))
        elif t in ('MISSION_REQUEST', 'MISSION_REQUEST_INT'):
            self.mission_req = m.seq
        elif t == 'MISSION_ACK':
            self.mission_ack = m.type

    def _on_obs(self, m):
        t = m.get_type()
        self.obs_types.add(t)
        if t == 'HEARTBEAT' and m.get_srcSystem() == 1:
            self.armed_obs = bool(m.base_mode & mavutil.mavlink.MAV_MODE_FLAG_SAFETY_ARMED)
        elif t == 'MISSION_CURRENT':
            self.mission_current_obs = m.seq
        elif t == 'GLOBAL_POSITION_INT':
            self.pos = (m.lat, m.lon)
            self.obs_seen_pos = True
        elif t == 'STATUSTEXT':
            self.statustext.append((time.monotonic(), m.text))

    def command(self, cmd, params, timeout=2.0, tries=30):
        """Send a command until it is acknowledged as accepted; returns True on success."""
        for _ in range(tries):
            self.acks = [a for a in self.acks if a[1] != cmd]
            p = list(params) + [0] * (7 - len(params))
            self.link.mav.command_long_send(1, 1, cmd, 0, *p)
            t_end = time.monotonic() + timeout
            while time.monotonic() < t_end:
                self.pump(0.02)
                for a in self.acks:
                    if a[1] == cmd:
                        if a[2] == mavutil.mavlink.MAV_RESULT_ACCEPTED:
                            return True
                        t_end = time.monotonic()  # rejected, retry after the wait
                        break
            self.pump(0.5)
        return False

    def upload(self, items, timeout=3.0, tries=20):
        n = len(items)
        for _ in range(tries):
            self.mission_req = None
            self.mission_ack = None
            self.link.mav.mission_count_send(1, 1, n, 0)
            last = time.monotonic()
            while time.monotonic() - last < timeout:
                self.pump(0.01)
                if self.mission_req is not None:
                    k = self.mission_req
                    self.mission_req = None
                    if 0 <= k < n:
                        self.link.mav.mission_item_int_send(1, 1, k, *items[k])
                        last = time.monotonic()
                if self.mission_ack is not None:
                    if self.mission_ack == 0:
                        return True
                    break
        return False


def mission_items(lat, lon, s):
    """Takeoff, a leg north, a leg east, land; MISSION_ITEM_INT fields after seq."""
    dlat = s['leg_m'] / 111320.0
    dlon = s['leg_m'] / (111320.0 * math.cos(math.radians(lat / 1e7)))
    rel = mavutil.mavlink.MAV_FRAME_GLOBAL_RELATIVE_ALT_INT
    alt = s['takeoff_alt_m']
    wp = mavutil.mavlink.MAV_CMD_NAV_WAYPOINT
    lat2 = lat + int(dlat * 1e7)
    lon3 = lon + int(dlon * 1e7)

    def it(cmd, la, lo, al):
        return (rel, cmd, 0, 1, 0, 0, 0, 0, la, lo, al, 0)
    return [it(wp, lat, lon, 0), it(mavutil.mavlink.MAV_CMD_NAV_TAKEOFF, lat, lon, alt), it(wp, lat2, lon, alt),
            it(wp, lat2, lon3, alt), it(mavutil.mavlink.MAV_CMD_NAV_LAND, lat2, lon3, 0)]


def set_param(conn, name, value, timeout=5.0):
    for _ in range(5):
        conn.mav.param_set_send(1, 1, name.encode(), float(value), mavutil.mavlink.MAV_PARAM_TYPE_REAL32)
        t_end = time.monotonic() + timeout / 5
        while time.monotonic() < t_end:
            m = conn.recv_match(type='PARAM_VALUE', blocking=True, timeout=0.2)
            if m is not None and m.param_id == name and abs(m.param_value - float(value)) < 1e-3:
                return True
    return False


def main(argv=None):
    ap = argparse.ArgumentParser()
    ap.add_argument('--config', choices=cfgmod.CONFIGS, required=True)
    ap.add_argument('--profile', choices=cfgmod.PROFILES, default='sik')
    ap.add_argument('--missions', type=int, default=None)
    ap.add_argument('--instance', type=int, default=0)
    ap.add_argument('--ardupilot', default=AP_DEFAULT)
    ap.add_argument('--out', default=os.path.join(HERE, 'raw'))
    ap.add_argument('--workdir', default=None)
    args = ap.parse_args(argv)
    s = cfgmod.load_settings()
    n_missions = args.missions or int(s['missions_per_config'])
    a = model.load_assumptions()
    prof = cfgmod.link_profile(args.profile)
    sec = cfgmod.security_config(args.config)
    rate = model.command_rate('drone')
    deadline = a['deadline_s']
    os.makedirs(args.out, exist_ok=True)
    wd = args.workdir or os.path.join(os.path.dirname(args.ardupilot), 'wp2_sitl_runs', f'{args.profile}_{args.config}')
    os.makedirs(wd, exist_ok=True)
    inst = args.instance
    binary = os.path.join(args.ardupilot, 'build', 'sitl', 'bin', 'arducopter')
    defaults = os.path.join(args.ardupilot, 'Tools', 'autotest', 'default_params', 'copter.parm')
    base_seed = run_seed(s, args.profile, args.config, 0)
    # MAVn stream rate groups: MAV1 is SERIAL0 (wired observer), MAV2 is SERIAL1 (emulated link)
    params = {'SERIAL1_PROTOCOL': 2, 'FS_GCS_ENABLE': 0, 'AUTO_OPTIONS': 3, 'MIS_RESTART': 1,
          'LAND_SPD_MS': s['land_speed_m_s'], 'WP_SPD': s['wp_speed_m_s'],
          'MAV1_POSITION': 2, 'MAV1_EXT_STAT': 2,
          'MAV2_EXTRA1': s['sr_extra1_hz'], 'MAV2_POSITION': s['sr_position_hz'], 'MAV2_EXTRA2': s['sr_extra2_hz'],
          'MAV2_EXT_STAT': s['sr_ext_stat_hz'], 'MAV2_EXTRA3': s['sr_extra3_hz'],
          'MAV2_RAW_SENS': s['sr_other_hz'], 'MAV2_RC_CHAN': s['sr_other_hz'], 'MAV2_RAW_CTRL': s['sr_other_hz'],
          'MAV2_ADSB': s['sr_other_hz'], 'MAV2_PARAMS': s['sr_other_hz']}
    parm = os.path.join(wd, 'sitl_study.parm')
    with open(parm, 'w') as fh:
        for k, v in params.items():
            fh.write(f'{k} {float(v):g}\n')
    log = open(os.path.join(wd, 'arducopter.log'), 'w')
    proc = subprocess.Popen([binary, '-w', '--model', '+', '--speedup', '1', '--defaults', defaults + ',' + parm, '-I', str(inst)],
                            cwd=wd, stdout=log, stderr=subprocess.STDOUT)
    relay = None
    try:
        time.sleep(3)
        obs = mavutil.mavlink_connection(f'tcp:127.0.0.1:{5760 + 10 * inst}', source_system=250, source_component=191,
                                         autoreconnect=True)
        obs.wait_heartbeat(timeout=60)
        # the parameters are loaded at boot from a defaults file; the wired port checks each value
        param_ok = {k: set_param(obs, k, v) for k, v in params.items()}
        key = None
        if args.config == 'signing':
            # provisioning over the wired port, as the flight stack documents; a test key drawn from the run seed
            key = random.Random(base_seed).randbytes(32)
            ts = int((time.time() - 1420070400) * 100000)
            obs.mav.setup_signing_send(1, 1, key, ts)
            time.sleep(1.0)
        relay = linkrelay.Relay(prof, sec, base_seed, 14600 + inst, ('127.0.0.1', 5762 + 10 * inst),
                                queue_limit_bytes=int(s['queue_limit_bytes']))
        relay.stream_cmd_id = int(s['stream_cmd_id'])
        relay.start()
        time.sleep(0.5)
        link = mavutil.mavlink_connection(f'udpout:127.0.0.1:{14600 + inst}', source_system=255, source_component=190)
        if key is not None:
            link.setup_signing(key, sign_outgoing=True)
        gcs = Gcs(link, obs, relay, s, rate)
        dbg(f'params {param_ok}')
        missions = []
        for i in range(n_missions):
            seed = run_seed(s, args.profile, args.config, i)
            rng = random.Random(seed)
            o_start = rng.uniform(s['outage_window_start_s'], s['outage_window_end_s'])
            o_dur = rng.expovariate(1.0 / a['outage_mean_s'])
            gcs.mission = i
            rec = dict(profile=args.profile, config=args.config, mission=i, seed=seed, outage_start_after_arm_s=o_start,
                       outage_duration_s=o_dur, handshake_s=float('nan'), completed=0, t_arm=float('nan'),
                       t_disarm=float('nan'), upload_ok=0, arm_ok=0)
            gcs.pump(1.0)
            dbg(f'mission {i} start')
            if sec['session']:
                relay.auto_rehandshake = False
                t_hs = time.monotonic()
                relay.start_session()
                while not relay.session_up() and time.monotonic() - t_hs < 60:
                    gcs.pump(0.01)
                if relay.hs_times:
                    hid, hs0, hs1 = relay.hs_times[-1]
                    rec['handshake_s'] = hs1 - hs0
                relay.auto_rehandshake = True
            # wait for the link heartbeat
            dbg('waiting link heartbeat')
            t_w = time.monotonic()
            while time.monotonic() - gcs.link_hb > 2.0 and time.monotonic() - t_w < 30:
                gcs.pump(0.05)
            dbg(f'link hb age {time.monotonic() - gcs.link_hb:.1f} s')
            gcs.pos = None
            t_w = time.monotonic()
            while gcs.pos is None or gcs.pos[0] == 0 or not any('using GPS' in x for _, x in gcs.statustext):
                gcs.pump(0.1)
                if time.monotonic() - t_w > 20:
                    dbg(f'no position yet; obs types {sorted(gcs.obs_types)} link types {sorted(gcs.link_types)}')
                    t_w = time.monotonic()
            items = mission_items(gcs.pos[0], gcs.pos[1], s)
            dbg('uploading')
            rec['upload_ok'] = int(gcs.upload(items))
            dbg(f'upload {rec["upload_ok"]}')
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
            dbg(f'armed {armed} {gcs.statustext[-3:]}')
            if not armed:
                missions.append(rec)
                continue
            t_arm = time.monotonic()
            rec['t_arm'] = t_arm
            relay.add_outage(t_arm + o_start, t_arm + o_start + o_dur)
            # command k is sent at t_arm + (k + u_k) x period with u_k uniform from the run seed, so that the
            # commands sample every phase of the flight stack's periodic telemetry instead of locking to one phase
            gcs.phase_rng = random.Random(seed * 7 + 1)
            gcs.t_stream0 = t_arm
            gcs.k_cmd = 0
            gcs.next_cmd = t_arm + gcs.phase_rng.random() * gcs.period
            gcs.streaming = True
            max_seq = 0
            while time.monotonic() - t_arm < s['mission_timeout_s']:
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
        write_outputs(args, relay, gcs, missions, prof, sec, base_seed, param_ok, deadline, rate)
    finally:
        if relay is not None:
            relay.stop()
        proc.terminate()
        try:
            proc.wait(timeout=10)
        except subprocess.TimeoutExpired:
            proc.kill()
        log.close()


def write_outputs(args, relay, gcs, missions, prof, sec, base_seed, param_ok, deadline, rate):
    tag = f'{args.profile}_{args.config}'
    cmds = relay.cmds
    sends = gcs.sends
    n = min(len(cmds), len(sends))
    with open(os.path.join(args.out, f'{tag}_commands.csv'), 'w', newline='') as f:
        w = csv.writer(f)
        w.writerow(['profile', 'config', 'mission', 'idx', 't_send', 't_relay_in', 't_vehicle', 't_vehicle_ack',
                    't_ground_ack', 'result', 'dropped', 'link_up_at_send'])
        for k in range(n):
            c = cmds[k]
            w.writerow([args.profile, args.config, sends[k][1], k, f'{sends[k][0]:.6f}', f'{c["t_relay_in"]:.6f}',
                        '' if c['t_vehicle'] is None else f'{c["t_vehicle"]:.6f}',
                        '' if c['t_vehicle_ack'] is None else f'{c["t_vehicle_ack"]:.6f}',
                        '' if c['t_ground_ack'] is None else f'{c["t_ground_ack"]:.6f}',
                        '' if c['result'] is None else c['result'], c['dropped'] or '', int(c['link_up_at_send'])])
    keys = ['profile', 'config', 'mission', 'seed', 'outage_start_after_arm_s', 'outage_duration_s', 'handshake_s',
            'completed', 't_arm', 't_disarm', 'upload_ok', 'arm_ok', 'max_mission_seq']
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
    st = relay.chan.stats
    info = dict(profile=args.profile, config=args.config, base_seed=base_seed, link_profile=prof, security=sec,
                params_ok=param_ok, deadline_s=deadline, command_rate_hz=rate, commands_sent=len(sends),
                commands_seen_by_relay=len(cmds), channel_stats=st, relay_drops=dict(relay.drops), frame_counts=dict(relay.frame_counts),
                flight_stack='ArduPilot Copter 4.7.2 SITL, built in multicopter model (--model +), speedup 1',
                pymavlink=getattr(__import__('pymavlink'), '__version__', 'unknown'), python=sys.version.split()[0],
                statustext=[t for _, t in gcs.statustext][-50:], t_relay_start=relay.t0, t_end=time.monotonic())
    with open(os.path.join(args.out, f'{tag}_run.json'), 'w') as f:
        json.dump(info, f, indent=1, default=str)


if __name__ == '__main__':
    sys.exit(main())
