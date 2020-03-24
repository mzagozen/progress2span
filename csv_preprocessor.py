#!/usr/bin/env python

import csv
import argparse
import io
import shutil


def clean_csv(csv_in: str, csv_out: str) -> None:
    with open(csv_in) as input_file:
        output_stream = io.StringIO(newline='')
        reader = csv.reader(input_file)
        writer = csv.writer(output_stream, dialect=csv.unix_dialect)
        for row in reader:
            # skip some subsystems:
            # - cdb: because of the weird interleaving bug
            # - xpath: because of verbosity++
            if row[4] in ('cdb', 'xpath'):
                continue
            writer.writerow([cell.replace('"', '').replace('\n', '\\n') for cell in row])

    with open(csv_out, 'w') as output_file:
        output_stream.seek(0)
        shutil.copyfileobj(output_stream, output_file)

if __name__ == '__main__':
    parser = argparse.ArgumentParser(description='Preprocess the NSO progress trace CSV')
    parser.add_argument('csv_in', type=str, help="Name of the input CSV file")
    parser.add_argument('csv_out', type=str, help="Name of the output CSV file")
    args = parser.parse_args()

    clean_csv(args.csv_in, args.csv_out)
