from __future__ import annotations

from datetime import datetime
from typing import Literal

from pydantic import BaseModel, Field

TaskStatus = Literal["inbox", "todo", "in_progress", "done"]
TaskPriority = Literal["low", "medium", "high"]
DealStatus = Literal["lead", "qualified", "proposal", "won", "lost"]


class HealthResponse(BaseModel):
    status: str


class TaskListCreate(BaseModel):
    name: str = Field(min_length=1, max_length=80)
    color: str = Field(default="#64748b", min_length=4, max_length=20)


class TaskListUpdate(BaseModel):
    name: str | None = Field(default=None, min_length=1, max_length=80)
    color: str | None = Field(default=None, min_length=4, max_length=20)


class TaskListOut(BaseModel):
    id: str
    name: str
    color: str
    created_at: datetime


class SprintCreate(BaseModel):
    name: str = Field(min_length=1, max_length=120)
    start_date: datetime | None = None
    end_date: datetime | None = None
    directions: list[str] = Field(
        default_factory=lambda: ["Health", "Career", "Relationships", "Growth"],
        min_length=4,
        max_length=4,
    )


class SprintUpdate(BaseModel):
    name: str | None = Field(default=None, min_length=1, max_length=120)
    start_date: datetime | None = None
    end_date: datetime | None = None


class SprintDirectionOut(BaseModel):
    id: str
    sprint_id: str
    name: str
    position: int
    created_at: datetime


class SprintOut(BaseModel):
    id: str
    name: str
    start_date: datetime | None
    end_date: datetime | None
    created_at: datetime
    directions: list[SprintDirectionOut]


class SprintDirectionUpdate(BaseModel):
    name: str = Field(min_length=1, max_length=80)


class SprintActiveUpdate(BaseModel):
    sprint_id: str | None = None


class SprintActiveOut(BaseModel):
    sprint_id: str | None
    sprint: SprintOut | None


class TaskCreate(BaseModel):
    title: str = Field(min_length=1, max_length=200)
    note: str | None = None
    status: TaskStatus = "inbox"
    priority: TaskPriority = "medium"
    duration_min: int = Field(ge=1, le=1440)
    deadline: datetime | None = None
    list_id: str
    sprint_id: str | None = None
    sprint_direction_id: str | None = None


class TaskUpdate(BaseModel):
    title: str | None = Field(default=None, min_length=1, max_length=200)
    note: str | None = None
    status: TaskStatus | None = None
    priority: TaskPriority | None = None
    duration_min: int | None = Field(default=None, ge=1, le=1440)
    deadline: datetime | None = None
    list_id: str | None = None
    sprint_id: str | None = None
    sprint_direction_id: str | None = None


class TaskMove(BaseModel):
    status: TaskStatus


class TaskOut(BaseModel):
    id: str
    title: str
    note: str | None
    status: TaskStatus
    priority: TaskPriority
    duration_min: int
    deadline: datetime | None
    list_id: str
    sprint_id: str | None
    sprint_direction_id: str | None
    created_at: datetime
    updated_at: datetime


class TimeBlockCreate(BaseModel):
    task_id: str
    start_at: datetime
    end_at: datetime


class TimeBlockUpdate(BaseModel):
    start_at: datetime | None = None
    end_at: datetime | None = None


class TimeBlockOut(BaseModel):
    id: str
    task_id: str
    start_at: datetime
    end_at: datetime
    created_at: datetime


class CalendarEventOut(BaseModel):
    block: TimeBlockOut
    task: TaskOut


class CRMContactCreate(BaseModel):
    full_name: str = Field(min_length=1, max_length=120)
    email: str | None = None
    phone: str | None = None
    company: str | None = None
    note: str | None = None


class CRMContactUpdate(BaseModel):
    full_name: str | None = Field(default=None, min_length=1, max_length=120)
    email: str | None = None
    phone: str | None = None
    company: str | None = None
    note: str | None = None


class CRMContactOut(BaseModel):
    id: str
    full_name: str
    email: str | None
    phone: str | None
    company: str | None
    note: str | None
    created_at: datetime
    updated_at: datetime


class CRMDealCreate(BaseModel):
    title: str = Field(min_length=1, max_length=200)
    contact_id: str | None = None
    status: DealStatus = "lead"
    value_amount: float | None = None
    due_date: datetime | None = None
    note: str | None = None
    linked_task_id: str | None = None


class CRMDealUpdate(BaseModel):
    title: str | None = Field(default=None, min_length=1, max_length=200)
    contact_id: str | None = None
    status: DealStatus | None = None
    value_amount: float | None = None
    due_date: datetime | None = None
    note: str | None = None
    linked_task_id: str | None = None


class CRMDealOut(BaseModel):
    id: str
    title: str
    contact_id: str | None
    status: DealStatus
    value_amount: float | None
    due_date: datetime | None
    note: str | None
    linked_task_id: str | None
    created_at: datetime
    updated_at: datetime


class IntegrationConfigUpdate(BaseModel):
    enabled: bool
    settings_json: str = "{}"


class IntegrationConfigOut(BaseModel):
    provider: str
    enabled: bool
    settings_json: str
    updated_at: datetime


class StubCapabilityOut(BaseModel):
    module: str
    status: str
    message: str


class VoiceTaskParseRequest(BaseModel):
    transcript: str = Field(min_length=1, max_length=4000)
    list_id: str | None = None


class VoiceTaskParseOut(BaseModel):
    transcript: str
    title: str
    note: str | None
    status: TaskStatus | None
    priority: TaskPriority | None
    duration_min: int | None
    deadline: datetime | None
    list_id: str | None
    missing_fields: list[str]
    requires_clarification: bool
    next_question: str | None


class VoiceTaskCreateRequest(BaseModel):
    transcript: str = Field(min_length=1, max_length=4000)
    list_id: str
    sprint_id: str | None = None
    sprint_direction_id: str | None = None
    title: str | None = None
    note: str | None = None
    status: TaskStatus | None = None
    priority: TaskPriority | None = None
    duration_min: int | None = Field(default=None, ge=1, le=1440)
    deadline: datetime | None = None


class VoiceTaskCandidateOut(BaseModel):
    title: str
    note: str | None
    status: TaskStatus | None
    priority: TaskPriority | None
    duration_min: int | None
    deadline: datetime | None
    missing_fields: list[str]
    requires_clarification: bool
    next_question: str | None


class VoiceMessageAnalyzeRequest(BaseModel):
    message: str = Field(min_length=1, max_length=8000)
    list_id: str | None = None


class VoiceMessageAnalyzeOut(BaseModel):
    provider: str
    model: str | None
    tasks: list[VoiceTaskCandidateOut]
    error: str | None


class VoiceCreateManyRequest(BaseModel):
    message: str = Field(min_length=1, max_length=8000)
    list_id: str
    sprint_id: str | None = None
    sprint_direction_id: str | None = None


class VoiceCreateManyOut(BaseModel):
    provider: str
    model: str | None
    created_count: int
    tasks: list[TaskOut]
    error: str | None


class VoiceQuickActionOut(BaseModel):
    action: str
    label: str


class VoiceOperationOut(BaseModel):
    type: Literal["query", "delete", "update_status"]
    text: str | None = None
    status: TaskStatus | None = None
    without_deadline: bool = False
    new_status: TaskStatus | None = None
    relative_day: Literal["today", "yesterday"] | None = None
    limit: int = Field(default=10, ge=1, le=50)


class VoiceChatTurnRequest(BaseModel):
    message: str = Field(min_length=1, max_length=8000)
    list_id: str | None = None


class VoiceChatTurnOut(BaseModel):
    provider: str
    model: str | None
    intent: str
    assistant_reply: str
    active_sprint_id: str | None = None
    active_sprint_name: str | None = None
    tasks: list[VoiceTaskCandidateOut]
    actions: list[VoiceQuickActionOut]
    operation: VoiceOperationOut | None = None
    error: str | None


class VoiceConfirmTasksRequest(BaseModel):
    list_id: str
    tasks: list[VoiceTaskCandidateOut]
    sprint_id: str | None = None
    sprint_direction_id: str | None = None


class VoiceConfirmTasksOut(BaseModel):
    provider: str
    model: str | None
    created_count: int
    tasks: list[TaskOut]


class VoiceApplyActionRequest(BaseModel):
    action: str
    operation: VoiceOperationOut | None = None
    list_id: str | None = None
    task_ids: list[str] | None = None


class VoiceApplyActionOut(BaseModel):
    action: str
    affected_count: int
    tasks: list[TaskOut]
    assistant_reply: str
    preview_only: bool


class ChatHistoryConfigOut(BaseModel):
    enabled: bool
    retention_days: int


class ChatHistoryConfigUpdate(BaseModel):
    enabled: bool
    retention_days: int = Field(default=30, ge=1, le=365)


class ChatHistoryMessageOut(BaseModel):
    id: str
    role: str
    content: str
    intent: str | None
    provider: str | None
    model: str | None
    created_at: datetime
