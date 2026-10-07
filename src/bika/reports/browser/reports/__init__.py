# -*- coding: utf-8 -*-
#
# This file is part of SENAITE.CORE.
#
# SENAITE.CORE is free software: you can redistribute it and/or modify it under
# the terms of the GNU General Public License as published by the Free Software
# Foundation, version 2.
#
# This program is distributed in the hope that it will be useful, but WITHOUT
# ANY WARRANTY; without even the implied warranty of MERCHANTABILITY or FITNESS
# FOR A PARTICULAR PURPOSE. See the GNU General Public License for more
# details.
#
# You should have received a copy of the GNU General Public License along with
# this program; if not, write to the Free Software Foundation, Inc., 51
# Franklin Street, Fifth Floor, Boston, MA 02110-1301 USA.
#
# Copyright 2018-2021 by it's authors.
# Some rights reserved, see README and LICENSE.

import bs4
from AccessControl import Unauthorized
import collections
import importlib
import os
import urllib

from DateTime import DateTime
from Products.CMFCore.utils import getToolByName
from Products.Five.browser.pagetemplatefile import ViewPageTemplateFile
from datetime import datetime
from plone.app.layout.globals.interfaces import IViewView
from zope.component import getAdapters
from zope.interface import implements

from bika.lims import api
from bika.lims.browser import BrowserView
from bika.lims.utils import getUsers
from bika.lims.utils import logged_in_client
from bika.lims.utils import createPdf

from bika.reports import _
from bika.reports.browser.reports.selection_macros import SelectionMacrosView
from bika.reports.browser.reports.storage import data as storage_data
from bika.reports.browser.reports.storage import registry as storage_registry
from bika.reports.interfaces import IAdministrationReport
from bika.reports.interfaces import IProductivityReport
from senaite.app.listing import ListingView
from senaite.core.catalog import REPORT_CATALOG


class ProductivityView(BrowserView):
    """Productivity View form"""

    implements(IViewView)
    template = ViewPageTemplateFile("templates/productivity.pt")

    def __init__(self, context, request):
        BrowserView.__init__(self, context, request)
        self.context = context
        self.request = request

    def __call__(self):
        self.selection_macros = SelectionMacrosView(self.context, self.request)
        self.icon = self.portal_url + "/++resource++bika.lims.images/report_big.png"
        self.getAnalysts = getUsers(self.context, ["Manager", "LabManager", "Analyst"])
        self.last_month = DateTime() - 30
        self.last_month = self.last_month.strftime("%Y-%m-%d")
        self.today = DateTime().strftime("%Y-%m-%d")

        self.additional_reports = []
        adapters = getAdapters((self.context,), IProductivityReport)
        for name, adapter in adapters:
            report_dict = adapter(self.context, self.request)
            report_dict["id"] = name
            self.additional_reports.append(report_dict)

        return self.template()


class AdministrationView(BrowserView):
    """Administration View form"""

    implements(IViewView)
    template = ViewPageTemplateFile("templates/administration.pt")

    def __init__(self, context, request):
        BrowserView.__init__(self, context, request)
        self.context = context
        self.request = request

    def __call__(self):
        self.selection_macros = SelectionMacrosView(self.context, self.request)
        self.icon = self.portal_url + "/++resource++bika.lims.images/report_big.png"

        self.additional_reports = []
        adapters = getAdapters((self.context,), IAdministrationReport)
        for name, adapter in adapters:
            report_dict = adapter(self.context, self.request)
            report_dict["id"] = name
            self.additional_reports.append(report_dict)

        return self.template()


class StorageView(BrowserView):
    """The Storage tab: the storage reports, in their three sections"""

    implements(IViewView)
    template = ViewPageTemplateFile("templates/storage.pt")

    def __init__(self, context, request):
        BrowserView.__init__(self, context, request)
        self.context = context
        self.request = request

    def __call__(self):
        if not storage_data.can_use_storage(self.context):
            raise Unauthorized("Storage reports")
        self.selection_macros = SelectionMacrosView(self.context, self.request)
        self.icon = self.portal_url + "/++resource++bika.lims.images/report_big.png"
        return self.template()

    def has_storage(self):
        return storage_data.HAS_STORAGE

    def get_sections(self):
        """The sections of the page, each with its reports and their forms"""
        sections = []
        for category, title in storage_registry.CATEGORIES:
            reports = []
            for report_class in storage_registry.get_reports(category):
                report = report_class(self.context, self.request)
                reports.append({
                    "id": report_class.id,
                    "title": report_class.title,
                    "description": report_class.description,
                    "form": report.form_html(),
                })
            sections.append({"id": category, "title": title,
                             "reports": reports})
        return sections


class ReportHistoryView(ListingView):
    """Report history form"""

    def __init__(self, context, request):
        super(ReportHistoryView, self).__init__(context, request)

        self.catalog = REPORT_CATALOG
        self.contentFilter = {"portal_type": "Report", "sort_order": "reverse"}
        self.show_select_row = True
        self.show_select_column = True
        self.pagesize = 50

        self.icon = self.portal_url + "/++resource++bika.lims.images/report_big.png"
        self.title = self.context.translate(_("Reports"))
        self.description = ""

        # this is set up in call where member is authenticated
        self.columns = collections.OrderedDict((
            ("Title", {
                "title": _("Title"),
                "attr": "Title",
                "index": "title"}),
            ("file_size", {
                "title": _("Size"),
                "attr": "getFileSize",
                "sortable": False}),
            ("created", {
                "title": _("Created"),
                "attr": "created",
                "index": "created"}),
            ("creator", {
                "title": _("By"),
                "attr": "getCreatorFullName",
                "index": "Creator"}),
        ))

        self.review_states = [
            {
                "id": "default",
                "title": _("Active"),
                "contentFilter": {"is_active": True},
                "columns": self.columns.keys(),
            }, {
                "id": "inactive",
                "title": _("Inactive"),
                "contentFilter": {"is_active": False},
                "columns": self.columns.keys(),
            }, {
                "id": "all",
                "title": _("All"),
                "contentFilter": {},
                "columns": self.columns.keys(),
            },
        ]

        this_client = logged_in_client(self.context)
        if this_client:
            self.contentFilter["getClientUID"] = this_client.UID()
        else:
            pass
            # client_col = [("Client", {"title": _("Client"),
            #                           "attr": "getClientURL"})]
            # self.columns.update(client_col)
            # for i in range(len(self.review_states)):
            #     self.review_states[i]["columns"].append("Client")


    def lookupMime(self, name):
        mimetool = getToolByName(self, "mimetypes_registry")
        mimetypes = mimetool.lookup(name)
        if len(mimetypes):
            return mimetypes[0].name()
        else:
            return name

    def folderitem(self, obj, item, index):
        # https://github.com/collective/uwosh.pfg.d2c/issues/20
        # https://github.com/collective/uwosh.pfg.d2c/pull/21
        item["replace"]["Title"] = "<a href='%s/ReportFile'>%s</a>" % (
            item["url"],
            item["Title"],
        )
        item["replace"]["created"] = self.ulocalized_time(item["created"])
        return item


class SubmitForm(BrowserView):
    """Redirect to specific report"""

    implements(IViewView)
    frame_template = ViewPageTemplateFile("templates/report_frame.pt")
    # default and errors use the form the report was asked from
    template = ViewPageTemplateFile("templates/productivity.pt")
    administration_template = ViewPageTemplateFile(
        "templates/administration.pt")

    def __init__(self, context, request):
        BrowserView.__init__(self, context, request)
        self.context = context
        self.request = request

    def is_administration(self):
        """Whether the report was asked from the administration form"""
        return self.request.get("report_id", "").startswith("administration")

    def prepare_form(self):
        """What the form that is shown again needs, as the view of that form
        sets it up: the productivity form (the default) or the administration
        one
        """
        if self.is_storage():
            # the Storage page builds its own forms
            return
        self.selection_macros = SelectionMacrosView(self.context, self.request)
        self.icon = self.portal_url + "/++resource++bika.lims.images/report_big.png"
        interface = IProductivityReport
        if self.is_administration():
            interface = IAdministrationReport
        else:
            self.getAnalysts = getUsers(
                self.context, ["Manager", "LabManager", "Analyst"])
            self.last_month = (DateTime() - 30).strftime("%Y-%m-%d")
            self.today = DateTime().strftime("%Y-%m-%d")
        self.additional_reports = []
        for name, adapter in getAdapters((self.context,), interface):
            report_dict = adapter(self.context, self.request)
            report_dict["id"] = name
            self.additional_reports.append(report_dict)

    def is_storage(self):
        return self.request.get("report_id", "").startswith("storage_")

    def render_form(self):
        """The form the report was asked from, with its message"""
        if self.is_storage():
            return StorageView(self.context, self.request)()
        if self.is_administration():
            return self.administration_template()
        return self.template()

    def __call__(self):
        """Create and render selected report"""

        if "Cancel" in self.request.form:
            came_from = self.request.form.get("came_from", self.context.absolute_url())
            # Do your form processing
            self.request.response.redirect(came_from)
            return

        self.report_id = self.request.get("report_id", "")
        if self.is_storage() and not storage_data.can_use_storage(
                self.context):
            raise Unauthorized("Storage reports")
        # if there's an error, we show the form again: it needs these
        self.prepare_form()
        if not self.report_id:
            message = _("No report specified in request")
            self.logger.error(message)
            self.context.plone_utils.addPortalMessage(message, "error")
            return self.render_form()

        self.date = DateTime()
        username = self.context.portal_membership.getAuthenticatedMember().getUserName()
        self.reporter = self.user_fullname(username)
        self.reporter_email = self.user_email(username)

        # signature image
        self.reporter_signature = ""
        c = [
            x
            for x in self.senaite_catalog_setup(portal_type="LabContact")
            if x.getObject().getUsername() == username
        ]
        if c:
            sf = c[0].getObject().getSignature()
            if sf:
                self.reporter_signature = sf.absolute_url() + "/Signature"

        lab = api.get_senaite_setup().laboratory
        self.laboratory = lab
        self.lab_title = lab.getName()
        self.lab_address = lab.getPrintAddress()
        self.lab_email = lab.getEmailAddress()
        self.lab_url = lab.getLabURL()

        client = logged_in_client(self.context)
        if client:
            clientuid = client.UID()
            self.client_title = client.Title()
            self.client_address = client.getPrintAddress()
        else:
            clientuid = None
            self.client_title = None
            self.client_address = None

        # Render form output

        # the report can add file names to this list; they will be deleted
        # once the PDF has been generated.  temporary plot image files, etc.
        self.request["to_remove"] = []

        if self.is_storage():
            # the storage reports are found in their registry, never by a
            # module name taken from the request
            Report = storage_registry.get_report_class(self.report_id)
            if Report is None:
                message = "Report %s not found" % self.report_id
                self.logger.error(message)
                self.context.plone_utils.addPortalMessage(message, "error")
                return self.render_form()
        else:
            if "report_module" in self.request:
                module = self.request["report_module"]
            else:
                module = "bika.reports.browser.reports.%s" % self.report_id
            try:
                Report = getattr(importlib.import_module(module), "Report")
                # required during error redirect: the report must have a copy
                # of additional_reports, because it is used as a surrogate
                # view.
                Report.additional_reports = self.additional_reports
            except (ImportError, AttributeError):
                message = ("Report %s.Report not found (shouldn't happen)"
                           % module)
                self.logger.error(message)
                self.context.plone_utils.addPortalMessage(message, "error")
                return self.render_form()

        # Report must return dict with:
        # - report_title - title string for pdf/history listing
        # - report_data - rendered report
        output = Report(self.context, self.request)()

        # if CSV output is chosen, report returns None
        if not output:
            return

        if type(output) in (str, unicode, bytes):
            # remove temporary files
            for f in self.request["to_remove"]:
                os.remove(f)
            return output

        # The report output gets pulled through report_frame.pt
        self.reportout = output["report_data"]
        self.report_parms = ""
        self.plot_data = ""
        if output.get("report_parms"):
            self.report_parms = urllib.urlencode(output["report_parms"])
            self.report_parms += "&output_format=PDF"
            self.plot_data = output["plot_data"]
        framed_output = self.frame_template()

        self.logger.info("SubmitForm: Create framed_output")
        # self.logger.info("SubmitForm: report_parms: {}".format(self.report_parms))
        # self.logger.info("SubmitForm: framed_output: {}".format(framed_output))

        # NB: The output_format can be hidden on the form with no value!
        if len(self.request.get("output_format", "")) == 0:
            self.logger.info("SubmitForm: exit with framed_output")
            return framed_output

        # pdf = createPdf(framed_output)
        parser = bs4.BeautifulSoup(framed_output, "html.parser")
        for el in parser.find_all("form"):
            el.decompose()
        for el in parser.find_all("script", class_="svg-plot"):
            el.decompose()
        pdf = createPdf(parser.prettify())

        # remove temporary files
        for f in self.request["to_remove"]:
            os.remove(f)

        if not pdf:
            return

        # Create new report object
        title = output["report_title"]
        data = {"title": title, "Client": clientuid, "ReportFile": pdf}
        api.create(self.context, "Report", **data)

        now = datetime.now().strftime("%y%m%d%H%M%S")
        fn = "{}-{}.pdf".format(now, title)

        setheader = self.request.response.setHeader
        setheader("Content-Type", "application/pdf")
        setheader("Content-Disposition", 'attachment; filename="%s"' % fn)
        setheader("Content-Length", len(pdf))
        setheader("Cache-Control", "no-store")
        setheader("Pragma", "no-cache")
        self.logger.info("Add PDF to response")
        self.request.response.write(pdf)


# the storage reports register themselves
from bika.reports.browser.reports.storage import locations  # noqa: E402,F401
from bika.reports.browser.reports.storage import projects  # noqa: E402,F401
from bika.reports.browser.reports.storage import retrievals  # noqa: E402,F401
