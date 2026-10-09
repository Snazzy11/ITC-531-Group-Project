#!/usr/bin/env bash
# Builds milestone4.zip at the repository root: this folder plus the code it
# describes. Stops if any secret or password from store.env or .env.local made
# it into the ZIP.
#
#   milestones/milestone4/package.sh

set -euo pipefail
cd "$(dirname "$0")/../.."

for name in upload presigned report-clean report-dirty teardown; do
    if [ ! -s "milestones/milestone4/evidence/$name.txt" ]; then
        echo "STOP: evidence/$name.txt is missing; run milestones/milestone4/evidence/capture.sh first" >&2
        exit 1
    fi
done
if grep -rn "TODO(team)" milestones/milestone4 --include=*.md; then
    echo "WARNING: the TODO(team) items above are still open" >&2
fi

STAGE=$(mktemp -d)
trap 'rm -rf "$STAGE"' EXIT
DEST=$STAGE/milestone4

mkdir -p "$DEST/app/ports" "$DEST/app/routers" "$DEST/app/database" "$DEST/scripts"
cp -r milestones/milestone4/{README.md,STORAGE_DESIGN.md,PROVIDER_SHORTLIST.md,COST_AND_RISK.md,architecture-diagram.png,sources.md,adapters,evidence} "$DEST/"
cp app/{api.py,dependencies.py,presenters.py,messaging.py,crud.py,schemas.py,errors.py,image_processing.py,image_worker.py} "$DEST/app/"
cp app/routers/*.py "$DEST/app/routers/"
cp app/ports/storage.py "$DEST/app/ports/"
cp app/database/models.py "$DEST/app/database/"
cp scripts/storage_report.py "$DEST/scripts/"
cp gateway.conf "$DEST/"

leaked=0
for env in store.env .env.local; do
    [ -f "$env" ] || continue
    while IFS= read -r value; do
        if [ -n "$value" ] && grep -rqF -- "$value" "$DEST"; then
            echo "STOP: a secret from $env appears in:" >&2
            grep -rlF -- "$value" "$DEST" | sed "s|$STAGE/||" >&2
            leaked=1
        fi
    done < <(sed -n -E 's/^[A-Z_]*(SECRET|PASSWORD)[A-Z_]*=//p' "$env")
done
[ "$leaked" = 0 ] || exit 1

rm -f milestone4.zip
(cd "$STAGE" && uv run --no-project python -m zipfile -c "$OLDPWD/milestone4.zip" milestone4)
echo "Built milestone4.zip"
