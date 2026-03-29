from __future__ import annotations

from typing import Annotated

from fastapi import Depends
from sqlalchemy.orm import Session

from dkb_runtime.db.session import get_db

DbSession = Annotated[Session, Depends(get_db)]
