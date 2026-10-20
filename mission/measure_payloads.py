"""Measure maximum MAVLink 2 payload lengths from pymavlink generated classes (label: host measured).

Run with an interpreter that has pymavlink installed (kept outside the repository), for example
    /home/claude/work/venv_mav/bin/python mission/measure_payloads.py
Writes mission/payload_lengths.csv. The study itself only reads the CSV, so pymavlink is not a dependency.
"""
import csv
import os
import sys

MESSAGES = ['HEARTBEAT', 'SYS_STATUS', 'ATTITUDE', 'GLOBAL_POSITION_INT', 'LOCAL_POSITION_NED',
            'GPS_RAW_INT', 'VFR_HUD', 'BATTERY_STATUS', 'COMMAND_LONG', 'COMMAND_ACK',
            'SET_POSITION_TARGET_LOCAL_NED', 'SET_POSITION_TARGET_GLOBAL_INT', 'MISSION_ITEM_INT',
            'RC_CHANNELS', 'POSITION_TARGET_GLOBAL_INT', 'NAV_CONTROLLER_OUTPUT', 'SERVO_OUTPUT_RAW',
            'RAW_IMU', 'SCALED_PRESSURE', 'SYSTEM_TIME', 'MISSION_CURRENT', 'VIBRATION', 'POWER_STATUS']
OUT = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'payload_lengths.csv')


def measure(names=MESSAGES):
    """Return a list of (name, id, max_payload_bytes, crc_extra) read from pymavlink classes."""
    os.environ['MAVLINK20'] = '1'
    from pymavlink.dialects.v20 import common as m
    rows = []
    for n in names:
        cls = getattr(m, 'MAVLink_%s_message' % n.lower())
        rows.append((n, cls.id, cls.unpacker.size, cls.crc_extra))
    return rows


def main():
    try:
        import pymavlink  # noqa: F401
        from importlib.metadata import version
        ver = version('pymavlink')
    except Exception:
        print('pymavlink not available; keeping the existing', OUT)
        return 1
    rows = measure()
    with open(OUT, 'w', newline='') as f:
        w = csv.writer(f)
        w.writerow(['message', 'msg_id', 'max_payload_bytes', 'crc_extra', 'label', 'method'])
        for r in rows:
            w.writerow(list(r) + ['host measured', f'pymavlink {ver} dialects.v20.common struct size incl. extensions'])
    print('wrote', OUT)
    return 0


if __name__ == '__main__':
    sys.exit(main())
