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
# Deploy to the same ECS service on each run. Print the HTTPS URL last.
# The task definition, network and HTTPS listener must already exist.
# -----------------------------------------------------------------------------
adapter_deploy() (
  local name registry repository image_id image_result image_count image_failure
  local account_id image_path version
  local service_result service_status service_failure service_action
  local task_definition task_arn deployed_arn health
  export AWS_PAGER="" MSYS_NO_PATHCONV=1
  export PYTHON="${PYTHON:-python3}"
  for name in CLI AWS_REGION IMAGE_REF ECS_CLUSTER SERVICE_NAME SERVICE_URL \
      ECS_TASK_DEFINITION ECS_CONTAINER_NAME ECS_CONTAINER_PORT \
      ECS_NETWORK_CONFIGURATION ECS_TARGET_GROUP_ARN; do
    if [[ -z "${!name:-}" ]]; then
      echo "Missing configuration: $name" >&2
      return 1
    fi
    export "$name"
  done
  for name in "$CLI" "$PYTHON" curl; do
    if ! command -v "$name" >/dev/null; then
      echo "Command not found: $name" >&2
      return 1
    fi
  done
  if [[ ! "$SERVICE_URL" =~ ^https://[^/]+/?$ ]]; then
    echo "SERVICE_URL needs an HTTPS address without a path." >&2
    return 1
  fi
  registry="${IMAGE_REF%%/*}"
  image_path="${IMAGE_REF#*/}"
  account_id="${registry%%.*}"

  if [[ ! "$account_id" =~ ^[0-9]{12}$ ]]; then
    echo "The ECR registry needs a 12-digit AWS account ID." >&2
    return 1
  fi
  if [[ "$registry" != "$account_id.dkr.ecr.$AWS_REGION.amazonaws.com" ]]; then
    echo "Use an ECR registry in $AWS_REGION." >&2
    return 1
  fi

  if [[ "$image_path" == *@sha256:* ]]; then
    repository="${image_path%@sha256:*}"
    version="${image_path##*@sha256:}"
    if [[ ! "$version" =~ ^[0-9a-f]{64}$ ]]; then
      echo "The sha256 digest must contain 64 hex characters." >&2
      return 1
    fi
    image_id="imageDigest=sha256:$version"
  elif [[ "$image_path" == *:* ]]; then
    repository="${image_path%:*}"
    version="${image_path##*:}"
    if [[ ! "$version" =~ ^[0-9a-f]{40}$ ]]; then
      echo "Use the full 40-character commit SHA as the image tag." >&2
      return 1
    fi
    image_id="imageTag=$version"
  else
    echo "IMAGE_REF needs a commit SHA tag or sha256 digest." >&2
    return 1
  fi

  if [[ ! "$repository" =~ ^[a-z0-9._/-]+$ ]]; then
    echo "Invalid ECR repository name: $repository" >&2
    return 1
  fi

  # Stop on AWS errors; don't treat them as a missing service.
  service_result=$("$CLI" ecs describe-services --region "$AWS_REGION" \
    --cluster "$ECS_CLUSTER" --services "$SERVICE_NAME" \
    --query '[services[0].status, failures[0].reason]' --output text) || return 1
  service_result=${service_result//$'\r'/}
  read -r service_status service_failure <<< "$service_result"
  if [[ "$service_status" == ACTIVE && "$service_failure" == None ]]; then
    service_action=update
  elif [[ "$service_status" == INACTIVE && "$service_failure" == None ]]; then
    service_action=create
  elif [[ "$service_status" == None && "$service_failure" == MISSING ]]; then
    service_action=create
  else
    echo "Cannot deploy: service state $service_status ($service_failure)." >&2
    return 1
  fi

  # Keep the base task's roles, secrets and other containers.
  task_definition=$("$CLI" ecs describe-task-definition --region "$AWS_REGION" \
    --task-definition "$ECS_TASK_DEFINITION" --query taskDefinition --output json) || return 1
  task_definition=$(printf '%s' "$task_definition" | "$PYTHON" -c '
import json
import os
import sys

task = json.load(sys.stdin)
if task.get("networkMode") != "awsvpc":
    sys.exit("The task definition needs awsvpc networking.")
if "FARGATE" not in task.get("requiresCompatibilities", []):
    sys.exit("The task definition needs Fargate support.")

containers = []
for container in task["containerDefinitions"]:
    if container["name"] == os.environ["ECS_CONTAINER_NAME"]:
        containers.append(container)
if len(containers) != 1:
    sys.exit("ECS_CONTAINER_NAME must match one container in the task definition.")
container = containers[0]

port = int(os.environ["ECS_CONTAINER_PORT"])
port_found = False
for mapping in container.get("portMappings", []):
    if mapping["containerPort"] == port:
        port_found = True
        break
if port != 8000 or not port_found:
    sys.exit("The Seekr container needs a port mapping for 8000.")

container["image"] = os.environ["IMAGE_REF"]
container["healthCheck"] = {
    "command": [
        "CMD",
        "python",
        "-c",
        "import urllib.request; "
        "urllib.request.urlopen(\"http://127.0.0.1:8000/health\", timeout=10).close()",
    ],
    "interval": 10,
    "timeout": 12,
    "startPeriod": 20,
    "retries": 3,
}
task["runtimePlatform"] = {
    "cpuArchitecture": "X86_64",
    "operatingSystemFamily": "LINUX",
}

# Remove read-only fields before registering the next revision.
read_only_fields = [
    "taskDefinitionArn",
    "revision",
    "status",
    "requiresAttributes",
    "compatibilities",
    "registeredAt",
    "registeredBy",
    "deregisteredAt",
]
for key in read_only_fields:
    task.pop(key, None)
print(json.dumps(task))
') || return 1

  # Skip the push if this image is already in ECR.
  image_result=$("$CLI" ecr batch-get-image --region "$AWS_REGION" \
    --registry-id "$account_id" --repository-name "$repository" --image-ids "$image_id" \
    --query '[length(images), failures[0].failureCode]' --output text) || return 1
  image_result=${image_result//$'\r'/}
  read -r image_count image_failure <<< "$image_result"
  if [[ "$image_count" == 0 && "$image_failure" == ImageNotFound ]]; then
    if [[ "$image_id" != imageTag=* ]]; then
      echo "Publish the image before using its digest." >&2
      return 1
    fi
    if ! command -v docker >/dev/null; then
      echo "Docker is required to publish the image." >&2
      return 1
    fi
    local platform
    platform=$(docker image inspect --format '{{.Os}}/{{.Architecture}}' "$IMAGE_REF") || return 1
    platform=${platform//$'\r'/}
    if [[ "$platform" != linux/amd64 ]]; then
      echo "Build and tag IMAGE_REF locally with --platform linux/amd64 first." >&2
      return 1
    fi
    "$CLI" ecr get-login-password --region "$AWS_REGION" |
      docker login --username AWS --password-stdin "$registry" || return 1
    docker push "$IMAGE_REF" || return 1
  elif [[ "$image_count" != 1 ]]; then
    echo "Cannot use IMAGE_REF: $image_failure" >&2
    return 1
  fi
  printf 'IMAGE_REF=%s\n' "$IMAGE_REF"
  task_arn=$("$CLI" ecs register-task-definition --region "$AWS_REGION" \
    --cli-input-json "$task_definition" --query taskDefinition.taskDefinitionArn --output text) || return 1
  task_arn=${task_arn//$'\r'/}
  if [[ -z "$task_arn" || "$task_arn" == None ]]; then
    echo "ECS did not return a task definition ARN." >&2
    return 1
  fi
  local -a service_options=(
    --region "$AWS_REGION"
    --cluster "$ECS_CLUSTER"
    --task-definition "$task_arn"
    --desired-count 1
    --network-configuration "$ECS_NETWORK_CONFIGURATION"
    --load-balancers "targetGroupArn=$ECS_TARGET_GROUP_ARN,containerName=$ECS_CONTAINER_NAME,containerPort=$ECS_CONTAINER_PORT"
    --health-check-grace-period-seconds 60
  )
  if [[ "$service_action" == update ]]; then
    "$CLI" ecs update-service --service "$SERVICE_NAME" "${service_options[@]}" >/dev/null || return 1
  else
    "$CLI" ecs create-service --service-name "$SERVICE_NAME" --launch-type FARGATE \
      "${service_options[@]}" >/dev/null || return 1
  fi
  "$CLI" ecs wait services-stable --region "$AWS_REGION" \
    --cluster "$ECS_CLUSTER" --services "$SERVICE_NAME" || return 1
  # Check that ECS didn't roll back to the old revision.
  deployed_arn=$("$CLI" ecs describe-services --region "$AWS_REGION" \
    --cluster "$ECS_CLUSTER" --services "$SERVICE_NAME" \
    --query 'services[0].taskDefinition' --output text) || return 1
  deployed_arn=${deployed_arn//$'\r'/}
  if [[ "$deployed_arn" != "$task_arn" ]]; then
    echo "ECS is running a different task revision." >&2
    return 1
  fi
  health=$(curl --fail --silent --show-error --connect-timeout 10 --max-time 30 \
    "${SERVICE_URL%/}/health") || return 1
  printf '%s\n' "$health"
  printf '%s' "$health" | "$PYTHON" -c '
import json
import sys

health = json.load(sys.stdin)
checks = health.get("checks", {})
if checks.get("database") != "ok":
    sys.exit("Database health check failed.")
' || return 1
  curl --silent --show-error --connect-timeout 10 --max-time 30 \
    --output /dev/null --write-out 'http=%{http_code}\n' "${SERVICE_URL%/}/" || return 1
  printf '%s\n' "${SERVICE_URL%/}"
)

# -----------------------------------------------------------------------------
# List every service in this cluster so duplicates show up in the audit.
# This doesn't cover images, task revisions or other AWS resources.
# -----------------------------------------------------------------------------
adapter_enumerate() {
  local services service service_details identifier status
  local -a service_arns=()
  for service in CLI AWS_REGION ECS_CLUSTER; do
    if [[ -z "${!service:-}" ]]; then
      echo "Missing configuration: $service" >&2
      return 1
    fi
  done
  services=$(AWS_PAGER="" "$CLI" ecs list-services --region "$AWS_REGION" \
    --cluster "$ECS_CLUSTER" --query serviceArns --output text) || return 1
  services=${services//$'\r'/}
  if [[ -z "$services" || "$services" == None ]]; then
    return 0
  fi
  services=${services//$'\n'/ }
  read -r -a service_arns <<< "$services"
  for service in "${service_arns[@]}"; do
    service_details=$(AWS_PAGER="" "$CLI" ecs describe-services --region "$AWS_REGION" \
      --cluster "$ECS_CLUSTER" --services "$service" \
      --query 'services[0].[serviceArn, status]' --output text) || return 1
    service_details=${service_details//$'\r'/}
    read -r identifier status <<< "$service_details"
    if [[ -z "$identifier" || "$identifier" == None ]]; then
      echo "Could not read ECS service: $service" >&2
      return 1
    fi
    if [[ -z "$status" || "$status" == None ]]; then
      echo "Could not read the status of ECS service: $service" >&2
      return 1
    fi
    printf 'ecs-service\t%s\t%s\n' "$identifier" "$status"
  done
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
