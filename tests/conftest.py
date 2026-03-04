import sys
import os
import time
import tempfile
from pathlib import Path
import pytest

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

def pytest_configure(config):  # type: ignore[no-untyped-def]
    run_tag = f"run_{os.getpid()}_{int(time.time())}"
    roots = []
    env_root = str(os.environ.get("NH_PYTEST_TMP") or "").strip()
    if env_root:
        roots.append(Path(env_root))
    roots.extend(
        [
            ROOT / "tmp_pytest_work",
            ROOT / "tmp_pytest",
            Path(tempfile.gettempdir()) / "nova_hub_pytest",
        ]
    )

    base = None
    last_error = None
    for root in roots:
        try:
            candidate = root / run_tag
            candidate.mkdir(parents=True, exist_ok=True)
            base = candidate
            break
        except (OSError, ValueError, TypeError, KeyError, AttributeError, RuntimeError) as exc:
            last_error = exc
            continue

    if base is None:
        raise RuntimeError(f"Unable to create writable pytest base temp. Last error: {last_error}")

    # Unique workspace-local base temp avoids stale locks/ACL conflicts on Windows.
    config.option.basetemp = str(base)
    # Route stdlib tempfile users (TemporaryDirectory, mkdtemp) into workspace.
    os.environ["TMP"] = str(base)
    os.environ["TEMP"] = str(base)
    os.environ["TMPDIR"] = str(base)


@pytest.fixture(scope="session", autouse=True)
def _force_test_mode_env():
    prev = os.environ.get("NH_TEST_MODE")
    os.environ["NH_TEST_MODE"] = "1"
    try:
        yield
    finally:
        if prev is None:
            os.environ.pop("NH_TEST_MODE", None)
        else:
            os.environ["NH_TEST_MODE"] = prev
