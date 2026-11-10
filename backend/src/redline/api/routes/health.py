import logging
from dataclasses import dataclass
from enum import StrEnum
from typing import Annotated

from fastapi import APIRouter, Depends
from psycopg import Connection

from redline.api.dependencies import get_connection
from redline.storage.database import check_database

logger = logging.getLogger(__name__)

router = APIRouter()


class HealthStatus(StrEnum):
    """Whether the service can reach the database."""

    OK = "ok"


@dataclass
class HealthResponse:
    """The body of a health check."""

    status: HealthStatus


@router.get("/health")
def get_health(connection: Annotated[Connection, Depends(get_connection)]) -> HealthResponse:
    """Report that the service and the database are reachable."""
    logger.info("Started health check")
    check_database(connection)
    logger.info("Finished health check")
    return HealthResponse(status=HealthStatus.OK)
