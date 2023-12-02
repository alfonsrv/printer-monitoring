#!/usr/bin/env python3
# -*- coding: utf-8 -*-

r"""
Description:
	1) Connects to printers and reads its
		predefined values via SNMP.

	2) Reports values to URL.

Values:
	Name, S/N, Prints, Toner, ...

	[!] -1 means no value on OID; usually happens
		if a printer doesn't support the
		  requested function
	[!] -404 Timeout
	[!] -401 Unhandled Exception

"""

__author__ = 'Rau Systemberatung GmbH, 2024'
__copyright__ = '(c) Rau Systemberatung GmbH, 2024'
__version__ = '1.30'
__email__ = 'info@rausys.de'
__python__ = '3.x'
__service__ = 'PrinterMonitoring'


from pysnmp.entity.rfc3413.oneliner import cmdgen
from pysnmp.proto import rfc1905
from datetime import datetime, timezone
import argparse
import requests
import json

import os
from enum import Enum
import logging
import logging.handlers


BACKEND = 'https://sys.rau.biz/api/printer/'
HEADERS = {
    'Authentication': '1337Auth0rizedPrinterz#',
    'Content-Type': 'application/json; charset=utf-8',
    'User-Agent': f'RAUSYS Automation - Printers {__version__}',
}
PROXIES = {
    'http':'',
    'https':'',
}

os.chdir(os.path.realpath(os.path.join(os.getcwd(), os.path.dirname(__file__))))
LOG_LEVEL = logging.INFO  # logging.DEBUG // .ERROR...
LOG_FILE = 'RauSys-Monitoring.log'
LOG_PATH = os.path.join(os.getcwd(), LOG_FILE)
logging.basicConfig(
    format='%(asctime)s - [%(levelname)s] %(message)s',
    level=LOG_LEVEL,
    handlers=[
        logging.StreamHandler(),
        logging.handlers.RotatingFileHandler(
            LOG_PATH,
            maxBytes=5000000,   # 10 MB
            backupCount=3
        )
    ]
)

logger = logging.getLogger(__name__)


class PrinterConsumable():
    """ Hilfsklasse für Drucker Verbrauchsmaterialien """

    class Consumable(Enum):
        FUSER = 'FUSER'
        CLEANER = 'CLEANER'
        TRANSFER = 'TRANSFER'
        WASTE = 'WASTE'
        BLACK_TONER = 'BLACK_TONER'
        CYAN_TONER = 'CYAN_TONER'
        MAGENTA_TONER = 'MAGENTA_TONER'
        YELLOW_TONER = 'YELLOW_TONER'
        BLACK_DRUM = 'BLACK_DRUM'
        CYAN_DRUM = 'CYAN_DRUM'
        MAGENTA_DRUM = 'MAGENTA_DRUM'
        YELLOW_DRUM = 'YELLOW_DRUM'

    def __init__(self, name, capacity, remaining, type):
        logger.debug(f'|--> {type} {name}')
        self.name = name
        self.capacity = int(capacity) if capacity and capacity.isdigit() else None
        self.remaining = int(remaining) if isinstance(remaining, str) and remaining.isdigit() else None  # can be 0
        self.type = type.value
        if not self.initialized: logger.warning(f'{self} did not initialize properly!')

    def __str__(self) -> str:
        if not self.initialized: return f'[{self.type}] – no data –'
        return f'[{self.type}] {self.name} ({self.remaining}/{self.capacity}) {self.percentage}%'

    @property
    def percentage(self) -> int:
        if self.remaining is None or self.capacity is None: return None
        z = self.remaining / self.capacity
        if z > 1 or z < 0:
            z = self.capacity / self.remaining
        return int(round(z,2)*100)

    @property
    def initialized(self):
        """ Hilfsfunktion um zu evaluieren, ob Consumable vollständig
        initialisiert wurde oder nicht """
        return self.capacity


class Printer():
    oid_printer_name = '1.3.6.1.2.1.1.5.0'
    oid_printer_model = '1.3.6.1.2.1.25.3.2.1.3.1'
    oid_printer_meta = '1.3.6.1.2.1.1.1.0'
    # alternativ 1.3.6.1.4.1.2699.1.2.1.2.1.1.3.1
    # alternativ2 1.3.6.1.2.1.1.1.0
    oid_printer_serial = '1.3.6.1.2.1.43.5.1.1.17.1'
    # alternativ SN: 1.3.6.1.4.1.253.8.53.3.2.1.3.1

    # Usage/Prints Details
    oid_print_count = '1.3.6.1.4.1.253.8.53.13.2.1.6.1.20.1'
    oid_print_color = '1.3.6.1.4.1.253.8.53.13.2.1.6.1.20.33'
    oid_print_mono = '1.3.6.1.4.1.253.8.53.13.2.1.6.1.20.34'

    # Fixiereinheit/Fuser Kit
    oid_fuser_name = '1.3.6.1.2.1.43.11.1.1.6.1.9'
    oid_fuser_capacity = '1.3.6.1.2.1.43.11.1.1.8.1.9'
    oid_fuser_remaining = '1.3.6.1.2.1.43.11.1.1.9.1.9'

    # Resttonbehälter/Waste Cartridge
    oid_waste_name = '1.3.6.1.2.1.43.11.1.1.6.1.10'
    oid_waste_capacity = '1.3.6.1.2.1.43.11.1.1.8.1.10'
    oid_waste_remaining = '1.3.6.1.2.1.43.11.1.1.9.1.10'

    # Bandreiniger/Transfer Belt Cleaner Kit
    oid_cleaner_name = '1.3.6.1.2.1.43.11.1.1.6.1.11'
    oid_cleaner_capacity = '1.3.6.1.2.1.43.11.1.1.8.1.11'
    oid_cleaner_remaining = '1.3.6.1.2.1.43.11.1.1.9.1.11'

    # Transferrolle/Transfer Roller
    oid_transfer_name = '1.3.6.1.2.1.43.11.1.1.6.1.12'
    oid_transfer_capacity = '1.3.6.1.2.1.43.11.1.1.8.1.12'
    oid_transfer_remaining = '1.3.6.1.2.1.43.11.1.1.9.1.12'

    ## Toner ##########
    oid_black_toner_name = '1.3.6.1.2.1.43.11.1.1.6.1.1'
    oid_black_toner_capacity = '1.3.6.1.2.1.43.11.1.1.8.1.1'
    oid_black_toner_remaining = '1.3.6.1.2.1.43.11.1.1.9.1.1'

    oid_cyan_toner_name = '1.3.6.1.2.1.43.11.1.1.6.1.2'
    oid_cyan_toner_capacity = '1.3.6.1.2.1.43.11.1.1.8.1.2'
    oid_cyan_toner_remaining = '1.3.6.1.2.1.43.11.1.1.9.1.2'

    oid_magenta_toner_name = '1.3.6.1.2.1.43.11.1.1.6.1.3'
    oid_magenta_toner_capacity = '1.3.6.1.2.1.43.11.1.1.8.1.3'
    oid_magenta_toner_remaining = '1.3.6.1.2.1.43.11.1.1.9.1.3'

    oid_yellow_toner_name = '1.3.6.1.2.1.43.11.1.1.6.1.4'
    oid_yellow_toner_capacity = '1.3.6.1.2.1.43.11.1.1.8.1.4'
    oid_yellow_toner_remaining = '1.3.6.1.2.1.43.11.1.1.9.1.4'

    ## Bildtrommel ##########
    oid_black_drum_name = '1.3.6.1.2.1.43.11.1.1.6.1.5'
    oid_black_drum_capacity = '1.3.6.1.2.1.43.11.1.1.8.1.5'
    oid_black_drum_remaining = '1.3.6.1.2.1.43.11.1.1.9.1.5'

    oid_cyan_drum_name = '1.3.6.1.2.1.43.11.1.1.6.1.6'
    oid_cyan_drum_capacity = '1.3.6.1.2.1.43.11.1.1.8.1.6'
    oid_cyan_drum_remaining = '1.3.6.1.2.1.43.11.1.1.9.1.6'

    oid_magenta_drum_name = '1.3.6.1.2.1.43.11.1.1.6.1.7'
    oid_magenta_drum_capacity = '1.3.6.1.2.1.43.11.1.1.8.1.7'
    oid_magenta_drum_remaining = '1.3.6.1.2.1.43.11.1.1.9.1.7'

    oid_yellow_drum_name = '1.3.6.1.2.1.43.11.1.1.6.1.8'
    oid_yellow_drum_capacity = '1.3.6.1.2.1.43.11.1.1.8.1.8'
    oid_yellow_drum_remaining = '1.3.6.1.2.1.43.11.1.1.9.1.8'

    def __init__(self, ip, description, kunde, serial, *args, port=161, community='public', **kwargs):
        self.ip = ip
        self.kunde = kunde
        self.serial = serial
        self.description = description
        self.variant = type(self).__name__.lower()

        self.port = port
        self.community = community
        self.version = __version__
        self.status = 'ERROR'
        self.status = 'OK' if self.ping() else 'TIMEOUT'

    def to_json(self) -> dict:
        x = self.__dict__
        consumables = x.pop('consumables', list())
        x['consumables'] = list()
        for consumable in consumables:
            x['consumables'].append(consumable.__dict__)
        return x

    def initialize_values(self):
        logger.info(f'[>] Initialisiere Drucker {self.description} [{self.ip}]...')
        self.name = self.query_snmp(self.oid_printer_name)
        self.model = self.query_snmp(self.oid_printer_model)
        #self.serial = self.query_snmp(self.oid_printer_serial)
        self.meta = self.query_snmp(self.oid_printer_meta)

        self.print_count = self.query_snmp(self.oid_print_count)
        self.print_color = self.query_snmp(self.oid_print_color)
        self.print_mono = self.query_snmp(self.oid_print_mono)

        # Fallback um print_count vollständig zu initialisieren
        if not self.print_count:
            self.print_count = (self.print_color or 0) + (self.print_mono or 0)
            if not self.print_count: self.print_count = None

        self.consumables = []

        for consumable in PrinterConsumable.Consumable:
            # wenn oid_<consumable>_capacity gesetzt ist (also falls Variable vorhanden und
            # mit Wert belegt ist), initialisieren
            if getattr(self, f'oid_{consumable.value.lower()}_capacity'):
                logger.debug(f'Detected {consumable.value} as being present in OIDs')
                oid_name = getattr(self, f'oid_{consumable.value.lower()}_name')
                oid_capacity = getattr(self, f'oid_{consumable.value.lower()}_capacity')
                oid_remaining = getattr(self, f'oid_{consumable.value.lower()}_remaining')
                consumable_instance = PrinterConsumable(
                    name=self.query_snmp(oid_name),
                    capacity=self.query_snmp(oid_capacity),
                    remaining=self.query_snmp(oid_remaining),
                    type=consumable
                )

                if consumable_instance.initialized: self.consumables.append(consumable_instance)

    def ping(self) -> bool:
        if self.query_snmp(self.oid_printer_name):
            logger.info(f'[>] Drucker online, {self.description} [{self.ip}]')
            return True
        logger.error(f'Drucker nicht erreichbar oder "oid_printer_name" nicht auflösbar, {self.description} [{self.ip}]')
        return False

    def query_snmp(self, oid: str):
        """ SNMP Abfrage für angegebene OID """

        if self.status == 'TIMEOUT': return None
        if not oid: return None

        logger.debug(f'Querying {oid}...')
        cmdGen = cmdgen.CommandGenerator()
        error_indicator, error_status, error_index, binds = cmdGen.getCmd(
            #cmdgen.CommunityData(self.community, mpModel=0),
            cmdgen.CommunityData(self.community),
            cmdgen.UdpTransportTarget((self.ip, self.port)), oid)

        # Check for errors and print out results
        if error_indicator:
            logger.error(f'{error_indicator} for {self.ip}')
            return None

        elif error_status:
            logger.error(f'{error_status} at {error_index and binds[int(error_index)-1] or "?"}')
            return None

        for name, val in binds:
            logger.debug(f'{name} = {val}')
            # Evaluiert, ob kein Wert an OID; kein Wert an OID = -1
            if val is None or isinstance(val, rfc1905.NoSuchInstance) or isinstance(val, rfc1905.NoSuchObject):
                logger.debug(f'No OID such object!...')
                return None
            logger.debug(f'Returning OID value: {val}')
            return str(val).rstrip('\x00')

    def get_consumable(self, name: str) -> PrinterConsumable:
        """ Hilfsfunktion um Consumable zurückzugeben """
        for consumable in self.consumables:
            if consumable.type.lower() == name.lower():
                return consumable
        return '- nicht konfiguriert -'


class Xerox(Printer):
    """ Druckervariante normaler Xerox Drucker,
    der als Printer-Referenzobjekt dient. """
    pass


class XeroxC8130(Printer):
    """ Druckervariante Xerox Altalink C8130 (unserer) """
    # Resttonbehälter/Waste Cartridge
    oid_waste_name = '1.3.6.1.2.1.43.11.1.1.6.1.9'
    oid_waste_capacity = '1.3.6.1.2.1.43.11.1.1.8.1.9'
    oid_waste_remaining = '1.3.6.1.2.1.43.11.1.1.9.1.9'
    # Transferrolle/Transfer Roller
    oid_transfer_name = '1.3.6.1.2.1.43.11.1.1.6.1.11'
    oid_transfer_capacity = '1.3.6.1.2.1.43.11.1.1.8.1.11'
    oid_transfer_remaining = '1.3.6.1.2.1.43.11.1.1.9.1.11'
    # Bandreiniger/Transfer Belt Cleaner Kit
    oid_cleaner_name = '1.3.6.1.2.1.43.11.1.1.6.1.10'
    oid_cleaner_capacity = '1.3.6.1.2.1.43.11.1.1.8.1.10'
    oid_cleaner_remaining = '1.3.6.1.2.1.43.11.1.1.9.1.10'


class XeroxBW(Printer):

    def initialize_values(self):
        Printer.initialize_values(self)
        consumables = []
        # Append consumables in this list with a manually overwritten type
        manual_consumables = [
            PrinterConsumable.Consumable.FUSER
        ]
        remaining_status = lambda capacity, remaining: "1" if self.query_snmp(remaining) == "-3" and self.query_snmp(capacity) == "-2" else "0"

        for manual_consumable in manual_consumables:
            # check consumable has not been initialized automatically previously
            if manual_consumable.value in [consumable.type for consumable in self.consumables]:
                logger.warning(f'Manual Consumable {manual_consumable.value} initialization failed, because it was ' \
                    'already added during the automatic routine')
                continue

            # initialize based on manual OID overwrites
            capacity_oid = getattr(self, f'oid_{manual_consumable.value.lower()}_capacity_manual')
            remaining_oid = getattr(self, f'oid_{manual_consumable.value.lower()}_remaining_manual')
            name_oid = getattr(self, f'oid_{manual_consumable.value.lower()}_name_manual')
            consumable = PrinterConsumable(
                type=manual_consumable,
                name=self.query_snmp(name_oid),
                capacity="1",
                remaining=remaining_status(capacity_oid, remaining_oid)
            )
            if consumable.initialized: self.consumables.append(consumable)

    oid_printer_name = '1.3.6.1.2.1.1.1.0'

    # Fixiereinheit/Fuser Kit
    oid_fuser_name_manual = '1.3.6.1.2.1.43.11.1.1.6.1.40'
    oid_fuser_capacity_manual =  '1.3.6.1.2.1.43.11.1.1.8.1.40'
    oid_fuser_remaining_manual = '1.3.6.1.2.1.43.11.1.1.9.1.40'

    oid_fuser_name = None
    oid_fuser_capacity = None
    oid_fuser_remaining = None
    
    """ Druckervariante Xerox Schwarzweiß """
    oid_black_drum_name = '1.3.6.1.2.1.43.11.1.1.6.1.6'
    oid_black_drum_remaining = '1.3.6.1.2.1.43.11.1.1.9.1.6'
    oid_black_drum_capacity = '1.3.6.1.2.1.43.11.1.1.8.1.6'

    # Resttonbehälter/Waste Cartridge
    oid_waste_name = None
    oid_waste_capacity = None
    oid_waste_remaining = None

    # Bandreiniger/Transfer Belt Cleaner Kit
    oid_cleaner_name = None
    oid_cleaner_capacity = None
    oid_cleaner_remaining = None

    # Transferrolle/Transfer Roller
    oid_transfer_name = None
    oid_transfer_capacity = None
    oid_transfer_remaining = None

    oid_cyan_toner_name = None
    oid_cyan_toner_capacity = None
    oid_cyan_toner_remaining = None

    oid_magenta_toner_name = None
    oid_magenta_toner_capacity = None
    oid_magenta_toner_remaining = None

    oid_yellow_toner_name = None
    oid_yellow_toner_capacity = None
    oid_yellow_toner_remaining = None

    ## Bildtrommel ##########
    oid_magenta_drum_name = None
    oid_magenta_drum_capacity = None
    oid_magenta_drum_remaining = None

    oid_cyan_drum_name = None
    oid_cyan_drum_capacity = None
    oid_cyan_drum_remaining = None

    oid_yellow_drum_name = None
    oid_yellow_drum_capacity = None
    oid_yellow_drum_remaining = None


class XeroxWC3225(Printer):
    """ Druckervariante Xerox WorkCentre 3225 """
    oid_black_drum_name = '1.3.6.1.2.1.43.11.1.1.6.1.2'
    oid_black_drum_remaining = '1.3.6.1.2.1.43.11.1.1.9.1.2'
    oid_black_drum_capacity = '1.3.6.1.2.1.43.11.1.1.8.1.2'
    oid_cyan_toner_name = '1.3.6.1.2.1.43.11.1.1.6.1.5'
    oid_cyan_toner_remaining = '1.3.6.1.2.1.43.11.1.1.9.1.5'
    oid_cyan_toner_capacity = '1.3.6.1.2.1.43.11.1.1.8.1.5'


class XeroxVLB405(XeroxBW):
    """ Druckervariante Xerox VersaLink B400 und B405 """
    def initialize_values(self):
        Printer.initialize_values(self)
        consumables = []
        # Append consumables in this list with a manually overwritten type
        manual_consumables = [
            PrinterConsumable.Consumable.CLEANER
        ]
        remaining_status = lambda capacity, remaining: "1" if self.query_snmp(remaining) == "-3" and self.query_snmp(capacity) == "-2" else "0"

        for manual_consumable in manual_consumables:
            # check consumable has not been initialized automatically previously
            if manual_consumable.value in [consumable.type for consumable in self.consumables]:
                logger.warning(f'Manual Consumable {manual_consumable.value} initialization failed, because it was ' \
                    'already added during the automatic routine')
                continue

            # initialize based on manual OID overwrites
            capacity_oid = getattr(self, f'oid_{manual_consumable.value.lower()}_capacity_manual')
            remaining_oid = getattr(self, f'oid_{manual_consumable.value.lower()}_remaining_manual')
            name_oid = getattr(self, f'oid_{manual_consumable.value.lower()}_name_manual')
            consumable = PrinterConsumable(
                type=manual_consumable,
                name=self.query_snmp(name_oid),
                capacity="1",
                remaining=remaining_status(capacity_oid, remaining_oid)
            )
            if consumable.initialized: self.consumables.append(consumable)

    # Wartungs Kit
    oid_cleaner_name_manual = '1.3.6.1.2.1.43.11.1.1.6.1.40'
    oid_cleaner_capacity_manual = '1.3.6.1.2.1.43.11.1.1.8.1.40'
    oid_cleaner_remaining_manual = '1.3.6.1.2.1.43.11.1.1.9.1.40'


class XeroxVLC405(Printer):
    """ Druckervariante Xerox VersaLink C405 """
    def initialize_values(self):
        Printer.initialize_values(self)
        consumables = []
        # Append consumables in this list with a manually overwritten type
        manual_consumables = [
            PrinterConsumable.Consumable.FUSER,
            PrinterConsumable.Consumable.CLEANER,
            PrinterConsumable.Consumable.WASTE
        ]
        remaining_status = lambda capacity, remaining: "1" if self.query_snmp(remaining) == "-3" and self.query_snmp(capacity) == "-2" else "0"

        for manual_consumable in manual_consumables:
            # check consumable has not been initialized automatically previously
            if manual_consumable.value in [consumable.type for consumable in self.consumables]:
                logger.warning(f'Manual Consumable {manual_consumable.value} initialization failed, because it was ' \
                    'already added during the automatic routine')
                continue

            # initialize based on manual OID overwrites
            capacity_oid = getattr(self, f'oid_{manual_consumable.value.lower()}_capacity_manual')
            remaining_oid = getattr(self, f'oid_{manual_consumable.value.lower()}_remaining_manual')
            name_oid = getattr(self, f'oid_{manual_consumable.value.lower()}_name_manual')
            consumable = PrinterConsumable(
                type=manual_consumable,
                name=self.query_snmp(name_oid),
                capacity="1",
                remaining=remaining_status(capacity_oid, remaining_oid)
            )
            if consumable.initialized: self.consumables.append(consumable)

    oid_cyan_toner_name = '1.3.6.1.2.1.43.11.1.1.6.1.4'
    oid_cyan_toner_capacity = '1.3.6.1.2.1.43.11.1.1.8.1.4'
    oid_cyan_toner_remaining = '1.3.6.1.2.1.43.11.1.1.9.1.4'
    oid_yellow_toner_name = '1.3.6.1.2.1.43.11.1.1.6.1.2'
    oid_yellow_toner_capacity = '1.3.6.1.2.1.43.11.1.1.8.1.2'
    oid_yellow_toner_remaining = '1.3.6.1.2.1.43.11.1.1.9.1.2'

    # Fixiereinheit/Fuser Kit

    oid_fuser_name_manual = '1.3.6.1.2.1.43.11.1.1.6.1.12'
    oid_fuser_capacity_manual = '1.3.6.1.2.1.43.11.1.1.8.1.12'
    oid_fuser_remaining_manual = '1.3.6.1.2.1.43.11.1.1.9.1.12'

    oid_fuser_name = None
    oid_fuser_capacity = None
    oid_fuser_remaining = None

    # Resttonbehälter/Waste Cartridge
    oid_waste_name_manual = '1.3.6.1.2.1.43.11.1.1.6.1.5'
    oid_waste_capacity_manual = '1.3.6.1.2.1.43.11.1.1.8.1.5'
    oid_waste_remaining_manual = '1.3.6.1.2.1.43.11.1.1.9.1.5'

    oid_waste_name = None
    oid_waste_capacity = None
    oid_waste_remaining = None

    # Bandreiniger/Transfer Belt Cleaner Kit
    oid_cleaner_name_manual = '1.3.6.1.2.1.43.11.1.1.6.1.39'
    oid_cleaner_capacity_manual = '1.3.6.1.2.1.43.11.1.1.8.1.39'
    oid_cleaner_remaining_manual = '1.3.6.1.2.1.43.11.1.1.9.1.39'

    oid_cleaner_name = None
    oid_cleaner_capacity = None
    oid_cleaner_remaining = None

    # Transferrolle/Transfer Roller
    oid_transfer_name = None
    oid_transfer_capacity = None
    oid_transfer_remaining = None

    ## Bildtrommel ##########
    oid_black_drum_name = '1.3.6.1.2.1.43.11.1.1.6.1.41'
    oid_black_drum_capacity = '1.3.6.1.2.1.43.11.1.1.8.1.41'
    oid_black_drum_remaining = '1.3.6.1.2.1.43.11.1.1.9.1.41'

    oid_cyan_drum_name = None
    oid_cyan_drum_capacity = None
    oid_cyan_drum_remaining = None

    oid_magenta_drum_name = None
    oid_magenta_drum_capacity = None
    oid_magenta_drum_remaining = None

    oid_yellow_drum_name = None
    oid_yellow_drum_capacity = None
    oid_yellow_drum_remaining = None


class XeroxVLC505S(XeroxVLC405):
    def initialize_values(self):
        Printer.initialize_values(self)
        consumables = []
        # Append consumables in this list with a manually overwritten type
        manual_consumables = [
            PrinterConsumable.Consumable.FUSER,
            PrinterConsumable.Consumable.CLEANER,
            PrinterConsumable.Consumable.WASTE,
            PrinterConsumable.Consumable.TRANSFER
        ]
        remaining_status = lambda capacity, remaining: "1" if self.query_snmp(remaining) == "-3" and self.query_snmp(capacity) == "-2" else "0"

        for manual_consumable in manual_consumables:
            # check consumable has not been initialized automatically previously
            if manual_consumable.value in [consumable.type for consumable in self.consumables]:
                logger.warning(f'Manual Consumable {manual_consumable.value} initialization failed, because it was ' \
                    'already added during the automatic routine')
                continue

            # initialize based on manual OID overwrites
            capacity_oid = getattr(self, f'oid_{manual_consumable.value.lower()}_capacity_manual')
            remaining_oid = getattr(self, f'oid_{manual_consumable.value.lower()}_remaining_manual')
            name_oid = getattr(self, f'oid_{manual_consumable.value.lower()}_name_manual')
            consumable = PrinterConsumable(
                type=manual_consumable,
                name=self.query_snmp(name_oid),
                capacity="1",
                remaining=remaining_status(capacity_oid, remaining_oid)
            )
            if consumable.initialized: self.consumables.append(consumable)

    # Einzugsrolle Behälter 1
    oid_transfer_name = None
    oid_transfer_capacity = None
    oid_transfer_remaining = None

    oid_transfer_name_manual = '1.3.6.1.2.1.43.11.1.1.6.1.18'
    oid_transfer_capacity_manual = '1.3.6.1.2.1.43.11.1.1.8.1.18'
    oid_transfer_remaining_manual = '1.3.6.1.2.1.43.11.1.1.9.1.18'


    # Toner (swap cyan with yellow)
    oid_cyan_toner_name = '1.3.6.1.2.1.43.11.1.1.6.1.4'
    oid_cyan_toner_capacity = '1.3.6.1.2.1.43.11.1.1.8.1.4'
    oid_cyan_toner_remaining = '1.3.6.1.2.1.43.11.1.1.9.1.4'

    oid_yellow_toner_name = '1.3.6.1.2.1.43.11.1.1.6.1.2'
    oid_yellow_toner_capacity = '1.3.6.1.2.1.43.11.1.1.8.1.2'
    oid_yellow_toner_remaining = '1.3.6.1.2.1.43.11.1.1.9.1.2'

    # Fixiereinheit/Fuser Kit

    oid_fuser_name_manual = '1.3.6.1.2.1.43.11.1.1.6.1.12'
    oid_fuser_capacity_manual = '1.3.6.1.2.1.43.11.1.1.8.1.12'
    oid_fuser_remaining_manual = '1.3.6.1.2.1.43.11.1.1.9.1.12'

    oid_fuser_name = None
    oid_fuser_capacity = None
    oid_fuser_remaining = None

    # Sammelbehälter (Waste?)
    oid_waste_name_manual = '1.3.6.1.2.1.43.11.1.1.6.1.5'
    oid_waste_capacity_manual = '1.3.6.1.2.1.43.11.1.1.8.1.5'
    oid_waste_remaining_manual = '1.3.6.1.2.1.43.11.1.1.9.1.5'

    oid_waste_name = None
    oid_waste_capacity = None
    oid_waste_remaining = None

    # Wartungskit
    oid_cleaner_name_manual = '1.3.6.1.2.1.43.11.1.1.6.1.39'
    oid_cleaner_capacity_manual = '1.3.6.1.2.1.43.11.1.1.8.1.39'
    oid_cleaner_remaining_manual = '1.3.6.1.2.1.43.11.1.1.9.1.39'

    oid_cleaner_name = None
    oid_cleaner_capacity = None
    oid_cleaner_remaining = None

    ## Bildtrommel ##########
    oid_black_drum_name = '1.3.6.1.2.1.43.11.1.1.6.1.6'
    oid_black_drum_capacity = '1.3.6.1.2.1.43.11.1.1.8.1.6'
    oid_black_drum_remaining = '1.3.6.1.2.1.43.11.1.1.9.1.6'

    oid_yellow_drum_name = '1.3.6.1.2.1.43.11.1.1.6.1.7'
    oid_yellow_drum_capacity = '1.3.6.1.2.1.43.11.1.1.8.1.7'
    oid_yellow_drum_remaining = '1.3.6.1.2.1.43.11.1.1.9.1.7'

    oid_magenta_drum_name = '1.3.6.1.2.1.43.11.1.1.6.1.8'
    oid_magenta_drum_capacity = '1.3.6.1.2.1.43.11.1.1.8.1.8'
    oid_magenta_drum_remaining = '1.3.6.1.2.1.43.11.1.1.9.1.8'

    oid_cyan_drum_name = '1.3.6.1.2.1.43.11.1.1.6.1.9'
    oid_cyan_drum_capacity = '1.3.6.1.2.1.43.11.1.1.8.1.9'
    oid_cyan_drum_remaining = '1.3.6.1.2.1.43.11.1.1.9.1.9'


class HP(Printer):
    """ Druckervariante regulärer HP LaserJet Color. """
    oid_printer_name = '1.3.6.1.2.1.43.5.1.1.16.1'

    # Usage/Prints Details
    oid_print_count = '1.3.6.1.4.1.11.2.3.9.4.2.1.1.16.1.9.0'
    oid_print_color = '1.3.6.1.4.1.11.2.3.9.4.2.1.1.16.1.10.0'
    oid_print_mono = '1.3.6.1.4.1.11.2.3.9.4.2.1.1.16.1.11.0'


class HPBW(Printer):

    # Usage/Prints Details
    oid_print_count = '1.3.6.1.4.1.11.2.3.9.4.2.1.1.16.1.9.0'

    # Fixiereinheit/Fuser Kit
    oid_fuser_name = '1.3.6.1.2.1.43.11.1.1.6.1.2'
    oid_fuser_capacity = '1.3.6.1.2.1.43.11.1.1.8.1.2'
    oid_fuser_remaining = '1.3.6.1.2.1.43.11.1.1.9.1.2'

    ## damit der Rest -1 zurückgibt...
    oid_print_color = None
    oid_cyan_toner_name = None
    oid_cyan_toner_capacity = None
    oid_cyan_toner_remaining = None

    oid_magenta_toner_name = None
    oid_magenta_toner_capacity = None
    oid_magenta_toner_remaining = None

    oid_yellow_toner_name = None
    oid_yellow_toner_capacity = None
    oid_yellow_toner_remaining = None

    ## Bildtrommel ##########
    oid_black_drum_name = None
    oid_black_drum_capacity = None
    oid_black_drum_remaining = None

    oid_cyan_drum_name = None
    oid_cyan_drum_capacity = None
    oid_cyan_drum_remaining = None

    oid_magenta_drum_name = None
    oid_magenta_drum_capacity = None
    oid_magenta_drum_remaining = None

    oid_yellow_drum_name = None
    oid_yellow_drum_capacity = None
    oid_yellow_drum_remaining = None


class HPMFP(HP):
    oid_print_count = '1.3.6.1.2.1.43.10.2.1.4.1.1'
    oid_print_mono = '1.3.6.1.2.1.43.10.2.1.4.1.1'


class HPM426(HP):
    """ HP LJ MFP M426 """
    oid_print_count = '1.3.6.1.2.1.43.10.2.1.4.1.1'
    oid_print_color = None
    oid_print_mono = '1.3.6.1.2.1.43.10.2.1.4.1.1'

    # Fixiereinheit/Fuser Kit
    oid_fuser_name = None
    oid_fuser_capacity = None
    oid_fuser_remaining = None

    # Resttonbehälter/Waste Cartridge
    oid_waste_name = None
    oid_waste_capacity = None
    oid_waste_remaining = None

    # Bandreiniger/Transfer Belt Cleaner Kit
    oid_cleaner_name = None
    oid_cleaner_capacity = None
    oid_cleaner_remaining = None

    # Transferrolle/Transfer Roller
    oid_transfer_name = None
    oid_transfer_capacity = None
    oid_transfer_remaining = None

    ## Toner ##########
    oid_black_toner_name = '1.3.6.1.2.1.43.11.1.1.6.1.1'
    oid_black_toner_capacity = '1.3.6.1.2.1.43.11.1.1.8.1.1'
    oid_black_toner_remaining = '1.3.6.1.2.1.43.11.1.1.9.1.1'

    oid_cyan_toner_name = None
    oid_cyan_toner_capacity = None
    oid_cyan_toner_remaining = None

    oid_magenta_toner_name = None
    oid_magenta_toner_capacity = None
    oid_magenta_toner_remaining = None

    oid_yellow_toner_name = None
    oid_yellow_toner_capacity = None
    oid_yellow_toner_remaining = None

    ## Bildtrommel ##########
    oid_black_drum_name = None
    oid_black_drum_capacity = None
    oid_black_drum_remaining = None

    oid_cyan_drum_name = None
    oid_cyan_drum_capacity = None
    oid_cyan_drum_remaining = None

    oid_magenta_drum_name = None
    oid_magenta_drum_capacity = None
    oid_magenta_drum_remaining = None

    oid_yellow_drum_name = None
    oid_yellow_drum_capacity = None
    oid_yellow_drum_remaining = None


class KCSW(Printer):
    # Kyocera spezifisch Overall Prints
    oid_print_count = '1.3.6.1.4.1.1347.42.2.1.1.1.6.1.1'
    oid_print_mono = '1.3.6.1.4.1.1347.42.2.1.1.1.6.1.1'

    ## damit der Rest -1 zurückgibt...
    oid_print_color = '1.3.6.1'
    oid_cyan_toner_name = '1.3.6.1'
    oid_cyan_toner_capacity = '1.3.6.1'
    oid_cyan_toner_remaining = '1.3.6.1'

    oid_magenta_toner_name = '1.3.6.1'
    oid_magenta_toner_capacity = '1.3.6.1'
    oid_magenta_toner_remaining = '1.3.6.1'

    oid_yellow_toner_name = '1.3.6.1'
    oid_yellow_toner_capacity = '1.3.6.1'
    oid_yellow_toner_remaining = '1.3.6.1'

    ## Bildtrommel ##########
    oid_black_drum_name = '1.3.6.1'
    oid_black_drum_capacity = '1.3.6.1'
    oid_black_drum_remaining = '1.3.6.1'

    oid_cyan_drum_name = '1.3.6.1'
    oid_cyan_drum_capacity = '1.3.6.1'
    oid_cyan_drum_remaining = '1.3.6.1'

    oid_magenta_drum_name = '1.3.6.1'
    oid_magenta_drum_capacity = '1.3.6.1'
    oid_magenta_drum_remaining = '1.3.6.1'

    oid_yellow_drum_name = '1.3.6.1'
    oid_yellow_drum_capacity = '1.3.6.1'
    oid_yellow_drum_remaining = '1.3.6.1'

    # Bandreiniger auf -1
    oid_cleaner_name = '1.3.6.1'
    oid_cleaner_capacity = '1.3.6.1'
    oid_cleaner_remaining = '1.3.6.1'


class DICL(Printer):
    # Develop Ineo 450 / äquivalente Kyocera Produkte

    def initialize_values(self):
        Printer.initialize_values(self)
        consumables = []
        # Append consumables in this list with a manually overwritten type
        manual_consumables = [
            PrinterConsumable.Consumable.WASTE
        ]
        remaining_status = lambda capacity, remaining: "1" if self.query_snmp(remaining) == "-3" and self.query_snmp(capacity) == "-2" else "0"

        for manual_consumable in manual_consumables:
            # check consumable has not been initialized automatically previously
            if manual_consumable.value in [consumable.type for consumable in self.consumables]:
                logger.warning(f'Manual Consumable {manual_consumable.value} initialization failed, because it was ' \
                    'already added during the automatic routine')
                continue

            # initialize based on manual OID overwrites
            capacity_oid = getattr(self, f'oid_{manual_consumable.value.lower()}_capacity_manual')
            remaining_oid = getattr(self, f'oid_{manual_consumable.value.lower()}_remaining_manual')
            name_oid = getattr(self, f'oid_{manual_consumable.value.lower()}_name_manual')
            consumable = PrinterConsumable(
                type=manual_consumable,
                name=self.query_snmp(name_oid),
                capacity="1",
                remaining=remaining_status(capacity_oid, remaining_oid)
            )
            if consumable.initialized: self.consumables.append(consumable)
        
        if self.print_color is None: return  # if not initialized casting None to int below will raise an error
        self.print_color = int(self.print_color) + int(self.query_snmp(self.oid_copies_color))
        self.print_mono = int(self.print_mono) + int(self.query_snmp(self.oid_copies_monochrome))

    oid_printer_name = '1.3.6.1.2.1.1.1.0'

    # Sammelbehälter (Waste?)
    oid_waste_name_manual = '1.3.6.1.2.1.43.11.1.1.6.1.13'
    oid_waste_capacity_manual = '1.3.6.1.2.1.43.11.1.1.8.1.13'
    oid_waste_remaining_manual = '1.3.6.1.2.1.43.11.1.1.9.1.13'

    oid_waste_name = None
    oid_waste_capacity = None
    oid_waste_remaining = None

    # Transfer roller
    oid_cleaner_name = '1.3.6.1.2.1.43.11.1.1.6.1.16'
    oid_cleaner_capacity = '1.3.6.1.2.1.43.11.1.1.8.1.16'
    oid_cleaner_remaining = '1.3.6.1.2.1.43.11.1.1.9.1.16'

    # Usage/Prints Details
    oid_print_count = '1.3.6.1.2.1.43.10.2.1.4.1.1'
    oid_print_color = '1.3.6.1.4.1.18334.1.1.1.5.7.2.2.1.5.2.2'
    oid_print_mono = '1.3.6.1.4.1.18334.1.1.1.5.7.2.2.1.5.1.2'

    # colorOverall = copiesColor + print_color - specific to DICL
    oid_copies_color = '1.3.6.1.4.1.18334.1.1.1.5.7.2.2.1.5.2.1'
    oid_copies_monochrome = '1.3.6.1.4.1.18334.1.1.1.5.7.2.2.1.5.1.1'

    # Toner
    oid_black_toner_name = '1.3.6.1.2.1.43.11.1.1.6.1.4'
    oid_black_toner_capacity = '1.3.6.1.2.1.43.11.1.1.8.1.4'
    oid_black_toner_remaining = '1.3.6.1.2.1.43.11.1.1.9.1.4'

    oid_cyan_toner_name = '1.3.6.1.2.1.43.11.1.1.6.1.1'
    oid_cyan_toner_capacity = '1.3.6.1.2.1.43.11.1.1.8.1.1'
    oid_cyan_toner_remaining = '1.3.6.1.2.1.43.11.1.1.9.1.1'

    oid_magenta_toner_name = '1.3.6.1.2.1.43.11.1.1.6.1.2'
    oid_magenta_toner_capacity = '1.3.6.1.2.1.43.11.1.1.8.1.2'
    oid_magenta_toner_remaining = '1.3.6.1.2.1.43.11.1.1.9.1.2'

    oid_yellow_toner_name = '1.3.6.1.2.1.43.11.1.1.6.1.3'
    oid_yellow_toner_capacity = '1.3.6.1.2.1.43.11.1.1.8.1.3'
    oid_yellow_toner_remaining = '1.3.6.1.2.1.43.11.1.1.9.1.3'

    # Bildtrommel
    oid_black_drum_name = '1.3.6.1.2.1.43.11.1.1.6.1.11'
    oid_black_drum_capacity = '1.3.6.1.2.1.43.11.1.1.8.1.11'
    oid_black_drum_remaining = '1.3.6.1.2.1.43.11.1.1.9.1.11'

    oid_cyan_drum_name = '1.3.6.1.2.1.43.11.1.1.6.1.5'
    oid_cyan_drum_capacity = '1.3.6.1.2.1.43.11.1.1.8.1.5'
    oid_cyan_drum_remaining = '1.3.6.1.2.1.43.11.1.1.9.1.5'

    oid_magenta_drum_name = '1.3.6.1.2.1.43.11.1.1.6.1.7'
    oid_magenta_drum_capacity = '1.3.6.1.2.1.43.11.1.1.8.1.7'
    oid_magenta_drum_remaining = '1.3.6.1.2.1.43.11.1.1.9.1.7'

    oid_yellow_drum_name = '1.3.6.1.2.1.43.11.1.1.6.1.9'
    oid_yellow_drum_capacity = '1.3.6.1.2.1.43.11.1.1.8.1.9'
    oid_yellow_drum_remaining = '1.3.6.1.2.1.43.11.1.1.9.1.9'

    # Fixiereinheit/Fuser Kit
    oid_fuser_name = '1.3.6.1.2.1.43.11.1.1.6.1.14'
    oid_fuser_capacity = '1.3.6.1.2.1.43.11.1.1.8.1.14'
    oid_fuser_remaining = '1.3.6.1.2.1.43.11.1.1.9.1.14'

    # Transferrolle/Transfer Roller
    oid_transfer_name = '1.3.6.1.2.1.43.11.1.1.6.1.15'
    oid_transfer_capacity = '1.3.6.1.2.1.43.11.1.1.8.1.15'
    oid_transfer_remaining = '1.3.6.1.2.1.43.11.1.1.9.1.15'

    #def initialize_values(self):
        #Printer.initialize_values(self)
        #if self.print_color is None: return  # if not initialized casting None to int below will raise an error
        #self.print_color = int(self.print_color) + int(self.query_snmp(self.oid_copies_color))
        #self.print_mono = int(self.print_mono) + int(self.query_snmp(self.oid_copies_monochrome))


class HPM725BW(HPBW):
    # Skrip Eintrag 'Bandreiniger' ist bei diesem Modell 'Wartungskit'
    # Bandreiniger auf -1
    oid_cleaner_name = '1.3.6.1'
    oid_cleaner_capacity = '1.3.6.1'
    oid_cleaner_remaining = '1.3.6.1'


class XeroxPhaser(Printer):
    """ erstellt für Durckervariante Xerox Phaser 7760 """

    # Fixiereinheit/Fuser Kit
    oid_fuser_name = '1.3.6.1.2.1.43.11.1.1.6.1.6'
    oid_fuser_capacity = '1.3.6.1.2.1.43.11.1.1.8.1.6'
    oid_fuser_remaining = '1.3.6.1.2.1.43.11.1.1.9.1.6'

    # Resttonbehälter/Waste Cartridge
    oid_waste_name = '1.3.6.1.2.1.43.11.1.1.6.1.7'
    oid_waste_capacity = '1.3.6.1.2.1.43.11.1.1.8.1.7'
    oid_waste_remaining = '1.3.6.1.2.1.43.11.1.1.9.1.7'

    # Bandreiniger/Transfer Belt Cleaner Kit
    oid_cleaner_name = '1.3.6.1.2.1.43.11.1.1.6.1.13'
    oid_cleaner_capacity = '1.3.6.1.2.1.43.11.1.1.8.1.13'
    oid_cleaner_remaining = '1.3.6.1.2.1.43.11.1.1.9.1.13'

    # Transferrolle/Transfer Roller
    oid_transfer_name = '1.3.6.1.2.1.43.11.1.1.6.1.5'
    oid_transfer_capacity = '1.3.6.1.2.1.43.11.1.1.8.1.5'
    oid_transfer_remaining = '1.3.6.1.2.1.43.11.1.1.9.1.5'

    ## Toner ##########
    oid_cyan_toner_name = '1.3.6.1.2.1.43.11.1.1.6.1.1'
    oid_cyan_toner_capacity = '1.3.6.1.2.1.43.11.1.1.8.1.1'
    oid_cyan_toner_remaining = '1.3.6.1.2.1.43.11.1.1.9.1.1'

    oid_magenta_toner_name = '1.3.6.1.2.1.43.11.1.1.6.1.2'
    oid_magenta_toner_capacity = '1.3.6.1.2.1.43.11.1.1.8.1.2'
    oid_magenta_toner_remaining = '1.3.6.1.2.1.43.11.1.1.9.1.2'

    oid_yellow_toner_name = '1.3.6.1.2.1.43.11.1.1.6.1.3'
    oid_yellow_toner_capacity = '1.3.6.1.2.1.43.11.1.1.8.1.3'
    oid_yellow_toner_remaining = '1.3.6.1.2.1.43.11.1.1.9.1.3'

    oid_black_toner_name = '1.3.6.1.2.1.43.11.1.1.6.1.4'
    oid_black_toner_capacity = '1.3.6.1.2.1.43.11.1.1.8.1.4'
    oid_black_toner_remaining = '1.3.6.1.2.1.43.11.1.1.9.1.4'

    ## Bildtrommel ##########
    oid_black_drum_name = '1.3.6.1.2.1.43.11.1.1.6.1.11'
    oid_black_drum_capacity = '1.3.6.1.2.1.43.11.1.1.8.1.11'
    oid_black_drum_remaining = '1.3.6.1.2.1.43.11.1.1.9.1.11'

    oid_cyan_drum_name = '1.3.6.1.2.1.43.11.1.1.6.1.8'
    oid_cyan_drum_capacity = '1.3.6.1.2.1.43.11.1.1.8.1.8'
    oid_cyan_drum_remaining = '1.3.6.1.2.1.43.11.1.1.9.1.8'

    oid_magenta_drum_name = '1.3.6.1.2.1.43.11.1.1.6.1.9'
    oid_magenta_drum_capacity = '1.3.6.1.2.1.43.11.1.1.8.1.9'
    oid_magenta_drum_remaining = '1.3.6.1.2.1.43.11.1.1.9.1.9'

    oid_yellow_drum_name = '1.3.6.1.2.1.43.11.1.1.6.1.10'
    oid_yellow_drum_capacity = '1.3.6.1.2.1.43.11.1.1.8.1.10'
    oid_yellow_drum_remaining = '1.3.6.1.2.1.43.11.1.1.9.1.10'


class oki(Printer):
    # Usage/Prints Details
    oid_print_count = '1.3.6.1.4.1.2001.1.1.1.1.11.1.10.150.1.6.102'
    oid_print_color = '1.3.6.1.4.1.2001.1.1.1.1.11.1.10.170.1.6.1'
    oid_print_mono = '1.3.6.1.4.1.2001.1.1.1.1.11.1.10.170.1.7.1'

    # Fixiereinheit/Fuser Kit
    oid_fuser_name = '1.3.6.1.2.1.43.11.1.1.6.1.10'
    oid_fuser_capacity = '1.3.6.1.2.1.43.11.1.1.8.1.10'
    oid_fuser_remaining = '1.3.6.1.2.1.43.11.1.1.9.1.10'

    # Resttonbehälter/Waste Cartridge ist hier oid für Transferband
    oid_transfer_name = '1.3.6.1.2.1.43.11.1.1.6.1.9'
    oid_transfer_capacity = '1.3.6.1.2.1.43.11.1.1.8.1.9'
    oid_transfer_remaining = '1.3.6.1.2.1.43.11.1.1.9.1.9'

    # Resttonbehälter/Waste Cartridge
    oid_waste_name = '1.3.6.1'
    oid_waste_capacity = '1.3.6.1'
    oid_waste_remaining = '1.3.6.1'

    # Bandreiniger/Transfer Belt Cleaner Kit
    oid_cleaner_name = '1.3.6.1'
    oid_cleaner_capacity = '1.3.6.1'
    oid_cleaner_remaining = '1.3.6.1'


class okiC911(Printer):
	# Resttonbehälter/Waste Cartridge
    oid_waste_name = '1.3.6.1.2.1.43.11.1.1.6.1.11'
    oid_waste_capacity = '1.3.6.1.2.1.43.11.1.1.8.1.11'
    oid_waste_remaining = '1.3.6.1.2.1.43.11.1.1.9.1.11'

    # Fixiereinheit/Fuser Kit
    oid_fuser_name = '1.3.6.1.2.1.43.11.1.1.6.1.10'
    oid_fuser_capacity = '1.3.6.1.2.1.43.11.1.1.8.1.10'
    oid_fuser_remaining = '1.3.6.1.2.1.43.11.1.1.9.1.10'

    # Übertragungsband/Transfer Belt
    oid_transfer_name = '1.3.6.1.2.1.43.11.1.1.6.1.9'
    oid_transfer_capacity = '1.3.6.1.2.1.43.11.1.1.8.1.9'
    oid_transfer_remaining = '1.3.6.1.2.1.43.11.1.1.9.1.9'

    oid_cleaner_name = None
    oid_cleaner_capacity = None
    oid_cleaner_remaining = None


def report_data(printer: Printer) -> None:
    """ Report Printer to Backend """
    data = printer.to_json()
    data.setdefault('timestamp', datetime.now(timezone.utc).isoformat())
    logger.info(data)
    r = requests.post(BACKEND, proxies=PROXIES, headers=HEADERS, json=data, verify=True)

    if(r.status_code == 201):
        logger.info(f'[>] Reporting data for {printer.description} [{printer.serial}] to backend | {r.status_code}')
        return

    logger.error(f'Could not report data for {printer.description} [{printer.serial}] to backend | {r.status_code}')
    logger.debug(r.text)


def decide_printer(*args, **kwargs):
    """ Gibt das entsprechende Printer Objekt für
    einen Drucker <variant> zurück. """
    variant = kwargs.get('variant').lower()
    if(variant == 'xerox'): return Xerox(**kwargs)
    elif(variant == 'xeroxbw'): return XeroxBW(**kwargs)
    elif(variant == 'hp'): return HP(**kwargs)
    elif(variant == 'hpbw'): return HPBW(**kwargs)
    elif(variant == 'hpmfp'): return HPMFP(**kwargs)
    elif(variant == 'hpm426'): return HPM426(**kwargs)
    elif(variant == 'kcsw'): return KCSW(**kwargs)
    elif(variant == 'dicl'): return DICL(**kwargs)
    elif(variant == 'hpm725bw'): return HPM725BW(**kwargs)
    elif(variant == 'xeroxc8130'): return XeroxC8130(**kwargs)
    elif(variant == 'xeroxwc3225'): return XeroxWC3225(**kwargs)
    elif(variant == 'xeroxphaser'): return XeroxPhaser(**kwargs)
    elif(variant == 'xeroxvlc405'): return XeroxVLC405(**kwargs)
    elif(variant == 'xeroxvlc505s'): return XeroxVLC505S(**kwargs)
    elif(variant == 'xeroxvlb405'): return XeroxVLB405(**kwargs)
    elif(variant == 'oki'): return oki(**kwargs)
    elif(variant == 'okiC911'): return okiC911(**kwargs)
    logger.warning(f'Ungültige Variante: "{variant}" für Drucker mit IP: {kwargs.get("ip")}')
    return Printer(**kwargs)


def print_status(printer: Printer) -> None:
    print(f'########## Report for {printer.description} ##########')
    print('[i] Printer Overview')
    print(f' |-- Name: {printer.name}')
    print(f' |-- Model: {printer.model}')
    print(f' |-- IP address: {printer.ip}')
    print(f' |-- Serial number: {printer.serial}')
    print(f' |-- Client: {printer.kunde}')
    print(f' |-- Description: {printer.description}')
    print(f'[i] Printer statistics')
    print(f' |-- Mono: {int(printer.print_mono or 0):,}')
    print(f' |-- Color: {int(printer.print_color or 0):,}')
    print(f' |-- Total: {int(printer.print_count or 0):,}')
    print(f'[i] Toner values (TONER)')
    print(f' |-- [C] {printer.get_consumable("CYAN_TONER")}')
    print(f' |-- [M] {printer.get_consumable("MAGENTA_TONER")}')
    print(f' |-- [Y] {printer.get_consumable("YELLOW_TONER")}')
    print(f' |-- [K] {printer.get_consumable("BLACK_TONER")}')
    print(f'[i] Drum values (DRUM)')
    print(f' |-- [C] {printer.get_consumable("CYAN_DRUM")}')
    print(f' |-- [M] {printer.get_consumable("MAGENTA_DRUM")}')
    print(f' |-- [Y] {printer.get_consumable("YELLOW_DRUM")}')
    print(f' |-- [K] {printer.get_consumable("BLACK_DRUM")}')
    print(f'[i] Misc')
    print(f' |-- CLEANER {printer.get_consumable("CLEANER")}')
    print(f' |-- FUSER {printer.get_consumable("FUSER")}')
    print(f' |-- WASTE {printer.get_consumable("WASTE")}')
    print(f' |-- TRANSFER {printer.get_consumable("TRANSFER")}')


def initialize_printers() -> list:
    """ Hilfsfunktion die über Config iteriert und alle
    Drucker initialisiert zurückgibt """
    global PROXIES
    global HEADERS
    with open('printer_config.txt') as f:
        data = json.loads(f.read())

    PROXIES = {'http': data.get('proxy') or '', 'https': data.get('proxy') or ''}
    HEADERS.setdefault('Authorization', f'Token {data.get("token")}')

    printers = []
    for printer in data['printers']:
        printers.append(decide_printer(
            kunde=data['client'],
            ip=printer['ip'],
            serial=printer['serial'],
            description=printer['description'],
            variant=printer['variant']
        ))
    return printers


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('--report', help='Report raw printer data to backend', action='store_true')
    parser.add_argument('--debug', help='Verbose debug output, no reporting', action='store_true')
    parser.add_argument('--ping', help='Check printer alive status, no reporting', action='store_true')
    args = parser.parse_args()
    if not any(vars(args).values()): parser.error('No arguments provided.')

    logger.info('##################################################')
    logger.info(f'[>] RAUSYS SNMP Printer Monitoring and Reporting, v{__version__}')
    logger.info(f'[>] Innovative Managed Services and IT partner: rausys.de')

    printers = initialize_printers()
    for printer in printers:
        if args.report:
            if printer.status == 'OK':
                printer.initialize_values()
            report_data(printer)
        elif args.debug:
            printer.ping()
            printer.initialize_values()
            print_status(printer)

            print(printer.to_json())
            print('#########################################################')
        elif args.ping:
            printer.ping()

#a = Printer('10.100.20.110', 'Xerox', 'Beispielbeschreibung', 'Beispielkunde')
#a.printStatus()
