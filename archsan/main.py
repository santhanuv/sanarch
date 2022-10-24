from archinstaller import ArchInstaller
from pathlib import Path
import json
from lib import parser

def main():
    CONTEXT_FILE_PATH = "/tmp/archsan/context.json"
    
    args = parser.init_argparse()
    if not Path(args.config).exists():
        raise Exception(f'Profile: {args.config} does not exist.')

    install_state = None
    if args.resume and Path(CONTEXT_FILE_PATH).exists():
        with open(CONTEXT_FILE_PATH) as context_file:
            data = json.load(context_file)
            install_state = data["install_state"]

    installer = ArchInstaller(args.config, userpass=args.userpass, rootpass=args.rootpass)
    installer.install(install_state=install_state)
    

if __name__ == '__main__':
    main()