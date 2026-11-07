"""Independent data, disclosure, provenance and static-output regression checks."""
import copy
import csv
import hashlib
import json
import re
import statistics
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

import jsonschema
import numpy as np
from scipy.stats import pearsonr, spearmanr

WEB = Path(__file__).resolve().parents[1]
ROOT = WEB.parents[1]
DATA = json.loads((WEB / 'data/dashboard-aggregates.json').read_text(encoding='utf-8'))
SCHEMA = json.loads((WEB / 'data/dashboard.schema.json').read_text(encoding='utf-8'))
RAW = ROOT / 'data/raw/data_GIT.csv'


class DashboardDataTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        with RAW.open(encoding='utf-8-sig', newline='') as stream:
            cls.rows = list(csv.DictReader(stream))

    def test_strict_schema_and_reject_raw_payloads(self):
        validator = jsonschema.Draft202012Validator(SCHEMA, format_checker=jsonschema.FormatChecker())
        validator.validate(DATA)
        for mutate in [lambda d: d.update(rows=self.rows), lambda d: d['sales'].update(observations=[1, 2]),
                       lambda d: d['channels'][0].update(api_key='forbidden'),
                       lambda d: d['privacy'].update(weekly_rows_exported=True)]:
            bad = copy.deepcopy(DATA)
            mutate(bad)
            self.assertFalse(validator.is_valid(bad))

    def test_source_hash_period_and_split(self):
        self.assertEqual(hashlib.sha256(RAW.read_bytes()).hexdigest(), DATA['source_sha256'])
        self.assertEqual(len(self.rows), DATA['summary']['weeks'])
        self.assertEqual(DATA['summary']['weeks'], 209)
        self.assertEqual((DATA['summary']['train_weeks'], DATA['summary']['test_weeks']), (183, 26))
        dates = [r['wk_strt_dt'] for r in self.rows]
        self.assertEqual((min(dates), max(dates)), (DATA['period']['start'], DATA['period']['end']))

    def test_export_reproducible_and_existing_output_preserved(self):
        from export_dashboard_data import aggregate
        regenerated = aggregate()
        saved = copy.deepcopy(DATA)
        regenerated.pop('generated_at')
        saved.pop('generated_at')
        self.assertEqual(regenerated, saved)
        with tempfile.TemporaryDirectory() as directory:
            output = Path(directory) / 'existing.json'
            output.write_text('preserve me', encoding='utf-8')
            result = subprocess.run([sys.executable, '-B', str(WEB / 'scripts/export_dashboard_data.py'), '--output', str(output)], capture_output=True)
            self.assertNotEqual(result.returncode, 0)
            self.assertEqual(output.read_text(encoding='utf-8'), 'preserve me')

    def assert_stats(self, actual, values):
        expected = dict(zip(['min', 'q25', 'median', 'q75', 'max'], np.quantile(values, [0, .25, .5, .75, 1])))
        expected.update(total=sum(values), mean=statistics.mean(values))
        for key, value in expected.items():
            self.assertAlmostEqual(actual[key], value, delta=max(1e-7, abs(value) * 1e-12))

    def test_every_sales_and_channel_aggregate(self):
        sales = [float(r['sales']) for r in self.rows]
        self.assert_stats(DATA['sales'], sales)
        ids = ['mdsp_dm', 'mdsp_so', 'mdsp_vidtr', 'mdsp_viddig', 'mdsp_sem']
        self.assertEqual([c['id'] for c in DATA['channels']], ids)
        total = sum(float(r[ch]) for r in self.rows for ch in ids)
        self.assertAlmostEqual(DATA['summary']['spend_total'], total, places=4)
        for ch in DATA['channels']:
            values = [float(r[ch['id']]) for r in self.rows]
            self.assert_stats(ch['spend'], values)
            self.assertAlmostEqual(ch['share'], sum(values) / total, places=12)
            self.assertEqual(ch['zero_weeks'], values.count(0))
            self.assertAlmostEqual(ch['pearson'], float(pearsonr(values, sales).statistic), places=12)
            self.assertAlmostEqual(ch['spearman'], float(spearmanr(values, sales).statistic), places=12)
        self.assertAlmostEqual(sum(c['share'] for c in DATA['channels']), 1, places=12)

    def test_document_values_and_rounding(self):
        self.assertEqual(DATA['document_comparison']['mismatch_count'], 1)
        self.assertEqual(len(DATA['document_comparison']['checks']), 36)
        for check in DATA['document_comparison']['checks']:
            self.assertEqual(check['matches'], abs(check['computed'] - check['recorded']) <= check['tolerance'])
        mismatch = [c for c in DATA['document_comparison']['checks'] if not c['matches']]
        self.assertEqual(mismatch[0]['metric'], 'mdsp_sem.prose.q25')
        self.assertAlmostEqual(mismatch[0]['computed'], 355954.51, places=2)
        self.assertEqual(mismatch[0]['recorded'], 365000)
        models = DATA['model_performance']
        self.assertEqual(models['provenance'], 'document_recorded')
        self.assertFalse(models['trace_verified'])
        for model, values in zip(models['models'], [(.336, .4, 1.004), (.306, .36, 1.003)], strict=True):
            self.assertEqual((model['test_mape'], model['direction_accuracy'], model['max_rhat']), values)
        text = (ROOT / 'docs/bayes-run.md').read_text(encoding='utf-8').split('## 최종 확정런 — 2026-10-12')[1]
        for value in ['0.336', '0.306', '1.004', '1.003']:
            self.assertIn(value, text)

    def test_disclosure_allowlist(self):
        serialized = json.dumps(DATA, ensure_ascii=False)
        # Only overall period endpoints, recorded run date and generation date are allowed.
        allowed_dates = {DATA['period']['start'], DATA['period']['end'], DATA['model_performance']['run_date'], DATA['generated_at'][:10]}
        self.assertLessEqual(set(re.findall(r'\d{4}-\d{2}-\d{2}', serialized)), allowed_dates)
        self.assertNotIn('wk_strt_dt', serialized)
        self.assertNotIn('C:\\Users', serialized)
        self.assertNotRegex(serialized, r'(?i)(sk-[a-z0-9]{20}|ghp_[a-z0-9]+|bearer\s|password|api_key|@\w+\.)')
        def inspect(value):
            if isinstance(value, dict):
                for child in value.values(): inspect(child)
            if isinstance(value, list):
                self.assertLess(len(value), 40)
                for child in value: inspect(child)
        inspect(DATA)

    def test_static_output_contains_no_raw_csv_or_weekly_records(self):
        output = WEB / 'out'
        self.assertTrue((output / 'index.html').exists(), 'Run npm run build before this test')
        raw_header = RAW.read_text(encoding='utf-8-sig').splitlines()[0].encode()
        interior_dates = {r['wk_strt_dt'] for r in self.rows[1:-1]}
        for file in output.rglob('*'):
            if not file.is_file(): continue
            self.assertNotEqual(file.suffix.lower(), '.csv')
            if file.suffix not in ['.html', '.js', '.json', '.txt']: continue
            payload = file.read_bytes()
            self.assertNotIn(raw_header, payload, str(file))
            dates = set(re.findall(rb'201[4-8]-\d{2}-\d{2}', payload))
            self.assertFalse({d.decode() for d in dates} & interior_dates, str(file))


if __name__ == '__main__':
    unittest.main(verbosity=2)
