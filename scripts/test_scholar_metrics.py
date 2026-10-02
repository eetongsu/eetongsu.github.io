"""Regression checks for wrong-column updates and preservation on failed reads."""
import json
from copy import deepcopy
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

from update_scholar_metrics import fetch_serpapi, parse_metrics, parse_serpapi_metrics, update_profile

PROFILE_HTML = '''<html><div id="gsc_prf_in">Tong Su</div>
<table id="gsc_rsb_st"><tr><th></th><th>All</th><th>Since 2021</th></tr>
<tr><td><a>Citations</a></td><td>1,251</td><td>747</td></tr>
<tr><td>h-index</td><td>14</td><td>12</td></tr>
<tr><td>i10-index</td><td>17</td><td>15</td></tr></table></html>'''

API_RESULT = {
    'search_metadata': {'status': 'Success'},
    'search_parameters': {'engine': 'google_scholar_author', 'author_id': 'AXhvF3sAAAAJ', 'hl': 'en'},
    'author': {'name': 'Tong Su'},
    'cited_by': {'table': [
        {'citations': {'all': 1251, 'since_2021': 747}},
        {'h_index': {'all': 14, 'since_2021': 12}},
        {'i10_index': {'all': 17, 'since_2021': 15}},
    ]},
}


class ScholarMetricsTests(unittest.TestCase):
    def test_api_reads_all_time_not_recent_column(self):
        self.assertEqual(parse_serpapi_metrics(API_RESULT, 'Tong Su', 'AXhvF3sAAAAJ'),
                         {'citations': 1251, 'h_index': 14, 'i10_index': 17})

    def test_api_rejects_failed_wrong_author_and_incomplete_responses(self):
        mutations = [
            lambda p: p.update(error='API quota exhausted'),
            lambda p: p['search_metadata'].update(status='Processing'),
            lambda p: p['search_parameters'].update(author_id='another-author'),
            lambda p: p['author'].update(name='Another Author'),
            lambda p: p['cited_by']['table'].pop(),
            lambda p: p['cited_by']['table'][0]['citations'].pop('all'),
            lambda p: p['cited_by']['table'][0]['citations'].update(all=True),
            lambda p: p['cited_by']['table'][0]['citations'].update(all='1,251'),
            lambda p: p['cited_by']['table'][0]['citations'].update(all=3),
        ]
        for mutate in mutations:
            payload = deepcopy(API_RESULT)
            mutate(payload)
            with self.subTest(payload=payload), self.assertRaises(ValueError):
                parse_serpapi_metrics(payload, 'Tong Su', 'AXhvF3sAAAAJ')

    def test_api_failure_preserves_profile_and_success_updates_only_snapshot(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / 'profile.json'
            original = {'name': 'Tong Su', 'scholar': 'https://scholar.google.com/citations?user=AXhvF3sAAAAJ',
                        'metrics': {'citations': 744, 'h_index': 14, 'i10_index': 17}, 'snapshot_date': '2026-10-01',
                        'education': [{'institution': 'Dartmouth College'}]}
            path.write_text(json.dumps(original), encoding='utf-8')
            before = path.read_bytes()
            with patch('update_scholar_metrics.fetch_serpapi', return_value={'error': 'failed'}), self.assertRaises(ValueError):
                update_profile(path, '2026-10-02', source='serpapi', api_key='test-key')
            self.assertEqual(path.read_bytes(), before)
            with patch('update_scholar_metrics.fetch_serpapi', return_value=API_RESULT):
                result = update_profile(path, '2026-10-02', source='serpapi', api_key='test-key')
            self.assertEqual(result['metrics'], {'citations': 1251, 'h_index': 14, 'i10_index': 17})
            after = json.loads(path.read_text(encoding='utf-8'))
            self.assertEqual(after.pop('metrics'), result['metrics'])
            self.assertEqual(after.pop('snapshot_date'), '2026-10-02')
            original.pop('metrics')
            original.pop('snapshot_date')
            self.assertEqual(after, original)

    def test_no_api_request_without_key(self):
        with patch('update_scholar_metrics.urlopen') as request, self.assertRaises(ValueError):
            fetch_serpapi('https://scholar.google.com/citations?user=AXhvF3sAAAAJ', '')
        request.assert_not_called()

    def test_reads_all_time_not_recent_column(self):
        self.assertEqual(parse_metrics(PROFILE_HTML, 'Tong Su'), {'citations': 1251, 'h_index': 14, 'i10_index': 17})

    def test_rejects_challenge_wrong_author_incomplete_and_inconsistent_data(self):
        invalid = [
            '<html>Verify you are human</html>',
            PROFILE_HTML.replace('Tong Su', 'Another Author'),
            PROFILE_HTML.replace('i10-index', 'missing'),
            PROFILE_HTML.replace('1,251', '1,25'),
            PROFILE_HTML.replace('1,251', '3'),
            PROFILE_HTML.replace('All', 'Recent'),
        ]
        for html in invalid:
            with self.subTest(html=html), self.assertRaises(ValueError):
                parse_metrics(html, 'Tong Su')

    def test_failed_read_preserves_entire_file_and_date(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / 'profile.json'
            original = {'name': 'Tong Su', 'scholar': 'https://scholar.google.com/citations?user=AXhvF3sAAAAJ',
                        'metrics': {'citations': 744, 'h_index': 14, 'i10_index': 17}, 'snapshot_date': '2026-10-01'}
            path.write_text(json.dumps(original), encoding='utf-8')
            before = path.read_bytes()
            with patch('update_scholar_metrics.fetch_profile', side_effect=TimeoutError), self.assertRaises(TimeoutError):
                update_profile(path, '2026-10-02')
            self.assertEqual(path.read_bytes(), before)
            with patch('update_scholar_metrics.fetch_profile', return_value='<html>captcha</html>'), self.assertRaises(ValueError):
                update_profile(path, '2026-10-02')
            self.assertEqual(path.read_bytes(), before)

    def test_success_updates_metrics_and_date_preserving_other_profile_fields(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / 'profile.json'
            original = {'name': 'Tong Su', 'scholar': 'https://scholar.google.com/citations?user=AXhvF3sAAAAJ',
                        'metrics': {'citations': 744, 'h_index': 14, 'i10_index': 17}, 'snapshot_date': '2026-10-01',
                        'education': [{'institution': 'Dartmouth College'}]}
            path.write_text(json.dumps(original), encoding='utf-8')
            with patch('update_scholar_metrics.fetch_profile', return_value=PROFILE_HTML):
                self.assertTrue(update_profile(path, '2026-10-02')['updated'])
            after = json.loads(path.read_text(encoding='utf-8'))
            self.assertEqual(after['metrics']['citations'], 1251)
            self.assertEqual(after['snapshot_date'], '2026-10-02')
            self.assertEqual(after['education'], original['education'])


if __name__ == '__main__':
    unittest.main()
