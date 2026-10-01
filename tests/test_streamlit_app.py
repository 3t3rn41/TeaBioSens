from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
READY = all((ROOT / f"artifacts/models/{name}/model.joblib").exists() for name in ["chemistry", "sensory", "direct_recipe"])


@pytest.mark.skipif(not READY, reason="Run the full pipeline before the Streamlit smoke check")
def test_streamlit_pages_execute_without_app_exceptions():
    from streamlit.testing.v1 import AppTest

    app = AppTest.from_file(str(ROOT / "app/app.py"), default_timeout=120).run()
    assert not app.exception, "Streamlit raised during initial page render: " + "; ".join(str(item.message) for item in app.exception)

