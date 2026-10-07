# -*- coding: utf-8 -*-
"""The project reports of the Storage tab (issue #76 §17)"""

import unittest
from datetime import date
from datetime import timedelta

from bika.lims import api
from bika.reports.browser.reports.storage import registry
from bika.reports.tests.base import ReportsCase

IDS = ("storage_project_registered", "storage_project_stored",
       "storage_project_retrieved", "storage_project_returned",
       "storage_project_disposed", "storage_project_summary")


class TestRegistered(ReportsCase):

    def test_the_reports_are_in_the_project_section_in_order(self):
        import bika.reports.browser.reports  # noqa  (registers them)
        ids = [r.id for r in registry.get_reports("project")]
        self.assertEqual(ids, list(IDS))

    def test_it_lists_the_samples_that_have_a_project(self):
        one, two = self.project(u"P-1"), self.project(u"P-2")
        a, b = self.sample_in(two), self.sample_in(one)
        self.create_sample()
        rows = self.rows("storage_project_registered")
        self.assertEqual(self.column(rows, "sample"),
                         [api.get_id(b), api.get_id(a)])
        self.assertEqual(self.column(rows, "project"),
                         [one.get_full_title(), two.get_full_title()])

    def test_the_row_says_type_state_and_date(self):
        sample = self.sample_in(self.project(u"P-1"))
        row = self.rows("storage_project_registered")[0]
        self.assertEqual(row["sample_type"], u"Water")
        self.assertEqual(row["state"], u"Received")
        self.assertEqual(row["created"], date.today().isoformat())

    def test_it_can_be_filtered_by_project_and_sample_type(self):
        one, two = self.project(u"P-1"), self.project(u"P-2")
        mine = self.sample_in(one)
        self.sample_in(two)
        rows = self.rows("storage_project_registered",
                         project=api.get_uid(one))
        self.assertEqual(self.column(rows, "sample"), [api.get_id(mine)])
        other = api.create(api.get_senaite_setup().sampletypes, "SampleType",
                           title="Blood", Prefix="B")
        self.assertEqual(self.rows(
            "storage_project_registered", sampletype=api.get_uid(other)), [])

    def test_it_can_be_filtered_by_the_date_registered(self):
        self.sample_in(self.project(u"P-1"))
        today = date.today()
        self.assertEqual(len(self.rows(
            "storage_project_registered",
            created_fromdate=today.isoformat(),
            created_todate=today.isoformat())), 1)
        self.assertEqual(self.rows(
            "storage_project_registered",
            created_fromdate=(today + timedelta(days=1)).isoformat()), [])
        self.assertEqual(self.rows(
            "storage_project_registered",
            created_todate=(today - timedelta(days=1)).isoformat()), [])

    def test_the_output_counts_by_project(self):
        one = self.project(u"P-1", u"Alpha")
        self.sample_in(one)
        self.sample_in(one)
        text = self.text("storage_project_registered")
        self.assertIn(u"P-1 - Alpha 2", text)
        self.assertIn(u"Total 2", text)

    def test_nothing_registered_is_an_empty_report(self):
        self.assertEqual(self.rows("storage_project_registered"), [])
        self.assertIn(u"Total 0", self.text("storage_project_registered"))


class TestStored(ReportsCase):

    def test_it_lists_the_stored_samples_of_the_projects_with_where(self):
        project = self.project(u"P-1")
        sample, container = self.stored_in(project)
        self.sample_in(project)  # received, not stored
        self.stored_sample()     # no project
        rows = self.rows("storage_project_stored")
        self.assertEqual(self.column(rows, "sample"), [api.get_id(sample)])
        self.assertEqual(rows[0]["container"], container.get_full_title())
        self.assertEqual(rows[0]["position"],
                         container.position_to_alpha(0, 0))
        self.assertEqual(rows[0]["stored"], date.today().isoformat())

    def test_filters_project_container_sample_type_and_date(self):
        one, two = self.project(u"P-1"), self.project(u"P-2")
        a, box_a = self.stored_in(one)
        b, box_b = self.stored_in(two)
        self.assertEqual(self.column(self.rows(
            "storage_project_stored", project=api.get_uid(two)), "sample"),
            [api.get_id(b)])
        self.assertEqual(self.column(self.rows(
            "storage_project_stored", container=api.get_uid(box_a)),
            "sample"), [api.get_id(a)])
        today = date.today()
        self.assertEqual(len(self.rows(
            "storage_project_stored",
            stored_fromdate=today.isoformat())), 2)
        self.assertEqual(self.rows(
            "storage_project_stored",
            stored_fromdate=(today + timedelta(days=1)).isoformat()), [])


class TestRetrieved(ReportsCase):

    def test_it_lists_what_is_out_with_who_for_and_when_back(self):
        project = self.project(u"P-1")
        target = self.project(u"P-2")
        sample, container = self.stored_in(project)
        due = date.today() + timedelta(days=5)
        self.retrieve(sample, expected_return_date=due,
                      requesting_project=api.get_uid(target))
        rows = self.rows("storage_project_retrieved")
        self.assertEqual(self.column(rows, "sample"), [api.get_id(sample)])
        self.assertEqual(rows[0]["project"], project.get_full_title())
        self.assertEqual(rows[0]["requesting_project"],
                         target.get_full_title())
        self.assertEqual(rows[0]["expected"], due.isoformat())
        self.assertEqual(rows[0]["retrieved"], date.today().isoformat())
        self.assertTrue(rows[0]["requester"])
        self.assertTrue(rows[0]["request"].startswith("SRQ-"))

    def test_a_returned_sample_and_one_without_project_are_not_listed(self):
        project = self.project(u"P-1")
        sample, container = self.stored_in(project)
        self.retrieve(sample)
        self.give_back(sample, container)
        loose, box = self.stored_sample()
        self.retrieve(loose)
        self.assertEqual(self.rows("storage_project_retrieved"), [])

    def test_filters_project_sample_type_and_date_retrieved(self):
        one, two = self.project(u"P-1"), self.project(u"P-2")
        a, box_a = self.stored_in(one)
        b, box_b = self.stored_in(two)
        self.retrieve(a)
        self.retrieve(b)
        self.assertEqual(self.column(self.rows(
            "storage_project_retrieved", project=api.get_uid(one)),
            "sample"), [api.get_id(a)])
        tomorrow = date.today() + timedelta(days=1)
        self.assertEqual(self.rows(
            "storage_project_retrieved",
            retrieved_fromdate=tomorrow.isoformat()), [])


class TestReturned(ReportsCase):

    def test_it_lists_the_returns_with_the_retrieval_and_where_to(self):
        project = self.project(u"P-1")
        sample, container = self.stored_in(project)
        self.retrieve(sample)
        self.give_back(sample, container)
        rows = self.rows("storage_project_returned")
        self.assertEqual(self.column(rows, "sample"), [api.get_id(sample)])
        self.assertEqual(rows[0]["returned"], date.today().isoformat())
        self.assertEqual(rows[0]["retrieved"], date.today().isoformat())
        self.assertEqual(rows[0]["container"], container.get_full_title())
        self.assertEqual(rows[0]["condition"], u"intact")

    def test_nothing_returned_nothing_listed_and_filters_work(self):
        project = self.project(u"P-1")
        sample, container = self.stored_in(project)
        self.retrieve(sample)
        self.assertEqual(self.rows("storage_project_returned"), [])
        self.give_back(sample, container)
        self.assertEqual(self.rows(
            "storage_project_returned", project=api.get_uid(
                self.project(u"P-9"))), [])
        tomorrow = date.today() + timedelta(days=1)
        self.assertEqual(self.rows(
            "storage_project_returned",
            returned_fromdate=tomorrow.isoformat()), [])


class TestDisposed(ReportsCase):

    def test_it_lists_the_disposed_with_method_reason_and_who(self):
        project = self.project(u"P-1")
        sample, container = self.stored_in(project)
        self.dispose(sample, method=u"incineration")
        rows = self.rows("storage_project_disposed")
        self.assertEqual(self.column(rows, "sample"), [api.get_id(sample)])
        self.assertEqual(rows[0]["method"], u"incineration")
        self.assertEqual(rows[0]["reason"], u"Old")
        self.assertEqual(rows[0]["disposed"], date.today().isoformat())
        self.assertTrue(rows[0]["by"])

    def test_filters_project_method_and_date(self):
        one, two = self.project(u"P-1"), self.project(u"P-2")
        a, box_a = self.stored_in(one)
        b, box_b = self.stored_in(two)
        self.dispose(a, method=u"autoclave")
        self.dispose(b, method=u"chemical")
        self.assertEqual(self.column(self.rows(
            "storage_project_disposed", method="chemical"), "sample"),
            [api.get_id(b)])
        self.assertEqual(self.column(self.rows(
            "storage_project_disposed", project=api.get_uid(one)),
            "sample"), [api.get_id(a)])
        tomorrow = date.today() + timedelta(days=1)
        self.assertEqual(self.rows(
            "storage_project_disposed",
            disposed_fromdate=tomorrow.isoformat()), [])


class TestSummary(ReportsCase):

    def test_it_counts_each_state_of_the_samples_of_a_project(self):
        project = self.project(u"P-1")
        stored, box = self.stored_in(project)
        out, box_out = self.stored_in(project)
        back, box_back = self.stored_in(project)
        gone, box_gone = self.stored_in(project)
        self.sample_in(project)                       # only registered
        self.retrieve(out)
        self.retrieve(back)
        self.give_back(back, box_back)
        self.dispose(gone)
        rows = self.rows("storage_project_summary")
        self.assertEqual(len(rows), 1)
        row = rows[0]
        self.assertEqual(row["project"], project.get_full_title())
        self.assertEqual(
            (row["registered"], row["stored"], row["retrieved"],
             row["returned"], row["disposed"]), (5, 2, 1, 1, 1))

    def test_a_project_without_samples_has_zeros(self):
        self.project(u"P-1")
        row = self.rows("storage_project_summary")[0]
        self.assertEqual((row["registered"], row["stored"], row["retrieved"],
                          row["returned"], row["disposed"]), (0, 0, 0, 0, 0))

    def test_it_can_be_limited_to_a_project_and_a_sample_type(self):
        one, two = self.project(u"P-1"), self.project(u"P-2")
        self.sample_in(one)
        self.sample_in(two)
        rows = self.rows("storage_project_summary",
                         project=api.get_uid(one))
        self.assertEqual(self.column(rows, "project"),
                         [one.get_full_title()])
        other = api.create(api.get_senaite_setup().sampletypes, "SampleType",
                           title="Blood", Prefix="B")
        rows = self.rows("storage_project_summary",
                         sampletype=api.get_uid(other))
        self.assertEqual(sum(r["registered"] for r in rows), 0)

    def test_csv_of_the_summary_has_a_row_per_project(self):
        self.project(u"P-1")
        report = self.report("storage_project_summary")
        text = report.csv_data(report.get_rows({}))
        self.assertEqual(len(text.strip().splitlines()), 2)


def test_suite():
    suite = unittest.TestSuite()
    for case in (TestRegistered, TestStored, TestRetrieved, TestReturned,
                 TestDisposed, TestSummary):
        suite.addTest(unittest.makeSuite(case))
    return suite
