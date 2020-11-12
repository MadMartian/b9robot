# B9 Robot - Overview
A configurable Python daemon that dictates system notification messages audibly exclusive to Linux operating systems.

## Prerequisites
This project requires Python 3.5, all other dependencies are recorded in `requirements.txt`.  To install run `pip -r requirements.txt` from the repository root.

# Configuration
To configure this daemon see the sample configuration file enclosed in this repository.  Place the configuration file at `/etc/b9robot/mappings.yaml` even if that means moving and renaming the bundled `mappings.example.yaml`.  You can edit this configuration and send the _hang-up_ (`HUP`) signal to b9robot to automatically reload the configuration upon receipt of the next notification.
