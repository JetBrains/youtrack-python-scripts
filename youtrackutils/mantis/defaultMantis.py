from youtrackutils import mantis

# maps the cf type in mantis with the cf type in yt
mantis.CF_TYPES = {
    0 : "string",     #String
    1 : "integer",    #Nimeric
    2 : "string",     #Float
    3 : "enum[1]",    #Enumeration
    4 : "string",     #Email
    5 : "enum[*]",    #Checkbox
    6 : "enum[1]",    #List
    7 : "enum[*]",    #Multiselection list
    8 : "date",       #Date
    9 : "enum[1]"     # Radio
}


PRIORITY_VALUES = {
    10 : "none",
    20 : "low",
    30 : "normal",
    40 : "high",
    50 : "urgent",
    60 : "immediate"
}

SEVERITY_VALUES = {
    10 : "Feature",
    20 : "Trivial",
    30 : "Text",
    40 : "Tweak",
    50 : "Minor",
    60 : "Major",
    70 : "Crash",
    80 : "Block",
    90 : "Super Blocker"
}

REPRODUCIBILITY_VALUES = {
    10  : "Always",
    30  : "Sometimes",
    50  : "Random",
    70  : "Have not tried",
    90  : "Unable to reproduce",
    100 : "N/A"
}

STATUS_VALUES = {
    10 : "new",
    20 : "feedback",
    30 : "acknowledged",
    40 : "confirmed",
    50 : "assigned",
    60 : "resolved",
    70 : "closed",
    75 : "some_status_3",
    80 : "some_status_1",
    90 : "some_status_2"
}

RESOLUTION_VALUES = {
    10 : "open",
    20 : "fixed",
    30 : "reopened",
    40 : "unable to reproduce",
    50 : "not fixable",
    60 : "duplicate",
    70 : "no change required",
    80 : "suspended",
    90 : "won't fix"
}

#maps mantis link types with yt link types
mantis.LINK_TYPES = {
    0 : "Duplicate",    #duplicate of
    1 : "Relates",      #related to
    2 : "Depend"        #parent of
}

mantis.FIELD_NAMES = {
    u"severity"         :   u"Severity",
    u"handler_id"       :   u"Assignee",
    u"status"           :   u"State",
    u"resolution"       :   u"Resolution",
    u"category_id"      :   u"Subsystem",
    u"version"          :   u"Affected versions",
    u"fixed_in_version" :   u"Fix versions",
    u"build"            :   u"Fixed in build",
    u"os_build"         :   u"OS version",
    u"os"               :   u"OS",
    u"due_date"         :   u"Mantis Due date",
    u"target_version"   :   u"Target version", # it's better to import this fields with version type
    u"priority"         :   u"Priority",
    u"platform"         :   u"Platform",
    u"last_updated"     :   u"updated",
    u"date_submitted"   :   u"created",
    u"reporter_id"      :   u"reporterName",
    u"id"               :   u"numberInProject",
    u'project_id'       :   u'Subproject'
}

mantis.FIELD_VALUES = {
    u"State"            : STATUS_VALUES,
    u"Reproducibility"  : REPRODUCIBILITY_VALUES,
    u"Priority"         : PRIORITY_VALUES,
    u"Severity"         : SEVERITY_VALUES,
    u"Resolution"       : RESOLUTION_VALUES
}

mantis.FIELD_TYPES = {
    u"Priority"             :   "enum[1]",
    u"State"                :   "state[1]",
    u"Resolution"           :   "state[1]",
    u"Fix versions"         :   "version[*]",
    u"Affected versions"    :   "version[*]",
    u"Assignee"             :   "user[1]",
    u"Fixed in build"       :   "build[1]",
    u"Subsystem"            :   "ownedField[1]",
    u"Subproject"           :   "ownedField[1]",
    u"Severity"             :   "enum[1]",
    u"Platform"             :   "string",
    u"OS"                   :   "string",
    u"OS version"           :   "string",
    u"Reproducibility"      :   "enum[1]",
    u"Mantis Due date"      :   "date",
    u"Target version"       :   "version[1]",
}

# charset of your mantis database
mantis.CHARSET = "utf8"

# If True then issues to import to YouTrack will be collected from a project
# and all it's subprojects.
# If False then subprojects' issues won't be taken in account.
mantis.BATCH_SUBPROJECTS = True
  
