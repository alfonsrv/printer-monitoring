# Printer Monitoring 🖨️ – via SNMP and Python

Automatic printer monitoring via SNMP as decentralized agents to allow for easy reporting and consumables monitoring 🖨️

## Overview ⚡

Maps the SNMP OID values for various printer variants, queries them and reports the values to a REST API-backend for further processing, storing and alerting. 
Please note the REST API-backend is not included; alternatively you can use SMTP to report data via emails.

Requires Python 3; to use, simply install the dependencies `pip install -r requirements.txt`, set up your configuration and run `python Printer-Monitoring.py --help` 🐍

Run once-twice a day; Monitor; ???; Profit 💥 


## Configuration 🛠️

Edit the configuration file `printer_config.txt` (JSON) and edit the desired printers and variants. 

1. `client`: Name used for identifying the tenant a printer belongs to
2. `proxy`: Send data to backend using a standard proxy, else leave empty
3. `token`: Token to authenticate data report against the backend
4. `printers`: List of all configured printers to query and monitor
    1. `ip`: IP address of the target printer
    2. `variant`:Most important setting for getting accurate data. This describes a printer's type to map the relevant OIDs for querying (see [**Variants**](#variants-📇))
    3. `serial`:
    3. ```desc``` - used for describing and identifying a printer, e.g. where it is
5. Test your configuration and accurate data output using `python Printer-Monitoring.py --debug`

To deploy and run regularly use *cron* or *Windows Task Scheduler*.


## Variants 📇

| Variant       | Description                                         |
| :------------ | :-------------------------------------------------- |
| `xerox`       | Big Xerox printers, e.g. WorkCentre, AltaLink       |
| `xeroxbw`     | Smaller Xerox printers; e.g. VersaLink              |
| `xeroxphaser` | Custom class for Xerox Phaser 7760                  |
| `xeroxWC3225` | Custom class for Xerox Workcenter 3225              |
| `hp`          | HP Color LasetJets etc                              |
| `hpbw`        | HP LaserJet normal (B/W)                            |
| `hpmfp`       | HP MFPs, in case the previous one does not work     |
| `HPM725BW`    | Custom class for HP M725                            |
| `KCSW`        | Kyocera B/W-Printers                                 |
| `OKI`         | OKI printers                                |
| `DICL`        | Develop ineo+ 450i                                  |



## Docker Deployment 🐋

Run Docker using the `Dockerfile` and following sample command:

```bash
docker build -t printermonitoring . \
    && docker run -d --name printermonitoring \
        --restart unless-stopped \
        -v ./printer_config.txt:/app/printer_config.txt:ro \
        printermonitoring \
    && docker logs --follow printermonitoring
```

This allows running the script on e.g. 
Alternatively consider using `docker-compose`

