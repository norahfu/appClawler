#!/usr/bin/env python
#coding=utf-8
__author__ = 'Norah'
import sys, os
import time
import codecs
from extractor.myappParser import MyappParser
from extractor.sjbaiduParser import SjbaiduParser
reload(sys)
sys.setdefaultencoding('utf-8')
sys.path.append(u'..')

import urllib
import logging
from urllib import urlopen

import requests
import traceback
from nt import chdir
from util.mysqlWrapper import getConn, insertRecord, loadRecord, getRecord, sqlExecute
class fetcher:
    def __init__(self):
        self._seedsdir = u"../seeds"
        self._logdir = u"../log"

        logging.basicConfig(level=logging.DEBUG,
                format='%(asctime)s %(message)s |---| %(levelname)s  %(filename)s[line:%(lineno)d]',
                datefmt='%a, %d %b %Y %H:%M:%S',
                filename=u'{}/fetcher.log'.format(self._logdir),
                filemode='w')

        self.logger = logging.getLogger('FetcherLogger')
        self.logger.setLevel(logging.DEBUG)

    def get_from_url(self,url, suburl_filter):
        if not url:
            self.logger.warning(u"unvailable url: %s" % url)
            return False

        if url.startswith("https://"):
            return False

        real_url = url
        if not real_url.startswith("http://"):
            real_url = "http://" + real_url

        start_ts = time.time()
        self.logger.info(u"==FetchStart== {}, {}".format(start_ts, url))

        try:
            response = requests.get(url=real_url)    # 最基本的GET请求
            if not response.text or response.status_code != requests.codes.ok:
                self.logger.debug(u"Fetch failed with status code: {}".format(response.status_code))
                return False


            app,sublink = self.fetch_sjbaidu_app(response)
            app_data= {}
            for key in app.keys():
                app_data[key] = app[key] or u''
            #app_data = [data or u'' for data in app]
            ####:TODO'
            dimensions = {"url": url.strip(), "domain": suburl_filter}
            conn = getConn("taierdb")
            table = "app_Info"
            insertRecord(app_data, dimensions, table, conn=conn)
            conn.close()
            self.store_suburls(sublink,url,suburl_filter)

            #:TODO: 根据不同的parser解析
                #TODO:update table app_info.,self.fetch_app()


        except Exception as e:
            print e

        self.logger.info(u"FetchEnd  {} {}".format(time.time() - start_ts, url))

        return True

    def fetch_myapp_app(self,response):
        parser = MyappParser()
        app = parser.parse_app_data(response.text)
        related_apps = parser.parse_related_apps(response.text)
        sameDev_apps = parser.parse_samedev_apps(response.text)

        related_apps.extend(sameDev_apps)
        return app,related_apps

    def fetch_sjbaidu_app(self,response):
        parser = SjbaiduParser()
        related_apps = parser.parse_related_apps(response.text)
        app = parser.parse_app_data(response.text)

        return app,related_apps
    def get_seeds(self):
        seedfiles = os.listdir(self._seedsdir)
        for f in seedfiles:
            if not f.endswith(".done"):
                continue

            real_f = f.split(".done")[0]
            lines = list(file(self._seedsdir+"/"+real_f))
            numLine = len(lines)
            self.logger.debug(u"start file: real_f, with {} lines".format(numLine))

            for idxLine, line in enumerate(lines):
                url, suburl_filter = line.strip().split("\t", 2)
                self.logger.debug(u"start idxLine: {}/{}".format(idxLine, numLine))

                ret = False
                try:

                    ret = self.get_from_url(url, suburl_filter)
                    if ret:
                        sql = u"""update app_Seeds set fetchTimes = 1 where url = '{}'""".format(url);
                    else:
                        sql = u"""update app_Seeds set errorTimes = errorTimes + 1, fetchTimes = 1 where url = '{}'""".format(url);

                except Exception as e:
                    self.logger.warning(str(e))
                    self.logger.warning(traceback.format_exc())
                    continue

                conn = getConn("taierdb")
                try:
                    sqlExecute(sql, conn);

                except Exception as e:
                    self.logger.warning(str(e))
                    self.logger.warning(traceback.format_exc())

                conn.close()

            name = self._seedsdir+"/"+real_f+'.fetched'
            chdir(os.path.dirname(self._seedsdir+"/"+real_f))
            os.rename(real_f,name)
            os.remove(real_f+'.done')


    def store_suburls(self,suburls, url, suburl_filter):
        conn = getConn("taierdb")

        numSubLinks  = len(suburls)
        if not url:
            self.logger.warning("parentUrl is None")
            return False

        suburl_filter = suburl_filter.strip()
        dimensions = {"parentUrl": url.strip()}
        table="app_Seeds"
        numNewSubLinks = numSubLinks - len(getRecord(dimensions, table, conn=conn) or [])
        numNewSubLinks = (numNewSubLinks >= 0) and numNewSubLinks or 0

        dimensions = {"url": url.strip(), "domain": suburl_filter}
        measures = {"numSubLinks": numSubLinks, "numNewSubLinks": numNewSubLinks}

        loadRecord(measures, dimensions, table, conn=conn)


        for surl in suburls:
            if not surl:
                continue

        dimensions = {"url": surl.strip()}
        measures = {"errorTimes": 0, "fetchTimes": 0, "parentUrl": url.strip(), "domain": suburl_filter}

        if not getRecord(dimensions, table, conn=conn):
            insertRecord(measures, dimensions, table, conn=conn)

        conn.close()
        return True

if "__main__" == __name__:
    fetcher = fetcher()
    while True:
        fetcher.get_seeds()
        time.sleep(10)
