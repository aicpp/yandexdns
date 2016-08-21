Script to add/edit/delete DNS-records delegated to Yandex DNS service
=====================================================================

The script `yandexdns.py` uses Yandex DNS API v2 (https://tech.yandex.ru/pdd/doc/concepts/api-dns-docpage/) to control your DNS-records.  
By default, script update DNS-record of type A with actual external ipv4-address.


Access to API
-------------
1) Delegate your domain to Yandex DNS and confirm it (https://pdd.yandex.ru)  
2) Get your PDD-token (https://tech.yandex.ru/pdd/doc/concepts/access-docpage/)    

Installation
------------
1) Clone this git repo: `git clone https://github/aicpp/yandexdns`   
2) Write config file (default path: `~/.yandexdns.json`) like this:    
```json
{
"token" : "<YOUR_PDD_TOKEN>",
"domain" : "<domain like: domain.com>"
}
```
3) Ensure that your have record with type A in your DNS-records (https://pdd.yandex.ru/domain_ns/yourdomain.ru/)   

Usage
-----
The script log to console and file `/tmp/yandexdns.log`  
The script detect if it run by cron and disable console output in that case.  
By default, if error occurs, the exception will raised. It set in param `self.exceptionWhenError = True`

Run script in your server. It sets DNS-record of type A with actual external ipv4-address.  
If actual external ip is not match dns-record then script edit dns-record with it:  
```
2016-08-20 09:40:01.954 yandexdns       INFO    Dns record of type 'A': 111.111.111.111
2016-08-20 09:40:02.438 yandexdns       INFO    My current external ip: 222.222.222.222
2016-08-20 09:40:02.440 yandexdns       INFO    Need update ip. 222.222.222.222 <> 111.111.111.111
2016-08-20 09:40:02.542 yandexdns       INFO    External ip(record A) update to '222.222.222.222' successfully
```
If the record already is actual you'll see actual info:  
```
2016-08-20 00:09:03.996 yandexdns       INFO    External ip is actual. Domain: yourdomain.ru Ip: 222.222.222.222 TTL: 900
```

Prepare
-------
Load configuration from json-file:  
```python
    configData = SystemTools.loadJsonFromFile(YandexDNS.defaultConfigFilePath())
```
Instantiate YandexDNS-object and set it's logger:  
```python
    yadns = YandexDNS(domain=configData['domain'], token=configData['token'])
    yadns.setLogger(logger)
```
Load all DNS-records from Yandex API:  
```python
    yadns.loadRecords()
```

Examples
--------

Update your external ip:  
```python
    yadns.updateExternalIpv4()
```

Delete all records with type `SRV`:  
```python
    recordsToDelete = yadns.recordsByType('SRV')
    for rec in recordsToDelete:
        yadns.deleteRecord(rec)
```

Add new DNS-record of type `CNAME` and subdomain `www` to your domain:  
```python
    newParams = {}
    newParams['domain'] = yadns.domain
    newParams['type'] = 'CNAME'
    newParams['content'] = ('%s.' % yadns.domain)
    newParams['subdomain'] = 'www'
    if yadns.addRecord(newParams):
        logger.info('Add successfully')
```

Get www-record and update it content:
```python
    recordWWW = [rec for rec in yadns.apiRecords if rec['type'] == 'CNAME' and rec['subdomain'] == 'www'][0]
    logger.debug('www: %s' % yadns.printRecord(recordWWW))

    newParams = {}
    newParams['content'] = ('%s.' % yadns.domain)
    yadns.updateRecord(recordWWW, newParams=newParams)
```
