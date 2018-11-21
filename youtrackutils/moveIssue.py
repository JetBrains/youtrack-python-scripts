#! /usr/bin/env python

import sys

if sys.version_info >= (3, 0):
    print("\nThe script doesn't support python 3. Please use python 2.7+\n")
    sys.exit(1)

from youtrack import Issue, YouTrackException
from youtrack.connection import Connection
from youtrack.sync.links import LinkImporter

PREDEFINED_FIELDS = ["summary", "description", "created", "updated",
                     "updaterName", "resolved", "reporterName",
                     "assigneeName", "priority", "state"]


def main():
    try:
        (source_url, source_login, source_password,
         target_url, target_login, target_password) = sys.argv[1:7]
        source_id, target = sys.argv[7:]
    except (ValueError, IndexError):
        print("Usage: moveIssue source_url source_login source_password " +
              "target_url target_login target_password source_id " +
              "target_project_id_or_issue_id")
        sys.exit(1)
    do_move(source_url, source_login, source_password,
            target_url, target_login, target_password, source_id, target)


def check_user(user_login, source, target):
    if (user_login == "guest") or (user_login is None):
        return
    try:
        target.getUser(user_login)
    except YouTrackException:
        source_user = source.getUser(user_login)
        if not("email" in source_user):
            source_user.email = "no_email"
        print(target.importUsers([source_user]))
        print("User %s was created" % user_login)
        return user_login


def get_new_issue_id(project_id, target):
    max_id = 1
    max_number = 100
    while True:
        issues = target.getIssues(project_id, "", max_id, max_number)
        if len(issues) == 0:
            return max_id
        for issue in issues:
            issue_id = int(issue.numberInProject)
            if issue_id >= max_id:
                max_id = issue_id + 1


def get_time_tracking_state(source, target,
                            source_project_id, target_project_id):
    source_tt = source.getProjectTimeTrackingSettings(source_project_id)
    target_tt = target.getProjectTimeTrackingSettings(target_project_id)
    return source_tt and target_tt and source_tt.Enabled and target_tt.Enabled


def do_move(source_url, source_login, source_password,
            target_url, target_login, target_password, source_issue_id, target):
    print("source_url       : " + source_url)
    print("source_login     : " + source_login)
    print("source_password  : " + source_password)
    print("target_url       : " + target_url)
    print("target_login     : " + target_login)
    print("target_password  : " + target_password)
    print("source_id        : " + source_issue_id)

    if target.find('-') > -1:
        print("target_id        : " + target)
        target_project_id, target_issue_number = target.split('-')
    else:
        print("target_project_id: " + target)
        target_project_id = target
        target_issue_number = None

    # connecting
    try:
        target = Connection(target_url, target_login, target_password)
        print("Connected to target url [%s]" % target_url)
    except Exception as ex:
        print("Failed to connect to target url [%s] with login/password [%s/%s]"
              % (target_url, target_login, target_password))
        raise ex

    try:
        source = Connection(source_url, source_login, source_password)
        print("Connected to source url [%s]" % source_url)
    except Exception as ex:
        print("Failed to connect to source url [%s] with login/password [%s/%s]"
              % (source_url, source_login, source_password))
        raise ex

    try:
        target.getProject(target_project_id)
    except Exception as ex:
        print("Can't connect to target project [%s]" % target_project_id)
        raise ex

    # twin issues
    try:
        source_issue = source.getIssue(source_issue_id)
    except Exception as ex:
        print("Failed to get issue [%s]" % source_issue_id)
        raise ex

    target_issue = Issue()

    # import users if needed
    name_fields = ["reporterName", "assigneeName", "updaterName"]
    for field in name_fields:
        if field in source_issue:
            check_user(source_issue[field], source, target)

    if not target_issue_number:
        target_issue_number = str(get_new_issue_id(target_project_id, target))
    target_issue.numberInProject = target_issue_number

    # check subsystem
    target_subsystem = None
    try:
        target.getSubsystem(target_project_id, source_issue.subsystem)
        target_subsystem = source_issue.subsystem
    except (YouTrackException, AttributeError):
        pass
    target_issue.subsystem = target_subsystem
    for field in PREDEFINED_FIELDS:
        if field in source_issue:
            target_issue[field] = source_issue[field]

    if "Type" in source_issue:
        target_issue.type = source_issue["Type"]
    elif "type" in source_issue:
        target_issue.type = source_issue["type"]
    else:
        target_issue.type = "Bug"

    # convert custom field
    target_cfs = target.getProjectCustomFields(target_project_id)
    for cf in target_cfs:
        cf_name = cf.name
        if cf_name in source_issue:
            target_issue[cf_name] = source_issue[cf_name]

    # comments
    target_issue.comments = source_issue.getComments()
    for comment in target_issue.comments:
        check_user(comment.author, source, target)

    # import issue
    print(target.importIssues(
        target_project_id,
        "",
        [target_issue]))

    # attachments
    for attachment in source_issue.getAttachments():
        check_user(attachment.authorLogin, source, target)
        target.createAttachmentFromAttachment(
            "%s-%s" % (target_project_id, target_issue.numberInProject),
            attachment)

    # work items
    if get_time_tracking_state(
            source, target, source_issue_id.split('-')[0],
            target_project_id):
        workitems = source.getWorkItems(source_issue_id)
        if workitems:
            existing_workitems = dict()
            target_workitems = target.getWorkItems(
                target_project_id + '-' + target_issue_number)
            if target_workitems:
                for w in target_workitems:
                    _id = '%s\n%s\n%s' % (w.date, w.authorLogin, w.duration)
                    if hasattr(w, 'description'):
                        _id += '\n%s' % w.description
                    existing_workitems[_id] = w
            new_workitems = []
            for w in workitems:
                _id = '%s\n%s\n%s' % (w.date, w.authorLogin, w.duration)
                if hasattr(w, 'description'):
                    _id += '\n%s' % w.description
                if _id not in existing_workitems:
                    new_workitems.append(w)
            if new_workitems:
                print("Process workitems for issue [ " + source_issue_id + "]")
                try:
                    for w in new_workitems:
                        check_user(w.authorLogin, source, target)
                    target.importWorkItems(
                        target_project_id + '-' + target_issue_number,
                        new_workitems)
                except YouTrackException as e:
                    print("Failed to import workitems: " + str(e))

    # links
    link_importer = LinkImporter(target)
    links2import = source_issue.getLinks()
    link_importer.collectLinks(links2import)
    link_importer.addAvailableIssue(source_issue)
    for l in links2import:
        link_importer.addAvailableIssue(source.getIssue(l.source))
        link_importer.addAvailableIssue(source.getIssue(l.target))
    link_importer.importCollectedLinks()


if __name__ == "__main__":
    main()
