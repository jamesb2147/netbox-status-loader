This software is designed to be used in conjunction with Netbox as a system to maintain state data for Netbox's IPAM functionality. Netbox is an excellent DCIM and "source of truth" with an awesome API.

# Install

Perform a pull from this Github and also make sure you have a copy of Samuel's "ping" module for python. You'll need to grab a fresh copy from here on Github as the pypi module is either outdated or another branch; it will *not* work with this code, nor will other forks, such as ping3. Trust me, I've tried. You can currently find this code here, and note that it was pulled as of 12/31/17: https://github.com/samuel/python-ping

# Configuration

Open ping_to_netbox.py in your favorite editor (e.g. nano) and READ THE FREAKING HEADERS! They've got big, bright "#" symbols to indicate this is a distinct, important section that you need to check out.

### Note on performance and multiprocessing
The original design of this application was single-threaded. It was split into a multiprocessing model to speed scanning due to needing to hit large prefixes without waiting for timeouts on every individual IP address serially. Due to this design, scaling up the number of processes requires substantial resources, both in CPU and RAM. Testing at 1000 processes in the pool on an Ubuntu VM with 2GB of RAM yielded a completely non-responsive system that had to be cold booted to restore functionality.

*DO NOT TOUCH THE THREAD POOL UNLESS YOU ARE PREPARED TO DEAL WITH A NON-RESPONSIVE SYSTEM*

Performance is still not great with the current design and it may be improved in the future by moving to a newer library, such as multi-ping.

### Defaults

By default, the application runs in a mode where it pulls IP address objects only from Netbox, then polls them and replaces them in Netbox. Be aware, in the current version of the application, this will destroy any existing description attached to an IP address. There are probably better ways to accomplish this. These may be adopted in the future.

### Initial load

This application was designed for an environment currently operating without an IPAM. Therefore, there is a mode for reading "prefix" objects from Netbox, pinging through the entire address space, and *only saving IP address objects that respond or have a DNS entry*. Why behave this way? Netbox has convenience methods for providing new, available IP addresses upon request and provisioning them. If we create IP address objects and fill the prefix space, how will Netbox know that these addresses are available? It will not know and will think the entire prefix space has been exhausted. That's a problem, so we intentionally do not populate the entire prefix space.

Also worth noting here is that there is an option for the lazy that is currently not fleshed out, which is to automatically perform a similar scan on all private IP address space. This does not currently work and trying it will fail. My advice is currently to populate Netbox with the RFC1918 space manually prior to running Netbox Status Loader in prefix mode, if that is your desired goal. Notably, prefixes can overlap in Netbox, so this should not be too big a concern.

Finally, the initial load is intended to be just that. Once Netbox has your current state IP space, it is expected that it will become the "source of truth" for your network forever after that. Therefore, it is recommended to only use the default mode to pull IP addresses only from Netbox. Certainly, running in the prefix mode is possible, to continue scanning for new rogue devices, etc. However, performance of this application is already currently very poor, and performing the initial load with any reasonable frequency is likely to result in only frustration due to the time required to process it. See the above notes about performance for more detail.

# Runtime

Also worth noting here that this is a python2 application. I've been testing it in Ubuntu with Python 2.7.14. Testing with python3 was unsuccessful and requires changes to the ping library in addition to a few tweaks to the application itself that have not themselves been tested as adjusting the ping library was never completed.

More details on how to install and use this software will be added here in the future.
