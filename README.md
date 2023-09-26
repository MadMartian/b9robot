# B9 Robot - Overview
A configurable Python daemon that dictates system notification messages audibly exclusive to Linux operating systems.  This has been tested in Ubuntu 20.04 and 22.04.

## Prerequisites
1.  Festival speech engine
2.  ~~Python 3.6~~ *Python v10 is now supported*
3.  Pip
4.  VirtualEnv
5.  All other dependencies are recorded in `requirements.txt`.  To install run `pip -r requirements.txt` from the repository root.

# Install
There is an install script that has been tested on Ubuntu 20.04 (Focal) and 22.04 (Jammy).  For other distributions I'm afraid you're on your own, I am not remotely responsible for the absolute mess that modern dependency management has become.  

## Rant
I wasn't prepared for the absolute dependency hell that Python has become and I am still shocked that a custom install script is necessary for something so simple.  What really gets me is that I have only ever heard a handful of engineers call out this disaster trainwreck of dependency management that modern software engineering has become.  Nobody has time for playing endless games of dependency whack-a-mole, where's your divine discontent?

It's a bit overkill installing *OpenCV* just to check if the video camera is turned-on, but I want to use abstractions to avoid platform-dependent behaviour.  I suppose, if I get really annoyed, I'll just call `lsof /dev/video%d` from Python and be done with it.

# Configuration
To configure this daemon see the sample configuration file enclosed in this repository.  Place the configuration file at `/etc/b9robot/mappings.yaml` even if that means moving and renaming the bundled `mappings.example.yaml`.  You can edit this configuration and send the _hang-up_ (`HUP`) signal to b9robot to automatically reload the configuration upon receipt of the next notification.

# Features
1.  Dictate only during set schedules (time of day, day of week, etc.)
1.  Disable dictation based on the presence (or absence) of window(s) that match title and/or class
1.  Enable or disable dictation based on the activity status of web cam(s) connected to your system
1.  Filter and route notification messages through chains of rules
1.  Transform notification messages through chains of regular expression pattern matching rules
1.  Limit the length of messages
