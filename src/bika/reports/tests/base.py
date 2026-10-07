# -*- coding: utf-8 -*-
#
# Tests of the reports that run on SENAITE: the plain Plone fixture of the
# scaffold has no bika.lims in it.

import transaction
from plone.app.testing import FunctionalTesting
from plone.app.testing import applyProfile
from plone.testing import zope
from senaite.core.tests.base import BaseTestCase
from senaite.core.tests.layers import BaseLayer


class ReportsLayer(BaseLayer):

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


class ReportsTestCase(BaseTestCase):
    layer = REPORTS_TESTING
