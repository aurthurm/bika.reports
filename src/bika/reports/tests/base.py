# -*- coding: utf-8 -*-
#
# Tests of the reports that run on SENAITE with the storage module of
# nmrl.lims: the plain Plone fixture of the scaffold has no bika.lims in it.

import transaction
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
