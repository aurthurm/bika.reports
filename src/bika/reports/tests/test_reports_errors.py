# -*- coding: utf-8 -*-
"""The report forms must not break, whatever the report asked for"""

import glob
import importlib
import os
import unittest

from bika.reports.interfaces import IBikaReportsLayer
from bika.reports.tests.base import ReportsTestCase
from zope.interface import alsoProvides

REPORTS_DIR = os.path.join(
    os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
    "browser", "reports")


def report_modules():
    names = sorted(os.path.basename(path)[:-3]
                   for path in glob.glob(os.path.join(REPORTS_DIR, "*.py")))
    return [name for name in names
            if name.startswith(("administration_", "productivity_"))]


class TestReportModules(unittest.TestCase):

    def test_there_are_reports(self):
        self.assertTrue(report_modules())

    def test_every_report_can_be_imported_and_has_a_report(self):
        # a report whose module cannot be imported shows the user an error
        # page in place of the report
        failures = []
        for name in report_modules():
            module = "bika.reports.browser.reports.{}".format(name)
            try:
                found = importlib.import_module(module)
            except Exception as error:
                failures.append((name, repr(error)))
                continue
            if not hasattr(found, "Report"):
                failures.append((name, "no Report"))
        self.assertEqual(failures, [])


class TestSubmitForm(ReportsTestCase):

    def setUp(self):
        super(TestSubmitForm, self).setUp()
        alsoProvides(self.request, IBikaReportsLayer)
        # created when the add-on is installed
        self.folder = self.portal.reports

    def view(self, **form):
        self.request.form.clear()
        self.request.form.update(form)
        return self.folder.restrictedTraverse("createreport")

    def test_no_report_shows_the_form_again(self):
        html = self.view()()
        self.assertIn("<form", html)

    def test_an_unknown_report_shows_the_form_again(self):
        html = self.view(report_id="not_a_report")()
        self.assertIn("<form", html)

    def test_an_administration_report_that_fails_shows_the_form_again(self):
        # whichever page the report was asked from, the error is shown and
        # not a traceback about the missing parts of the page
        html = self.view(report_id="administration_not_a_report")()
        self.assertIn("<form", html)


class TestAdministrationReports(ReportsTestCase):

    def setUp(self):
        super(TestAdministrationReports, self).setUp()
        alsoProvides(self.request, IBikaReportsLayer)
        self.folder = self.portal.reports

    def run_report(self, report_id, **form):
        self.request.form.clear()
        self.request.form.update(form, report_id=report_id)
        return self.folder.restrictedTraverse("createreport")()

    def test_the_form_of_the_administration_reports_opens(self):
        html = self.folder.restrictedTraverse("administration")()
        self.assertIn("administration_allclients", html)

    def test_the_reports_that_used_bika_extras_run(self):
        # they imported their message factory from a package that is not
        # installed with this one
        for report_id, heading in (
                ("administration_allclients", "All Clients"),
                ("administration_clientcontacts", "Client Contacts"),
                ("administration_clientsamplepoints",
                 "Client Sample Points")):
            output = self.run_report(report_id)
            self.assertIn(heading, output, report_id)
            self.assertNotIn("Traceback", output, report_id)

    def test_the_all_clients_report_lists_the_clients(self):
        output = self.run_report("administration_allclients")
        self.assertIn("Total Clients", output)
        self.assertIn("HH", output)

    def test_a_report_that_fails_shows_the_administration_form(self):
        html = self.run_report("administration_not_a_report")
        self.assertIn("administration_allclients", html)


def test_suite():
    suite = unittest.TestSuite()
    suite.addTest(unittest.makeSuite(TestReportModules))
    suite.addTest(unittest.makeSuite(TestSubmitForm))
    suite.addTest(unittest.makeSuite(TestAdministrationReports))
    return suite
