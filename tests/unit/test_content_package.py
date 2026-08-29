from agents.content.runtime import ContentAgent
from agents.strategy.runtime import StrategyAgent, StrategyPlan
from content.models import Campaign, ContentPackage


def test_content_package_fields_are_first_class():
    package = ContentPackage(
        "pkg-1",
        "Title",
        "Body",
        topic="hooks",
        content_pillar="proof",
        hook="stop guessing",
        format="post",
        audience="founders",
        caption="Body",
        media_assets=("a.png",),
        commerce_intent="none",
        brand_id="brand-a",
        creator_id="creator-a",
        campaign_id="camp-1",
    )
    assert package.id == "pkg-1"
    assert package.hook == "stop guessing"
    assert "hook" not in package.metadata


def test_campaign_and_strategy_plan():
    campaign = Campaign("camp-1", "grow replies", audience="founders", status="active")
    assert campaign.id == "camp-1"
    result = StrategyAgent().run({"objective": "grow replies", "audience": "founders"})
    plan = result["plan"]
    assert isinstance(plan, StrategyPlan)
    assert plan.objective == "grow replies"
    assert plan.experiment_plan["observation_window"]
    content = ContentAgent().run({"title": "A", "body": "B", "hook": "H", "campaign_id": campaign.campaign_id})
    assert content["package"].hook == "H"
    assert content["package"].campaign_id == "camp-1"
