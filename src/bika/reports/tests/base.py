# -*- coding: utf-8 -*-
#
# Tests of the reports that run on SENAITE with the storage module of
# nmrl.lims: the plain Plone fixture of the scaffold has no bika.lims in it.

import re
from HTMLParser import HTMLParser

import transaction
from bika.lims import api
from bika.lims.workflow import doActionFor as do_action_for
from bika.reports.browser.reports.storage import registry
from bika.reports.interfaces import IBikaReportsLayer
from nmrl.lims.storage import api as sapi
from nmrl.lims.storage.config import TRANSACTION_DISPOSE
from nmrl.lims.storage.config import TRANSACTION_RETRIEVE
from nmrl.lims.storage.config import TRANSACTION_RETURN
from zope.interface import alsoProvides
from nmrl.lims.storage.tests.base import StorageTestCase
from nmrl.lims.storage.tests.base import StorageTestLayer
from plone.app.testing import FunctionalTesting
from plone.app.testing import applyProfile
from plone.testing import zope


class ReportsLayer(StorageTestLayer):

    def setUpZope(self, app, configurationContext):
        super(ReportsLayer, self).setUpZope(app, configurationContext)
        import bika.reports
        self.loadZCML(package=bika.reports)
        zope.installProduct(app, "bika.reports")

    def setUpPloneSite(self, portal):
        super(ReportsLayer, self).setUpPloneSite(portal)
        applyProfile(portal, "bika.reports:default")
        transaction.commit()


REPORTS_LAYER_FIXTURE = ReportsLayer()
REPORTS_TESTING = FunctionalTesting(
    bases=(REPORTS_LAYER_FIXTURE, ),
    name="bika.reports:ReportsTesting"
)


class ReportsTestCase(StorageTestCase):
    """A test case with a client, a contact and a sample type, and the helpers
    of the storage tests (stored samples, projects, requests)"""
    layer = REPORTS_TESTING


class ReportsCase(ReportsTestCase):
    """What the tests of the reports share"""

    def setUp(self):
        super(ReportsCase, self).setUp()
        alsoProvides(self.request, IBikaReportsLayer)
        self.folder = self.portal.reports
        self.request.environ["REQUEST_METHOD"] = "GET"
        self.enable_dispose()
        self.enable_governance()

    def report(self, report_id, **form):
        self.request.form.clear()
        self.request.form.update(form)
        return registry.get_report_class(report_id)(self.folder, self.request)

    def rows(self, report_id, **form):
        report = self.report(report_id, **form)
        values, parms = report.parse_filters()
        return report.get_rows(values)

    def column(self, rows, key):
        return [row[key] for row in rows]

    def text(self, report_id, **form):
        output = self.report(report_id, **form)()
        text = re.sub(r"<[^>]+>", " ", output["report_data"])
        return re.sub(r"\s+", " ", HTMLParser().unescape(text))

    def project(self, code, title=u"Project"):
        return self.create_project(code, title)

    def sample_in(self, project, **extra):
        return self.create_sample(Project=api.get_uid(project), **extra)

    def stored_in(self, project, container=None):
        """A sample of the project, stored in a (new) container"""
        sample = self.create_sample(Project=api.get_uid(project))
        container = container or self.create_container()
        free = container.get_first_empty_position()
        self.assertTrue(container.add_object_at(sample, *free))
        return sample, container

    def retrieve(self, sample, **values):
        values.setdefault("reason", u"Re-test")
        line = self.ready_request(sample, TRANSACTION_RETRIEVE, **values)
        self.assertTrue(do_action_for(sample, "recover")[0])
        return line

    def give_back(self, sample, container):
        request, skipped = sapi.create_storage_request(
            [sample], TRANSACTION_RETURN,
            {"reason": u"Done", "condition": u"intact"})
        self.assertTrue(self.approve(request))
        free = container.get_first_empty_position()
        self.assertTrue(container.add_object_at(sample, *free))
        return sapi.get_lines(request)[0]

    def dispose(self, sample, method=u"autoclave"):
        line = self.ready_request(sample, TRANSACTION_DISPOSE,
                                  method=method, reason=u"Old")
        self.assertTrue(do_action_for(sample, "dispose")[0])
        return line
