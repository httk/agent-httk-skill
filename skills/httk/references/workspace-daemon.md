# Confined workspace daemon

Use `mount-daemon` when files are the only channel to an HPC destination. The
workspace there has an **exchange** directory, `WORKSPACE/exchange/` (a
workspace extension; `httk workspace exchange enable`, also done by `daemon
init`), the one directory the client mounts (never the workspace). Every
unrestricted confined manager of the workspace serves it: it adopts `inbox`
bundles and returns finished exchange-origin jobs to `outbox`; jobs keep
running whether or not a daemon exists. The operator also runs `httk workspace
daemon`, a foreground Slurm broker that only starts, queries and cancels
managers on signed typed requests (health, start, status, cancel). Requests
cannot carry commands, paths or Slurm arguments. This is an opt-in deployment
feature with strict Linux, Bubblewrap (no unsandboxed fallback), Slurm and site
requirements. Read
[`workspace_daemon.md`](docs/httk-workflow/details/workspace_daemon.md) (trust,
layout, quotas, parallel launches, site acceptance) and
[`remotes.md`](docs/httk-workflow/details/remotes.md) before deployment. The
file-level rules of the exchange, the daemon request/response mailbox and the
confined launch files (`launch/` requests, statuses, trusted launch records)
are specified in
[`workflow_filesystem_api.md`](docs/httk-workflow/details/workflow_filesystem_api.md)
(sections "Exchange extension", "Daemon mailbox", "Confined launches"). Local
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

Layout: no special layout; the exchange is `WORKSPACE/exchange/`. State and
snapshots must lie outside the workspace. The ledger (`<state>/ledger/`) is
lock-free and works on any filesystem with POSIX rename/link semantics; any
number of daemon instances may run.

Trust model: the manager is trusted and runs unconfined in its Slurm batch
job; each job attempt runs in its own Bubblewrap sandbox that can write only
that job's directory (the workspace is readable). On a workspace with the exchange
extension enabled, every manager must set `manager.confine=bwrap` (else it
refuses to start, and stops claiming when the extension appears). Approved
manager configurations are ordinary global `slurm` launchers that set
`manager.confine=bwrap` (`confine.*` keys; `slurm.*`, `manager.workers|command`,
`environment.prelude` as usual). The broker sees the host read-only (Slurm,
MUNGE, user database just work) and writes only `WORKSPACE/exchange` and its
state; attempts see `confine.readonly_paths` (default: `/usr`, `/etc`, the
Python installation, where httk is imported from), so add software trees jobs
need with `--add-path`.

```console
httk workflow launcher add --template slurm --global small \
  --set manager.confine=bwrap --set slurm.cpus_per_task=2 --set slurm.mem=4G \
  --set slurm.time_limit=01:00:00 --set manager.workers=2
httk workflow launcher configure --add-path confine.readonly_paths=/software small
httk workspace daemon init /proj/campaign/workspace \
  --add launchers=small \
  --add authorized_keys=ed25519:CLIENT_PUBLIC_KEY
httk workspace daemon check /proj/campaign/workspace
httk workspace daemon run /proj/campaign/workspace
```

Repeat `--add` per item; `--set KEY=VALUE` sets other keys (`bwrap`, `python`,
`sbatch`, `squeue`, `scancel`, `sacct`, `slurm_conf`, `max_submissions`,
`force`; `cluster`/`scontrol` at `init` only). There is no `--exchange` option.
`init` saves `<state>/configuration.json`, writes `exchange/daemon.json` (public
trust anchors and digests) and ends with the `check`; state of an earlier
enrollment (the SQLite ledger, or ledger format 1 before the October 7 2026
anchor envelope) is refused, so re-initialize. `show WORKSPACE [--json]`
prints the enrollment and configuration. `check` enters the real broker
sandbox and checks the scheduler clients; it does not submit work or test
compute-node execution. `run --once` does one bounded scan; `run` polls until
SIGINT/SIGTERM (use a site supervisor). Repeat non-default `--state` on later
calls; `--snapshots` is remembered. The exchange writer must be the workspace
owner's account (a separate transport UID is unsupported); restricting that
account's SFTP access is a site matter. Mount without `follow_symlinks`.

Changing the configuration: edit launchers with `httk workflow launcher
configure`, or the daemon configuration with `httk workspace daemon configure
WORKSPACE --set|--add|--remove KEY=VALUE` (lists `launchers`,
`authorized_keys`), then restart `run`. There is no approval or reload step:
every `check`/`run` re-reads the configuration and current launcher bundles and
activates changes, rewriting `daemon.json` (clients read it live). Activation
is allowed while a daemon runs: running instances exit at their next admission
and a supervisor restarts them; a restart also applies an httk upgrade. Queued
and running jobs keep their frozen snapshot. A change of the fixed connection
(workspace, state, snapshots, cluster) needs a new enrollment.

## Client

Mount the exchange (mount point outside any local workspace), then:

```console
httk workflow remote add --template mount-daemon confined
httk workflow remote daemon configure confined --exchange /mnt/cluster/exchange
httk workflow remote check confined
httk workflow remote daemon health confined
```

Remote settings: `exchange` and `daemon_workspace_id` are required;
`daemon_enrollment_id` and `daemon_public_key` are optional, needed only for
signed requests. `configure` pins the workspace from `exchange.json` and the
daemon identities from `daemon.json` (when present) and publishes nothing;
`check` reads `exchange.json` and, with the daemon pinned, `daemon.json` and a
signed health request.

Send a job, start a manager (fresh 32-hex request ID per operation), and fetch:

```console
httk job eject JOB /mnt/cluster/exchange/inbox          # local atomic export, then copy-out; --resume
python -c 'import secrets; print(secrets.token_hex(16))'
httk workflow remote daemon start confined --configuration small --request-id REQUEST_ID
httk workflow remote daemon status confined                       # passive: status.json, managers.json
httk workflow remote daemon status confined --handle MANAGER_HANDLE   # signed, fresh ID
httk workflow remote daemon cancel confined --handle MANAGER_HANDLE --request-id ANOTHER_ID
httk job adopt /mnt/cluster/exchange/outbox/JOB_KEY      # copied, verified, source removed
```

Any unrestricted confined manager (no `--placement-prefix` or pool restriction) adopts `inbox` bundles. A finished exchange-origin job
(succeeded/failed/cancelled, no parent, no unfinished children) returns to
`outbox/<job_key>` about 60 s later. Refused bundles land in
`outbox/rejected/<unique>/{<name>, reason.json}`, with the reason in
`reason.json` (`status.json` lists only job states). Failed jobs are never retried automatically: adopt, fix, eject
again. `managers.json` lists each manager's scheduler state, exit code and
times; a finished manager's Slurm output is at `managers/<handle>.log`
(`httk workflow remote daemon log REMOTE --handle H`). To take back a bundle
nobody has adopted, `httk workflow remote daemon take-back REMOTE NAME
[DESTINATION]` (client-only: rename to a dot name, copy out, remove; if the
name is gone a manager took it, so cancel the job).

After a timeout, retry the same request ID with identical fields; the daemon
never submits a duplicate. `uncertain` means the operator must reconcile with
Slurm; do not retry it with a new ID. Keep client and server clocks
synchronized (130 minutes skew allowed). A cancel acknowledgement is not proof
that the manager stopped. `status.json` and `managers.json` are informational
only. The client removes a response once it has verified it; the daemon removes
unconsumed responses after the request lifetime plus the skew allowance
(3600 + 7800 s).

Parallel launches: code commands name only the program (`vasp.command =
"vasp_std"`); the attempt's launch prefix `HTTK_WORKFLOW_LAUNCH`
(`manager.launch_template` or the built-in Slurm prefix) supplies the parallel
start. Under confinement it is a launch client that asks the trusted manager to
start rank sandboxes; use `$HTTK_WORKFLOW_LAUNCH ./program input.dat`. Each
launch style needs its own site acceptance (multi-node communication, shared
memory, isolation, spawn, cancellation). The manager starts the launch only
after recording its process and allocation durably (a gate holds the prefix
until then). Another manager commits, takes over or cancels the attempt only
once every recorded launch provably ended; for Slurm it asks `squeue` (a
running allocation blocks even past its recorded end time). A non-Slurm
multi-node launch technology must provide an `exec:PATH` allocation probe that
records an `identity` and answers `PATH ended` (see
[`launcher_authoring.md`](docs/httk-workflow/details/launcher_authoring.md)),
or such takeovers wait for `httk job confirm-launches-ended`.
`confine.shm_root` (default `/dev/shm`) must be a node-local tmpfs: it is
checked at the start-time confinement probe (claims are held back) and at
every launch.

The built-in Slurm prefix is `env SLURM_HOSTFILE=<nodefile> srun [--mpi=M]
--ntasks=T --distribution=arbitrary --exact --cpus-per-task=C ...` (no
`--nodes`/`--nodelist`; a custom `manager.launch_template` using
`--distribution=arbitrary` must not pass them either). `manager.launch_mpi=<plugin>`
adds `--mpi=<plugin>` (ignored with a template); Intel MPI needs `pmi2`:
`httk workflow launcher configure --set manager.launch_mpi=pmi2 small`, then
restart the daemon.

`manager.confine.block_mpi_spawn` (under `manager.confine=bwrap`) is `on`
(default), `auto` or `off`. With `on`, the rank helper keeps Slurm's `PMI_FD`,
relays PMI-1 through a filter that refuses `MPI_Comm_spawn` and fails closed
on anything else, and drops `PMI_PORT`; `auto` is `on` when `PMI_FD` is set,
else `off`; `off` passes Slurm's PMI through, so spawn escapes the sandbox. It
does not cover a non-Slurm PMIx server (e.g. an Open MPI `mpirun` template).
See the full reference, [PMI-2
launches](docs/httk-workflow/details/workspace_daemon.md#pmi-2-launches-intel-mpi).
