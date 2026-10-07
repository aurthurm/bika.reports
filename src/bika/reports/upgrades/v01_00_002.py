# -*- coding: utf-8 -*-
#
# This file is part of BIKA.REPORTS.

from bika.reports import PROFILE_ID
from bika.reports import logger


def upgrade(tool):
    """Adds the Storage tab to the header of the reports: the actions of the
    type of the reports folder come from the profile
    """
    logger.info("Upgrade to BIKA.REPORTS 1.0.2 [BEGIN]")
    tool.runImportStepFromProfile(PROFILE_ID, "typeinfo")
    logger.info("Upgrade to BIKA.REPORTS 1.0.2 [DONE]")
