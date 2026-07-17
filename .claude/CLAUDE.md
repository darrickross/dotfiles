# Machine-wide agent guidance (deployed from the dotfiles repo)

This file is deployed to `~/.claude/CLAUDE.md` by Home Manager from the
dotfiles repo (`.claude/CLAUDE.md` there is the source of truth — edit it
there, then run `hms`). It applies to every project on this machine.

## Secrets and credentials

Application secrets live in Bitwarden Secrets Manager and are never on
disk. Full guide: `~/.local/share/doc/cbws/secrets.md`. The contract:

- A program that needs a secret reads it from an **environment variable**;
  inject them by running the program as `cbws-exec -- <command>` (each BWS
  secret's Key becomes an env var). Expect one YubiKey PIN + touch prompt
- Discover available secrets with `cbws-list-available-secrets`
- Write/update secrets only with `cbws-secret-set <KEY>` — value via
  stdin, never as an argument
- Never export `BWS_ACCESS_TOKEN` into a shell, never hardcode or write
  secret values to disk (no `.env`, `/tmp`, rc files), never echo them
  into logs or output
- All `cbws-*` commands support `--help`

## Tooling on this machine

Packages, scripts, and shell config are managed declaratively by Nix Home
Manager in the dotfiles repo (clone root: `$(dotfiles-root)`). Do not
install tools with `pip`, `apt`, `nix-env`, etc. — add them to the
appropriate module under `.config/home-manager/` there and run `hms`.
