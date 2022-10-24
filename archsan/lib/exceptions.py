from dataclasses import dataclass

class NoInternet(Exception):
    def __init__(self, msg = None):
        super().__init__(msg)
        
        if not msg:
            self.msg = "No Internet Connection"
        else:
            self.msg = msg
        

class UpdateError(Exception):
    def __init__(self, msg):
        super().__init__(self.msg)
        self.msg = msg


class CommandError(Exception):
    def __init__(self, msg, cmd, return_code):
        super().__init__(msg)
        self.msg = msg
        self.cmd = cmd
        self.return_code = return_code