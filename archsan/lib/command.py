import subprocess

from dataclasses import dataclass, field
from typing import Optional
from lib.exceptions import CommandError
from typing import Union, TextIO
 
@dataclass
class Command:
    ROOT_PATH = "/mnt"

    """
        A base class to run linux commands

        Usage
        ----
        Command(name, args = [arguments], shell)

        If shell is true, the command will be executed with shell

        Use the execute method to run the command or cmd_instance()
        --

    """
    name: str
    args:Optional[list] = field(default_factory=list)
    shell:bool = field(default=False)
    capture_output: bool = field(default=True)
    check_returncode: bool = field(default=True)
    cwd:str = field(default=None)
    stdout: Union[TextIO, int] = field(default=None)
    stderr: Union[TextIO, int] = field(default=None)
    stdin: Union[TextIO, int] = field(default=None)
    chroot: bool = field(default=False)

    def __post_init__(self):
        if self.stdout or self.stderr:
            self.capture_output = False
        
        if self.chroot:
            if self.cwd:
                raise Exception("Can't set cwd and chroot at the same time.")
            
            self.cwd = self.ROOT_PATH

    @property
    def cmd(self):
        return [self.name] + self.args
    
    @property
    def cmd_str(self):
        arg_str = " ".join(self.args)
        return f'{self.name} {arg_str}'

    def append_args(self, str):
        self.args.append(str)
    
    def execute(self, input = None, arch_chroot=False):
        if arch_chroot:
            if not self.args:
                self.args = []
            
            program_name = self.name
            self.args.insert(0, self.name)
            self.name = "arch-chroot"
            self.args.insert(0, "/mnt")
        else:
            # saving to name because when the command is executed with same instance name is changed to arch-chroot
            program_name = self.name

        try:
            if self.shell == False:
                cp = subprocess.run(
                    self.cmd, capture_output=self.capture_output, text=True, cwd=self.cwd,stdout=self.stdout, 
                    stderr=self.stderr, stdin=self.stdin,input=input)
            else:
                cp = subprocess.run(
                    self.cmd_str, shell=True, capture_output=self.capture_output, text=True, 
                    stdout=self.stdout, stderr=self.stderr, stdin=self.stdin, cwd=self.cwd, input=input)

            if cp != None and self.check_returncode:
                cp.check_returncode()
        except Exception as e:
            if cp is not None:
                raise CommandError(msg=cp.stderr, cmd=self.cmd_str, return_code=cp.returncode)
            else:
                raise CommandError(msg=e, cmd=self.cmd_str, return_code=-1)

        finally:
            self.name = program_name

        return cp
        
    def __call__(self, input = None, arch_chroot=False):
        return self.execute(input=input, arch_chroot=arch_chroot)