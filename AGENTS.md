# AGENTS.md — Agent guidance for this dotfiles repo

## Repo layout and dotfile management

The directory structure of this repo mirrors `~` exactly (`.config/`, `.ssh/`, etc.). Dotfiles are activated via Home Manager, not symlinked manually.

- Shell config (`.bashrc`) is sourced at build time via `programs.bash.bashrcExtra` in `home.nix` — Home Manager generates `~/.bashrc` and sources the repo file
- Scripts and managed files are declared as `home.file` entries in `home.nix`
- Adding a new managed file means declaring it in `home.nix` under `home.file` and running `hms`

---

## Home Manager — source of truth for scripts, aliases, and packages

All shell scripts, aliases, and installed packages are managed in [`.config/home-manager/home.nix`](.config/home-manager/home.nix). Do not install packages with `nix-env`, `pip`, `apt`, or any other package manager.

- To add a package: add it to the `home.packages` list in `home.nix`
- To add a script or alias: add a `home.file` or `programs.bash.shellAliases` entry in `home.nix`
- After any change to `home.nix`: run `hms` (`home-manager switch && exec $SHELL -l`) to apply it
- To update flake inputs (nixpkgs, home-manager): run `hmu` (`nix flake update`)
- Python packages are pinned in `home.nix` — add new dependencies there, not with `pip install`

---

## WSL2 specifics

This machine runs Linux under WSL2. Several tools forward to Windows binaries to access hardware (YubiKey USB) that is not passed through to WSL.

- **GPG** — aliased to `/mnt/c/Program Files (x86)/GnuPG/bin/gpg.exe` (Gpg4win)
- **age-plugin-yubikey** — `~/.local/bin/age-plugin-yubikey` is a wrapper that calls the Windows `.exe`; do not replace it with a Linux binary or the YubiKey age identity will stop working
- **SSH SK helper** — `SSH_SK_HELPER` points to `/mnt/c/Program Files/OpenSSH/ssh-sk-helper.exe`
- YubiKey USB is **not** forwarded to WSL via usbipd; all YubiKey operations must go through these Windows wrappers

---

## Secrets architecture

This repo uses a two-layer system. Never collapse these layers or short-circuit them.

### Layer 1 — BWS access token (bootstrap secret)

The Bitwarden Secrets Manager (BWS) access token is the credential that unlocks all other secrets. It is:

- Stored encrypted at `~/.local/secrets/bitwarden.yaml` using sops + age + YubiKey
- Encrypted under the age recipient in `.sops.yaml` (a YubiKey-backed key, slot 1)
- Loaded into the shell by sourcing `bws-load-local-machine-credential` (alias), which decrypts the file with sops and exports `BWS_ACCESS_TOKEN` into the current shell session only

The file `~/.local/secrets/bitwarden.yaml` is in `.gitignore` and must never be committed. It is re-created by running `bw_sync_encrypted_secrets.sh`.

### Layer 2 — Application secrets (Bitwarden Secrets Manager)

All application secrets live in Bitwarden Secrets Manager (BWS). They are never written to disk. Access pattern:

```bash
# 1. Load the token (once per shell session)
bws-load-local-machine-credential

# 2. Run a command with secrets injected as env vars
bws run -- <command>
```

`bws run` sets each secret as an environment variable named after its **Key** field in BWS, then execs the command. The values are never written to disk and do not appear in shell history.

---

## Rules for writing scripts and nix config

### Never do these

- Do not hardcode secret values in any `.nix`, `.sh`, or any tracked file
- Do not store secrets in plaintext — not in `/tmp`, not in env files, not in shell rc files
- Do not use `set -euo pipefail` in scripts that will be **sourced** — it leaks those options into the calling interactive shell, which causes unrelated failed commands (e.g. a `bws run` returning 404) to silently exit the user's terminal session. Use explicit `|| { ... return 1; }` guards instead
- Do not use `bw unlock --raw` without first checking `bw status` — `unlock` only works on an already-authenticated vault and will fail silently on a fresh machine

### Sourced scripts

Any script that must `export` variables into the calling shell must be sourced, not executed. Follow the pattern in `_bws-load-local-machine-credential`:

1. Prefix the filename with `_` to signal it is not called directly
2. Guard against direct execution with a `BASH_SOURCE[0] == $0` check that uses `exit 1` (not `return 1`) so the error is clear when run as a subprocess
3. Use `return 1` (not `exit 1`) on all other error paths so the calling shell is not terminated
4. Do not set `set -euo pipefail` — handle each error path explicitly

### Temporary files containing secrets

If a script must write a secret to a temporary file (e.g. for sops encryption), always:

1. Create it with `mktemp` inside `~/.local/secrets/` so the `.sops.yaml` path regex matches and the correct YubiKey recipient is auto-selected
2. Register an `EXIT` trap immediately: `trap 'shred -u "$TMPFILE" 2>/dev/null || rm -f "$TMPFILE"' EXIT`
3. Use `shred -u` (not `rm`) as the primary cleanup method

### Notes field validation

When fetching a Bitwarden item with `bw get item | jq -r '.notes'`, always validate before use:

```bash
NOTES=$(bw get item "item-name" | jq -r '.notes')
[[ "$NOTES" != "null" && -n "$NOTES" ]] \
  || { echo "Error: notes field is empty or missing" >&2; exit 1; }
```

`jq -r '.notes'` outputs the literal string `null` when the field is absent, which passes the `||` guard but produces broken YAML when encrypted and stored.

---

## Naming secrets in Bitwarden Secrets Manager

The **Key** field becomes the environment variable name injected by `bws run`. Requirements:

- `SCREAMING_SNAKE_CASE` — `MY_API_KEY`, not `my-api-key` or `My_Api_Key`
- Must start with a letter or underscore — not a digit
- No hyphens — hyphens are not valid in shell variable names
- No spaces
- Do not shadow shell builtins: `PATH`, `HOME`, `USER`, `SHELL`, `IFS`, `PS1`, etc.

Pattern: `SERVICE_PURPOSE` — e.g. `GITHUB_TOKEN`, `POSTGRES_PASSWORD`, `STRIPE_API_KEY`

---

## Rules for writing Markdown

### Line endings

All text files use LF line endings — enforced by `.gitattributes`. When creating new files, ensure your editor or tool does not produce CRLF.

### Tables

- Align column separator pipes so all rows in a column have the same width — pad with spaces
- The separator row (dashes) must match the width of the widest cell in each column
- Always include a space inside each cell: `| cell |` not `|cell|`

Example of a correctly formatted table:

```markdown
| Short   | A longer column header |
| ------- | ---------------------- |
| value   | another value          |
| x       | y                      |
```

---

## Key files

| Path                                    | Purpose                                                                                                             |
| --------------------------------------- | ------------------------------------------------------------------------------------------------------------------- |
| `.config/home-manager/home.nix`         | All scripts, aliases, and packages are defined here as home-manager managed files                                   |
| `.sops.yaml`                            | sops encryption rules — age recipient is the YubiKey public key, path regex targets `secrets/*.yaml`                |
| `~/.local/secrets/bitwarden.yaml`       | Encrypted BWS access token — gitignored, created by `bw_sync_encrypted_secrets.sh`                                  |
| `~/.config/age/yubikey-identity.txt`    | YubiKey age identity stanza — required by sops at runtime via `SOPS_AGE_KEY_FILE`                                   |

## Available commands (after home-manager switch)

| Command                               | What it does                                                                                                        |
| ------------------------------------- | ------------------------------------------------------------------------------------------------------------------- |
| `bws-load-local-machine-credential`   | Sources `_bws-load-local-machine-credential`, decrypts and exports `BWS_ACCESS_TOKEN`                               |
| `bws-check-available-secrets`         | Lists UUID and Key of every secret the machine account can access                                                   |
| `bws run -- <cmd>`                    | Runs `<cmd>` with all BWS secrets injected as environment variables                                                 |
| `bw_sync_encrypted_secrets.sh`        | Fetches the BWS token from Bitwarden vault and writes it encrypted to `~/.local/secrets/bitwarden.yaml`             |
