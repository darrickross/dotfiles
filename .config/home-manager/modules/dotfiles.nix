# Registry of plain config files tracked in this repo that home-manager
# deploys into $HOME. Add a file here (source = repo path, keyed by its
# home-relative path) and run 'hms' to place it.
#
# The repo copy is the source of truth — edit it with any editor, then run
# 'hms' to apply. Nix snapshots the file at build time, so the deployed
# copy is a read-only symlink into the nix store; tools that rewrite their
# own config (e.g. `gh config set`, `aws configure`) will fail against it —
# make those edits in the repo instead.
#
# Relative sources resolve inside the nix-store copy of the repo, so files
# referenced here MUST be tracked by git (at least `git add`ed) or the
# flake build will not see them.
{ ... }:
{
  home.file = {
    # Git identity, signing, and gh-based credential helper.
    ".gitconfig" = {
      source = ../../../.gitconfig;
      force = true;
    };

    # SSH: entry point plus per-host configs it Includes. Machine-local
    # configs (e.g. local_network.ssh_config) are intentionally not tracked
    # or deployed — create them directly in ~/.ssh/configs/.
    ".ssh/config" = {
      source = ../../../.ssh/config;
      force = true;
    };
    ".ssh/configs/github.ssh_config" = {
      source = ../../../.ssh/configs/github.ssh_config;
      force = true;
    };

    # AWS CLI defaults (no credentials — those are never tracked).
    ".aws/config" = {
      source = ../../../.aws/config;
      force = true;
    };

    # GitHub CLI settings. Auth state lives in hosts.yml/keyring, not here.
    ".config/gh/config.yml" = {
      source = ../../gh/config.yml;
      force = true;
    };

    # oh-my-posh prompt theme, read by modules/bash/prompt.nix.
    ".config/ohmyposh/bash_prompt.toml" = {
      source = ../../ohmyposh/bash_prompt.toml;
      force = true;
    };

    # Nix settings (flakes enabled). First-time bootstrap still requires the
    # manual `cp` from the README — flakes must already be enabled for
    # home-manager to evaluate this flake at all; this keeps it synced after.
    ".config/nix/nix.conf" = {
      source = ../../nix/nix.conf;
      force = true;
    };

    # sops creation rules (age recipient = YubiKey public key). Placed at a
    # fixed home path so scripts can find it regardless of where this repo is
    # cloned — sops only discovers .sops.yaml by walking upward from cwd, so
    # scripts must pass --config with this path explicitly.
    ".config/sops/.sops.yaml" = {
      source = ../../sops/.sops.yaml;
      force = true;
    };
  };
}
