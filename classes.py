from subprocess import Popen, PIPE
from threading import Thread
import asyncio, subprocess
import re, json, sys, time

"""
    Contains the classes needed for the Arch Linux installation.
"""


class ArchInstaller():

    """
        Contains Information about the installation and static methods to set those informations.
    """
    
    PART_FILE = None
    CONFIG_FILE = None
    DEFAULT = False
    PART_INFO = []
    CONFIG_INFO = {}
    IS_BTRFS = True
    que = None
    run_state = False
    internet_state = False

    @staticmethod
    def set_run_state(val):
        
        """
            Set the running state of the Installation.

            True means Running.
            False means Stopped.
        """

        ArchInstaller.run_state = val
    
    @staticmethod
    def set_queue(que):
        
        """
            Set the queue needed for installation.
        """
        ArchInstaller.que = que

    @staticmethod
    def set_files(part_file, config_file):
        
        """
            Set files needed for installation.
        """

        ArchInstaller.PART_FILE = part_file
        ArchInstaller.CONFIG_FILE = config_file
        ArchInstaller.set_part_info()
        ArchInstaller.set_config_info()

    @staticmethod
    def set_default(defalut):
        
        """
            This functions set the default answer to confirmation in installation.

            Setting this to true the installer will assume yes to all confirmations needed.
        """

        ArchInstaller.DEFAULT = defalut

    @staticmethod
    def set_part_info():
        
        """
            Set the partition information from the partition file specified in this class.
        """

        with open(ArchInstaller.PART_FILE) as f:
            data = f.read()
            ArchInstaller.PART_INFO = json.loads(data)

    @staticmethod
    def set_config_info():
        
        """
            Set the configuration information from the configuration file specified in this class.
        """

        with open(ArchInstaller.CONFIG_FILE) as f:
            data = f.read()
            ArchInstaller.CONFIG_INFO = json.loads(data)

    @staticmethod
    def get_part_info():
        
        """
            Return the partition information set in this class.
        """
        return ArchInstaller.PART_INFO

    @staticmethod
    def get_config_info():

        """
            Return the configuration information set in this class.
        """

        return ArchInstaller.CONFIG_INFO

    @staticmethod
    def get_default():
        
        """
            Returns the default value to set this class for confirmations.
        """

        return ArchInstaller.DEFAULT

    @staticmethod
    def set_is_btrfs(val):
        
        """
            Set the if the file partitions contain btrfs file system.

            True means there is btrfs file system.
        """

        ArchInstaller.IS_BTRFS = val

    @staticmethod
    def get_is_btrfs():
        
        """
            Returns the value of IS_BTRFS variable in this class.
        """

        return ArchInstaller.IS_BTRFS

    @staticmethod
    def set_internet_state(val):

        """
            Setting this to True tell other classes and functions that the internet 
            connection is ok.
        """

        ArchInstaller.internet_state = val
    
    @staticmethod
    def get_internet_state():

        """
            Returns the current internet status that has set by the Ping class.
        """

        return ArchInstaller.internet_state


class Command():
    
    """
        This class contains the general commands and commands needed for installing 
        Arch on the system.
    """

    chroot = 'arch-chroot' 
    chroot_loc = '/mnt'

    @staticmethod
    def verify_efi_boot():

        """
            Verify the if the system is booted in EFI mode.
        """

        proc = Popen(['ls', '/sys/firmware/efi/efivars'], stdout=PIPE, stderr=PIPE, text=True)
        stdout = proc.communicate()[0]
        if len(stdout) > 2:
            ArchInstaller.que.put_nowait('[ OK ] System Successfully Booted in EFI.\n')
        else:
            raise ArchException('[ ERR ] System is not Booted in EFI. Please Boot in EFI MODE',1)

    @staticmethod
    def mkdir(dir = None):

        """
            Create directory specified as argument.

            Argument should be a string and should contain the path to the directory.
        """

        if dir is None:
            return 1

        proc = Popen(['mkdir', '-p', dir], stdout=PIPE, stderr=PIPE, text=True)
        proc.communicate()
        return proc.returncode

    @staticmethod
    def pacstrap():

        """
            Update the the essential packages needed for installing Arch.

            Uses the arch pacstrap to install the base and other packages.
        """

        spinner = CSpinner('Installing Essential Packages ',delay_time=0.5)
        spinner.start()
        #ArchInstaller.que.put_nowait('Installing Essential Packages...')
        pacs = ArchInstaller.get_config_info()['pacstrap']
        
        if pacs is None:
            spinner.stop()
            return 0
        
        pac_command = 'base '
        for pac in pacs:
            pac_command += pac + ' '
        
        command = 'pacstrap /mnt ' + pac_command

        proc = Popen(command, stdout=PIPE, stderr=PIPE, stdin=PIPE, text=True, shell=True)
        proc.communicate('y\n')

        spinner.stop()
        ArchInstaller.que.put_nowait('Done packstrap...\n')
        return 0

    @staticmethod
    def pacman():

        """
            Install the packages using Arch pacman.
        """

        pacs = ArchInstaller.get_config_info()['pacman']
        spinner = CSpinner('Installing Packages ',delay_time=0.5)
        spinner.start()
        #ArchInstaller.que.put_nowait('Installing Packages...')

        if pacs is None:
            spinner.stop()
            return
            
        pac_command = ''
        for pac in pacs:
            pac_command += pac + ' '
        
        command = f'{Command.chroot} {Command.chroot_loc} pacman -S --noconfirm ' + pac_command
        proc = Popen(command, stdout=PIPE, stderr=PIPE, text=True, shell=True)
        proc.communicate()
        
        #Raise Exception
        if proc.returncode != 0:
            spinner.stop()
            raise ArchException('Unable to install Packages Using pacman', 1)
        
        spinner.stop()
        ArchInstaller.que.put_nowait('Done Installing packages...\n')
        return 0

    @staticmethod
    def set_mirrorlist():
        
        """
            Set Mirror list.

            Don't use this now.(Buggy)
        """

        proc = Popen(['pacman','--noconfirm','-S','reflector'],stdout=PIPE, stderr=PIPE)
        proc.communicate()
        if proc.returncode != 0:
            return (proc.returncode, '[ERR]Unable to install Reflector')
        
        proc = Popen(['reflector','--latest', '10', '--sort', 
            'rate', '--save', '/etc/pacman.d/mirrorlist'], stderr=PIPE)
        err = proc.communicate()[1]
        
        if proc.returncode == 0:
            return (proc.returncode, '[OK]Mirror List set')
        else:
            return (proc.returncode, err)

    @staticmethod
    def genfstab(uuid=True):

        """
            Generate the fstab to /etc/fstab file.

            Settings uuid to True will use UUID to generate fstab file(Default is True).
        """

        if uuid:
            proc = Popen('genfstab -U /mnt >> /mnt/etc/fstab', stdout=PIPE, stderr=PIPE,text=True, shell=True)
        else:
            proc = Popen('genfstab mnt >> /mnt/etc/fstab', stdout=PIPE, stderr=PIPE,text=True, shell=True)

        proc.communicate()
        
        if proc.returncode != 0:
            raise ArchException('[ ERR ] Unable to Generate fstab.', 1)
        
        return proc.returncode

    @staticmethod
    def enable_services():
        """
            Enable Systemd services.
        """
        services = ArchInstaller.get_config_info()['services']
        for service in services:
            scommand = f'{Command.chroot} {Command.chroot_loc} systemctl enable {service}'
            proc = Popen(scommand, text=True, stdout=PIPE, stderr=PIPE, shell=True)
            proc.communicate()

            if proc.returncode != 0:
                ArchInstaller.que.put_nowait(f'[ ERR] Unable to enable {service}\nCheck if the service is installed or the name is correct!')
            else:
                ArchInstaller.que.put_nowait(f'[ OK ] Successfully enabled {service}\n')


    @staticmethod
    def arch_config():
        
        """
            Configures the Arch system.
        """

        ArchInstaller.que.put_nowait('configuring')
        config = ArchInstaller.get_config_info()['settings']

        zone = '/usr/share/zoneinfo/' + config['zone']
        proc = Popen([Command.chroot,Command.chroot_loc, 'ln', '-sf', zone, '/etc/localtime'],
        text= True)
        err = proc.communicate()[1]

        if proc.returncode != 0:
            raise ArchException(f'Unable to set Zone info\n{err}', 1)
        
        proc = Popen([Command.chroot, Command.chroot_loc, 'hwclock', '--systohc'], text=True)
        err = proc.communicate()[1]

        if proc.returncode != 0:
            raise ArchException(f'Unable to set Hardware Clock\n{err}', 2)

        with open('/mnt/etc/locale.gen', 'a') as f:
            for locale in config['locale']:
                f.write(locale + '\n')

        proc = Popen([Command.chroot, Command.chroot_loc, 'locale-gen'], text=True)
        err = proc.communicate()[1]

        if proc.returncode != 0:
            raise ArchException(f'Unable to Generate Locale\n{err}', 3)

        with open('/mnt/etc/locale.conf', 'w') as f:
            lang = config['lang']
            f.write(f'LANG={lang}\n')

        if config['keymap'] != '' or not None:
            with open('/mnt/etc/vconsole.conf', 'w') as f:
                keymap = config['keymap']
                f.write(f'KEYMAP={keymap}\n')

        hostname = config['hostname']
        with open('/mnt/etc/hostname', 'w') as f:
            f.write(hostname)
            f.write('\n')

        with open('/mnt/etc/hosts', 'w') as f:
            f.write(f'\n127.0.0.1\tlocalhost\n::1\tlocalhost\n127.0.1.1\t{hostname}.localdomain\t {hostname}')
            f.write('\n')


    @staticmethod
    def mkinitcpio():

        """
            Recreates the initramfs with configurations in mkinitcpio.conf

            FOR BTRFS ONLY
        """

        loc = Command.chroot_loc
        with open(f'{loc}/etc/mkinitcpio.conf', 'r') as fr:
            with open(f'{loc}/etc/mkinitcpio.conf.bak', 'w') as fw:
                for line in fr:
                    if not line.startswith('#'):
                        if line.find('MODULES') != -1:
                            modules = line[line.find('(')+1:line.find(')')].strip()
                            
                            if modules != '':
                                new_modules = f'MODULES=({modules} btrfs)'
                            else:
                                new_modules = f'MODULES=(btrfs)'
                            
                            fw.write(new_modules + '\n')
                            continue
                    fw.write(line)

        proc = Popen(['mv', '/mnt/etc/mkinitcpio.conf.bak', '/mnt/etc/mkinitcpio.conf'], 
        text=True)
        proc.communicate()

        proc = Popen([Command.chroot, Command.chroot_loc, 'mkinitcpio', '-p', 'linux'],
        text=True)
        err = proc.communicate()[1]

        if proc.returncode != 0:
            raise ArchException(f'mkinitcpio Error\n{err}', 4)

    @staticmethod
    def passwd(user):

        """
            Set password for the user.
        """

        chroot = Command.chroot
        loc = Command.chroot_loc

        name = user
        if user == 'root':
            ArchInstaller.que.put_nowait(f'Enter root password:\n')
            user = ''
        else:
            ArchInstaller.que.put_nowait(f'Enter the new password for {user}:\n')
        
        proc = Popen(f'{chroot} {loc} passwd ' + user, shell=True, text=True)
        proc.communicate()

        if proc.returncode != 0:
            raise ArchException(f'Unable to set {name} password', 1)

        return 0

    @staticmethod
    def user_add(name=None, groups=None):

        """
            Create New user and set password.

            If no name and groups are specified as arguments the information from the configuration
            file will be used.
        """

        chroot = Command.chroot
        loc = Command.chroot_loc

        if name is None:
            settings = ArchInstaller.get_config_info()['settings']
            name = settings['user name']
            groups = settings['user groups']
            if name is None or name == '':
                name = input('Enter user Name: ')
                groups = input('Enter the groups: ')
        
        command = f'{chroot} {loc} useradd -mG {groups} {name}'
        proc = Popen(command, shell=True, text=True)
        proc.communicate()

        if proc.returncode != 0:
            raise ArchException('Unable to add User', 1)
        
        proc = Popen(f'{chroot} {loc} EDITOR=vim visudo', stdout=PIPE, stderr=PIPE, stdin=PIPE,
        text=True, shell=True)
        proc.communicate(':q!')

        loc = Command.chroot_loc
        with open(f'{loc}/etc/sudoers', 'r') as fr:
            with open(f'{loc}/etc/sudoers.temp', 'w') as fw:
                for line in fr:
                    if line.find('# %wheel ALL=(ALL) ALL') != -1:
                        newline = line.replace('# ', '')
                        fw.write(newline)
                    else:
                        fw.write(line)

        proc = Popen(['mv', f'{loc}/etc/sudoers.temp', f'{loc}/etc/sudoers'], 
        text=True)
        proc.communicate()

        if proc.returncode != 0:
            raise ArchException('Unable to edit sudoers', 2)
        
        try:
            Command.passwd(name)
        except ArchException as e:
            raise ArchException('Unable set user password', 3)
        
        return 0
                

class BootLoader():
    
    """
        Installs a bootloader.
    """

    @staticmethod
    def inst_grub():

        """
            Installs the grub bootloader.
        """

        chroot = Command.chroot
        chroot_loc = Command.chroot_loc
        part_info = ArchInstaller.get_part_info()

        for dev in part_info:
            for part in dev['partitions']:
                if part['part name'] == 'efi':
                    mnt = part['mount point']
                    mnt = mnt.replace('/mnt', '')
                    break

        proc = Popen(
            f'{chroot} {chroot_loc} grub-install --target=x86_64-efi --efi-directory={mnt} --bootloader-id=GRUB', shell=True, text=True)
        proc.communicate()

        proc = Popen(f'{chroot} {chroot_loc} grub-mkconfig -o /boot/grub/grub.cfg', shell=True,
        text=True)
        proc.communicate()

        return proc.returncode


class CSpinner():

    """
        A custom spinner for showing Installations and Downloads.
    """

    #SPIN_POSITIONS = ['|', '/', '-', '\\','|', '/' , '-', '\\']
    SPIN_POSITIONS = ['*_*','*_-','-_*']
    
    def __init__(self, prompt, no_times=0, delay_time=1, isQueue=True):
        
        """
            Constructor for the custom spinner
        """

        self.pos = 0
        self.pos_len = len(self.SPIN_POSITIONS)
        self.state = False
        self.prompt = prompt
        self.isQueue = isQueue
        self.no_times = no_times
        self.delay_time = delay_time
        self.t = Thread(target=self.spin, daemon=True)


    def set_times(self, no_times=1, delay_time=1):
        
        """
            Set the no_times and delay_time instance variable.

            This is used inform the spinner to spin how many times(no_times) and
            the delay between each spin(delay_time).
        """

        self.no_times = no_times
        self.delay_time = delay_time

    def next_toque(self):

        """
            Enqueue the next spin position to the queue in the ArchInstaller class.
        """

        if self.pos < self.pos_len:
            ArchInstaller.que.put_nowait(self.SPIN_POSITIONS[self.pos]+ ' ')
            ArchInstaller.que.put_nowait('\b\b\b\b')
            self.pos += 1
        else:
            self.pos = 0
            self.next_toque()

    def next(self):
        
        """
            Print the next spin postition.
        """

        if self.pos < self.pos_len:
            sys.stdout.write(self.SPIN_POSITIONS[self.pos]+' ')
            sys.stdout.flush()
            sys.stdout.write('\b\b\b\b')
            self.pos += 1
        else:
            self.pos = 0
            self.next()

    def stop(self):
        
        """
            Stop the spinner.
        """

        self.state = False
        self.t.join()
        if not self.isQueue:
            print()
        else:
            ArchInstaller.que.put_nowait('\n')
        return
    
    def start(self):

        """
            Start the thread for spinner.
        """

        self.state = True
        if not self.isQueue:
            print(self.prompt, end=' ')
        else:
            ArchInstaller.que.put_nowait(self.prompt)
        self.t.start()


    def spin(self):
        
        """
            Spins the spinner for a specified amount of time or till the state instance
            variable become false.

            State instance variable can be set false using stop method.
        """

        counter = 0
        while True:
            if self.no_times > 0 and counter > self.no_times:
                break
            if self.isQueue:
                self.next_toque()
            else:
                self.next()
            if self.state:
                time.sleep(self.delay_time)
            else:
                break
        return
        

class Ping():

    """
        Class for Cheking the internet connection.

        Ping the given site.
    """
    
    @staticmethod
    def ping(site):
        
        """
            Ping the specified site.
        """

        #spinner = CSpinner('Checking Internet Connection ', 99, 0.3, True)
        #ArchInstaller.que.put_nowait('Checking internet Connnection...\n')
        #spinner.start()
        status = False
        proc = Popen(['ping', '-c 5',site], stdout=PIPE, stderr=PIPE, text=True)
        try:
            proc.communicate(timeout=10)
        except subprocess.TimeoutExpired:
            proc.kill()
            msg = proc.communicate()[1]
            msg += '[Error] No internet connection'
            status = False

        if proc.returncode == 0:
            status = True
            msg = '[OK]Internet Connection Checked'
        
        #spinner.stop()
        #print(msg)
        if not status:
            raise Exception('[ ERR ] Check your Internet Connection.', 1)

        
        ArchInstaller.set_internet_state(True)


class SysClockUpdator():

    """
        Update the system clock.
    """

    ALREADY_ACTIVE = '[ OK ] System Clock was Already Active.'
    SETTING_CLOCK = '[ WAIT ] Setting the System Clock...'
    ERR_STATUS = '[ ERR ] Unable to find System Clock Status.'
    OK_UPDATE = '[ OK ] System Clock Updated.'
    ERR_UPDATE = '[ ERR ] Unable to Update System Clock.'

    STATE_COMPLETED = 0
    STATE_INCOMPLETED = 1
    STATE_ERR = 2

    CURR_STATE = None

    @classmethod
    def check_status(cls):
        """
            Check the status for the system clock.
        """

        proc = Popen(['timedatectl', 'status'], stdout=PIPE, stdin=PIPE, text=True)
        out, err = proc.communicate()
    
        if proc.returncode != 0:
            status_msg = err + cls.ERR_STATUS
            cls.CURR_STATE = cls.STATE_ERR
            raise ArchException(status_msg, proc.returncode)
    
        re_out = re.search('.*NTP service:(.*$)', out, re.MULTILINE)
    
        # Return system call is active
        if re_out.group(1).strip().lower() != 'active':
            cls.CURR_STATE = cls.STATE_INCOMPLETED
        else:
            status_msg = cls.ALREADY_ACTIVE
            cls.CURR_STATE = cls.STATE_COMPLETED
            ArchInstaller.que.put_nowait(status_msg)
        
        return
    
    @classmethod
    def set_clock(cls):
        
        """
            Update the system clock.
        """

        proc = Popen(['timedatectl', 'set-ntp', 'true'], stdout=PIPE, stderr=PIPE, text=True)
        err = proc.communicate()[1]
        
        if proc.returncode != 0:
            msg = cls.ERR_UPDATE
            msg += err
            ArchInstaller.que.put_nowait(msg)
            raise ArchException(msg, proc.returncode)
        else:
            msg = cls.OK_UPDATE
            ArchInstaller.que.put_nowait(msg)
    
        return

    
    @classmethod
    def update_sys_clock(cls):

        """
            Checks status and updates the system clock if nessassory.
        """

        cls.check_status()
        if cls.CURR_STATE != cls.STATE_INCOMPLETED:
            return

        cls.set_clock()
        return
    

class Partitioner():

    """
        Create the partitions.
    """

    @classmethod
    def set_msg(cls, ERR_PARTITION, ERR_MBR, OK_SUCCESS):

        """
            Set the error messages and successs messages.
        """
        
        cls.ERR_PARTITION = ERR_PARTITION
        cls.ERR_MBR = ERR_MBR
        cls.OK_SUCCESS = OK_SUCCESS

    @staticmethod
    async def write_stdin(proc, command, endwith):

        """
            Reads the output from stdout and write to stdin.
        """

        out = await proc.stdout.read(10240)
        command = str.encode(command)
        out = out.decode('utf-8')
        if endwith and out.endswith(endwith) or not endwith:
            proc.stdin.write(command)
        else:
            command = command.decode('utf-8')
            return False
        
        return True

    @staticmethod
    async def create_partition(part_info):

        """
            Creates the partitions specified as arguments.

            This information is set in a file in JSON format.  
        """

        for dev in part_info:
            if dev['part table'].find('gpt') == -1:
                return Partitioner.ERR_MBR
            
            proc = await asyncio.create_subprocess_exec('gdisk', dev['name'], 
            stdin=asyncio.subprocess.PIPE,
            stdout=asyncio.subprocess.PIPE)

            if not await Partitioner.write_stdin(proc, 'o\n', None):
                return Partitioner.ERR_PARTITION
                
            if not await Partitioner.write_stdin(proc, 'Y\n', '(Y/N): '): 
                return Partitioner.ERR_PARTITION

            for partition in dev['partitions']:
                if not await Partitioner.write_stdin(proc, 'n\n', None):
                    return Partitioner.ERR_PARTITION
                
                if not await Partitioner.write_stdin(proc, f"{partition['part number']}\n" , ': '): 
                    return Partitioner.ERR_PARTITION

                if not await Partitioner.write_stdin(proc, '\n', ': '): 
                    return Partitioner.ERR_PARTITION
                
                if partition['size'] == '-':
                    size_string = '\n'
                else:
                    size_string = f"{partition['size']}\n"
                
                if not await Partitioner.write_stdin(proc, size_string, ': '): 
                    return Partitioner.ERR_PARTITION
                
                if not await Partitioner.write_stdin(proc, f"{partition['hex code']}\n", ': '): 
                    return Partitioner.ERR_PARTITION

            if not await Partitioner.write_stdin(proc, 'w\n', ': '):
                return Partitioner.ERR_PARTITION
            
            if not await Partitioner.write_stdin(proc, 'Y\n', '(Y/N): '):
                return Partitioner.ERR_PARTITION

            stderr = (await proc.communicate())[1]
            if stderr is not None:
                return Partitioner.ERR_PARTITION
            else:
                return Partitioner.OK_SUCCESS


class Formater():

    """
        Format the partitions created with a filesystem.
    """

    format_method = {
        'fat32': 'fat',
        'ext4': 'ext4',
        'btrfs': 'btrfs',
        'swap': 'swap'
    }

    @classmethod
    def set_msg(cls, OK_FORMAT, ERR_FORMAT, ERR_SUPPORT):
        
        """
            Set the error and success messages.
        """

        cls.OK_FORMAT = OK_FORMAT
        cls.ERR_FORMAT = ERR_FORMAT
        cls.ERR_SUPPORT = ERR_SUPPORT

    def format(self, part_info):

        """
            Format the partititons with the information given as argument.

            This information is set in a file in JSON format.
        """

        for devices in part_info:
            dev_name = devices['name']
            for partition in devices['partitions']:
                part_id = dev_name + partition['part number']
                func = getattr(self, self.format_method[partition['fs']], 'Invalid')

                if func == 'Invalid':
                    return Formater.ERR_SUPPORT
                

                if partition['fs'] in 'btrfs':
                    ArchInstaller.set_is_btrfs(True)
                    return_code = func(part_id, partition['subvolumes'], partition['mount point'])
                else:
                    return_code = func(part_id)

        if return_code != 0:
            return Formater.ERR_FORMAT
        else:
            return Formater.OK_FORMAT


    @staticmethod
    def format_exec(command_list):

        """
            Execute the format command given as argument.
        """

        proc = Popen(command_list, stdout=PIPE,stderr=PIPE, text=True)
        proc.communicate()
        return proc.returncode 

    @staticmethod
    def fat(part_id):
        
        """
            Format with FAT32 filesystem.
        """

        return Formater.format_exec(['mkfs.fat', '-F32', part_id])

    @staticmethod
    def ext4(part_id):

        """
            Format with ext4 filesystem.
        """

        return Formater.format_exec(['mkfs.ext4', part_id])
    
    @staticmethod
    def btrfs(part_id, subvolumes, mnt):

        """
            Format with btrfs filesystem.
        """

        format_stat = Formater.format_exec(['mkfs.btrfs', '-f', part_id])
        if format_stat != 0:
            return format_stat
        
        proc = Popen(['mount', part_id, mnt], stdout=PIPE, text=True)
        proc.communicate()

        if proc.returncode != 0:
            return proc.returncode
        
        for subvolume in subvolumes:
            if mnt.endswith('/'):
                sub_name = mnt + subvolume['name']
            else:
                sub_name = mnt + '/' + subvolume['name']

            proc = Popen(['btrfs', 'subvolume', 'create', sub_name], stdout=PIPE,
            text=True)
            proc.communicate()[0]
            if proc.returncode != 0:
                return proc.returncode
        
        Mounter.umount(mnt)

        return proc.returncode

    @staticmethod
    def swap(part_id):

        """
            Creates a swap filesystem partition.
        """

        res = Formater.format_exec(['mkswap', part_id])

        if res != 0:
            return res

        return Formater.format_exec(['swapon', part_id])


class Mounter():

    """
        Mounts the formated partitions in specified location.
    """

    ERR_MOUNT = None
    OK_MOUNT = None
    
    @classmethod
    def set_msgs(cls, ERR_MOUNT, OK_MOUNT):

        """
            Set the error and succcess messages.
        """

        cls.ERR_MOUNT = ERR_MOUNT
        cls.OK_MOUNT = OK_MOUNT


    @staticmethod
    def mount(part_id, loc, options=None):

        """
            Mount the partitions with partition id, location and options specified as 
            arguments. 
        """

        if options is not None:
            proc = Popen(['mount', '-o', options, part_id, loc], 
            stdout=PIPE, text=True)
            proc.communicate()
            return proc.returncode
        else:
            proc = Popen(['mount', part_id, loc], stdout=PIPE, text=True)
            proc.communicate()
            return proc.returncode

    @staticmethod
    def btrfs_mount(subvolumes, options, part_id, loc):

        """
            Mount a btrfs filesystem partition.

            Mount all the subvolumes in specified locations with the options specified.
        """

        if subvolumes is None:
            return 2
        
        for subvol in subvolumes:
            loc = subvol['mount point']
            Command.mkdir(loc)
            options += f",subvol={subvol['name']}"

            res = Mounter.mount(part_id, loc, options)

            if res != 0:
                return res
        
        return 0

    
    @staticmethod
    def gen_mount(part_id, loc):

        """
            Mount general filesystem in the specified location.
        """

        Command.mkdir(loc)
        return Mounter.mount(part_id, loc)

    @staticmethod
    def mount_parts(part_info):

        """
            Mount all the partitions given as argument.

            This information should be set in a file in JSON format.
        """

        mounted = []
        unmount_parts = []
        for dev in part_info:
            part_name = dev['name']
            for partition in dev['partitions']:
                if partition['hex code'] == '8200' or partition['part name'] == 'swap':
                    continue
                part_id = part_name + partition['part number']
                loc = partition['mount point']
                options = partition['mount options']
                fs_type = partition['fs']

                if fs_type == 'btrfs':
                    subvolumes = partition['subvolumes']
                else:
                    subvolumes = None

                if partition['part name'] != 'root' and 'root' not in mounted:
                    unmount_parts.append(
                        {
                            "part_id": part_id,
                            "loc": loc,
                            "options": options,
                            "fs_type": fs_type,
                            "subvolumes": subvolumes
                        }
                    )
                    continue


                if options == '':
                    options = None
                
                if fs_type == 'btrfs':
                    res = Mounter.btrfs_mount(subvolumes, options, part_id, loc)
                else:
                    res = Mounter.gen_mount(part_id, loc)
                
                if res != 0:
                    return Mounter.ERR_MOUNT
        
        for unmount_part in unmount_parts:
            if unmount_part['fs_type'] == 'btrfs':
                res = Mounter.btrfs_mount(unmount_part['subvolumes'], 
                unmount_part['options'], unmount_part['part_id'], 
                unmount_part['loc'])
            else:
                res = Mounter.gen_mount(unmount_part['part_id'], unmount_part['loc'])
                
            if res != 0:
                return Mounter.ERR_MOUNT

        return Mounter.OK_MOUNT

    @staticmethod
    def umount(part_id, withRec=False, umall=False):

        """
            Umount the partitions
        """

        if not withRec and not umall:
            proc = Popen(['umount', part_id], stdout=PIPE, stdin=PIPE, 
            text=True)
            proc.communicate()
        elif withRec:
            proc = Popen(['umount', '-R', part_id], stdout=PIPE, stdin=PIPE, 
            text=True)
            proc.communicate()
        elif umall:
            proc = Popen(['umount', '-a'], stdout=PIPE, stderr=PIPE, text=True)
            proc.communicate()

        return proc.returncode
    
    @staticmethod
    def disable_swap(part_id):

        """
            Disable swap.
        """

        proc = Popen(['swapoff', part_id], stdout=PIPE, stderr=PIPE, text=True)
        proc.communicate()

        return proc.returncode

    @staticmethod
    def findmnt(part_id):

        """
            Find if a partition is mounted.

            If yes returns the location.
        """

        proc = Popen(['findmnt', part_id], stdout=PIPE, stdin=PIPE, text=True)
        out = proc.communicate()[0]

        return [proc.returncode, out]


class PartitionMaker():

    """
        Creates the partitions specified in the ArchInstaller class.
    """

    ERR_OPEN = '[ERR]Unable to open File.'
    ERR_CLOSE = '[ERR]Unable to close File.'
    ERR_FDISK = '[ERR]Unable to use fdisk.'
    #ERR_WRITE = '[ERR]Unable to write to File.'
    ERR_NO_PERMISSION = '[ERR]No permission To partition.'
    ERR_CONFIRM = '[ERR]Unable to get confirmation To partition.'
    ERR_PARTITION = '[ERROR]Unable to Create Partitions.'
    ERR_MBR = '[ERROR]MBR partition is not Available now.'
    WARN_PARTITION = '[WARNING] Partitioning will REMVOE ALL DATA.'
    #OK_WRITE = '[OK]Part Data has been Written Successfully.'
    OK_PART = '[OK]Partition has Successfully Created.'
    OK_FORMAT = '[OK]Disk Formated Successfully.'
    ERR_FORMAT = '[ERR]Disk Format Unsuccessfull.'
    ERR_SUPPORT = '[ERR]Format Type Not Supported.'
    ERR_MOUNT = '[ERR]Unable to Mount the Partition.'
    OK_MOUNT = '[OK]Partitions Mounted Successfully.'

    def __init__(self):
        
        """
            Constructor.
        """

        self.part_info = ArchInstaller.get_part_info()
        self.is_part = ArchInstaller.get_default()
        Partitioner.set_msg(
            ERR_PARTITION=PartitionMaker.ERR_PARTITION, 
            ERR_MBR=PartitionMaker.ERR_MBR,
            OK_SUCCESS=PartitionMaker.OK_PART
        )
        self.success_status = None
        Formater.set_msg( 
            PartitionMaker.OK_FORMAT,
            PartitionMaker.ERR_FORMAT,
            PartitionMaker.ERR_SUPPORT
        )
        Mounter.set_msgs(PartitionMaker.ERR_MOUNT, PartitionMaker.OK_MOUNT)
    

    def get_part_details(self):

        """
            Get the Deviece details from the system.

            THIS METHOD WILL BE CHANGED
        """

        proc = Popen(['fdisk' , '-l'], stdout=PIPE, stderr=PIPE, text=True)
        out, err = proc.communicate()

        if proc.returncode != 0:
            print(err + '\n' + PartitionMaker.ERR_FDISK)

            return 3
        
        if 'Permission denied' in out or 'Permission denied' in err:
            print(PartitionMaker.ERR_NO_PERMISSION)
            return 4
        
        dev_list_string = re.split('\n{3}', out, re.MULTILINE)

        devices = []

        for device in dev_list_string:
            dev = dict()
            dev['name'] = re.match('.*(/dev/(?!loop).*):', device, re.MULTILINE)
            dev['size'] = re.match('.*: (.*GiB),', device, re.MULTILINE)
            dev['model'] = re.search('^Disk model: (.*$)', device, re.MULTILINE)
            dev['type'] = re.search('.* typed: (.*$)', device, re.MULTILINE)
            dev['id'] = re.search('.* identifier: (.*$)', device, re.MULTILINE)
            tmp = re.split('\n{2}', device, re.MULTILINE)
            if len(tmp) >= 2 and 'Device' in tmp[1]:
                dev['partitions'] = tmp[1].strip()
            else:
                dev['partitions'] = None
            devices.append(dev)

        
        for device in devices:
            for key, val in device.items():
                if key == 'partition':
                    continue
                try:
                    device[key] = val.group(1).strip()
                except AttributeError:
                    pass

        return devices

    
    def tostr_part_device(self, devices):

        """
            Convert the device information given as argument to a string.

            The argument should be a string of objects.
        """

        part_dev_str = ''
        for device in devices:
            if device['name'] == None:
                continue
            for key, val in device.items():
                if key not in 'partitions':
                    part_dev_str += str(f'{key}:\t{val}\n')
                if 'partitions' in key:
                    part_dev_str += str('\nPartitions:\n\n')
                    part_dev_str += str(f"{device['partitions']}\n")
            
            part_dev_str += '\n'

        return part_dev_str

    def tostr_part_list(self, part_list):

        """
            Convert the partition list specified to a sring.
        """

        part_list_str = ''
        for part in  part_list:
            for key, val in part.items():
                part_list_str += str(f"\t{key}:\t{val}\n")
            
            part_list_str += '\n'
        
        return part_list_str

    def tostr_part_info(self, part_info):

        """
            conver the partition information specified to string.
        """

        part_info_str = ''

        for dev_info in part_info:
            for key, val in dev_info.items():
                if 'partitions' in key:
                    part_info_str += '\nPartitions: \n\n'
                    part_info_str += self.tostr_part_list(val)
                else:
                    part_info_str += str(f"{key} :\t{val}\n")
        
        part_info_str = part_info_str[:-2]
        return part_info_str


    def ask_confirmation(self):

        """
            Ask confimation from the user for partitiong.
        """

        #info_str = 'DEVICES AND PARTITIONS AVAILABLE: \n' \
        #+ self.tostr_part_device(cur_devices) + '\n' \
        #+ 'USING THE PARTITIONS: \n' \
        #+ self.tostr_part_info(part_info)

        question = 'Do YOU WANT TO CONTINUE WITH THIS CONFIGURATION ?(y/n)'

        sys.stdout.write("\x1b[2J\x1b[H")
        
        for dev in self.part_info:
            name = dev['name']
            label = dev['part table']
            print(f'DEVICE\t{name}\nPARTITION TABLE\t{label}')
            for part in dev['partitions']:
                part_id = name + part['part number']
                size = part['size'].replace('+', "")
                fs = part['fs']

                if fs != 'swap':
                    mnt = part['mount point']
                else:
                    mnt = ''
                
                mnt_options = part['mount options']

                if fs == 'btrfs':
                    subvols = part['subvolumes']
                else:
                    subvols = []

                print(f'\tPARTITION\t\tSIZE\tTYPE\t\tMOUNT POINT')
                print(f'\t{part_id}\t\t{size}\t{fs}\t\t{mnt}')
                
                if mnt_options != '':
                    print(f'\n\tMOUNT OPTIONS\t{mnt_options}')

                if fs == 'btrfs':
                    print('\n\tSUBVOLUMES')
                    print('\t\tNAME\t\tMOUNT POINT')
                    for subvol in subvols:
                        sub_name = subvol['name']
                        sub_mnt = subvol['mount point']
                        print(f'\t\t{sub_name}\t\t{sub_mnt}')
        
        confirmation = input(question)
        if confirmation in ('y', 'Y'):
            self.is_part = True
        else:
            self.is_part = False

        return self.is_part


    def partition(self):

        """
            Partition the Devices with the specified information in ArchInstaller 
            part_info variable.
        """

        #cur_devices = self.get_part_details()
        
        if not self.is_part:
            print("Please confirm Parition configuraion to continue or use -y with the command.")
            sys.exit(0)
        
        if confirm == False:
            part_file = ArchInstaller.PART_FILE
            print(f'Edit the {part_file} file and continue.')
            return 0
        elif confirm == None:
            ArchInstaller.que.put_nowait(PartitionMaker.ERR_CONFIRM)
            raise ArchException(PartitionMaker.ERR_CONFIRM, 1)
        
        # Unmount all Disks if mounted
        if Mounter.findmnt('/mnt')[0] == 0:
            Mounter.umount('/mnt', withRec=True)
        for dev in self.part_info:
            for part in dev['partitions']:
                part_id = dev['name'] + part['part number']
                if part['fs'] == 'swap':
                    Mounter.disable_swap(part_id)
                    continue
                if Mounter.findmnt(part_id)[0] == 0:
                    Mounter.umount(part_id)

        # Partitioning Our Devices 
        partition_status = asyncio.run(Partitioner.create_partition(self.part_info))
        
        # Checking Partition Status
        if partition_status != PartitionMaker.OK_PART:
            ArchInstaller.que.put_nowait(partition_status)
            raise ArchException(PartitionMaker.ERR_MBR, 2)

        # Formating
        msg = Formater().format(self.part_info)
        
        # Checking Format Status
        if msg != PartitionMaker.OK_FORMAT:
            ArchInstaller.que.put_nowait(msg)
            raise ArchException(msg, 3)
        
        # Mounting
        msg = Mounter.mount_parts(self.part_info)
        # Checking Mount Status
        if msg != PartitionMaker.OK_MOUNT:
            ArchInstaller.que.put_nowait(msg)
            raise ArchException(msg, 4)
        
        ArchInstaller.que.put_nowait('\n[ OK ] Partitioning Successfull.\n')
        return 0

## EXCEPTIONS
class ArchException(Exception):
    """This is the base class for all exceptions in this Installer"""
    def __init__(self, msg, return_code):
        self.msg = msg
        self.return_code = return_code
