from pydantic import BaseModel, Field


class JiraWebhookPayload(BaseModel):
    webhookEvent: str = Field(min_length=1, max_length=100)
    issue: dict | None = None


class WebhookStatus(BaseModel):
    name: str = Field(min_length=1, max_length=150)


class WebhookAssignee(BaseModel):
    displayName: str = Field(min_length=1, max_length=150)


class WebhookFields(BaseModel):
    status: WebhookStatus
    assignee: WebhookAssignee | None


class WebhookIssue(BaseModel):
    key: str = Field(pattern=r"^[A-Za-z][A-Za-z0-9_]*-[0-9]+$", max_length=50)
    fields: WebhookFields
