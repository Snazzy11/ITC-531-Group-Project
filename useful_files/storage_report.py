import argparse, re, sys
from botocore.exceptions import BotoCoreError, ClientError
from store import Store

SCHEME = re.compile(
    r"(uploads|direct)/\d{4}/\d{2}/\d{2}/"
    r"[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}\.[a-z0-9]+"
)


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--prefix", default="")
    args = ap.parse_args()

    try:
        store = Store()
        items = list(store.list(args.prefix))

        unstamped = []
        for o in items:
            head = store.head(o.key)
            if head is None or "original-name" not in head["Metadata"]:
                unstamped.append(o.key)
    except (BotoCoreError, ClientError, KeyError) as exc:
        print(f"ERROR: could not run report: {exc!r}", file=sys.stderr)
        return 2

    off_scheme = [o.key for o in items if not SCHEME.fullmatch(o.key)]

    totals = {}
    for o in items:
        top = o.key.split("/")[0]
        totals[top] = totals.get(top, 0) + o.size
    grand = sum(totals.values())

    print(f"Storage report: bucket={store.bucket} prefix={args.prefix!r} objects={len(items)}")
    print(f"\nUnstamped objects (no original-name): {len(unstamped)}")
    for k in unstamped:
        print(f"  {k}")
    print(f"\nOff-scheme keys: {len(off_scheme)}")
    for k in off_scheme:
        print(f"  {k}")
    print("\nBytes by top-level prefix:")
    for top in sorted(totals):
        print(f"  {top}: {totals[top]}")
    print(f"  TOTAL: {grand}")

    return 0 if not unstamped and not off_scheme else 1


if __name__ == "__main__":
    sys.exit(main())
