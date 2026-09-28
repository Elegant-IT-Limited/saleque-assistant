from tests.api.conftest import auth
from tests.support.seed import ID, WS_A


def test_scoring_another_workspaces_lead_is_a_404_not_a_leak(api):
    assert api.post(f"/api/internal/leads/{ID['leadA']}/score", headers=auth(WS_A)).json()["owner"] == "sales"
    # lead B exists, just not in workspace A; the answer must be indistinguishable from a bad id
    assert api.post(f"/api/internal/leads/{ID['leadB']}/score", headers=auth(WS_A)).status_code == 404
