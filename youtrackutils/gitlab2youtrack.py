#! /usr/bin/env python

# Contributed by yavin5 <yavinfive464@gmail.com>
# Adapted from github2youtrack.py
# Currently issue comment attachments are not migrated, but everything else is.
import getopt
import sys

if sys.version_info >= (3, 0):
    print("\nThe script doesn't support python 3. Please use python 2.7+\n")
    sys.exit(1)

import os
import re
import requests
import logging
import csv
import youtrack
import youtrackutils.csvClient
import csv2youtrack
from youtrack.importHelper import utf8encode

import httplib as http_client
http_client.HTTPConnection.debuglevel = 1
logging.basicConfig()
logging.getLogger().setLevel(logging.DEBUG)
requests_log = logging.getLogger("requests.packages.urllib3")
requests_log.setLevel(logging.DEBUG)
requests_log.propagate = True

youtrackutils.csvClient.FIELD_NAMES = {
    "Project Name" : "project_name",
    "Project Id"   : "project_id",
    "Summary"      : "summary",
    "State"        : "State",
    "Id"           : "numberInProject",
    "Created"      : "created",
    "Updated"      : "updated",
    "Resolved"     : "resolved",
    "Assignee"     : "Assignee",
    "Description"  : "description",
    "Labels"       : "Labels",
    "Author"       : "reporterName",
    "Milestone"    : "Fix versions",
    "Weight"       : "Estimation",
    "Time Spent"   : "Spent Time"
}

youtrackutils.csvClient.FIELD_TYPES = {
    "State"        : "state[1]",
    "Assignee"     : "user[1]",
    "Labels"       : "enum[*]",
    "Fix versions" : "version[*]",
    "Type"         : "enum[1]"
}

youtrackutils.csvClient.DATE_FORMAT_STRING = "%Y-%m-%dT%H:%M:%SZ"
youtrackutils.csvClient.VALUE_DELIMITER = "|"
youtrackutils.csvClient.USE_MARKDOWN = True

CSV_FILE = "gitlab2youtrack-{repo}-{data}.csv"

help_url = "\
https://www.jetbrains.com/help/youtrack/standalone/import-from-gitlab.html"

GITLAB_API_ENDPOINT = "https://www.gitlab.com/api/v4"
gitlab_api_endpoint = GITLAB_API_ENDPOINT

def usage():
    basename = os.path.basename(sys.argv[0])

    print("""
Usage:
    %s [OPTIONS] yt_url gl_api_endpoint gl_login gl_token gl_project_name gl_project_id

    yt_url          YouTrack base URL

    gl_api_endpoint The REST API endpoint to the instance of GitLab

    gl_login        The username to log in to GitLab

    gl_token        The private token to log in to GitLab

    gl_project_name The name of the GitLab project to import issues from

    gl_project_id   The id of the GitLab project to import issues from

    For instructions, see:
    %s

Options:
    -h,  Show this help and exit
    -T TOKEN_FILE,
         Path to file with permanent token
    -t TOKEN,
         Value for permanent token as text
    -u LOGIN,
         YouTrack user login to perform import on behalf of
    -p PASSWORD,
         YouTrack user password

Examples:

    $ %s -T token https://youtrack.company.com https://api.gitlab.com/api/v4 gl-user gl-token gl_project_name gl_project_id


""" % (basename, help_url, basename))


def main():
    try:
        params = {}
        opts, args = getopt.getopt(sys.argv[1:], 'hu:p:t:T:')
        for opt, val in opts:
            if opt == '-h':
                usage()
                sys.exit(0)
            elif opt == '-u':
                params['login'] = val
            elif opt == '-p':
                params['password'] = val
            elif opt == '-t':
                params['token'] = val
            elif opt == '-T':
                check_file_and_save(val, params, 'token_file')
    except getopt.GetoptError as e:
        print(e)
        usage()
        sys.exit(1)

    try:
        params['target_url'], gitlab_api_endpoint, gitlab_user, gitlab_token, gitlab_project_name, gitlab_project_id = args
    except (ValueError, KeyError, IndexError):
        print("Bad arguments")
        usage()
        sys.exit(1)

    if gitlab_project_name.find('/') > -1:
        gitlab_project_owner, gitlab_project_name = gitlab_project_name.split('/')
    else:
        gitlab_project_owner = gitlab_user

    params['issues_file'] = CSV_FILE.format(repo=gitlab_project_name, data='issues')
    params['comments_file'] = CSV_FILE.format(repo=gitlab_project_name, data='comments')

    gitlab2csv(params['issues_file'],
               params['comments_file'],
               gitlab_api_endpoint,
               gitlab_user,
               gitlab_token,
               gitlab_project_name,
               gitlab_project_owner,
               gitlab_project_id)

    try:
        csv2youtrack.csv2youtrack(params)
    except youtrack.YouTrackException as e:
        print e
        pass

def check_file_and_save(filename, params, key):
    try:
        params[key] = os.path.abspath(filename)
    except (OSError, IOError) as e:
        print("Data file is not accessible: " + str(e))
        print(filename)
        sys.exit(1)


def get_last_part_of_url(url_string):
    return url_string.split('/').pop()


# based on https://gist.gitlab.com/unbracketed/3380407
def write_issues(r, issues_csvout, comments_csvout, gitlab_api_endpoint, gitlab_project_owner, gitlab_project_name, gitlab_project_id, headers):
    """output a list of issues to csv"""
    if not r.status_code == 200:
        raise Exception(r.status_code)
    for issue in r.json():
        labels = []
        labels_lowercase = []
        for label in issue['labels']:
            label_name = label
            if not label_name:
                continue
            labels.append(label_name)
            labels_lowercase.append(label_name)

        # TODO: Join writerow
        #labels = csvClient.VALUE_DELIMITER.join([str(x) for x in labels])

        assignee = issue['assignee']
        if assignee:
            assignee = assignee.get('username')
        else:
            assignee = issue['assignees']
            if assignee:
                assignee = assignee.get('username')

        created = issue['created_at']
        updated = issue.get('updated_at', '')
        resolved = issue.get('closed_at', '')

        author = issue['author'].get('username')
        if not author:
            # I'm not sure if the line below applies to Gitlab or just Github.
            author = get_last_part_of_url(issue['user'].get('url'))

        project = re.sub(r'[^\w]', '_', get_last_part_of_url(gitlab_project_name))

        milestone = issue.get('milestone')
        if milestone:
            milestone = milestone['title']
        else:
            milestone = ''

        state = issue['state'].lower()
        if state == 'closed':
            if 'wontfix' in labels_lowercase or 'invalid' in labels_lowercase:
                state = "Won't fix"
            else:
                state = "Fixed"

        issue_type = 'Task'
        if 'bug' in labels_lowercase:
            issue_type = 'Bug'

        issue_row = [project, project, issue['iid'], state, issue['title'],
                     issue['description'], created, updated, resolved, author or 'guest',
                     assignee, youtrackutils.csvClient.VALUE_DELIMITER.join(labels),
                     issue_type, milestone, str(issue['weight']) + "d",
                     issue['time_stats']['human_total_time_spent']]
        issues_csvout.writerow([utf8encode(e) for e in issue_row])

        # Handle migrating issue comments from GitLab to YouTrack.
        if int(issue.get('user_notes_count', 0)) > 0:
            gitlab_comments_url = "%s/projects/%s/issues/%s/notes?sort=asc&order_by=updated_at" % (gitlab_api_endpoint, gitlab_project_id, issue['iid']) 
            rc = requests.get(gitlab_comments_url, headers=headers)
            if not rc.status_code == 200:
                raise Exception(r.status_code)
            for comment in rc.json():
                author = comment['author'].get('username')
                if not author:
                    author = "guest"
                reg1 = re.compile('api/v4', re.VERBOSE)
                gitlab_base = reg1.sub(r'', gitlab_api_endpoint)
                comment_body = ''
                try:
                    reg2 = re.compile("mentioned in commit (\w+)", re.MULTILINE)
                    comment_body = reg2.sub(r"mentioned in commit [\1](" + gitlab_base + gitlab_project_owner + "/" + gitlab_project_name + r"/commit/\1) in GitLab.", str(comment['body']))
                    reg3 = re.compile("mentioned in merge request \!(\d+)", re.MULTILINE)
                    comment_body = reg3.sub(r"mentioned in merge request [!\1](" + gitlab_base + gitlab_project_owner + "/" + gitlab_project_name + r"/merge_requests/\1) in GitLab.", comment_body)
                    #print str(comment['body'])
                    #print comment_body
                except (UnicodeEncodeError, RuntimeError, TypeError, NameError):
                    pass
                comment_row = [project, issue['iid'], author or 'guest',
                               comment['created_at'], comment_body]
                comments_csvout.writerow([utf8encode(e) for e in comment_row])


def gitlab2csv(issues_csv_file, comments_csv_file, gitlab_api_endpoint, gitlab_user, gitlab_token, gitlab_project_name, gitlab_project_owner, gitlab_project_id):
    issues_url = '%s/projects/%s/issues?id=18&order_by=created_at&page=1&per_page=100&sort=desc&state=all' % (gitlab_api_endpoint, gitlab_project_id)
    HEADERS = {'PRIVATE-TOKEN': gitlab_token}

    r = requests.get(issues_url, headers=HEADERS)
    issues_csvout = csv.writer(open(issues_csv_file, 'wb'))
    issues_csvout.writerow(
        ('Project Name', 'Project Id', 'Id', 'State', 'Summary', 'Description',
         'Created', 'Updated', 'Resolved', 'Author', 'Assignee', 'Labels',
         'Type', 'Milestone', 'Weight', 'Time Spent'))
    comments_csvout = csv.writer(open(comments_csv_file, 'wb'))
    write_issues(r, issues_csvout, comments_csvout, gitlab_api_endpoint, gitlab_project_owner, gitlab_project_name, gitlab_project_id, HEADERS)

    #more pages? examine the 'link' header returned
    if 'link' in r.headers:
        pages = dict(
            [(rel[6:-1], url[url.index('<')+1:-1]) for url, rel in
                [link.split(';') for link in
                    r.headers['link'].split(',')]])
        while 'last' in pages and 'next' in pages:
            r = requests.get(pages['next'], headers=HEADERS)
            write_issues(r, issues_csvout, comments_csvout, gitlab_api_endpoint, gitlab_project_owner, gitlab_project_name, gitlab_project_id, HEADERS)
            pages = dict(
                [(rel[6:-1], url[url.index('<') + 1:-1]) for url, rel in
                 [link.split(';') for link in
                  r.headers['link'].split(',')]])


if __name__ == "__main__":
    main()
