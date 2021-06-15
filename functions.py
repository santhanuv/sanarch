import subprocess, re, argparse
from subprocess import Popen, PIPE
from progress.spinner import Spinner
from threading import Thread
import classes
import json



## Install Dependencies

## Check the system booted in UEFI Mode
# Returns True in EFI Mode and False in Legacy Mode
def verify_efi_boot():
    proc = Popen(['ls', '/sys/firmware/efi/efivars'], stdout=PIPE, stderr=PIPE, text=True)
    stdout = proc.communicate()[0]
    if len(stdout) > 2:
        return True
    return False



## Update the system clock
def update_sys_clock():
    return classes.SysClockUpdator().update_sys_clock()


