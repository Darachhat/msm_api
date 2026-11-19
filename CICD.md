# CI/CD (GitHub Actions + Ansible + Docker Swarm)

Ported from the GitLab pipeline in `hub_api` and the playbooks in `ansible-cicd`.

## Flow

| GitLab (hub_api)                  | GitHub (this repo)                                  |
|-----------------------------------|-----------------------------------------------------|
| `.gitlab-ci.yml` build/deploy/notify/scan | `.github/workflows/ci-cd.yml` (test, build, deploy, notify, cve-scan) |
| Private Docker registry           | GitHub Container Registry `ghcr.io/<owner>/msm_api` |
| `build.sh` / `deploy.sh`          | `docker/build-push-action` + `ansible-playbook` step |
| `ansible-cicd` repo               | `ansible/` folder in this repo                      |
| `when: manual` on prod            | Required reviewers on the `prod` GitHub Environment |
| `DEV_*`, `UAT_*`… variables       | Per-environment secrets/variables (same names, no prefix) |

Branches `dev`, `uat`, `staging`, `prod` deploy to the environment of the same name.
Pull requests only run the `test` job.

## One-time GitHub setup

1. Create four **Environments** (Settings → Environments): `dev`, `uat`, `staging`, `prod`.
   Add *Required reviewers* to `prod`.
2. In each environment add:

**Secrets**

| Name | Purpose |
|------|---------|
| `SERVER_IP`, `SERVER_USER` | Swarm manager host and SSH user (user must be in the `docker` group) |
| `SSH_PRIVATE_KEY` | Private key for that user |
| `GHCR_PULL_TOKEN` | PAT with `read:packages` so the server can pull the image |
| `DB_PASS`, `JWT_PRIVATE_KEY`, `JWT_PUBLIC_KEY` | App & RS256 JWT secrets |
| `R2_ACCESS_KEY_ID`, `R2_SECRET_ACCESS_KEY` | Cloudflare R2 |
| `SUDO_PASSWORD` | Optional, only if `USE_SUDO=true` |
| `TELEGRAM_BOT_TOKEN`, `TELEGRAM_CHAT_ID` | Optional notifications |

**Variables**

`SERVICE_URL`, `PORT` (default 8000), `SERVICE_REPLICAS` (default 1), `DB_HOST`, `DB_PORT`,
`DB_NAME`, `DB_USER`, `DB_SSL`, `DB_DIALECT`, `R2_ACCOUNT_ID`, `R2_ENDPOINT_URL`,
`R2_BUCKET_NAME`, `R2_PUBLIC_URL`, `WHITE_LIST_CORS` (JSON list), `USE_SUDO` (default false).

3. Server prerequisites: Docker Swarm initialised and an external overlay network named
   `swarm_network` (`docker network create -d overlay --attachable swarm_network`).
   Deploy files go to `/var/www/msm/api/msm_api` (writable by the SSH user, or set `USE_SUDO=true`).

## Database migrations

SQL files in `migrations/` are **not** applied by the pipeline. Run them manually
(after a backup) before deploying a release that needs them.

## Local check

```
python -m compileall -q app main.py
python -c "from main import app"
```
