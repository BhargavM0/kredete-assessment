from enum import Enum
from typing import List, Optional
from datetime import datetime
from pydantic import BaseModel, Field


class RunStatus(str, Enum):
    PENDING = "PENDING"
    RUNNING = "RUNNING"
    COMPLETED = "COMPLETED"
    FAILED = "FAILED"
    MAX_STEPS_EXCEEDED = "MAX_STEPS_EXCEEDED"


class StepStatus(str, Enum):
    PENDING = "PENDING"
    RUNNING = "RUNNING"
    COMPLETED = "COMPLETED"
    FAILED = "FAILED"


class Step(BaseModel):
    name: str
    status: StepStatus = StepStatus.PENDING
    cost: int = 0
    charged: bool = False
    output: Optional[str] = None
    error: Optional[str] = None
    started_at: Optional[datetime] = None
    finished_at: Optional[datetime] = None


class Run(BaseModel):
    id: str
    goal: str
    status: RunStatus
    steps: List[Step] = Field(default_factory=list)
    credits_consumed: int = 0
    max_steps: int = 10
    created_at: datetime


class CreateRunRequest(BaseModel):
    goal: str
    max_steps: Optional[int] = 10
