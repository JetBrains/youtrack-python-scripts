from youtrackutils import csvClient

csvClient.FIELD_NAMES = {
#default fields (always available)
  #required fields
    "Projects"      :   "project_name", #make sure that all the fields are filled out for each task
                                        #asana leaves them blank for entries with a Parent Task
    "Project ID"    :   "project_id", #needs to be added to the csv from asana
    "Number"        :   "numberInProject", #needs to be added
    "Name"          :   "summary",
    "Created At"    :   "created",
    "Reporter"      :   "reporterName", #needs to be added
  #optional
    "Notes"         :   "description",
    "Last Modified" :   "updated",
    #"Modified By"   :   "updaterName",
    "Completed At"  :   "resolved",
    #"Liked By"      :   "voterName",
    #"Watched By"    :   "watcherName",
    #"Group"         :   "permittedGroup",
  #not listed but found in code
    #"Tags"          :   "Tags", #can't get this to work properly
    #"Project Short" :   "projectShortName", #the same as project_id?
    
#extra fields defined in project
    "Assignee"      :   "Assignee",
    "Due Date"      :   "Due Date",
    #"Parent Task"   :   "Affected versions", #set this to something appropriate
    "State"         :   "State", #needs to be added
}
csvClient.FIELD_TYPES = {
    "Assignee"          :   "user[1]",
    "Due Date"          :   "date",
    "Affected versions" :   "version[*]",
    "State"             :   "state[1]",
}


csvClient.CSV_DELIMITER = ","
csvClient.DATE_FORMAT_STRING = "%Y-%m-%d"
csvClient.GENERATE_ID_FOR_ISSUES = True

