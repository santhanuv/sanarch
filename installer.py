import argparse

#Parse the CLI Aguments 
def argument_parsing():
    yes = False
    parser = argparse.ArgumentParser()
    #parser.add_argument("mode", help="Select the mode of install.")
    parser.add_argument('df', help="Sepicify the file contaning dependency information for installation.")
    parser.add_argument("pf", help="Specify the file that contains partitioning information.")
    parser.add_argument('-y', '--yes', help="Give yes to all Y to all confirmations.", 
    action="store_true")
    args = parser.parse_args()
    
    if args.yes:
        yes = args.yes
    
    return (args.df, args.pf, yes)


#Installing dependencies... This will only work if the internet connection is fine.
def install_deps(deps_file):
    import json
    from subprocess import Popen, PIPE

    with open(deps_file) as f:
        data = f.read()
        deps = json.loads(data)

    #Getting the deps dictionary from the dictionary got from file.
    deps = deps['deps']

    print('Installing Dependencies...')

    proc = Popen(f'pacman -Syy', shell=True, stdout=PIPE, stderr=PIPE)
    proc.communicate()

    #Refresh package Database
    if proc.returncode != 0:
        return [1, '[ERR]Unable to refresh package database.']

    #Install with packman
    for pac_dep in deps['pacman']:
        proc = Popen(f'pacman -S --noconfirm {pac_dep}', shell=True, stdout=PIPE, stderr=PIPE)
        proc.communicate()[1]

        if proc.returncode != 0:
            return [2, f'[ERR]Unable to Download {pac_dep}. Download Manually and Continue.']

    #Install with pip
    for pip_dep in deps['pip']:
        proc = Popen(f'pip install {pip_dep}', shell=True, stdout=PIPE, stdin=PIPE)
        proc.communicate()[1]

        if proc.returncode != 0:
            return [3, f'[ERR]Unable to Install {pip_dep}']
    
    return [0, '[OK]Dependencies Installed Succesfully.']

## Parse the arguments given to the program
DEP_FILE, PART_FILE, DEFAULT = argument_parsing()

#Installing dependencies
rc, msg = install_deps(DEP_FILE)
print(msg)
if rc != 0:
    exit(2)

import functions, classes
import sys


# Checking IF the system booted in UEFI mode
EFI_BOOT = functions.verify_efi_boot()
if EFI_BOOT != True:
    print("[WARNING]: Boot Mode is not EFI")
else:
    print("[OK]Boot Mode is EFI")



# Starting to Install Arch Linux.

## Check Internet Connection.
# Returns a list with status and msg.
status, msg = classes.Ping('archlinux.org').ping()
print(msg)
if status != True:
    sys.exit(1)


# Update system clock
status, msg = functions.update_sys_clock()
print(msg)
if status != 0:
    exit(3)


#Create Partition
part_stat = classes.PartitionMaker(PART_FILE, DEFAULT).partition()
if part_stat == -1:
    exit(-1)
elif part_stat != 0:
    exit(4 + part_stat)
