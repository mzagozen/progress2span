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

def mark_done(name: str) -> None:
    pathlib.Path(name + '.done').touch()

def find_candidates(pattern: str, force: bool = False) -> Set[str]:
    # if the pattern ends with '*', it will pick up '*.done' files too. but if
    # it doesn't, include '<pattern>.done' explicitly
    if pattern.endswith('*'):
        every = glob.glob(pattern)
    else:
        every = glob.glob(pattern) + glob.glob(pattern + '.done')
    every_file = set(c for c in every if not c.endswith('.done'))
    if force:
        return every_file

    done = set(re.sub(r'\.done$', '', c) for c in every if c.endswith('.done'))
    print(f'{every}\n{every_file}\n{done}')
    return every_file - done

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

    csv_name_clean = f'{csv_name}-processed'
    csv_preprocessor.clean_csv(csv_name, csv_name_clean)
    return csv_name_clean

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
    args.extend(['escript', 'progress2span.erl', csv_name, json_name, '-tu', '-d'])
    if audit_name:
        args.extend(('-a', audit_name))
    process = subprocess.Popen(args, stdout=sys.stdout, stderr=sys.stderr)
    code = process.wait()
    print(f'Exited with code {code}')
    return code == 0

def upload_json(json_name: str, url: str) -> bool:
    args = ['curl', '--fail', '--noproxy', '*', '-v', '-H', 'Content-Type: application/json', url, '--data-binary', f'@{json_name}']
    process = subprocess.Popen(args, stdout=sys.stdout, stderr=sys.stderr)
    code = process.wait()
    print(f'Exited with code {code}')
    return code == 0


def remove_if_exists(name: str) -> None:
    p = pathlib.Path(name)
    if p.is_file():
        p.unlink()

def cleanup(name: str) -> None:
    """Remove extracted / generated files

    The input parameter is a log or CSV filename. This function will remove the
    extracted file if a .gz file with the same name is found. It will also
    remove the '*-processed' files."""

    # remove extracted file if there is an archive
    if name.endswith('.gz'):
        extracted_file = re.sub(r'\.gz$', '', name)
        remove_if_exists(extracted_file)
    else:
        extracted_file = name

    # remove '*-processed' files
    for f in glob.glob(f'{extracted_file}-processed*'):
        remove_if_exists(f)

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
                mark_done(cp)
                if ca:
                    mark_done(ca)

                cleanup(cp)
                if ca:
                    cleanup(ca)

    #progress2span('progress-trace.log-20200322', 'progress-trace.log-20200322.json')
