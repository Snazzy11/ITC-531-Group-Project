devburton@DevonB:~/itc541$ bash scripts/doctor.sh
ITC 531 environment check — 2026-09-04 23:18 UTC

Platform
   ok  os=Linux arch=x86_64
   ok  running inside WSL2

Course tooling
   ok  git
   ok  unzip
   ok  curl

Container engine
   ok  engine responding
   ok  server version 29.5.3
   ok  dockerd (moby) container engine
   ok  compose v2: 5.3.1
  warn the old 'docker-compose' v1 binary is also installed. Ignore it; every command in this course uses 'docker compose'.

This module
   ok  module 1 is complete — 'docker compose up -d --wait' from here

Kubernetes toggle
   ok  Kubernetes off — correct for ITC 531

Memory
  warn 7778 MB visible. Workable, but run one module's stack at a time — 'docker compose down --volumes' before starting the next.

Ports the course uses

Working directory
   ok  /home/devburton/itc541
   ok  line endings are LF

Editor
   ok  the 'code' command is on your PATH — 'code .' opens this folder

Adapters
   ok  adapter 'local' present (local)
  warn not a git repository yet — remember that adapters/*.env must never be committed

Student extension
  warn scripts/doctor.local.sh not present — the Module 1 assignment asks you to write one

Summary  15 ok, 4 warn, 0 fail
Ready. Paste this output into the Module 1 discussion.