from subprocess import PIPE
from dataclasses import dataclass, field
from lib.command import Command

@dataclass
class Pacman:
    arch_chroot: bool = field(default=True)
    pacman: Command = field(default=None, init=False)

    def __post_init__(self):
        self.pacman = Command(name="pacman", capture_output=False, stderr=PIPE)

    def __empty_args(self):
        self.pacman.args = []

    def install(self, packages = None):
        if not packages:
            packages = []

        args = ["-S", "--noconfirm"] + packages
        self.pacman.args = args

        self.pacman(arch_chroot=self.arch_chroot)
        self.__empty_args()

    def refresh_db(self, force = False):
        if not force:
            self.pacman.args = ["-Sy"]
        else:
            self.pacman.args = ["-Syy"]
        
        self.pacman(arch_chroot=self.arch_chroot)
        self.__empty_args()

    def setup_parallel_download(self, parallel_downloads = 1, arch_chroot = True):
        if arch_chroot:
            file = "/mnt/etc/pacman.conf"
        else:
            file = "/etc/pacman.conf"
        
        with open(file, "r") as conf_file:
            lines = conf_file.readlines()
        
        for num,line in enumerate(lines):
            if "ParallelDownloads" in line:
                lines[num] = f"ParallelDownloads = {parallel_downloads}\n"
        
        with open(file, "w") as conf_file:
            conf_file.writelines(lines)

