#!/usr/bin/python

import calendar
import datetime
import json
import optparse
import os
import paramiko
from pprint import pprint
import sys

HOME = os.getenv('USERPROFILE') or os.getenv('HOME')

TEAM = [
    "zhongyue.nah@intel.com",
]

PROJECTS = {
    'ironic': [
        'ironic', 'ironic-specs',
        'python-ironicclient', 'ironic-python-agent',
    ],
    'sahara': [
        'sahara', 'python-saharaclient',
        'sahara-dashboard', 'sahara-extra',
        'sahara-image-elements', 'sahara-specs'
    ],
    'manila': [
        'manila', 'python-manilaclient',
    ],
}

ALIAS = {
    'zhongyue.luo@gmail.com': 'zhongyue.nah@intel.com',
}


def change_stream(ssh_client, query, start_dt, end_dt):
    now = datetime.datetime.now()
    lo_bound_day = (now-start_dt).days + 1
    up_bound_day = (now-end_dt).days
    cmd_tmpl = ('gerrit query --current-patch-set --files --format JSON '
                '-- %s -age:%sday age:%sday' %
                (query, lo_bound_day, up_bound_day))
    start_epoch = calendar.timegm(start_dt.utctimetuple())
    end_epoch = calendar.timegm(end_dt.utctimetuple())
    command = cmd_tmpl
    while True:
        stdin, stdout, stderr = ssh_client.exec_command(command)
        for l in stdout:
            json_obj = json.loads(l)
            if json_obj.get('type') == 'stats':
                break
            elif not json_obj['owner'].get('email'):
                continue
            change = json_obj
            real_owner = ALIAS.get(change['owner']['email'])
            if real_owner:
                change['owner']['email'] = real_owner
            if start_epoch <= change['lastUpdated'] < end_epoch:
                yield change
        if not json_obj['rowCount']:
            break
        else:
            command = cmd_tmpl + ' resume_sortkey:%s' % change['sortKey']


def member_report(ssh_client, start_date, end_date, verbose=False):
    # Nubmer of the merged patches in the past N days,
    # for all the projects (including openstack and stackforge)
    print '******************************************************'
    print ' Number of changes from', start_date, 'till', end_date
    print ' Including all the openstack and stackforge projects'
    print '******************************************************'
    print 'people', '\t\t\t', 'merged', '\t', 'open'
    print '--------------------------------------'

    merged = {}
    new = {}
    query = '( owner:%s )' % ' OR owner:'.join(TEAM)
    for change in change_stream(ssh_client, query, start_date, end_date):
        owner = change['owner'].get('email')
        status = change['status']
        if status == 'MERGED':
            merged.setdefault(owner, []).append(change)
        elif status == 'NEW':
            new.setdefault(owner, []).append(change)

    new_total = 0
    merged_total = 0
    for owner in TEAM:
        merged_cnt = len(merged.get(owner, []))
        new_cnt = len(new.get(owner, []))
        merged_total += merged_cnt
        new_total += new_cnt
        print owner, '\t', merged_cnt, '\t', new_cnt
    print '--------------------------------------'
    print 'TOTAL', '\t\t\t', merged_total, '\t', new_total

    if verbose:
        for change in ([item for sublist in merged.values()
                        for item in sublist] +
                       [item for sublist in new.values()
                        for item in sublist]):
            deletions = 0
            insertions = 0
            for i in change['currentPatchSet']['files']:
                if i['file'] == '/COMMIT_MSG':
                    continue
                deletions += i['deletions']
                insertions += i['insertions']
            subject = change.get('subject')
            project = change.get('project')
            owner = change.get('owner').get('email')
            url = change.get('url')
            date = datetime.datetime.fromtimestamp(change.get('lastUpdated'))
            status = change.get('status')
            print '\t'.join([str(i) for i in
                             [status, date, owner, project,
                              insertions, deletions, subject, url]])


def company_report(ssh_client, project, start_date, end_date):
    # Nubmer of the merged patches in the past N days, for sahara project
    # ssh -p 29418 zhidong@review.openstack.org gerrit query project:openstack/sahara status:merged age:14days
    # unfortunately age:14days doesn't work, so we need a work-around
    print '******************************************************'
    print ' Number of merged changes from', start_date, 'till', end_date
    print ' for openstack/%s project only' % project
    print '******************************************************'
    print 'merged', '\t', '%', '\t', 'inserted', '\t', 'deleted', '\t', 'domain'
    print '--------------------------------------'

    total = 0
    merged = {}
    deletions = {}
    insertions = {}
    query = ('( project:openstack/%s )' %
             ' OR project:openstack/'.join(PROJECTS[project]))
    for change in change_stream(ssh_client, query, start_date, end_date):
        owner = change['owner'].get('email')
        domain = owner.split('@')[1]
        merged[domain] = merged.setdefault(domain, 0) + 1
        total += 1
        for i in change['currentPatchSet']['files']:
            if i['file'] == '/COMMIT_MSG':
                continue
            deletions[domain] = (deletions.setdefault(domain, 0) +
                                 i['deletions'])
            insertions[domain] = (insertions.setdefault(domain, 0) +
                                  i['insertions'])
    asdf = sorted(merged.items(), key=lambda(x, y): y, reverse=True)
    for domain, cnt in asdf:
        print '\t'.join([str(i) for i in [cnt, '%.1f' % (cnt * 100.0 / total),
                         insertions[domain], deletions[domain], domain]])
    print '--------------------------------------'
    print 'TOTAL', '\t', total


if __name__ == '__main__':
    usage = 'Usage: %prog [options] YYYY-MM-DD YYYY-MM-DD'
    optparser = optparse.OptionParser(usage)
    optparser.add_option('-H', '--host', default='review.openstack.org',
                         help='Specifies the host of gerrit server')
    optparser.add_option('-P', '--port', type='int', default=29418,
                         help='Specifies the port to connect to on gerrit')
    optparser.add_option('-l', '--login_name', default='zyluo',
                         help='Specifies the user to log in as on gerrit')
    optparser.add_option('-i', '--identity_file',
                         default=os.path.join(HOME, '.ssh', 'id_rsa.pub'),
                         help='Specifies the identity file for public key auth')
    optparser.add_option('-p', '--project', default=None,
                         help='Project to generate stats for')
    optparser.add_option('-v', '--verbose', action='store_true', default=False,
                         help='Um... Hard to explain. Try it and see')
    options, args = optparser.parse_args()

    if len(args) != 2:
        optparser.error("incorrect number of arguments")

    try:
        s_date = datetime.datetime.strptime(args[0], '%Y-%m-%d')
        e_date = datetime.datetime.strptime(args[1], '%Y-%m-%d')
    except ValueError:
        optparser.error("incorrect format of arguments")

    if not s_date < e_date:
        optparser.error("incorrect order of arguments")
    elif options.project and options.project not in PROJECTS:
        optparser.error("incorrect project name")

    client = paramiko.SSHClient()
    client.set_missing_host_key_policy(paramiko.AutoAddPolicy())
    client.load_system_host_keys()
    client.connect(options.host,
                   port=options.port,
                   key_filename=options.identity_file,
                   username=options.login_name)
    member_report(client, s_date, e_date, options.verbose)
    if options.project:
        company_report(client, options.project, s_date, e_date)
    else:
        for project in PROJECTS:
            company_report(client, project, s_date, e_date)
    client.close()
