from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import ClassVar
from sanarch.lib.utils.pacman import Pacman
from pathlib import Path
from sanarch.lib.command import Command

def bootloader_helper(bootloader):
    match bootloader:
        case "grub":
            return Grub()
        case _:
            raise Exception("Bootloader not supported!")

@dataclass
class Bootloader(ABC):
    TARGET: ClassVar[str] = "x86_64-efi"

    @abstractmethod
    def install(self, esp,*, detect_other_os = False):
        """ Installs the bootloader """

@dataclass
class Grub(Bootloader):
    CONFIG_FILE_PATH: ClassVar = "/boot/grub/grub.cfg"
    PACKAGES: ClassVar[list[str]] = ["grub", "efibootmgr", "os-prober", "dosfstools", "mtools"]
    BOOTLOADER_ID: ClassVar[str] = "GRUB"
    pacman:Pacman = field(init=False, default=None)

    def __post_init__(self):
        self.pacman = Pacman(arch_chroot=True)


    def install_package(self):
        self.pacman.install(packages=self.PACKAGES)


    def mkconfig(self):
        args = ["-o", self.CONFIG_FILE_PATH]
        mkconfig = Command(name="grub-mkconfig", args=args)
        mkconfig(arch_chroot=True)


    def grub_install(self, esp):
        Path(f'/mnt/self.INSTALL_DIR').mkdir(parents=True, exist_ok=True)

        args = [f'--target={self.TARGET}', f'--bootloader-id={self.BOOTLOADER_ID}', f'--efi-directory={esp}']
        grub = Command(name = "grub-install", args=args, capture_output=False)
        grub(arch_chroot=True)


    def update_config(self, file, current_line, replace_line, *, match_exact = True, greedy = False):
        with open(file, "r") as grubfile:
            lines = grubfile.readlines()
        
        for linenum, line in enumerate(lines):
            if match_exact and current_line == line or not match_exact and current_line in line:
                lines[linenum] = replace_line
                if not greedy:
                    break

        with open(file, "w") as grubfile:
            grubfile.writelines(lines)        


    def install(self, esp, *, detect_other_os = False):
        DEFAULT_CONFIG_FILE = "/mnt/etc/default/grub"

        if not esp:
            raise Exception("No esp specified")
        
        # Installs the required packages
        self.install_package()

        # Install grub to the system
        self.grub_install(esp)
        if detect_other_os:
            self.update_config(DEFAULT_CONFIG_FILE, "#GRUB_DISABLE_OS_PROBER=false", "GRUB_DISABLE_OS_PROBER=false", match_exact= False)

        # Create the configuration files
        self.mkconfig()
