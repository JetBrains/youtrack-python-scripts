from youtrackutils import csvClient 

csvClient.FIELD_NAMES = {
    "Project"       :   "project_name",
    "Project Id"    :   "project_id",
    "Summary"       :   "summary",
    "Reporter"      :   "reporterName",
    "Created"       :   "created",
    "Updated"       :   "updated",
    "Description"   :   "description",
    "Issue Id"      :   "numberInProject"
}
csvClient.FIELD_TYPES = {
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


csvClient.CSV_DELIMITER = ","
csvClient.DATE_FORMAT_STRING = "%A, %B %d, %Y %I:%M:%S %p %z"
