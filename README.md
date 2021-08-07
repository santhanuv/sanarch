# Arch-Installer

Automated Arch Linux installer written in python, to learn Python :).

## Configuration Files
part_file: Contains information about how to partition the disk in JSON format.
config_file: Contains information about installation in JSON format.

## Installation

After Booting into live environment:
```
pacman -Syy git
git clone https://github.com/santhanuv17/arch-installer.git
cd arch-installer
python installer.py part_file config_file
```

## Options
-y : Installs without asking confirmation.

# Current File System support.
1. ext4
2. btrfs
3. FAT32
4. swap
