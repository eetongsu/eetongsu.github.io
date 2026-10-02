"""Regression checks for wrong-column updates and preservation on failed reads."""
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

from update_scholar_metrics import parse_metrics, update_profile

PROFILE_HTML = '''<html><div id="gsc_prf_in">Tong Su</div>
<table id="gsc_rsb_st"><tr><th></th><th>All</th><th>Since 2021</th></tr>
<tr><td><a>Citations</a></td><td>1,251</td><td>747</td></tr>
<tr><td>h-index</td><td>14</td><td>12</td></tr>
<tr><td>i10-index</td><td>17</td><td>15</td></tr></table></html>'''


class ScholarMetricsTests(unittest.TestCase):
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
