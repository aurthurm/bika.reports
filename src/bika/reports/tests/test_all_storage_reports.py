# -*- coding: utf-8 -*-
"""Every storage report opens, runs with no filter and with each output"""

import unittest

from bika.reports.browser.reports.storage import registry
from bika.reports.tests.base import ReportsCase

EXPECTED = 19


class TestEveryReport(ReportsCase):

    def reports(self):
        import bika.reports.browser.reports  # noqa  (registers them)
        found = []
        for category, title in registry.CATEGORIES:
            found.extend(registry.get_reports(category))
        return found

    def test_there_are_the_reports_of_the_issue(self):
        ids = [r.id for r in self.reports()]
        self.assertEqual(len(ids), EXPECTED)
        self.assertEqual(len(set(ids)), EXPECTED)
        self.assertTrue(all(i.startswith("storage_") for i in ids))

    def test_the_page_lists_them_all_in_their_sections(self):
        self.request.form.clear()
        html = self.folder.restrictedTraverse("storage")()
        for report in self.reports():
            self.assertIn('value="{}"'.format(report.id), html, report.id)
        for title in ("Project reports", "Storage reports",
                      "Retrieval reports"):
            self.assertIn(title, html)

    def test_every_report_runs_with_no_data_and_no_filter(self):
        for report in self.reports():
            output = self.report(report.id)()
            self.assertIn("report_data", output, report.id)
            self.assertIn("Total", output["report_data"], report.id)

    def test_every_report_makes_a_csv_with_its_columns(self):
        for report in self.reports():
            instance = self.report(report.id)
            text = instance.csv_data(instance.get_rows({}))
            self.assertEqual(len(text.strip().splitlines()[0].split(",")),
                             len(report.columns), report.id)

    def test_every_report_runs_through_the_form_that_makes_reports(self):
        for report in self.reports():
            self.request.form.clear()
            self.request.form["report_id"] = report.id
            html = self.folder.restrictedTraverse("createreport")()
            self.assertIn(report.title if isinstance(report.title, str)
                          else u"{}".format(report.title), html, report.id)


def test_suite():
    suite = unittest.TestSuite()
    suite.addTest(unittest.makeSuite(TestEveryReport))
    return suite
