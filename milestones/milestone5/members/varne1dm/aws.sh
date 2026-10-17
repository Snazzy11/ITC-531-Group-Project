#!/usr/bin/env bash
# =============================================================================
# ITC 531 — Provider adapter template
#
# THIS FILE IS YOUR WORK. Copy it to adapters/<yourprovider>.sh and implement the
# five functions below using your chosen provider's CLI or API.
#
# It is the primary artifact for SLO 3 ("develop scripts to assist in the
# management and automation of current cloud platform solutions"). The course
# deliberately does not write it for you, because the whole point is that you
# can automate a platform you selected yourself against a stated contract.
#
# The course scripts (cloud-verify / cloud-audit / cloud-down) source this file
# and call these functions. They never call a provider directly.
#
# RULES
#   1. Every function must be safe to run twice.
#   2. adapter_destroy must remove everything adapter_deploy created. If you
#      cannot destroy it, do not create it.
#   3. Print to stdout. Return 0 for success, non-zero for failure.
#   4. Never echo a secret. `set -x` is not your friend here.
#   5. Read configuration from adapters/<yourprovider>.env. No literals.
# =============================================================================

set -euo pipefail

# -----------------------------------------------------------------------------
# adapter_meta — who you are targeting and what you claim it does.
# Printed by every course script so your evidence is self-describing.
# -----------------------------------------------------------------------------
adapter_meta() {
  cat <<META
provider:        ${PROVIDER_NAME}
region:          ${PROVIDER_REGION}
compute service: ${COMPUTE_SERVICE}
storage service: ${STORAGE_SERVICE}
auth model:      ${AUTH_MODEL}
contract check:  ${CONTRACT_CHECKED}
META
}

# -----------------------------------------------------------------------------
# C1-C6: adapter_verify
#
# Prove the target satisfies the capability contract, WITHOUT creating anything
# that costs money. Read-only calls only. This is the Module 6 gate.
#
# Required checks:
#   C1  the container service exists and you are authenticated to it
#   C2  the S3-compatible endpoint answers a signed list-buckets
#   C3  the credential in use is NOT account-wide (print its scope)
#   C4  an enumerate command exists and returns (even if empty)
#   C5  a spend alert is configured — print its threshold
#   C6  print the current published free allowance or expected term cost
# -----------------------------------------------------------------------------

check_compute() {
  # TODO C1: one read-only call proving you are authenticated to the service
  #          that runs an OCI image. Use "$CLI" and values from the .env.
  local result

  if result=$("$CLI" ecs describe-clusters \
      --output text \
      --clusters "${ECS_CLUSTER}" \
      --query 'clusters[0].status'); then

    if [[ "$result" == "ACTIVE" ]]; then
      echo "OK - ECS cluster status: ${result}"
      return 0
    else
      echo "FAIL - ECS cluster status: ${result}"
      return 1
    fi
  else
    echo "Fail - Unable to describe ECS cluster: ${result}"
    return 1
  fi
}

check_storage() {
  # TODO C2: one signed, read-only call against $S3_ENDPOINT_URL.
  local result

  if result=$("$CLI" s3api list-buckets --endpoint-url "${S3_ENDPOINT_URL}" --query "Buckets[].[Name]" --output text); then
    echo "OK - Endpoint reachable, Name: ${result}"
    return 0
  else
    echo "FAIL - Endpoint unreachable: ${result}"
    return 1
  fi
}

check_credential() {
  # TODO C3: print the credential's ACTUAL scope as the provider reports it
  #          (A7), not the word "scoped". Never echo the credential (A5).
  local result

  if result=$("$CLI" iam list-attached-user-policies --user-name "$IAM_USER_NAME" --query 'AttachedPolicies[].PolicyName' --output text); then

    if [[ -n "$result" && "$result" != "None" ]]; then
      echo "OK - Authenticated with IAM policy: ${result}"
      return 0
    else
      echo "FAIL - No attached IAM policies found"
      return 1
    fi
  else
    echo "FAIL - Unable to retrieve IAM policies"
    return 1
  fi
}

check_enumerate() {
  # TODO C4: call the documented list command and report what came back, even
  #          when that is zero resources. This is the command teardown rests on.
  local result

  if result=$("$CLI" ecs list-clusters --output text --query 'clusterArns'); then
    echo "OK - Cluster reachable and enumerated: ${result}"
    return 0
  else
    echo "FAIL - Cluster unreachable: ${result}"
    return 1
  fi
}

check_spend_alert() {
  # TODO C5: report the threshold you configured, from SPEND_ALERT_THRESHOLD.
  echo \$${SPEND_ALERT_THRESHOLD}
}

check_cost_model() {
  # TODO C6: report the published free allowance, or the term's expected cost.
  echo \$100 Free Credit / 6 month free account period / 5 GB Storage - More than satisfiable for all our expected needs.
}

adapter_verify() {
  status=0
  line="$(check_compute)"     || status=1; echo "C1 compute      : ${line}"
  line="$(check_storage)"     || status=1; echo "C2 storage      : ${line}"
  line="$(check_credential)"  || status=1; echo "C3 credential   : ${line}"
  line="$(check_enumerate)"   || status=1; echo "C4 enumerate    : ${line}"
  line="$(check_spend_alert)" || status=1; echo "C5 spend alert  : ${line}"  
  line="$(check_cost_model)"  || status=1; echo "C6 cost model   : ${line}"
  return $status
}

# -----------------------------------------------------------------------------
# adapter_deploy — push the image and run it. Must print the resulting HTTPS URL
# on the last line of stdout, and nothing else on that line.
#
# It must be idempotent: running it twice updates the running service rather
# than creating a second one.
# -----------------------------------------------------------------------------
adapter_deploy() {
  echo "NOT IMPLEMENTED" >&2; return 1
}

# -----------------------------------------------------------------------------
# adapter_enumerate — list everything that exists in the account, one resource
# per line, in the form:   <type>  <identifier>  <state>
#
# `bash scripts/cloud-audit.sh <yourprovider>` treats ANY output as a failure at teardown time, so this
# must be complete. An adapter that under-reports is worse than none: it is how
# a student ends the term believing they cleaned up when they did not.
# -----------------------------------------------------------------------------
adapter_enumerate() {
  echo "NOT IMPLEMENTED" >&2; return 1
}

# -----------------------------------------------------------------------------
# adapter_destroy — remove everything adapter_deploy created, then verify by
# calling adapter_enumerate and failing if anything remains.
#
# Object storage note: a bucket delete fails while objects remain, and on a
# versioned bucket "remove the objects" also means the non-current versions AND
# the delete markers. app/ports/storage.py:empty_bucket() does this correctly —
# call it rather than reimplementing it.
# -----------------------------------------------------------------------------
adapter_destroy() {
  echo "NOT IMPLEMENTED" >&2; return 1
}

# =============================================================================
# ILLUSTRATIVE FRAGMENTS
#
# Three shapes, so you can see that the pattern is provider-SHAPED rather than
# provider-SPECIFIC. These were syntactically current on 2026-07-28. Treat them
# as a starting point to check against today's documentation, NOT as answers.
# The course does not endorse or require any of these.
#
# --- shape A: a CLI with an explicit deploy verb -----------------------------
# adapter_deploy() {
#   "$CLI" auth login --token "$PROVIDER_TOKEN" >/dev/null
#   "$CLI" image push "$IMAGE_REF"
#   "$CLI" service update "$SERVICE_NAME" --image "$IMAGE_REF" --env-file "$ENV_FILE"
#   "$CLI" service describe "$SERVICE_NAME" --format '{{.URL}}'   # last line = URL
# }
#
# --- shape B: a registry push plus a declarative apply ------------------------
# adapter_deploy() {
#   docker push "$IMAGE_REF"
#   "$CLI" apply -f infra/service.yaml
#   "$CLI" get service "$SERVICE_NAME" -o jsonpath='{.status.url}'
# }
#
# --- shape C: OpenTofu all the way ------------------------------------------
# adapter_deploy() {
#   tofu -chdir=infra/tofu init -input=false
#   tofu -chdir=infra/tofu apply -auto-approve -var "image=$IMAGE_REF"
#   tofu -chdir=infra/tofu output -raw service_url
# }
# adapter_destroy() {
#   tofu -chdir=infra/tofu destroy -auto-approve
#   adapter_enumerate | tee /dev/stderr | grep -q . && { echo "residue remains"; return 1; }
#   return 0
# }
# =============================================================================
