# -*- coding: utf-8 -*-
"""What the storage reports read, in one place: the storage data of
nmrl.lims. Without it the Storage page says it is not available
"""

from AccessControl import getSecurityManager
from bika.lims import api

try:
    from nmrl.lims.storage import api as sapi
    from nmrl.lims.storage.catalog import STORAGE_CATALOG
    from senaite.storage.permissions import TransitionRecoverSample
    HAS_STORAGE = True
except ImportError:  # pragma: no cover
    sapi = None
    STORAGE_CATALOG = None
    TransitionRecoverSample = None
    HAS_STORAGE = False


def can_use_storage(context):
    """Whether the user works with storage: the group that sees the storage
    history of a sample, and so its reports
    """
    if not HAS_STORAGE:
        return False
    return bool(getSecurityManager().checkPermission(
        TransitionRecoverSample, context))


def get_projects():
    """All the projects, whatever their state, by code: [{uid, title}]"""
    if not HAS_STORAGE:
        return []
    brains = api.search({
        "portal_type": "Project",
        "sort_on": "get_code_key",
        "sort_order": "ascending",
    }, STORAGE_CATALOG)
    return [{"uid": brain.UID, "title": brain.get_full_title}
            for brain in brains]


def get_sample_types():
    """The sample types, by title: [{uid, title}]"""
    brains = api.search({"portal_type": "SampleType",
                         "sort_on": "sortable_title"}, "senaite_catalog_setup")
    return [{"uid": brain.UID, "title": brain.Title} for brain in brains]


def get_containers():
    """The sample containers of the storage, by full title: [{uid, title}]"""
    if not HAS_STORAGE:
        return []
    from senaite.storage.catalog import STORAGE_CATALOG as CONTAINERS
    brains = api.search({"portal_type": "StorageSamplesContainer"},
                        CONTAINERS)
    containers = [{"uid": brain.UID,
                   "title": api.get_object(brain).get_full_title()}
                  for brain in brains]
    return sorted(containers, key=lambda item: item["title"])
