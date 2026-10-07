# -*- coding: utf-8 -*-
"""The storage reports, by category, in the order of the page"""

import collections

from bika.reports import _

# the sections of the Storage page
CATEGORIES = (
    ("project", _(u"Project reports")),
    ("storage", _(u"Storage reports")),
    ("retrieval", _(u"Retrieval reports")),
)

_REPORTS = collections.OrderedDict()


def register(report_class):
    """Makes a report available on the Storage page and to `createreport`.
    Can be used as a decorator
    """
    _REPORTS[report_class.id] = report_class
    return report_class


def unregister(report_id):
    _REPORTS.pop(report_id, None)


def get_report_class(report_id):
    """The class of the report, or None. A report is found here and never by
    a module name from a request
    """
    return _REPORTS.get(report_id)


def get_reports(category):
    """The reports of a category, in the order they were registered"""
    return [report for report in _REPORTS.values()
            if report.category == category]
