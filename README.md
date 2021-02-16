# B9 Robot - Overview
A configurable Python daemon that dictates system notification messages audibly exclusive to Linux operating systems.

## Prerequisites
1.  Festival speech engine
2.  Python 3.6
3.  Pip
4.  VirtualEnv
5.  All other dependencies are recorded in `requirements.txt`.  To install run `pip -r requirements.txt` from the repository root.

# Install
There is an install script that has been tested on Ubuntu 20.04 (Focal).  For other distributions I'm afraid you're on your own.  

## Rant
I wasn't prepared for the absolute dependency hell that Python has become and I am still shocked that a custom install script is necessary for something so simple.  This is my first (and last) Python project I will invest time in.  Nobody has time for playing endless games of depedency whack-a-mole.

# Configuration
To configure this daemon see the sample configuration file enclosed in this repository.  Place the configuration file at `/etc/b9robot/mappings.yaml` even if that means moving and renaming the bundled `mappings.example.yaml`.  You can edit this configuration and send the _hang-up_ (`HUP`) signal to b9robot to automatically reload the configuration upon receipt of the next notification.

# Features
1.  Dictate only during set schedules (time of day, day of week, etc.)
1.  Disable dictation based on the presence (or absence) of window(s) that match title and/or class
1.  Enable or disable dictation based on the activity status of web cam(s) connected to your system
1.  Filter and route notification messages through chains of rules
1.  Transform notification messages through chains of regular expression pattern matching rules
1.  Limit the length of messages
