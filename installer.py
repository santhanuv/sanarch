import functions, sys
from threading import Thread
from multiprocessing import Process

"""
    Calls the functions to install Arch Linux.
"""

# Parse the arguments given to the program
PART_FILE, CONF_FILE, DEFAULT = functions.argument_parsing()

# Settings the files and configurations That is needed for the installation.
functions.intialize_install(PART_FILE, CONF_FILE, DEFAULT)

# Create thread to check the internet connection and a process to install the arch system.
t1 = Thread(target=functions.ping, daemon=True)
p1 = Process(target=functions.install, daemon=True)

# Thread to print the messages that the threads and the process wants to output.
# A Queue from the multiprocessing module is used to pass the information. This queue is both thread
# and process safe.
t2 = Thread(target=functions.dequeue, args=(t1, p1),daemon=True)

# Starting the process and threads
t1.start()
p1.start()
t2.start()

# Wating for the threads to finish
t1.join()
p1.join()
t2.join()

print('Installation Completed Successfully. Please Reboot :)')
