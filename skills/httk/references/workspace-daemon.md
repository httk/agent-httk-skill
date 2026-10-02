# Signed Slurm workspace daemon

Use `mount-daemon` when a client can access a destination workspace and request
mailboxes through a filesystem mount, while the destination operator controls
the Slurm manager. The client sends signed, typed health/start/status/cancel
requests; it cannot submit commands or override scheduler settings. This is an
opt-in deployment feature of current *httk-workflow* source, with strict Linux,
Bubblewrap, Slurm, mount, and site setup requirements. Read the full
[`workspace_daemon.md`](docs/httk-workflow/workspace_daemon.md) and
[`remotes.md`](docs/httk-workflow/remotes.md) snapshot before deployment. Local
tests do not establish HPC or site acceptance.

## Client identity

On the client, inspect the configured identities and identify the intended
default by its `default`, `short`, and `public_key` fields:

```console
httk identity list --json
```

If no identity exists, initialize one. To select an existing identity, use its
`short` value. Share only the selected `ed25519:...` public key with the
destination operator; keep private keys out of mounted paths and exports.
Run setup and signing commands as the same user with the same
`HTTK_CONFIG_HOME`. If the key command prints `None`, finish identity setup
before continuing.

```console
httk init --name 'Your Name' --email you@example.org
httk identity default SHORT
python -c 'from httk.core.identity import identity_public_key; print(identity_public_key())'
```

The last command prints only the selected default public key. `httk init` is
idempotent when a default identity already exists.

## Destination operator

Create a named Slurm launcher with finite resources. The approved settings must
include CPUs per task, memory, and time limit; workers share that approved
manager allocation.

```console
httk workflow launcher add --template slurm --global small \
  --set slurm.cpus_per_task=2 --set slurm.mem=4G \
  --set slurm.time_limit=01:00:00 --set slurm.partition=batch \
  --set manager.workers=2
httk workspace init --name runs /srv/httk/example/data
```

Create `/opt/httk-control/example.json` using the full template in the narrative
reference. Set `workspace` to `/srv/httk/example/data`, `state` to a protected
local path such as `/var/lib/httk/example`, `allowed_launchers` to `["small"]`,
and `authorized_keys` to `["ed25519:CLIENT_PUBLIC_KEY"]`, replacing the key with
the client's complete public string. Keep policy, trusted runtime, private
ledger and snapshots outside the writable workspace and mailbox exports.
The default mailboxes are sibling paths `data.daemon-requests` and
`data.daemon-responses`. The transport account must also be restricted
server-side; a mount alone does not confine an unrestricted SSH/SFTP account.

Initialize, check, export the public endpoint through a trusted handoff, then
run the daemon in the foreground or under a site supervisor:

```console
httk workspace daemon /srv/httk/example/data --policy /opt/httk-control/example.json --initialize
httk workspace daemon /srv/httk/example/data --policy /opt/httk-control/example.json --check
httk workspace daemon /srv/httk/example/data --policy /opt/httk-control/example.json --export-endpoint > endpoint.json
httk workspace daemon /srv/httk/example/data --policy /opt/httk-control/example.json
```

`--check` validates the broker sandbox and scheduler clients, but does not submit
work or verify compute-node execution. Protect `endpoint.json` during handoff:
it carries public trust anchors and approved configuration digests. The separate
daemon response key is pinned from this trusted export. The daemon's private key
and the site's Slurm authentication, such as MUNGE, stay on the destination.

## Mounted client

Make sure the destination workspace, request mailbox, and response mailbox are
mounted at separate absolute local paths. Import the trusted endpoint and run a
signed health check. Run the add command in a project, or add `--global` before
the remote name for a user-wide remote:

```console
httk workflow remote add --template mount-daemon confined
httk workflow remote daemon configure confined --endpoint endpoint.json \
  --mount-root /home/me/mounts/cluster/data \
  --requests /home/me/mounts/cluster/data.daemon-requests \
  --responses /home/me/mounts/cluster/data.daemon-responses
httk workflow remote check confined
httk workflow remote daemon health confined
```

Transfer jobs with absolute mounted workspace paths. Start names one approved
configuration and requires a fresh 32-character lowercase hexadecimal request
ID. Status refreshes use a fresh ID; cancel also requires a fresh ID. The start
response contains an opaque manager handle for status and cancellation.

```console
httk job transfer default /home/me/mounts/cluster/data --job JOB
python -c 'import secrets; print(secrets.token_hex(16))'
httk workflow remote daemon start confined --configuration small --request-id REQUEST_ID
httk workflow remote daemon status confined --handle MANAGER_HANDLE
httk workflow remote daemon cancel confined --handle MANAGER_HANDLE --request-id CANCEL_REQUEST_ID
httk job transfer /home/me/mounts/cluster/data default --state succeeded
```

Save each operation's ID. After a timeout, retry with the same ID and identical
fields. The client caches the exact signed request under
`<httk data home>/daemon-requests/<enrollment-id>` (by default
`~/.local/share/httk/daemon-requests/<enrollment-id>`; `HTTK_DATA_HOME` or
`XDG_DATA_HOME` can change the data home). Retry as the same user with the same
data-home setting, and retain this cache so the original signature and
timestamps are reused. The daemon never submits a duplicate twice; `uncertain`
means the operator must reconcile with Slurm. Do not retry an uncertain start
with a new ID. A new status request needs a new ID. The protocol allows 130
minutes of clock skew in either direction; keep client and server clocks
synchronized. A cancellation acknowledgement is not proof the manager or jobs
have stopped.

To change approved resources or keys, stop the daemon and update policy or
launcher settings. Reload, then export a new endpoint and re-import it on the
client with `remote daemon configure`:

```console
httk workspace daemon /srv/httk/example/data --policy /opt/httk-control/example.json --reload
httk workspace daemon /srv/httk/example/data --policy /opt/httk-control/example.json --export-endpoint > endpoint.json
```

Workspace edits alone do not change frozen approvals; queued and running jobs
retain their approved snapshot. Keep the prior endpoint export and client
request history so timed-out requests can be retried against the original
approval. Restart the foreground daemon after reloading and exporting.

For an explicitly approved MPI configuration, the workflow must invoke the
application through:

```console
httk workflow mpi run -- /opt/application/bin/program input.dat
```

MPI needs site-specific PMIx, control-path, shared-memory, device and cleanup
setup in the operator policy. Use the full daemon reference's MPI section and
complete its multi-node containment and communication checks before relying on
it. Never infer real-cluster readiness from local protocol tests.
