import csv


def writr_data_to_csv(heads, data, path):
    with open(path, 'w', newline='') as f:
        write = csv.writer(f)
        write.writerow(heads)
        for i in range(len(data)):
            write.writerow(data[i])
