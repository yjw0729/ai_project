import csv


def resd_data_from_csv(path) -> list:
    with open(path, encoding='utf-8') as f:
        reader = csv.reader(f)
        data = []
        for row in reader:
            data.append(row)
    return data
