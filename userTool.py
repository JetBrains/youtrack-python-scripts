#! /usr/bin/env python

import sys

if sys.version_info >= (3, 0):
    print("\nThe script doesn't support python 3. Please use python 2.7+\n")
    sys.exit(1)

import getopt
import os
from youtrack.sync.users import UserImporter
from youtrack.connection import Connection


def _import_all_users(source, target, import_groups):
    print('Starting user importing')
    user_importer = UserImporter(
        source, target, caching_users=True, import_groups=import_groups)
    start = 0
    imported_number = 0
    users_to_import = source.getUsersTen(start)
    while len(users_to_import):
        refined_users = [source.getUser(user.login) for user in users_to_import]
        imported_number += user_importer.importUsersRecursively(refined_users)
        start += 10
        users_to_import = source.getUsersTen(start)
        if imported_number % 20 == 0:
            print('Imported ' + str(imported_number) + ' users')
    print('Finished. Total number of imported users: ' + str(imported_number))


def _delete_all_users_except_root_and_guest(target):
    print('Starting user deleting')
    excluded = ['root', 'guest']
    deleted_number = 0
    users_to_delete = target.getUsersTen(0)
    while len(users_to_delete) > 2:
        for user in users_to_delete:
            if _check_login(user.login, excluded):
                target.deleteUser(user.login)
                deleted_number += 1
        users_to_delete = target.getUsersTen(0)
        if deleted_number % 50 == 0:
            print('Deleted ' + str(deleted_number) + ' users')
    print('Finished. Total number of deleted users: ' + str(deleted_number))


def _delete_all_groups_except_initial(target):
    print('Starting group deleting')
    excluded = ['All Users', 'New Users', 'Reporters']
    deleted_number = 0
    groups_to_delete = target.getGroups()
    for group in groups_to_delete:
        if group.name not in excluded:
            target.deleteGroup(group.name)
            deleted_number += 1
            print('Deleted ' + str(group.name) + ' users')
    print('Finished. Total number of deleted groups: ' + str(deleted_number))


def _import_one_user_with_groups(source, target, login):
    print('Starting user importing')
    user_importer = UserImporter(source, target, caching_users=False)
    users_to_import = [source.getUser(login)]
    if _check_login(login):
        user_importer.importUsersRecursively(users_to_import)
        print('User was successfully imported')
    else:
        print('User login ' + str(login) + ' contains prohibited chars')


def _check_login(login, excluded=None):
    if not excluded:
        excluded = []
    return login not in excluded and '/' not in login


def import_users(
        source_url, source_login, source_password,
        target_url, target_login, target_password, import_groups=False):

    source = Connection(source_url, source_login, source_password)
    target = Connection(target_url, target_login, target_password)

    _import_all_users(source, target, import_groups)
#    _delete_all_users_except_root_and_guest(target)
#    _delete_all_groups_except_initial(target)
#    _import_one_user_with_groups(source, target, 'batman')


def usage():
    print("""
Usage:
    %s [OPTIONS] s_url s_user s_pass t_url t_user t_pass

    s_url         Source YouTrack URL
    s_user        Source YouTrack user
    s_pass        Source YouTrack user's password
    t_url         Target YouTrack URL
    t_user        Target YouTrack user
    t_pass        Target YouTrack user's password

Options:
    -h,  Show this help and exit
    -g,  Import groups for users
""" % os.path.basename(sys.argv[0]))


def main():
    import_groups = False
    try:
        opts, args = getopt.getopt(sys.argv[1:], 'hg')
        for opt, val in opts:
            if opt == '-h':
                usage()
                sys.exit(0)
            elif opt == '-g':
                import_groups = True
        (source_url, source_login, source_password,
         target_url, target_login, target_password) = args[0:6]
    except getopt.GetoptError as e:
        print(e)
        usage()
        sys.exit(1)
    except ValueError:
        print('Not enough arguments')
        sys.exit(1)

    import_users(source_url, source_login, source_password,
                 target_url, target_login, target_password, import_groups)

if __name__ == "__main__":
    main()

