# dotfiles

A collection of dotfiles located at or below a users home directory. This allows me to manage all of my standard configuration on linux systems ensuring I can get up an running ASAP.

## Requirements

Ensure you have the following installed on your system

1. `git`
2. `stow`

### `apt` - package manager

```sh
sudo apt install git stow
```

### `dnf` - package manager

```sh
sudo dnf install git stow
```

## Setting Up Your Dotfiles on a New System

> [!WARNING]
> This explains how to use this exact `dotfiles` repository. If you intend to create one for yourself I suggest you follow the [Create your own `dotfiles` repository](#create-your-own-dotfiles-repository) steps below.

### 0 - Picking an install directory

I personally enjoy placing all work in a sub directory of my home directory to keep things cleaned up. You can choose where you want to place the `dotfiles` repo.

I use a variable to ensure all subsequent commands can reference the same path exactly as needed.

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

### 2 - Dry Run the Operation

Show all of the changes stow would make to the system.

```sh
stow \
  --verbose=1 \
  --dir="$INSTALL_DIR" \
  --target="$HOME" \
  --no-folding \
  --simulate \
  .
```

> [!NOTE]
> Heres what the above arguments mean:
>
> - `--verbose=1`
>   - Select verbosity level 1 which prints a concise list of operations performed.
> - `--dir="$INSTALL_DIR"`
>   - Tell stow where to find the folder containing dotfiles to link back to.
> - `--target="$HOME"`
>   - Tell stow where to place the symbolic links, this repository is for common dotfiles in your home directory.
> - `--no-folding`
>   - Tell stow to always create folders.
>   - Example, given `<dotfiles_repo_directory>/.folder_name/my.config`
>     - Default
>       - stow will create a symbolic link in the directory `$HOME` named `.folder_name/my.config` pointing to `<dotfiles_repo_directory>/.folder_name/my.config`
>     - With `--no-folding`
>       - stow will create the folder `$HOME/.folder_name`
>       - stow will then create a symbolic link called `my.config` in `.folder_name` pointing to `<dotfiles_repo_directory>/.folder_name/my.config`
>   - This option ensures that when you are placing your dotfiles on a new system which has not yet installed the software, the original file structure is maintained.
> - `--simulate`
>   - stow will not make any modifications to the system and instead just show you what would happen if it did run.
> - `.`
>   - This tells stow to unpack all configs (minus any listed in `.stow-local-ignore`).

Expected dry run results:

```sh
MKDIR: .aws
LINK: .aws/config => ../projects/dotfiles/.aws/config
LINK: .gitconfig => projects/dotfiles/.gitconfig
LINK: .bash_logout => projects/dotfiles/.bash_logout
MKDIR: .config
MKDIR: .config/gh
LINK: .config/gh/config.yml => ../../projects/dotfiles/.config/gh/config.yml
WARNING! stowing . would cause conflicts:
  * existing target is neither a link nor a directory: .bashrc
  * existing target is neither a link nor a directory: .profile
All operations aborted.
```

Explanation:

- `MKDIR: <FOLDER>`
  - Stow is showing what folders it will create
- `LINK: <SYMBOLIC_LINK_FILE> => <PATH_TO_DOTFILE>`
  - Stow is showing what symbolic link files it will create
- `WARNING! stowing . would cause conflicts:` & `* existing target is neither a link nor a directory: <FILE>`
  - Stow is showing what conflicts exist which would abort stows operations

### 3 - Handle conflicts & Apply Symbolic Links

By default there will usually be some conflicts. There are 3 ways to fix those conflicts.

1. Adopt the file
    - [3.a - Adopt Conflicts](#3a---adopt-conflicts)
    - Usually I would suggest doing this as its the easiest way to get started.
2. Backup the old config to a new name
    - [3.b - Backup Conflicts](#3b---backup-conflicts)
    - When I know all of the contents of existing conflicts are completely wrong, and I want to keep nothing from them.
3. Delete the old conflict
    - [3.c - Delete Conflicts](#3c---delete-conflicts)
    - In the event that I know none of the configs currently in place are correct, then I can forcefully override them.

> [!TIP]
> For beginners select [3.a - Adopt Conflicts](#3a---adopt-conflicts) for the easiest operation.

#### 3.a - Adopt Conflicts

Easiest way to handle conflicts is to "adopt" all of the current config files into your dotfile git repo using `--adopt`. This will move the conflicting files from the `$HOME` directory to the dotfiles directory. Then create all symbolic links.

```sh
stow \
  --verbose=1 \
  --dir="$INSTALL_DIR" \
  --target="$HOME" \
  --no-folding \
  --adopt \
  .
```

> [!NOTE]
> `--adopt` is used to tell `stow` to move all conflicting files into the dotfiles folder, then install symbolic links
>
> See [2 - Dry Run the Operation](#2---dry-run-the-operation) for explanation of the remaining arguments used in this command.
>
> Because git is used to track the version of files you can safely do this operation because you can verify all changes in the dotfile directory before committing. This allows you to view all differences between the dotfile in git, and what currently exists on the system.

You can now check the differences in those conflicts.

```sh
cd $INSTALL_DIR
git status
```

You will now see the previously noted conflicts files that git is tracking the differences of.

```text
On branch main
Your branch is up to date with 'origin/main'.

Changes not staged for commit:
  (use "git add <file>..." to update what will be committed)
  (use "git restore <file>..." to discard changes in working directory)
        modified:   .bashrc
        modified:   .profile

no changes added to commit (use "git add" and/or "git commit -a")
```

You can now review the changes using `git diff <FILE>`

```text
$ git diff .bashrc
diff --git a/.bashrc b/.bashrc
index a8b0327..c5500a4 100644
--- a/.bashrc
+++ b/.bashrc
@@ -128,3 +128,8 @@ # Content of file not changed line a
 # Content of file not changed line b
 # Content of file not changed line c
 # Content of file not changed line d
+
+# Some differences HERE
+
```

Follow standard git procedures to either add the changes or remove them

```sh
git add -p
```

Need help using git on the command line?

- [What does each of the `[y,n,q,a,d,/,K,j,J,g,e,?]` stand for in context of `git -p`](https://stackoverflow.com/a/10605465)
- [My preferred youtube playlist guide to `git`, "Git Tutorials" by Dan Gitschooldude](https://www.youtube.com/playlist?list=PLu-nSsOS6FRIg52MWrd7C_qSnQp3ZoHwW)

Once you have handles all of the differences you are done, all of your symbolic links will be installed.

> [!IMPORTANT]
> See [4 - Review](#4---review) as the next step.

#### 3.b - Backup Conflicts

Optionally if you do not want to review the differences between the conflicting files and the current dotfile version, you can just make a backup of the conflicts.

For each conflict identified above during [2 - Dry Run the Operation](#2---dry-run-the-operation), run the following replacing `FILE_PATH_HERE` with the actual conflicting file.

```sh
mv FILE_PATH_HERE FILE_PATH_HERE.bak
```

Now you can run stow as normal without issues.

```sh
stow \
  --verbose=1 \
  --dir="$INSTALL_DIR" \
  --target="$HOME" \
  --no-folding \
  .
```

Make sure to resolve all conflicts otherwise stow will error out.

> [!IMPORTANT]
> See [4 - Review](#4---review) as the next step.

#### 3.c - Delete Conflicts

If you know what your are doing, and do not want to keep any existing conflicting files you can delete the changes using `--adopt` [from 3.a - Adopt Conflicts](#3a---adopt-conflicts) and `git reset *`

> [!CAUTION]
> The following is an action that can not be undone, please take caution to only do this if you are sure you do not need the existing contents of the conflicting files.

```sh
cd $INSTALL_DIR
git status
```

Verify first that there are no current changes in the git repo before taking this operation. You are expecting to see the following output:

```text
$ git status
On branch main
Your branch is up to date with 'origin/main'.

nothing to commit, working tree clean
```

> [!WARNING]
> If you do not see the above output resolve any above changes first, then recheck the current status is up to date.

Now go about deleting all conflicts

```sh
stow \
  --verbose=1 \
  --dir="$INSTALL_DIR" \
  --target="$HOME" \
  --no-folding \
  --adopt \
  .

git restore .
```

You have now overridden the conflict files and applied the dotfiles.

### 4 - Review

You can now verify that the symbolic links are present using `ls -al` to list all files, showing their type, which in the case of symbolic links, will show the link's path. Using `grep` to filter this down can be used to show just the symbolic links.

```sh
ls -al $HOME | grep "\->"
```

Example output

```text
$ ls -al $HOME | grep "\->"
lrwxrwxrwx  1 my_user my_user    25 Aug  3 22:14 .bash_logout -> projects/dotfiles/.bash_logout
lrwxrwxrwx  1 my_user my_user    20 Aug  3 22:57 .bashrc -> projects/dotfiles/.bashrc
lrwxrwxrwx  1 my_user my_user    23 Aug  3 22:14 .gitconfig -> projects/dotfiles/.gitconfig
lrwxrwxrwx  1 my_user my_user    21 Aug  3 22:14 .profile -> projects/dotfiles/.profile
```

You can also use `find` to search recursively to see the symbolic links, without their link path.

```sh
find $HOME -type l
```

Example output

```text
$ find $HOME -type l
/home/my_user/.aws/config
/home/my_user/.gitconfig
/home/my_user/.bash_logout
/home/my_user/.bashrc
/home/my_user/.profile
/home/my_user/.config/gh/config.yml
```

## Create your own `dotfiles` repository

TODO
