from ingestion.collection_taxonomy import (
    CATEGORY_AI,
    CATEGORY_COGNITION,
    CATEGORY_CONTENT,
    CATEGORY_FINANCE,
    classify_collection_text,
)


def test_classifies_ai_items():
    result = classify_collection_text(
        title="Claude Code Workflow 必读：面向所有任务的 harness",
        body="用 Agent 和 Skill 搭建 Codex 自动化工作流。",
    )

    assert result.category == CATEGORY_AI
    assert "Claude Code" in result.tags
    assert "AI Agent" in result.tags


def test_classifies_content_items():
    result = classify_collection_text(
        title="X运营增长经验：如何从100到11万关注",
        body="适合自媒体内容创作、流量增长和获客转化。",
    )

    assert result.category == CATEGORY_CONTENT
    assert "增长" in result.tags
    assert "获客" in result.tags


def test_classifies_finance_items_first():
    result = classify_collection_text(
        title="Hermes + Polymarket：如何搭建 BTC 交易代理",
        body="用 Claude Code、Codex、AI Agent、Skill 搭一个交易系统。Alpha、BTC、Polymarket。",
    )

    assert result.category == CATEGORY_FINANCE
    assert "BTC" in result.tags
    assert "Polymarket" in result.tags


def test_defaults_to_cognition_when_no_specific_bucket_matches():
    result = classify_collection_text(
        title="how to be good at research",
        body="研究方法、判断、学习和决策。",
    )

    assert result.category == CATEGORY_COGNITION
    assert "研究方法" in result.tags


def test_strong_cognition_title_beats_ai_terms():
    result = classify_collection_text(
        title="AI 时代：认知 > 格局 > 技术 > 管理",
        body="Claude、Agent、AI 工具都只是外层，核心是判断和认知升级。",
    )

    assert result.category == CATEGORY_COGNITION
