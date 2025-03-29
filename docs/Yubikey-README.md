# Setting Up Yubikey on a New Computer

## Windows

### SSH Resident Key

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

### GPG Key

1. **Install GPG for Windows**
   Download and install [Gpg4win](https://gnupg.org/download/).

---

#### Optional: Set Up Kleopatra to Start on Login

You have two options:

##### Option A: Import Existing XML Task File

Use the provided `Start Kleopatra in Background at Login.xml`.
*Note: This method may not always work reliably.*

##### Option B: Create a Scheduled Task Manually

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

### Import the GPG Public Key

To import your GPG public key:

```bash
gpg --import <Path/to/file.asc>
```

---

### Test GPG Functionality

You can verify it's working with:

```bash
echo "test" | gpg --clearsign
```
