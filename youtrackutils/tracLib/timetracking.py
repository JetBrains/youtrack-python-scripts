from youtrackutils.tracLib import TracWorkItem, to_unix_time

class TimeTrackingPlugin(object):
    @classmethod
    def get_name(self):
        raise NotImplementedError

    def __init__(self, trac_env):
        self.env = trac_env

    def _get_issue_workitems(self, ticket_id):
        raise NotImplementedError

    def _build_workitem(self, time, duration, author, comment=None):
        return TracWorkItem(time, duration, author, comment)

    def __getitem__(self, id_):
        return self._get_issue_workitems(id_)


class TimeHoursPlugin(TimeTrackingPlugin):
    @classmethod
    def get_name(self):
        return 'trachours'

    def _get_issue_workitems(self, ticket_id):
        query = """
            SELECT
                time_started * 1000, /* convert to format with millis */
                seconds_worked,
                worker,
                comments
            FROM
                ticket_time
            WHERE
                ticket=%s
            ORDER BY
                time_started DESC
        """ % str(ticket_id)

        workitems = []
        for time, duration, author, comment in self.env.db_query(query):
            workitems.append(
                self._build_workitem(time, duration, author, comment))

        return workitems


class TimingAndEstimationPlugin(TimeTrackingPlugin):
    @classmethod
    def get_name(self):
        return 'timingandestimationplugin'

    def _get_issue_workitems(self, ticket_id):
        query = """
            SELECT
                time,
                newvalue * 3600, /* convert hours to seconds */
                author
            FROM
                ticket_change
            WHERE
                ticket=%s
            AND
                field='hours'
            ORDER BY
                time DESC
        """ % str(ticket_id)

        workitems = []
        for time, duration, author in self.env.db_query(query):
            workitems.append(
                self._build_workitem(to_unix_time(time), duration, author))

        return workitems


plugins = (TimeHoursPlugin,
           TimingAndEstimationPlugin)
