"""Prepare an offline, provisional site-group split; never contact sites or APIs."""
import argparse
import csv
import hashlib
import json
from collections import Counter, defaultdict
from pathlib import Path
from urllib.parse import urlsplit

import tldextract


def prepare(source, destination, seed='memophish-v1'):
    source, destination = Path(source), Path(destination)
    # Existing results must be retained; choose a new output directory for a rerun.
    destination.mkdir(parents=True, exist_ok=False)
    rows = list(csv.DictReader(source.open(encoding='utf-8-sig', newline='')))
    by_url = defaultdict(list)
    for row in rows:
        if row['label'] not in ('benign', 'malicious'):
            raise ValueError('Unexpected label')
        by_url[row['url']].append(row)
    extractor = tldextract.TLDExtract(suffix_list_urls=(), cache_dir=None,
                                     include_psl_private_domains=True)
    groups, excluded = defaultdict(list), []
    for url, records in sorted(by_url.items()):
        reasons = []
        if len({r['label'] for r in records}) > 1:
            reasons.append('conflicting_labels')
        if any(r['is_shortener'].lower() == 'true' for r in records):
            reasons.append('unresolved_shortener')
        if any(r['query_redacted'].lower() == 'true' for r in records):
            reasons.append('redacted_query')
        parsed = urlsplit(url)
        if parsed.scheme not in ('http', 'https') or not parsed.hostname:
            reasons.append('invalid_url')
        if reasons:
            excluded.append({'url': url, 'reasons': reasons,
                             'record_ids': [r['id'] for r in records]})
            continue
        host = parsed.hostname.lower()
        extracted = extractor(host)
        site = extracted.top_domain_under_public_suffix or host
        groups[site].append({'url': url, 'label': records[0]['label'],
                            'site_group': site, 'record_ids': [r['id'] for r in records]})
    # Assign whole groups by size, with seed-derived tie order. Labels do not
    # determine assignments. Targets are approximate due to large site groups.
    names = ('warmup', 'validation', 'test')
    total = sum(map(len, groups.values()))
    targets = dict(zip(names, (total * .6, total * .2, total * .2)))
    splits = {name: [] for name in names}
    order = sorted(groups, key=lambda site: (-len(groups[site]),
        hashlib.sha256((seed + ':' + site).encode()).hexdigest()))
    for site in order:
        name = max(names, key=lambda name: targets[name] - len(splits[name]))
        splits[name].extend(groups[site])
    url_sets = [set(r['url'] for r in splits[name]) for name in names]
    site_sets = [set(r['site_group'] for r in splits[name]) for name in names]
    for i in range(len(names)):
        for j in range(i):
            assert not url_sets[i] & url_sets[j], 'URL leakage'
            assert not site_sets[i] & site_sets[j], 'Site leakage'
    assert sum(map(len, url_sets)) == total
    manifest = {'status': 'provisional_not_live_validated', 'seed': seed,
                'source_sha256': hashlib.sha256(source.read_bytes()).hexdigest(),
                'input_records': len(rows), 'unique_urls': len(by_url),
                'duplicate_extra_records': len(rows) - len(by_url),
                'excluded_unique_urls': len(excluded), 'eligible_unique_urls': total,
                'excluded_reason_counts': dict(Counter(reason for r in excluded for reason in r['reasons'])),
                'target_fractions': {'warmup': .6, 'validation': .2, 'test': .2},
                'grouping': 'bundled PSL with private suffixes; entire registered site kept together',
                'limitations': ['No live availability or current-label verification',
                    'Cross-domain templates and redirect destinations not verified',
                    'URL deduplication is exact string matching; aliases still need review',
                    'Conservative shared-host grouping may create label imbalance',
                    'No detection results, API calls, or memory snapshot produced'],
                'splits': {}}
    for name in names:
        records = sorted(splits[name], key=lambda r: r['url'])
        (destination / f'{name}_urls.txt').write_text(''.join(r['url'] + '\n' for r in records), encoding='utf-8')
        with (destination / f'{name}_labels.csv').open('w', encoding='utf-8', newline='') as handle:
            writer = csv.DictWriter(handle, fieldnames=['url', 'label'])
            writer.writeheader()
            writer.writerows({'url': r['url'], 'label': r['label']} for r in records)
        (destination / f'{name}_manifest.json').write_text(json.dumps(records, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')
        manifest['splits'][name] = {'urls': len(records), 'site_groups': len(site_sets[names.index(name)]),
                                    'historical_labels': dict(Counter(r['label'] for r in records))}
    (destination / 'excluded.json').write_text(json.dumps(excluded, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')
    (destination / 'manifest.json').write_text(json.dumps(manifest, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')
    return manifest


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--source', default='data/socphish/socphish_public.csv')
    parser.add_argument('--output', required=True, help='New output directory; existing directories are never overwritten')
    parser.add_argument('--seed', default='memophish-v1')
    args = parser.parse_args()
    print(json.dumps(prepare(args.source, args.output, args.seed), ensure_ascii=False, indent=2))
