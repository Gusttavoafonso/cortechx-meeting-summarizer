from app.core.config import Settings
from app.schemas.summary import SummaryResponse
from app.services.integrations.service import IntegrationService


class FakeProvider:
    def __init__(self, name, configured=True, error=None):
        self.name = name
        self.configured = configured
        self.error = error
        self.called = False

    def is_configured(self, settings):
        return self.configured

    def send(self, result, settings):
        self.called = True
        if self.error:
            raise self.error


def sample_result():
    return SummaryResponse(
        id=1,
        meeting_id=42,
        summary="Resumo persistido",
        key_points=[],
        decisions=[],
        tasks=[],
        created_at="2026-01-01T00:00:00Z",
        updated_at="2026-01-01T00:00:00Z",
    )


def test_dispatch_runs_all_configured_providers_even_if_one_fails():
    discord = FakeProvider("discord", error=RuntimeError("discord indisponível"))
    notion = FakeProvider("notion")
    service = IntegrationService([discord, notion], Settings())

    outcomes = service.dispatch(sample_result())

    assert discord.called and notion.called
    assert [(item.provider, item.status) for item in outcomes] == [
        ("discord", "FAILED"),
        ("notion", "SUCCESS"),
    ]


def test_dispatch_skips_unconfigured_provider():
    provider = FakeProvider("discord", configured=False)
    service = IntegrationService([provider], Settings())

    assert service.dispatch(sample_result()) == []
    assert not provider.called
