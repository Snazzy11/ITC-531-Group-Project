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

  if [[ "${DEPLOY_TARGET:-}" == ec2 ]]; then
    if result=$("$CLI" ec2 describe-instances --region "$AWS_REGION" \
        --instance-ids "$EC2_INSTANCE_ID" --output text \
        --query 'Reservations[0].Instances[0].State.Name'); then
      echo "OK - EC2 instance ${EC2_INSTANCE_ID} state: ${result}"
      return 0
    fi
    echo "FAIL - Unable to describe EC2 instance ${EC2_INSTANCE_ID}"
    return 1
  fi

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
# DEPLOY_TARGET=ecs (Milestone 6): deploy to the same ECS service on each run.
# Print the HTTPS URL last. The task definition, network and HTTPS listener
# must already exist.
# -----------------------------------------------------------------------------
deploy_ecs() (
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
# This doesn't cover images, task revisions or other AWS resources;
# enumerate_region below does.
# -----------------------------------------------------------------------------
enumerate_ecs() {
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
# Remove the configured ECS service. Other AWS resources stay in place.
# -----------------------------------------------------------------------------
destroy_ecs() (
  local result status failure tasks task
  export AWS_PAGER="" MSYS_NO_PATHCONV=1
  if [[ -z "${CLI:-}" || -z "${AWS_REGION:-}" ||
        -z "${ECS_CLUSTER:-}" || -z "${SERVICE_NAME:-}" ]]; then
    echo "Set CLI, AWS_REGION, ECS_CLUSTER and SERVICE_NAME in aws.env." >&2
    return 1
  fi

  result=$("$CLI" ecs describe-services --region "$AWS_REGION" \
    --cluster "$ECS_CLUSTER" --services "$SERVICE_NAME" \
    --query '[services[0].status, failures[0].reason]' --output text) || return 1
  result=${result//$'\r'/}
  read -r status failure <<< "$result"

  if [[ "$status" == None && "$failure" == MISSING ]]; then
    echo "$SERVICE_NAME is already removed."
  elif [[ "$failure" != None ]]; then
    echo "Cannot remove service: $failure." >&2
    return 1
  elif [[ "$status" == ACTIVE || "$status" == DRAINING || "$status" == INACTIVE ]]; then
    if [[ "$status" == ACTIVE ]]; then
      "$CLI" ecs update-service --region "$AWS_REGION" --cluster "$ECS_CLUSTER" \
        --service "$SERVICE_NAME" --desired-count 0 >/dev/null || return 1
      "$CLI" ecs wait services-stable --region "$AWS_REGION" \
        --cluster "$ECS_CLUSTER" --services "$SERVICE_NAME" || return 1
    fi

    # Wait for tasks that are still stopping.
    tasks=$("$CLI" ecs list-tasks --region "$AWS_REGION" --cluster "$ECS_CLUSTER" \
      --service-name "$SERVICE_NAME" --desired-status STOPPED \
      --query taskArns --output text) || return 1
    tasks=${tasks//$'\r'/}
    for task in $tasks; do
      if [[ "$task" != None ]]; then
        "$CLI" ecs wait tasks-stopped --region "$AWS_REGION" \
          --cluster "$ECS_CLUSTER" --tasks "$task" || return 1
      fi
    done

    if [[ "$status" == ACTIVE ]]; then
      "$CLI" ecs delete-service --region "$AWS_REGION" \
        --cluster "$ECS_CLUSTER" --service "$SERVICE_NAME" >/dev/null || return 1
    fi
    "$CLI" ecs wait services-inactive --region "$AWS_REGION" \
      --cluster "$ECS_CLUSTER" --services "$SERVICE_NAME" || return 1
  else
    echo "Cannot remove service in state: $status." >&2
    return 1
  fi

  result=$(enumerate_ecs) || return 1
  if [[ -n "$result" ]]; then
    printf 'ECS services still remain:\n%s\n' "$result" >&2
    return 1
  fi
  echo "ECS service cleanup finished. Other AWS resources were not removed."
)

# =============================================================================
# DEPLOY_TARGET=ec2 (final product): the whole compose stack on one EC2
# instance. The instance, its security group and the Cloudflare R2 bucket were
# made by hand; adapter_destroy removes all three. The app's settings and
# secrets live in .env.local on the instance. Nothing here reads or prints it.
# =============================================================================

ec2_ssh() {
  local -a options=(-i "$EC2_SSH_KEY" -o BatchMode=yes -o ConnectTimeout=15
    -o StrictHostKeyChecking=accept-new)
  if [[ -n "${EC2_KNOWN_HOSTS:-}" ]]; then
    options+=(-o "UserKnownHostsFile=$EC2_KNOWN_HOSTS")
  fi
  ssh "${options[@]}" "$EC2_SSH_USER@$EC2_HOST" "$@"
}

# Runs a command that changes something, or with ADAPTER_DRY_RUN=1 prints it
# instead. Read-only calls don't go through this.
mutate() {
  if [[ "${ADAPTER_DRY_RUN:-}" == 1 ]]; then
    printf 'DRY RUN, would run:'
    printf ' %q' "$@"
    printf '\n'
  else
    "$@"
  fi
}

# Reports a step that went through mutate(), marked when nothing really ran.
done_echo() {
  if [[ "${ADAPTER_DRY_RUN:-}" == 1 ]]; then
    printf '(dry run) %s\n' "$*"
  else
    printf '%s\n' "$*"
  fi
}

# Check out DEPLOY_SHA on the instance, build and start the stack, check
# /health from here, and print the URL last. Safe to run again: the same SHA
# rebuilds and restarts the API and workers, and the data volumes stay.
deploy_ec2() (
  local name health remote_args
  export PYTHON="${PYTHON:-python3}"
  for name in EC2_HOST EC2_SSH_USER EC2_SSH_KEY EC2_APP_DIR DEPLOY_SHA SERVICE_URL; do
    if [[ -z "${!name:-}" ]]; then
      echo "Missing configuration: $name" >&2
      return 1
    fi
  done
  for name in ssh curl "$PYTHON"; do
    if ! command -v "$name" >/dev/null; then
      echo "Command not found: $name" >&2
      return 1
    fi
  done
  if [[ ! "$DEPLOY_SHA" =~ ^[0-9a-f]{40}$ ]]; then
    echo "DEPLOY_SHA must be the full 40-character commit SHA." >&2
    return 1
  fi
  if [[ ! "$SERVICE_URL" =~ ^https?://[^/]+/?$ ]]; then
    echo "SERVICE_URL needs an address without a path." >&2
    return 1
  fi

  printf 'deploy %s to %s@%s:%s at %s\n' "$DEPLOY_SHA" "$EC2_SSH_USER" "$EC2_HOST" \
    "$EC2_APP_DIR" "$(date -u '+%Y-%m-%d %H:%M:%S UTC')"
  # The values go to the remote script as quoted arguments, not pasted into it.
  remote_args=$(printf '%q ' "$EC2_APP_DIR" "$DEPLOY_SHA")
  ec2_ssh "bash -s -- $remote_args" <<'REMOTE' || return 1
set -euo pipefail
cd "$1"
sha=$2
if [[ -n "$(git status --porcelain --untracked-files=no)" ]]; then
  echo "The checkout on the instance has local changes; deploy refused." >&2
  exit 1
fi
if [[ ! -f .env.local ]]; then
  echo ".env.local is missing on the instance." >&2
  exit 1
fi
git fetch --quiet origin
git -c advice.detachedHead=false checkout --quiet --detach "$sha"
echo "checked out $(git rev-parse HEAD)"
compose=(docker compose --env-file .env.local)
# </dev/null everywhere: this script arrives on stdin, so nothing may read it.
"${compose[@]}" build --quiet </dev/null
# As in CI: --wait rejects the workers, whose health check is turned off, so
# wait for the rest and check that no worker exited. sed only trims the
# progress lines; with pipefail a compose failure still fails the deploy.
"${compose[@]}" up -d --wait --wait-timeout 300 gateway app prometheus grafana \
  </dev/null 2>&1 | sed -E '/ (Waiting|Healthy)$/d'
"${compose[@]}" up -d matching_worker image_worker logger notifier </dev/null 2>&1 |
  sed -E '/ (Waiting|Healthy)$/d'
sleep 5
exited=$("${compose[@]}" ps --status exited --services </dev/null)
if [[ -n "$exited" ]]; then
  echo "These services exited: $exited" >&2
  exit 1
fi
# compose tags what it builds :latest. Tag the API image with the commit too and
# print its content-addressed id, which is what the containers actually run.
container=$("${compose[@]}" ps -q app </dev/null)
image_id=$(docker inspect --format '{{.Image}}' "$container")
repository=$(docker inspect --format '{{.Config.Image}}' "$container")
repository=${repository%:*}
docker tag "$image_id" "$repository:$sha"
echo "IMAGE_REF=$repository:$sha"
echo "IMAGE_ID=$image_id"
"${compose[@]}" ps --format 'table {{.Service}}\t{{.Image}}\t{{.Status}}' </dev/null
REMOTE

  health=$(curl --fail --silent --show-error --connect-timeout 10 --max-time 30 \
    "${SERVICE_URL%/}/health") || return 1
  printf '%s\n' "$health"
  printf '%s' "$health" | "$PYTHON" -c '
import json
import sys

if json.load(sys.stdin).get("checks", {}).get("database") != "ok":
    sys.exit("Database health check failed.")
' || return 1
  printf '%s\n' "${SERVICE_URL%/}"
)

# One "<kind>\t<columns>" line per row a read-only AWS call returns. A failed
# call is an error, never an empty list: an audit that can't look must not
# print CLEAN.
aws_rows() {
  local kind=$1 out line
  shift
  if ! out=$(AWS_PAGER="" "$CLI" "$@" --region "$AWS_REGION" --output text); then
    echo "Could not list $kind; the audit is incomplete." >&2
    return 1
  fi
  out=${out//$'\r'/}
  while IFS= read -r line; do
    if [[ -n "$line" && "$line" != None ]]; then
      printf '%s\t%s\n' "$kind" "$line"
    fi
  done <<< "$out"
}

# Everything in AWS_REGION that costs money or holds our data, whoever made it,
# so leftovers from Milestone 6 show up too. The default VPC and its default
# security group are left out. IAM, budgets and other regions are not checked.
enumerate_region() {
  aws_rows ec2-instance ec2 describe-instances \
    --filters Name=instance-state-name,Values=pending,running,shutting-down,stopping,stopped \
    --query 'Reservations[].Instances[].[InstanceId,State.Name,InstanceType,PublicIpAddress]' || return 1
  aws_rows ebs-volume ec2 describe-volumes \
    --query 'Volumes[].[VolumeId,State,Size]' || return 1
  aws_rows ebs-snapshot ec2 describe-snapshots --owner-ids self \
    --query 'Snapshots[].[SnapshotId,StartTime]' || return 1
  aws_rows ami ec2 describe-images --owners self \
    --query 'Images[].[ImageId,Name]' || return 1
  aws_rows elastic-ip ec2 describe-addresses \
    --query 'Addresses[].[AllocationId,PublicIp]' || return 1
  aws_rows nat-gateway ec2 describe-nat-gateways \
    --filter Name=state,Values=pending,available \
    --query 'NatGateways[].[NatGatewayId,State]' || return 1
  aws_rows security-group ec2 describe-security-groups \
    --query "SecurityGroups[?GroupName!='default'].[GroupId,GroupName]" || return 1
  aws_rows key-pair ec2 describe-key-pairs \
    --query 'KeyPairs[].[KeyPairId,KeyName]' || return 1
  aws_rows load-balancer elbv2 describe-load-balancers \
    --query 'LoadBalancers[].[LoadBalancerArn,State.Code]' || return 1
  aws_rows target-group elbv2 describe-target-groups \
    --query 'TargetGroups[].[TargetGroupArn]' || return 1
  aws_rows http-api apigatewayv2 get-apis \
    --query 'Items[].[ApiId,Name,ApiEndpoint]' || return 1
  aws_rows ecs-cluster ecs list-clusters --query 'clusterArns[]' || return 1
  aws_rows ecr-repository ecr describe-repositories \
    --query 'repositories[].[repositoryName]' || return 1
  aws_rows rds-instance rds describe-db-instances \
    --query 'DBInstances[].[DBInstanceIdentifier,DBInstanceStatus]' || return 1
  aws_rows rds-snapshot rds describe-db-snapshots \
    --query 'DBSnapshots[].[DBSnapshotIdentifier,SnapshotType]' || return 1
  aws_rows log-group logs describe-log-groups \
    --query 'logGroups[].[logGroupName,storedBytes]' || return 1
  aws_rows ssm-parameter ssm describe-parameters \
    --query 'Parameters[].[Name,Type]' || return 1
  aws_rows s3-bucket s3api list-buckets --query 'Buckets[].[Name]' || return 1
}

# The R2 bucket the app stores photos and files in, through the S3 API with
# the R2 key pair in the OBJECT_STORE_PROFILE AWS CLI profile.
object_store_args() {
  printf '%s\0' --endpoint-url "$OBJECT_STORE_ENDPOINT_URL" \
    --profile "$OBJECT_STORE_PROFILE" --region "${OBJECT_STORE_REGION:-auto}"
}

enumerate_object_store() {
  local count error
  local -a store=()
  if [[ -z "${OBJECT_STORE_BUCKET:-}" ]]; then
    echo "Object store not checked: set OBJECT_STORE_BUCKET, OBJECT_STORE_ENDPOINT_URL and OBJECT_STORE_PROFILE." >&2
    return 0
  fi
  mapfile -d '' store < <(object_store_args)
  if ! error=$(AWS_PAGER="" "$CLI" s3api head-bucket --bucket "$OBJECT_STORE_BUCKET" \
      "${store[@]}" 2>&1 >/dev/null); then
    if [[ "$error" == *"Not Found"* || "$error" == *404* ]]; then
      return 0
    fi
    echo "Could not check object store bucket $OBJECT_STORE_BUCKET: $error" >&2
    return 1
  fi
  count=$(AWS_PAGER="" "$CLI" s3api list-objects-v2 --bucket "$OBJECT_STORE_BUCKET" \
    "${store[@]}" --query 'length(Contents || `[]`)' --output text) || return 1
  printf 'object-store-bucket\t%s\t%s objects\n' "$OBJECT_STORE_BUCKET" "${count//$'\r'/}"
}

# Empties and deletes the R2 bucket, then terminates the instance and removes
# its Elastic IPs, kept volumes, security groups and key pair. Each step is
# skipped if that resource is already gone, so a second run is safe.
destroy_ec2() (
  local name state error existing groups addresses volumes group group_name item attempt
  local -a store=()
  export AWS_PAGER=""
  for name in CLI AWS_REGION EC2_INSTANCE_ID; do
    if [[ -z "${!name:-}" ]]; then
      echo "Missing configuration: $name" >&2
      return 1
    fi
  done

  if [[ -n "${OBJECT_STORE_BUCKET:-}" ]]; then
    existing=$(enumerate_object_store) || return 1
    if [[ -n "$existing" ]]; then
      mapfile -d '' store < <(object_store_args)
      mutate "$CLI" s3 rm "s3://$OBJECT_STORE_BUCKET" --recursive --only-show-errors \
        "${store[@]}" || return 1
      mutate "$CLI" s3api delete-bucket --bucket "$OBJECT_STORE_BUCKET" \
        "${store[@]}" || return 1
      done_echo "Object store bucket $OBJECT_STORE_BUCKET emptied and deleted."
    else
      echo "Object store bucket $OBJECT_STORE_BUCKET is already removed."
    fi
  else
    echo "Object store not configured here; empty and delete the bucket by hand." >&2
  fi

  # Only "no such instance" counts as gone; any other error stops here.
  if ! state=$("$CLI" ec2 describe-instances --region "$AWS_REGION" \
      --instance-ids "$EC2_INSTANCE_ID" --output text \
      --query 'Reservations[0].Instances[0].State.Name' 2>&1); then
    error=$state
    if [[ "$error" != *InvalidInstanceID.NotFound* ]]; then
      echo "Could not read $EC2_INSTANCE_ID: $error" >&2
      return 1
    fi
    state=missing
  fi
  state=${state//$'\r'/}
  if [[ "$state" == terminated || "$state" == missing ]]; then
    echo "$EC2_INSTANCE_ID is already terminated."
  else
    # Read what belongs to the instance before it is gone.
    groups=$("$CLI" ec2 describe-instances --region "$AWS_REGION" \
      --instance-ids "$EC2_INSTANCE_ID" --output text \
      --query 'Reservations[0].Instances[0].SecurityGroups[].GroupId') || return 1
    addresses=$("$CLI" ec2 describe-addresses --region "$AWS_REGION" \
      --filters "Name=instance-id,Values=$EC2_INSTANCE_ID" --output text \
      --query 'Addresses[].AllocationId') || return 1
    volumes=$("$CLI" ec2 describe-instances --region "$AWS_REGION" \
      --instance-ids "$EC2_INSTANCE_ID" --output text \
      --query 'Reservations[0].Instances[0].BlockDeviceMappings[?Ebs.DeleteOnTermination==`false`].Ebs.VolumeId') || return 1

    mutate "$CLI" ec2 terminate-instances --region "$AWS_REGION" \
      --instance-ids "$EC2_INSTANCE_ID" --output text \
      --query 'TerminatingInstances[0].CurrentState.Name' || return 1
    mutate "$CLI" ec2 wait instance-terminated --region "$AWS_REGION" \
      --instance-ids "$EC2_INSTANCE_ID" || return 1
    done_echo "$EC2_INSTANCE_ID terminated."

    for item in ${addresses//$'\r'/}; do
      [[ "$item" == None ]] && continue
      mutate "$CLI" ec2 release-address --region "$AWS_REGION" --allocation-id "$item" || return 1
      done_echo "Released Elastic IP $item."
    done
    for item in ${volumes//$'\r'/}; do
      [[ "$item" == None ]] && continue
      mutate "$CLI" ec2 delete-volume --region "$AWS_REGION" --volume-id "$item" || return 1
      done_echo "Deleted volume $item."
    done
    for group in ${groups//$'\r'/}; do
      [[ "$group" == None ]] && continue
      group_name=$("$CLI" ec2 describe-security-groups --region "$AWS_REGION" \
        --group-ids "$group" --output text --query 'SecurityGroups[0].GroupName') || return 1
      [[ "${group_name//$'\r'/}" == default ]] && continue
      # The terminated instance's network interface can hold the group for a
      # little while (DependencyViolation), so try for up to a minute.
      for attempt in 1 2 3 4 5 6; do
        mutate "$CLI" ec2 delete-security-group --region "$AWS_REGION" --group-id "$group" && break
        [[ $attempt == 6 ]] && return 1
        sleep 10
      done
      done_echo "Deleted security group $group (${group_name//$'\r'/})."
    done
  fi

  if [[ -n "${EC2_KEY_NAME:-}" ]]; then
    mutate "$CLI" ec2 delete-key-pair --region "$AWS_REGION" --key-name "$EC2_KEY_NAME" || return 1
    done_echo "Deleted key pair $EC2_KEY_NAME (if it existed)."
  fi
  echo "EC2 teardown finished. The verify step lists anything else still in $AWS_REGION."
)

# =============================================================================
# The functions the course scripts call. DEPLOY_TARGET picks the shape.
# =============================================================================

require_target() {
  case "${DEPLOY_TARGET:-}" in
    ecs|ec2) return 0 ;;
    *) echo "Set DEPLOY_TARGET to ecs or ec2 in aws.env." >&2; return 1 ;;
  esac
}

adapter_deploy() {
  require_target || return 1
  "deploy_$DEPLOY_TARGET"
}

adapter_enumerate() {
  require_target || return 1
  if [[ -n "${ECS_CLUSTER:-}" ]]; then
    enumerate_ecs || return 1
  fi
  if [[ "$DEPLOY_TARGET" == ec2 ]]; then
    enumerate_region || return 1
    enumerate_object_store || return 1
  fi
}

adapter_destroy() {
  require_target || return 1
  "destroy_$DEPLOY_TARGET"
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
