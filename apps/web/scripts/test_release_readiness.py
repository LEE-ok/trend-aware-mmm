"""M4 aggregate audit, publication disclosure, static privacy and portability checks."""
import csv
import hashlib
import json
import re
import shutil
import subprocess
import tempfile
import unittest
from decimal import Decimal
from pathlib import Path

import numpy as np

WEB = Path(__file__).resolve().parents[1]
ROOT = WEB.parents[1]
AUDIT = json.loads((WEB / 'data/release-audit.json').read_text(encoding='utf-8'))


class ReleaseReadinessTests(unittest.TestCase):
    def test_recent_budget_uses_exact_cents_and_preserves_m2_m3_defaults(self):
        with (ROOT / AUDIT['source']).open(encoding='utf-8-sig', newline='') as stream:
            rows = list(csv.DictReader(stream))
        channels = ['mdsp_dm', 'mdsp_so', 'mdsp_vidtr', 'mdsp_viddig', 'mdsp_sem']
        expected = sum((Decimal(row[c]) for row in rows[-13:] for c in channels), Decimal(0))
        self.assertEqual(Decimal(AUDIT['recent_13_weeks_total_usd']), expected)
        self.assertEqual(expected, Decimal('16195402.79'))
        self.assertEqual(expected - Decimal(AUDIT['document_budget_usd']), Decimal(AUDIT['actual_minus_document_usd']))
        m2 = json.loads((WEB / 'data/mmm-results.json').read_text(encoding='utf-8'))
        self.assertEqual(m2['budget_million_usd'], 16.2)
        self.assertEqual(AUDIT['provenance'], 'csv_computed')
        self.assertEqual(AUDIT['document_budget_provenance'], 'document_recorded')

    def test_audit_reproducible_and_public_candidate_content_match(self):
        from export_release_audit import audit
        self.assertEqual(audit(), AUDIT)
        source_hash = hashlib.sha256((ROOT / AUDIT['source']).read_bytes()).hexdigest()
        self.assertEqual(AUDIT['source_sha256'], source_hash)
        review = AUDIT['publication_review']
        self.assertEqual(review['public_file_sha256'], source_hash)
        self.assertEqual(review['repository_license'], 'MIT')
        self.assertEqual(review['dataset_redistribution_status'], 'unconfirmed')

    def test_sem_q1_document_discrepancy_remains_unresolved(self):
        with (ROOT / AUDIT['source']).open(encoding='utf-8-sig', newline='') as stream:
            values = [float(row['mdsp_sem']) for row in csv.DictReader(stream)]
        for subset in [values, values[:-26], values[-26:]]:
            for method in ['linear', 'lower', 'higher', 'midpoint', 'nearest']:
                self.assertGreater(abs(float(np.quantile(subset, .25, method=method)) - 365000), 500)
        self.assertEqual(AUDIT['sem_q1']['cause'], 'unconfirmed')
        self.assertEqual(AUDIT['sem_q1']['csv_usd'], '355954.51')
        self.assertEqual(AUDIT['sem_q1']['difference_usd'], '9045.49')
        self.assertIn('36.5만', (ROOT / 'docs/eda.md').read_text(encoding='utf-8'))

    def test_methodology_and_provenance_disclosures(self):
        html = (WEB / 'out/methodology/index.html').read_text(encoding='utf-8')
        for value in ['분석 방법론', 'Adstock', 'Hill Saturation', 'Bayesian posterior', '33.6%', '30.6%',
                      '40%', '36%', '183 / 26주', '209주', 'S0', 'S1', 'S2', 'S3', 'S4', '2026-10-12',
                      'csv_computed', 'document_recorded', '16,195,402.79', '4,597.21', '미확인', 'MIT',
                      '실제 집행 성과', '국소 최적', 'paired', '99.9%', 'trace']:
            self.assertIn(value, html, value)
        overview = (WEB / 'out/index.html').read_text(encoding='utf-8')
        self.assertIn('시나리오 원본 산출물 JSON', overview)
        self.assertIn('모델 원본 산출물이 아닙니다', overview)
        for route in ['', 'eda']:
            self.assertIn('csv_computed', (WEB / 'out' / route / 'index.html').read_text(encoding='utf-8'))
        for disclosure in ['데이터의 실제 생성자', '현재 시장 실적이 아닙니다', '본 프로젝트 전체에 MIT를 적용',
                           'HTML·JS·RSC', '원본 주간 CSV 입력값', '/third-party/mmm-stan-LICENSE.txt']:
            self.assertIn(disclosure, html)
        notice = WEB / 'public/third-party/mmm-stan-LICENSE.txt'
        self.assertEqual(hashlib.sha256(notice.read_bytes()).hexdigest(),
                         '6f8030d496080b7b870bdf72f7c257edfac56ef3d8714c9aa455daba3810f21c')
        self.assertEqual(notice.read_bytes(), (WEB / 'out/third-party/mmm-stan-LICENSE.txt').read_bytes())

    def test_static_bundle_has_no_raw_artifacts_credentials_or_host_paths(self):
        patterns = [
            rb'-----BEGIN (?:RSA |EC |OPENSSH )?PRIVATE KEY-----',
            rb'\b(?:AKIA|ASIA)[A-Z0-9]{16}\b', rb'\bgh[pousr]_[A-Za-z0-9]{20,}\b',
            rb'\bgithub_pat_[A-Za-z0-9_]{20,}\b', rb'\bsk-(?:proj-)?[A-Za-z0-9_-]{20,}\b',
            rb'[A-Za-z]:[\\/]+Users[\\/]+', rb'/Users/[^/]+/',
        ]
        forbidden = {'.csv', '.nc', '.npy', '.npz', '.pkl', '.pickle', '.parquet', '.sqlite', '.pem', '.key', '.py', '.map'}
        files = [p for p in (WEB / 'out').rglob('*') if p.is_file()]
        self.assertTrue(files)
        for file in files:
            self.assertNotIn(file.suffix.lower(), forbidden, str(file.relative_to(WEB)))
            self.assertFalse(file.name.startswith('.env'))
            payload = file.read_bytes()
            self.assertFalse(any(re.search(pattern, payload) for pattern in patterns), f'Sensitive content (value withheld): {file.relative_to(WEB)}')

    def test_app_is_static_and_import_case_is_portable(self):
        self.assertIn('output: "export"', (WEB / 'next.config.ts').read_text(encoding='utf-8'))
        self.assertFalse((WEB / 'app/api').exists())
        for directory in ['app', 'components', 'lib']:
            for file in (WEB / directory).rglob('*'):
                if file.suffix not in {'.ts', '.tsx'}:
                    continue
                text = file.read_text(encoding='utf-8')
                self.assertNotRegex(text, r'(?m)^[\s]*[\x22\x27]use server[\x22\x27]')
                for imported in re.findall(r'from [\x22\x27](@/[^\x22\x27]+)[\x22\x27]', text):
                    relative = imported[2:]
                    options = [WEB / relative, WEB / f'{relative}.ts', WEB / f'{relative}.tsx']
                    resolved = next((p for p in options if p.is_file()), None)
                    self.assertIsNotNone(resolved, imported)
                    current = WEB
                    for part in resolved.relative_to(WEB).parts:
                        self.assertIn(part, [p.name for p in current.iterdir()], imported)
                        current = current / part

    def test_windows_alias_normalizer_and_linux_flat_output_are_idempotent(self):
        with tempfile.TemporaryDirectory() as tmp:
            folder = Path(tmp)
            (folder / 'scripts').mkdir()
            output = folder / 'out'
            (output / 'scenarios/__next.scenarios').mkdir(parents=True)
            (output / 'scenarios/__next.scenarios/__PAGE__.txt').write_text('RSC fixture', encoding='utf-8')
            (output / 'optimization').mkdir()
            (output / 'optimization/__next.optimization.__PAGE__.txt').write_text('Linux fixture', encoding='utf-8')
            script = folder / 'scripts/normalize-static-export.mjs'
            shutil.copyfile(WEB / 'scripts/normalize-static-export.mjs', script)
            for _ in range(2):
                subprocess.run(['node', str(script)], check=True, capture_output=True)
            self.assertEqual((output / 'scenarios/__next.scenarios.__PAGE__.txt').read_text(encoding='utf-8'), 'RSC fixture')
            self.assertEqual((output / 'optimization/__next.optimization.__PAGE__.txt').read_text(encoding='utf-8'), 'Linux fixture')


if __name__ == '__main__':
    unittest.main(verbosity=2)
