from pathlib import Path
import shutil
from tempfile import tempdir
from sanarch.lib.exceptions import CommandError
from sanarch.lib.utils.pacman import Pacman
from sanarch.lib.utils.bootloader import Bootloader, Grub, bootloader_helper
from sanarch.lib.disk.partition import Partition
from sanarch.lib.general import BootMode
from sanarch.lib.command import Command
from sanarch.lib import exceptions
from sanarch.lib.logger import Logger
#from sanarch.lib.menu import menu
from sanarch.lib import linuxcmd
import os
from sanarch.lib.config import Config
from sanarch.lib.disk.blockdevice import BlockDevice
import json


class ArchInstaller:
    LOG_DIR = '/tmp/archsan'
    LOG_FILENAME = 'arch-install.log'
    MAJOR_LOOP: int = 7
    MAJOR_ROM: int = 11
    FSTAB_PATH = "/mnt/etc/fstab"
    # /mnt is added because chroot command is not executed
    LOCALTIME_PATH = '/etc/localtime'
    LOCALE_GEN_PATH = '/mnt/etc/locale.gen'
    LOCALE_LANG_PATH = '/mnt/etc/locale.conf'
    LOCALE_KEYMAP_PATH = '/mnt/etc/vconsole.conf'
    HOSTNAME_PATH = '/mnt/etc/hostname'
    HOSTS_PATH = '/mnt/etc/hosts'
    SUDOFILE_PATH = '/mnt/etc/sudoers'

    def __init__(self, config_file, *, rootpass = None, userpass = None):
        self.boot_mode = BootMode.UNDEFINED

        self.config = Config(config_file)
        self.pacman = Pacman()

        self.blkdevs: list[BlockDevice] = []
        self.logger = Logger("Install-Log",log_dir=self.LOG_DIR, file_name=self.LOG_FILENAME)
        self.rootpass = rootpass
        self.userpass = userpass
        # self.logger.disable_console_output()
        
        self.__initBlkDevice()
        
    def __initBlkDevice(self):
        self.blkdevs = []
        for info in self.config.get_device_info():
            bdev_info = self.scan_blockdevice(info["device"]) 
            blk = BlockDevice(
                    name=bdev_info["name"],
                    size=bdev_info["size"],
                    path=bdev_info["path"],
                    model=bdev_info["model"],
                    wipe=info["wipe"],
                    part_info=info["partitions"],
                    skip_partition=info["skip-partitions"],
                    logger=self.logger
                )

            self.blkdevs.append(blk)


    def scan_blockdevice(self, device: str):
        res = linuxcmd.lsblk_json(device=device)

        info = json.loads(res.stdout)
        bdev = info["blockdevices"]
        if len(bdev) == 0:
            raise Exception(f'Device: {device} not Found')
        else:
            bdev = bdev[0]

        return bdev
        
    def verify_efi(self):
        if os.path.exists("/sys/firmware/efi/efivars"):
            self.logger.info("System is booted in UEFI mode.")
            self.boot_mode = BootMode.UEFI
            return True
        else:
            self.logger.warning("System is booted in BIOS mode.")
            self.boot_mode = BootMode.BIOS
            return False

    def check_iconnection(self):
        try:
            nc = Command("nc", ["-zw1", "archlinux.org", "443"], shell=True)
            cp = nc()
            self.logger.info("Verified Internet connectivity.")
        except Exception as e:
            self.logger.critical("No Internet Connection")
            raise exceptions.NoInternet()
        
        return cp.returncode == 0
    
    def update_sys_clock(self):
        try:
            Command("timedatectl", args = ["set-ntp true"], shell=True)()
            cp = Command("timedatectl", args = ["status"])()
            if "NTP service: active" in cp.stdout:
                self.logger.info("Updated System Clock.")
                return 0
            else:
                self.logger.error("Unable to update System Clock")
                return 1
        except Exception as e:
            raise exceptions.UpdateError(e)

    def partition_disk(self):
        for blkdev in self.blkdevs:
            try:
                blkdev.backup_partition_table()
                remove_partitions = self.config.get_remove_partitions(blkdev.path)
                blkdev.remove_partitions(remove_partitions)
                blkdev.write_partition()
                blkdev.format_partitions()
                blkdev.mount_partitions()
            except Exception as e:
                blkdev.load_partition_table_backup()
                self.logger.error(f"Unable to partition {blkdev.path}\n---\nError:\n{e}---\n")
                raise e

    def setup_parallel_download(self, arch_chroot = True):
        cpus = linuxcmd.nproc()
        self.pacman.setup_parallel_download(parallel_downloads=cpus+2, arch_chroot=arch_chroot)

    def install_base_packages(self):
        self.logger.info("Installing base packages")
        packages = self.config.base_packages
        linuxcmd.packstrap(packages)
        self.logger.info("Installed Base Packages")

    def generate_fstab(self):
        # Inform os about partition table updates
        try:
            Command('partprobe')()
        except Exception as e:
            self.logger.warning(f"partprobe unable to inform os about partition table updates\nError => {e}")

        path = Path(self.FSTAB_PATH)
        if path.exists():
            path.replace("/mnt/etc/fstab.bak")

        self.logger.debug("Generating fstab")
        args = ['-U', '/mnt']

        with open("/etc/fstab", "r") as fstab_default:
            default_content = fstab_default.readlines()

        with open(self.FSTAB_PATH, "w") as fstab:
            default_content.append("\n")
            fstab.writelines(default_content)

        with open(self.FSTAB_PATH, "a") as fstab:
            Command('genfstab', args=args, stdout=fstab)()

    def pacman_key_setup(self):
        Command('pacman-key', args=['--init'])(arch_chroot=True)
        Command('pacman-key', args=['--populate'])(arch_chroot=True)


    def set_time_zone(self):
        self.logger.debug("Setting timezone")
        timezone = self.config.timezone

        if not timezone:
            self.logger.warn("Warning Timezones not provided! Unable to set timezone")
            return 

        timezone_path = f'/usr/share/zoneinfo/{timezone["region"]}/{timezone["city"]}'

        if not Path(timezone_path).exists():
            raise Exception(f'Invalid timezone: {timezone["region"]}/{timezone["city"]}')

        ln = Command(name="ln", args=["-sf", timezone_path, self.LOCALTIME_PATH])
        ln(arch_chroot=True)

        hw = Command(name="hwclock", args=["--systohc"])
        hw(arch_chroot=True)

        self.logger.info("Updated timezone")

    def set_localization(self):
        self.logger.debug("Setting Localization information")
        path = self.LOCALE_GEN_PATH
        locales = self.config.locales

        with open(path, "r") as locale_gen_file:
            lines = locale_gen_file.readlines()

        for linenum, line in enumerate(lines):
            for locale in locales:
                if locale in line:
                    lines[linenum] = f'{locale}\n'
                    locales.remove(locale)
                    break

        with open(path, "w") as locale_gen_file:
            locale_gen_file.writelines(lines)
        
        lgen = Command(name = "locale-gen")
        lgen(arch_chroot=True)

        with open(self.LOCALE_LANG_PATH, "w") as locale_lang_file:
            line = f'LANG={self.config.locale_lang}\n'
            locale_lang_file.write(line)
        
        if self.config.locale_keymap:
            with open(self.LOCALE_KEYMAP_PATH, "w") as locale_keymap_file:
                line = f'KEYMAP={self.config.locale_keymap}\n'
                locale_keymap_file.write(line)
        
        self.logger.info("Updated localization information")

    def set_network_config(self):
        self.logger.debug("Configuring network")
        hostname = self.config.hostname
        HOSTS_LINE = f'127.0.0.1\tlocalhost\n::1\t\tlocalhost\n127.0.1.1\t{hostname}\n'
        with open(self.HOSTNAME_PATH, "w") as hostname_file:
            line = f'{hostname}\n'
            hostname_file.write(line)

        with open(self.HOSTS_PATH, "a") as hosts_file:
            hosts_file.write(f'\n{HOSTS_LINE}')
        
        self.logger.info("Successfully configured network")

    def set_root_password(self):
        self.logger.debug("Setting root password")
        
        import sys
        if self.rootpass:
            password = self.rootpass
        else:
            password = None
            print("Enter the root password: ")
        
        linuxcmd.passwd(password = password, arch_chroot=True)
        
        self.logger.debug("Updated root password")

    def setup_bootloader(self):
        esp = self.config.esp
        if self.config.bootloader:
            self.logger.debug("Installing bootloader")
            bootloader: Bootloader = bootloader_helper(self.config.bootloader)
            bootloader.install(esp, detect_other_os=self.config.detect_other_os)

            self.logger.info("Successfully installed bootloader")
        else:
            self.logger.warn("No bootloader specified! Skipping the installation.")

    def __set_sudo_previlage(self):
        self.logger.debug("Setting sudo previlages for users")
        
        WHEEL_LINE = '%wheel ALL=(ALL:ALL) ALL'

        with open(self.SUDOFILE_PATH, "r") as sudofile:
            lines = sudofile.readlines()

        for num, line in enumerate(lines):
            if WHEEL_LINE in line:
                lines[num] = WHEEL_LINE
                break
        
        Path(self.SUDOFILE_PATH).replace(f"{self.SUDOFILE_PATH}.bak")
        with open(self.SUDOFILE_PATH, "w") as sudofile:
            sudofile.writelines(lines)
        
        self.logger.debug("Updated sudo previlages for users")

    def setup_users(self):
        self.logger.debug("Setting up users")
        self.pacman.install(["sudo"])

        users = self.config.users
        if not users:
            return
        
        for user in users:
            username = user["name"]
            # Create the user
            self.logger.debug(f"Creating user {username}")
            try:
                linuxcmd.useradd(username, create_home=user["create-home"], arch_chroot=True)
            except CommandError as e:
                if e.return_code == 9:
                    # Log
                    print("user already exists")
                else:
                    raise e
            
            # Set the user password
            if username in self.userpass.keys():
                password = self.userpass[username]
            else:
                password = None
                print("Enter the password for", username)
            
            linuxcmd.passwd(user=username, password=password, arch_chroot=True)
            # Add groups to user
            linuxcmd.user_add_groups(user=username, groups=user["groups"], arch_chroot=True)  
            self.logger.info(f"Created user {username}")
        
        self.__set_sudo_previlage()


    def install_packages(self):
        self.logger.info("Installing packages")
        packages = self.config.packages
        if not packages:
            return

        try:
            self.pacman.install(packages)
        except CommandError as e:
            for line in e.msg.splitlines():
                if "error" in line:
                    res = line.split(":")
                    if res[1].strip().lower() == "target not found":
                        package = res[2].strip()
                        self.logger.warn(f"Package not found! Ignoring {package}")
                        packages.remove(package)
            self.pacman.install(packages)

        self.logger.info("Installed packages")

    def enable_serivces(self):
        self.logger.debug("Enabling system services")
        services = self.config.services
        if not services:
            return
        
        for service in services:
            linuxcmd.enable_sevice(service, arch_chroot=True)
        
        self.logger.info("Enabled system services")

    def run_after_scripts(self):
        TEMP_DIR = "/mnt/temp/archsan/scripts/"
        dest = Path(TEMP_DIR)
        dest.mkdir(parents=True, exist_ok=True)

        scripts = self.config.after_scripts
        for script in scripts:
            name = script["prog"]
            path:str = script["path"]

            if path[0] != "/":
                src = Path(__file__).parent.resolve() / f"{path}"
            else:
                src = Path(path)
            
            shutil.copy(src, dest)
            script_name = path.split("/")[-1]
            path = TEMP_DIR.removeprefix("/mnt") + script_name
            args = [path]

            if script["args"]:
                args += script["args"]

            self.logger.info(f"Running script {name} {' '.join(args)}")
            Command(name, args=args, capture_output=False)(arch_chroot=True)

    def update_context(self, curr_install_state):
        context = {"install_state": curr_install_state}
        Path("/tmp/archsan").mkdir(parents=True, exist_ok=True)
        with open("/tmp/archsan/context.json", "w") as context_file:
            json.dump(context, context_file)

    def install(self, install_state = 0):
        if install_state is None:
            install_state = 0
         
        curr_install_state = install_state
        try:
            self.verify_efi()
            self.check_iconnection()
            if install_state < 1:
                self.update_sys_clock()
                curr_install_state += 1
            if install_state < 2:
                self.partition_disk()
                curr_install_state += 1
            if install_state < 3:
                self.setup_parallel_download(arch_chroot=False)
                self.install_base_packages()
                curr_install_state += 1
            if install_state < 4:
                self.generate_fstab()
                curr_install_state += 1
                self.pacman_key_setup()
            if install_state < 5:
                self.set_time_zone()
                curr_install_state += 1
            if install_state < 6:
                self.set_localization()
                curr_install_state += 1
            if install_state < 7:
                self.set_network_config()
                curr_install_state += 1
            if install_state < 8:
                self.set_root_password()
                curr_install_state += 1
            if install_state < 9:
                self.setup_bootloader()
                curr_install_state += 1
            if install_state < 10:
                self.setup_users()
                curr_install_state += 1
            if install_state < 11:
                self.setup_parallel_download(arch_chroot=True)
                self.install_packages()
                curr_install_state += 1
            if install_state < 12:
                self.enable_serivces()
                curr_install_state += 1
            if install_state < 13:
                self.run_after_scripts()
                curr_install_state += 1

            self.update_context(curr_install_state)
        except exceptions.NoInternet as e:
            import sys
            self.logger.critical("No internet connection")
            sys.exit(1)
        except exceptions.UpdateError as e:
            self.logger.warn(f"Unable to Update System Clock\n---\nError:\n{e}\n---\n")
        except Exception as e:
            self.logger.critical(f'{e}\nExiting...')
            self.update_context(curr_install_state)
        
        
