import argparse

def parse_userpass(userpass_list):
    user_list = []
    for userpass in userpass_list:
        user_password = userpass.split(":")
        user_list.append(user_password)
    
    return dict(user_list)
        

def init_argparse():
    parser = argparse.ArgumentParser(description="Automation tool for arch linux installation from profile")
    init_argparse_arguments(parser)
    args = parser.parse_args()
    args.userpass = parse_userpass(args.userpass)
    return args

def init_argparse_arguments(parser: argparse.ArgumentParser):
    parser.add_argument('config', type=str, help="path to config file")
    parser.add_argument('--resume', action='store_true', help="resume installation from the last success point")
    parser.add_argument('--rootpass', type=str, help="password for the root user")
    parser.add_argument('--userpass', nargs="*", type=str, help="password for non-root user | Format: {username}:{password} |")