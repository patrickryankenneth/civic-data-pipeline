# Development Sandbox (not required to run this project)

This project was developed inside a disposable Podman container with
btrfs copy-on-write snapshots, isolating the dev environment from the
host machine. This is a personal development convenience, not a
project dependency — the published package has no container
requirement.

Architecture notes (sanitized — actual quadlet excluded, contains
host-specific paths and a local-only sandbox DB password):
- Fresh btrfs snapshot of the Python env + LLM agent state on every
  container start; deleted on stop.
- Isolated Postgres + Redis instances inside the container.
- `.git` and `.gitignore` mounted read-only so an automated coding
  agent operating inside the container cannot alter version control.
