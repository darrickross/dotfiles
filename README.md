# dotfiles

A collection of dotfiles located at or below a users home directory. This allows me to manage all of my standard configuration on linux systems ensuring I can get up an running ASAP.

## Requirements

Ensure you have the following installed on your system

1. `git`
2. `nix` (with flakes enabled)

### Install `git`

#### `apt` - package manager

```sh
sudo apt install git
```

#### `dnf` - package manager

```sh
sudo dnf install git
```

### Install `nix`

Use the [official installer](https://nixos.org/download/):

```sh
sh <(curl -L https://nixos.org/nix/install) --daemon
```

> [!NOTE]
> The official installer does not enable flakes by default. The repo includes `.config/nix/nix.conf` with flakes enabled — see step 2 of the setup below.

## Setting Up Your Dotfiles on a New System

> [!WARNING]
> This explains how to use this exact `dotfiles` repository. If you intend to create one for yourself I suggest you follow the [Create your own `dotfiles` repository](#create-your-own-dotfiles-repository) steps below.

### 0 - Picking an install directory

I personally enjoy placing all work in a sub directory of my home directory to keep things cleaned up. You can choose where you want to place the `dotfiles` repo.

I use a variable to ensure all subsequent commands can reference the same path exactly as needed.

> [!TIP]
> I recommend using a common directory for your project or git repos to place your `INSTALL_DIR` inside.

```bash
INSTALL_DIR="$HOME/projects/dotfiles"
```

> [!NOTE]
> `INSTALL_DIR` requirements:
>
> - You may use either an absolute path, or relative path
> - ***Do not include a trailing slash***
>
> Your path should end in the folder which the git repository will be downloaded into. Meaning to get to this file located at the root of the repository, you should be able to identify it using `$INSTALL_DIR/README.md`.

### 1 - Git clone this repository

Clone this repository to your new system.

```sh
git clone https://github.com/darrickross/dotfiles.git $INSTALL_DIR
```

### 2 - Enable nix flakes

Copy the repo's nix configuration to enable flakes (skip if your nix already has flakes enabled):

```sh
mkdir -p ~/.config/nix
cp $INSTALL_DIR/.config/nix/nix.conf ~/.config/nix/nix.conf
```

### 3 - Link the Home Manager configuration

Link the repo's Home Manager directory to the default location Home Manager looks in:

```sh
mkdir -p ~/.config
ln -s "$INSTALL_DIR/.config/home-manager" ~/.config/home-manager
```

This symlink serves two purposes:

1. It lets plain `home-manager switch` (the `hms` alias) find the flake without a `--flake` argument.
2. Scripts and aliases locate the live repo clone at runtime by resolving this symlink backwards (see `dotfiles-root`), so nothing in the configuration hardcodes where you cloned the repo.

### 4 - Apply the Home Manager configuration

Home Manager generates `~/.bashrc`, `~/.bash_profile`, `~/.profile`, and `~/.bash_logout` itself and will refuse to overwrite existing files, so remove the distro's stock copies first:

```sh
rm -f ~/.bashrc ~/.bash_profile ~/.profile ~/.bash_logout
```

Run the Home Manager switch using the flake in this repo. On a fresh system where `home-manager` is not yet on `PATH`, use `nix run`:

```sh
nix run home-manager/master -- switch --flake ~/.config/home-manager#itsjustmech
```

> [!NOTE]
> This will install all packages declared in `home.nix`, generate shell config, and place managed files. It may take several minutes on a first run while Nix downloads packages.

After the first successful switch the `hms` alias is available for future updates:

```sh
hms
```

### 5 - Review

Verify that Home Manager applied the configuration correctly by checking that managed files and aliases are in place:

```sh
# Confirm the home-manager generation was created
home-manager generations

# Confirm managed scripts are on PATH
which cbws-exec
which cbws-list-available-secrets
which cbws-sync-encrypted-secrets

# Confirm the repo clone resolves from the symlink made in step 3
dotfiles-root
```

## YubiKey Setup

### Linux

#### SSH Resident Key `ed25519-sk`

```bash
ssh-keygen -t ed25519-sk -O resident -O verify-required
```

---

### Windows

#### SSH Resident Key

1. **Install Windows OpenSSH**
   Download from [Win32-OpenSSH Releases](https://github.com/PowerShell/Win32-OpenSSH/releases).
   This provides access to `ssh-sk-helper.exe`.

2. **Re-generate the resident key**
   Run the following command (in PowerShell, not WSL):

   ```bash
   ssh-keygen -K
   ```

3. **Rename the key**
   Replace `HASH_HERE` with the appropriate identifier:

   ```bash
   mv id-HASH_HERE yubikey_sk
   ```

---

#### GPG Key

1. **Install GPG for Windows**
   Download and install [Gpg4win](https://gnupg.org/download/).

---

##### Optional: Set Up Kleopatra to Start on Login

You have two options:

###### Option A: Import Existing XML Task File

Use the provided [`Start Kleopatra in Background at Login.xml`](./docs/Start%20Kleopatra%20in%20Background%20at%20Login.xml).

> [!NOTE]
> This method may not always work reliably. You can manually recreate this using [Option B](#option-b-create-a-scheduled-task-manually).

###### Option B: Create a Scheduled Task Manually

1. Open **Task Scheduler**
2. Go to **Action > Create Task**
3. Under the **General** tab:
   - Name the task (e.g., "Kleopatra Background Start")
4. Under the **Triggers** tab:
   - New Trigger: **At log on**
5. Under the **Actions** tab:
   - New Action: **Start a program**
   - **Program**: `cmd.exe`
   - **Arguments**:

     ```none
     /c START "" /B "C:\Program Files (x86)\Gpg4win\bin\kleopatra.exe" --daemon
     ```

6. Under the **Conditions** tab:
   - Uncheck all options
7. Under the **Settings** tab:
   - Uncheck all except **"Allow task to be run on demand"**

---

#### Import the GPG Public Key

To import your GPG public key:

```bash
gpg --import <Path/to/file.asc>
```

---

#### Test GPG Functionality

You can verify it's working with:

```bash
echo "test" | gpg --clearsign
```

---

### WSL2

WSL2 has no direct USB access, so the YubiKey cannot be used by Linux binaries directly. The solution is to install the relevant tools on the **Windows host** — WSL2's default PATH includes the Windows PATH, so Linux processes can discover and invoke Windows `.exe` files transparently.

#### `age-plugin-yubikey`

Allows `age`/`sops` inside WSL2 to perform YubiKey-backed encryption/decryption. The Linux `age` binary spawns `age-plugin-yubikey.exe` as a subprocess over stdin/stdout — the `.exe` runs on Windows where it has full USB access to the YubiKey. No USB forwarding (e.g. usbipd-win) is required.

##### Installation (PowerShell as Administrator)

1. Download the latest `age-plugin-yubikey.exe` from the [releases page](https://github.com/str4d/age-plugin-yubikey/releases).

2. Create the install directory:

   ```powershell
   mkdir "C:\Program Files\age-plugin-yubikey"
   ```

3. Copy the binary into it:

   ```powershell
   cp age-plugin-yubikey.exe "C:\Program Files\age-plugin-yubikey\age-plugin-yubikey.exe"
   ```

4. **Optional** — Add to the Windows system PATH so `age-plugin-yubikey.exe` is callable from anywhere on Windows (not required for WSL2, which uses the wrapper script):

   ```powershell
   [Environment]::SetEnvironmentVariable(
     "Path",
     $Env:Path + ";C:\Program Files\age-plugin-yubikey",
     [EnvironmentVariableTarget]::Machine
   )
   ```

5. **WSL2** — Apply the home-manager configuration to install the wrapper script:

   ```bash
   hms
   ```

> [!NOTE]
> WSL2 uses the wrapper script at `~/.local/bin/age-plugin-yubikey` (managed by home-manager) which hardcodes the path to the `.exe`. The optional system PATH step is only needed if you also want to call `age-plugin-yubikey.exe` directly from Windows.

Verify the wrapper is working from WSL2:

```bash
age-plugin-yubikey --help
```

##### Initial Key Generation (WSL2, first time only)

> [!WARNING]
> Only run this once per YubiKey. Generating a key in a slot that already has one will overwrite it permanently with no recovery.

1. Generate the age key on the YubiKey:

   > [!IMPORTANT]
   > Skip this step if you already have an `age` key on your yubikey.

   ```bash
   age-plugin-yubikey --generate --slot 1 --pin-policy always --touch-policy always --name "darrickross/dotfiles age"
   ```

2. Export the identity stanza so `sops` can use the YubiKey for decryption:

   ```bash
   mkdir -p ~/.config/age
   age-plugin-yubikey --identity --slot 1 > ~/.config/age/yubikey-identity.txt
   ```

   This file is what `SOPS_AGE_KEY_FILE` points to.

##### Load `age` Public Key into `.sops.yaml`

> [!WARNING]
> The recipient committed in `.config/sops/.sops.yaml` belongs to the repo owner's YubiKey. Anything encrypted to it can only be decrypted by that physical key. If you are not the repo owner — or you have replaced your YubiKey — you **must** replace the recipient with your own using the steps below before encrypting anything, otherwise you will create files you cannot decrypt.

These steps are safe to run at any time. Make sure the YubiKey is available on the host Windows system before running them.

1. Load the recipient (public key) into `.config/sops/.sops.yaml`. The script locates the repo from your current directory, so run it from anywhere inside your dotfiles clone:

   ```bash
   cd $INSTALL_DIR
   sops-load-yubikey-recipient
   ```

2. Apply the change so home-manager places the updated file at `~/.config/sops/.sops.yaml` (where scripts read it from):

   ```bash
   hms
   ```

---

## Bitwarden Setup

### Design rationale — one machine account, one project

The primary reason for this setup is to reduce the number of BWS projects and machine accounts: the Bitwarden Secrets Manager **free tier allows only 3 projects and 3 machine accounts**, which is too few to scope a project per workload. The accepted risk is a single machine account whose token reads a single project of co-mingled secrets — any command run through `cbws-exec` receives every secret in the default project.

The compensating controls are on the token's *lifetime* rather than its scope: it only ever exists (1) encrypted on disk under a YubiKey-backed age key, and (2) in the environment of the one process tree started by `cbws-exec` or `cbws-list-available-secrets`. It is never exported into an interactive shell — no command exists to do so.

The CLI workflow is **read-only**: this machine only reads secrets. Creating, editing, or deleting secrets is done manually in the Bitwarden Secrets Manager web UI.

### `local-machine-bws-secrets` Secure Note

The `cbws-sync-encrypted-secrets` script fetches a Bitwarden Secure Note named **`local-machine-bws-secrets`** from your primary Bitwarden account. The Notes field must contain valid YAML in the following format:

```yaml
local_computer_machine_account_bws_access_token: "your-bws-access-token"
default_project_id: "your-default-project-id"
```

The BWS access token comes from the Bitwarden Secrets Manager web app under the machine account for this computer. `default_project_id` is the UUID of the BWS project whose secrets `cbws-exec` injects when `--project-id` is not given — find it in the Secrets Manager web app under **Projects**.

> [!NOTE]
> Run `cbws-sync-encrypted-secrets` on first setup, or any time the BWS access token is rotated. It encrypts the token locally with your YubiKey so it never sits on disk in plaintext.

---

### Daily Workflow

#### 1. Run a command with secrets injected — `cbws-exec` (primary)

`cbws-exec` is the default way to use secrets. It decrypts the BWS access token with your YubiKey (one PIN + touch), then runs your command via `bws run` scoped to `default_project_id` — each secret's **Key** becomes an environment variable in the command's process tree:

```bash
cbws-exec -- ./my-script-here               # script reads secrets from env vars
cbws-exec --project-id <UUID> -- ./deploy.sh # override the default project
```

Write your scripts to assume the secrets are already present as environment variables. The token and the secrets exist only for the lifetime of the command: nothing is exported into your interactive shell, and nothing touches disk or shell history. Each invocation costs one YubiKey touch, which is the point — decryption always requires physical presence.

#### 2. List available secrets

To see what secrets the machine account has access to:

```bash
cbws-list-available-secrets
```

This is self-contained: it prompts for your YubiKey PIN + touch to decrypt the access token, lists the secrets, and exits — the token lives only inside that subprocess and never enters your shell.

Output shows the UUID and key name of every secret:

```text
             Secret UUID             | Key
xxxxxxxx-xxxx-xxxx-xxxx-xxxxxxxxxxxx | MY_API_KEY
xxxxxxxx-xxxx-xxxx-xxxx-xxxxxxxxxxxx | DATABASE_PASSWORD
```

The **Key** column is what you use as the environment variable name in your commands.

#### 3. Creating or editing secrets — use the web UI

There is intentionally no command for loading `BWS_ACCESS_TOKEN` into your shell or for writing secrets from the CLI. This machine only **reads** secrets; create, edit, or delete them in the Bitwarden Secrets Manager web UI. (The former `cbws-load-local-machine-credential` loader was removed for this reason — exporting the token into an interactive shell would hand it to every child process for the rest of the session.)

---

### Naming Secrets in Bitwarden Secrets Manager

The **Key** field of a secret in Bitwarden Secrets Manager becomes the environment variable name when `cbws-exec` (via `bws run`) injects it. Follow these rules to avoid unexpected behavior:

- **Use uppercase with underscores** — `MY_API_KEY`, not `my-api-key`. Lowercase names work but are unconventional for environment variables.
- **Start with a letter or underscore** — names that start with a digit are invalid in most shells (`1PASSWORD` will fail).
- **No hyphens** — hyphens are not valid in shell variable names. Use underscores instead (`API_SECRET_KEY`, not `API-SECRET-KEY`).
- **No spaces** — spaces break variable name parsing entirely.
- **Avoid reserved names** — do not use names that shells or programs define themselves (`PATH`, `HOME`, `USER`, `SHELL`, `IFS`, etc.).

A safe naming pattern is `SCREAMING_SNAKE_CASE` that describes the system and purpose:

examples:

```text
SERVICE_NAME_SECRET_TYPE
GITHUB_TOKEN
POSTGRES_PASSWORD
STRIPE_API_KEY
```

---

## Create your own `dotfiles` repository

TODO
