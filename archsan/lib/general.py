import enum

class BootMode(enum.Enum):
    UNDEFINED = 0
    UEFI = 1
    BIOS = 2