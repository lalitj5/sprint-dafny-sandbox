def bubble_sort(arr):
    n = len(arr)
    for i in range(n):
        for j in range(0, n-i-1):
            if arr[j] > arr[j+1]:
                arr[j], arr[j+1] = arr[j+1], arr[j]
    return arr

if __name__ == "__main__":
    # Highly inefficient array generation and sorting
    import random
    arr = [random.randint(1, 1000) for _ in range(5000)]
    print("Sorting array of size 5000...")
    bubble_sort(arr)
    print("Done!")
