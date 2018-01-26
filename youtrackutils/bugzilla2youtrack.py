#! /usr/bin/env python

import sys

if sys.version_info >= (3, 0):
    print("\nThe script doesn't support python 3. Please use python 2.7+\n")
    sys.exit(1)

import calendar
import youtrack
from youtrack.connection import Connection
from youtrackutils.bugzilla.bzClient import Client
from youtrack import *
from StringIO import StringIO
import youtrackutils.bugzilla.defaultBzMapping
import youtrackutils.bugzilla
import os
from youtrack.importHelper import create_custom_field, process_custom_field

# Enable unbuffered output
sys.stdout = os.fdopen(sys.stdout.fileno(), 'w', 0)
sys.stderr = os.fdopen(sys.stderr.fileno(), 'w', 0)


def main():
    try:
        target_url, target_login, target_pass, bz_db, bz_host, bz_port, bz_login, bz_pass = sys.argv[1:9]
        bz_product_names = sys.argv[9:]
    except:
        sys.exit()
        #    issues_filter = lambda issue: ("bug_status" in issue) and (issue["bug_status"] in ['UNCONFIRMED', 'NEW', 'ASSIGNED', 'REOPENED'])
    bugzilla2youtrack(target_url, target_login, target_pass, bz_db, bz_host, bz_port, bz_login, bz_pass,
        bz_product_names, lambda issue: True)


def to_yt_user(bz_user):
    user = User()
    user.login = bz_user.login
    user.email = bz_user.email
    user.fullName = bz_user.full_name
    return user


def to_unix_date(value):
    return str(calendar.timegm(value.timetuple()) * 1000)


def import_single_user(bz_user, target):
    target.importUsers([to_yt_user(bz_user)])


def to_yt_comment(bz_comment, target):
    comment = Comment()
    if bz_comment.reporter != "":
        import_single_user(bz_comment.reporter, target)
        comment.author = bz_comment.reporter.login
    else:
        comment.author = "guest"
    if bz_comment.content != "":
        comment.text = bz_comment.content
    else:
        return None
    comment.created = str(int(bz_comment.time * 1000))
    return comment


def to_yt_issue_link_type(bz_link_type):
    link_type = IssueLinkType()
    link_type.name = bz_link_type.name
    if bz_link_type.description != "":
        link_type.outwardName = bz_link_type.description
        link_type.inwardName = "incoming " + bz_link_type.description
    else:
        link_type.outwardName = bz_link_type.name
        link_type.inwardName = "incoming " + bz_link_type.name
    link_type.directed = True
    return link_type


def to_yt_issue_link(bz_issue_link):
    link = Link()
    link.typeName = bz_issue_link.name
    link.source = str(bz_issue_link.target_product_id) + "-" + str(bz_issue_link.target)
    link.target = str(bz_issue_link.source_product_id) + "-" + str(bz_issue_link.source)
    return link


def add_value_to_field(field_name, field_type, field_value, project_id, target):
    if (field_type is not None) and field_type.startswith("user"):
        import_single_user(field_value, target)
        field_value = field_value.login
    if field_name in youtrack.EXISTING_FIELDS:
        return
    custom_field = target.getProjectCustomField(project_id, field_name)
    if hasattr(custom_field, "bundle"):
        bundle = target.getBundle(field_type, custom_field.bundle)
        try:
            target.addValueToBundle(bundle, field_value)
        except YouTrackException:
            pass


def get_yt_field_type(field_name, target):
    if field_name in youtrackutils.bugzilla.FIELD_TYPES:
        return youtrackutils.bugzilla.FIELD_TYPES[field_name]
    try:
        return target.getCustomField(field_name).type
    except YouTrackException:
        return None


def get_yt_field_name(field_name, target):
    if field_name in youtrackutils.bugzilla.FIELD_NAMES:
        return youtrackutils.bugzilla.FIELD_NAMES[field_name]
    if field_name in youtrack.EXISTING_FIELDS:
        return field_name
    try:
        target.getCustomField(field_name)
        return field_name
    except YouTrackException:
        return None


def to_yt_issue(bz_issue, project_id, target):
    issue = Issue()
    issue.comments = []
    bzStatus = None
    bzRes = None

    for key in bz_issue.keys():
        value = bz_issue[key]
        if youtrackutils.bugzilla.USE_STATE_MAP and key == youtrackutils.bugzilla.STATE_STATUS:
            bzStatus = value
            continue 
        if youtrackutils.bugzilla.USE_STATE_MAP and key == youtrackutils.bugzilla.STATE_RESOLUTION:
            bzRes    = value
            continue 

        if key in ['flags', 'tags', 'attachments', 'comments']:
            continue
        field_name = get_yt_field_name(key, target)
        if field_name is None:
            continue
        if value is None:
            continue

        if isinstance(value, list):
            if not len(value):
                continue
        elif not len(unicode(value)):
            continue
        field_type = get_yt_field_type(field_name, target)
        if (field_type is None) and (field_name not in youtrack.EXISTING_FIELDS):
            continue

        value = get_yt_field_value_from_bz_field_value(field_name, field_type, value)

        if isinstance(value, list):
            for v in value:
                add_value_to_field(field_name, field_type, v, project_id, target)
        else:
            add_value_to_field(field_name, field_type, value, project_id, target)

        if (field_type is not None) and field_type.startswith("user"):
            if isinstance(value, list):
                value = [v.login for v in value]
            else:
                value = value.login
        if field_type == "date":
            value = to_unix_date(value)
        if not isinstance(value, list):
            value = unicode(value)

        issue[field_name] = value
    if "comments" in bz_issue:
        for comment in bz_issue["comments"]:
            yt_comment = to_yt_comment(comment, target)
            if yt_comment is not None and yt_comment.text.lstrip() != '':
                issue.comments.append(yt_comment)
    if youtrackutils.bugzilla.USE_STATE_MAP:
        prestate = youtrackutils.bugzilla.STATE_MAP[bzStatus]
        resultState = None
        if isinstance(prestate, str):
            resultState = prestate
        else:
            if bzRes in prestate:
                resultState = prestate[bzRes]
            else:
                resultState = prestate["*"]
        issue["State"] = resultState

    return issue


def get_name_for_new_cf(cf):
    if cf in youtrackutils.bugzilla.FIELD_NAMES:
        return youtrackutils.bugzilla.FIELD_NAMES[cf]
    return cf


def create_yt_custom_field(cf, target):
    cf_name = get_name_for_new_cf(cf.name)
    cf_type = youtrackutils.bugzilla.CF_TYPES[cf.type]
    if cf_name in youtrackutils.bugzilla.FIELD_TYPES:
        cf_type = youtrackutils.bugzilla.FIELD_TYPES[cf_name]
    create_custom_field(target, cf_type, cf_name, True)


def create_project_field(project_id, target, name):
    yt_cf_name = get_name_for_new_cf(name)
    field_type = get_yt_field_type(yt_cf_name, target)
    process_custom_field(target, project_id, field_type, yt_cf_name)
    cf = target.getProjectCustomField(project_id, yt_cf_name)
    return cf, field_type


def process_components(components, project_id, target):
    cf, field_type = create_project_field(project_id, target, "component")
    if hasattr(cf, "bundle"):
        bundle = target.getBundle(field_type, cf.bundle)
        for c in components:
            new_component = bundle.createElement(get_yt_field_value_from_bz_field_value(cf.name, field_type, c.name))
            if isinstance(new_component, OwnedField):
                if c.initial_owner is not None:
                    import_single_user(c.initial_owner, target)
                    new_component.login = c.initial_owner.login
            try:
                target.addValueToBundle(bundle, new_component)
            except YouTrackException:
                pass


def process_versions(versions, project_id, target):
    cf, field_type = create_project_field(project_id, target, "version")
    if hasattr(cf, "bundle"):
        bundle = target.getBundle(field_type, cf.bundle)
        for v in versions:
            new_version = bundle.createElement(get_yt_field_value_from_bz_field_value(cf.name, field_type, v.value))
            if isinstance(new_version, VersionField):
                new_version.released = True
                new_version.archived = False
            try:
                target.addValueToBundle(bundle, new_version)
            except YouTrackException:
                pass


def get_number_in_project_field_name():
    for key, value in youtrackutils.bugzilla.FIELD_NAMES.items():
        if value == "numberInProject":
            return key


def get_yt_field_value_from_bz_field_value(yt_field_name, yt_field_type, bz_value):
    if isinstance(bz_value, str) or isinstance(bz_value, unicode):
        return bz_value.replace("/", "_")
    if isinstance(bz_value, list) and len(bz_value) and (
        isinstance(bz_value[0], str) or isinstance(bz_value[0], unicode)):
        return [v.replace("/", "_") for v in bz_value]
    return bz_value


def bugzilla2youtrack(target_url, target_login, target_pass, bz_db, bz_host, bz_port, bz_login, bz_pass,
                      bz_product_names, issues_filter):
    # connecting to bz
    client = Client(bz_host, int(bz_port), bz_login, bz_pass, db_name=bz_db)

    if not len(bz_product_names):
        answer = raw_input("All projects will be imported. Are you sure? [y/n]")
        if answer.capitalize() != "Y":
            sys.exit()
        bz_product_names = client.get_product_names()

    print("bz_product_names :   " + repr(bz_product_names))

    # connecting to yt
    target = Connection(target_url, target_login, target_pass)

    print("Creating issue link types")
    link_types = client.get_issue_link_types()
    for link in link_types:
        print("Processing link type [ %s ]" % link.name)
        try:
            target.createIssueLinkType(to_yt_issue_link_type(link))
        except YouTrackException:
            print("Can't create link type [ %s ] (maybe because it already exists)" % link.name)
    print("Creating issue link types finished")

    print("Creating custom fields")
    custom_fields = client.get_custom_fields()
    for cf in custom_fields:
        create_yt_custom_field(cf, target)
    print("Creating custom fields finished")

    for key in youtrackutils.bugzilla.FIELD_TYPES:
        if key not in youtrack.EXISTING_FIELDS:
            create_custom_field(target, youtrackutils.bugzilla.FIELD_TYPES[key], key, True, bundle_policy="1")

    bz_product_ids = []

    for name in bz_product_names:
        product_id = str(client.get_product_id_by_name(name))
        bz_product_ids.append(product_id)
        print("Creating project [ %s ] with name [ %s ]" % (product_id, name))
        try:
            target.getProject(str(product_id))
        except YouTrackException:
            target.createProjectDetailed(str(product_id), name, client.get_project_description(product_id),
                target_login)

        print("Importing components for project [ %s ]" % product_id)
        process_components(client.get_components(product_id), product_id, target)
        print("Importing components finished for project [ %s ]" % product_id)

        print("Importing versions for project [ %s ]" % product_id)
        process_versions(client.get_versions(product_id), product_id, target)
        print("Importing versions finished for project [ %s ] finished" % product_id)

        print("Importing issues to project [ %s ]" % product_id)
        max_count = 100
        count = 0
        from_id = 0
        bz_issues_count = client.get_issues_count(product_id)
        while count < bz_issues_count:
            batch = client.get_issues(product_id, from_id, from_id + max_count)
            batch = [bz_issue for bz_issue in batch if (issues_filter(bz_issue))]
            count += len(batch)
            from_id += max_count
            target.importIssues(product_id, product_id + " assignees",
                [to_yt_issue(bz_issue, product_id, target) for bz_issue in batch])
            # todo convert to good tags import
            for issue in batch:
                tags = issue["keywords"] | issue["flags"]
                for t in tags:
                    print("Processing tag [ %s ]" % t.encode('utf8'))
                    target.executeCommand(str(product_id) + "-" + str(issue[get_number_in_project_field_name()]),
                        "tag " + t.encode('utf8'))
            for issue in batch:
                for attach in issue["attachments"]:
                    print("Processing attachment [ %s ]" % (attach.name.encode('utf8')))
                    content = StringIO(attach.content)
                    target.createAttachment(str(product_id) + "-" + str(issue[get_number_in_project_field_name()]),
                        attach.name, content, attach.reporter.login
                        , created=str(int(attach.created) * 1000))
        print("Importing issues to project [ %s ] finished" % product_id)

    # todo add pagination to links
    print("Importing issue links")
    cf_links = client.get_issue_links()
    duplicate_links = client.get_duplicate_links()
    if len(duplicate_links):
        try:
            target.createIssueLinkTypeDetailed("Duplicate", "duplicates", "is duplicated by", True)
        except YouTrackException:
            print("Can't create link type [ Duplicate ] (maybe because it already exists)")
    depend_links = client.get_dependencies_link()
    if len(depend_links):
        try:
            target.createIssueLinkTypeDetailed("Depend", "depends on", "is required for", True)
        except YouTrackException:
            print("Can't create link type [ Depend ] (maybe because it already exists)")
    links = cf_links | duplicate_links | depend_links

    links_to_import = list([])
    for link in links:
        print("Processing link %s for issue%s" % (link.name, link.source))
        if (str(link.target_product_id) in bz_product_ids) and (str(link.source_product_id) in bz_product_ids):
            links_to_import.append(to_yt_issue_link(link))
    print(target.importLinks(links_to_import))
    print("Importing issue links finished")


if __name__ == "__main__":
    main()
