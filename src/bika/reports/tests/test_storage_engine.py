# -*- coding: utf-8 -*-
"""The Storage tab of the reports, and the engine its reports run on"""

import unittest
from datetime import date

from AccessControl import Unauthorized
from bika.lims import api
from bika.reports.interfaces import IBikaReportsLayer
from bika.reports.tests.base import ReportsTestCase
from plone.app.testing import TEST_USER_ID
from plone.app.testing import setRoles
from zope.interface import alsoProvides


def stub_report():
    """A report to try the engine with"""
    from bika.lims.utils import t  # noqa
    from bika.reports import _
    from bika.reports.browser.reports.storage.base import StorageReport
    from bika.reports.browser.reports.storage import filters as flt

    class StubReport(StorageReport):
        id = "storage_stub"
        title = _(u"Stub report")
        description = _(u"A report to test the engine")
        category = "project"
        filters = (
            flt.DateRange("registered", _(u"Date registered")),
            flt.Project("project", _(u"Project")),
            flt.Choice("kind", _(u"Kind"),
                           options=(("a", _(u"Kind A")), ("b", _(u"Kind B")))),
            flt.Days("days", _(u"Within days"), default=30),
        )
        columns = (
            ("sample", _(u"Sample")),
            ("project", _(u"Project")),
            ("created", _(u"Registered")),
        )

        def get_rows(self, values):
            from senaite.core.catalog import SAMPLE_CATALOG
            query = {"portal_type": "AnalysisRequest",
                     "sort_on": "created", "sort_order": "ascending"}
            if values.get("project"):
                query["project_uid"] = values["project"]
            rows = []
            for brain in api.search(query, SAMPLE_CATALOG):
                rows.append({
                    "sample": brain.getId,
                    "project": values.get("project_title", u""),
                    "created": api.get_object(brain).created().strftime(
                        "%Y-%m-%d"),
                })
            return rows

    return StubReport


class TestEngine(ReportsTestCase):

    def setUp(self):
        super(TestEngine, self).setUp()
        alsoProvides(self.request, IBikaReportsLayer)
        self.folder = self.portal.reports
        from bika.reports.browser.reports.storage import registry
        self.registry = registry
        self.Stub = stub_report()
        registry.register(self.Stub)

    def tearDown(self):
        self.registry.unregister("storage_stub")
        super(TestEngine, self).tearDown()

    def run_report(self, **form):
        self.request.form.clear()
        self.request.form.update(form)
        return self.Stub(self.folder, self.request)()

    def text(self, output):
        import re
        return re.sub(r"\s+", " ", re.sub(r"<[^>]+>", " ", output))

    # the registry
    def test_the_registry_lists_the_reports_of_a_category(self):
        self.assertIn("storage_stub", [
            r.id for r in self.registry.get_reports("project")])
        self.assertEqual(self.registry.get_reports("retrieval"), [])
        self.assertIs(self.registry.get_report_class("storage_stub"),
                      self.Stub)
        self.assertIsNone(self.registry.get_report_class("storage_nothing"))

    def test_the_categories_are_in_the_order_of_the_page(self):
        self.assertEqual([c[0] for c in self.registry.CATEGORIES],
                         ["project", "storage", "retrieval"])

    # the report
    def test_the_output_has_a_title_the_parameters_and_the_rows(self):
        self.stored_sample()
        output = self.run_report()
        self.assertEqual(output["report_title"], u"Stub report")
        text = self.text(output["report_data"])
        self.assertIn(u"Stub report", text)
        self.assertIn(u"Sample", text)
        self.assertIn(u"Total", text)

    def test_the_project_filter_limits_the_rows_and_is_shown(self):
        project = self.create_project(u"P-1", u"One")
        mine = self.create_sample(Project=api.get_uid(project))
        self.create_sample()
        text = self.text(self.run_report(
            project=api.get_uid(project))["report_data"])
        self.assertIn(api.get_id(mine), text)
        self.assertIn(u"P-1", text)
        self.assertEqual(text.count(u"W26-"), 1)

    def test_the_dates_are_parsed(self):
        from bika.reports.browser.reports.storage import filters as flt
        self.request.form.clear()
        self.request.form.update({"registered_fromdate": "2026-01-02",
                                  "registered_todate": "2026-03-04"})
        parsed = flt.DateRange("registered", u"Registered").parse(
            self.request)
        self.assertEqual(parsed.value, (date(2026, 1, 2), date(2026, 3, 4)))
        self.assertFalse(parsed.error)

    def test_an_invalid_date_is_reported_and_ignored(self):
        self.stored_sample()
        output = self.run_report(registered_fromdate="2026-13-45")
        text = self.text(output["report_data"])
        self.assertIn(u"not a valid date", text)

    def test_an_unknown_choice_and_a_bad_number_are_ignored(self):
        output = self.run_report(kind="zzz", days="abc")
        self.assertIn(u"Stub report", self.text(output["report_data"]))
        output = self.run_report(days="-5")
        self.assertIn(u"Stub report", self.text(output["report_data"]))

    def test_the_form_has_a_control_for_each_filter(self):
        project = self.create_project(u"P-1", u"One")
        html = self.Stub(self.folder, self.request).form_html()
        for name in ("registered_fromdate", "registered_todate", "project",
                     "kind", "days", "output_format"):
            self.assertIn('name="{}"'.format(name), html)
        self.assertIn(api.get_uid(project), html)
        self.assertIn(u"Kind B", html)

    def test_csv_has_the_header_and_the_rows(self):
        sample = self.stored_sample()[0]
        report = self.Stub(self.folder, self.request)
        self.request.form.clear()
        text = report.csv_data(report.get_rows({}))
        lines = text.strip().splitlines()
        self.assertEqual(lines[0], "Sample,Project,Registered")
        self.assertTrue(lines[1].startswith(api.get_id(sample)))

    def test_csv_is_chosen_with_the_output_format(self):
        self.stored_sample()
        written = []
        self.request.RESPONSE.write = written.append
        output = self.run_report(output_format="CSV")
        self.assertIsNone(output)
        self.assertTrue(written)
        self.assertTrue(self.request.RESPONSE.getHeader(
            "Content-Type").startswith("text/csv"))

    # the form that makes the report
    def test_createreport_runs_a_registered_storage_report(self):
        sample = self.stored_sample()[0]
        self.request.form.clear()
        self.request.form["report_id"] = "storage_stub"
        html = self.folder.restrictedTraverse("createreport")()
        self.assertIn(api.get_id(sample), html)

    def test_an_unknown_storage_report_shows_the_storage_page(self):
        self.request.form.clear()
        self.request.form["report_id"] = "storage_nothing"
        html = self.folder.restrictedTraverse("createreport")()
        self.assertIn("Retrieval reports", html)
        self.assertNotIn("Productivity reports", html)

    def test_createreport_refuses_a_storage_report_to_who_cannot_use_it(self):
        setRoles(self.portal, TEST_USER_ID, ["Member"])
        self.request.form.clear()
        self.request.form["report_id"] = "storage_stub"
        with self.assertRaises(Unauthorized):
            self.folder.restrictedTraverse("createreport")()


class TestStoragePage(ReportsTestCase):

    def setUp(self):
        super(TestStoragePage, self).setUp()
        alsoProvides(self.request, IBikaReportsLayer)
        self.folder = self.portal.reports
        from bika.reports.browser.reports.storage import registry
        self.registry = registry
        self.Stub = stub_report()
        registry.register(self.Stub)

    def tearDown(self):
        self.registry.unregister("storage_stub")
        super(TestStoragePage, self).tearDown()

    def html(self):
        return self.folder.restrictedTraverse("storage")()

    def test_the_page_has_the_three_sections_in_order(self):
        html = self.html()
        positions = [html.index(title) for title in (
            "Project reports", "Storage reports", "Retrieval reports")]
        self.assertEqual(positions, sorted(positions))

    def test_a_report_is_listed_in_its_section_with_its_form(self):
        html = self.html()
        project_part = html[html.index("Project reports"):
                            html.index("Storage reports")]
        self.assertIn("Stub report", project_part)
        self.assertIn("A report to test the engine", project_part)
        self.assertIn('name="report_id"', project_part)
        self.assertIn('value="storage_stub"', project_part)
        self.assertIn("Generate report", project_part)

    def test_the_page_is_refused_to_who_cannot_use_storage(self):
        setRoles(self.portal, TEST_USER_ID, ["Member"])
        with self.assertRaises(Unauthorized):
            self.html()

    # the header
    def test_the_header_has_a_storage_tab(self):
        fti = api.get_tool("portal_types")["ReportFolder"]
        actions = dict((a.getId(), a) for a in fti.listActions())
        self.assertIn("storage", actions)
        self.assertEqual(actions["storage"].title, "Storage")
        self.assertTrue(actions["storage"].getActionExpression().endswith(
            "/storage"))
        # after the other tabs
        ids = [a.getId() for a in fti.listActions()]
        self.assertLess(ids.index("administration"), ids.index("storage"))

    def test_the_upgrade_gives_an_existing_site_the_tab(self):
        from bika.reports.upgrades.v01_00_002 import upgrade
        fti = api.get_tool("portal_types")["ReportFolder"]
        fti.deleteActions([
            i for i, a in enumerate(fti.listActions())
            if a.getId() == "storage"])
        self.assertNotIn("storage", [a.getId() for a in fti.listActions()])
        upgrade(api.get_tool("portal_setup"))
        self.assertIn("storage", [a.getId() for a in fti.listActions()])

    def test_the_upgrade_is_offered_to_a_site_at_1_0_1(self):
        tool = api.get_tool("portal_setup")
        tool.setLastVersionForProfile("bika.reports:default", "1.0.1")
        steps = []
        for entry in tool.listUpgrades("bika.reports:default"):
            steps.extend(entry if isinstance(entry, list) else [entry])
        self.assertTrue([s for s in steps
                         if s.get("dest") == ("1", "0", "2")] or
                        [s for s in steps if "Storage" in s.get("title", "")])


def test_suite():
    suite = unittest.TestSuite()
    suite.addTest(unittest.makeSuite(TestEngine))
    suite.addTest(unittest.makeSuite(TestStoragePage))
    return suite
