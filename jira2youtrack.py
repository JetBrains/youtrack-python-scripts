#! /usr/bin/env python

# **********************************************************
# *  Since YouTrack 6.5 there is build-in JIRA import.     *
# *  Please use this script only in case you have problems *
# *  with the native implementation.                       *
# **********************************************************

import sys

if sys.version_info >= (3, 0):
    print("\nThe script doesn't support python 3. Please use python 2.7+\n")
    sys.exit(1)

import calendar
import functools
import os
import re
import getopt
import datetime
import urllib2
import jira
from jira.client import JiraClient
from youtrack import Issue, YouTrackException, Comment, Link, WorkItem
import youtrack
from youtrack.connection import Connection
from youtrack.importHelper import create_bundle_safe


jt_fields = []

_debug = os.environ.get('DEBUG')


def usage():
    print("""
**********************************************************
*  Since YouTrack 6.5 there is build-in JIRA import.     *
*  Please use this script only in case you have problems *
*  with the native implementation.                       *
**********************************************************

Usage:
    %s [OPTIONS] j_url j_user j_pass y_url y_user y_pass [project_id[,range] ...]

The script imports issues from Jira to YouTrack.
By default it imports issues and all attributes like attachments, labels, links.
This behaviour can be changed by passing import options -i, -a, -l, -t amd -w.

Arguments:
    j_url         Jira URL
    j_user        Jira user
    j_pass        Jira user's password
    y_url         YouTrack URL
    y_user        YouTrack user
    y_pass        YouTrack user's password
    project_id    ProjectID to import
    range         Import issues from given range only. Format is [X:]Y.
                  Default value for X is 1, so it can be omitted.
                  Examples: DEMO,100, DEMO,101:200

Options:
    -h,  Show this help and exit
    -i,  Import issues
    -a,  Import attachments
    -r,  Replace old attachments with new ones (remove and re-import)
    -l,  Import issue links
    -t,  Import Jira labels (convert to YT tags)
    -w,  Import Jira work logs
    -m,  Comma-separated list of field mappings.
         Mapping format is JIRA_FIELD_NAME:YT_FIELD_NAME@FIELD_TYPE
    -M,  Comma-separated list of field value mappings.
         Mapping format is YT_FIELD_NAME:JIRA_FIELD_VALUE=YT_FIELD_VALUE[;...]
""" % os.path.basename(sys.argv[0]))

# Primary import options
FI_ISSUES = 0x01
FI_ATTACHMENTS = 0x02
FI_LINKS = 0x04
FI_LABELS = 0x08
FI_WORK_LOG = 0x16

# Secondary import options (from 0x80)
FI_REPLACE_ATTACHMENTS = 0x80


def main():
    flags = 0
    field_mappings = dict()
    value_mappings = dict()
    try:
        opts, args = getopt.getopt(sys.argv[1:], 'harltiwm:M:')
        for opt, val in opts:
            if opt == '-h':
                usage()
                sys.exit(0)
            elif opt == '-i':
                flags |= FI_ISSUES
            elif opt == '-a':
                flags |= FI_ATTACHMENTS
            elif opt == '-r':
                flags |= FI_REPLACE_ATTACHMENTS
            elif opt == '-l':
                flags |= FI_LINKS
            elif opt == '-t':
                flags |= FI_LABELS
            elif opt == '-w':
                flags |= FI_WORK_LOG
            elif opt == '-m':
                for mapping in val.split(','):
                    m = re.match(r'^([^:]+):([^@]+)@(.+)$', mapping)
                    if not m:
                        raise ValueError('Bad field mapping (skipped): %s' % mapping)
                    jira_name, yt_name, field_type = m.groups()
                    field_mappings[jira_name.lower()] = (yt_name.lower(), field_type)
            elif opt == '-M':
                for mapping in val.split(','):
                    m = re.match(r'^([^:]+):(.+)$', mapping)
                    if not m:
                        raise ValueError('Bad field mapping (skipped): %s' % mapping)
                    field_name, v_mappings = m.groups()
                    field_name = field_name.lower()
                    for vm in v_mappings.split(';'):
                        m = re.match(r'^([^=]+)=(.+)$', vm)
                        if not m:
                            raise ValueError('Bad field mapping (skipped): %s' % vm)
                        jira_value, yt_value = m.groups()
                        if field_name not in value_mappings:
                            value_mappings[field_name] = dict()
                        value_mappings[field_name][jira_value.lower()] = yt_value
    except getopt.GetoptError as e:
        print(e)
        usage()
        sys.exit(1)
    if len(args) < 7:
        print('Not enough arguments')
        usage()
        sys.exit(1)

    if not flags & 0x7F:
        flags |= FI_ISSUES | FI_ATTACHMENTS | FI_LINKS | FI_LABELS | FI_WORK_LOG
    j_url, j_login, j_password, y_url, y_login, y_password = args[:6]

    projects = []
    for project in args[6:]:
        m = re.match(
            r'^(?P<pid>[^,]+)(?:,(?P<n1>\d+)(?::(?P<n2>\d+))?)?$', project)
        if m:
            m = m.groupdict()
            start = 1
            end = 0
            if m.get('n2') is not None:
                start = int(m['n1'])
                end = int(m['n2'])
            elif m.get('n1') is not None:
                start = 1
                end = int(m['n1'])
            if end and end < start:
                raise ValueError('Bad argument => %s' % project)
            projects.append((m['pid'].upper(), start, end))
        else:
            raise ValueError('Bad argument => %s' % project)

    jira2youtrack(j_url, j_login, j_password,
                  y_url, y_login, y_password, projects,
                  flags, field_mappings, value_mappings)


def to_yt_issue(target, issue, project_id,
                fields_mapping=None, value_mappings=None):
    yt_issue = Issue()
    yt_issue['comments'] = []
    yt_issue.numberInProject = issue['key'][(issue['key'].find('-') + 1):]
    for field, value in issue['fields'].items():
        if value is None:
            continue
        if fields_mapping and field.lower() in fields_mapping:
            field_name, field_type = fields_mapping[field.lower()]
        else:
            field_name = get_yt_field_name(field)
            field_type = get_yt_field_type(field_name)
        if field_name == 'comment':
            for comment in value['comments']:
                yt_comment = Comment()
                yt_comment.text = comment['body']
                comment_author_name = "guest"
                if 'author' in comment:
                    comment_author = comment['author']
                    create_user(target, comment_author)
                    comment_author_name = comment_author['name']
                yt_comment.author = comment_author_name.replace(' ', '_')
                yt_comment.created = to_unix_date(comment['created'])
                yt_comment.updated = to_unix_date(comment['updated'])
                yt_issue['comments'].append(yt_comment)
        elif (field_name is not None) and (field_type is not None):
            if isinstance(value, list) and len(value):
                yt_issue[field_name] = []
                for v in value:
                    if isinstance(v, dict):
                        v['name'] = get_yt_field_value(field_name, v['name'], value_mappings)
                    else:
                        v = get_yt_field_value(field_name, v, value_mappings)
                    create_value(target, v, field_name, field_type, project_id)
                    yt_issue[field_name].append(get_value_presentation(field_type, v))
            else:
                if field_name.lower() == 'estimation':
                    if field_type == 'period':
                        value = int(int(value) / 60)
                    elif field_type == 'integer':
                        value = int(int(value) / 3600)
                if isinstance(value, int):
                    value = str(value)
                if len(value):
                    if isinstance(value, dict):
                        value['name'] = get_yt_field_value(field_name, value['name'], value_mappings)
                    else:
                        value = get_yt_field_value(field_name, value, value_mappings)
                    create_value(target, value, field_name, field_type, project_id)
                    yt_issue[field_name] = get_value_presentation(field_type, value)
        elif _debug:
            print('DEBUG: unclassified field', field_name)
    return yt_issue


def ignore_youtrack_exceptions(f):
    @functools.wraps(f)
    def wrapper(*args, **kwargs):
        try:
            return f(*args, **kwargs)
        except YouTrackException as e:
            print(e)
    return wrapper


@ignore_youtrack_exceptions
def process_labels(target, issue):
    tags = issue['fields']['labels']
    for tag in tags:
        tag = re.sub(r'[,&<>]', '_', tag)
        try:
            target.executeCommand(issue['key'], 'tag ' + tag, disable_notifications=True)
        except YouTrackException:
            tag = re.sub(r'[\s-]', '_', tag)
            target.executeCommand(issue['key'], 'tag ' + tag, disable_notifications=True)


def get_yt_field_name(jira_name):
    if jira_name in jira.FIELD_NAMES:
        return jira.FIELD_NAMES[jira_name]
    return jira_name


def get_yt_field_type(yt_name):
    result = jira.FIELD_TYPES.get(yt_name)
    if result is None:
        result = youtrack.EXISTING_FIELD_TYPES.get(yt_name)
    return result


def get_yt_field_value(field_name, jira_value, value_mappings):
    new_value = jira_value
    if isinstance(field_name, unicode):
        field_name = field_name.encode('utf-8')
    if isinstance(jira_value, unicode):
        jira_value = jira_value.encode('utf-8')
    try:
        new_value = value_mappings[field_name.lower()][jira_value.lower()]
    except KeyError:
        pass
    return new_value


def process_links(target, issue, yt_links):
    for sub_task in issue['fields']['subtasks']:
        parent = issue[u'key']
        child = sub_task[u'key']
        link = Link()
        link.typeName = u'subtask'
        link.source = parent
        link.target = child
        yt_links.append(link)

    links = issue['fields'][u'issuelinks']
    for link in links:
        if u'inwardIssue' in link:
            source_issue = issue[u'key']
            target_issue = link[u'inwardIssue'][u'key']
        elif u'outwardIssue' in link:
            source_issue = issue[u'key']
            target_issue = link[u'outwardIssue'][u'key']
        else:
            continue

        type = link[u'type']
        type_name = type[u'name']
        inward = type[u'inward']
        outward = type[u'outward']
        try:
            target.createIssueLinkTypeDetailed(
                type_name, outward, inward, inward != outward)
        except YouTrackException:
            pass

        yt_link = Link()
        yt_link.typeName = type_name
        yt_link.source = source_issue
        yt_link.target = target_issue
        yt_links.append(yt_link)


def create_user(target, value):
    try:
        target.createUserDetailed(value['name'].replace(' ', '_'), value['displayName'], value[u'name'], 'fake_jabber')
    except YouTrackException as e:
        print(str(e))
    except KeyError as e:
        print(str(e))


def create_value(target, value, field_name, field_type, project_id):
    if field_type.startswith('user'):
        create_user(target, value)
        value['name'] = value['name'].replace(' ', '_')
    if field_name in jira.EXISTING_FIELDS:
        return
    if field_name.lower() not in [field.name.lower() for field in target.getProjectCustomFields(project_id)]:
        if field_name.lower() not in [field.name.lower() for field in target.getCustomFields()]:
            target.createCustomFieldDetailed(field_name, field_type, False, True, False, {})
        if field_type in ['string', 'date', 'integer', 'period']:
            try:
                target.createProjectCustomFieldDetailed(
                    project_id, field_name, "No " + field_name)
            except YouTrackException as e:
                if e.response.status == 409:
                    print(e)
                else:
                    raise e
        else:
            bundle_name = "%s: %s" % (project_id, field_name)
            create_bundle_safe(target, bundle_name, field_type)
            try:
                target.createProjectCustomFieldDetailed(
                    project_id, field_name, "No " + field_name,
                    {'bundle': bundle_name})
            except YouTrackException as e:
                if e.response.status == 409:
                    print(e)
                else:
                    raise e
    if field_type in ['string', 'date', 'integer', 'period']:
        return
    project_field = target.getProjectCustomField(project_id, field_name)
    bundle = target.getBundle(field_type, project_field.bundle)
    try:
        target.addValueToBundle(bundle, re.sub(r'[<>/]', '_', get_value_presentation(field_type, value)))
    except YouTrackException:
        pass


def to_unix_date(time_string, truncate=False):
    tz_diff = 0
    if len(time_string) == 10:
        dt = datetime.datetime.strptime(time_string, '%Y-%m-%d')
    else:
        m = re.search('(Z|([+-])(\d\d):?(\d\d))$', time_string)
        if m:
            tzm = m.groups()
            time_string = time_string[0:-len(tzm[0])]
            if tzm[0] != 'Z':
                tz_diff = int(tzm[2]) * 60 + int(tzm[3])
                if tzm[1] == '-':
                    tz_diff = -tz_diff
        time_string = re.sub('\.\d+$', '', time_string).replace('T', ' ')
        dt = datetime.datetime.strptime(time_string, '%Y-%m-%d %H:%M:%S')
    epoch = calendar.timegm(dt.timetuple()) + tz_diff
    if truncate:
        epoch = int(epoch / 86400) * 86400
    return str(epoch * 1000)


def get_value_presentation(field_type, value):
    if field_type == 'date':
        return to_unix_date(value)
    if field_type == 'integer' or field_type == 'period':
        return str(value)
    if field_type == 'string':
        return value
    if 'name' in value:
        return value['name']
    if 'value' in value:
        return value['value']


@ignore_youtrack_exceptions
def process_attachments(source, target, issue, replace=False):
    def get_attachment_hash(attach):
        return attach.name + '\n' + attach.created

    if 'attachment' not in issue['fields']:
        return
    issue_id = issue['key']
    existing_attachments = dict()
    for a in target.getAttachments(issue_id):
        existing_attachments[get_attachment_hash(a)] = a
    for jira_attachment in issue['fields']['attachment']:
        attachment = JiraAttachment(jira_attachment, source)
        attachment_hash = get_attachment_hash(attachment)
        if attachment_hash in existing_attachments and not replace:
            continue
        if 'author' in jira_attachment:
            create_user(target, jira_attachment['author'])
        attachment_name = attachment.name
        if isinstance(attachment_name, unicode):
            attachment_name = attachment_name.encode('utf-8')
        try:
            print('Creating attachment %s for issue %s' % \
                  (attachment_name, issue_id))
            target.createAttachmentFromAttachment(issue_id, attachment)
        except BaseException as e:
            print('Cannot create attachment %s' % attachment_name)
            print(e)
            continue
        if not replace:
            continue
        old_attachment = existing_attachments.get(attachment_hash)
        if not old_attachment:
            continue
        try:
            print('Deleting old version of attachment %s for issue %s' % \
                  (attachment_name, issue_id))
            target.deleteAttachment(issue_id, old_attachment.id)
        except BaseException as e:
            print('Cannot delete old version of attachment %s' % attachment_name)
            print(e)


@ignore_youtrack_exceptions
def process_worklog(source, target, issue):
    worklog = source.get_worklog(issue['key'])
    if worklog:
        work_items = []
        for w in worklog['worklogs']:
            create_user(target, w['author'])
            work_item = WorkItem()
            work_item.authorLogin = w['author']['name']
            work_item.date = to_unix_date(w['started'], truncate=True)
            if 'comment' in w:
                work_item.description = w['comment']
            work_item.duration = int(int(w['timeSpentSeconds']) / 60)
            work_items.append(work_item)
            #target.createWorkItem(issue['key'], work_item)
        target.importWorkItems(issue['key'], work_items)


def jira2youtrack(source_url, source_login, source_password,
                  target_url, target_login, target_password,
                  projects, flags, field_mappings, value_mappings):
    print('source_url   : ' + source_url)
    print('source_login : ' + source_login)
    print('target_url   : ' + target_url)
    print('target_login : ' + target_login)

    source = JiraClient(source_url, source_login, source_password)
    target = Connection(target_url, target_login, target_password)

    issue_links = []
    chunk_size = 10

    for project in projects:
        project_id, start, end = project
        try:
            target.createProjectDetailed(project_id, project_id, '', target_login)
        except YouTrackException:
            pass

        while True:
            _end = start + chunk_size - 1
            if end and _end > end:
                _end = end
            if start > _end:
                break
            print('Processing issues: %s [%d .. %d]' % (project_id, start, _end))
            try:
                jira_issues = source.get_issues(project_id, start, _end)
                start += chunk_size
                if not (jira_issues or end):
                    break
                # Filter out moved issues
                jira_issues = [issue for issue in jira_issues
                               if issue['key'].startswith('%s-' % project_id)]
                if flags & FI_ISSUES:
                    issues2import = []
                    for issue in jira_issues:
                        issues2import.append(
                            to_yt_issue(target, issue, project_id,
                                        field_mappings, value_mappings))
                    if not issues2import:
                        continue
                    target.importIssues(
                        project_id, '%s assignees' % project_id, issues2import)
            except YouTrackException as e:
                print(e)
                continue
            for issue in jira_issues:
                if flags & FI_LINKS:
                    process_links(target, issue, issue_links)
                if flags & FI_LABELS:
                    process_labels(target, issue)
                if flags & FI_ATTACHMENTS:
                    process_attachments(source, target, issue,
                                        flags & FI_REPLACE_ATTACHMENTS > 0)
                if flags & FI_WORK_LOG:
                    process_worklog(source, target, issue)

    if flags & FI_LINKS:
        target.importLinks(issue_links)


class JiraAttachment(object):
    def __init__(self, attach, source):
        if 'author' in attach:
            self.authorLogin = attach['author']['name'].replace(' ', '_')
        else:
            self.authorLogin = 'root'
        self._url = attach['content']
        self.name = attach['filename']
        self.created = to_unix_date(attach['created'])
        self._source = source

    def getContent(self):
        return urllib2.urlopen(
            urllib2.Request(self._url, headers=self._source._headers))

if __name__ == '__main__':
    main()
