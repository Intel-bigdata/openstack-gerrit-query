#!/usr/bin/python

import calendar
import datetime
import getpass
import json
import optparse
import os

import paramiko

HOME = os.getenv('USERPROFILE') or os.getenv('HOME')

ALIAS = {
    'zhongyue.luo@gmail.com': 'zhongyue.nah@intel.com',
    'devananda.vdv@gmail.com': 'devananda@hp.com',
    'lucasagomes@gmail.com': 'lucasagomes@redhat.com',
    'rameshg87@gmail.com': 'rameshg@hp.com',
    'glongwave@gmail.com': 'eric.guo@easystack.cn',
    'tan.lin.good@gmail.com': 'tan.lin@intel.com',
}

TEAM = [
    "ken.chen@intel.com",
    "huichun.lu@intel.com",
    "zhongyue.nah@intel.com",
    "weiting.chen@intel.com",
    "zhidong.yu@intel.com",
    "jun.sun@intel.com",
    "chen.li@intel.com"
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


def tab_delimeter(*args):
    return '\t'.join([str(i) for i in args])


def change_stream(ssh_client, query, start_dt, end_dt):
    now = datetime.datetime.now()
    lo_bound_day = (now-start_dt).days + 1
    up_bound_day = (now-end_dt).days
    if up_bound_day > 0:
        day_range = '-age:%sday age:%sday' % (lo_bound_day, up_bound_day)
    else:
        day_range = '-age:%sday' % lo_bound_day
    cmd_tmpl = ('gerrit query --current-patch-set --files --format JSON '
                '-- %s %s' % (query, day_range))
    start_epoch = calendar.timegm(start_dt.utctimetuple())
    end_epoch = calendar.timegm(end_dt.utctimetuple())
    command = cmd_tmpl
    while True:
        stdin, stdout, stderr = ssh_client.exec_command(command)
        for l in stdout:
            json_obj = json.loads(l)
            if json_obj.get('type') == 'stats':
                break
            change = json_obj
            if 'email' not in change['owner']:
                continue
            elif start_epoch <= change['lastUpdated'] < end_epoch:
                real_owner = ALIAS.get(change['owner']['email'])
                if real_owner:
                    change['owner']['email'] = real_owner
                yield change
        if not json_obj['rowCount']:
            break
        else:
            command = cmd_tmpl + ' resume_sortkey:%s' % change['sortKey']


def xxx(change_json_obj_list):
    for change in change_json_obj_list:
        status = change.get('status')
        date = datetime.datetime.fromtimestamp(change.get('lastUpdated'))
        owner = change['owner']['email']
        project = change.get('project')
        insertions = sum([i['insertions']
                          for i in change['currentPatchSet']['files']
                          if i['file'] != "/COMMIT_MSG"])
        deletions = sum([i['deletions']
                         for i in change['currentPatchSet']['files']
                         if i['file'] != "/COMMIT_MSG"])
        subject = change.get('subject')
        url = change.get('url')
        print tab_delimeter(status, date, owner, project,
                            insertions, deletions, subject, url)


def member_report(ssh_client, start_date, end_date, verbose=False):
    print 'OpenStack Contribution Report'
    print start_date, '-', end_date

    print ('\nIndividual contribution (covering all the proejcts '
           'in http://git.openstack.org/cgit)')
    print tab_delimeter('contributor', '#merged', '#open')

    merged = {}
    new = {}
    query = '( owner:%s )' % ' OR owner:'.join(TEAM)
    for change in change_stream(ssh_client, query, start_date, end_date):
        owner = change['owner']['email']
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
        print tab_delimeter(owner, merged_cnt, new_cnt)
    print tab_delimeter('TOTAL', merged_total, new_total)

    if verbose:
        xxx([item for sublist in merged.values() for item in sublist] +
            [item for sublist in new.values() for item in sublist])


def company_report(ssh_client, project, start_date, end_date, verbose=False):
    print '\nProject group:', project, '(%s)' % ','.join(PROJECTS[project])
    print tab_delimeter('rank', 'domain', '#merged', '%merged', 'LOC inserted',
                        'LOC deleted')

    merged = {}
    query = ('( project:openstack/%s )' %
             ' OR project:openstack/'.join(PROJECTS[project]))
    for change in change_stream(ssh_client, query, start_date, end_date):
        status = change.get('status')
        if status == 'MERGED':
            owner = change['owner']['email']
            domain = owner.split('@')[1]
            merged.setdefault(domain, []).append(change)

    rankings = sorted([(k, len(v)) for k, v in merged.iteritems()],
                      key=lambda(x, y): y, reverse=True)
    merged_total = sum([y for x, y in rankings])
    for rank, (k, v) in enumerate(rankings, start=1):
        changes = merged[k]
        insertions = sum([i['insertions']
            for j in changes for i in j['currentPatchSet']['files']
            if i['file'] != "/COMMIT_MSG"])
        deletions = sum([i['deletions']
            for j in changes for i in j['currentPatchSet']['files']
            if i['file'] != "/COMMIT_MSG"])
        percentage = '%.1f%%' % (v * 100.0 / merged_total)
        print tab_delimeter(rank, k, v, percentage, insertions, deletions)

    if verbose:
        for k, v in rankings:
            xxx(merged[k])


if __name__ == '__main__':
    usage = 'Usage: %prog [options] YYYY-MM-DD YYYY-MM-DD'
    optparser = optparse.OptionParser(usage)
    optparser.add_option('-H', '--host', default='review.openstack.org',
                         help='Specifies the host of gerrit server')
    optparser.add_option('-P', '--port', type='int', default=29418,
                         help='Specifies the port to connect to on gerrit')
    optparser.add_option('-l', '--login_name', default=getpass.getuser(),
                         help='Specifies the user to log in as on gerrit')
    optparser.add_option('-i', '--identity_file',
                         default=os.path.join(HOME, '.ssh', 'id_rsa.pub'),
                         help='Specifies the identity file '
                              'for public key auth')
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
    elif s_date > datetime.datetime.now():
        optparser.error("invalid start date")
    elif options.project and options.project not in PROJECTS:
        optparser.error("invalid project name")

    client = paramiko.SSHClient()
    client.set_missing_host_key_policy(paramiko.AutoAddPolicy())
    client.load_system_host_keys()
    client.connect(options.host,
                   port=options.port,
                   key_filename=options.identity_file,
                   username=options.login_name)
    member_report(client, s_date, e_date, options.verbose)
    if options.project:
        company_report(client, options.project,
                       s_date, e_date, options.verbose)
    else:
        for project in PROJECTS:
            company_report(client, project, s_date, e_date, options.verbose)
    client.close()
