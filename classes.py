from subprocess import Popen, PIPE
from progress.spinner import Spinner
from threading import Thread
import asyncio, subprocess
import re, json, urwid, sys, time


class Command():
    @staticmethod
    def mkdir(folders = None):
        if folders is None:
            return 1
        
        proc = Popen(['mkdir', '-p', folders], stdout=PIPE, stderr=PIPE, text=True)
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
                    return_code = func(part_id, partition['subvolumes'])
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
    def btrfs(part_id, subvolumes):
        format_stat = Formater.format_exec(['mkfs.btrfs', '-f', part_id])
        if format_stat != 0:
            return format_stat
        
        proc = Popen(['mount', part_id, '/mnt'], stdout=PIPE, text=True)
        proc.communicate()

        if proc.returncode != 0:
            return proc.returncode
        
        for subvolume in subvolumes:
            proc = Popen(['btrfs', 'subvolume', 'create', subvolume['mount point']], stdout=PIPE,
            text=True)
            proc.communicate()[0]
            if proc.returncode != 0:
                return proc.returncode
        
        Mounter.umount('/mnt')

        return proc.returncode

        @staticmethod
        def swap(part_id):
            res = Formater.format_exec(['mkswap', part_id])

            if proc != 0:
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
        for subvol in subvolumes:
            loc = subvol['mount point']
            Command.mkdir(subvol['mount point'])
            options += f",subvol={subvol['name']}"
            if subvol['name'] == 'root' and subvol['mount point'] == '/mnt/root':
                loc = '/mnt'
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
        for dev in part_info:
            part_name = dev['name']
            for partition in dev['partitions']:
                if partition['hex code'] == '8200' or partition['name'] == 'swap':
                    continue
                part_id = part_name + partition['part number']
                loc = partition['mount point']
                options = partition['mount options']
            
                if options == '':
                    options = None
                
                if partition['fs'] == 'btrfs':
                    res = Mounter.btrfs_mount(partition['subvolumes'], options, part_id, loc)
                else:
                    res = Mounter.gen_mount(part_id, loc)
                
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

    def __init__(self, part_filename, default):
        self.part_filename = part_filename
        self.part_info = None
        self.default = default
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

    def open_files(self):
        try:
            self.part_file_r = open(self.part_filename, 'r')
        except Exception:
            print(PartitionMaker.ERR_OPEN)
            return 1

    def close_files(self):
        try:
            self.part_file_r.close()
        except Exception:
            print(PartitionMaker.ERR_CLOSE)
            return 2
    

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


    def read_part_info(self):
        data = self.part_file_r.read()
        part_info = json.loads(data)
        return part_info
    
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
        self.open_files()
        cur_devices = self.get_part_details()
        self.part_info = self.read_part_info()
        self.close_files()
        
        if not self.default:
            confirm = self.print_on_wid(cur_devices, self.part_info)
        else:
            confirm = True
        
        if confirm == False:
            print(f'Edit the {self.part_filename} file and continue.')
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


