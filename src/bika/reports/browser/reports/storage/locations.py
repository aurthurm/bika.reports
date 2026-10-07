# -*- coding: utf-8 -*-
"""The storage reports (issue #76 §18): where the samples are, how full the
containers are, and how long the samples are kept
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


def where(sample):
    """The container of a stored sample and its position, as one text"""
    container, label = data.position_label(sample)
    if container is None:
        return u""
    title = container.get_full_title()
    return u"{} · {}".format(title, label) if label else title


class CountedBy(StorageReport):
    """A report that counts its rows by the value of one column"""
    category = "storage"
    count_column = "container"

    def footer(self, rows):
        span = max(len(self.columns) - 1, 1)
        counts = collections.OrderedDict()
        for row in rows:
            key = row[self.count_column]
            counts[key] = counts.get(key, 0) + 1
        lines = [[{"value": key, "colspan": span}, {"value": count}]
                 for key, count in counts.items()]
        lines.extend(super(CountedBy, self).footer(rows))
        return lines


@register
class ByLocation(CountedBy):
    id = "storage_by_location"
    title = _(u"Samples by storage location")
    description = _(u"The samples in storage, by container and position")
    filters = (
        filters.Container("container", _(u"Container")),
        filters.Project("project", _(u"Project")),
        filters.SampleType("sampletype", _(u"Sample type")),
        filters.DateRange("stored", _(u"Date stored")),
    )
    columns = (
        ("container", _(u"Container")), ("position", _(u"Position")),
        ("sample", _(u"Sample")), ("sample_type", _(u"Sample type")),
        ("project", _(u"Project")), ("stored", _(u"Stored")),
    )

    def get_rows(self, values):
        titles, found = {}, []
        samples = data.get_stored_samples(
            values.get("project"), values.get("sampletype"),
            values.get("container"))
        for sample in samples:
            stored = sample.getDateStored()
            if not data.date_in(stored, values.get("stored")):
                continue
            container, label = data.position_label(sample)
            title = container.get_full_title() if container else u""
            found.append((title, data.position_key(sample), {
                "container": title,
                "position": label,
                "sample": api.get_id(sample),
                "sample_type": safe_unicode(sample.getSampleTypeTitle()),
                "project": data.project_title(
                    data.sapi.get_sample_project_uid(sample), titles),
                "stored": data.iso(stored),
            }))
        return [row for title, position, row in sorted(
            found, key=lambda item: item[:2])]


@register
class Utilisation(StorageReport):
    id = "storage_utilisation"
    title = _(u"Container utilisation")
    description = _(u"How full each container is: its capacity, the places "
                    u"used, the ones held for retrieved samples and the free "
                    u"ones")
    category = "storage"
    filters = (
        filters.Container("container", _(u"Container")),
        filters.Choice("fill", _(u"Filling"), options=(
            ("full", _(u"Full")), ("free", _(u"With free space")))),
    )
    columns = (
        ("container", _(u"Container")), ("capacity", _(u"Capacity")),
        ("used", _(u"Used")), ("held", _(u"Held for retrieved samples")),
        ("free", _(u"Free")), ("percent", _(u"Used %")),
    )

    def get_rows(self, values):
        rows = []
        for container in data.get_container_objects(values.get("container")):
            capacity = container.get_samples_capacity()
            if not container.is_managed() and \
                    container.getPhysicalCapacity() is None:
                capacity = None
            used = container.get_samples_utilization()
            held = len(data.sapi.get_held(container))
            free = None if capacity is None else max(
                capacity - used - held, 0)
            if values.get("fill") == "full" and not (
                    free is not None and free == 0):
                continue
            if values.get("fill") == "free" and not (
                    free is None or free > 0):
                continue
            rows.append({
                "container": container.get_full_title(),
                "capacity": capacity if capacity is not None else u"",
                "used": used, "held": held,
                "free": free if free is not None else u"",
                "percent": u"{:.1f}%".format(100.0 * used / capacity)
                if capacity else u"",
            })
        return rows


@register
class StoredVsRetrieved(StorageReport):
    id = "storage_stored_vs_retrieved"
    title = _(u"Stored vs retrieved samples")
    description = _(u"By sample type, how many samples are in storage and "
                    u"how many are out of it")
    category = "storage"
    filters = (
        filters.Project("project", _(u"Project")),
        filters.SampleType("sampletype", _(u"Sample type")),
        filters.Container("container", _(u"Container")),
    )
    columns = (
        ("sample_type", _(u"Sample type")), ("stored", _(u"Stored")),
        ("retrieved", _(u"Retrieved")), ("total", _(u"Total")),
    )
    counted = ("stored", "retrieved", "total")

    def get_rows(self, values):
        counts = collections.OrderedDict()

        def add(sample, key):
            title = safe_unicode(sample.getSampleTypeTitle())
            row = counts.setdefault(title, {
                "sample_type": title, "stored": 0, "retrieved": 0,
                "total": 0})
            row[key] += 1
            row["total"] += 1

        for sample in data.get_stored_samples(
                values.get("project"), values.get("sampletype"),
                values.get("container")):
            add(sample, "stored")
        for line in data.sapi.get_out_of_storage():
            sample = data.sample_of(line)
            if sample is None:
                continue
            if values.get("project") and values["project"] != \
                    data.sapi.get_sample_project_uid(sample):
                continue
            if values.get("sampletype") and \
                    values["sampletype"] != data.sample_type_uid(sample):
                continue
            if values.get("container") and \
                    values["container"] != line.container_uid:
                continue
            add(sample, "retrieved")
        return sorted(counts.values(), key=lambda row: row["sample_type"])

    def footer(self, rows):
        line = [{"value": _(u"Total"), "class": "total_label"}]
        line.extend({"value": sum(row[key] for row in rows)}
                    for key in self.counted)
        return [line]


class RetentionReport(StorageReport):
    """The stored samples whose retention is judged against today"""
    category = "storage"

    def days_between(self, day, other):
        return (day - other).days

    def stored(self, values):
        from senaite.storage import api as storage_api
        for sample in data.get_stored_samples(
                values.get("project"), values.get("sampletype"),
                values.get("container")):
            expiry = sample.getStorageExpiryDate()
            if not expiry:
                continue
            yield sample, data.to_date(expiry), \
                bool(storage_api.is_retention_expired(sample))

    def row(self, sample, expiry, titles, **extra):
        container, label = data.position_label(sample)
        row = {
            "sample": api.get_id(sample),
            "project": data.project_title(
                data.sapi.get_sample_project_uid(sample), titles),
            "container": container.get_full_title() if container else u"",
            "expiry": expiry.isoformat(),
        }
        row.update(extra)
        return row


@register
class Approaching(RetentionReport):
    id = "storage_retention_approaching"
    title = _(u"Samples approaching retention expiry")
    description = _(u"The stored samples whose retention ends within a "
                    u"number of days")

    def __init__(self, context, request, report=None):
        super(Approaching, self).__init__(context, request, report)
        self.filters = (
            filters.Days("days", _(u"Expires within (days)"),
                         default=self.warning_days()),
            filters.Project("project", _(u"Project")),
            filters.Container("container", _(u"Container")),
        )

    columns = (
        ("sample", _(u"Sample")), ("project", _(u"Project")),
        ("container", _(u"Container")), ("expiry", _(u"Retain until")),
        ("days_left", _(u"Days left")),
    )

    @staticmethod
    def warning_days():
        from senaite.storage import api as storage_api
        return storage_api.get_warning_days_before_expiration()

    def get_rows(self, values):
        days = values.get("days", self.warning_days())
        today = date.today()
        titles, rows = {}, []
        for sample, expiry, expired in self.stored(values):
            left = self.days_between(expiry, today)
            if expired or left > days:
                continue
            rows.append(self.row(sample, expiry, titles, days_left=left))
        return sorted(rows, key=lambda row: (row["expiry"], row["sample"]))


@register
class Past(RetentionReport):
    id = "storage_retention_past"
    title = _(u"Samples past retention")
    description = _(u"The stored samples whose retention has ended")
    filters = (
        filters.Project("project", _(u"Project")),
        filters.Container("container", _(u"Container")),
        filters.SampleType("sampletype", _(u"Sample type")),
    )
    columns = (
        ("sample", _(u"Sample")), ("project", _(u"Project")),
        ("container", _(u"Container")), ("expiry", _(u"Retain until")),
        ("days_past", _(u"Days past")),
    )

    def get_rows(self, values):
        today = date.today()
        titles, rows = {}, []
        for sample, expiry, expired in self.stored(values):
            if not expired:
                continue
            rows.append(self.row(sample, expiry, titles,
                                 days_past=self.days_between(today, expiry)))
        return sorted(rows, key=lambda row: (row["expiry"], row["sample"]))


@register
class Custody(StorageReport):
    id = "storage_custody"
    title = _(u"Current custody status")
    description = _(u"Where each sample that has been in storage is now: "
                    u"stored, retrieved or disposed of")
    category = "storage"
    filters = (
        filters.Choice("status", _(u"Status"), options=(
            ("stored", _(u"Stored")), ("retrieved", _(u"Retrieved")),
            ("disposed", _(u"Disposed")))),
        filters.Project("project", _(u"Project")),
        filters.SampleType("sampletype", _(u"Sample type")),
        filters.Container("container", _(u"Container")),
    )
    columns = (
        ("sample", _(u"Sample")), ("sample_type", _(u"Sample type")),
        ("project", _(u"Project")), ("status", _(u"Status")),
        ("where", _(u"Where")), ("since", _(u"Since")),
    )

    def wanted(self, values, sample):
        if values.get("project") and values["project"] != \
                data.sapi.get_sample_project_uid(sample):
            return False
        if values.get("sampletype") and \
                values["sampletype"] != data.sample_type_uid(sample):
            return False
        return True

    def get_rows(self, values):
        titles, rows = {}, []
        status = values.get("status")

        def add(sample, label, place, since, container_uid):
            if values.get("container") and \
                    values["container"] != container_uid:
                return
            rows.append({
                "sample": api.get_id(sample),
                "sample_type": safe_unicode(sample.getSampleTypeTitle()),
                "project": data.project_title(
                    data.sapi.get_sample_project_uid(sample), titles),
                "status": label, "where": place, "since": since,
            })

        if status in (None, "stored"):
            for sample in data.get_stored_samples(
                    values.get("project"), values.get("sampletype")):
                container = data.sapi.get_container(sample)
                add(sample, u"Stored", where(sample),
                    data.iso(sample.getDateStored()),
                    api.get_uid(container) if container else None)
        if status in (None, "retrieved"):
            for line in data.sapi.get_out_of_storage():
                sample = data.sample_of(line)
                if sample is None or not self.wanted(values, sample):
                    continue
                add(sample, u"Retrieved", line.storage_location or u"",
                    data.iso(line.physical_action_at), line.container_uid)
        if status in (None, "disposed"):
            for sample in data.get_stored_or_disposed("disposed", values):
                disposal = data.sapi.get_disposal(sample)
                if disposal is None:
                    continue
                add(sample, u"Disposed", disposal.storage_location or u"",
                    data.iso(disposal.physical_action_at),
                    disposal.container_uid)
        return sorted(rows, key=lambda row: (row["status"], row["sample"]))
