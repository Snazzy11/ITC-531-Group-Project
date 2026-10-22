#!/usr/bin/env bash
# Builds final_product_<team>.zip at the repository root, laid out as the final
# product spec asks. Stops if a secret from the local env files, a private key,
# a bare JWT or an unredacted presigned signature made it into the bundle.
#
#   final_product/package.sh <teamname>

set -euo pipefail
cd "$(dirname "$0")/.."

team=${1:?usage: final_product/package.sh <teamname>}
name="final_product_$team"
src=final_product

missing=0
for file in README.md ARCHITECTURE.md EVALUATION.md sources.md \
    evidence/walkthrough.md evidence/metrics-scrape.txt evidence/dashboard-panel.png \
    evidence/ci-and-deploy.md evidence/transcripts/01-relational-postgres.txt \
    teardown/residual-risk.md; do
  if [ ! -s "$src/$file" ]; then
    echo "MISSING: $src/$file" >&2
    missing=1
  fi
done
[ "$missing" = 0 ] || { echo "STOP: add the files above first" >&2; exit 1; }
for file in audit-before.txt cloud-down.txt audit-after-CLEAN.txt; do
  # Teardown may be submitted after the rest (the spec's one exemption), so this only warns.
  [ -s "$src/teardown/$file" ] || echo "WARNING: teardown/$file is not there yet" >&2
done
if grep -rn "TODO(team)" "$src" --include=*.md; then
  echo "WARNING: the TODO(team) items above are still open" >&2
fi

stage=$(mktemp -d)
trap 'rm -rf "$stage"' EXIT
dest="$stage/$name"
mkdir -p "$dest/adapters"
cp -r "$src"/{README.md,ARCHITECTURE.md,EVALUATION.md,sources.md,evidence,teardown} "$dest/"
cp adapters/aws.env.example "$dest/adapters/"
find "$dest" \( -name '*.pem' -o -name '*.env' -o -name '.env*' \) -print -delete

leaked=0
for env in .env.local adapters/aws.env store.env; do
  [ -f "$env" ] || continue
  while IFS= read -r value; do
    value=${value%\"}; value=${value#\"}
    if [ ${#value} -ge 6 ] && grep -rqF -- "$value" "$dest"; then
      echo "STOP: a secret from $env appears in:" >&2
      grep -rlF -- "$value" "$dest" | sed "s|$stage/||" >&2
      leaked=1
    fi
  done < <(sed -n -E 's/^[A-Z_]*(SECRET|PASSWORD|_KEY)[A-Z_]*=//p' "$env")
done
if grep -rlE -- '-----BEGIN [A-Z ]*PRIVATE KEY-----|eyJ[A-Za-z0-9_-]{20,}\.eyJ|X-Amz-(Signature|Credential)=[A-Za-z0-9%]' "$dest"; then
  echo "STOP: a private key, a JWT or an unredacted presigned URL is in the files above" >&2
  leaked=1
fi
[ "$leaked" = 0 ] || exit 1

rm -f "$name.zip"
(cd "$stage" && python3 -m zipfile -c "$OLDPWD/$name.zip" "$name")
echo "Built $name.zip"
