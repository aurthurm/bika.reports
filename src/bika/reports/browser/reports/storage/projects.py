# -*- coding: utf-8 -*-
"""The project reports (issue #76 §17): what happened to the samples of the
projects, filtered by project, sample type and date
"""

import collections

from bika.lims import api
from bika.reports import _
from bika.reports.browser.reports.storage import data
from bika.reports.browser.reports.storage import filters
from bika.reports.browser.reports.storage.base import StorageReport
from bika.reports.browser.reports.storage.registry import register
from Products.CMFPlone.utils import safe_unicode


class ProjectSamplesReport(StorageReport):
    """A list of samples of the projects, counted by project at the end"""
    category = "project"

    def project_of(self, sample, titles):
        return data.project_title(
            data.sapi.get_sample_project_uid(sample), titles)

    def footer(self, rows):
        span = max(len(self.columns) - 1, 1)
        counts = collections.OrderedDict()
        for row in rows:
            counts[row["project"]] = counts.get(row["project"], 0) + 1
        lines = [[{"value": project, "colspan": span}, {"value": count}]
                 for project, count in counts.items()]
        lines.extend(super(ProjectSamplesReport, self).footer(rows))
        return lines


@register
class Registered(ProjectSamplesReport):
    id = "storage_project_registered"
    title = _(u"Samples registered by project")
    description = _(u"The samples that were registered for a project, with "
                    u"the date they were registered")
    filters = (
        filters.Project("project", _(u"Project")),
        filters.SampleType("sampletype", _(u"Sample type")),
        filters.DateRange("created", _(u"Date registered")),
    )
    columns = (
        ("project", _(u"Project")), ("sample", _(u"Sample")),
        ("sample_type", _(u"Sample type")), ("state", _(u"State")),
        ("created", _(u"Registered")),
    )

    def get_rows(self, values):
        titles = {}
        samples = data.get_project_samples(
            values.get("project"), sampletype=values.get("sampletype"),
            created=values.get("created"))
        return [{
            "project": self.project_of(sample, titles),
            "sample": api.get_id(sample),
            "sample_type": safe_unicode(sample.getSampleTypeTitle()),
            "state": data.state_title(sample),
            "created": data.iso(sample.created()),
        } for sample in samples]


@register
class Stored(ProjectSamplesReport):
    id = "storage_project_stored"
    title = _(u"Samples stored by project")
    description = _(u"The samples of a project that are in storage now, "
                    u"where, and since when")
    filters = (
        filters.Project("project", _(u"Project")),
        filters.SampleType("sampletype", _(u"Sample type")),
        filters.Container("container", _(u"Container")),
        filters.DateRange("stored", _(u"Date stored")),
    )
    columns = (
        ("project", _(u"Project")), ("sample", _(u"Sample")),
        ("sample_type", _(u"Sample type")), ("container", _(u"Container")),
        ("position", _(u"Position")), ("stored", _(u"Stored")),
    )

    def get_rows(self, values):
        titles = {}
        wanted = None
        if values.get("container"):
            container = api.get_object_by_uid(values["container"], None)
            wanted = set(container.get_samples_uids()) if container else set()
        rows = []
        samples = data.get_project_samples(
            values.get("project"), review_state="stored",
            sampletype=values.get("sampletype"))
        for sample in samples:
            if wanted is not None and api.get_uid(sample) not in wanted:
                continue
            stored = sample.getDateStored()
            if not data.date_in(stored, values.get("stored")):
                continue
            container, label = data.position_label(sample)
            rows.append({
                "project": self.project_of(sample, titles),
                "sample": api.get_id(sample),
                "sample_type": safe_unicode(sample.getSampleTypeTitle()),
                "container": container.get_full_title() if container
                else u"",
                "position": label,
                "stored": data.iso(stored),
            })
        return rows


@register
class Retrieved(ProjectSamplesReport):
    id = "storage_project_retrieved"
    title = _(u"Samples currently retrieved by project")
    description = _(u"The samples of a project that are out of storage, for "
                    u"whom, and when they are expected back")
    filters = (
        filters.Project("project", _(u"Project")),
        filters.SampleType("sampletype", _(u"Sample type")),
        filters.DateRange("retrieved", _(u"Date retrieved")),
    )
    columns = (
        ("project", _(u"Project")), ("sample", _(u"Sample")),
        ("sample_type", _(u"Sample type")), ("retrieved", _(u"Retrieved")),
        ("requester", _(u"Requested by")),
        ("requesting_project", _(u"Requesting project")),
        ("expected", _(u"Expected back")), ("request", _(u"Request")),
    )

    def get_rows(self, values):
        titles, rows = {}, []
        for line in data.sapi.get_out_of_storage():
            sample = data.sample_of(line)
            if sample is None:
                continue
            uid = data.sapi.get_sample_project_uid(sample)
            if not uid or (values.get("project") and
                           values["project"] != uid):
                continue
            if values.get("sampletype") and \
                    values["sampletype"] != data.sample_type_uid(sample):
                continue
            if not data.date_in(line.physical_action_at,
                                values.get("retrieved")):
                continue
            request = data.sapi.get_request(line)
            rows.append({
                "project": data.project_title(uid, titles),
                "sample": api.get_id(sample),
                "sample_type": safe_unicode(sample.getSampleTypeTitle()),
                "retrieved": data.iso(line.physical_action_at),
                "requester": line.requester or u"",
                "requesting_project": data.project_title(
                    line.requesting_project, titles),
                "expected": data.iso(line.expected_return_date),
                "request": api.get_id(request) if request else u"",
            })
        return sorted(rows, key=lambda row: (row["project"].lower(),
                                             row["retrieved"] or u"",
                                             row["sample"]))


@register
class Returned(ProjectSamplesReport):
    id = "storage_project_returned"
    title = _(u"Samples returned by project")
    description = _(u"The samples of a project that were retrieved and put "
                    u"back in storage")
    filters = (
        filters.Project("project", _(u"Project")),
        filters.SampleType("sampletype", _(u"Sample type")),
        filters.DateRange("returned", _(u"Date returned")),
    )
    columns = (
        ("project", _(u"Project")), ("sample", _(u"Sample")),
        ("sample_type", _(u"Sample type")), ("retrieved", _(u"Retrieved")),
        ("returned", _(u"Returned")), ("container", _(u"Returned to")),
        ("condition", _(u"Condition")),
    )

    def get_rows(self, values):
        titles, rows = {}, []
        for line in data.get_lines(data.TRANSACTION_RETURN, "completed"):
            sample = data.sample_of(line)
            if sample is None:
                continue
            uid = data.sapi.get_sample_project_uid(sample)
            if not uid or (values.get("project") and
                           values["project"] != uid):
                continue
            if values.get("sampletype") and \
                    values["sampletype"] != data.sample_type_uid(sample):
                continue
            if not data.date_in(line.physical_action_at,
                                values.get("returned")):
                continue
            retrieval = api.get_object_by_uid(
                line.related_transaction, None) \
                if line.related_transaction else None
            rows.append({
                "project": data.project_title(uid, titles),
                "sample": api.get_id(sample),
                "sample_type": safe_unicode(sample.getSampleTypeTitle()),
                "retrieved": data.iso(
                    retrieval.physical_action_at) if retrieval else None,
                "returned": data.iso(line.physical_action_at),
                "container": line.storage_location or u"",
                "condition": line.condition or u"",
            })
        return sorted(rows, key=lambda row: (row["project"].lower(),
                                             row["returned"] or u"",
                                             row["sample"]))


@register
class Disposed(ProjectSamplesReport):
    id = "storage_project_disposed"
    title = _(u"Samples disposed by project")
    description = _(u"The samples of a project that were disposed of, how, "
                    u"why and by whom")
    filters = (
        filters.Project("project", _(u"Project")),
        filters.Choice("method", _(u"Disposal method"),
                       options=tuple((m, m) for m in data.DISPOSAL_METHODS)),
        filters.DateRange("disposed", _(u"Date disposed")),
    )
    columns = (
        ("project", _(u"Project")), ("sample", _(u"Sample")),
        ("sample_type", _(u"Sample type")), ("disposed", _(u"Disposed")),
        ("method", _(u"Method")), ("reason", _(u"Reason")), ("by", _(u"By")),
    )

    def get_rows(self, values):
        titles, rows = {}, []
        samples = data.get_project_samples(
            values.get("project"), review_state="disposed")
        for sample in samples:
            disposal = data.sapi.get_disposal(sample)
            when = disposal.physical_action_at if disposal else None
            method = disposal.method if disposal else None
            if values.get("method") and values["method"] != method:
                continue
            if not data.date_in(when, values.get("disposed")):
                continue
            rows.append({
                "project": self.project_of(sample, titles),
                "sample": api.get_id(sample),
                "sample_type": safe_unicode(sample.getSampleTypeTitle()),
                "disposed": data.iso(when),
                "method": method or u"",
                "reason": (disposal.reason if disposal else u"") or u"",
                "by": (disposal.physical_action_by if disposal else u"")
                or u"",
            })
        return rows


@register
class Summary(StorageReport):
    id = "storage_project_summary"
    title = _(u"Project summary")
    description = _(u"For each project, the samples registered, stored now, "
                    u"currently retrieved, returned and disposed of")
    category = "project"
    filters = (
        filters.Project("project", _(u"Project")),
        filters.SampleType("sampletype", _(u"Sample type")),
    )
    columns = (
        ("project", _(u"Project")), ("registered", _(u"Registered")),
        ("stored", _(u"Stored")), ("retrieved", _(u"Currently retrieved")),
        ("returned", _(u"Returned")), ("disposed", _(u"Disposed")),
    )
    counted = ("registered", "stored", "retrieved", "returned", "disposed")

    def count_by_project(self, lines, values):
        """How many of the lines belong to each project (by the project of
        the sample, of the sample type asked for)"""
        counts = collections.Counter()
        for line in lines:
            sample = data.sample_of(line)
            if sample is None:
                continue
            uid = data.sapi.get_sample_project_uid(sample)
            if not uid:
                continue
            if values.get("sampletype") and \
                    values["sampletype"] != data.sample_type_uid(sample):
                continue
            counts[uid] += 1
        return counts

    def get_rows(self, values):
        retrieved = self.count_by_project(
            data.sapi.get_out_of_storage(), values)
        returned = self.count_by_project(
            data.get_lines(data.TRANSACTION_RETURN, "completed"), values)
        rows = []
        for project in data.get_projects():
            if values.get("project") and values["project"] != project["uid"]:
                continue
            counts = {}
            for key, state in (("registered", None), ("stored", "stored"),
                               ("disposed", "disposed")):
                counts[key] = len(data.get_project_samples(
                    project["uid"], review_state=state,
                    sampletype=values.get("sampletype")))
            row = {"project": project["title"],
                   "retrieved": retrieved.get(project["uid"], 0),
                   "returned": returned.get(project["uid"], 0)}
            row.update(counts)
            rows.append(row)
        return rows

    def footer(self, rows):
        span = 1
        line = [{"value": _(u"Total"), "colspan": span,
                 "class": "total_label"}]
        line.extend({"value": sum(row[key] for row in rows)}
                    for key in self.counted)
        return [line]
