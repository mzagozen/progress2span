import glob
import gzip
import re
import shutil
import subprocess
import argparse
import sys
import pathlib
from typing import Optional, Set

import csv_preprocessor


def normalize_filename(filename: str) -> str:
    return re.sub(r'\.gz$', '', filename)

def done_read() -> Set[str]:
    try:
        s = set()
        with open('progress.done') as f:
            for l in f.readlines():
                s.add(l.strip())
        return s
    except FileNotFoundError:
        return set()

def done_update(name: str) -> None:
    with open('progress.done', 'a+') as f:
        f.write(normalize_filename(name))
        f.write('\n')

def find_candidates(pattern: str, force: bool = False) -> Set[str]:
    current = set((f, normalize_filename(f)) for f in glob.glob(pattern))
    if force:
        candidates = set(c[0] for c in current)
        return candidates

    done = done_read()
    candidates = set()
    for c, cn in current:
        if c not in done and cn not in done:
            candidates.add(c)
    return candidates

def gunzip(src: str, dst: str) -> None:
    with gzip.open(src, 'rb') as f1, \
         open(dst, 'wb') as f2:
        shutil.copyfileobj(f1, f2)

def csv_extract_and_preprocess(name: str) -> str:
    if name.endswith('.gz'):
        csv_name = normalize_filename(name)
        gunzip(name, csv_name)
    else:
        csv_name = name

    csv_preprocessor.clean_csv(csv_name)
    return csv_name

def audit_extract(name: str) -> str:
    if name.endswith('.gz'):
        audit_name = normalize_filename(name)
        gunzip(name, audit_name)
    else:
        audit_name = name
    return audit_name

def find_audit_log(csv_name: str, pattern: Optional[str] = None) -> Optional[str]:
    if pattern:
        for f in glob.glob(pattern):
            return f
    else:
        match = re.search(r'(\d{8})(?:\.csv)?', csv_name)
        if match:
            date_part = match.groups()[0]
            folder = pathlib.Path(csv_name).parent
            pattern = folder / pathlib.Path(f'audit.log-{date_part}*')
            for f in glob.glob(str(pattern)):
                return f
    return None

def progress2span(csv_name: str, json_name: str, audit_name: Optional[str] = None, docker: bool = False) -> bool:
    if docker:
        args = ['docker', 'run', '-it', '--rm', '-v', f'{pathlib.Path.cwd()}:/app', '-w', '/app', 'erlang']
    else:
        args = []
    args.extend(['escript', 'progress2span.erl', csv_name, json_name, '-tu'])
    if audit_name:
        args.extend(('-a', audit_name))
    process = subprocess.Popen(args, stdout=sys.stdout, stderr=sys.stderr)
    code = process.wait()
    print(f'Exited with code {code}')
    return code == 0

def upload_json(json_name: str, url: str) -> bool:
    args = ['curl', '--noproxy', '*', '-v', '-H', 'Content-Type: application/json', url, '--data-binary', f'@{json_name}']
    process = subprocess.Popen(args, stdout=sys.stdout, stderr=sys.stderr)
    code = process.wait()
    print(f'Exited with code {code}')
    return code == 0

def cleanup(name) -> None:
    p = pathlib.Path(name)
    if p.is_file():
        p.unlink()

if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('pattern', default='progress-trace.log*', type=str)
    parser.add_argument('--audit-pattern', type=str)
    parser.add_argument('--jaeger-url', default='http://127.0.0.1:9411/api/v2/spans')
    parser.add_argument('--docker', action='store_true')
    parser.add_argument('--force', action='store_true')
    args = parser.parse_args()

    for cp in find_candidates(args.pattern, args.force):
        csv = csv_extract_and_preprocess(cp)
        ca = find_audit_log(csv, args.audit_pattern)
        if ca:
            audit_log = audit_extract(ca)
            print(f'Found audit log {audit_log}')
        else:
            audit_log = None

        json = f'{csv}.json'
        success_json = progress2span(csv, json, audit_log, args.docker)
        if success_json:
            success_upload = upload_json(json, args.jaeger_url)
            if success_upload:
                done_update(cp)

        if cp != csv:
            cleanup(csv)
        if ca != audit_log:
            cleanup(audit_log)
        cleanup(json)

    #progress2span('progress-trace.log-20200322', 'progress-trace.log-20200322.json')
