# Using secrets from any repo on this machine

This is the canonical guide for **consuming** secrets with this machine's
credential tooling. It is written for humans and agents working in *any*
repo (homelab, project repos, one-off scripts) — not just this dotfiles
repo. The tooling itself is defined in
[`.config/home-manager/modules/secrets.nix`](../.config/home-manager/modules/secrets.nix)
and installed globally by Home Manager, so every command below is already
on PATH in every directory.

Home Manager also deploys a copy of this document to
`~/.local/share/doc/cbws/secrets.md`, so it can be referenced from repos
that don't know where the dotfiles clone lives.

For the *internals* — the two-layer design, YubiKey/sops/age encryption,
and the rules for modifying the tooling — see
[`AGENTS.md` → "Secrets architecture"](../AGENTS.md#secrets-architecture)
and [`README.md` → "Bitwarden Setup"](../README.md#bitwarden-setup) in the
dotfiles repo.

## The contract

Application secrets live in **Bitwarden Secrets Manager (BWS)** and are
**never written to disk**. A program that needs a secret reads it from an
**environment variable**, and that variable is injected by running the
program under `cbws-exec`:

```bash
cbws-exec -- <command> [args...]
```

`cbws-exec` decrypts the BWS access token (one YubiKey PIN + touch),
injects every secret in the project as an environment variable named after
its BWS **Key**, and execs the command. The token and the secret values
exist only in that process tree and vanish when it exits — nothing is
exported into the calling shell, written to a file, or left in history.

## Reading secrets

```bash
# Run anything that reads secrets from env vars
cbws-exec -- ansible-playbook site.yml
cbws-exec -- terraform apply
cbws-exec -- ./my-script.sh

# Use a different BWS project than the default
cbws-exec --project-id <UUID> -- <command>
```

Write your scripts and playbooks to read secrets from environment
variables and document which variables they expect — e.g. a playbook that
needs `PROXMOX_API_TOKEN` should say "run via
`cbws-exec -- ansible-playbook …`".

## Discovering what exists

```bash
cbws-list-available-secrets   # UUID + Key of every secret the machine account can read
```

## Writing a secret

`cbws-secret-set` is the **only** write path. The value comes from stdin —
never from an argument, so it cannot leak into shell history or `ps`:

```bash
some-generator | cbws-secret-set MY_API_KEY   # piped value
cbws-secret-set MY_API_KEY                    # hidden interactive prompt
cbws-secret-set -y MY_API_KEY < value.txt     # no-tty scripting (auto-approve overwrite)
```

Deletion and bulk management happen in the Bitwarden Secrets Manager web
UI, deliberately — do not build other write paths.

## Naming secrets

The **Key** becomes the environment variable name injected by `cbws-exec`,
so it must be a valid shell variable name:

- `SCREAMING_SNAKE_CASE`, pattern `SERVICE_PURPOSE` — e.g. `GITHUB_TOKEN`,
  `POSTGRES_PASSWORD`, `STRIPE_API_KEY`
- Starts with a letter or underscore; no hyphens, no spaces
- The variable name should be verbose to show what its associated with `R0_PROXMOX_CLUSTER_PASSWORD`, `R0_ANSIBLE_USERNAME`, `PROXMOX_CHAIN_CERT_BUNDLE`
  - Here `R0` is a term I use for "Rack 0"
- Never shadow shell variables: `PATH`, `HOME`, `USER`, `SHELL`, `IFS`, …

## Rules for consumer repos

- **Never** hardcode secret values in tracked files, and never write them
  to disk — not in `.env` files, not in `/tmp`, not in shell rc files
- **Never** export `BWS_ACCESS_TOKEN` into an interactive shell, and do
  not build tooling that does — the token's only sanctioned lifetime is
  inside a `cbws-exec` process tree. (A former
  `bws-load-local-machine-credential` command did this; it was removed on
  purpose.)
- **Never** echo secret values into logs or command output
- Direct `bws` CLI calls are not part of the workflow — go through
  `cbws-exec` / `cbws-secret-set`
- Expect one YubiKey PIN + touch prompt per `cbws-*` invocation; don't
  "fix" the prompt away by caching tokens

## Command reference

| Command                       | What it does                                                                                  |
| ----------------------------- | --------------------------------------------------------------------------------------------- |
| `cbws-exec -- <cmd>`          | Run `<cmd>` with secrets injected as env vars; token dies with the process                    |
| `cbws-list-available-secrets` | List UUID + Key of every secret the machine account can read                                  |
| `cbws-secret-set <KEY>`       | Create/update a secret, value from stdin, confirm-before-overwrite (`-y` to skip)             |
| `cbws-sync-encrypted-secrets` | (Setup/rotation only) fetch the BWS token from the Bitwarden vault and re-encrypt it locally  |
| `sops-load-yubikey-recipient` | (Setup only) read the age recipient from YubiKey slot 1 into the dotfiles repo's `.sops.yaml` |

Every command supports `-h`/`--help`.
