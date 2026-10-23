"""Read-only, standard-library reproduction of saved summary statistics; no model imports."""
import argparse
import hashlib
import itertools
import json
import math
from pathlib import Path
import statistics

RUN = 'data'
METHODS = ('R0', 'R1', 'input_steady')
FIELDS = ('class_id', 'seed', 'identity', 'dose', 'odor', 'event')
T95 = 2.131449545559323
EPS = 1e-12  # Numerical tolerance only; not a meaningful-effect threshold.


def require(ok, message):
    if not ok:
        raise ValueError(message)


def load(path):
    def pairs(items):
        result = {}
        for k, v in items:
            require(k not in result, 'duplicate JSON key')
            result[k] = v
        return result
    return json.loads(path.read_text(encoding='utf-8'), object_pairs_hook=pairs,
                      parse_constant=lambda x: (_ for _ in ()).throw(ValueError('nonfinite JSON')))


def interval(values):
    mean = statistics.mean(values)
    sd = statistics.stdev(values)
    half = T95 * sd / 4
    return dict(n=16, df=15, values=values, mean=mean, SD=sd, t95=[mean-half, mean+half],
                warning='DEGENERATE_SD_NOT_POPULATION_NULL' if sd == 0 else
                'CONDITIONAL_BLOCK_IID_APPROXIMATION_SPARSE_SKEW_RISK')


def compare(actual, expected, location='statistics'):
    if isinstance(expected, dict):
        require(isinstance(actual, dict) and set(actual) == set(expected), location+' keys')
        for key in expected:
            compare(actual[key], expected[key], location+'/'+key)
    elif isinstance(expected, list):
        require(isinstance(actual, list) and len(actual) == len(expected), location+' length')
        for i, (a, e) in enumerate(zip(actual, expected)):
            compare(a, e, location+'/'+str(i))
    elif type(expected) is float:
        require(type(actual) in (int, float) and math.isfinite(actual) and
                math.isclose(actual, expected, rel_tol=1e-12, abs_tol=EPS), location+' numeric mismatch')
    else:
        require(type(actual) is type(expected) and actual == expected, location+' mismatch')


def summarize(rows, jobs):
    require(len(jobs) == 64, '64 jobs required')
    seeds = list(dict.fromkeys(j['seed'] for j in jobs))
    require(len(seeds) == 16 and all(type(s) is int and 0 <= s <= 0xffffffff for s in seeds), '16 typed seeds')
    maps = ('r3', 'r4', 'r5', 'r6')
    require({(j['class_id'], j['seed']) for j in jobs} == set(itertools.product(maps, seeds)), 'job grid')
    expected = set(itertools.product(maps, seeds, ('A', 'B'), ('1.0', '0.25'), ('A', 'B'), (1, 2)))
    grid = {}
    for row in rows:
        key = tuple(row[k] for k in FIELDS)
        require(type(row['seed']) is int and type(row['event']) is int and key in expected and key not in grid, 'row grid/duplicate/type')
        require(row['role'] == ('primary' if row['event'] == 2 else 'auxiliary'), 'endpoint role')
        require(set(row['predictions']) == set(METHODS) and set(row['errors']) == set(METHODS), 'method set')
        require(all(type(v) is float and math.isfinite(v) for v in
                    [row['observed'], *row['predictions'].values(), *row['errors'].values()]), 'finite floats required')
        require(-2 <= row['observed'] <= 2 and all(-2 <= v <= 2 for v in row['predictions'].values()), 'POST difference range')
        require(row['predictions']['R0'] == 0.0, 'R0 must be zero')
        for m in METHODS:
            compare(row['errors'][m], row['predictions'][m]-row['observed'], 'error arithmetic')
        require(isinstance(row['frozen_sha256'], str) and len(row['frozen_sha256']) == 64 and
                all(c in '0123456789abcdefABCDEF' for c in row['frozen_sha256']), 'frozen digest syntax')
        grid[key] = row
    require(set(grid) == expected, 'incomplete row grid')
    roles = {}
    for role, event in (('primary', 2), ('auxiliary', 1)):
        cells = []
        for c, identity, dose, odor in itertools.product(maps, ('A', 'B'), ('1.0', '0.25'), ('A', 'B')):
            selected = [grid[c, s, identity, dose, odor, event] for s in seeds]
            positives = sum(abs(r['observed']) > EPS for r in selected)
            methods = {}
            for m in METHODS:
                errors = [r['errors'][m] for r in selected]
                tp = sum(abs(r['observed']) > EPS and abs(r['predictions'][m]) > EPS for r in selected)
                fp = sum(abs(r['observed']) <= EPS and abs(r['predictions'][m]) > EPS for r in selected)
                methods[m] = dict(MAE=interval(list(map(abs, errors))), bias=interval(errors),
                                  RMSE=math.sqrt(statistics.mean(e*e for e in errors)), max_absolute_error=max(map(abs, errors)),
                                  numerical_classification=dict(observed_positive=positives, TP=tp, FP=fp, FN=positives-tp,
                                                                TN=16-positives-fp, sensitivity=tp/positives if positives else None,
                                                                warning='NUMERICAL_NOT_SESOI' if positives else 'UNDEFINED_ZERO_POSITIVES'))
            losses = {m: interval([abs(r['errors']['R1'])-abs(r['errors'][m]) for r in selected]) for m in ('R0', 'input_steady')}
            cells.append(dict(class_id=c, identity=identity, dose=dose, odor=odor, seed_order=seeds,
                              methods=methods, paired_absolute_loss_difference=losses, rows=selected))
        roles[role] = dict(event=event, microstep=3, cells=cells, rows=512)
    return roles


def audit(repo):
    manifest = load(Path(__file__).with_name('manifest.json'))
    for source in manifest['files']:
        path = repo/source['path']
        require(path.is_file(), 'missing source: '+source['path'])
        raw = path.read_bytes()
        require(len(raw) == source['bytes'] and hashlib.sha256(raw).hexdigest() == source['sha256'], 'manifest drift: '+source['path'])
    root = repo/RUN
    cold = load(root/'cold_evidence.json')
    for name in ('measurements', 'predictions', 'statistics'):
        ref = cold[name]
        require(ref['file'] == name+'.json', 'unexpected input path')
        raw = (root/ref['file']).read_bytes()
        require(len(raw) == ref['bytes'] and hashlib.sha256(raw).hexdigest() == ref['sha256'].lower(), 'cold hash: '+name)
    measurements = load(root/'measurements.json')
    predictions = load(root/'predictions.json')
    saved = load(root/'statistics.json')
    require(predictions['rows'] == 1024 and cold['jobs'] == 64 and cold['rows'] == 1024, 'metadata counts')
    require(measurements['predictions_sha256'].lower() == cold['predictions']['sha256'].lower(), 'prediction binding')
    jobs = [item['job'] for item in predictions['jobs']]
    require(len({(j['class_id'], j['seed']) for j in jobs}) == 64, 'duplicate job')
    for item in predictions['jobs']:
        require(len(item['frozen']) == 8, 'eight frozen refs per job')
    refs = { (item['job']['class_id'], item['job']['seed']): {f['sha256'].lower() for f in item['frozen']} for item in predictions['jobs'] }
    for row in measurements['rows']:
        require(row['frozen_sha256'].lower() in refs.get((row['class_id'], row['seed']), set()), 'frozen ref binding')
    roles = summarize(measurements['rows'], jobs)
    require(saved['status'] == 'COMPLETE_FIXED16_DESCRIPTIVE' and saved['scientific_pass'] is False and saved['top_up'] is False, 'saved status')
    compare(saved['roles'], roles)
    result = dict(task='MB-READOUT-AUDIT-PUBLIC-V1', status='SAVED_SUMMARIES_REPRODUCED', model_calls=0,
                  scientific_pass=False, submission_ready=False, human_verification='PENDING',
                  scope='Saved measurements to summaries only; not native trajectory or prediction-generation reproduction.', roles={},
                  tolerance=dict(absolute=EPS, relative=1e-12), manifest_files_checked=len(manifest['files']))
    for role, value in roles.items():
        selected = [r for r in measurements['rows'] if r['role'] == role]
        def compact(value):
            if isinstance(value, dict):
                return {k: compact(v) for k, v in value.items() if k not in ('rows', 'values', 'seed_order')}
            if isinstance(value, list):
                return [compact(v) for v in value]
            return value
        cells = [compact(cell) for cell in value['cells']]
        result['roles'][role] = dict(rows=512, cells=cells, nonzero=sum(abs(r['observed']) > EPS for r in selected),
            negative=sum(r['observed'] < -EPS for r in selected), positive=sum(r['observed'] > EPS for r in selected),
            pooled_descriptive_only={m: dict(MAE=statistics.mean(abs(r['errors'][m]) for r in selected),
                RMSE=math.sqrt(statistics.mean(r['errors'][m]**2 for r in selected))) for m in METHODS},
            dose_counts={d: dict(rows=256, nonzero=sum(abs(r['observed']) > EPS for r in selected if r['dose'] == d)) for d in ('1.0', '0.25')})
    return result


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--repo-root', type=Path, default=Path(__file__).resolve().parent)
    args = parser.parse_args()
    try:
        result = audit(args.repo_root.resolve())
    except (OSError, ValueError, KeyError, TypeError, OverflowError) as exc:
        print(json.dumps(dict(status='FAIL', error=str(exc)), ensure_ascii=False))
        return 1
    print(json.dumps(result, ensure_ascii=False, allow_nan=False))
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
