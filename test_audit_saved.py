import copy
import hashlib
import itertools
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch
import audit_saved as audit


class SavedAuditTests(unittest.TestCase):
    def setUp(self):
        self.jobs = [dict(class_id=c, seed=s) for c, s in itertools.product(('r3','r4','r5','r6'), range(16))]
        self.rows = []
        for c, s, i, d, o, e in itertools.product(('r3','r4','r5','r6'), range(16), ('A','B'), ('1.0','0.25'), ('A','B'), (1,2)):
            observed = -0.01*(s+1) if i == 'A' else 0.0
            predictions = dict(R0=0.0, R1=observed*1.2, input_steady=observed*0.99)
            self.rows.append(dict(class_id=c, seed=s, identity=i, dose=d, odor=o, event=e,
                role='primary' if e == 2 else 'auxiliary', observed=observed, predictions=predictions,
                errors={m:v-observed for m,v in predictions.items()}, frozen_sha256='a'*64))

    def test_valid_full_grid_and_zero_sensitivity(self):
        r = audit.summarize(self.rows, self.jobs)
        self.assertEqual(len(r['primary']['cells']), 32)
        self.assertEqual(r['primary']['cells'][0]['methods']['R0']['numerical_classification']['FN'], 16)
        self.assertIsNone(r['primary']['cells'][4]['methods']['R1']['numerical_classification']['sensitivity'])

    def test_missing_row(self):
        with self.assertRaises(ValueError): audit.summarize(self.rows[:-1], self.jobs)

    def test_duplicate_row(self):
        with self.assertRaises(ValueError): audit.summarize(self.rows+[self.rows[0]], self.jobs)

    def test_nonfinite(self):
        self.rows[0]['observed'] = float('nan')
        with self.assertRaises(ValueError): audit.summarize(self.rows, self.jobs)

    def test_wrong_role(self):
        self.rows[0]['role'] = 'primary'
        with self.assertRaises(ValueError): audit.summarize(self.rows, self.jobs)

    def test_error_arithmetic(self):
        self.rows[0]['errors']['R1'] += 0.1
        with self.assertRaises(ValueError): audit.summarize(self.rows, self.jobs)

    def test_statistics_mismatch(self):
        r = audit.summarize(self.rows, self.jobs)
        changed = copy.deepcopy(r)
        changed['primary']['cells'][0]['methods']['R1']['MAE']['mean'] += 0.1
        with self.assertRaises(ValueError): audit.compare(changed, r)

    def test_job_incomplete(self):
        with self.assertRaises(ValueError): audit.summarize(self.rows, self.jobs[:-1])

    def test_json_corruption_and_duplicate_key(self):
        with tempfile.TemporaryDirectory() as tmp:
            p = Path(tmp)/'bad.json'
            for text in ('{', '{"x":NaN}', '{"x":1,"x":2}'):
                p.write_text(text, encoding='utf-8')
                with self.assertRaises((ValueError, json.JSONDecodeError)): audit.load(p)

    def test_missing_repository(self):
        with tempfile.TemporaryDirectory() as tmp:
            with self.assertRaises((OSError, ValueError)): audit.audit(Path(tmp))

    def fixture(self, repo):
        root = repo/audit.RUN
        root.mkdir(parents=True)
        def write(name, value):
            (root/name).write_text(json.dumps(value), encoding='utf-8')
        frozen = [dict(sha256='a'*64) for _ in range(8)]
        write('predictions.json', dict(rows=1024, jobs=[dict(job=j, frozen=frozen) for j in self.jobs]))
        digest = hashlib.sha256((root/'predictions.json').read_bytes()).hexdigest()
        write('measurements.json', dict(rows=self.rows, predictions_sha256=digest))
        write('statistics.json', dict(status='COMPLETE_FIXED16_DESCRIPTIVE', scientific_pass=False,
                                     top_up=False, roles=audit.summarize(self.rows, self.jobs)))
        self.reseal(root)
        return root

    def reseal(self, root):
        cold = dict(jobs=64, rows=1024)
        for name in ('measurements', 'statistics', 'predictions'):
            raw = (root/(name+'.json')).read_bytes()
            cold[name] = dict(file=name+'.json', bytes=len(raw), sha256=hashlib.sha256(raw).hexdigest())
        (root/'cold_evidence.json').write_text(json.dumps(cold), encoding='utf-8')

    def fixture_audit(self, repo):
        original = audit.load
        # Isolate only the production manifest; the fixture data use real reads/hashes.
        def loader(path):
            return dict(files=[]) if path.name == 'manifest.json' else original(path)
        with patch.object(audit, 'load', side_effect=loader):
            return audit.audit(repo)

    def test_full_readonly_fixture(self):
        with tempfile.TemporaryDirectory() as tmp:
            repo = Path(tmp)
            root = self.fixture(repo)
            before = {p.name:p.read_bytes() for p in root.iterdir()}
            result = self.fixture_audit(repo)
            self.assertEqual(result['status'], 'SAVED_SUMMARIES_REPRODUCED')
            self.assertEqual(before, {p.name:p.read_bytes() for p in root.iterdir()})

    def test_hash_tamper_rejected(self):
        with tempfile.TemporaryDirectory() as tmp:
            repo = Path(tmp)
            root = self.fixture(repo)
            (root/'measurements.json').write_text('{}', encoding='utf-8')
            with self.assertRaisesRegex(ValueError, 'cold hash'): self.fixture_audit(repo)

    def test_missing_file_rejected(self):
        with tempfile.TemporaryDirectory() as tmp:
            repo = Path(tmp)
            root = self.fixture(repo)
            (root/'statistics.json').unlink()
            with self.assertRaises(OSError): self.fixture_audit(repo)

    def test_resealed_incorrect_statistic_rejected(self):
        with tempfile.TemporaryDirectory() as tmp:
            repo = Path(tmp)
            root = self.fixture(repo)
            saved = audit.load(root/'statistics.json')
            saved['roles']['primary']['cells'][0]['methods']['R1']['MAE']['mean'] += 0.1
            (root/'statistics.json').write_text(json.dumps(saved), encoding='utf-8')
            self.reseal(root)
            with self.assertRaisesRegex(ValueError, 'numeric mismatch'): self.fixture_audit(repo)


if __name__ == '__main__':
    unittest.main()
