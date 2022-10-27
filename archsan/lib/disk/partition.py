from dataclasses import dataclass, field, InitVar
from lib.disk.filesystem import FileSystem, filesystem_helper
from lib.linuxcmd import sgdisk, awk
from typing import ClassVar

@dataclass(eq=True)
class Partition:
    # Support for petabytes(p or pib) is not added - cuz I don't think I will be using it anytime soon :)
    SIZE_UNITS: ClassVar[list[str]] = ["0", "k", "m", "g", "t"]
    SIZE_UNITS_FULL: ClassVar[list[str]] = ["kib", "mib", "gib", "tib"]
    MIN_SIZE: ClassVar[str] = '2m' # 2mib for default alignment at start and end (2048)

    device: str = field(compare=True)
    size: str = field(compare=True)
    number: int = field(compare=True)
    path:str = field(default=None, compare=True)
    type: str = field(default="0", compare=True)
    typename: str = field(default=None, compare=False)
    name: str = field(default=None, compare=True)
    label: str = field(default=None, compare=False)
    uuid: str = field(default=None, compare=False)
    skip_format: bool = field(default=False, compare=False)
    mountpoint: InitVar[str] = field(default=None, compare=False)
    fs: InitVar[str] = field(default=None, compare=False)
    force_format: InitVar[bool] = field(default=False, compare=False)
    mountoptions: InitVar[str] = field(default=None, compare=False)
    subvolumes: InitVar[list[dict]] = field(default=None, compare=False)
    overwrite: bool = field(default=False, compare=False)
    check_exists: bool = field(default=False, compare=False)
    filesystem: FileSystem = field(default=None, init=False, compare=False)

    def __post_init__(self, mountpoint, fs, force_format, mountoptions, subvolumes):      
        if not self.path:
            self.path = f'{self.device}{self.number}'

        if self.size[0] != '0':
            self.size = '+' + self.size
        
        try:
            self.number = int(self.number)
        except ValueError:
            raise Exception("Parititon number should be an integer")

        if not self.number:
            self.number = 0
        
        # Lowercase makes it easier to compare
        self.size = self.size.lower()
        
        if self.type:
            self.type = self.type.lower()

        if fs:
            self.filesystem = filesystem_helper(fs, self.path, mountpoint, force_format, mountoptions, subvolumes)
        
        #print("self: ", self)

    @staticmethod
    def get_part_typecodes(device) -> dict[str, str]:
        # sgdisk = Command('sgdisk', args=[f'-p {device}'], shell=True)
        sg_res = sgdisk(device, endalign=False,args=['-p'])
        awk_pattern = f"'{{if(NF == 0) {{ flag=1 }}}} {{ if(flag == 1 && NF != 0 && $0 !~ /Number/) {{ print $1, $6 }}}}'"

        awk_res = awk(args=['-v flag=0',awk_pattern], shell=True, input=sg_res.stdout)
        part_codes_str = awk_res.stdout.split('\n')

        part_typecodes = {}

        for part_code_str in part_codes_str:
            if part_code_str:
                num_code = part_code_str.split(' ')
                part_typecodes[num_code[0]] = num_code[1]

        return part_typecodes
    
    @staticmethod
    def get_part_typecode(device, partnum):
        typecodes = Partition.get_part_typecodes(device)
        return typecodes[partnum]

    @classmethod
    def cmp_size(cls, size1: str, size2: str) -> bool:
        # Assumes that the size contains only one letter 
        # as it should be converted to the single letter format in Config class
        if size1[0] == '+':
            size1 = size1[1:]
        
        if size2[0] == '+':
            size2 = size2[1:]

        if float(size1[:-1]) == float(size2[:-1]):
            return 0
        elif size1[-1].lower() == size2[-1].lower():
            if float(size1[0:-1]) > float(size2[0:-1]):
                return 1
            else:
                return -1
        else:
            if cls.SIZE_UNITS.index(size1[-1].lower()) > cls.SIZE_UNITS.index(size2[-1].lower()):
                return 1
            else:
                return -1

    def __gt__(self, other):
        res = self.cmp_size(self.size, other.size)
        return res == 1

    def write_partition(self) -> int:
        args = [f'-n {self.number}:0:{self.size}']

        if self.type:
            args += [f'-t {self.number}:{self.type}']
        
        if self.name:
            args += [f'-c {self.number}:{self.name}']

        sgdisk(self.device, args=args)

        # self.path = f'{self.device}{self.number}'
        
        return self.number

    def delete_partition(self) -> bool:
        self.delete_partition_with_number(self.device, self.number)
    
    @staticmethod
    def delete_partition_with_number(device, partnum):
        args = [f'-d {partnum}']

        res = sgdisk(device, endalign=False, args=args)
        return res.returncode == 0

    def format(self):        
        if not self.path:
            raise Exception("No partition found! Create the partition first")

        if not self.skip_format:
            self.filesystem.format()

    def mount(self):
        # if not self.mountpoint:
        #     raise Exception("Invalid Partition")
        
        # FileSystem.mount(self.fs, self.path, self.mountpoint)
        self.filesystem.mount()

    def display(self, window, start_x = 0, y = 0, gap = 4, keys = None):
        if not keys:
            keys = [key for key, value in self.info.items()]
        
        max_y, max_x = window.getmaxyx()
        item_width = max_x // len(keys) + gap

        info = self.info
        curr_x = start_x
        for key in keys:
            window.addstr(y, curr_x, f'{info[key]}')
            curr_x += gap