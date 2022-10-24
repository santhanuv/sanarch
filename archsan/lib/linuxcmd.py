from lib.command import Command, CommandError
from lib import logger
from pathlib import Path

def lsblk(args = None, shell = False, input = None):
    # Constants for excluding loop and rom devices
    MAJOR_LOOP = 7
    MAJOR_ROM = 11
    
    if not args:
        args = []

    cmd = Command('lsblk', args=[f'-e {MAJOR_LOOP},{MAJOR_ROM}'] + args, shell=shell)
    res = cmd(input = input)

    return res

def lsblk_json(output = None, device = None):
    default = 'NAME,MODEL,VENDOR,TYPE,PATH,SIZE,MOUNTPOINT,PARTFLAGS,PARTLABEL,PARTTYPENAME,PARTUUID,FSTYPE,FSAVAIL,PATH'
    
    if output:
        output = f'{default},{output}'
    else:
        output = default

    if device:
        return lsblk(args=['--json', f'--output {output}', f'{device}'], shell=True)
    else:
        return lsblk(args=['--json', f'--output {output}'], shell=True)

def wipefs(device, args = None, shell = False, input = None):
    if args:
        args = ['--all', f'{device}'] + args
    else:
        args = ['--all', f'{device}']

    cmd = Command('wipefs', args=args, shell=shell)
    return cmd(input)

def sgdisk(device, endalign=True, args = None, shell = False, input = None):
    if not args:
        args = []

    if endalign:
        args = ['-I'] + args
    
    args += [device]
    cmd = Command('sgdisk', args=args, shell=shell)
    return cmd(input)

def awk(args: list = None, shell = False, input = None):
    if not args:
        raise Exception("awk need arguments")
    
    cmd = Command('awk',args=args, shell=shell)
    return cmd(input=input)

def get_avail_space(device):
    sg_res = sgdisk(device, endalign=False, args=[f'-p'])

    awk_pattern = f"'/free space/ {{print $7, $8}}'"
    awk_res = awk(args=[awk_pattern], shell=True, input=sg_res.stdout)

    size = ''
    if awk_res.stdout:
        size = awk_res.stdout[1:-2]

    return size

def mount(device, mountpoint):
    cmd = Command("mount", args=[device, mountpoint])
    return cmd()

def umount_all():
    cmd = Command("umount", args=['-a'], check_returncode=False)
    return cmd()


def packstrap(packages):
    args = ['/mnt'] + packages
    return Command('pacstrap', args=args, capture_output=False)()


def nproc():
    cp = Command("nproc")()
    cpus = int(cp.stdout)
    return cpus

def genfstab(fstab_path): 
    pass


def passwd(*, user = None, password = None, arch_chroot = True):
    # Log
    if user:
        input = f"{user}:{password}"
    else:
        # Sets password for the root user
        input = f"root:{password}"
    
    return Command("chpasswd", capture_output=False)(input=input,arch_chroot=arch_chroot)
        


def useradd(name, create_home = True, arch_chroot = True):
    # Log
    if not name:
        raise Exception("Invalid name for user")
    
    print("Creating the user:", name)
    if create_home:
        args = ['-m', f'{name}']
    else:
        args = [f'{name}']

    return Command("useradd", args=args)(arch_chroot=arch_chroot)

def user_add_groups(user, groups: list, arch_chroot = True):
    # Log
    if not user or not groups:
        raise Exception("Invalid user or groups")
    
    groups_str = ",".join(groups)
    args = ["-aG", groups_str, user]

    return Command("usermod", args=args, shell=True)(arch_chroot=arch_chroot)

def enable_sevice(service, arch_chroot = True):
    # Log
    if not service:
        raise Exception("Invalid Service")

    return Command(name="systemctl", args=["enable", service])(arch_chroot=arch_chroot)
