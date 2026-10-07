# -*- coding: utf-8 -*-
"""The retrieval reports of the Storage tab (issue #76 §19)"""

import unittest
from datetime import date
from datetime import timedelta

from bika.lims import api
from bika.lims.workflow import doActionFor as do_action_for
from bika.reports.browser.reports.storage import registry
from bika.reports.tests.base import ReportsCase
from nmrl.lims.storage import api as sapi
from nmrl.lims.storage.config import TRANSACTION_DISPOSE
from nmrl.lims.storage.config import TRANSACTION_RETRIEVE

IDS = ("storage_retrievals_by_reason", "storage_retrievals_by_project",
       "storage_retrievals_by_date", "storage_requests_approved",
       "storage_requests_declined", "storage_returns_outstanding",
       "storage_returns_overdue")

TODAY = date.today()


class RetrievalCase(ReportsCase):

    def loose(self):
        """A stored sample with no project"""
        return self.stored_sample()[0]

    def request_for(self, samples, transaction_type=TRANSACTION_RETRIEVE,
                    approve=True, **values):
        values.setdefault("reason", u"Re-test")
        if transaction_type == TRANSACTION_DISPOSE:
            values.setdefault("method", u"autoclave")
        request, skipped = sapi.create_storage_request(
            samples, transaction_type, values)
        self.assertEqual(skipped, [])
        if approve:
            self.assertTrue(self.approve(request))
        return request

    def retrieved(self, samples, **values):
        """One request for the samples, approved and carried out"""
        request = self.request_for(samples, **values)
        for sample in samples:
            self.assertTrue(do_action_for(sample, "recover")[0])
        return request


class TestRegistered(RetrievalCase):

    def test_the_reports_are_in_the_retrieval_section_in_order(self):
        import bika.reports.browser.reports  # noqa
        self.assertEqual([r.id for r in registry.get_reports("retrieval")],
                         list(IDS))


class TestByReason(RetrievalCase):

    def test_it_counts_requests_and_samples_by_reason(self):
        self.retrieved([self.loose(), self.loose()], reason=u"Re-test")
        self.retrieved([self.loose()], reason=u"Confirmatory")
        rows = self.rows("storage_retrievals_by_reason")
        self.assertEqual(
            [(r["reason"], r["requests"], r["samples"]) for r in rows],
            [(u"Confirmatory", 1, 1), (u"Re-test", 1, 2)])

    def test_a_request_not_carried_out_is_not_a_retrieval(self):
        self.request_for([self.loose()])
        self.assertEqual(self.rows("storage_retrievals_by_reason"), [])

    def test_filters_project_requester_and_date(self):
        one = self.project(u"P-1")
        mine, box = self.stored_in(one)
        self.retrieved([mine], reason=u"Mine")
        other = self.retrieved([self.loose()], reason=u"Other")
        for line in sapi.get_lines(other):
            line.requester = u"someone"
        rows = self.rows("storage_retrievals_by_reason",
                         project=api.get_uid(one))
        self.assertEqual([r["reason"] for r in rows], [u"Mine"])
        rows = self.rows("storage_retrievals_by_reason", requester="someone")
        self.assertEqual([r["reason"] for r in rows], [u"Other"])
        tomorrow = TODAY + timedelta(days=1)
        self.assertEqual(self.rows(
            "storage_retrievals_by_reason",
            retrieved_fromdate=tomorrow.isoformat()), [])

    def test_the_footer_totals(self):
        self.retrieved([self.loose(), self.loose()])
        self.assertIn(u"Total 1 2",
                      self.text("storage_retrievals_by_reason"))


class TestByProject(RetrievalCase):

    def test_it_counts_by_requesting_project_and_those_without(self):
        target = self.project(u"P-2", u"Target")
        self.retrieved([self.loose(), self.loose()],
                       requesting_project=api.get_uid(target))
        self.retrieved([self.loose()])
        rows = self.rows("storage_retrievals_by_project")
        got = dict((r["project"], (r["requests"], r["samples"]))
                   for r in rows)
        self.assertEqual(got[target.get_full_title()], (1, 2))
        self.assertEqual(got[u"(none)"], (1, 1))

    def test_filters_requesting_project_reason_and_date(self):
        target = self.project(u"P-2", u"Target")
        self.retrieved([self.loose()], reason=u"A",
                       requesting_project=api.get_uid(target))
        self.retrieved([self.loose()], reason=u"B")
        rows = self.rows("storage_retrievals_by_project",
                         requesting_project=api.get_uid(target))
        self.assertEqual([r["project"] for r in rows],
                         [target.get_full_title()])
        rows = self.rows("storage_retrievals_by_project", reason="B")
        self.assertEqual([r["project"] for r in rows], [u"(none)"])
        tomorrow = TODAY + timedelta(days=1)
        self.assertEqual(self.rows(
            "storage_retrievals_by_project",
            retrieved_fromdate=tomorrow.isoformat()), [])


class TestByDate(RetrievalCase):

    def test_it_groups_by_month_by_default_and_by_the_period_chosen(self):
        self.retrieved([self.loose(), self.loose()])
        rows = self.rows("storage_retrievals_by_date")
        self.assertEqual([(r["period"], r["requests"], r["samples"])
                          for r in rows],
                         [(TODAY.strftime("%Y-%m"), 1, 2)])
        for group, expected in (
                ("day", TODAY.isoformat()),
                ("year", TODAY.strftime("%Y")),
                ("week", "{}-W{:02d}".format(*(TODAY.isocalendar()[:2])))):
            rows = self.rows("storage_retrievals_by_date", group_by=group)
            self.assertEqual([r["period"] for r in rows], [expected], group)

    def test_filters_project_and_date(self):
        one = self.project(u"P-1")
        mine, box = self.stored_in(one)
        self.retrieved([mine])
        self.retrieved([self.loose()])
        rows = self.rows("storage_retrievals_by_date",
                         project=api.get_uid(one))
        self.assertEqual(sum(r["samples"] for r in rows), 1)
        tomorrow = TODAY + timedelta(days=1)
        self.assertEqual(self.rows(
            "storage_retrievals_by_date",
            retrieved_fromdate=tomorrow.isoformat()), [])

    def test_a_bad_period_is_ignored(self):
        self.retrieved([self.loose()])
        rows = self.rows("storage_retrievals_by_date", group_by="century")
        self.assertEqual(len(rows), 1)


class TestApprovedAndDeclined(RetrievalCase):

    def make(self):
        approved = self.request_for([self.loose()])
        done = self.retrieved([self.loose(), self.loose()])
        refused = self.request_for([self.loose()], approve=False)
        do_action_for(refused, "decline")
        waiting = self.request_for([self.loose()], approve=False)
        draft, skipped = sapi.create_storage_request(
            [self.loose()], TRANSACTION_RETRIEVE, {"reason": u"x"},
            submit=False)
        disposal = self.request_for([self.loose()], TRANSACTION_DISPOSE)
        return approved, done, refused, waiting, draft, disposal

    def test_approved_are_the_approved_and_the_completed_ones(self):
        approved, done, refused, waiting, draft, disposal = self.make()
        rows = self.rows("storage_requests_approved")
        self.assertEqual(sorted(r["request"] for r in rows),
                         sorted([api.get_id(approved), api.get_id(done)]))
        by = dict((r["request"], r) for r in rows)
        row = by[api.get_id(done)]
        self.assertEqual((row["type"], row["samples"], row["state"]),
                         (u"RETRIEVE", 2, u"Completed"))
        self.assertTrue(row["requester"])
        self.assertTrue(row["decision_by"])
        self.assertEqual(row["decided"], TODAY.isoformat())
        self.assertEqual(row["reason"], u"Re-test")

    def test_approved_can_be_of_another_type_or_all(self):
        approved, done, refused, waiting, draft, disposal = self.make()
        rows = self.rows("storage_requests_approved", type="DISPOSE")
        self.assertEqual([r["request"] for r in rows],
                         [api.get_id(disposal)])
        rows = self.rows("storage_requests_approved", type="all")
        self.assertEqual(len(rows), 3)

    def test_approved_filters_requester_and_date(self):
        approved, done, refused, waiting, draft, disposal = self.make()
        approved.requester = u"someone"
        rows = self.rows("storage_requests_approved", requester="someone")
        self.assertEqual([r["request"] for r in rows],
                         [api.get_id(approved)])
        tomorrow = TODAY + timedelta(days=1)
        self.assertEqual(self.rows(
            "storage_requests_approved",
            decided_fromdate=tomorrow.isoformat()), [])

    def test_declined_lists_only_the_declined_with_the_decision(self):
        approved, done, refused, waiting, draft, disposal = self.make()
        refused.decision_reason = u"No capacity"
        rows = self.rows("storage_requests_declined")
        self.assertEqual([r["request"] for r in rows],
                         [api.get_id(refused)])
        self.assertEqual(rows[0]["decision_reason"], u"No capacity")
        self.assertEqual(rows[0]["decided"], TODAY.isoformat())
        self.assertEqual(self.rows("storage_requests_declined",
                                   type="DISPOSE"), [])
        self.assertEqual(self.rows(
            "storage_requests_declined", decided_fromdate=(
                TODAY + timedelta(days=1)).isoformat()), [])


class TestReturns(RetrievalCase):

    def out(self, days_ago, due_in=None, **values):
        sample = self.loose()
        if due_in is not None:
            values["expected_return_date"] = TODAY + timedelta(days=due_in)
        request = self.retrieved([sample], **values)
        line = sapi.get_lines(request)[0]
        line.physical_action_at = line.physical_action_at - timedelta(
            days=days_ago)
        return sample, line

    def test_outstanding_lists_everything_that_is_out_longest_first(self):
        recent, line_recent = self.out(1, due_in=5)
        old, line_old = self.out(10)
        rows = self.rows("storage_returns_outstanding")
        self.assertEqual(self.column(rows, "sample"),
                         [api.get_id(old), api.get_id(recent)])
        self.assertEqual(rows[0]["days_out"], 10)
        self.assertEqual(rows[0]["expected"], u"")
        self.assertEqual(rows[1]["expected"],
                         (TODAY + timedelta(days=5)).isoformat())

    def test_a_returned_sample_is_not_outstanding(self):
        sample, line = self.out(1)
        sapi.close_open_retrievals(sample)
        self.assertEqual(self.rows("storage_returns_outstanding"), [])

    def test_overdue_lists_only_the_late_ones_most_late_first(self):
        late, a = self.out(8, due_in=-3)
        later, b = self.out(12, due_in=-9)
        self.out(2, due_in=4)
        self.out(5)
        rows = self.rows("storage_returns_overdue")
        self.assertEqual(self.column(rows, "sample"),
                         [api.get_id(later), api.get_id(late)])
        self.assertEqual([r["days_overdue"] for r in rows], [9, 3])

    def test_filters_project_requesting_project_and_requester(self):
        one, target = self.project(u"P-1"), self.project(u"P-2")
        mine, box = self.stored_in(one)
        request = self.retrieved(
            [mine], requesting_project=api.get_uid(target),
            expected_return_date=TODAY - timedelta(days=2))
        other, line = self.out(3, due_in=-1)
        for report in ("storage_returns_outstanding",
                       "storage_returns_overdue"):
            self.assertEqual(self.column(self.rows(
                report, project=api.get_uid(one)), "sample"),
                [api.get_id(mine)], report)
            self.assertEqual(self.column(self.rows(
                report, requesting_project=api.get_uid(target)), "sample"),
                [api.get_id(mine)], report)
            self.assertEqual(self.rows(report, requester="nobody"), [],
                             report)


def test_suite():
    suite = unittest.TestSuite()
    for case in (TestRegistered, TestByReason, TestByProject, TestByDate,
                 TestApprovedAndDeclined, TestReturns):
        suite.addTest(unittest.makeSuite(case))
    return suite
