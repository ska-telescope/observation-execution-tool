"""
The ska_oso.activity.domain module contains code that belongs to the activity
domain layer. Classes and definitions contained in this domain layer define
the high-level concepts used to describe and launch scheduling block
activities.
"""
import enum
from typing import Optional

from pydantic import BaseModel


class ActivityState(enum.Enum):
    """
    ActivityState represent the state of an Activity.

    ActivityState is currently a placeholder, to be elaborated with the full
    activity lifecycle (CREATED, RUNNING, SUCCEEDED, FAILED, etc.) in a later
    PI.
    """

    TODO = enum.auto()


class Activity(BaseModel):
    """
    Activity represents an action taken on a scheduling block.

    An activity maps to a script that accomplishes the activity's goal. In a
    telescope control context, activities and goals could be 'allocate
    resources for this SB', 'observe this SB', etc. That is, users talk about
    doing something with the SB; their focus is not on which script needs to
    run and what script parameters are required to accomplish that task.
    """

    activity_id: int
    procedure_id: Optional[int]
    sbd_id: str
    activity_name: str
    prepare_only: bool
    sbi_id: str
