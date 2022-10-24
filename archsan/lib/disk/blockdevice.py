from lib.config import Config
from lib.disk.partition import Partition
from lib.exceptions import CommandError
from lib.menu.menu import MenuItem
from lib.linuxcmd import lsblk_json, wipefs, get_avail_space, sgdisk
import json
from dataclasses import asdict, dataclass, field, InitVar
from typing import ClassVar
from pathlib import Path
from lib.logger import Logger

@dataclass
class BlockDevice():
    PART_TABLE_BACKUP_DIR: ClassVar[str] = '/tmp/archsan/'
    PART_KEYS_SHOW: ClassVar[list[str]] = ["name", "path", "size", "label"]
    PART_KEYS_SHOW_FULL: ClassVar[list[str]] = PART_KEYS_SHOW + ["fs", "mountpoint"]

    name: str
    size: str
    path: str
    logger: Logger = field(default=None)
    model: str = field(default=None)
    uuid: str = field(default=None)
    wipe: bool = field(default=False)
    skip_partition: bool = field(default=False)
    part_info: InitVar[list[dict]] = None
    partitions: list[Partition] = field(init=False, default_factory=list)

    def __post_init__(self, part_info):
        if not self.logger:
            self.logger = Logger("logger-blockdev")
    
        self.__verified = 0
        if part_info:
            for part_data in part_info:
                try:
                    partition_obj = Partition(
                        device=self.path, 
                        size=part_data["size"], 
                        type=part_data["type"], # Partition typecode for sgdisk; eg:ef00 for efi partition
                        number=part_data["number"],
                        label=part_data["label"],
                        mountpoint=part_data["mountpoint"],
                        fs=part_data["fs"],
                        mountoptions=part_data["mountoptions"],
                        overwrite=part_data["overwrite"],
                        check_exists=part_data["exists"],
                        force_format=part_data["force-format"],
                        subvolumes=part_data["subvolumes"]
                    )
                    self.partitions.append(partition_obj)
                except KeyError as e:
                    #Log the error
                    raise e
        


    @property
    def info(self):
        return asdict(self)
    
    @staticmethod
    def scan_blk(device):
        pass

    @staticmethod
    def overwrite_partition(curr_partition: Partition, new_partition: Partition = None, usedefaultsize = True, logger = None):
        # To completely use the size of the deleted partition default value 0 is given to sgdisk
        # rather than given float values directly to sgdisk
        if logger:
            logger.debug(f"Overwriting Parititon {curr_partition.number}")
        
        size = curr_partition.size
        if new_partition:
            size = new_partition.size

            if usedefaultsize:
                new_partition.size = '0'
        
        curr_partition.delete_partition()

        if new_partition:
            new_partition.write_partition()
        else:
            curr_partition.write_partition()

        if new_partition:
            new_partition.size = size

    def backup_partition_table(self):
        self.logger.debug(f"Creating backup for {self.path}")
        dir = Path(f'{self.PART_TABLE_BACKUP_DIR}')
        dir.mkdir(parents=True, exist_ok=True)
        args = [f'--backup={self.PART_TABLE_BACKUP_DIR}/{self.name}_partition_table.backup']
        sgdisk(self.path, endalign=False, args=args)
    
    def load_partition_table_backup(self):
        self.logger.debug(f"Recovering {self.path} from backup")
        dir = Path(f'{self.PART_TABLE_BACKUP_DIR}')
        if not dir.is_dir():
            raise Exception("Unable to load the partition")
        
        args = [f'--load-backup={self.PART_TABLE_BACKUP_DIR}/{self.name}_partition_table.backup']
        sgdisk(self.path, endalign=False, args=args)

    def verify_disk(self):
        self.logger.debug(f"Verifiying partition table in {self.path}")
        self.__verified += 1
        if self.__verified == 3:
            return False
        
        import re
        res = sgdisk(self.path, endalign=False, args=['-v'])
        error_part = re.search(r".*Caution: Partition (.).*",res.stdout)

        # Select only the first group from the output regex
        if error_part:
            error_part = error_part.group(1)

        if error_part:
            self.logger.warn(f"Bad partition ( {error_part} ) in {self.path}")
            try:
                error_part = int(error_part)
            except ValueError:
                error_part = None
            # Look
            proceed = input(f"Error in partition {error_part}. Do you want auto re-partition the disk?(yes/no): ")
            if proceed.lower() == 'yes' or proceed.lower() == 'y':
                corrected = False
                for partition in self.avaliable_partitions:
                    if partition.number == error_part:
                        self.overwrite_partition(partition, usedefaultsize=True, logger=self.logger)
                        if self.__verified < 3 and self.verify_disk():
                            corrected = True
                        
                        break
                if not corrected:
                    # Look
                    self.logger.error("Unable to correct the partition error")
                    dywc = input("Do you want to continue ?(yes/no): ").lower()
                    if dywc == 'no' or dywc == 'n':
                        SystemExit()
                    else:
                        self.logger.warn("Warining - Continuing with bad partitiong")  
                else:
                    self.logger.info("Corrected the partition.")                
            else:
                # Look
                self.logger.warn(f"Warning: {res.stdout}")
                return False

        self.logger.info(f"Successfully partitioned {self.path}")   
        return True
        

    def __wipe_and_write_partition(self):
        self.logger.warn(f"Wiping all data in {self.path}")
        # wipefs(self.path)
        sgdisk(self.path, endalign=False, args=['-Z', '-o'])

        for partition in self.partitions:
            partition.write_partition()

    def __resolve_partnum_conflict(self, partition:Partition, curr_partition:Partition):
        self.logger.debug(f"Partition {partition.number} already exists in {self.path}")
        if partition.size == '0' and partition.overwrite:
            # Deleting and creating the partition so that all the partition with the specified parameters are created
            self.overwrite_partition(curr_partition, new_partition=partition, usedefaultsize=False, logger=self.logger)
        elif partition.size == '0' and not partition.overwrite:
            # Log
            # Check if only default size option is different
            curr_partition.size = '0'
            if partition != curr_partition:
                # Look
                proceed = input(f'Parition-{partition.number} have different parameters with the existing one.\n\
                    Do you want to overwrite the partition? (yes/no): ')
                if proceed.lower() in 'yes':
                    self.overwrite_partition(curr_partition, new_partition=partition, usedefaultsize=False, logger=self.logger)
                else:
                    # Log
                    print("Change the configuration and continue")
                    SystemExit()
            else:
                self.logger.info("Using existing partition", curr_partition.number)
        # Check if the size of partition is greater the existing partition
        elif partition > curr_partition:
            # Check if the current partition is the last partition available
            if curr_partition != self.avaliable_partitions[-1]:
                raise Exception(f'Too big partition to be created.\
                    \nCheck if other partitions are present after Partition-{curr_partition.number}')
            elif partition.overwrite:
                # Look
                # Log - Optionally check if it is larger than the disk size
                self.overwrite_partition(curr_partition, new_partition=partition, usedefaultsize=False, logger=self.logger)
            else:
                raise Exception(f'No overwrite option specified for Partition-{partition.number}.\
                    \nPartition already exists.')

        elif partition < curr_partition:
            if partition.overwrite:
                self.overwrite_partition(curr_partition, new_partition=partition, usedefaultsize=False, logger=self.logger)
            else:
                raise Exception(f'No overwrite option specified for Partition-{partition.number}.\
                    \nPartition already exists.')

    def write_partition(self):
        self.logger.info(f"Partitioning {self.path}")
        if self.skip_partition:
            self.logger.debug(f"Ignoring partitioning {self.path}")
            return

        if self.wipe:
            self.__wipe_and_write_partition()
        else:
            self.logger.debug(f"Scanning current partitions in {self.path}")            
            self.avaliable_partitions = self.load_current_partitions()

            for partition in self.partitions:
                found = False
                for curr_partition in self.avaliable_partitions:
                    # if curr_partition in self.part_info["remove-partitions"]:
                    #     curr_partition.delete_partition()
                    #     break

                    if partition == curr_partition:
                        self.logger.debug(f"Partition {curr_partition.number} already exists in {self.path}")
                        found = True
                        if partition.overwrite:
                            self.overwrite_partition(curr_partition, new_partition=partition, usedefaultsize=False, logger=self.logger)
                        else:
                            self.logger.debug(f"Using existing partition {curr_partition.number} for {self.path}")
                        
                        break

                    elif partition.number == curr_partition.number:
                        found = True
                        self.__resolve_partnum_conflict(partition, curr_partition)
                        break
 
                if not found:
                    if partition.check_exists:
                        raise Exception(f"Partition {partition.number} doesn't exist.")

                    avail_size_raw = get_avail_space(self.path)
                    avail_size = Config.parseSize(avail_size_raw)
                    no_space_msg = f'No space available for Partition-{partition.number}'

                    if partition.size == '0':
                        if Partition.cmp_size(avail_size, Partition.MIN_SIZE) == 1:
                            partition.write_partition()
                        else:
                            raise Exception(no_space_msg)
                    else:
                        if Partition.cmp_size(avail_size, partition.size) >= 0 and\
                            Partition.cmp_size(avail_size, Partition.MIN_SIZE) == 1:
                            partition.write_partition()
                        else:
                            # Log
                            raise Exception(no_space_msg)

        self.verify_disk()

    def format_partitions(self):
        self.logger.debug(f"Formatting partitions in {self.path}")
        for partition in self.partitions:
            partition.format()
        
        self.logger.info(f"Successfully formatted partitions in {self.path}")

    def mount_partitions(self):
        partitions = sorted(self.partitions, key=lambda partition: partition.filesystem.mountpoint.count("/"))
        self.logger.debug(f"Mounting partitions in {self.path}")
        for partition in partitions:
            partition.mount()
        
        self.logger.info(f"Successfully mounted partitions in {self.path}")

    def load_current_partitions(self) -> list[Partition]:
        res = lsblk_json(device=self.path)
        info = json.loads(res.stdout)
        if "blockdevices" not in info:
            raise Exception(f"{self.path} doesn't exist.")
        else:
            blk = info["blockdevices"][0]
        
        curr_partitions = []
        if "children" in blk:
            curr_partitions_info = blk["children"]
        else:
            curr_partitions_info = []

        part_typecodes = Partition.get_part_typecodes(self.path)
        for partition in curr_partitions_info:
            partnum = partition["path"][-1]
            partcode = part_typecodes[partnum]
            part = Partition(
                name=partition["name"],
                label=partition["partlabel"],
                number=partnum,
                size=partition["size"],
                device=self.path,
                type=partcode,
                fs=None,
            )

            curr_partitions.append(part)

        return curr_partitions

    def remove_partitions(self, partnums: list[int]):
        for partnum in partnums:
            try:
                Partition.delete_partition_with_number(self.path, partnum)
            except CommandError as e:
                if "out of range" in e.msg:
                    self.logger.warn(f"{partnum} doesn't exist in {self.path}. Ignoring.")
                else:
                    raise e

    def display_partitions(self, window, fullscreen = False):
        max_x = window.getmaxyx()[1]
        
        x_begin = self.x_begin
        if len(self.partitions) == 0:
            window.addstr(self.curr_line, x_begin, 'No Partitions found!')
            return

        if fullscreen:
            keys = self.PART_KEYS_SHOW_FULL
            column_width = len(self.PART_KEYS_SHOW_FULL) + 1
        else:
            keys = self.PART_KEYS_SHOW
            column_width = len(self.PART_KEYS_SHOW) + 1
        gap_x = max_x // column_width

        for idx, key in enumerate(keys):
            window.addstr(self.curr_line, x_begin + idx, f'{key}')
            x_begin += max_x // column_width
        
        for partition in self.partitions:
            self.curr_rwin_line += 2
            x_begin = self.x_begin

            partition.display(window=window,start_x=x_begin, y=self.curr_line, gap=gap_x, keys=keys)
                    
    def display(self, window, fullscreen = False):
        window.clear()
        window.border()

        if not fullscreen:
            window.addstr(0, 4, "info")
        else:
            max_x = window.getmaxyx()[1]
            head_str = f'Block Device - {self.info["name"]}'.upper()
            x_begin = max_x // 2 - len(head_str)
            window.addstr(0, x_begin, head_str)

        if not fullscreen:
            self.curr_line = 2
        else:
            self.curr_line = 4
        
        # Position where the left column(key) is placed; -- Value is placed 5 times the key position value
        self.x_begin = 4
        for key, value in self.info.items():
            try:
                window.addstr(self.curr_line, self.x_begin, f'{key}'.capitalize())
                window.addstr(self.curr_line, self.x_begin * 5, f'{value}')
            except:
                raise Exception(f'Unable to display {key} with {value}')

            self.curr_line += 2

        self.curr_line += 2
        window.addstr(self.curr_line, self.x_begin, f"partition {fullscreen}".capitalize())
        self.curr_line += 2
        self.display_partitions(window, fullscreen=fullscreen)

        window.refresh()

    def __str__(self):
        str = 'Block Device:'

        for key,value in self.info.items():
            if key == "partitions":
                continue
            field = f'\n\t{key.capitalize()}:\t{value}'
            str += field

        return str