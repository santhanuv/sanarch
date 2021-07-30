import argparse, sys, time, classes
from subprocess import Popen, PIPE
from multiprocessing import Queue


"""
    Contains the functions to Install Arch Linux.
"""


# Queue for writing for stdout.
# Thread and process safe way to print to the output.
que = Queue()

#Parse the CLI Aguments 
def argument_parsing():
    
    """
        This functions get the parse the arguments given to the program by the user.
        
        Arguments Needed:
            1. File containing partition Information.
            2. File containing configuration Information.
        
        Optional Arguments:
            1. No confirmation(Default to yes for all queries.)

    """

    yes = False
    parser = argparse.ArgumentParser()
    #parser.add_argument("mode", help="Select the mode of install.")
    parser.add_argument("pf", help="Specify the file that contains partitioning information.")
    parser.add_argument("cf", help="Specify the file that contains Configurations.")
    parser.add_argument('-y', '--yes', help="Give yes to all Y to all confirmations.", 
    action="store_true")
    args = parser.parse_args()
    
    if args.yes:
        yes = args.yes
    
    return (args.pf, args.cf, yes)

def intialize_install(PART_FILE, CONF_FILE, DEFAULT):

    """
        This functions set ArchInstaller class with needed information.
    """

    classes.ArchInstaller.set_default(DEFAULT)
    classes.ArchInstaller.set_files(PART_FILE, CONF_FILE)
    classes.ArchInstaller.set_queue(que)
    classes.ArchInstaller.set_run_state(True)



def dequeue(p1, p2):

    """
        To print the value in the queue from the multiprocessing module to stdout.

        A queue is implemented to write to stdout inorder to make it thread and process safe.
        The queue in the multiprocessing module is both process and thread safe.
        The functions and methods that need to write to stout enqueue the msg to the que and a 
        another thread is used to print the enqueued value to the stdout. The value is dequeued before printing.
    """

    while classes.ArchInstaller.run_state:
        try:
            data = que.get_nowait()
            sys.stdout.write(data)
            sys.stdout.flush()
        except:
            pass

def ping():

    """
        This function Check the internet connection by pinging archlinux.org.
    """

    try:
        classes.Ping.ping('archlinux.org')
        que.put_nowait('[ OK ] Internet Connection Checked.\n')
        time.sleep(0.01)
    except classes.ArchException as pingException:
        print([pingException.msg])
        sys.exit(1)


def partition():

    """
        Partitions the Disk.
    """

    try:
        classes.Command.verify_efi_boot()
        classes.SysClockUpdator().update_sys_clock()
        classes.PartitionMaker().partition()
    except classes.ArchException as e:
        print(e.msg)
        sys.exit(e.return_code)


def install():
    """
        Install the Arch os to the system.
    """
    try:
        classes.Command.pacstrap()
        classes.Command.pacman()
        classes.Command.genfstab(uuid=True)
        classes.Command.arch_config()
        
        if classes.ArchInstaller.get_is_btrfs():
            classes.Command.mkinitcpio()
        
        classes.BootLoader.inst_grub()

        try:
            classes.Command.passwd('root')
        except classes.ArchException as e:
            print(e.msg)
        
        try:
            classes.Command.user_add()
        except:
            print(e.msg)
        
        classes.enable_services()
        classes.Mounter.umount(None, umall=True)
        print('Installation Completed Successfully. Please Reboot :)')
    
    except classes.ArchException as e:
        print(e.msg)
        sys.exit(e.return_code)
    finally:
        classes.ArchInstaller.set_run_state(False)







