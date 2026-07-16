#!/usr/bin/env python3
"""Create or update a secret in Bitwarden Secrets Manager.

Deployed as `cbws-secret-set` (see .config/home-manager/modules/secrets.nix).
This is the ONLY supported write path to Secrets Manager from this machine —
everything else (cbws-exec, cbws-list-available-secrets) is read-only, and
nothing ever exports BWS_ACCESS_TOKEN into an interactive shell.

The secret VALUE is taken from stdin, never from an argument, so it cannot
land in shell history or `ps` output:

  some-generator | cbws-secret-set MY_API_KEY      # piped
  cbws-secret-set MY_API_KEY                        # interactive, hidden prompt

Everything else comes from the sops+age(YubiKey) encrypted file at
~/.local/secrets/bitwarden.yaml (decrypted once — one YubiKey PIN + touch):

  local_computer_machine_account_bws_access_token   BWS machine account token
  default_project_id                                project used without --project-id
  organization_id                                   BWS organization (see README)

If a secret with the same key already exists in the organization it is
updated (its note is preserved), after an interactive confirmation on the
terminal — pass -y/--yes to skip the prompt (required when there is no tty).
The machine account needs *read-write* access to the project for this to
succeed.

The Bitwarden SDK talks to the US cloud by default; set BWS_API_URL and
BWS_IDENTITY_URL for the EU cloud or a self-hosted server.
"""

from __future__ import annotations

import argparse
import getpass
import json
import os
import shutil
import subprocess
import sys
import uuid
from pathlib import Path
from typing import NoReturn

from bitwarden_sdk import BitwardenClient, DeviceType, client_settings_from_dict

SECRETS_FILE = Path.home() / ".local/secrets/bitwarden.yaml"
TOKEN_FIELD = "local_computer_machine_account_bws_access_token"
SECURE_NOTE = "local-machine-bws-secrets"

BWS_API_URL = os.environ.get("BWS_API_URL", "https://api.bitwarden.com")
BWS_IDENTITY_URL = os.environ.get("BWS_IDENTITY_URL", "https://identity.bitwarden.com")


def die(*lines: str) -> NoReturn:
    print(f"Error: {lines[0]}", file=sys.stderr)
    for line in lines[1:]:
        print(f"  {line}", file=sys.stderr)
    sys.exit(1)


def load_local_secrets() -> dict:
    """Decrypt ~/.local/secrets/bitwarden.yaml (one YubiKey PIN + touch)."""
    # Preflight with actionable errors, mirroring the cbws-* bash scripts.
    if not shutil.which("age-plugin-yubikey"):
        die(
            "age-plugin-yubikey not found on PATH.",
            "On WSL it is deployed by modules/wsl.nix — run 'hms'.",
        )
    age_key_file = os.environ.get("SOPS_AGE_KEY_FILE", "")
    if not age_key_file or not Path(age_key_file).is_file():
        die(
            f"age identity file not found at {age_key_file or '<SOPS_AGE_KEY_FILE unset>'}",
            "Generate it:  age-plugin-yubikey --identity --slot 1 > ~/.config/age/yubikey-identity.txt",
        )
    if not SECRETS_FILE.is_file():
        die(
            f"secrets file not found at {SECRETS_FILE}",
            "Run cbws-sync-encrypted-secrets to create it.",
        )

    print(
        f"Decrypting {SECRETS_FILE} — confirm with your YubiKey PIN + touch.",
        file=sys.stderr,
    )
    # --output-type json so the stdlib can parse it without a YAML dependency.
    proc = subprocess.run(
        ["sops", "--decrypt", "--output-type", "json", str(SECRETS_FILE)],
        capture_output=True,
        text=True,
    )
    if proc.returncode != 0:
        die(f"failed to decrypt {SECRETS_FILE}", proc.stderr.strip())
    return json.loads(proc.stdout)


def parse_uuid(value: str, what: str) -> uuid.UUID:
    try:
        return uuid.UUID(value)
    except ValueError:
        die(f"{what} is not a valid UUID: {value!r}")


def read_value() -> str:
    """Read the secret value from stdin (hidden prompt when interactive)."""
    if sys.stdin.isatty():
        value = getpass.getpass("Secret value (input hidden): ")
    else:
        value = sys.stdin.read()
        # Strip exactly one trailing newline so `echo`/heredoc pipes behave;
        # any further whitespace is assumed to be part of the secret.
        if value.endswith("\r\n"):
            value = value[:-2]
        elif value.endswith(("\n", "\r")):
            value = value[:-1]
    if not value:
        die("secret value is empty — nothing was written")
    return value


def confirm_overwrite(key: str, secret_id: str) -> bool:
    """Ask on the controlling terminal — stdin may be the value pipe."""
    try:
        tty = open("/dev/tty", "r+")
    except OSError:
        die(
            f"secret '{key}' already exists and no terminal is available to confirm.",
            "Re-run with -y/--yes to overwrite it.",
        )
    with tty:
        tty.write(f"Secret '{key}' already exists ({secret_id}). Overwrite? [y/N] ")
        tty.flush()
        answer = tty.readline().strip().lower()
    return answer in ("y", "yes")


def unwrap(response, what: str):
    """Return .data from a ResponseForX, dying on API-level failure."""
    if not getattr(response, "success", False):
        die(
            f"{what} failed: {getattr(response, 'error_message', None) or 'unknown error'}"
        )
    return response.data


def main() -> None:
    parser = argparse.ArgumentParser(
        prog="cbws-secret-set",
        description="Create or update a Bitwarden Secrets Manager secret. "
        "The value is read from stdin (piped, or a hidden prompt).",
    )
    parser.add_argument(
        "key", help="secret Key (becomes the env var name under cbws-exec)"
    )
    parser.add_argument(
        "--project-id",
        help="project to assign the secret to (default: default_project_id "
        f"from {SECRETS_FILE})",
    )
    parser.add_argument(
        "-y",
        "--yes",
        action="store_true",
        help="overwrite an existing secret without asking",
    )
    args = parser.parse_args()

    data = load_local_secrets()

    token = data.get(TOKEN_FIELD) or die(
        f"{TOKEN_FIELD} is missing or empty in {SECRETS_FILE}"
    )
    project_raw = (
        args.project_id
        or data.get("default_project_id")
        or die(
            "no project id available.",
            f"Add default_project_id to the '{SECURE_NOTE}' Secure Note and",
            "re-run cbws-sync-encrypted-secrets, or pass --project-id <UUID>.",
        )
    )
    org_raw = data.get("organization_id") or die(
        f"organization_id is missing in {SECRETS_FILE}.",
        f"Add organization_id to the '{SECURE_NOTE}' Secure Note and re-run",
        "cbws-sync-encrypted-secrets. It is the UUID in the Secrets Manager",
        "web-app URL:  https://vault.bitwarden.com/#/sm/<organization_id>/...",
    )
    project_id = parse_uuid(project_raw, "project id")
    org_id = parse_uuid(org_raw, "organization_id")

    client = BitwardenClient(
        client_settings_from_dict(
            {
                "apiUrl": BWS_API_URL,
                "identityUrl": BWS_IDENTITY_URL,
                "deviceType": DeviceType.SDK,
                "userAgent": "cbws-secret-set",
            }
        )
    )
    # No state_file: nothing about the session is persisted to disk.
    unwrap(client.auth().login_access_token(token, None), "access token login")

    secrets_client = client.secrets()
    identifiers = unwrap(secrets_client.list(str(org_id)), "listing secrets")
    matches = [s for s in identifiers.data if s.key == args.key]

    if len(matches) > 1:
        die(
            f"{len(matches)} secrets named '{args.key}' exist "
            f"({', '.join(str(m.id) for m in matches)}).",
            "Resolve the duplicate in the Secrets Manager web UI first.",
        )

    if matches:
        existing_id = str(matches[0].id)
        if not args.yes and not confirm_overwrite(args.key, existing_id):
            print("Aborted — nothing was written.", file=sys.stderr)
            sys.exit(1)
        existing = unwrap(secrets_client.get(existing_id), "fetching existing secret")
        value = read_value()
        unwrap(
            secrets_client.update(
                str(org_id),
                existing_id,
                args.key,
                value,
                existing.note or "",
                [project_id],
            ),
            "updating secret",
        )
        moved = (
            f" (moved from project {existing.project_id})"
            if existing.project_id and str(existing.project_id) != str(project_id)
            else ""
        )
        print(
            f"Updated secret '{args.key}' ({existing_id}) in project {project_id}{moved}."
        )
    else:
        value = read_value()
        created = unwrap(
            secrets_client.create(
                org_id,
                args.key,
                value,
                "",
                [project_id],
            ),
            "creating secret",
        )
        print(f"Created secret '{args.key}' ({created.id}) in project {project_id}.")


if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        print("\nAborted.", file=sys.stderr)
        sys.exit(130)
