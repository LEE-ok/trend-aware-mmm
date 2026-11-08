"""Independently compare every M2 numeric record against final-run document tables."""
import copy
import hashlib
import json
import re
import unittest
from pathlib import Path

import jsonschema

WEB = Path(__file__).resolve().parents[1]
ROOT = WEB.parents[1]
DATA = json.loads((WEB / 'data/mmm-results.json').read_text(encoding='utf-8'))


def nums(cell):
    return [float(n) for n in re.findall(r'[+-]?\d+(?:\.\d+)?', cell)]


class RecordedResultsTests(unittest.TestCase):
    def test_schema_and_reject_unknown_or_unverified_fields(self):
        schema = json.loads((WEB / 'data/mmm-results.schema.json').read_text(encoding='utf-8'))
        validator = jsonschema.Draft202012Validator(schema)
        validator.validate(DATA)
        for mutate in [lambda d: d.update(trace_verified=True), lambda d: d.update(provenance='csv_computed'),
                       lambda d: d['scenario_models'][0]['scenarios'][0].update(interval=[1]),
                       lambda d: d['optimization_plans'][0].update(probability_positive=2),
                       lambda d: d.update(raw_rows=[1]), lambda d: d.update(run_date='2026-10-05')]:
            bad = copy.deepcopy(DATA)
            mutate(bad)
            self.assertFalse(validator.is_valid(bad))

    def test_source_hashes_and_provenance(self):
        self.assertEqual(DATA['provenance'], 'document_recorded')
        self.assertEqual(DATA['validation_scope'], 'document_values_only')
        self.assertFalse(DATA['trace_verified'])
        for source in DATA['sources']:
            self.assertEqual(source['sha256'], hashlib.sha256((ROOT / source['path']).read_bytes()).hexdigest())
        self.assertEqual((DATA['weeks'], DATA['currency'], DATA['amount_unit'], DATA['interval_probability']),
                         (13, 'USD', 'hundred_million_usd', .8))

    def test_all_26_scenario_rows_against_final_section(self):
        text = (ROOT / DATA['scenario_source']).read_text(encoding='utf-8')
        final = text[text.index('## 확정런 재산출 — 2026-10-12'):]
        headings = ['### 기본 모델', '### trend 결합 모델']
        for i, model in enumerate(DATA['scenario_models']):
            block = final.split(headings[i])[1].split('\n### ')[0]
            lines = re.findall(r'^\| (S[0-4](?:_\d+)?) \| (.*?) \| (.*?) \| (.*?) \| (.*?) \|$', block, re.M)
            self.assertEqual([r['id'] for r in model['scenarios']], [line[0] for line in lines])
            self.assertEqual(len(lines), 13)
            for row, (sid, mean, ci, change, flag) in zip(model['scenarios'], lines, strict=True):
                self.assertEqual((row['mean'], row['interval']), (float(mean), nums(ci)))
                self.assertEqual(row['change_pct'], None if sid == 'S0' else float(change.rstrip('%')))
                self.assertEqual(row['extrapolation'], '있음' in flag)
                self.assertLess(row['interval'][0], row['mean'])
                self.assertGreater(row['interval'][1], row['mean'])

    def test_scenario_movements(self):
        conditions = (ROOT / 'docs/scenario.md').read_text(encoding='utf-8')
        for channel in ['VIDTR', 'SEM', 'VIDDIG', 'SO']:
            self.assertRegex(conditions, f'DM에서 {channel}(?:로|으로)(?: 총예산 기준)?:')
        for model in DATA['scenario_models']:
            for row in model['scenarios']:
                if row['id'] == 'S0':
                    self.assertEqual((row['shift_pp'], row['from_channel'], row['to_channel']), (0, None, None))
                else:
                    group, shift = row['id'].split('_')
                    self.assertEqual(row['shift_pp'], int(shift))
                    self.assertEqual(row['from_channel'], 'DM')
                    self.assertEqual(row['to_channel'], {'S1': 'VIDTR', 'S2': 'SEM', 'S3': 'VIDDIG', 'S4': 'SO'}[group])
                    self.assertEqual(row['extrapolation'], group == 'S3' and int(shift) >= 10)

    def test_all_optimization_cells_against_final_table(self):
        text = (ROOT / DATA['optimization_source']).read_text(encoding='utf-8')
        final = text.split('# draws 전체 최적 분포 — 2026-10-12')[1].split('draw별 최적 비중')[0]
        rows = [[c.strip() for c in line.strip('|').split('|')] for line in final.splitlines() if line.startswith('| ')]
        table = {r[0]: r[1:] for r in rows}
        keys = ['기대최적 비중 dm/so/vidtr/viddig/sem (%)', '기대최적 매출 (억)', 'S0 매출 (억)',
                'S0 대비 증분 (억, paired)', 'S0 대비 증분 (%)', 'P(증분 > 0)', '외삽 플래그']
        for i, plan in enumerate(DATA['optimization_plans']):
            expected = [table[k][i] for k in keys]
            actual = [plan['shares_pct'], [plan['mean'], *plan['interval']], [plan['s0_mean'], *plan['s0_interval']],
                      [plan['paired_increment'], *plan['paired_interval']], [plan['change_pct']], [plan['probability_positive']]]
            for values, cell in zip(actual, expected[:6], strict=True):
                self.assertEqual(values, nums(cell))
            self.assertEqual(plan['extrapolation'], 'viddig' in expected[6])
            scenario_model = DATA['scenario_models'][0 if i == 0 else 1]
            self.assertEqual(plan['s0_mean'], scenario_model['scenarios'][0]['mean'])
            self.assertEqual(plan['s0_interval'], scenario_model['scenarios'][0]['interval'])

    def test_s0_shares_constraints_and_defaults(self):
        text = (ROOT / DATA['s0_share_source']).read_text(encoding='utf-8')
        for channel, value in zip(DATA['channels'], DATA['s0_shares_pct'], strict=True):
            self.assertIn(f'| mdsp_{channel.lower()} | {value:.2f}% |', text)
        self.assertAlmostEqual(sum(DATA['s0_shares_pct']), 100)
        self.assertEqual(DATA['default_scenario_model'], 'trend')
        self.assertEqual(DATA['default_optimization'], 'trend_bounded')
        final = DATA['optimization_plans'][2]
        self.assertEqual(final['bounds_pct'], [[5, 60], [0, 60], [0, 60], [0, 8.3], [0, 60]])
        self.assertFalse(final['extrapolation'])
        for plan in DATA['optimization_plans']:
            self.assertLessEqual(abs(sum(plan['shares_pct']) - 100), .100001)
            for value, (lo, hi) in zip(plan['shares_pct'], plan['bounds_pct'], strict=True):
                self.assertTrue(lo <= value <= hi)
        self.assertAlmostEqual(sum(final['shares_pct']), 99.9)
        self.assertNotIn(52.6, [p['change_pct'] for p in DATA['optimization_plans']])

    def test_document_export_reproducible(self):
        from export_m2_data import export
        self.assertEqual(export(), DATA)

    def test_static_disclosures_and_routes(self):
        for path in ['', 'eda', 'scenarios', 'optimization', 'simulator', 'methodology']:
            self.assertTrue((WEB / 'out' / path / 'index.html').exists(), path)
        for path in ['scenarios', 'optimization']:
            html = (WEB / 'out' / path / 'index.html').read_text(encoding='utf-8')
            for label in ['document_recorded', '2026-10-12', '억 USD', '80%', '13주', 'trace', '대체 표']:
                self.assertIn(label, html)


if __name__ == '__main__':
    unittest.main(verbosity=2)
