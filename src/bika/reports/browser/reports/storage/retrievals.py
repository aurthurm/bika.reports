# -*- coding: utf-8 -*-
"""The retrieval reports (issue #76 §19): what was retrieved and why, the
requests that were approved and declined, and the samples still out
"""

import collections
from datetime import date

from bika.lims import api
from bika.reports import _
from bika.reports.browser.reports.storage import data
from bika.reports.browser.reports.storage import filters
from bika.reports.browser.reports.storage.base import StorageReport
from bika.reports.browser.reports.storage.registry import register
from Products.CMFPlone.utils import safe_unicode

NONE = _(u"(none)")


def retrieval_lines(values):
    """The retrievals that were carried out, of the filters: the lines of
    the requests of retrieval that are completed, by date retrieved
    """
    for line in data.get_lines(data.TRANSACTION_RETRIEVE, "completed"):
        if values.get("project") and \
                values["project"] != line.originating_project:
            continue
        if values.get("requesting_project") and \
                values["requesting_project"] != line.requesting_project:
            continue
        if values.get("requester") and values["requester"] != line.requester:
            continue
        if values.get("reason") and values["reason"] != line.reason:
            continue
        if not data.date_in(line.physical_action_at,
                            values.get("retrieved")):
            continue
        yield line


class GroupedRetrievals(StorageReport):
    """The retrievals counted by something: requests and samples per group"""
    category = "retrieval"
    counted = ("requests", "samples")

    def group_of(self, line, values):
        raise NotImplementedError

    def get_rows(self, values):
        groups = collections.OrderedDict()
        for line in retrieval_lines(values):
            key = self.group_of(line, values)
            group = groups.setdefault(key, {"requests": set(),
                                            "samples": set()})
            group["requests"].add(line.request_uid)
            group["samples"].add(line.sample_uid)
        return [self.row(key, len(group["requests"]), len(group["samples"]))
                for key, group in sorted(groups.items())]

    def footer(self, rows):
        line = [{"value": _(u"Total"), "class": "total_label"}]
        line.extend({"value": sum(row[key] for row in rows)}
                    for key in self.counted)
        return [line]


@register
class ByReason(GroupedRetrievals):
    id = "storage_retrievals_by_reason"
    title = _(u"Retrievals by reason")
    description = _(u"The retrievals that were carried out, by the reason "
                    u"they were requested for")
    filters = (
        filters.DateRange("retrieved", _(u"Date retrieved")),
        filters.Project("project", _(u"Project")),
        filters.Requester("requester", _(u"Requested by")),
    )
    columns = (("reason", _(u"Reason")), ("requests", _(u"Requests")),
               ("samples", _(u"Samples")))

    def group_of(self, line, values):
        return safe_unicode(line.reason or u"")

    def row(self, key, requests, samples):
        return {"reason": key, "requests": requests, "samples": samples}


@register
class ByRequestingProject(GroupedRetrievals):
    id = "storage_retrievals_by_project"
    title = _(u"Retrievals by requesting project")
    description = _(u"The retrievals that were carried out, by the project "
                    u"they were requested for")
    filters = (
        filters.DateRange("retrieved", _(u"Date retrieved")),
        filters.Project("requesting_project", _(u"Requesting project")),
        filters.Reason("reason", _(u"Reason")),
    )
    columns = (("project", _(u"Requesting project")),
               ("requests", _(u"Requests")), ("samples", _(u"Samples")))

    def group_of(self, line, values):
        return data.project_title(line.requesting_project) or \
            safe_unicode(NONE)

    def row(self, key, requests, samples):
        return {"project": key, "requests": requests, "samples": samples}


@register
class ByDate(GroupedRetrievals):
    id = "storage_retrievals_by_date"
    title = _(u"Retrievals by date")
    description = _(u"The retrievals that were carried out, by day, week, "
                    u"month or year")
    filters = (
        filters.DateRange("retrieved", _(u"Date retrieved")),
        filters.Project("project", _(u"Project")),
        filters.Choice("group_by", _(u"Group by"), default="month", options=(
            ("day", _(u"Day")), ("week", _(u"Week")),
            ("month", _(u"Month")), ("year", _(u"Year")))),
    )
    columns = (("period", _(u"Period")), ("requests", _(u"Requests")),
               ("samples", _(u"Samples")))

    def group_of(self, line, values):
        day = data.to_date(line.physical_action_at)
        group = values.get("group_by", "month")
        if group == "day":
            return day.isoformat()
        if group == "week":
            year, week = day.isocalendar()[:2]
            return u"{}-W{:02d}".format(year, week)
        if group == "year":
            return u"{}".format(day.year)
        return day.strftime("%Y-%m")

    def row(self, key, requests, samples):
        return {"period": key, "requests": requests, "samples": samples}


class DecidedRequests(StorageReport):
    """The requests that a manager decided in a way: when, by whom, why"""
    category = "retrieval"
    states = ()
    columns = (
        ("request", _(u"Request")), ("type", _(u"Type")),
        ("samples", _(u"Samples")), ("reason", _(u"Reason")),
        ("requester", _(u"Requested by")), ("requested", _(u"Requested")),
        ("decision_by", _(u"Decided by")), ("decided", _(u"Decided")),
        ("state", _(u"State")),
    )

    def make_filters(self, decided_title):
        return (
            filters.Choice("type", _(u"Type of request"), default="RETRIEVE",
                           options=(("RETRIEVE", _(u"Retrieval")),
                                    ("RETURN", _(u"Return")),
                                    ("DISPOSE", _(u"Disposal")),
                                    ("all", _(u"All")))),
            filters.DateRange("decided", decided_title),
            filters.Requester("requester", _(u"Requested by")),
        )

    def get_rows(self, values):
        kind = values.get("type", "RETRIEVE")
        rows = []
        for request in data.get_requests(
                list(self.states), None if kind == "all" else kind):
            if values.get("requester") and \
                    values["requester"] != request.requester:
                continue
            if not data.date_in(request.decision_at, values.get("decided")):
                continue
            row = {
                "request": api.get_id(request),
                "type": request.transaction_type or u"",
                "samples": len(data.sapi.get_lines(request)),
                "reason": safe_unicode(request.reason or u""),
                "requester": request.requester or u"",
                "requested": data.iso(request.requested_at),
                "decision_by": request.decision_by or u"",
                "decided": data.iso(request.decision_at),
                "state": data.state_title(request),
            }
            row.update(self.extra(request))
            rows.append(row)
        return sorted(rows, key=lambda row: (row["decided"], row["request"]))

    def extra(self, request):
        return {}


@register
class Approved(DecidedRequests):
    id = "storage_requests_approved"
    title = _(u"Approved requests")
    description = _(u"The requests that a manager approved, and what became "
                    u"of them")
    states = ("approved", "completed")

    def __init__(self, context, request, report=None):
        super(Approved, self).__init__(context, request, report)
        self.filters = self.make_filters(_(u"Date approved"))


@register
class Declined(DecidedRequests):
    id = "storage_requests_declined"
    title = _(u"Declined requests")
    description = _(u"The requests that a manager declined, and why")
    states = ("declined",)
    columns = DecidedRequests.columns + (
        ("decision_reason", _(u"Reason declined")),)

    def __init__(self, context, request, report=None):
        super(Declined, self).__init__(context, request, report)
        self.filters = self.make_filters(_(u"Date declined"))

    def extra(self, request):
        return {"decision_reason": safe_unicode(
            request.decision_reason or u"")}


class Returns(StorageReport):
    """The samples that were retrieved and are not back"""
    category = "retrieval"
    filters = (
        filters.Project("project", _(u"Project")),
        filters.Project("requesting_project", _(u"Requesting project")),
        filters.Requester("requester", _(u"Requested by")),
    )
    columns = (
        ("sample", _(u"Sample")), ("project", _(u"Project")),
        ("requesting_project", _(u"Requesting project")),
        ("requester", _(u"Requested by")), ("retrieved", _(u"Retrieved")),
        ("days_out", _(u"Days out")), ("expected", _(u"Expected back")),
        ("request", _(u"Request")),
    )

    def lines(self):
        return data.sapi.get_out_of_storage()

    def get_rows(self, values):
        titles, rows, today = {}, [], date.today()
        for line in self.lines():
            sample = data.sample_of(line)
            if sample is None:
                continue
            uid = data.sapi.get_sample_project_uid(sample)
            if values.get("project") and values["project"] != uid:
                continue
            if values.get("requesting_project") and \
                    values["requesting_project"] != line.requesting_project:
                continue
            if values.get("requester") and \
                    values["requester"] != line.requester:
                continue
            request = data.sapi.get_request(line)
            retrieved = data.to_date(line.physical_action_at)
            row = {
                "sample": api.get_id(sample),
                "project": data.project_title(uid, titles),
                "requesting_project": data.project_title(
                    line.requesting_project, titles),
                "requester": line.requester or u"",
                "retrieved": data.iso(retrieved),
                "days_out": (today - retrieved).days if retrieved else u"",
                "expected": data.iso(line.expected_return_date),
                "request": api.get_id(request) if request else u"",
            }
            row.update(self.extra(line, today))
            rows.append(row)
        return self.order(rows)

    def extra(self, line, today):
        return {}

    def order(self, rows):
        return sorted(rows, key=lambda row: (-(row["days_out"] or 0),
                                             row["sample"]))


@register
class Outstanding(Returns):
    id = "storage_returns_outstanding"
    title = _(u"Outstanding returns")
    description = _(u"The samples that were retrieved and have not been "
                    u"returned, the ones out the longest first")


@register
class Overdue(Returns):
    id = "storage_returns_overdue"
    title = _(u"Overdue returns")
    description = _(u"The samples that are still out after the date they "
                    u"were expected back, the most overdue first")
    columns = Returns.columns + (("days_overdue", _(u"Days overdue")),)

    def lines(self):
        return data.sapi.get_overdue_retrievals()

    def extra(self, line, today):
        return {"days_overdue": (today - line.expected_return_date).days}

    def order(self, rows):
        return sorted(rows, key=lambda row: (-row["days_overdue"],
                                             row["sample"]))
