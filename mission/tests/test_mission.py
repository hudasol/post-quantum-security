"""Unit tests for the mission study (python3 -m unittest discover -s mission/tests -t .)."""
import math
import os
import unittest

import numpy as np
import pandas as pd

from mission import model, sim, study, run_all


class TestModel(unittest.TestCase):
    def test_link_params_and_assumptions(self):
        p = model.load_link_params()
        self.assertEqual(p['mav_sig_field_bytes'], 13)
        a = model.load_assumptions()
        self.assertEqual(int(a['seed']), 20261020)

    def test_payloads_host_measured(self):
        pl = model.load_payloads()
        self.assertEqual(pl['HEARTBEAT'], 9)
        self.assertEqual(pl['COMMAND_LONG'], 33)

    def test_traffic_has_one_command_per_vehicle(self):
        tr = model.load_traffic()
        for v in ['drone', 'robot']:
            self.assertEqual(len([r for r in tr if r['vehicle'] == v and r['role'] == 'command']), 1)
        self.assertEqual(model.command_rate('drone'), 1.0)

    def test_cycle_table(self):
        c = model.cycle_table()
        self.assertEqual(c['mldsa44_verify'][0], 1421623)
        self.assertEqual(c['ed25519_verify'][0], 1360800)
        self.assertEqual(c['x25519_two_mults'][0], 2 * 913800)
        self.assertEqual(c['x25519_two_mults'][3], 2 * 476275)
        self.assertEqual(c['x25519_two_mults'][4], 2 * 1036600)
        self.assertEqual(c['ed25519_verify'][3], 722000)
        self.assertEqual(c['ed25519_verify'][4], 1463600)
        with self.assertRaises(KeyError):
            model.evidence_cycles(['NO-SUCH-ROW'])

    def test_handshake_bytes(self):
        self.assertEqual(model.handshake_bytes('B'), 4772)
        self.assertEqual(model.handshake_bytes('A'), 144)
        self.assertEqual(model.handshake_bytes('C'), 0)
        self.assertEqual(model.handshake_bytes('D'), 0)
        with self.assertRaises(ValueError):
            model.arch_profile('Z')

    def test_link_frames(self):
        sik = model.link_profile('sik')
        self.assertAlmostEqual(sik['rate'], 57600)
        self.assertAlmostEqual(model.link_frames(72, sik)[0], 72 * 8 / 57600)
        z = model.link_profile('ieee802154')
        self.assertEqual(len(model.link_frames(100, z)), 2)
        self.assertAlmostEqual(model.link_frames(100, z)[0], 127 * 8 / 250000)
        lo = model.link_profile('lora_dr0')
        self.assertEqual(len(model.link_frames(78, lo)), 2)
        self.assertEqual(lo['duty'], 0.01)
        with self.assertRaises(ValueError):
            model.link_profile('wifi')

    def test_frame_and_object_sizes(self):
        self.assertEqual(model.mav_frame_bytes(33, 13), 58)
        sik = model.link_profile('sik')
        fr = model.object_frames(2420, sik)
        self.assertEqual(len(fr), math.ceil(2420 / 239))

    def test_command_frames_c_is_larger(self):
        sik = model.link_profile('sik')
        a, b = model.command_frames('drone', 'C', sik)
        self.assertGreater(sum(a), 10 * sum(b))
        a2, _ = model.command_frames('drone', 'A', sik)
        self.assertAlmostEqual(sum(a2) - sum(b), 13 * 8 / 57600)

    def test_telemetry_load(self):
        sik = model.link_profile('sik')
        air, msgs, fr = model.telemetry_load('drone', 'A', sik)
        self.assertGreater(air, 0)
        self.assertGreater(msgs, 10)
        d = model.telemetry_load_by_dir('drone', 'A', sik)
        self.assertAlmostEqual(d['up'] + d['down'], air)

    def test_phases(self):
        ph = model.mission_phases('drone')
        self.assertEqual(ph[0][0], 'preflight')
        self.assertEqual(ph[-1][2], 750)
        self.assertEqual(model.mission_phases('robot')[-1][2], 960)


class TestSim(unittest.TestCase):
    def test_merge_and_overlap(self):
        s, e = sim.merge_intervals([(5, 7), (1, 3), (2, 4), (9, 9)])
        self.assertEqual(list(s), [1, 5])
        self.assertEqual(list(e), [4, 7])
        o = sim.overlaps(s, e, np.array([0, 4.5, 6, 8]), np.array([0.5, 4.8, 6.1, 10]))
        self.assertEqual(list(o), [False, False, True, False])
        self.assertFalse(sim.overlaps(np.zeros(0), np.zeros(0), np.array([1.0]), np.array([2.0]))[0])

    def test_lindley(self):
        st = sim.lindley(np.array([0.0, 0.1, 5.0]), np.array([1.0, 1.0, 1.0]))
        self.assertEqual(list(st), [0.0, 1.0, 5.0])

    def test_transfer_through_outages(self):
        self.assertAlmostEqual(sim.transfer_through_outages(0, 10, np.array([2.0]), np.array([5.0])), 13)
        self.assertAlmostEqual(sim.transfer_through_outages(0, 1, np.array([2.0]), np.array([5.0])), 1)

    def test_rng_deterministic(self):
        self.assertEqual(sim.rng_for('x').random(), sim.rng_for('x').random())
        self.assertNotEqual(sim.rng_for('x').random(), sim.rng_for('y').random())

    def test_sample_flight_no_loss(self):
        link = model.link_profile('sik')
        t, air = sim.sample_flight(sim.rng_for('f'), [0.01, 0.01], link, 0.0, 0.001)
        self.assertAlmostEqual(t, 0.02 + link['turnaround'] + 0.001)
        self.assertAlmostEqual(air, 0.021)

    def test_sample_outages(self):
        s, e = sim.sample_outages(sim.rng_for('o'), 3600, 0, 5)
        self.assertEqual(len(s), 0)
        s, e = sim.sample_outages(sim.rng_for('o'), 36000, 60, 5)
        self.assertGreater(len(s), 300)

    def test_session_timeline_no_outage(self):
        cfg = sim.build_config('drone', 'B', 'sik', frame_loss=0.0, rekey_interval_s=math.inf)
        st = sim.session_timeline(sim.rng_for('s'), cfg, cfg['T'], np.zeros(0), np.zeros(0))
        self.assertEqual(st['n_hs'], 1)
        self.assertEqual(st['ttra'], [])

    def test_session_teardown(self):
        cfg = sim.build_config('drone', 'A', 'sik', frame_loss=0.0, rekey_interval_s=math.inf)
        st = sim.session_timeline(sim.rng_for('s'), cfg, cfg['T'], np.array([100.0]), np.array([150.0]))
        self.assertEqual(st['n_hs'], 2)
        self.assertEqual(len(st['ttra']), 1)

    def test_run_config_deterministic_and_bounds(self):
        r1, _ = sim.run_config('drone', 'D', 'sik', 3, [0.5])
        r2, _ = sim.run_config('drone', 'D', 'sik', 3, [0.5])
        self.assertEqual(r1[0]['avail'], r2[0]['avail'])
        for r in r1:
            self.assertTrue(0 <= r['avail'] <= 1)
            self.assertEqual(r['n_handshakes'], 0)

    def test_no_loss_no_outage_full_availability(self):
        r, _ = sim.run_config('drone', 'A', 'ieee802154', 2, [0.5], frame_loss=0.0, outage_rate_per_h=0.0)
        self.assertEqual(r[0]['avail'], 1.0)

    def test_overrides(self):
        cfg = sim.build_config('drone', 'A', 'lora_dr5', cmd_rate=0.5, tel_scale=0.0)
        self.assertEqual(cfg['cmd_rate'], 0.5)
        self.assertEqual(cfg['tel_air'], 0.0)


class TestStudy(unittest.TestCase):
    def test_boot_ci(self):
        pt, lo, hi = study.boot_ci(np.arange(100.0))
        self.assertTrue(lo <= pt <= hi)
        self.assertTrue(math.isnan(study.boot_ci([float('nan')])[0]))
        pt, lo, hi = study.boot_ci(np.arange(100.0), stat=np.mean)
        self.assertAlmostEqual(pt, 49.5)
        self.assertTrue(lo < pt < hi)

    def test_job_row(self):
        row = study._job(('drone', 'A', 'sik', 3, {}, 'test'))
        self.assertEqual(row['label'], 'estimated')
        self.assertIn('avail_median', row)
        self.assertEqual(row['seed'], 20261020)

    def test_envelope(self):
        cols = {f'avail_mean_{d:g}': 1.0 for d in study.DEADLINES}
        df = pd.DataFrame([dict(vehicle='drone', link='sik', arch='A', tag='base', utilisation_median=0.1,
                                utilisation_down_median=float('nan'), first_session_s_median=1.0, **cols),
                           dict(vehicle='drone', link='lora_dr0', arch='A', tag='base', utilisation_median=5.0,
                                utilisation_down_median=float('nan'), first_session_s_median=1.0, **cols)])
        env = study.envelope(df, 0.99)
        self.assertTrue(env[env.link == 'sik'].feasible.all())
        self.assertFalse(env[env.link == 'lora_dr0'].feasible.any())
        self.assertIn('label', env.columns)

    def test_compute_latency_table(self):
        comp, src = study.compute_latency_table()
        r = comp[(comp.arch == 'C')].iloc[0]
        self.assertAlmostEqual(r.ms_at_168MHz, 1421623 / 168e6 * 1e3)
        self.assertIn('label', src.columns)

    def test_link_crosscheck(self):
        cc = study.link_crosscheck()
        self.assertEqual(len(cc), 2)
        self.assertTrue((cc.mission_model_s > 0).all())

    def test_job_lists(self):
        self.assertEqual(len(study.base_jobs(1)), 32)
        self.assertTrue(all(j[1] in ('A', 'B') for j in study.sweep_jobs(1) if j[5] == 'sweep:rekey_interval_s'))
        self.assertEqual(len(study.lowrate_jobs(1)), 16)


class TestRunAll(unittest.TestCase):
    def test_fmt(self):
        self.assertEqual(run_all.fmt(float('nan')), 'n/a')
        self.assertEqual(run_all.fmt(3), '3')
        self.assertEqual(run_all.fmt(0.5), '0.500')
        self.assertEqual(run_all.fmt(math.inf), 'inf')

    def test_md_table(self):
        t = run_all.md_table(pd.DataFrame([dict(a=1.5, b='x')]), ['a', 'b'])
        self.assertIn('| 1.500 | x |', t)

    def test_feasible_set(self):
        env = pd.DataFrame([dict(tag='base', vehicle='drone', deadline_s=0.5, feasible=True, link='sik', arch='B')])
        self.assertEqual(run_all.feasible_set(env, 'base', 'drone', 0.5), {('sik', 'B')})

    @unittest.skipUnless(os.path.exists(os.path.join(run_all.RES, 'base.csv')), 'results not generated')
    def test_documents_generate(self):
        d = run_all.load()
        paths = {k: 'x.png' for k in ['deadline', 'loss', 'envelope']}
        self.assertIn('estimated', run_all.study_doc(d, paths))
        self.assertIn('Recommendation', run_all.arch_doc(d, paths))


if __name__ == '__main__':
    unittest.main()
