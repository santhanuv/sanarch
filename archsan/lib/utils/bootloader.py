from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import ClassVar
from lib.utils.pacman import Pacman
from pathlib import Path
from lib.command import Command

def bootloader_helper(bootloader):
    match bootloader:
        case "grub":
            return Grub()
        case _:
            raise Exception("Bootloader not supported!")

@dataclass
class Bootloader(ABC):
    INSTALL_DIR: ClassVar[str] = "/boot/efi"
    TARGET: ClassVar[str] = "x86_64-efi"

    @abstractmethod
    def install(self):
        """ Installs the bootloader """

@dataclass
class Grub(Bootloader):
    CONFIG_FILE_PATH: ClassVar = "/boot/grub/grub.cfg"
    PACKAGES: ClassVar[list[str]] = ["grub", "efibootmgr"]
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


    def grub_install(self):
        Path(f'/mnt/self.INSTALL_DIR').mkdir(parents=True, exist_ok=True)

        args = [f'--target={self.TARGET}', f'--bootloader-id={self.BOOTLOADER_ID}', f'--efi-directory={self.INSTALL_DIR}']
        grub = Command(name = "grub-install", args=args)
        grub(arch_chroot=True)


    def install(self):
        # Installs the required packages
        self.install_package()
        
        # Install grub to the system
        self.grub_install()

        # Create the configuration files
        self.mkconfig()