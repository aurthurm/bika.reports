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


# ---- helpers of the reports

if HAS_STORAGE:
    from nmrl.lims.storage.config import DISPOSAL_METHODS
    from nmrl.lims.storage.config import TRANSACTION_DISPOSE
    from nmrl.lims.storage.config import TRANSACTION_RETRIEVE
    from nmrl.lims.storage.config import TRANSACTION_RETURN
else:  # pragma: no cover
    DISPOSAL_METHODS = ()
    TRANSACTION_DISPOSE = TRANSACTION_RETRIEVE = TRANSACTION_RETURN = None


def to_date(value):
    """A date from a date, a datetime or a DateTime; None when empty"""
    if not value:
        return None
    if hasattr(value, "asdatetime"):
        return value.asdatetime().date()
    if hasattr(value, "date") and callable(value.date):
        return value.date()
    return value


def iso(value):
    """A date as text (YYYY-MM-DD), empty without one"""
    day = to_date(value)
    return day.isoformat() if day else u""


def date_in(value, daterange):
    """Whether the day of `value` is in the range (from, to), either end
    open. Without a range everything is in; a value without a date is not in
    a range that was given
    """
    if not daterange:
        return True
    day = to_date(value)
    if day is None:
        return False
    start, end = daterange
    return (not start or day >= start) and (not end or day <= end)


def created_query(daterange):
    """The catalog query of a range of the `created` index"""
    from DateTime import DateTime
    if not daterange:
        return None
    start, end = daterange
    start = start and DateTime(start.isoformat() + " 00:00:00")
    end = end and DateTime(end.isoformat() + " 23:59:59")
    if start and end:
        return {"query": [start, end], "range": "min:max"}
    return {"query": start or end, "range": "min" if start else "max"}


def state_title(obj):
    """The title of the state of an object, as people see it"""
    tool = api.get_tool("portal_workflow")
    state = api.get_review_status(obj)
    workflow = tool.getWorkflowsFor(obj)[0]
    return workflow.states[state].title if state in workflow.states \
        else state


def project_title(uid, cache=None):
    """The code and title of a project; empty without one"""
    if not uid:
        return u""
    if cache is not None and uid in cache:
        return cache[uid]
    project = api.get_object_by_uid(uid, None)
    title = project.get_full_title() if project is not None else u""
    if cache is not None:
        cache[uid] = title
    return title


def get_project_samples(project=None, review_state=None, sampletype=None,
                        created=None):
    """The samples that belong to a project (the given one or any), as
    objects, by project and then by date. Optionally in a state, of a sample
    type and registered in a range
    """
    from senaite.core.catalog import SAMPLE_CATALOG
    uids = [project] if project else [p["uid"] for p in get_projects()]
    if not uids:
        return []
    query = {"portal_type": "AnalysisRequest", "project_uid": uids}
    if review_state:
        query["review_state"] = review_state
    if sampletype:
        query["getSampleTypeUID"] = sampletype
    date_query = created_query(created)
    if date_query:
        query["created"] = date_query
    samples = [api.get_object(brain)
               for brain in api.search(query, SAMPLE_CATALOG)]
    titles = {}
    return sorted(samples, key=lambda sample: (
        project_title(sapi.get_sample_project_uid(sample), titles).lower(),
        sample.created()))


def get_lines(transaction_type, review_state=None):
    """The storage transactions (the lines of the requests) of a type"""
    query = {"portal_type": "StorageTransaction",
             "transaction_type": transaction_type}
    if review_state:
        query["review_state"] = review_state
    return [api.get_object(brain)
            for brain in api.search(query, STORAGE_CATALOG)]


def sample_of(line):
    return api.get_object_by_uid(line.sample_uid, None)


def sample_type_uid(sample):
    sample_type = sample.getSampleType()
    return api.get_uid(sample_type) if sample_type else None


def position_label(sample):
    """The container of the sample and the label of its position"""
    container = sapi.get_container(sample)
    if container is None:
        return None, u""
    position = container.get_object_position(sample)
    label = u""
    if position and container.requires_position_tracking():
        label = container.position_to_alpha(*position)
    return container, label


def get_container_objects(uid=None):
    """The sample containers (or the one with the UID) as objects, by full
    title"""
    if not HAS_STORAGE:
        return []
    from senaite.storage.catalog import STORAGE_CATALOG as CONTAINERS
    query = {"portal_type": "StorageSamplesContainer"}
    if uid:
        query["UID"] = uid
    containers = [api.get_object(brain)
                  for brain in api.search(query, CONTAINERS)]
    return sorted(containers, key=lambda item: item.get_full_title())


def get_stored_samples(project=None, sampletype=None, container=None):
    """The samples that are in storage now, optionally of a project, of a
    sample type and in a container (by UID)
    """
    from senaite.core.catalog import SAMPLE_CATALOG
    query = {"portal_type": "AnalysisRequest", "review_state": "stored"}
    if project:
        query["project_uid"] = project
    if sampletype:
        query["getSampleTypeUID"] = sampletype
    if container:
        found = get_container_objects(container)
        uids = found[0].get_samples_uids() if found else []
        if not uids:
            return []
        query["UID"] = uids
    return [api.get_object(brain)
            for brain in api.search(query, SAMPLE_CATALOG)]


def position_key(sample):
    """To put the samples of a container in the order of its positions"""
    container = sapi.get_container(sample)
    position = container.get_object_position(sample) if container else None
    return position or (0, 0)


def get_stored_or_disposed(state, values):
    """The samples in a state (disposed), of the project and sample type of
    the filters"""
    from senaite.core.catalog import SAMPLE_CATALOG
    query = {"portal_type": "AnalysisRequest", "review_state": state}
    if values.get("project"):
        query["project_uid"] = values["project"]
    if values.get("sampletype"):
        query["getSampleTypeUID"] = values["sampletype"]
    return [api.get_object(brain)
            for brain in api.search(query, SAMPLE_CATALOG)]
