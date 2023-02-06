from logging import raiseExceptions
from pathlib import Path
import yaml
from sanarch.lib.disk.partition import Partition

class Config:
    PARTITION_KEYS = ["label", "number", "type", "fs", "size", "mountpoint", "mountoptions", "subvolumes", "overwrite", "skip-format", "exists"]
    PARTITION_KEYS_ASSERT = ["number", "fs", "size", "mountpoint"]
    PARTLABEL_KEYS = ["device", "wipe", "partitions", "skip-partition", "remove-partitions"]
    CONFIG_KEYS = ["partlabel", "base-packages"]
    OPTIONAL_CONFIG_KEYS = ["timezone-region", "timezone-city", "locales-use-default", "locales", "locale_LANG", "locale_KEYMAP", 
                            "hostname", "temp-rootpass", "bootloader", "esp", "detect-other-os", "users", "packages", "after-scripts"]
    DEFAULT_LOCALES = ["en_US.UTF-8 UTF-8"]
    DEFAULT_LANG = "en_US.UTF-8"
    DEFAULT_HOSTNAME = "archlinux"

    def __init__(self, config_file):
        self.file = config_file
        self.__config = self.load(config_file)
        self.validate_config_params()

    @property
    def partlabel(self):
        try:
            return self.__config["partlabel"]
        except Exception:
            return []

    @property
    def base_packages(self):
        return self.__config["base-packages"]

    def iswipe(self, device: str) -> bool:
        for dev in self.partlabel:
            if dev["device"] == device:
                return dev["wipe"]
            
        return False

    @property
    def timezone(self):
        if not self.__config["timezone-region"] or not self.__config["timezone-city"]:
            return None

        return {"region": self.__config["timezone-region"], "city": self.__config["timezone-city"]}

    @property
    def locales(self):
        if self.__config["locales"]:
            return self.DEFAULT_LOCALES + self.__config["locales"]
        else:
            return self.DEFAULT_LOCALES
        
    @property
    def locale_lang(self):
        if self.__config["locale_LANG"]:
            return self.__config["locale_LANG"]
        else:
            return self.DEFAULT_LANG
    
    @property
    def locale_keymap(self):
        if self.__config["locale_KEYMAP"]:
            return self.__config["locale_KEYMAP"]
        else:
            return None

    @property
    def hostname(self):
        if self.__config["hostname"]:
            return self.__config["hostname"]
        else:
            return self.DEFAULT_HOSTNAME

    @property
    def bootloader(self):
        if self.__config["bootloader"]:
            return self.__config["bootloader"]
        else:
            return None

    @property
    def esp(self):
        return self.__config["esp"]

    @property
    def users(self):
        return self.__config["users"]


    @property
    def packages(self):
        return self.__config["packages"]

    @property
    def services(self):
        return self.__config["enable-services"]

    @property
    def detect_other_os(self):
        return self.__config["detect-other-os"]

    @property
    def after_scripts(self):
        return self.__config["after-scripts"]

    def get_all_devs(self):
        return [disk["device"] for disk in self.partlabel]

    def get_device_info(self) -> list[tuple[str,Partition, bool]]:
        return [
            {
                "device": disk["device"], 
                "partitions":disk["partitions"], 
                "skip-partitions": disk["skip-partition"],
                "remove-partitions": disk["remove-partitions"],
                "wipe": disk["wipe"],
            } 
            for disk in self.partlabel
        ]

    def get_partitions(self, device):
        for disk in self.partlabel:
            if disk["device"] == device:
                return disk["partitions"]
            
        return None
    
    def get_remove_partitions(self, device):
        for disk in self.partlabel:
            if disk["device"] == device:
                return disk["remove-partitions"]

    @staticmethod
    def parseSize(size:str, partnum = None):
        # For convinience converting all letters in size to lower case
        size = str(size)
        size = size.lower().replace(" ", "")

        # Check if the size is valid
        if not size[-1] in Partition.SIZE_UNITS and not size[-3:] in Partition.SIZE_UNITS_FULL:
            msg = f'Invalid value for size. (partition {partnum})'
            raise Exception(msg)
        
        # Convert to single letter unit
        if size != "0" and size[-3:] in Partition.SIZE_UNITS_FULL:
            size = size[:-3] + size[-3]

        return size
    

    def validate_config_params(self):
        missing_configkeys = list(set(self.CONFIG_KEYS) - set(self.__config.keys()))
        if missing_configkeys:
            raise Exception(f"No options for {missing_configkeys} is provided in the config!")

        missing_optional_config_keys = list(set(self.OPTIONAL_CONFIG_KEYS) - set(self.__config.keys()))
        for key in missing_optional_config_keys:
            if key == "locales-use-default":
                self.__config[key] = True
            elif key == "detect-other-os":
                self.__config[key] = False
            else:
                self.__config[key] = None
            
        self.validate_partlabel()
        

    def validate_dev_params(self):
        for dev in self.partlabel:
            missingkeys = list(set(self.PARTLABEL_KEYS) - set(dev.keys()))
            
            if "skip-partition" in missingkeys:
                dev["skip-partition"] = False
                missingkeys.remove("skip-partition")
            
            if "remove-partitions" in missingkeys:
                dev["remove-partitions"] = []
                missingkeys.remove("remove-partitions")

            if len(missingkeys) != 0:
                raise Exception(f'{missingkeys} are required')


    def validate_partition_params(self):
        try:
            for dev in self.partlabel:
                for partition in dev["partitions"]:
                    missingkeys = list(set(self.PARTITION_KEYS) - set(partition.keys()))

                    # Check if missing keys are part of required keys
                    reqkeys = [key for key in missingkeys if key in self.PARTITION_KEYS_ASSERT]
                    if len(reqkeys) != 0:
                        reqkeys_str = ','.join(reqkeys)
                        try:
                            partnum = partition["number"]
                        except KeyError:
                            partnum = ''
                        
                        if len(reqkeys) == 1:
                            prefix = f'key "{reqkeys_str}" is '
                        else:
                            prefix = f'keys "{reqkeys_str}" are '

                        msg = f'{prefix} required for {dev["device"]} - Partition {partnum}'
                        raise Exception(msg)

                    partition["size"] = self.parseSize(partition["size"], partition["number"])

                    for key in missingkeys:
                        # If type code is not given assume Linux filesystem as default (8300)
                        if key == "path":
                            partition["path"] = f'{dev["device"]}/{partition["number"]}'
                        elif key == "type":
                            partition["type"] = '8300'
                        elif key in ["overwrite", "exists", "force-format", "skip-format"]:
                            partition[key] = False
                        else:
                            partition[key] = None
                    
        except KeyError as e:
            print('Error: ', e)
            pass


    def validate_partlabel(self):
        # Need to implement enforcing of certain keys
        self.validate_dev_params()
        self.validate_partition_params()
            

    def load(self, config_file):
        # directory containing the this file
        dir = Path(__file__).resolve().parent
        root = dir.parts[-1]
        while root != "archsan":
            dir = dir.parent
            root = dir.parts[-1]
        
        # file_path = dir / 'profiles/default.yaml'
        
        with open(config_file) as f:
            return yaml.safe_load(f)
