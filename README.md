# Printer Monitoring

### Overview

Printer Monitoring via SNMP and Reporting of a printer's consumables status (for mostly Xerox so far)  

The script is intended to be run as a remote service on a customer's server - called via Task Scheduler, which then gathers the data of one or multiple defined printers on the network via SNMP. It then reports the raw data via REST POST for further data processing and analysis to allow for maximum flexibility - it's mostly just dividing values to get percentages and then pushing them to an Excel or Google Docs Sheet.  

Mostly implemented Xerox so far, but should also work for other printers. Feel free to contribute new printer OID implementations for other brands.

### Configuration    

The configuration file ```printer_config.txt``` has to be in the same directory as the Python file.  

1. Client name is used for quickly identifying the tenant a printer belongs to
2. Setting a proxy or leaving it empty for reporting data to the remote endpoint
3. ```ip``` - IP address of the target printer
4. ```variant``` - is the most important setting for getting accurate data and describes a printer's type. A table for which variant to pick can be found below.
5. ```desc``` - used for describing and identifying a printer, e.g. where it is
6. Download and install requirements listed below on a target computer running this script
7. Test your configuration and accurate data output using ```<scriptname>.py debug```
8. Use Windows Task Scheduler or cronjobs to regularly execute the script

The provided printer.php is a PHP implementation of how the backend can fetch and write the data to MySQL. If you're not getting data, check your firewall ports and if SNMP is enabled on your printer(s).

```
### Currently available printer variants
xerox - usually color printers with full functionality e.g. WorkCentre oder AltaLink  
xeroxbw - usually smaller b&w printers, e.g. VersaLink
```

### Requirements  

+ Python3.7+  
+ pip install pysnmp requests
