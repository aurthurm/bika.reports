# -*- coding: utf-8 -*-
"""The filters of the storage reports: each one makes the control of the form,
and reads and checks its value from the request. A value that is not valid is
reported in the parameters of the report and is not used: it never raises
"""

from datetime import datetime
from xml.sax.saxutils import escape
from xml.sax.saxutils import quoteattr

from bika.reports import _
from bika.reports.browser.reports.storage import data
from Products.CMFPlone.utils import safe_unicode
from zope.i18n import translate

OUTPUT_FORMATS = (
    ("", _(u"Preview")),
    ("PDF", _(u"PDF")),
    ("CSV", _(u"CSV")),
)


class Parsed(object):
    """What a filter read from the request: its `value` (None when the filter
    was not used), the `label` that is shown in the parameters of the report
    and an `error` message when the input was not valid
    """

    def __init__(self, value=None, label=u"", error=None):
        self.value = value
        self.label = label
        self.error = error


def _text(value):
    return safe_unicode(value or u"").strip()


def _options_html(options, selected, blank=None, request=None):
    html = []
    if blank is not None:
        html.append(u"<option value=\"\">{}</option>".format(
            escape(safe_unicode(translate(blank, context=request)))))
    for value, label in options:
        html.append(u"<option value={}{}>{}</option>".format(
            quoteattr(safe_unicode(value)),
            u" selected=\"selected\"" if safe_unicode(value) == selected
            else u"",
            escape(safe_unicode(translate(label, context=request)))))
    return u"\n".join(html)


class Filter(object):
    """One control of the form of a report"""

    def __init__(self, name, title, **options):
        self.name = name
        self.title = title
        self.options = options

    def label(self, report):
        return safe_unicode(translate(self.title, context=report.request))

    def field(self, report, control):
        return (u"<div class=\"field\"><label for=\"{name}\">{title}</label> "
                u"{control}</div>").format(
                    name=self.name, title=escape(self.label(report)),
                    control=control)

    def render(self, report):
        raise NotImplementedError

    def parse(self, request):
        raise NotImplementedError


class DateRange(Filter):
    """From and to dates (both optional), as `name_fromdate` and
    `name_todate`. The value is (from, to), each a date or None
    """

    def render(self, report):
        controls = (
            u"<input type=\"date\" id=\"{n}_fromdate\" name=\"{n}_fromdate\"/>"
            u" &ndash; "
            u"<input type=\"date\" id=\"{n}_todate\" name=\"{n}_todate\"/>"
        ).format(n=self.name)
        return self.field(report, controls)

    def parse(self, request):
        dates = []
        for suffix in ("fromdate", "todate"):
            raw = _text(request.form.get("{}_{}".format(self.name, suffix)))
            if not raw:
                dates.append(None)
                continue
            try:
                dates.append(datetime.strptime(raw, "%Y-%m-%d").date())
            except ValueError:
                return Parsed(error=_(
                    u"'${value}' is not a valid date",
                    mapping={"value": raw}))
        if not any(dates):
            return Parsed()
        start, end = dates
        if start and end and start > end:
            return Parsed(error=_(u"The first date is after the second"))
        label = u"{} - {}".format(
            start.isoformat() if start else u"...",
            end.isoformat() if end else u"...")
        return Parsed(tuple(dates), label)


class _Select(Filter):
    """A choice among the items of a catalog or a list"""
    blank = _(u"All")

    def items(self):
        return []

    def render(self, report):
        selected = _text(report.request.form.get(self.name))
        options = [(item["uid"], safe_unicode(item["title"]))
                   for item in self.items()]
        control = u"<select id=\"{n}\" name=\"{n}\">{o}</select>".format(
            n=self.name, o=_options_html(
                options, selected, self.blank, report.request))
        return self.field(report, control)

    def parse(self, request):
        uid = _text(request.form.get(self.name))
        if not uid:
            return Parsed()
        for item in self.items():
            if item["uid"] == uid:
                return Parsed(uid, safe_unicode(item["title"]))
        return Parsed(error=_(u"The selection is not known"))


class Project(_Select):
    blank = _(u"All projects")

    def items(self):
        return data.get_projects()


class SampleType(_Select):
    blank = _(u"All sample types")

    def items(self):
        return data.get_sample_types()


class Container(_Select):
    blank = _(u"All containers")

    def items(self):
        return data.get_containers()


class _Known(_Select):
    """A choice among what exists, and any other value is used as typed: a
    user or a reason that was never recorded matches nothing, it does not
    show everything
    """

    def parse(self, request):
        value = _text(request.form.get(self.name))
        return Parsed(value, value) if value else Parsed()


class Requester(_Known):
    blank = _(u"All requesters")

    def items(self):
        return data.get_requesters()


class Reason(_Known):
    blank = _(u"All reasons")

    def items(self):
        return data.get_reasons()


class Choice(_Select):
    """One of a fixed list of `options`: ((value, label), ...)"""

    def items(self):
        return [{"uid": value, "title": label}
                for value, label in self.options["options"]]

    def render(self, report):
        selected = _text(report.request.form.get(self.name))
        default = self.options.get("default")
        if not selected and default is not None:
            selected = safe_unicode(default)
        blank = None if default is not None else self.blank
        control = u"<select id=\"{n}\" name=\"{n}\">{o}</select>".format(
            n=self.name, o=_options_html(
                self.options["options"], selected, blank, report.request))
        return self.field(report, control)

    def parse(self, request):
        raw = _text(request.form.get(self.name))
        default = self.options.get("default")
        if not raw and default is not None:
            raw = safe_unicode(default)
        if not raw:
            return Parsed()
        for value, label in self.options["options"]:
            if safe_unicode(value) == raw:
                return Parsed(value, safe_unicode(
                    translate(label, context=request)))
        return Parsed(error=_(u"The selection is not known"))


class Days(Filter):
    """A number of days, zero or more; `default` when it is empty"""

    def render(self, report):
        default = self.options.get("default")
        value = _text(report.request.form.get(self.name)) or (
            u"{}".format(default) if default is not None else u"")
        control = (u"<input type=\"number\" min=\"0\" id=\"{n}\" name=\"{n}\" "
                   u"value={v}/>").format(n=self.name, v=quoteattr(value))
        return self.field(report, control)

    def parse(self, request):
        raw = _text(request.form.get(self.name))
        default = self.options.get("default")
        if not raw:
            if default is None:
                return Parsed()
            return Parsed(default, u"{}".format(default))
        try:
            days = int(raw)
        except ValueError:
            days = -1
        if days < 0:
            error = _(u"'${value}' is not a number of days",
                      mapping={"value": raw})
            if default is None:
                return Parsed(error=error)
            return Parsed(default, u"{}".format(default), error=error)
        return Parsed(days, u"{}".format(days))


def output_format_html(report):
    """The control that chooses what the report is made as"""
    selected = _text(report.request.form.get("output_format"))
    return (u"<div class=\"field\"><label for=\"output_format\">{}</label> "
            u"<select id=\"output_format\" name=\"output_format\">{}"
            u"</select></div>").format(
                escape(safe_unicode(translate(
                    _(u"Output format"), context=report.request))),
                _options_html(OUTPUT_FORMATS, selected,
                              request=report.request))
