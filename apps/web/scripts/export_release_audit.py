"""Reproducible aggregate-only release audit. No model execution or weekly export."""
import argparse
import csv
import hashlib
import json
from decimal import Decimal
from pathlib import Path

import numpy as np

WEB = Path(__file__).resolve().parents[1]
ROOT = WEB.parents[1]


def audit():
    raw = ROOT / 'data/raw/data_GIT.csv'
    with raw.open(encoding='utf-8-sig', newline='') as stream:
        rows = list(csv.DictReader(stream))
    channels = ['mdsp_dm', 'mdsp_so', 'mdsp_vidtr', 'mdsp_viddig', 'mdsp_sem']
    total = sum((Decimal(row[channel]) for row in rows[-13:] for channel in channels), Decimal(0))
    q1 = float(np.quantile([float(row['mdsp_sem']) for row in rows], .25, method='linear'))
    return {
        'schema_version': '1.0.0', 'source': 'data/raw/data_GIT.csv',
        'source_sha256': hashlib.sha256(raw.read_bytes()).hexdigest(),
        'provenance': 'csv_computed', 'validation_scope': 'aggregate_arithmetic_only',
        'currency': 'USD', 'recent_13_weeks_total_usd': str(total.quantize(Decimal('.01'))),
        'document_budget_usd': '16200000.00', 'document_budget_provenance': 'document_recorded',
        'document_budget_source': 'docs/scenario.md',
        'actual_minus_document_usd': str((total - Decimal('16200000')).quantize(Decimal('.01'))),
        'sem_q1': {'csv_usd': f'{q1:.2f}', 'document_usd': '365000.00',
                   'difference_usd': f'{365000 - q1:.2f}', 'source': 'docs/eda.md', 'cause': 'unconfirmed'},
        'publication_review': {
            'checked_on': '2026-11-08',
            'matching_public_file': 'https://github.com/sibylhe/mmm_stan/blob/main/data.csv',
            'public_file_sha256': 'f690896bf40e622f77b6498ae3e182e4d48dd17bc1dee74fe811e8e3c0ce8696',
            'repository_license': 'MIT',
            'license_url': 'https://github.com/sibylhe/mmm_stan/blob/main/LICENSE',
            'dataset_redistribution_status': 'unconfirmed',
        },
    }


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output', type=Path, default=WEB / 'data/release-audit.json')
    args = parser.parse_args()
    with args.output.open('x', encoding='utf-8', newline='\n') as stream:
        json.dump(audit(), stream, ensure_ascii=False, indent=2, allow_nan=False)
        stream.write('\n')
