from sqlalchemy.orm import Session

from app.models import AppSetting

TEST_MODE = "test_mode"


def read_flag(session: Session, key: str) -> bool | None:
    setting = session.get(AppSetting, key)
    return None if setting is None else setting.value == "1"


def write_flag(session: Session, key: str, enabled: bool) -> None:
    setting = session.get(AppSetting, key)
    if setting is None:
        session.add(AppSetting(key=key, value="1" if enabled else "0"))
    else:
        setting.value = "1" if enabled else "0"
