# Sanarch
## A script that installs arch linux automatically from a configuration file.

Sanarch is a simple script written in python to install arch linux from a configuration file. This makes it easier to re-install the system whenever the system breaks. The configurations for the system are specified in a yaml file. This project allows you to:

* Install the base system from a given configuration file.
* Further setup the system after the installation using a custom script.
* Custom script can be written in any scripting language.
* Script can be resumed after correcting any errors during the installation.

## How to use the script

Run the script using the command:
```
git clone https://github.com/santhanuv/sanarch.git
cd sanarch
python -m sanarch _root-password_ "username:_user-password_" _path-to-config-file_
```
