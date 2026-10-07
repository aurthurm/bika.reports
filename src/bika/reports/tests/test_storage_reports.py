# -*- coding: utf-8 -*-
"""The storage reports of the Storage tab (issue #76 §18)"""

import unittest
from datetime import date
from datetime import timedelta

from bika.lims import api
from bika.reports.browser.reports.storage import registry
from bika.reports.tests.base import ReportsCase
from DateTime import DateTime

IDS = ("storage_by_location", "storage_utilisation",
       "storage_stored_vs_retrieved", "storage_retention_approaching",
       "storage_retention_past", "storage_custody")


class StorageCase(ReportsCase):

    def retain(self, sample, days):
        """Keep the sample until `days` from today (negative: it passed)"""
        sample.setStorageExpiryDate(DateTime() + days)
        sample.reindexObject()

    def stored_loose(self, container=None):
        """A sample with no project, stored in a (new) container"""
        sample = self.create_sample()
        container = container or self.create_container()
        free = container.get_first_empty_position()
        self.assertTrue(container.add_object_at(sample, *free))
        return sample, container


class TestRegistered(StorageCase):

    def test_the_reports_are_in_the_storage_section_in_order(self):
        import bika.reports.browser.reports  # noqa
        self.assertEqual([r.id for r in registry.get_reports("storage")],
                         list(IDS))


class TestByLocation(StorageCase):

    def test_it_lists_every_stored_sample_by_container_and_position(self):
        a, box_a = self.stored_loose()
        b, box_a = self.stored_loose(box_a)
        project = self.project(u"P-1")
        c, box_c = self.stored_in(project)
        self.create_sample()   # received
        rows = self.rows("storage_by_location")
        self.assertEqual(len(rows), 3)
        by_sample = dict((r["sample"], r) for r in rows)
        self.assertEqual(by_sample[api.get_id(a)]["container"],
                         box_a.get_full_title())
        self.assertEqual(by_sample[api.get_id(a)]["position"],
                         box_a.position_to_alpha(0, 0))
        self.assertEqual(by_sample[api.get_id(b)]["position"],
                         box_a.position_to_alpha(0, 1))
        self.assertEqual(by_sample[api.get_id(c)]["project"],
                         project.get_full_title())
        self.assertEqual(by_sample[api.get_id(a)]["project"], u"")
        # by container, then by position
        containers = [r["container"] for r in rows]
        self.assertEqual(containers, sorted(containers))

    def test_filters(self):
        one = self.project(u"P-1")
        a, box_a = self.stored_in(one)
        b, box_b = self.stored_loose()
        self.assertEqual(self.column(self.rows(
            "storage_by_location", container=api.get_uid(box_b)), "sample"),
            [api.get_id(b)])
        self.assertEqual(self.column(self.rows(
            "storage_by_location", project=api.get_uid(one)), "sample"),
            [api.get_id(a)])
        other = api.create(api.get_senaite_setup().sampletypes, "SampleType",
                           title="Blood", Prefix="B")
        self.assertEqual(self.rows(
            "storage_by_location", sampletype=api.get_uid(other)), [])
        tomorrow = date.today() + timedelta(days=1)
        self.assertEqual(self.rows(
            "storage_by_location", stored_fromdate=tomorrow.isoformat()), [])

    def test_the_output_counts_by_container(self):
        a, box = self.stored_loose()
        self.stored_loose(box)
        text = self.text("storage_by_location")
        self.assertIn(u"{} 2".format(box.get_full_title()), text)
        self.assertIn(u"Total 2", text)


class TestUtilisation(StorageCase):

    def test_it_says_how_full_each_container_is(self):
        box = self.create_container(Rows=2, Columns=2)
        self.stored_loose(box)
        self.stored_loose(box)
        rows = self.rows("storage_utilisation")
        row = [r for r in rows if r["container"] == box.get_full_title()][0]
        self.assertEqual((row["capacity"], row["used"], row["held"],
                          row["free"]), (4, 2, 0, 2))
        self.assertEqual(row["percent"], u"50.0%")

    def test_a_position_held_for_a_retrieved_sample_is_not_free(self):
        box = self.create_container(Rows=2, Columns=2)
        sample, box = self.stored_loose(box)
        self.stored_loose(box)
        self.retrieve(sample, hold_position=True)
        row = self.rows("storage_utilisation")[0]
        self.assertEqual((row["used"], row["held"], row["free"]), (1, 1, 2))

    def test_an_unmanaged_container_has_its_capacity(self):
        from bika.lims import api as bika_api
        storage = self.portal.senaite_storage
        facility = bika_api.create(storage, "StorageFacility", title="F")
        position = bika_api.create(facility, "StoragePosition", title="R")
        freezer = bika_api.create(position, "StorageContainer", title="Z")
        loose = bika_api.create(freezer, "StorageSamplesContainer",
                                title="Loose", managed=False,
                                physical_capacity=3)
        self.assertTrue(loose.add_object(self.create_sample()))
        row = [r for r in self.rows("storage_utilisation")
               if r["container"] == loose.get_full_title()][0]
        self.assertEqual((row["capacity"], row["used"], row["free"]),
                         (3, 1, 2))

    def test_it_can_be_limited_to_a_container_or_to_full_ones(self):
        full = self.create_container(Rows=1, Columns=1, title="Full box")
        self.stored_loose(full)
        roomy = self.create_container(Rows=2, Columns=2, title="Roomy box")
        self.assertEqual(len(self.rows("storage_utilisation",
                                       container=api.get_uid(roomy))), 1)
        names = [r["container"] for r in self.rows(
            "storage_utilisation", fill="full")]
        self.assertEqual(names, [full.get_full_title()])
        names = [r["container"] for r in self.rows(
            "storage_utilisation", fill="free")]
        self.assertEqual(names, [roomy.get_full_title()])


class TestStoredVsRetrieved(StorageCase):

    def test_it_counts_what_is_in_and_what_is_out_by_sample_type(self):
        a, box = self.stored_loose()
        b, box = self.stored_loose(box)
        c, box = self.stored_loose(box)
        self.retrieve(c)
        rows = self.rows("storage_stored_vs_retrieved")
        self.assertEqual(len(rows), 1)
        self.assertEqual((rows[0]["sample_type"], rows[0]["stored"],
                          rows[0]["retrieved"], rows[0]["total"]),
                         (u"Water", 2, 1, 3))

    def test_filters_project_sample_type_and_container(self):
        one = self.project(u"P-1")
        a, box_a = self.stored_in(one)
        b, box_b = self.stored_loose()
        self.retrieve(a)
        rows = self.rows("storage_stored_vs_retrieved",
                         project=api.get_uid(one))
        self.assertEqual((rows[0]["stored"], rows[0]["retrieved"]), (0, 1))
        rows = self.rows("storage_stored_vs_retrieved",
                         container=api.get_uid(box_b))
        self.assertEqual((rows[0]["stored"], rows[0]["retrieved"]), (1, 0))
        # the container a sample left counts for the sample out
        rows = self.rows("storage_stored_vs_retrieved",
                         container=api.get_uid(box_a))
        self.assertEqual((rows[0]["stored"], rows[0]["retrieved"]), (0, 1))

    def test_the_footer_totals(self):
        a, box = self.stored_loose()
        self.assertIn(u"Total 1 0 1",
                      self.text("storage_stored_vs_retrieved"))


class TestRetention(StorageCase):

    def test_approaching_lists_what_expires_within_the_days(self):
        soon, box = self.stored_loose()
        later, box = self.stored_loose(box)
        past, box = self.stored_loose(box)
        none, box = self.stored_loose(box)
        self.retain(soon, 3)
        self.retain(later, 60)
        self.retain(past, -2)
        rows = self.rows("storage_retention_approaching", days="10")
        self.assertEqual(self.column(rows, "sample"), [api.get_id(soon)])
        self.assertEqual(rows[0]["expiry"],
                         (date.today() + timedelta(days=3)).isoformat())
        self.assertIn(rows[0]["days_left"], (2, 3))

    def test_the_days_default_to_the_warning_of_senaite_storage(self):
        from senaite.storage import api as storage_api
        warning = storage_api.get_warning_days_before_expiration()
        inside, box = self.stored_loose()
        outside, box = self.stored_loose(box)
        self.retain(inside, max(warning - 1, 0))
        self.retain(outside, warning + 20)
        rows = self.rows("storage_retention_approaching")
        self.assertEqual(self.column(rows, "sample"), [api.get_id(inside)])

    def test_approaching_filters_project_and_container(self):
        one = self.project(u"P-1")
        a, box_a = self.stored_in(one)
        b, box_b = self.stored_loose()
        self.retain(a, 2)
        self.retain(b, 2)
        self.assertEqual(self.column(self.rows(
            "storage_retention_approaching", days="10",
            project=api.get_uid(one)), "sample"), [api.get_id(a)])
        self.assertEqual(self.column(self.rows(
            "storage_retention_approaching", days="10",
            container=api.get_uid(box_b)), "sample"), [api.get_id(b)])

    def test_past_lists_what_expired_with_the_days(self):
        old, box = self.stored_loose()
        fresh, box = self.stored_loose(box)
        self.retain(old, -5)
        self.retain(fresh, 5)
        rows = self.rows("storage_retention_past")
        self.assertEqual(self.column(rows, "sample"), [api.get_id(old)])
        self.assertIn(rows[0]["days_past"], (4, 5))
        self.assertEqual(rows[0]["container"], box.get_full_title())

    def test_past_filters(self):
        one = self.project(u"P-1")
        a, box_a = self.stored_in(one)
        b, box_b = self.stored_loose()
        self.retain(a, -3)
        self.retain(b, -3)
        self.assertEqual(self.column(self.rows(
            "storage_retention_past", project=api.get_uid(one)), "sample"),
            [api.get_id(a)])
        self.assertEqual(self.column(self.rows(
            "storage_retention_past", container=api.get_uid(box_b)),
            "sample"), [api.get_id(b)])

    def test_a_bad_number_of_days_falls_back_to_the_default(self):
        a, box = self.stored_loose()
        self.retain(a, 1)
        rows = self.rows("storage_retention_approaching", days="abc")
        self.assertEqual(self.column(rows, "sample"), [api.get_id(a)])


class TestCustody(StorageCase):

    def test_it_says_where_each_sample_is(self):
        project = self.project(u"P-1")
        inside, box = self.stored_in(project)
        out, box_out = self.stored_loose()
        gone, box_gone = self.stored_loose()
        self.retrieve(out)
        self.dispose(gone)
        rows = dict((r["sample"], r)
                    for r in self.rows("storage_custody"))
        self.assertEqual(rows[api.get_id(inside)]["status"], u"Stored")
        self.assertEqual(rows[api.get_id(inside)]["where"],
                         u"{} · {}".format(box.get_full_title(),
                                           box.position_to_alpha(0, 0)))
        self.assertEqual(rows[api.get_id(inside)]["project"],
                         project.get_full_title())
        self.assertEqual(rows[api.get_id(out)]["status"], u"Retrieved")
        self.assertEqual(rows[api.get_id(out)]["since"],
                         date.today().isoformat())
        self.assertEqual(rows[api.get_id(gone)]["status"], u"Disposed")

    def test_filters_status_project_sample_type_and_container(self):
        one = self.project(u"P-1")
        a, box_a = self.stored_in(one)
        b, box_b = self.stored_loose()
        self.retrieve(b)
        self.assertEqual(self.column(self.rows(
            "storage_custody", status="retrieved"), "sample"),
            [api.get_id(b)])
        self.assertEqual(self.column(self.rows(
            "storage_custody", status="stored"), "sample"), [api.get_id(a)])
        self.assertEqual(self.column(self.rows(
            "storage_custody", project=api.get_uid(one)), "sample"),
            [api.get_id(a)])
        self.assertEqual(self.column(self.rows(
            "storage_custody", container=api.get_uid(box_b)), "sample"),
            [api.get_id(b)])

    def test_a_sample_never_stored_is_not_in_it(self):
        self.create_sample()
        self.assertEqual(self.rows("storage_custody"), [])


def test_suite():
    suite = unittest.TestSuite()
    for case in (TestRegistered, TestByLocation, TestUtilisation,
                 TestStoredVsRetrieved, TestRetention, TestCustody):
        suite.addTest(unittest.makeSuite(case))
    return suite
