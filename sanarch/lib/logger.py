import logging
from pathlib import Path
import sys

class LevelFilter(logging.Filter):
    def __init__(self, levelno):
        self.levelno = levelno

    def filter(self, record):
        return record.levelno == self.levelno

class CustomStreamHandler(logging.StreamHandler):
    def __init__(self, stream, name = None):
        super().__init__(stream)
        self.name = name
        

class Logger(logging.getLoggerClass()):
    """
        A Logger class to log information to console and files.
    """

    DEBUG_HANDLER_NAME = "debug"
    DEBUG_FORMAT = '[DEBUG] %(message)s'
    STDOUT_FORMAT = '[OK] %(message)s'
    STDERR_FORMAT = '[ERR] %(message)s'
    WARN_FORMAT = '[WARNING] %(message)s'
    FILE_FORMAT = '%(asctime)s - %(levelname)s : %(message)s'

    def __init__(self, name, log_dir = None, file_name = None):
        super().__init__(name)
        self.setLevel(logging.DEBUG)

        # Creating handler for logging debug to stdout
        self.debug_handler = CustomStreamHandler(sys.stdout, self.DEBUG_HANDLER_NAME)
        self.debug_handler.setLevel(logging.DEBUG)
        self.debug_handler.addFilter(LevelFilter(logging.DEBUG))
        self.debug_handler.setFormatter(logging.Formatter(self.DEBUG_FORMAT))

        # Creating handlers for logging to stdout
        self.stdout_handler = CustomStreamHandler(sys.stdout)
        self.stdout_handler.setLevel(logging.INFO)
        # self.stdout_handler.addFilter(lambda record: record.levelno == logging.INFO)
        self.stdout_handler.addFilter(LevelFilter(logging.INFO))
        self.stdout_handler.setFormatter(logging.Formatter(self.STDOUT_FORMAT))
        
        # Handler for warning in stderr or stdout
        self.warn_handler = CustomStreamHandler(sys.stderr)
        self.warn_handler.setLevel(logging.WARNING)
        self.warn_handler.addFilter(LevelFilter(logging.WARNING))
        self.warn_handler.setFormatter(logging.Formatter(self.WARN_FORMAT))

        # Handler for stderr
        self.stderr_handler = CustomStreamHandler(sys.stderr)
        self.stderr_handler.setLevel(logging.ERROR)
        self.stderr_handler.setFormatter(logging.Formatter(self.STDERR_FORMAT))

        # Enable console
        self.enable_console_output()

        # Setup log-file directory and path
        self.file_handler = None
        if log_dir and file_name:
            self.init_file_handler(log_dir, file_name)


    def init_file_handler(self, dir, filename):
        target = Path(dir) / filename
        path = Path(dir)

        try:
            # Backup log file if one already exists
            if target.exists():
                target.replace(target.with_suffix('.log.bak'))
        except Exception as e:
            print(f"Unable to backup log file\n{e}")
            
        try:
            path.mkdir(parents=True, exist_ok=True)
        except:
            print(f'Unable to create directory: {dir}\nDefault to ~/tmp/sanarch/{filename}')
            path = Path.home() / 'tmp/sanarch'
            path.mkdir(parents=True, exist_ok=True)
        
        self.log_file = path / filename

        # Handler for file
        self.file_handler = logging.FileHandler(self.log_file)
        self.file_handler.setLevel(logging.DEBUG)
        self.file_handler.setFormatter(logging.Formatter(self.FILE_FORMAT))
        
        # Enable file handler
        self.enable_file_output()

    def has_console_handler(self):
        return len([handler for handler in self.handlers if type(handler) == logging.StreamHandler]) > 0

    def has_file_handler(self):
        return len([handler for handler in self.handlers if type(handler) == logging.FileHandler]) > 0

    def has_debug_handler(self):
        return len([handler for handler in self.handlers if handler.name == self.DEBUG_HANDLER_NAME]) > 0

    def enable_console_output(self):
        if not self.has_console_handler():
            self.addHandler(self.stdout_handler)
            self.addHandler(self.warn_handler)
            self.addHandler(self.stderr_handler)

    def disable_console_output(self):
        if self.has_console_handler():
            self.removeHandler(self.stdout_handler)
            self.removeHandler(self.warn_handler)
            self.removeHandler(self.stderr_handler)

    def enable_file_output(self):
        if not self.file_handler:
            raise Exception("No log file specified")

        if not self.has_file_handler():
            self.addHandler(self.file_handler)

    def disable_file_output(self):
        if self.file_handler and self.has_file_handler():
            self.removeHandler(self.file_handler)
    
    def enable_debug_handler(self):
        if not self.has_debug_handler():
            self.addHandler(self.debug_handler)
        
    def disable_debug_handler(self):
        if self.has_debug_handler():
            self.removeHandler(self.debug_handler)
