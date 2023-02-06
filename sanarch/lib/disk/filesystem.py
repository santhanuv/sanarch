from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from sanarch.lib.command import Command
from pathlib import Path
from typing import Optional

def filesystem_helper(fstype, path, mountpoint, force_format, mountoptions, subvolumes):
    match fstype:
        case "btrfs":
            return Btrfs(path, mountpoint, force_format=force_format, mountoptions=mountoptions, subvolumes=subvolumes)
        case "vfat":
            return VFat(path, mountpoint, force_format=force_format, mountoptions=mountoptions)
        case "xfs":
            return Xfs(path, mountpoint, force_format=force_format, mountoptions=mountoptions)
        case "ext4":
            return Ext4(path, mountpoint, force_format=force_format, mountoptions=mountoptions)
        case _:
            raise Exception("Invalid Filesystem")

@dataclass
class FileSystem(ABC):
    devpath: str
    mountpoint: str
    force_format: bool = field(default=False)
    label: Optional[str] = field(default=None)
    mountoptions: Optional[str] = field(default=None)

    
    def mount(self):
        """ 
            Mount the partition to the specified mountpoint  
        """
        # Creates the mountpoint directory if it doesn't exist.
        if not self.mountpoint:
            raise Exception("Invalid mountpoint")

        Path(self.mountpoint).mkdir(parents=True, exist_ok=True)
        return Command('mount', args=[self.devpath, self.mountpoint])()
    
    def umount(self, check_returncode = True):
        """
            Unmount the partition.
        """
        return Command('umount', args=[self.devpath], check_returncode=check_returncode)()

    @abstractmethod
    def format(self):
        """ Format the filesystem"""

@dataclass
class Btrfs(FileSystem):
    subvolumes: list[dict] = field(default=None)

    def create_subvolumes(self):
        if not self.subvolumes:
            raise Exception("No subvolumes")

        super().mount()
        try:
            for subvol in self.subvolumes:
                csubvol_args = ['sub', 'cr', f'{self.mountpoint}/{subvol["name"]}']
                Command('btrfs', args=csubvol_args, cwd=self.mountpoint)()
        except Exception as e:
            raise e
        finally:
            super().umount()
    
    def mount(self):
        for subvol in self.subvolumes:
            args = ['-o', f'{self.mountoptions},subvol={subvol["name"]}', self.devpath, subvol["mountpoint"]]
            Path(subvol["mountpoint"]).mkdir(parents=True, exist_ok=True)
            Command('mount', args=args)()

    def format(self):
        if self.label:
            args = [f'-L {self.label}', self.devpath]
        else:
            args = [self.devpath]

        if self.force_format:
            args = ['-f'] + args

        Command('mkfs.btrfs', args=args)()
        self.create_subvolumes()


class VFat(FileSystem):
    def format(self):
        if self.label:
            args = ['-F 32',f'-n {self.label}', self.devpath]
        else:
            args = ['-F 32',self.devpath]

        return Command('mkfs.vfat', args=args, shell=True)()

class Xfs(FileSystem):
    def format(self):
        if self.label:
            args = [f'-L {self.label}', self.devpath]
        else:
            args = [self.devpath]

        if self.force_format:
            args = ['-f'] + args

        return Command('mkfs.xfs', args=args, shell=True)()


class Ext4(FileSystem):
    def format(self):
        if self.label:
            args = [f'-L {self.label}', self.devpath]
        else:
            args = [self.devpath]

        if self.force_format:
            args = ['-F'] + args

        cmd = Command('mkfs.ext4', args=args, shell=True)
        return cmd()
        
