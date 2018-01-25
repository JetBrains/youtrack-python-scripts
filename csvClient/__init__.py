# represents the format of the string (see http://docs.python.org/library/datetime.html#strftime-strptime-behavior)
# format symbol "z" doesn't wok sometimes, maybe you will need to change csv2youtrack.to_unix_date(time_string)
DATE_FORMAT_STRING = ""


FIELD_NAMES = {
    "Project"       :   "project",
    "Summary"       :   "summary",
    "Reporter"      :   "reporterName",
    "Created"       :   "created",
    "Updated"       :   "updated",
    "Description"   :   "description"
}
FIELD_TYPES = {
    "Fix versions"      :   "version[*]",
    "State"             :   "state[1]",
    "Assignee"          :   "user[1]",
    "Affected versions" :   "version[*]",
    "Fixed in build"    :   "build[1]",
    "Priority"          :   "enum[1]",
    "Subsystem"         :   "ownedField[1]",
    "Browser"           :   "enum[1]",
    "OS"                :   "enum[1]",
    "Verified in build" :   "build[1]",
    "Verified by"       :   "user[1]",
    "Affected builds"   :   "build[*]",
    "Fixed in builds"   :   "build[*]",
    "Reviewed by"       :   "user[1]",
    "Story points"      :   "integer",
    "Value"             :   "integer",
    "Marketing value"   :   "integer"
}

CSV_DELIMITER = ","
