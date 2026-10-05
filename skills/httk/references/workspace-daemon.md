# Confined workspace daemon

Use `mount-daemon` when files are the only channel to an HPC destination. The
destination operator runs `httk workspace daemon`, a foreground Slurm broker;
the client mounts one **exchange directory** (never the workspace), sends job
bundles, collects finished jobs, reads passive status, and sends signed typed
health/start/status/cancel requests. Requests cannot carry commands, paths or
Slurm arguments. This is an opt-in deployment feature with strict Linux,
Bubblewrap (no unsandboxed fallback), Slurm and site requirements. Read
[`workspace_daemon.md`](docs/httk-workflow/details/workspace_daemon.md) (trust,
layout, quotas, MPI, site acceptance) and
[`remotes.md`](docs/httk-workflow/details/remotes.md) before deployment. Local
tests do not establish HPC or site acceptance.

## Client identity

Share only your public key with the operator; the private key stays on the
client. Use the same user and `HTTK_CONFIG_HOME` for setup and signing.

```console
httk init --name 'Your Name' --email you@example.org
python -c 'from httk.core.identity import identity_public_key; print(identity_public_key())'
```

`httk identity list --json` shows identities; `httk identity default SHORT`
selects one. `httk init` is idempotent. If the key prints `None`, finish
identity setup first.

## Destination operator

Layout: the workspace and exchange are siblings in a dedicated parent that
contains nothing else, on one filesystem and one mount (jobs move by plain
rename). The exchange must not exist yet, or be empty.

Approved manager configurations are global `--template daemon` launchers.
Keys: `slurm.partition|account|gres|reservation|cpus_per_task|mem|time_limit`,
`manager.workers|command`, `environment.prelude`; MPI only via
`slurm.mpi=pmix` (needs `manager.workers=1` and `daemon.mpi.control_root`).
Optional `daemon.*` site keys have defaults and must agree across launchers. A
`slurm` launcher cannot be approved.

```console
httk workflow launcher add --template daemon --global small \
  --set slurm.cpus_per_task=2 --set slurm.mem=4G \
  --set slurm.time_limit=01:00:00 --set manager.workers=2
httk workspace daemon /proj/campaign/workspace --initialize \
  --exchange /proj/campaign/exchange --launcher small \
  --authorize ed25519:CLIENT_PUBLIC_KEY
httk workspace daemon /proj/campaign/workspace --check
httk workspace daemon /proj/campaign/workspace
```

Repeat `--launcher` and `--authorize` per item. `--initialize` writes
`exchange/endpoint.json` (public trust anchors and digests). `--check` enters
the real broker sandbox and checks the scheduler clients; it does not submit
work or test compute-node execution. `--once` does one bounded scan; normal
startup polls until SIGINT/SIGTERM (use a site supervisor). Repeat non-default
`--state`/`--snapshots` on later calls. The SSHFS account must be restricted
server-side to the exchange; a mount alone does not confine it. Mount without
`follow_symlinks`.

To change launchers or keys, stop the daemon, edit launchers, then
`httk workspace daemon WORKSPACE --reload` (given `--launcher`/`--authorize`
lists replace the stored ones). It rewrites `endpoint.json`; clients need no
reconfiguration. Queued and running jobs keep their frozen snapshot. A change
of the fixed connection (paths, Slurm executables, cluster) needs a new
enrollment.

## Client

Mount the exchange (mount point outside any local workspace), then:

```console
httk workflow remote add --template mount-daemon confined
httk workflow remote daemon configure confined --exchange /mnt/cluster/exchange
httk workflow remote check confined
httk workflow remote daemon health confined
```

`configure` pins the daemon identities from `endpoint.json` and publishes
nothing; `check` sends a signed health request only.

Start a manager (fresh 32-hex request ID per operation), then send the job:

```console
python -c 'import secrets; print(secrets.token_hex(16))'
httk workflow remote daemon start confined --configuration small --request-id REQUEST_ID
httk job eject JOB /mnt/cluster/exchange/inbox
httk workflow remote daemon status confined                       # passive: status.json, managers.json
httk workflow remote daemon status confined --handle MANAGER_HANDLE   # signed, fresh ID
httk workflow remote daemon cancel confined --handle MANAGER_HANDLE --request-id ANOTHER_ID
httk job adopt /mnt/cluster/exchange/outbox/JOB_KEY
```

The daemon moves `inbox` bundles into the workspace and a daemon-started
manager adopts them. A finished job (succeeded/failed/cancelled, no parent, no
unfinished children) auto-ejects to `outbox/<job_key>` about 60 s later;
`job adopt` takes it back. Refused bundles land in `outbox/rejected/`, with the
reason in `status.json`. Failed jobs are never retried automatically: adopt,
fix, eject again.

After a timeout, retry the same request ID with identical fields; the daemon
never submits a duplicate. `uncertain` means the operator must reconcile with
Slurm; do not retry it with a new ID. Keep client and server clocks
synchronized (130 minutes skew allowed). A cancel acknowledgement is not proof
that the manager stopped. `status.json` and `managers.json` are informational
only.

For MPI launchers the workflow runs the application through
`httk workflow mpi run -- /opt/application/bin/program input.dat`. Complete the
multi-node and communication checks in the full reference before relying on it.
