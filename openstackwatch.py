# -*- encoding: utf-8 -*-
__author__ = "Chmouel Boudjnah <chmouel@chmouel.com>"
import json
import datetime
import os
import sys
import time
import cStringIO
import ConfigParser
import urllib

import PyRSS2Gen

PROJECTS = ['openstack/nova', 'openstack/keystone', 'opensack/swift']
JSON_URL = 'https://review.openstack.org/query?q=status:open'
DEBUG = False

curdir = os.path.dirname(os.path.realpath(sys.argv[0]))


def parse_ini(inifile):
    ret = {}
    if not os.path.exists(inifile):
        return
    config = ConfigParser.RawConfigParser(allow_no_value=True)
    config.read(inifile)
    if config.has_section('swift'):
        ret['swift'] = dict(config.items('swift'))
    try:
        ret['projects'] = config.get('general', 'projects')
    except(ConfigParser.NoOptionError):
        ret['projects'] = PROJECTS
    try:
        ret['projects'] = config.get('general', 'json_url')
    except(ConfigParser.NoOptionError):
        ret['json_url'] = JSON_URL
    return ret
CONFIG = parse_ini("%s/openstackwatch.ini" % curdir)


def debug(msg):
    if DEBUG:
        print msg


def get_javascript():
    url = urllib.urlretrieve(CONFIG['json_url'])
    return open(url[0]).read()


def parse_javascript(javascript):
    for row in javascript.splitlines():
        try:
            json_row = json.loads(row)
        except(ValueError):
            continue
        if not json_row or not 'project' in json_row or \
                json_row['project'] not in CONFIG['projects']:
            continue
        yield json_row


def upload_rss(xml):
    import swiftclient
    cfg = CONFIG['swift']
    client = swiftclient.Connection(cfg['auth_url'],
                                    cfg['username'],
                                    cfg['password'],
                                    auth_version=cfg.get('auth_version',
                                                         '2.0'))
    try:
        client.get_container(cfg['container'])
    except(swiftclient.client.ClientException):
        client.put_container(cfg['container'])
        # eventual consistenties
        time.sleep(1)

    client.put_object(cfg['container'], cfg['uploaded_file'],
                      cStringIO.StringIO(xml))


def main():
    javascript = get_javascript()
    rss = PyRSS2Gen.RSS2(
        title="OpenStack watch RSS feed",
        link="http://github.com/chmouel/openstackwatch.rss",
        description="The latest reviews about Openstack, straight "
                    "from Gerrit.",
        lastBuildDate=datetime.datetime.now()
    )
    for row in parse_javascript(javascript):
        author = row['owner']['name']
        author += " <%s>" % ('email' in row['owner'] and
                             row['owner']['email']
                             or row['owner']['username'])
        rss.items.append(
            PyRSS2Gen.RSSItem(
                title="%s [%s]: %s" % (os.path.basename(row['project']),
                                       row['status'],
                                       row['subject']),
                author=author,
                link=row['url'],
                guid=PyRSS2Gen.Guid(row['id']),
                pubDate=datetime.datetime.fromtimestamp(row['lastUpdated']),
            ))
    xml = rss.to_xml()
    if 'swift' in CONFIG:
        upload_rss(xml)
    else:
        print xml

if __name__ == '__main__':
    main()
