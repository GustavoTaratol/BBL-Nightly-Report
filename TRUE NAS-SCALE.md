# TrueNAS SCALE deployment plan

The intended host is TrueNAS SCALE. The service should run as a container with
persistent storage mounted from a dataset.

Recommended dataset layout:

```text
ix-applications/datasets/bbl-best-worst/
  data/
  secrets/
```

`data/` stores reports, box scores, roster snapshots, logs, and the persistent
CBS browser profile. `secrets/` stores the deployment environment file and must
not be exposed through the generated reports.

The first deployment test should be interactive so the CBS service account can
log in. After that, the scheduled container can run headlessly. The scheduler
must preserve the browser profile between restarts.

Do not place the CBS password in `docker-compose.yml`, the Git repository, or
Claude prompts. If the session expires, re-authenticate through the browser
profile rather than adding credentials to source code.
