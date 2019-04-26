#!/usr/bin/env python3
# -*- coding: utf-8 -*-

r'''
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

Requirements:
	pip3 install pysnmp requests

Config:
	{
		"kunde": "Client Name",
		"proxy": "",
		"drucker": [{
			"ip": "10.100.20.110",
			"variant": "xerox",
			"desc": "2. OG | Marketing"
		}, {
			"ip": "10.100.20.110",
			"variant": "xeroxbw",
			"desc": "1. OG | Empfang"
		}, {
			"ip": "192.168.22.21",
			"variant": "xerox",
			"desc": "5. OG | Zentrale"
		}]
	}
'''

__author__ = 'github/alfonsrv'
__version__ = '0.3'
__python__ = '3.7'
__service__ = 'PrinterMonitoring'


from pysnmp.entity.rfc3413.oneliner import cmdgen
from pysnmp.proto import rfc1905
from datetime import datetime
import sys, traceback
import requests, json, os

BACKEND = 'https://services.domain.biz/printer.php'
HEADERS = {
			'Authentication': '4uth0rizedPr1nterz#',
			'Content-Type': 'application/json; charset=utf-8',
		}
PROXIES = {
			'http':'',
			'https':'',
}
LOGFILE = 'Printer-Monitoring.log'


def override(f):
	'''
	Tut nichts; existiert nur, damit man @override
	für Dokumentationszwecke nutzen kann.
	'''
	return f

class Printer():
	oid_printerName = '1.3.6.1.2.1.1.5.0'
	oid_printerModel = '1.3.6.1.2.1.25.3.2.1.3.1'
	oid_printerMeta = '1.3.6.1.2.1.1.1.0'
	# alternativ 1.3.6.1.4.1.2699.1.2.1.2.1.1.3.1
	# alternativ2 1.3.6.1.2.1.1.1.0
	oid_printerSerial = '1.3.6.1.2.1.43.5.1.1.17.1'
	# alternativ SN: 1.3.6.1.4.1.253.8.53.3.2.1.3.1

	# Usage/Prints Details
	oid_printsOverall = '1.3.6.1.4.1.253.8.53.13.2.1.6.1.20.1'
	oid_printsColor = '1.3.6.1.4.1.253.8.53.13.2.1.6.1.20.33'
	oid_printsMonochrome = '1.3.6.1.4.1.253.8.53.13.2.1.6.1.20.34'

	# Bildtransferkit
	oid_fuserType = '1.3.6.1.2.1.43.11.1.1.6.1.9'
	oid_fuserCapacity = '1.3.6.1.2.1.43.11.1.1.8.1.9'
	oid_fuserRemaining = '1.3.6.1.2.1.43.11.1.1.9.1.9'
	
	# Resttonbehälter
	oid_wasteType = '1.3.6.1.2.1.43.11.1.1.6.1.10'
	oid_wasteCapacity = '1.3.6.1.2.1.43.11.1.1.8.1.10'
	oid_wasteRemaining = '1.3.6.1.2.1.43.11.1.1.9.1.10'
	
	# Walzenkit
	oid_cleanerType = '1.3.6.1.2.1.43.11.1.1.6.1.11'
	oid_cleanerCapacity = '1.3.6.1.2.1.43.11.1.1.8.1.11'
	oid_cleanerRemaining = '1.3.6.1.2.1.43.11.1.1.9.1.11'
	
	# Vorlageneinzugskit
	oid_transferType = '1.3.6.1.2.1.43.11.1.1.6.1.12'
	oid_transferCapacity = '1.3.6.1.2.1.43.11.1.1.8.1.12'
	oid_transferRemaining = '1.3.6.1.2.1.43.11.1.1.9.1.12'


	## Toner ##########
	oid_blackTonerType = '1.3.6.1.2.1.43.11.1.1.6.1.1'
	oid_blackTonerCapacity = '1.3.6.1.2.1.43.11.1.1.8.1.1'
	oid_blackTonerRemaining = '1.3.6.1.2.1.43.11.1.1.9.1.1'

	oid_cyanTonerType = '1.3.6.1.2.1.43.11.1.1.6.1.2'
	oid_cyanTonerCapacity = '1.3.6.1.2.1.43.11.1.1.8.1.2'
	oid_cyanTonerRemaining = '1.3.6.1.2.1.43.11.1.1.9.1.2'
	
	oid_magentaTonerType = '1.3.6.1.2.1.43.11.1.1.6.1.3'
	oid_magentaTonerCapacity = '1.3.6.1.2.1.43.11.1.1.8.1.3'
	oid_magentaTonerRemaining = '1.3.6.1.2.1.43.11.1.1.9.1.3'

	oid_yellowTonerType = '1.3.6.1.2.1.43.11.1.1.6.1.4'
	oid_yellowTonerCapacity = '1.3.6.1.2.1.43.11.1.1.8.1.4'
	oid_yellowTonerRemaining = '1.3.6.1.2.1.43.11.1.1.9.1.4'

	## Bildtrommel ##########
	oid_blackDrumType = '1.3.6.1.2.1.43.11.1.1.6.1.5'
	oid_blackDrumCapacity = '1.3.6.1.2.1.43.11.1.1.8.1.5'
	oid_blackDrumRemaining = '1.3.6.1.2.1.43.11.1.1.9.1.5'

	oid_cyanDrumType = '1.3.6.1.2.1.43.11.1.1.6.1.6'
	oid_cyanDrumCapacity = '1.3.6.1.2.1.43.11.1.1.8.1.6'
	oid_cyanDrumRemaining = '1.3.6.1.2.1.43.11.1.1.9.1.6'
	
	oid_magentaDrumType = '1.3.6.1.2.1.43.11.1.1.6.1.7'
	oid_magentaDrumCapacity = '1.3.6.1.2.1.43.11.1.1.8.1.7'
	oid_magentaDrumRemaining = '1.3.6.1.2.1.43.11.1.1.9.1.7'
	
	oid_yellowDrumType = '1.3.6.1.2.1.43.11.1.1.6.1.8'
	oid_yellowDrumCapacity = '1.3.6.1.2.1.43.11.1.1.8.1.8'
	oid_yellowDrumRemaining = '1.3.6.1.2.1.43.11.1.1.9.1.8'
	

	def __init__(self, ip, variant, beschreibung, kunde, port=161, community='public'):

		self.ip = ip
		self.kunde = kunde
		self.desc = beschreibung
		self.variant = type(self).__name__
		
		self.port = port
		self.community = community
		self.variant = variant.lower()
		self.name = -401

	def initializeValues(self):
		#if(self.ping()):
		writeLog('[>] Initialisiere Drucker %s [%s]...' % (self.desc, self.ip))
		self.name = self.getSnmp(self.oid_printerName)
		self.model = self.getSnmp(self.oid_printerModel)
		self.serial = self.getSnmp(self.oid_printerSerial)
		self.meta = self.getSnmp(self.oid_printerMeta)

		self.printsOverall = self.getSnmp(self.oid_printsOverall)
		self.printsColor = self.getSnmp(self.oid_printsColor)
		self.printsMonochrome = self.getSnmp(self.oid_printsMonochrome)
		
		self.fuserType = self.getSnmp(self.oid_fuserType)
		self.fuserCapacity = self.getSnmp(self.oid_fuserCapacity)
		self.fuserRemaining = self.getSnmp(self.oid_fuserRemaining)

		self.wasteType = self.getSnmp(self.oid_wasteType)
		self.wasteCapacity = self.getSnmp(self.oid_wasteCapacity)
		self.wasteRemaining = self.getSnmp(self.oid_wasteRemaining)

		self.cleanerType = self.getSnmp(self.oid_cleanerType)
		self.cleanerCapacity = self.getSnmp(self.oid_cleanerCapacity)
		self.cleanerRemaining = self.getSnmp(self.oid_cleanerRemaining)

		self.transferType = self.getSnmp(self.oid_transferType)
		self.transferCapacity = self.getSnmp(self.oid_transferCapacity)
		self.transferRemaining = self.getSnmp(self.oid_transferRemaining)

		self.blackTonerType = self.getSnmp(self.oid_blackTonerType)
		self.blackTonerCapacity = self.getSnmp(self.oid_blackTonerCapacity)
		self.blackTonerRemaining = self.getSnmp(self.oid_blackTonerRemaining)

		self.cyanTonerType = self.getSnmp(self.oid_cyanTonerType)
		self.cyanTonerCapacity = self.getSnmp(self.oid_cyanTonerCapacity)
		self.cyanTonerRemaining = self.getSnmp(self.oid_cyanTonerRemaining)

		self.magentaTonerType = self.getSnmp(self.oid_magentaTonerType)
		self.magentaTonerCapacity = self.getSnmp(self.oid_magentaTonerCapacity)
		self.magentaTonerRemaining = self.getSnmp(self.oid_magentaTonerRemaining)

		self.yellowTonerType = self.getSnmp(self.oid_yellowTonerType)
		self.yellowTonerCapacity = self.getSnmp(self.oid_yellowTonerCapacity)
		self.yellowTonerRemaining = self.getSnmp(self.oid_yellowTonerRemaining)

		self.blackDrumType = self.getSnmp(self.oid_blackDrumType)
		self.blackDrumCapacity = self.getSnmp(self.oid_blackDrumCapacity)
		self.blackDrumRemaining = self.getSnmp(self.oid_blackDrumRemaining)

		self.cyanDrumType = self.getSnmp(self.oid_cyanDrumType)
		self.cyanDrumCapacity = self.getSnmp(self.oid_cyanDrumCapacity)
		self.cyanDrumRemaining = self.getSnmp(self.oid_cyanDrumRemaining)

		self.magentaDrumType = self.getSnmp(self.oid_magentaDrumType)
		self.magentaDrumCapacity = self.getSnmp(self.oid_magentaDrumCapacity)
		self.magentaDrumRemaining = self.getSnmp(self.oid_magentaDrumRemaining)
		
		self.yellowDrumType = self.getSnmp(self.oid_yellowDrumType)
		self.yellowDrumCapacity = self.getSnmp(self.oid_yellowDrumCapacity)
		self.yellowDrumRemaining = self.getSnmp(self.oid_yellowDrumRemaining)

		'''
		self.cyanToner = self.getToner('c')
		self.magentaToner = self.getToner('m')
		self.yellowToner = self.getToner('y')
		self.blackToner = self.getToner('k')

		self.cyanDrum = self.getDrum('c')
		self.magentaDrum = self.getDrum('m')
		self.yellowDrum = self.getDrum('y')
		self.blackDrum = self.getDrum('k')

		self.fuser = self.getMisc('fuser')
		self.cleaner = self.getMisc('cleaner')
		self.waste = self.getMisc('waste')
		self.transfer = self.getMisc('transfer')
		writeLog('[>] OK. Alle Werte initialisiert.')
		'''



	def getToner(self, color):
		'''
			Hilfsfunktion ausrechnen % Werte Toner
		'''
		color = color.lower()
		if(color == 'c'):
			remaining = self.cyanTonerRemaining
			capacity = self.cyanTonerCapacity
		if(color == 'm'):
			remaining = self.magentaTonerRemaining
			capacity = self.magentaTonerCapacity
		if(color == 'y'):
			remaining = self.yellowTonerRemaining
			capacity = self.yellowTonerCapacity
		if(color == 'k'):
			remaining = self.blackTonerRemaining
			capacity = self.blackTonerCapacity
		try:
			if(remaining == -1 or capacity == -1):
				return -1
			if(remaining == -404 or capacity == -404):
				return -404
			if(remaining == -401 or capacity == -401):
				return -401
			return int(round((int(remaining) / int(capacity)) * 100))
		except:
			return -1


	def getDrum(self, color):
		'''
			Hilfsfunktion ausrechnen % Werte Bildtrommel
		'''
		color = color.lower()
		if(color == 'c'):
			remaining = self.cyanDrumRemaining
			capacity = self.cyanDrumCapacity
		if(color == 'm'):
			remaining = self.magentaDrumRemaining
			capacity = self.magentaDrumCapacity
		if(color == 'y'):
			remaining = self.yellowDrumRemaining
			capacity = self.yellowDrumCapacity
		if(color == 'k'):
			remaining = self.blackDrumRemaining
			capacity = self.blackDrumCapacity
		try:
			if(remaining == -1 or capacity == -1):
				return -1
			if(remaining == -404 or capacity == -404):
				return -404
			if(remaining == -401 or capacity == -401):
				return -401
			return int(round((int(remaining) / int(capacity)) * 100))
		except:
			return -1
	
	def getMisc(self, what):
		'''
			Hilfsfunktion ausrechnen % Werte verschiedener Subteile
		'''
		what = what.lower()
		if(what == 'fuser'):
			remaining = self.fuserRemaining
			capacity = self.fuserCapacity
		if(what == 'cleaner'):
			remaining = self.cleanerRemaining
			capacity = self.cleanerCapacity
		if(what == 'waste'):
			remaining = self.wasteRemaining
			capacity = self.wasteCapacity
		if(what == 'transfer'):
			remaining = self.transferRemaining
			capacity = self.transferCapacity
		try:
			if(remaining == -1 or capacity == -1):
				return -1
			if(remaining == -404 or capacity == -404):
				return -404
			if(remaining == -401 or capacity == -401):
				return -401
			return int(round((int(remaining) / int(capacity)) * 100))
		except:
			return -1


	def ping(self):
		if(self.getSnmp(self.oid_printerName) != -404):
			writeLog('[>] Printer online, %s [%s]' % (self.desc, self.ip))
			return True
		else:
			writeLog('[ERROR] Printer offline, %s [%s]' % (self.desc, self.ip))
			return False


	def printStatus(self):
		'''
			Konsolendarstellung 
		'''
		print('########## Bericht für %s ##########' % self.desc)
		print('[i] Druckerübersicht')
		print(' |-- Name: %s' % self.name)
		print(' |-- Modell: %s' % self.model)
		print(' |-- IP-Adresse: %s' % self.ip)
		print(' |-- Seriennummer: %s' % self.serial)
		print(' |-- Kunde: %s' % self.kunde)
		print(' |-- Beschreibung: %s' % self.desc)
		print('[i] Druckstatistik')
		print(' |-- Mono: %s' % format(int(self.printsMonochrome),',d').replace(',','.'))
		print(' |-- Farbe: %s' % format(int(self.printsColor),',d').replace(',','.'))
		print(' |-- Total: %s' % format(int(self.printsOverall),',d').replace(',','.'))
		print('[i] Tonerwerte')
		print(' |-- [C] %d%%' % self.getToner('c')) 
		print(' |-- [M] %d%%' % self.getToner('m'))
		print(' |-- [Y] %d%%' % self.getToner('y'))
		print(' |-- [K] %d%%' % self.getToner('k'))
		print('[i] Bildtrommelwerte')
		print(' |-- [C] %d%%' % self.getDrum('c')) 
		print(' |-- [M] %d%%' % self.getDrum('m'))
		print(' |-- [Y] %d%%' % self.getDrum('y'))
		print(' |-- [K] %d%%' % self.getDrum('k'))
		print('[i] Verschiedenes')
		print(' |-- Bandreiniger %d%%' % self.getMisc('cleaner'))
		print(' |-- Fixiereinheit %d%%' % self.getMisc('fuser')) 
		print(' |-- Resttonbehälter %d%%' % self.getMisc('waste'))
		print(' |-- Vorlageneinzugskit %d%%' % self.getMisc('transfer'))

			
	def getSnmp(self, oid):
		'''
			Macht SNMP Abfrage für angegebene OID
		'''
		# Check ob Drucker schon Timeouts hatte
		if(self.name != -404):
			ip = self.ip
			port = self.port
			community = self.community

			cmdGen = cmdgen.CommandGenerator()
			errorIndication, errorStatus, errorIndex, varBinds = cmdGen.getCmd(
				cmdgen.CommunityData(community),
				cmdgen.UdpTransportTarget((ip, port)),
				oid)

			# Check for errors and print out results
			if(errorIndication):
				if(self.name != -404):
					writeLog('[ERROR] %s for %s' % (str(errorIndication), self.ip))
				if('timeout' in str(errorIndication)):
					return -404
				else:
					return -401
			else:
				if errorStatus:
					writeLog('[ERROR] %s at %s' % (errorStatus.prettywriteLog(), errorIndex and varBinds[int(errorIndex)-1] or '?'))
				else:
					for name, val in varBinds:
						#writeLog('%s = %s' % (name.prettywriteLog(), val.prettywriteLog()))
						# Evaluiert, ob kein Wert an OID; kein Wert an OID = -1
						if(val == '' or val == None or isinstance(val, rfc1905.NoSuchInstance) or isinstance(val, rfc1905.NoSuchObject)):
							val = '-1'
						val = str(val)
						if(val.isdigit() or self.isNegative(val)):
							return int(val)
						return val
		else:
			return -404

	@staticmethod
	def isNegative(intTest):
		'''
			Helperfunction to evaluate if negative number is int
			used in getSnmp to evaluate bad results
		'''
		try:
			int(intTest)
			return True
		except ValueError:
			return False

class Xerox(Printer):
	'''
	Druckervariante normaler Xerox Drucker, der als Printer-
	Referenzobjekt dient.
	'''
	pass


class XeroxBW(Printer):
	'''
	Druckervariante Xerox Schwarzweiß
	'''
	oid_blackDrumType = '1.3.6.1.2.1.43.11.1.1.6.1.6'
	oid_blackDrumRemaining = '1.3.6.1.2.1.43.11.1.1.9.1.6'
	oid_blackDrumCapacity = '1.3.6.1.2.1.43.11.1.1.8.1.6'
	oid_cyanDrumType = '1.3.6.1.2.1.43.11.1.1.6.1.5'
	oid_cyanDrumRemaining = '1.3.6.1.2.1.43.11.1.1.9.1.5'
	oid_cyanDrumCapacity = '1.3.6.1.2.1.43.11.1.1.8.1.5'
	


class HP(Printer):
	'''
	Druckervariante regulärer HP LaserJet Color.
	'''
	pass
		

def writeLog(logString):
	print(logString)
	with open(LOGFILE, 'a') as f:
		f.write(('%s - %s\n' % (datetime.now().strftime('%Y-%m-%d %H:%M:%S'), logString)))
	f.close()


# sends data to backend
def reportData(printer):
	sslVerify = True
	r = requests.post(BACKEND, proxies=PROXIES, headers=HEADERS, json=printer.__dict__, verify=sslVerify)
	
	if(r.status_code != 200):
		writeLog('[ERROR] Could not report data for %s [%s] to backend | %d' % (printer.desc, printer.serial, r.status_code))
		return
	writeLog('[>] Reporting data for %s [%s] to backend | %d' % (printer.desc, printer.serial, r.status_code))
	return r.text


def decidePrinter(ip, variant, desc, kunde):
	'''
	Gibt das entsprechende Printer Objekt für einen
	Drucker <variant> zurück.
	'''
	variant = variant.lower()
	if(variant == 'xerox'):
		return Xerox(ip, variant, desc, kunde)
	elif(variant == 'xeroxbw'):
		return XeroxBW(ip, variant, desc, kunde)
	return Printer(ip, variant, desc, kunde)


def initializePrinters():
	'''
	Hilfsfunktion die über Config iteriert und alle
	Drucker initialisiert zurückgibt
	'''
	global PROXIES
	with open('printer_config.txt') as f:
		data = json.loads(f.read())

	PROXIES = {'http':data['proxy'], 'https':data['proxy']}
	printers = []
	for printer in data['drucker']:
			printers.append(decidePrinter(printer['ip'], printer['variant'], printer['desc'], data['kunde']))
	return printers


########### E I N S T I E G S F U N K T I O N ############################

if __name__ == '__main__':
	os.chdir(os.path.realpath(os.path.join(os.getcwd(), os.path.dirname(__file__))))
	writeLog('##################################################')
	writeLog('[>] SNMP Printer Monitoring and Reporting, alfonsrv x 2019')
	if(len(sys.argv) > 1):
		try:
			printers = initializePrinters()
			if(sys.argv[1].lower() == 'report'):
				for printer in printers:
					printer.initializeValues()
					writeLog(printer.__dict__)
					reportData(printer)

			elif(sys.argv[1].lower() == 'debug'):
				for printer in printers:
					printer.ping()
					printer.initializeValues()
					printer.printStatus()
					print(printer.__dict__)
					print('#########################################################')

			elif(sys.argv[1].lower() == 'ping'):
				for printer in printers:
					printer.ping()
		except Exception as e:
			writeLog('[ERROR]: %s' % str(e))
			writeLog(traceback.format_exc())
			exit()

	else:
		print('')
		print('Aborting. No arguments were supplied.')
		print('Usage: printer-monitoring.py <parameter>')
		print('- report	- Report raw printer data')
		print('- debug		- Verbose debug output, no reporting')
		print('- ping		- Check printer alive status, no reporting')