# -*- coding: utf-8 -*-
"""The base of the storage reports: a report declares its filters and its
columns and says how to get its rows. This builds the form, reads the filters,
and makes the preview, the PDF (through the form that frames it) and the CSV
"""

import csv
import datetime
import os

from bika.lims.browser import BrowserView
from bika.lims.utils import t
from bika.reports import _
from bika.reports.browser.reports.storage import data
from bika.reports.browser.reports.storage import filters as filters_module
from plone.app.layout.globals.interfaces import IViewView
from Products.CMFPlone.utils import safe_unicode
from Products.Five.browser.pagetemplatefile import ViewPageTemplateFile
from six import BytesIO
from zope.i18n import translate
from zope.interface import implements

# the output of the other reports of this package
OUTPUT_TEMPLATE = os.path.join(
    os.path.dirname(os.path.abspath(__file__)), os.pardir, "templates",
    "report_out.pt")


class StorageReport(BrowserView):
    """A report of the Storage page

    id          the identifier of the report (starts with "storage_")
    title       what the page and the report are called
    description what the report is for, on the page
    category    "project", "storage" or "retrieval": its section of the page
    filters     the filters of its form, from `filters`
    columns     ((key, title), ...) of the table
    get_rows    the rows as dicts by column key, for the filter values
    """
    implements(IViewView)
    template = ViewPageTemplateFile(OUTPUT_TEMPLATE)

    id = None
    title = u""
    description = u""
    category = None
    filters = ()
    columns = ()

    def __init__(self, context, request, report=None):
        self.report = report
        BrowserView.__init__(self, context, request)

    # to be done by each report
    def get_rows(self, values):
        raise NotImplementedError

    # the form
    def form_html(self):
        """The controls of the form, without the form and its button"""
        controls = [flt.render(self) for flt in self.filters]
        controls.append(filters_module.output_format_html(self))
        return u"<fieldset>{}</fieldset>".format(u"\n".join(controls))

    # the filters
    def parse_filters(self):
        """Reads the filters of the request. Returns (values, parms): the
        value of each filter that was used, by name (and its label as
        `<name>_label`), and the rows for the parameters of the report, with
        the filters whose input was not valid
        """
        values, parms = {}, []
        for flt in self.filters:
            parsed = flt.parse(self.request)
            title = safe_unicode(translate(flt.title, context=self.request))
            if parsed.error:
                parms.append({
                    "title": title, "type": "text",
                    "value": safe_unicode(translate(
                        parsed.error, context=self.request))})
            if parsed.value is None:
                continue
            values[flt.name] = parsed.value
            values[flt.name + "_label"] = parsed.label
            if not parsed.error:
                parms.append({"title": title, "value": parsed.label,
                              "type": "text"})
        return values, parms

    # the output
    def column_titles(self):
        return [safe_unicode(translate(title, context=self.request))
                for key, title in self.columns]

    def cell(self, value):
        if value is None:
            return u""
        if isinstance(value, (datetime.date, datetime.datetime)):
            return value.isoformat()[:16].replace("T", " ")
        return safe_unicode(value)

    def csv_data(self, rows):
        """The rows as CSV text, with the titles of the columns first"""
        output = BytesIO()
        writer = csv.writer(output)
        encode = lambda value: safe_unicode(value).encode("utf-8")  # noqa
        writer.writerow([encode(title) for title in self.column_titles()])
        for row in rows:
            writer.writerow([encode(self.cell(row.get(key)))
                             for key, title in self.columns])
        return output.getvalue()

    def write_csv(self, rows):
        report_data = self.csv_data(rows)
        stamp = datetime.datetime.now().strftime("%Y-%m-%d %H%M")
        setheader = self.request.RESPONSE.setHeader
        setheader("Content-Type", "text/csv")
        setheader("Content-Disposition",
                  "attachment;filename=\"{} {}.csv\"".format(
                      self.id, stamp))
        self.request.RESPONSE.write(report_data)

    def footer(self, rows):
        """The lines under the table: the number of rows by default"""
        span = max(len(self.columns) - 1, 1)
        return [[{"value": _(u"Total"), "colspan": span,
                  "class": "total_label"},
                 {"value": len(rows)}]]

    def __call__(self):
        values, parms = self.parse_filters()
        rows = self.get_rows(values)
        if self.request.get("output_format", "") == "CSV":
            self.write_csv(rows)
            return None
        datalines = [[{"value": self.cell(row.get(key))}
                      for key, title in self.columns] for row in rows]
        # a blank line, as the PDF of the other reports needs
        if self.request.get("output_format", "") == "PDF" and datalines:
            datalines.append([{"value": "."}] * len(self.columns))
        self.report_content = {
            "headings": {"header": self.title,
                         "subheader": self.description},
            "parms": parms,
            "formats": {"columns": len(self.columns),
                        "col_heads": self.column_titles(), "class": ""},
            "datalines": datalines,
            "footings": self.footer(rows),
        }
        return {"report_title": t(self.title),
                "report_data": self.template()}
