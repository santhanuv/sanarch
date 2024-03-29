# Sanarch
## A script that installs arch linux automatically from a configuration file.

Sanarch is a simple script written in python to install arch linux from a configuration file. This makes it easier to re-install the system whenever the system breaks. The configurations for the system are specified in a yaml file. This project allows you to:

* Install the base system from a given configuration file.
* Further setup the system after the installation using a custom script.
* Custom script can be written in any scripting language.
* Script can be resumed after correcting any errors during the installation.
* Supports installation with windows dual boot.

## How to use the script

### Command:
`python -m sanarch` when inside the root directory of the project or `sanarch` when in virtual enviroment can be used to invoke the script.
### Arguments:
#### Required Arguments:
`path-to-config-file` : Path to the config file used.<br/>
`root-password` : Password for the root user.<br/>
`username_:user-password` : Username and the password for that user.<br/>
#### Optional Arguments:
`--resume` : Retry installation from the last error.<br/>
#### To Run the script:
1. Boot the live environment.
2. Run the script using the command:
```
git clone https://github.com/santhanuv/sanarch.git
cd sanarch
python -m sanarch path-to-config-file "root-password" "username:user-password"
```
#### Example:
```
python -m sanarch profiles/default.yaml "user123" "archuser:user123"
```

**Example Configuration files are in profiles directory.**

## Modify or use the script in live environment with python virtual environment

1. Boot the live environment
2. Clone the repo and change into the directory
3. Create virtual environment
  `python -m venv venv`
4. Activate the virtual environment
  `source venv/bin/activate`
5. Install the package
  `python -m pip install -e .`
7. Run the script directly using sanarch command. 
  `sanarch path-to-config-file "root-password" "username:user-password"`
8. To deactivate the virtual enviroment run:
  `deactivate`

## Use Custom Scripts

Custom scripts can be used to setup the system after installation of the base system. Any scripting language can be used for this purpose. 
To use your custom scripts:
1. In the config file use `after-scripts` key to add a list of scripts to run.
2. Each item in the `after-scripts` list should contain the following keys:
  * `prog`: The program that is used to run the script. eg: bash, python
  * `path`: Path to the script.
  * `args`: Arguments that should be given to the script. 
  
## Logging

Logging information can be found in the /tmp/sanarch/arch-install.log. This can be used to debug the errors during the installation.
