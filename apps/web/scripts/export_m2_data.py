"""Export recorded final-run tables only. Never loads CSV, trace or model code."""
import argparse
import hashlib
import json
import re
from pathlib import Path

import jsonschema

WEB = Path(__file__).resolve().parents[1]
ROOT = WEB.parents[1]


def numbers(text):
    return [float(n) for n in re.findall(r'[+-]?\d+(?:\.\d+)?', text)]


def export():
    paths = ['docs/scenario-results.md', 'docs/optimization.md', 'docs/scenario.md']
    texts = {p: (ROOT / p).read_text(encoding='utf-8') for p in paths}
    final = texts[paths[0]].split('## 확정런 재산출 — 2026-10-12\n', 1)[1]
    models = []
    for model_id, label, section in [('base', '기본 모델', '### 기본 모델'),
                                     ('trend', 'trend 결합 모델', '### trend 결합 모델')]:
        block = final.split(section, 1)[1].split('\n### ', 1)[0]
        scenarios = []
        for line in block.splitlines():
            if not re.match(r'\| S[0-4](?:_| \|)', line):
                continue
            cells = [c.strip() for c in line.strip('|').split('|')]
            sid = cells[0]
            group = sid.split('_')[0]
            scenarios.append(dict(id=sid, mean=float(cells[1]), interval=numbers(cells[2]),
                                  change_pct=None if sid == 'S0' else numbers(cells[3])[0],
                                  extrapolation='있음' in cells[4],
                                  from_channel=None if sid == 'S0' else 'DM',
                                  to_channel={'S0': None, 'S1': 'VIDTR', 'S2': 'SEM', 'S3': 'VIDDIG', 'S4': 'SO'}[group],
                                  shift_pp=0 if sid == 'S0' else int(sid.split('_')[1])))
        assert len(scenarios) == 13
        models.append(dict(id=model_id, label=label, scenarios=scenarios))
    block = texts[paths[1]].split('# draws 전체 최적 분포 — 2026-10-12', 1)[1].split('draw별 최적 비중', 1)[0]
    rows = [[c.strip() for c in line.strip('|').split('|')] for line in block.splitlines() if line.startswith('| ')]
    table = {row[0]: row[1:] for row in rows}
    def find(prefix):
        return next(v for k, v in table.items() if k.startswith(prefix))
    plans = []
    for i, (pid, label) in enumerate([('base', '기본 모델'), ('trend', 'trend 결합 모델'), ('trend_bounded', 'trend + 운영 경계 · 최종 권고안')]):
        sales, baseline, paired = [numbers(find(prefix)[i]) for prefix in ['기대최적 매출', 'S0 매출', 'S0 대비 증분 (억']]
        plans.append(dict(id=pid, label=label, shares_pct=numbers(find('기대최적 비중')[i]),
                          mean=sales[0], interval=sales[1:], s0_mean=baseline[0], s0_interval=baseline[1:],
                          paired_increment=paired[0], paired_interval=paired[1:],
                          change_pct=numbers(find('S0 대비 증분 (%)')[i])[0],
                          probability_positive=float(find('P(증분')[i]), extrapolation=i == 1,
                          extrapolation_channel='VIDDIG' if i == 1 else None,
                          bounds_pct=[[5, 60], [0, 60], [0, 60], [0, 8.3], [0, 60]] if i == 2 else [[0, 60]] * 5))
    shares = {m[0].upper(): float(m[1]) for m in re.findall(r'\| mdsp_(\w+) \| ([\d.]+)% \|', texts[paths[2]])}
    return dict(schema_version='1.0.0', provenance='document_recorded', validation_status='passed',
                validation_scope='document_values_only', trace_verified=False, run_date='2026-10-12',
                sources=[dict(path=p, sha256=hashlib.sha256((ROOT / p).read_bytes()).hexdigest()) for p in paths],
                currency='USD', amount_unit='hundred_million_usd', weeks=13, interval_probability=0.8,
                budget_million_usd=16.20, channels=['DM', 'SO', 'VIDTR', 'VIDDIG', 'SEM'],
                s0_shares_pct=[shares[c] for c in ['DM', 'SO', 'VIDTR', 'VIDDIG', 'SEM']],
                s0_share_source='docs/scenario.md', scenario_source='docs/scenario-results.md',
                optimization_source='docs/optimization.md', default_scenario_model='trend',
                default_optimization='trend_bounded', scenario_models=models, optimization_plans=plans)


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output', type=Path, default=WEB / 'data/mmm-results.json')
    args = parser.parse_args()
    data = export()
    schema = json.loads((WEB / 'data/mmm-results.schema.json').read_text(encoding='utf-8'))
    jsonschema.Draft202012Validator(schema).validate(data)
    # Exclusive creation preserves any existing reviewed snapshot.
    with args.output.open('x', encoding='utf-8', newline='\n') as stream:
        json.dump(data, stream, ensure_ascii=False, indent=2, allow_nan=False)
        stream.write('\n')
