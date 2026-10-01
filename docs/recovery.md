# Recovery

Synchronization is not backup. A VM snapshot is not backup. RAID is not
backup. Replication also reproduces deletions and corrupt data.

Restic is used only when `RESTIC_REPOSITORY` and its credentials are explicitly
configured. `labctl backup restore-test` restores a known fixture into a new
temporary directory, compares its checksum, reports the proof, and removes the
scratch directory only after success.

A repository on the same Mac can prove the commands and checksum behavior. It
does not survive loss of the Mac and must not be described as resilient.

The 2026-09-30 development proof initialized a repository outside this Git
tree, created a fixture snapshot, passed `restic check`, restored to a new
scratch directory, and matched SHA-256
`6696c702f1b5e1ba326d3fe99023f082ddd2070bcb2985147d10bbf87727c231`.
That result validates mechanics only.

```console
RESTIC_REPOSITORY=/explicit/target RESTIC_PASSWORD_FILE=/private/file \
  ./bin/labctl backup create
RESTIC_REPOSITORY=/explicit/target RESTIC_PASSWORD_FILE=/private/file \
  ./bin/labctl backup check
RESTIC_REPOSITORY=/explicit/local-test RESTIC_PASSWORD_FILE=/private/file \
  ./bin/labctl backup restore-test --allow-local-repository
```

Service-specific quiesce/export steps are required before databases become
important. Copying a live database file is not accepted as a restore strategy.

The disposable sandbox has no recovery promise. `labctl sandbox destroy --yes`
deletes that VM intentionally; recreate it from `infra/lima/sandbox.yaml` and
rerun verification. Evidence worth retaining belongs in reviewed, sanitized
records—not in sandbox disk state.
