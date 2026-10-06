"""Offline checks for deduplication, exclusion and site-group split integrity."""
import csv
import json
import tempfile
import unittest
from pathlib import Path

from prepare_splits import prepare

FIELDS = ['id', 'url', 'label', 'is_shortener', 'query_redacted']


def row(url, label='benign', short=False, redacted=False):
    return dict(id=url, url=url, label=label, is_shortener=str(short), query_redacted=str(redacted))


class SplitTests(unittest.TestCase):
    def generate(self, directory, rows, name='split'):
        source = directory / f'{name}.csv'
        with source.open('w', newline='', encoding='utf-8') as handle:
            writer = csv.DictWriter(handle, fieldnames=FIELDS)
            writer.writeheader(); writer.writerows(rows)
        target = directory / name
        report = prepare(source, target)
        return target, report

    def test_duplicate_conflict_and_special_urls_are_isolated(self):
        rows = [row('https://same.example.com'), row('https://same.example.com'),
                row('https://conflict.example.net'), row('https://conflict.example.net', 'malicious'),
                row('https://short.example.org', short=True),
                row('https://redacted.example.edu', redacted=True)]
        with tempfile.TemporaryDirectory(dir='/tmp') as folder:
            target, report = self.generate(Path(folder), rows)
            self.assertEqual(report['duplicate_extra_records'], 2)
            self.assertEqual(report['eligible_unique_urls'], 1)
            self.assertEqual(report['excluded_unique_urls'], 3)
            excluded = json.loads((target / 'excluded.json').read_text())
            self.assertIn('conflicting_labels', next(r for r in excluded if 'conflict' in r['url'])['reasons'])

    def test_site_groups_never_cross_splits(self):
        rows = [row('https://a.example.com/one'), row('https://b.example.com/two')]
        rows += [row(f'https://site-{i}.org/') for i in range(30)]
        with tempfile.TemporaryDirectory(dir='/tmp') as folder:
            target, report = self.generate(Path(folder), rows)
            urls, sites, locations = set(), set(), {}
            for name in ('warmup', 'validation', 'test'):
                records = json.loads((target / f'{name}_manifest.json').read_text())
                current_sites = {r['site_group'] for r in records}
                self.assertFalse(sites & current_sites)
                sites |= current_sites
                for r in records:
                    self.assertNotIn(r['url'], urls)
                    urls.add(r['url']); locations[r['url']] = name
            self.assertEqual(locations[rows[0]['url']], locations[rows[1]['url']])
            self.assertEqual(len(urls), len(rows))

    def test_assignment_does_not_use_labels(self):
        rows = [row(f'https://site-{i}.com') for i in range(20)]
        with tempfile.TemporaryDirectory(dir='/tmp') as folder:
            a, _ = self.generate(Path(folder), rows, 'a')
            b, _ = self.generate(Path(folder), [{**r, 'label': 'malicious'} for r in rows], 'b')
            for name in ('warmup', 'validation', 'test'):
                self.assertEqual((a / f'{name}_urls.txt').read_bytes(), (b / f'{name}_urls.txt').read_bytes())

    def test_repeatable_and_never_overwrites(self):
        rows = [row(f'https://site-{i}.com') for i in range(20)]
        with tempfile.TemporaryDirectory(dir='/tmp') as folder:
            a, _ = self.generate(Path(folder), rows, 'a')
            b, _ = self.generate(Path(folder), rows, 'b')
            for p in a.iterdir():
                self.assertEqual(p.read_bytes(), (b / p.name).read_bytes())
            with self.assertRaises(FileExistsError):
                prepare(Path(folder) / 'a.csv', a)

    def test_private_suffix_tenants_are_distinct(self):
        rows = [row('https://one.blogspot.com'), row('https://two.blogspot.com')]
        with tempfile.TemporaryDirectory(dir='/tmp') as folder:
            target, _ = self.generate(Path(folder), rows)
            sites = {r['site_group'] for name in ('warmup', 'validation', 'test')
                     for r in json.loads((target / f'{name}_manifest.json').read_text())}
            self.assertEqual(sites, {'one.blogspot.com', 'two.blogspot.com'})


if __name__ == '__main__':
    unittest.main(verbosity=2)
