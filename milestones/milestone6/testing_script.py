from time import sleep

if __name__ == '__main__':
    import statistics
    import sys
    import time

    import requests

    url, n = sys.argv[1], int(sys.argv[2])
    s = requests.Session()

    s.get(url) # single warmup request

    lat = []
    for _ in range(n):
        # Wait so we dont exceed rate limit
        sleep(0.15)

        t = time.perf_counter() # timer
        res = s.get(url) # get url
        lat.append((time.perf_counter() - t) * 1000)

        print(f'Request {_} finished: {res.text}')
        try:
            res.raise_for_status() # if an error, raise
        except Exception as e:
            print(f'Request {_} failed: {e}')
            print('Result would have been: ')
            q = statistics.quantiles(lat, n=100)
            print(f"p50={statistics.median(lat):.1f} ms  p95={q[94]:.1f} ms")
            sys.exit(1)
            

    q = statistics.quantiles(lat, n=100)
    print(f"p50={statistics.median(lat):.1f} ms  p95={q[94]:.1f} ms")

