class Mapping(object):
    FIELD_NAMES = {
        'id'              : 'numberInProject',
        'subject'         : 'summary',
        'author'          : 'reporterName',
        'status'          : 'State',
        'priority'        : 'Priority',
        'created_on'      : 'created',
        'updated_on'      : 'updated',
        'tracker'         : 'Type',
        'assigned_to'     : 'Assignee',
        'due_date'        : 'Due Date',
        'estimated_hours' : 'Estimation',
        'category'        : 'Subsystem',
        'fixed_version'   : 'Fix versions',
        'redmine_id'      : 'Redmine ID'
    }

    FIELD_TYPES = {
        'Type'         : 'enum[1]',
        'State'        : 'state[1]',
        'Priority'     : 'enum[1]',
        'Assignee'     : 'user[1]',
        'Due Date'     : 'date',
        'Estimation'   : 'period',
        'Subsystem'    : 'ownedField[1]',
        'Fix versions' : 'version[*]',
        'Redmine ID'   : 'integer'
    }

    CONVERSION = {
        'State': {
            'Resolved' : 'Fixed',
            'Closed'   : 'Fixed',
            'Rejected' : "Won't fix"
        },
        'Priority': {
            'High'      : 'Major',
            'Low'       : 'Minor',
            'Urgent'    : 'Critical',
            'Immediate' : 'Show-stopper'
        }
    }

#    RESOLVED_STATES = [
#        "Can't Reproduce",
#        "Duplicate",
#        "Fixed",
#        "Won't fix",
#        "Incomplete",
#        "Obsolete",
#        "Verified"
#    ]

    PERMISSIONS = {
        'add_project'           : 'CREATE_PROJECT',
        'edit_project'          : 'UPDATE_PROJECT',
        'close_project'         : 'DELETE_PROJECT',
        'manage_members'        : [ 'CREATE_USER', 'READ_USER', 'UPDATE_USER',
                                    'CREATE_USERGROUP', 'READ_USERGROUP',
                                    'UPDATE_USERGROUP' ],
        'add_messages'          : 'CREATE_COMMENT',
        'edit_messages'         : 'UPDATE_NOT_OWN_COMMENT',
        'edit_own_messages'     : 'UPDATE_COMMENT',
        'delete_messages'       : 'DELETE_NOT_OWN_COMMENT',
        'delete_own_messages'   : 'DELETE_COMMENT',
        'view_issues'           : 'READ_ISSUE',
        'add_issues'            : 'CREATE_ISSUE',
        'edit_issues'           : 'UPDATE_ISSUE',
        'delete_issues'         : 'DELETE_ISSUE',
        'view_issue_watchers'   : 'VIEW_WATCHERS',
        'add_issue_watchers'    : 'UPDATE_WATCHERS',
        'delete_issue_watchers' : 'UPDATE_WATCHERS',
        'log_time'              : 'UPDATE_WORK_ITEM',
        'view_time_entries'     : 'READ_WORK_ITEM',
        'edit_time_entries'     : 'UPDATE_WORK_ITEM',
        'edit_own_time_entries' : 'UPDATE_NOT_OWN_WORK_ITEM',
#        'select_project_modules'        : None,
#        'manage_versions'               : None,
#        'add_subprojects'               : None,
#        'manage_boards'                 : None,
#        'view_calendar'                 : None,
#        'manage_documents'              : None,
#        'view_documents'                : None,
#        'manage_files'                  : None,
#        'view_files'                    : None,
#        'view_gantt'                    : None,
#        'manage_categories'             : None,
#        'manage_issue_relations'        : None,
#        'manage_subtasks'               : None,
#        'set_issues_private'            : None,
#        'set_own_issues_private'        : None,
#        'add_issue_notes'               : None,
#        'edit_issue_notes'              : None,
#        'edit_own_issue_notes'          : None,
#        'view_private_notes'            : None,
#        'set_notes_private'             : None,
#        'move_issues'                   : None,
#        'manage_public_queries'         : None,
#        'save_queries'                  : None,
#        'manage_news'                   : None,
#        'comment_news'                  : None,
#        'manage_project_activities'     : None,
#        'manage_wiki'                   : None,
#        'rename_wiki_pages'             : None,
#        'delete_wiki_pages'             : None,
#        'view_wiki_pages'               : None,
#        'export_wiki_pages'             : None,
#        'view_wiki_edits'               : None,
#        'edit_wiki_pages'               : None,
#        'delete_wiki_pages_attachments' : None,
#        'protect_wiki_pages'            : None
    }
