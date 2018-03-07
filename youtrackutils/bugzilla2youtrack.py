#! /usr/bin/env python
import getopt
import sys

from youtrackutils.utils.mapfile import dump_map_file, load_map_file

if sys.version_info >= (3, 0):
    print("\nThe script doesn't support python 3. Please use python 2.7+\n")
    sys.exit(1)

import calendar
import youtrack
from youtrack.connection import Connection, utf8encode
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

help_url = "\
https://www.jetbrains.com/help/youtrack/standalone/Import-from-Bugzilla.html"


def usage():
    basename = os.path.basename(sys.argv[0])

    print("""
Usage:
    %s [OPTIONS] yt_url bz_db bz_host bz_port bz_login bz_pass [bz_product]

    yt_url      YouTrack base URL
    
    bz_db       Bugzilla database name (the default database name is bugs)
    
    bz_host     MySQL server hostname which serves Bugzilla source database
    
    bz_port     MySQL server portThe port (the default port number is 3306)
    
    bz_login    The username to log in to the Bugzilla source database server
    
    bz_pass     The password to log in to the Bugzilla source database server
    
    bz_product  The optional name of the source product to import from Bugzilla
                To import multiple products, separate product names with commas
    
        The script uses default mapping settings to import data from source
    tracker, like how fields from source tracker should be imported to YouTrack.
        If you wish to modify the settings you can run the script with -g option
    to generate mapping file Then you'll be able to modify the file to feet your
    needs and re-run the script with the mapping file using -m option.

    For instructions, see:
    %s 

Options:
    -h,  Show this help and exit
    -g,  Generate mapping file from the defaults
    -T TOKEN_FILE,
         Path to file with permanent token
    -t TOKEN,
         Value for permanent token as text
    -u LOGIN,
         YouTrack user login to perform import on behalf of
    -p PASSWORD,
         YouTrack user password
    -m MAPPING_FILE,
         Path to mapping file that maps columns from csv to YouTrack fields

Examples:

    Generate mapping file (can be customized and used for further import)

    $ %s -g -m mapping.json


    Import issues using the mapping file:

    $ %s -T token https://youtrack.company.com bugs localhost 3306 bz bz


""" % (basename, help_url, basename, basename))


def main():
    try:
        params = {}
        opts, args = getopt.getopt(sys.argv[1:], 'hgu:p:m:t:T:')
        for opt, val in opts:
            if opt == '-h':
                usage()
                sys.exit(0)
            elif opt == '-g':
                params['generate_mapping'] = True
            elif opt == '-u':
                params['yt_login'] = val
            elif opt == '-p':
                params['yt_password'] = val
            elif opt == '-m':
                check_file_and_save(val, params, 'mapping_file')
            elif opt == '-t':
                params['token'] = val
            elif opt == '-T':
                check_file_and_save(val, params, 'token_file')
    except getopt.GetoptError as e:
        print(e)
        usage()
        sys.exit(1)

    if params.get('generate_mapping', False):
        return dump_map_file(get_mappings(), params.get('mapping_file'))

    try:
        for k in ('yt_url',
                  'bz_db', 'bz_host', 'bz_port', 'bz_login', 'bz_password'):
            params[k] = args.pop(0)
        params['bz_product_names'] = args
    except (ValueError, KeyError, IndexError):
        print("Bad arguments")
        usage()
        sys.exit(1)

    if 'mapping_file' in params:
        update_mappings(load_map_file(params['mapping_file']))
    bugzilla2youtrack(params)


def check_file_and_save(filename, params, key):
    try:
        params[key] = os.path.abspath(filename)
    except (OSError, IOError) as e:
        print("Data file is not accessible: " + str(e))
        print(filename)
        sys.exit(1)


def get_mappings():
    return dict(
        __help__="For instructions, see: " + help_url +
                 "#customize-mapping-file",
        field_names=youtrackutils.bugzilla.FIELD_NAMES,
        field_types=youtrackutils.bugzilla.FIELD_TYPES,
        cf_types=youtrackutils.bugzilla.CF_TYPES,
        bz_database_charset=youtrackutils.bugzilla.BZ_DB_CHARSET,
        use_state_map=youtrackutils.bugzilla.USE_STATE_MAP,
        state_map=youtrackutils.bugzilla.STATE_MAP
    )


def update_mappings(mapping_data):
    if 'bz_database_charset' in mapping_data:
        youtrackutils.bugzilla.BZ_DB_CHARSET = \
            str(mapping_data['bz_database_charset'])
    if 'use_state_map' in mapping_data:
        if str(mapping_data['use_state_map']).lower() \
                in ("yes", "true", "1"):
            youtrackutils.bugzilla.USE_STATE_MAP = True
    if 'state_map' in mapping_data:
        youtrackutils.bugzilla.STATE_MAP = mapping_data['state_map']
    if 'cf_types' in mapping_data:
        youtrackutils.bugzilla.CF_TYPES = mapping_data['cf_types']
    youtrackutils.bugzilla.FIELD_NAMES = mapping_data['field_names']
    youtrackutils.bugzilla.FIELD_TYPES = mapping_data['field_types']


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
        if youtrackutils.bugzilla.USE_STATE_MAP:
            if key.lower() == youtrackutils.bugzilla.STATE_STATUS.lower():
                bzStatus = value
            if key.lower() == youtrackutils.bugzilla.STATE_RESOLUTION.lower():
                bzRes = value

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

        value = get_yt_field_value_from_bz_field_value(value)

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
        comments = bz_issue.get("comments")
        if comments:
            issue.description = comments.pop(0).content
        for comment in comments:
            yt_comment = to_yt_comment(comment, target)
            if yt_comment is not None and yt_comment.text.lstrip() != '':
                issue.comments.append(yt_comment)
    if youtrackutils.bugzilla.USE_STATE_MAP:
        field_name = 'State'
        field_type = get_yt_field_type(field_name, target)
        if field_type and bzStatus in youtrackutils.bugzilla.STATE_MAP:
            pre_state = youtrackutils.bugzilla.STATE_MAP[bzStatus]
            if isinstance(pre_state, basestring):
                value = pre_state
            elif isinstance(pre_state, dict):
                if bzRes in pre_state:
                    value = pre_state[bzRes]
                elif '*' in pre_state:
                    value = pre_state['*']
                else:
                    value = bzStatus
            else:
                value = str(pre_state)
            add_value_to_field(
                field_name, field_type, value, project_id, target)
            issue[field_name] = value

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
            new_component = bundle.createElement(
                get_yt_field_value_from_bz_field_value(c.name))
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
            new_version = bundle.createElement(
                get_yt_field_value_from_bz_field_value(v.value))
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


def get_yt_field_value_from_bz_field_value(bz_value):
    if isinstance(bz_value, str) or isinstance(bz_value, unicode):
        return bz_value.replace("/", "_")
    if isinstance(bz_value, list) and len(bz_value) and \
            (isinstance(bz_value[0], str) or isinstance(bz_value[0], unicode)):
        return [v.replace("/", "_") for v in bz_value]
    return bz_value


def bugzilla2youtrack(params):
    # Connecting to Bugzilla
    client = Client(host=params['bz_host'],
                    port=int(params['bz_port']),
                    login=params['bz_login'],
                    password=params['bz_password'],
                    db_name=params['bz_db'])

    bz_product_names = params.get('bz_product_names')
    if not bz_product_names:
        answer = raw_input(
            "All projects will be imported. Are you sure? [Y/n] ")
        if answer.strip().lower() not in ("y", "yes", ""):
            sys.exit()
        bz_product_names = client.get_product_names()

    print("bz_product_names: " + repr(bz_product_names))

    # Connecting to YouTrack
    token = params.get('token')
    if not token and 'token_file' in params:
        try:
            with open(params['token_file'], 'r') as f:
                token = f.read().strip()
        except (OSError, IOError) as e:
            print("Cannot load token from file: " + str(e))
            sys.exit(1)
    if token:
        target = Connection(params['yt_url'], token=token)
    elif 'yt_login' in params:
        target = Connection(params['yt_url'],
                            params.get('yt_login'),
                            params.get('yt_password'))
    else:
        print("You have to provide token or login/password to import data")
        sys.exit(1)

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
            target.getProject(product_id)
        except YouTrackException:
            target.createProjectDetailed(
                product_id,
                name,
                client.get_project_description(product_id),
                'root'
            )

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
            batch = [bz_issue for bz_issue in batch]
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
                issue_id = str(product_id) + '-' + \
                           str(issue[get_number_in_project_field_name()])
                for attach in issue["attachments"]:
                    print("Processing attachment [ %s ] for issue %s" %
                          (utf8encode(attach.name), issue_id))
                    content = StringIO(attach.content)
                    try:
                        target.importAttachment(
                            issue_id, attach.name, content, attach.reporter.login,
                            None, None, str(int(attach.created) * 1000))
                    except Exception as e:
                        print("WARN: Cant import attachment [ %s ]" %
                              utf8encode(attach.name))
                        print(repr(e))
                        print("Please check Max Upload File Size in YouTrack")
                        continue
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
