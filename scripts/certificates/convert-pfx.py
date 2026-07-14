#!/usr/bin/env python3
"""Extract keys and certificates from a PKCS#12 (.pfx/.p12) bundle.

Python port of convert_pfx.sh. Parses the bundle with the `cryptography`
library instead of shelling out to openssl, so the password never appears
on a process command line (visible in `ps`), in an exported environment
variable, or in shell history.

Password sources, in order:

  --password-stdin    read the password from stdin — for pipelines and
                      automation, e.g. a secrets manager
  interactive prompt  getpass prompt with terminal echo disabled (default)

Output files reuse the extensions of the shell version:

  | Flag                | File                    |
  | ------------------- | ----------------------- |
  | -p, --private       | <output>.insecure.pem   |
  | -P, --public        | <output>.pub            |
  | -c, --certificate   | <output>.crt            |
  | -C, --chain         | <output>.chain.crt      |
  | -r, --root-ca       | <output>.root.crt       |

The private key is written unencrypted (hence `.insecure.pem`) with 0600
permissions.

Examples:
  convert-pfx.py -i /path/to/bundle.pfx -p -c -C
  convert-pfx.py -i bundle.pfx -a -o /path/to/output
  convert-pfx.py -i bundle.pfx -d
  bws run -- bash -c 'printf %s "$PFX_PASSWORD"' \\
    | convert-pfx.py -i bundle.pfx -s --password-stdin
"""

from __future__ import annotations

import argparse
import getpass
import os
import sys
from pathlib import Path

from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.serialization import pkcs12
from cryptography.x509 import Certificate

# Default file extensions (matching convert_pfx.sh)
EXT_PRIVATE_KEY = "insecure.pem"
EXT_PUBLIC_KEY = "pub"
EXT_CERTIFICATE = "crt"
EXT_CHAIN_CERTIFICATE = "chain.crt"
EXT_ROOT_CA_CERTIFICATE = "root.crt"

# Log levels
QUIET = 0
DEFAULT = 1
VERBOSE = 2

GREEN = "\033[0;32m"
RED = "\033[0;31m"
RESET = "\033[0m"

log_level = DEFAULT


def print_error(message: str) -> None:
    print(f"{RED}ERROR{RESET}: {message}", file=sys.stderr)


def print_if_not_quiet(message: str) -> None:
    if log_level >= DEFAULT:
        print(message)


def print_if_verbose(message: str) -> None:
    if log_level >= VERBOSE:
        print(message)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Extract keys/certificates from a PKCS#12 (.pfx/.p12) bundle.",
        epilog="Examples:" + __doc__.split("Examples:")[1],
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    parser.add_argument(
        "-i",
        "--input",
        required=True,
        metavar="PATH",
        help="input .pfx/.p12 file",
    )

    extract = parser.add_argument_group("file types to extract")
    extract.add_argument(
        "-p",
        "--private",
        action="store_true",
        help=f"extract private key                name.{EXT_PRIVATE_KEY}",
    )
    extract.add_argument(
        "-P",
        "--public",
        action="store_true",
        help=f"extract public key                 name.{EXT_PUBLIC_KEY}",
    )
    extract.add_argument(
        "-c",
        "--certificate",
        action="store_true",
        help=f"extract certificate                name.{EXT_CERTIFICATE}",
    )
    extract.add_argument(
        "-C",
        "--chain",
        action="store_true",
        help=f"extract full certificate chain     name.{EXT_CHAIN_CERTIFICATE}",
    )
    extract.add_argument(
        "-r",
        "--root-ca",
        action="store_true",
        help=f"extract root CA certificate        name.{EXT_ROOT_CA_CERTIFICATE}",
    )
    extract.add_argument(
        "-s",
        "--standard",
        action="store_true",
        help="effectively the same as -p -c",
    )
    extract.add_argument(
        "-a",
        "--all",
        action="store_true",
        help="effectively the same as -p -P -c -C -r",
    )

    modifiers = parser.add_argument_group("modifiers")
    modifiers.add_argument(
        "-o",
        "--output",
        metavar="PATH",
        help="base name for output files (defaults to the .pfx filename)",
    )
    modifiers.add_argument(
        "--password-stdin",
        action="store_true",
        help="read the bundle password from stdin instead of prompting",
    )
    modifiers.add_argument(
        "-d",
        "--details",
        action="store_true",
        help="show details about the .pfx file",
    )
    modifiers.add_argument(
        "-q", "--quiet", action="store_true", help="run in quiet mode"
    )
    modifiers.add_argument(
        "-v", "--verbose", action="store_true", help="run in verbose mode"
    )

    args = parser.parse_args()

    if args.standard:
        args.private = True
        args.certificate = True
    if args.all:
        args.private = True
        args.public = True
        args.certificate = True
        args.chain = True
        args.root_ca = True

    return args


def read_password(pfx_file: str, from_stdin: bool) -> bytes:
    """Return the bundle password without it ever touching argv or env.

    --password-stdin reads all of stdin and strips trailing newlines (the
    same contract as `docker login --password-stdin`); otherwise getpass
    prompts on the controlling terminal with echo disabled.
    """
    if from_stdin:
        return sys.stdin.buffer.read().rstrip(b"\r\n")
    return getpass.getpass(f"Enter password for {pfx_file}: ").encode()


def load_bundle(pfx_file: str, password: bytes):
    """Load the PKCS#12 bundle; exits with a clear error on bad password."""
    data = Path(pfx_file).read_bytes()
    try:
        # `or None`: an empty password means an unprotected bundle.
        return pkcs12.load_key_and_certificates(data, password or None)
    except ValueError:
        print_error(f"Invalid password (or corrupt PKCS#12 data) for {pfx_file}")
        sys.exit(1)


def pem(cert: Certificate) -> bytes:
    return cert.public_bytes(serialization.Encoding.PEM)


def write_private_key(path: str, key) -> None:
    """Write the unencrypted private key, created with 0600 permissions."""
    key_bytes = key.private_bytes(
        serialization.Encoding.PEM,
        serialization.PrivateFormat.PKCS8,
        serialization.NoEncryption(),
    )
    fd = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_TRUNC, 0o600)
    with os.fdopen(fd, "wb") as f:
        f.write(key_bytes)


def find_root_ca(ca_certs: list[Certificate]) -> Certificate | None:
    """Return the self-signed (issuer == subject) certificate in the chain."""
    for index, cert in enumerate(ca_certs, start=1):
        print_if_verbose(f"Operating on certificate: {index}/{len(ca_certs)}")
        print_if_verbose(f" - Issuer:  {cert.issuer.rfc4514_string()}")
        print_if_verbose(f" - Subject: {cert.subject.rfc4514_string()}")
        if cert.issuer == cert.subject:
            print_if_verbose(" - Self-signed certificate detected.")
            print_if_verbose(" - Assuming this is the Root CA certificate.")
            return cert
    return None


def show_details(
    pfx_file: str, key, cert: Certificate | None, ca_certs: list[Certificate]
) -> None:
    print_if_not_quiet("")
    print(f"Details of {pfx_file}:")
    if key is not None:
        print(f"  Private key:   {type(key).__name__.lstrip('_')}, {key.key_size} bits")
    else:
        print("  Private key:   (none)")
    for label, c in [("Certificate", cert)] + [
        ("CA certificate", ca) for ca in ca_certs
    ]:
        if c is None:
            print(f"  {label}:   (none)")
            continue
        print(f"  {label}:")
        print(f"    Subject:     {c.subject.rfc4514_string()}")
        print(f"    Issuer:      {c.issuer.rfc4514_string()}")
        print(f"    Serial:      {c.serial_number:x}")
        print(f"    Not before:  {c.not_valid_before_utc}")
        print(f"    Not after:   {c.not_valid_after_utc}")


def main() -> int:
    global log_level

    args = parse_args()
    if args.quiet:
        log_level = QUIET
    elif args.verbose:
        log_level = VERBOSE

    pfx_file = args.input
    if not os.path.isfile(pfx_file):
        print_error(f"File not found: {pfx_file}")
        return 1

    output_name = args.output or f"./{Path(pfx_file).stem}"

    password = read_password(pfx_file, args.password_stdin)
    key, cert, ca_certs = load_bundle(pfx_file, password)
    ca_certs = list(ca_certs or [])

    created: list[str] = []

    if args.private:
        path = f"{output_name}.{EXT_PRIVATE_KEY}"
        print_if_verbose(f"Extracting private key to '{path}'...")
        if key is None:
            print_error(
                "Failed to extract private key: bundle contains no private key."
            )
            return 1
        write_private_key(path, key)
        print_if_not_quiet("Successfully extracted Private Key.")
        created.append(path)

    if args.public:
        path = f"{output_name}.{EXT_PUBLIC_KEY}"
        print_if_verbose(f"Extracting public key to '{path}'...")
        if cert is None:
            print_error("Failed to extract public key: bundle contains no certificate.")
            return 1
        public_bytes = cert.public_key().public_bytes(
            serialization.Encoding.PEM,
            serialization.PublicFormat.SubjectPublicKeyInfo,
        )
        Path(path).write_bytes(public_bytes)
        print_if_not_quiet("Successfully extracted Public Key.")
        created.append(path)

    if args.certificate:
        path = f"{output_name}.{EXT_CERTIFICATE}"
        print_if_verbose(f"Extracting certificate to '{path}'...")
        if cert is None:
            print_error(
                "Failed to extract certificate: bundle contains no certificate."
            )
            return 1
        Path(path).write_bytes(pem(cert))
        print_if_not_quiet("Successfully extracted Certificate.")
        created.append(path)

    if args.chain:
        path = f"{output_name}.{EXT_CHAIN_CERTIFICATE}"
        print_if_verbose(f"Extracting chain certificate to '{path}'...")
        if not ca_certs:
            print_error(
                "Failed to extract chain certificate: bundle contains no CA certificates."
            )
            return 1
        Path(path).write_bytes(b"".join(pem(c) for c in ca_certs))
        print_if_not_quiet("Successfully extracted Chain Certificate.")
        created.append(path)

    if args.root_ca:
        path = f"{output_name}.{EXT_ROOT_CA_CERTIFICATE}"
        print_if_verbose(f"Extracting root CA certificate to '{path}'...")
        print_if_verbose(f"Found {len(ca_certs)} certificates in the chain")
        root_ca = find_root_ca(ca_certs)
        if root_ca is None:
            print_error("Failed to extract root CA certificate.")
            return 1
        Path(path).write_bytes(pem(root_ca))
        print_if_not_quiet("Successfully extracted Root CA Certificate.")
        created.append(path)

    if args.details:
        show_details(pfx_file, key, cert, ca_certs)

    if created and log_level >= DEFAULT:
        print("")
        print("Files created:")
        for path in created:
            print(f"  - {path}")

    return 0


if __name__ == "__main__":
    sys.exit(main())
