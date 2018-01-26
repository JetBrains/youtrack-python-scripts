FIELD_TYPES = {
#    u'java.lang.String': 'string',
#    u'java.util.Date': 'date',
#    u'com.atlassian.jira.project.version.Version': 'version[*]',
#    u'com.atlassian.jira.issue.issuetype.IssueType': 'enum[1]',
#    u'com.atlassian.jira.issue.priority.Priority': 'enum[1]',
#    u'com.atlassian.jira.issue.status.Status': 'state[1]',
#    u'com.opensymphony.user.User': 'user[1]',
#    u'com.atlassian.jira.bc.project.component.ProjectComponent': 'ownedField[*]',
#    u'com.atlassian.jira.plugin.system.customfieldtypes:importid': 'string',
#    u'com.atlassian.jira.plugin.system.customfieldtypes:radiobuttons': 'enum[1]',
#    u'com.atlassian.jira.toolkit:multikeyfield': 'enum[*]',
#    u'com.atlassian.jira.toolkit:participants': 'user[*]',
#    u'com.atlassian.jira.plugin.system.customfieldtypes:multicheckboxes': 'enum[*]',
#    u'com.atlassian.jira.plugin.system.customfieldtypes:textfield': 'string'
    u'aggregatetimespent'       : u'integer',
    u'aggregatetimeestimate'    : u'integer',
    u'Fix versions'             : u'version[*]',
    u'priority'                 : u'enum[1]',
    u'timespent'                : u'integer',
    u'State'                    : u'state[1]',
    u'Affected versions'        : u'version[*]',
    u'Type'                     : u'enum[*]',
    u'customfield_10550'        : u'string',
    u'assignee'                 : u'user[1]',
    u'customfield_10250'        : u'string',
    u'timeestimate'             : u'integer',
    u'components'               : u'ownedField[*]',
    u'resolution'               : u'state[1]',
    u'timeoriginalestimate'     : u'integer',
    u'aggregatetimeoriginalestimate'    : u'integer',
    u'customfield_10153'        : u'date',
    u'customfield_10051'        : u'date',
    u'customfield_10050'        : u'date',
    u'customfield_10156'        : u'string',
    u'customfield_10154'        : u'string',
    u'Estimation'               : u'period'
}

FIELD_NAMES = {
    u'reporter': 'reporterName',
    u'fixVersions': 'Fix versions',
    u'versions': 'Affected versions',
    u'status' : 'State',
    u'issuetype' : 'Type',
    u'resolutiondate' : 'resolved',
    u'timeoriginalestimate': 'Estimation'
}

EXISTING_FIELDS = ['numberInProject', 'projectShortName', 'summary', 'description', 'created',
                   'updated', 'updaterName', 'resolved', 'reporterName']


class JiraException(Exception):
    def __init__(self, *args, **kwargs):
        super(JiraException, self).__init__(*args, **kwargs)
