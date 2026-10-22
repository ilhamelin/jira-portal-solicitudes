from typing import Annotated

from fastapi import APIRouter, Depends

from ...models import Usuario
from ...schemas.jira import BulkSyncResponse
from ...services.jira_client import JiraClient
from ..deps import Database, get_jira_client, require_role

router = APIRouter(prefix="/jira", tags=["jira"])


@router.post("/sync", response_model=BulkSyncResponse)
async def sync_all(
    db: Database, user: Annotated[Usuario, Depends(require_role("coordinador"))],
    jira: Annotated[JiraClient, Depends(get_jira_client)],
):
    return await jira.sync_all_active_issues(db)
