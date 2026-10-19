# Milestone 6 - Part 1

## Image and service

```bash
IMAGE_REF=533267434818.dkr.ecr.us-east-2.amazonaws.com/seekr:be5b7ad7f3768bcacd6ccd278b86bf9853188365
SERVICE_URL=https://tusbb8zllh.execute-api.us-east-2.amazonaws.com
```

The image is `linux/amd64` and uses the full commit SHA as its tag. The
Dockerfile installs pinned dependencies before copying the
app, runs as user `10001:10001`, and checks `/health` with
`urllib.request`.

HTTPS goes through API Gateway, then a load balancer to ECS. Only
`GET /health` and `GET /`

## Setup for the commands

`adapters/aws.env` uses the `seekr-deploy` profile for the limited
`seekr-deployer` IAM user. The app's database password and JWT secret are in
AWS Parameter Store.

The audit script is copied from Module 7

```bash
cd /c/dev/SystemDesign/tmp/seekr-part1-run
cp /c/dev/SystemDesign/output/module7-team-ci/milestones/milestone5/members/varne1dm/aws.sh adapters/aws.sh
cp //wsl.localhost/Ubuntu/home/devburton/itc531/module_7/scripts/cloud-audit.sh scripts/cloud-audit.sh
set -a
source adapters/aws.env
set +a
source adapters/aws.sh
```

## First deployment

```bash
adapter_deploy
```

Output:

IMAGE_REF=533267434818.dkr.ecr.us-east-2.amazonaws.com/seekr:be5b7ad7f3768bcacd6ccd278b86bf9853188365
{"status":"ok","checks":{"database":"ok"}}
http=404
https://tusbb8zllh.execute-api.us-east-2.amazonaws.com

## Second deployment

same settings used.

```bash
adapter_deploy
```

Output:

IMAGE_REF=533267434818.dkr.ecr.us-east-2.amazonaws.com/seekr:be5b7ad7f3768bcacd6ccd278b86bf9853188365
{"status":"ok","checks":{"database":"ok"}}
http=404
https://tusbb8zllh.execute-api.us-east-2.amazonaws.com

## Cloud audit after both deployments

```bash
set +e
bash scripts/cloud-audit.sh aws
```

Output:

ITC 531 cloud audit — adapter=aws — 2026-10-18 22:57 UTC
  provider:        Amazon Web Services
  region:          us-east-2
  compute service: Amazon Elastic Container Service
  storage service: Amazon S3
  auth model:      IAM user seekr-deployer
  contract check:  Full contract not rerun for this Part 1 test
---------------------------------------------------------------
ecs-service	arn:aws:ecs:us-east-2:533267434818:service/itc531_cluster/seekr	ACTIVE
---------------------------------------------------------------
NOT CLEAN — 1 resource(s) exist.

If you are finished with them:   bash scripts/cloud-down.sh aws
If you are mid-assignment that is fine — but check again when you finish.




The audit found an active ECS service. Its exit code is `1` because the
course script uses that when resources still exist. Both deployments
updated the same `seekr` service. They registered task revisions `seekr:2`
and `seekr:3`.

## HTTPS checks after the second deployment

```bash
curl -s "$SERVICE_URL/health"
```

Output:

```json
{"status":"ok","checks":{"database":"ok"}}
```

```bash
curl -s -o /dev/null -w "http=%{http_code}\n" "$SERVICE_URL/"
```

Output:

http=404

`checks.database` is `ok`, so the deployed app can query PostgreSQL. The root
returns `404` because Seekr has no handler for `/`.

Final ECS check (service name, desired tasks, running tasks, task definition):

```bash
"$CLI" ecs describe-services --cluster "$ECS_CLUSTER" --services "$SERVICE_NAME" --query 'services[0].[serviceName,desiredCount,runningCount,taskDefinition]' --output text
```

Output:

seekr	1	1	arn:aws:ecs:us-east-2:533267434818:task-definition/seekr:3


## Green run of CI
https://github.com/Snazzy11/ITC-531-Group-Project/actions/runs/39197002008

## Split of work
Devon did part 1
Parker did parts 2 & 4
Doug did parts 3, 5, & 6

