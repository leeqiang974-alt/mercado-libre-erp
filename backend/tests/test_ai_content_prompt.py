from types import SimpleNamespace

from app.services.ai_content_generation import _build_prompt


def test_ai_prompt_keeps_existing_draft_evidence_when_source_text_is_sparse():
    draft = SimpleNamespace(
        title="20Pcs Black Cable Clips, Desk Wall Cord Organizer Holders",
        description=(
            "Existing product copy with the collected count, color, and intended desk and wall use."
        ),
        source_variant_attributes_json={"Color": "Black"},
    )
    source = SimpleNamespace(
        title="",
        description="",
        bullets_json=[],
        technical_details_json={},
        measurements_json={},
        variants_json=[],
    )

    prompt = _build_prompt(draft, source, "CBT414091")

    assert "CURRENT DRAFT DESCRIPTION: Existing product copy" in prompt
    assert "SOURCE TITLE: 20Pcs Black Cable Clips, Desk Wall Cord Organizer Holders" in prompt
    assert 'SOURCE DESCRIPTION: (not captured)' in prompt
    assert 'CURRENT DRAFT VARIANT ATTRIBUTES: {"Color": "Black"}' in prompt
    assert "120-250 English words" in prompt


def test_ai_prompt_includes_all_available_source_evidence_blocks():
    draft = SimpleNamespace(
        title="Listing title",
        description="Current draft evidence",
        source_variant_attributes_json={"Color": "Blue"},
    )
    source = SimpleNamespace(
        title="Source title",
        description="Source description",
        bullets_json=["Adhesive backing"],
        technical_details_json={"Material": "Silicone"},
        measurements_json={"item_weight": {"value": 10, "unit": "g"}},
        variants_json=[{"asin": "B000TEST01", "attributes": {"Color": "Blue"}}],
    )

    prompt = _build_prompt(draft, source, "CBT414091")

    assert "SOURCE DESCRIPTION: Source description" in prompt
    assert 'SOURCE BULLETS: ["Adhesive backing"]' in prompt
    assert 'SOURCE TECHNICAL DETAILS: {"Material": "Silicone"}' in prompt
    assert 'SOURCE MEASUREMENTS: {"item_weight": {"value": 10, "unit": "g"}}' in prompt
    assert 'SOURCE VARIANTS: [{"asin": "B000TEST01", "attributes": {"Color": "Blue"}}]' in prompt
    assert "CURRENT DRAFT DESCRIPTION: Current draft evidence" in prompt
