#!/usr/bin/env python

import csv
import argparse
import io
import shutil


def clean_csv(name: str) -> None:
    with open(name) as input_file:
        output_stream = io.StringIO(newline='')
        reader = csv.reader(input_file)
        writer = csv.writer(output_stream, dialect=csv.unix_dialect)
        for row in reader:
            writer.writerow([cell.replace('"', '').replace('\n', '\\n') for cell in row])

    with open(name, 'w') as output_file:
        output_stream.seek(0)
        shutil.copyfileobj(output_stream, output_file)

if __name__ == '__main__':
    parser = argparse.ArgumentParser(description='Preprocess the NSO progress trace CSV')
    parser.add_argument('csv', type=str)
    args = parser.parse_args()

    clean_csv(args.csv)
