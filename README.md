# dotfiles

A collection of dotfiles located at or below a users home directory. This allows me to manage all of my standard configuration on linux systems ensuring I can get up an running ASAP.

## Requirements

Ensure you have the following installed on your system

### Git

```bash
sudo apt install git
```

### Stow

```bash
sudo apt install stow
```

## Check out repo

First, check out the dotfiles repo in your $HOME directory using git.

Notice the trailing `$HOME` specifying where to check the repo at.

```bash
git clone https://github.com/darrickross/dotfiles.git $HOME/dotfiles
cd $HOME/dotfiles
```

## Installation

### Automagic

Automagically install the dotfiles into the home directory. If it runs into conflicting files which already exist it asks you if you want to back them up. Backing up will `mv $file $file.bak`

```bash
./install
```

### Manual

Use GNU stow to create symlinks

```bash
stow .
```

Or more verbose

```bash
stow -v 2 .
```

Or do a dry run

```bash
stow -n -v 2 .
```
