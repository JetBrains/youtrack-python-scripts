from youtrackutils import bugzilla

bugzilla.FIELD_TYPES = {
    "created": "date",
    "updated": "date",
    "numberInProject": "integer",
    "reporterName": "user[1]",
    "Assignee": "user[1]",
    "Subsystem": "ownedField[1]",
    "Affected versions": "version[*]",
    "Severity": "enum[1]",
    "State": "state[1]",
    "Status": "state[1]",
    "Resolution": "state[1]",
    "OS": "enum[1]",
    "Platform": "enum[1]",
    "watcherName": "user[*]",
    "voterName": "user[*]",
    "Deadline": "date",
    "Estimate": "integer",
    "QA contact": "user[1]",
    "Milestone": "version[*]"
}

bugzilla.FIELD_NAMES = {
    "bug_id": "numberInProject",
    "reporter": "reporterName",
    "version": "Affected versions",
    "voters": "voterName",
    "assigned_to": "Assignee",
    "bug_severity": "Severity",
    "resolution": "Resolution",
    "bug_status": "Status",
    "creation_ts": "created",
    "op_sys": "OS",
    "rep_platform": "Platform",
    "short_desc": "summary",
    "cc": "watcherName",
    "delta_ts": "updated",
    "qa_contact": "QA contact",
    "estimated_time": "Estimate",
    "target_milestone": "Milestone",
    "component": "Subsystem",
}

# Mapping between cf types in bz and util
bugzilla.CF_TYPES = {
    "1": "string",   # FIELD_TYPE_FREETEXT
    "2": "enum[1]",  # FIELD_TYPE_SINGLE_SELECT
    "3": "enum[*]",  # FIELD_TYPE_MULTY_SELECT
    "4": "string",   # FIELD_TYPE_TEXTAREA
    "5": "date",     # FIELD_TYPE_DATETIME
    "7": "string"    # FIELD_TYPE_BUG_URLS
}

# If we need to import empty comments
bugzilla.ACCEPT_EMPTY_COMMENTS = False
bugzilla.BZ_DB_CHARSET = 'utf8'

bugzilla.USE_STATE_MAP = True
bugzilla.STATE_STATUS = "bug_status"
bugzilla.STATE_RESOLUTION = "resolution"


bugzilla.STATE_MAP = {
    "UNCONFIRMED": "Open",
    "CONFIRMED": "Submitted",
    "NEW": "Submitted",
    "ASSIGNED": "Submitted",
    "REOPENED": "Reopened",
    "FIXED": "Fixed",
    "INVALID": "Won't fix",
    "WONTFIX": "Won't fix",
    "MOVED": "Won't fix",
    "LATER": "Won't fix",
    "IN_PROGRESS": "In Progress",
    "DUPLICATE": "Duplicate",
    "VERIFIED": "Verified",
    "RESOLVED": {"FIXED": "Fixed", "*": "Won\'t fix", "DUPLICATE": "Duplicate"},
    "CLOSED": {"FIXED": "Fixed", "*": "Won\'t fix", "DUPLICATE": "Duplicate"}
}
