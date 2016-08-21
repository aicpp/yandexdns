#!/usr/bin/python

import os
import sys
import urllib2
import urllib
import json
import re
import unicodedata

import logging
import logging.handlers
import tempfile


class YandexDNS(object):
    """
    Class to work with Yandex DNS API v2
    API docs: https://tech.yandex.ru/pdd/doc/concepts/api-dns-docpage/
    setup your domains: https://pdd.yandex.ru
    get your API token: https://pddimp.yandex.ru/api2/admin/get_token
    """

    def __init__(self, domain, token):
        self.domain = domain # like: domain.com
        self.token = token # like: 123456789ABCDEF0000000000000000000000000000000000000
        self.logger = logging.getLogger(__name__)
        self.logger.addHandler(logging.NullHandler())
        self.apiUrlBase = "https://pddimp.yandex.ru/api2/admin/dns"
        self.apiRecords = []
        self.exceptionWhenError = True # raise exception instead return code

    @staticmethod
    def defaultConfigFilePath():
        return '~/.yandexdns.json'

    def setLogger(self, logger):
        self.logger = logger

    def returnResult(self, result):
        """ check result and raise exception if result is not True """
        if not result and self.exceptionWhenError:
            raise Exception('Invalid result')
        return result

    def isResponseSuccess(self, jsonDict):
        """ check response json is success """
        return self.returnResult(jsonDict['success'] == 'ok' and jsonDict['domain'] == self.domain)

    def isDomainValid(self, record):
        """  check record to match defined domain """
        return record['domain'] == self.domain

    def recordsByType(self, typeDNS):
        return [rec for rec in self.apiRecords if rec['type'] == typeDNS]

    def loadRecords(self):
        """
        Load dns-records from yandex API using identification token + domain
        :return: true if success
        """
        url = '%s/list?domain=%s' % (self.apiUrlBase, self.domain)
        request = urllib2.Request(url)
        request.add_header('PddToken', self.token)
        jsonDict = HttpTools.loadJsonFromRequest(request)
        if self.isResponseSuccess(jsonDict):
            records = jsonDict['records']
            for rec in records:
                assert self.isDomainValid(rec), "Invalid domain in reply"
            self.apiRecords = records
        return self.returnResult(bool(self.apiRecords))

    def addRecord(self, record):
        """
        Add DNS record
        :param record: record to add
        :return: true if success
        """
        url = '%s/add' % (self.apiUrlBase)
        params = {}
        # add required params
        required = [ 'domain', 'type', 'content' ]
        for key in required:
            if key in record:
                params[key] = record[key]
            else:
                return self.returnResult(False)

        # additional params
        for key, value in record.iteritems():
            if not key in params:
                params[key] = value

        self.logger.debug('params:%s' % params)
        data = urllib.urlencode(params)
        request = urllib2.Request(url=url, data=data)
        request.add_header('PddToken', self.token)

        jsonDict = HttpTools.loadJsonFromRequest(request)
        self.logger.debug('resp:%s' % jsonDict)
        return self.isResponseSuccess(jsonDict)

    def updateRecord(self, record, newParams):
        """
        Update DNS record
        :param record: existed record (received by API)
        :param newParams: params to update
        :return: true if success
        """
        url = '%s/edit' % (self.apiUrlBase)
        params = {}
        # required params
        params['domain'] = self.domain
        params['record_id'] = record['record_id']
        # additional params
        for key, value in newParams.iteritems():
            if not key in params:
                params[key] = value

        self.logger.debug('params:%s' % params)
        data = urllib.urlencode(params)
        request = urllib2.Request(url=url, data=data)
        request.add_header('PddToken', self.token)

        jsonDict = HttpTools.loadJsonFromRequest(request)
        self.logger.debug('resp:%s' % jsonDict)
        return self.isResponseSuccess(jsonDict)

    def deleteRecord(self, record):
        """
        Delete DNS record
        :param record: existed record (received by API). Meaning only record id.
        :return: true if success
        """
        self.logger.info('Deleting record:%s' % self.printRecord(record))
        url = '%s/del' % (self.apiUrlBase)
        params = {}
        params['domain'] = self.domain
        params['record_id'] = record['record_id']
        data = urllib.urlencode(params)
        request = urllib2.Request(url=url, data=data)
        request.add_header('PddToken', self.token)

        jsonDict = HttpTools.loadJsonFromRequest(request)
        return self.returnResult(self.isResponseSuccess(jsonDict))

    def updateExternalIpv4(self):
        """
        Update record A (ipv4 address) to actual external ip
        External ip retreive using free internet services
        """
        recA = self.recordsByType('A')[0]
        if not recA:
            return self.returnResult(False)
        # logger.debug('recA:%s' % recA)
        srvIp = recA['content']

        # get current external ip
        myIp = HttpTools.getMyExternalIp()
        if not myIp:
            return self.returnResult(False)

        if srvIp != myIp:
            self.logger.info('Dns record of type \'A\': %s' % srvIp)
            self.logger.info('My current external ip: %s' % myIp)
            self.logger.info('Need update ip. %s <> %s' % (myIp, srvIp))
            updateOk = self.updateRecord(record=recA, newParams={ 'content' : myIp })
            if updateOk:
                self.logger.info('External ip(record A) update to \'%s\' successfully', myIp)
            else:
                self.logger.error('Error when update external ip(record A) to \'%s\'', myIp)
        else:
            self.logger.info('External ip is actual. Domain: %s Ip: %s TTL: %d' % (self.domain, myIp, recA['ttl']))


    @staticmethod
    def printRecord(record):
        return ("%s %5s %10s %20s %7s" % (
             record['record_id']
            ,record['type']
            ,record['subdomain'][:10]
            ,record['content'][:20]
            ,record['ttl']
        ))

# -----------------------------------------------------

class SystemTools(object):
    @staticmethod
    def isCronMode():
        """
        Detect if script running in cron mode. In that case stdout file descriptor is not a tty device
        Note: in python debug mode(i.e. pycharm ide) this function returns invalid value
        :return: true if cron mode
        """
        return not os.isatty(sys.stdout.fileno())

    @staticmethod
    def normalizePath(path):
        result = path.replace(os.path.sep, '/')
        result = os.path.expanduser(result)
        while '//' in result:
            result = result.replace('//', '/')
        result = result.rstrip('/')
        result = unicodedata.normalize('NFC', result.decode('utf-8'))
        return result

    @staticmethod
    def loadJsonFromFile(configFile):
        """
        load configuration params from file
        file should contain json like this:
        { "token" : "<YOUR_PDD_TOKEN>", "domain" : "<domain like: domain.com>" }
        :param configFile: filepath to config file
        :return: dictionary by config file
        """
        path = SystemTools.normalizePath(configFile)
        with open(path) as json_file:
            json_data = json.load(json_file)
        return json_data

    @staticmethod
    def saveJsonToFile(srcDict, outFile):
        path = SystemTools.normalizePath(outFile)
        with open(path, 'w') as json_file:
            json.dump(srcDict, json_file)

class HttpTools(object):
    @staticmethod
    def loadJsonFromRequest(request, timeout=10):
        """ download url and parse data as json """
        response = urllib2.urlopen(request, timeout=timeout)
        return json.load(response, encoding='utf-8')

    @staticmethod
    def getMyExternalIp():
        """ return external ipv4 address """
        sources = [{"ip": "http://api.ipify.org/?format=json"},
                   {"ip_addr": "http://ifconfig.me/all.json",},
                   {"ip": "http://www.trackip.net/ip?json"}]

        for source in sources:
            for key in source.keys():
                request = urllib2.Request(source[key])
                jsonDict = HttpTools.loadJsonFromRequest(request)
                ip = jsonDict[key]
                pattern = r'^(?:(?:25[0-5]|2[0-4][0-9]|[01]?[0-9][0-9]?)\.){3}(?:25[0-5]|2[0-4][0-9]|[01]?[0-9][0-9]?)$'
                test_ip = re.compile(pattern)
                if test_ip.match(ip):
                    return ip

class Logger(object):
    @staticmethod
    def createLogger():
        """ create default logger """
        logger = logging.getLogger(__name__)
        logger.setLevel(logging.DEBUG)

        if not SystemTools.isCronMode():
            logger.setLevel(logging.DEBUG)
            logger.addHandler(Logger.createConsoleHandler())
        logFilePath = Logger.defaultLogFilePath(__file__)
        logger.addHandler(Logger.createLogFileHandler(logFilePath))
        return logger

    @staticmethod
    def defaultLogFilePath(fileName):
        """
        Return filepath in temporary directory with script name.
        Invoke as defaultLogFilePath(fileName=__file__) to use script name as filename
        :return: str
        """
        scriptname = os.path.splitext(os.path.basename(fileName))[0]
        tempdir = tempfile.gettempdir()
        return os.path.join(tempdir, scriptname + '.log')

    @staticmethod
    def createLogFileHandler(filePath, maxBytes=1048576, backupCount=3):
        fileHandler = logging.handlers.RotatingFileHandler(filePath, maxBytes=maxBytes, backupCount=backupCount)
        formatDt = u"%Y-%m-%d %H:%M:%S"
        fmtFile = logging.Formatter(fmt=u"%(asctime)s.%(msecs)03d %(module)-15s %(levelname)-7s %(message)s",
                                    datefmt=formatDt)
        fileHandler.setFormatter(fmtFile)
        return fileHandler

    @staticmethod
    def createConsoleHandler():
        conHandler = logging.StreamHandler()
        conHandler.setLevel(logging.DEBUG)
        fmtCon = logging.Formatter(fmt=u"%(asctime)s %(message)s", datefmt=u"%H:%M:%S")
        conHandler.setFormatter(fmtCon)
        return conHandler

    @staticmethod
    def createFileRotationHandler(filePath, maxBytes=1048576, backupCount=2):
        handler = logging.handlers.RotatingFileHandler(filePath, maxBytes=maxBytes, backupCount=backupCount)
        return handler

# -----------------------------------------------------
def main():
    logger = Logger.createLogger()
    try:
        configData = SystemTools.loadJsonFromFile(YandexDNS.defaultConfigFilePath())

        yadns = YandexDNS(domain=configData['domain'], token=configData['token'])
        yadns.setLogger(logger)

        # load all records
        yadns.loadRecords()

        # logger.debug('Get %d dns-records' % len(yadns.apiRecords))
        # SystemTools.saveJsonToFile(yadns.apiRecords, '~/yandex_dns_records.json')
        # yadns.apiRecords.sort(key=lambda tup: tup['type'])
        # [logger.debug(yadns.printRecord(rec)) for rec in yadns.apiRecords]

        # update external ipv4
        yadns.updateExternalIpv4()

    except urllib2.URLError, e:
        logger.error('URLError = %s' % (str(e.reason)))
    except ValueError, e:
        logger.error('ValueError = %s' % (str(e.message)))
    except:
        logger.exception('')

if __name__ == '__main__':
    main()
