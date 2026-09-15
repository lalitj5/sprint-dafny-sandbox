import json
import time
import subprocess
import numpy as np

data = json.load(open('benchmark_data.json'))
n = len(data)

arr = np.asarray(data, dtype=np.int64)
times = []
for _ in range(10):
    a = arr.copy()
    t = time.perf_counter()
    a.sort()
    times.append(time.perf_counter() - t)
opt_sort = min(times)

e2e = []
for _ in range(5):
    t = time.perf_counter()
    a = np.asarray(data, dtype=np.int64)
    a.sort()
    b = a.tolist()
    e2e.append(time.perf_counter() - t)
opt_e2e = min(e2e)

correct = (np.sort(np.asarray(data, dtype=np.int64)).tolist() == sorted(data))

def bubble_sort(a):
    a = list(a)
    m = len(a)
    for i in range(m):
        swapped = False
        for j in range(m - i - 1):
            if a[j] > a[j + 1]:
                a[j], a[j + 1] = a[j + 1], a[j]
                swapped = True
        if not swapped:
            break
    return a

sub_n = 3000
sub = data[:sub_n]
t = time.perf_counter()
bubble_sort(sub)
bub = time.perf_counter() - t
bub_extrap = bub * (n / float(sub_n)) ** 2

orig = subprocess.run(['python', 'script.py'], capture_output=True).stdout
opt = subprocess.run(['python', 'script_optimized.py'], capture_output=True).stdout

lines = []
lines.append('benchmark_dataset_size: ' + str(n))
lines.append('optimized_algorithm: numpy in-place sort O(n log n)')
lines.append('optimized_sort_100k_seconds: ' + format(opt_sort, '.6f'))
lines.append('optimized_end_to_end_100k_seconds: ' + format(opt_e2e, '.6f'))
lines.append('optimized_under_0.01s: ' + str(opt_sort < 0.01))
lines.append('')
lines.append('bubble_measured_n: ' + str(sub_n))
lines.append('bubble_measured_seconds: ' + format(bub, '.6f'))
lines.append('bubble_estimated_100k_seconds: ' + format(bub_extrap, '.1f') + ' (labelled O(n^2) estimate, not measured)')
lines.append('')
lines.append('sorted_output_correct: ' + str(correct))
lines.append('stdout_identical_to_original_script: ' + str(orig == opt))
open('benchmark_results.txt', 'w').write(chr(10).join(lines) + chr(10))
print(chr(10).join(lines))
