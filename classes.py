from subprocess import Popen, PIPE
from progress.spinner import Spinner
from threading import Thread
import asyncio, subprocess
import re, json, urwid, sys, time
import concurrent.futures


class ArchInstaller():
    PART_FILE = None
    CONFIG_FILE = None
    DEFAULT = False
    PART_INFO = []
    CONFIG_INFO = {}
    IS_BTRFS = True

    @staticmethod
    def set_files(part_file, config_file):
        ArchInstaller.PART_FILE = part_file
        ArchInstaller.CONFIG_FILE = config_file
        ArchInstaller.set_part_info()
        ArchInstaller.set_config_info()

    @staticmethod
    def set_default(defalut):
        ArchInstaller.DEFAULT = defalut

    @staticmethod
    def set_part_info():
        with open(ArchInstaller.PART_FILE) as f:
            data = f.read()
            ArchInstaller.PART_INFO = json.loads(data)

    @staticmethod
    def set_config_info():
        with open(ArchInstaller.CONFIG_FILE) as f:
            data = f.read()
            ArchInstaller.CONFIG_INFO = json.loads(data)

    @staticmethod
    def get_part_info():
        return ArchInstaller.PART_INFO

    @staticmethod
    def get_config_info():
        return ArchInstaller.CONFIG_INFO

    @staticmethod
    def get_default():
        return ArchInstaller.DEFAULT

    @staticmethod
    def set_is_btrfs(val):
        ArchInstaller.IS_BTRFS = val

    @staticmethod
    def get_is_btrfs():
        return ArchInstaller.IS_BTRFS


class CommandExecutor():
    @staticmethod
    def execute(command, stdout=None, stderr=None,stdin=None, input= None):
        proc = Popen(command, stdout=stdout, stderr=stderr,stdin=stdin, text=True)
        
        out, err = proc.communicate(input)

        return (proc.returncode, out, err)


class Command():
    chroot = 'arch-chroot' 
    chroot_loc = '/mnt'

    @staticmethod
    def mkdir(folders = None):
        if folders is None:
            return 1

        proc = Popen(['mkdir', '-p', folders], stdout=PIPE, stderr=PIPE, text=True)
        proc.communicate()
        return proc.returncode

    @staticmethod
    def pacstrap():
        pacs = ArchInstaller.get_config_info()['pacstrap']
        
        if pacs is None:
            return 0
        
        pac_command = 'base '
        for pac in pacs:
            pac_command += pac + ' '
        
        command = 'pacstrap /mnt ' + pac_command

        proc = Popen(command, stdin=PIPE, text=True, shell=True)
        proc.communicate('y\n')

        return 0

    @staticmethod
    def pacman():
        pacs = ArchInstaller.get_config_info()['pacman']

        if pacs is None:
            return
            
        pac_command = ''
        for pac in pacs:
            pac_command += pac + ' '
        
        command = f'{Command.chroot} {Command.chroot_loc} pacman -S --noconfirm ' + pac_command
        proc = Popen(command,text=True, shell=True)
        proc.communicate()
        
        #Raise Exception
        if proc.returncode != 0:
            exit(13)
        
        return 0

    @staticmethod
    def set_mirrorlist():
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
        if uuid:
            proc = Popen('genfstab -U /mnt >> /mnt/etc/fstab', stdout=PIPE, stderr=PIPE,text=True, shell=True)
        else:
            proc = Popen('genfstab mnt >> /mnt/etc/fstab', stdout=PIPE, stderr=PIPE,text=True, shell=True)

        out = proc.communicate()[0]
        
        print(out)
        return proc.returncode

    @staticmethod
    def arch_config():
        config = ArchInstaller.get_config_info()['settings']

        zone = '/usr/share/zoneinfo/' + config['zone']
        proc = Popen([Command.chroot,Command.chroot_loc, 'ln', '-sf', zone, '/etc/localtime'],
        text= True)
        proc.communicate()

        if proc.returncode != 0:
            return 1
        
        proc = Popen([Command.chroot, Command.chroot_loc, 'hwclock', '--systohc'], text=True)
        proc.communicate()

        if proc.returncode != 0:
            return 2

        with open('/mnt/etc/locale.gen', 'a') as f:
            for locale in config['locale']:
                f.write(locale + '\n')

        proc = Popen([Command.chroot, Command.chroot_loc, 'locale-gen'], text=True)
        proc.communicate()

        if proc.returncode != 0:
            return 3

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

        tmp_pass = config['tmp rt pass']
        proc = Popen([Command.chroot, Command.chroot_loc, 'passwd', 'root'], stdin=PIPE,text=True)
        proc.communicate(f'{tmp_pass}\n{tmp_pass}\n')

        if ArchInstaller.get_is_btrfs():
            with open('/mnt/etc/mkinitcpio.conf', 'r') as fr:
                with open('/mnt/etc/mkinitcpio.conf.bak', 'w') as fw:
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
            proc.communicate()

        if proc.returncode != 0:
            return proc.returncode
                

class BootLoader():
    @staticmethod
    def inst_grub():
        chroot = Command.chroot
        chroot_loc = Command.chroot_loc
        proc = Popen(
            f'{chroot} {chroot_loc} grub-install --target=x86_64-efi --efi-directory=/boot --bootloader-id=GRUB', shell=True, text=True)
        proc.communicate()

        proc = Popen(f'{chroot} {chroot_loc} grub-mkconfig -o /boot/grub/grub.cfg', shell=True,
        text=True)
        proc.communicate()

        return proc.returncode


class CustomSpinner():
    def __init__(self,prompt, no_of_times, time_in_sec):
        self.t = Thread(target=self.spin, args=(no_of_times, time_in_sec), daemon=True)
        self.state = True
        self.spinner = Spinner(prompt)
    
    def spin(self, no_of_times, time_in_sec):
        for _ in range(no_of_times):
            self.spinner.next()
            if self.state:
                time.sleep(time_in_sec)
            else:
                return
    
    def start(self):
        self.t.start()

    def stop(self):
        self.state = False
        self.t.join()
        print()
        return 

class Ping():
    def __init__(self, site):
        self.state = False
        self.site = site
        self.spinner = CustomSpinner('Checking Internet Connection ', 99, 0.1)

    def ping(self):
        self.spinner.start()
        status = False
        proc = Popen(['ping', '-c 5',self.site], stdout=PIPE, stderr=PIPE, text=True)
        try:
            proc.communicate(timeout=10)
        except subprocess.TimeoutExpired:
            proc.kill()
            msg = proc.communicate()[1]
            msg += '\n[Error] No internet connection\n'

        if proc.returncode == 0:
            status = True
            msg = '[OK]Internet Connection Checked'
        
        self.spinner.stop()
        return [status, msg]




class SysClockUpdator():
    ALREADY_ACTIVE = '[OK]System Clock was Already Active.'
    SETTING_CLOCK = 'Setting the System Clock...'
    ERR_STATUS = '[ERROR]Unable to find System Clock Status.'
    OK_UPDATE = '[OK]System Clock Updated.'
    ERR_UPDATE = '[ERROR]Unable to Update System Clock.'

    STATE_COMPLETED = 0
    STATE_INCOMPLETED = 1
    STATE_ERR = 2

    CURR_STATE = None

    @classmethod
    def check_status(cls):
        proc = Popen(['timedatectl', 'status'], stdout=PIPE, stdin=PIPE, text=True)
        out, err = proc.communicate()
    
        if proc.returncode != 0:
            status_msg = err + cls.ERR_STATUS
            cls.CURR_STATE = cls.STATE_ERR
            return [proc.returncode, status_msg]
    
        re_out = re.search('.*NTP service:(.*$)', out, re.MULTILINE)
    
        # Return system call is active
        if re_out.group(1).strip().lower() != 'active':
            status_msg = cls.SETTING_CLOCK
            cls.CURR_STATE = cls.STATE_INCOMPLETED
        else:
            status_msg = cls.ALREADY_ACTIVE
            cls.CURR_STATE = cls.STATE_COMPLETED

        return [proc.returncode, status_msg]

    
    @classmethod
    def set_clock(cls):
        proc = Popen(['timedatectl', 'set-ntp', 'true'], stdout=PIPE, stderr=PIPE, text=True)
        err = proc.communicate()[1]
        if proc.returncode != 0:
            print(proc.returncode)
            msg = err
            msg += cls.ERR_UPDATE
            cls.CURR_STATE = cls.STATE_ERR
        else:
            msg = cls.OK_UPDATE
            cls.CURR_STATE = cls.STATE_COMPLETED
    
        return [ proc.returncode, msg ]

    
    @classmethod
    def update_sys_clock(cls):
        rv = cls.check_status()
        if cls.CURR_STATE != cls.STATE_INCOMPLETED:
            return rv

        rv = cls.set_clock()
        return rv


class PartUi():
    TAB_SPACE = 4

    def __init__(self, text, que, palette=None):
        text = text.replace('\t', ' ' * 4)
        self.confirmation = None
        self.palette = palette
        self.text = f"{text}\n{que}\n"
        self.text = urwid.Text([('text', self.text)])
        self.map_txt = urwid.AttrMap(self.text, 'map_text')
        self.fill = urwid.Filler(self.map_txt, 'top')
        self.map_fill = urwid.AttrMap(self.fill, 'map_fill')
        self.loop = urwid.MainLoop(self.map_fill, self.palette, unhandled_input=self.spcl_key_press)
    
    def spcl_key_press(self, key):
        if key in ('q', 'Q'):
            raise urwid.ExitMainLoop()
        elif key in ('y', 'Y'):
            self.confirmation = True
            raise urwid.ExitMainLoop()
        elif key in ('n', 'N'):
            self.confirmation = False
            raise urwid.ExitMainLoop()

    def run(self):
        self.loop.run()
        # Clear the Screen 
        proc = Popen(['clear'], stderr=PIPE, shell=True)
        proc.communicate()
        return self.confirmation
    

class Partitioner():
    @classmethod
    def set_msg(cls, ERR_PARTITION, ERR_MBR, OK_SUCCESS):
        cls.ERR_PARTITION = ERR_PARTITION
        cls.ERR_MBR = ERR_MBR
        cls.OK_SUCCESS = OK_SUCCESS

    @staticmethod
    async def write_stdin(proc, command, endwith):
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
    format_method = {
        'fat32': 'fat',
        'ext4': 'ext4',
        'btrfs': 'btrfs',
        'swap': 'swap'
    }

    @classmethod
    def set_msg(cls, OK_FORMAT, ERR_FORMAT, ERR_SUPPORT):
        cls.OK_FORMAT = OK_FORMAT
        cls.ERR_FORMAT = ERR_FORMAT
        cls.ERR_SUPPORT = ERR_SUPPORT

    def format(self, part_info):
        print("Formatting")
        for devices in part_info:
            dev_name = devices['name']
            for partition in devices['partitions']:
                part_id = dev_name + partition['part number']
                func = getattr(self, self.format_method[partition['fs']], 'Invalid')

                if func == 'Invalid':
                    return [-1, Formater.ERR_SUPPORT]
                

                if partition['fs'] in 'btrfs':
                    ArchInstaller.set_is_btrfs(True)
                    return_code = func(part_id, partition['subvolumes'], partition['mount point'])
                else:
                    return_code = func(part_id)

        if return_code != 0:
            return [return_code, Formater.ERR_FORMAT]
        else:
            return [return_code, Formater.OK_FORMAT]


    @staticmethod
    def format_exec(command_list):
        proc = Popen(command_list, stdout=PIPE, text=True)
        proc.communicate()
        return proc.returncode 

    @staticmethod
    def fat(part_id):
        return Formater.format_exec(['mkfs.fat', '-F32', part_id])

    @staticmethod
    def ext4(part_id):
        return Formater.format_exec(['mkfs.ext4', part_id])
    
    @staticmethod
    def btrfs(part_id, subvolumes, mnt):
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
        res = Formater.format_exec(['mkswap', part_id])

        if res != 0:
            return res

        return Formater.format_exec(['swapon', part_id])


class Mounter():
    @classmethod
    def set_msgs(cls, ERR_MOUNT, OK_MOUNT):
        cls.ERR_MOUNT = ERR_MOUNT
        cls.OK_MOUNT = OK_MOUNT


    @staticmethod
    def mount(part_id, loc, options=None):
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
        if subvolumes is None:
            return 2
        
        for subvol in subvolumes:
            loc = subvol['mount point']
            Command.mkdir(loc)
            options += f",subvol={subvol['name']}"

            res = Mounter.mount(part_id, loc, options)

            if res != 0:
                return
        
        return 0

    
    @staticmethod
    def gen_mount(part_id, loc):
        Command.mkdir(loc)
        return Mounter.mount(part_id, loc)

    @staticmethod
    def mount_parts(part_info):
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
                    return 1
        
        for unmount_part in unmount_parts:
            if unmount_part['fs_type'] == 'btrfs':
                res = Mounter.btrfs_mount(unmount_part['subvolumes'], 
                unmount_part['options'], unmount_part['part_id'], 
                unmount_part['loc'])
            else:
                res = Mounter.gen_mount(unmount_part['part_id'], unmount_part['loc'])
                
            if res != 0:
                return 1

        return 0

    @staticmethod
    def umount(part_id, withRec=False):
        if not withRec:
            proc = Popen(['umount', part_id], stdout=PIPE, stdin=PIPE, 
            text=True)
            proc.communicate()
        else:
            proc = Popen(['umount', '-R', part_id], stdout=PIPE, stdin=PIPE, 
            text=True)
            proc.communicate()

        return proc.returncode

    @staticmethod
    def findmnt(part_id):
        proc = Popen(['findmnt', part_id], stdout=PIPE, stdin=PIPE, text=True)
        out = proc.communicate()[0]

        return [proc.returncode, out]


class PartitionMaker():
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
        self.part_info = ArchInstaller.get_part_info()
        self.default = ArchInstaller.get_default()
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
    

    def get_part_details(self):
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
        part_list_str = ''
        for part in  part_list:
            for key, val in part.items():
                part_list_str += str(f"\t{key}:\t{val}\n")
            
            part_list_str += '\n'
        
        return part_list_str

    def tostr_part_info(self, part_info):
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


    def print_on_wid(self, cur_devices, part_info):
        info_str = 'DEVICES AND PARTITIONS AVAILABLE: \n' \
        + self.tostr_part_device(cur_devices) + '\n' \
        + 'USING THE PARTITIONS: \n' \
        + self.tostr_part_info(part_info)

        que = 'Do YOU WANT TO CONTINUE WITH THIS CONFIGURATION ?(y/n)'
        palette = None

        confirmation = PartUi(info_str,que,palette).run()
        return confirmation


    def partition(self):
        cur_devices = self.get_part_details()
        
        if not self.default:
            confirm = self.print_on_wid(cur_devices, self.part_info)
        else:
            confirm = True
        
        if confirm == False:
            part_file = ArchInstaller.PART_FILE
            print(f'Edit the {part_file} file and continue.')
            return -1
        elif confirm == None:
            print(PartitionMaker.ERR_CONFIRM)
            return 5
        else:
            print(PartitionMaker.WARN_PARTITION)
        
        # Unmount all Disks if mounted
        if Mounter.findmnt('/mnt')[0] == 0:
            Mounter.umount('/mnt', withRec=True)
        for dev in self.part_info:
            for part in dev['partitions']:
                part_id = dev['name'] + part['part number']
                if Mounter.findmnt(part_id)[0] == 0:
                    Mounter.umount(part_id)
        
        partition_status = asyncio.run(Partitioner.create_partition(self.part_info))

        if partition_status == PartitionMaker.ERR_MBR:
            print(PartitionMaker.ERR_MBR)
            return 6
        elif partition_status == PartitionMaker.ERR_PARTITION:
            print(PartitionMaker.ERR_PARTITION)
            return 7
        elif partition_status == PartitionMaker.OK_PART:
            self.success_status = PartitionMaker.OK_PART
            print(PartitionMaker.OK_PART)

        rcode, msg = Formater().format(self.part_info)
        
        if rcode != 0:
            print(msg)
            return 8
        print(msg)

        Mounter.set_msgs(PartitionMaker.ERR_MOUNT, PartitionMaker.OK_MOUNT)
        mnt_res = Mounter.mount_parts(self.part_info)

        if mnt_res != 0:
            print(PartitionMaker.ERR_MBR)
            return 9

        print(PartitionMaker.OK_MOUNT)
        return 0


