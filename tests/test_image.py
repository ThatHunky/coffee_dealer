"""Smoke tests for image renderer."""

from datetime import date

from src.image_render import renderer
from src.models import Assignment


def test_renderer_creates_image():
    """Test that renderer creates a non-empty PNG."""
    year, month = 2024, 10

    # Create some test assignments
    assignments = [
        Assignment.from_people(date(2024, 10, 5), ["diana"]),
        Assignment.from_people(date(2024, 10, 10), ["dana", "zhenya"]),
        Assignment.from_people(date(2024, 10, 15), ["diana", "dana"]),
    ]

    # Render
    img_buffer = renderer.render(year, month, assignments)

    # Check non-empty
    assert img_buffer is not None
    img_data = img_buffer.read()
    assert len(img_data) > 0
    assert img_data[:4] == b"\x89PNG"  # PNG magic bytes


def test_assignment_emojis():
    """Test that assignments have correct emojis."""
    # Diana only -> blue circle
    a1 = Assignment.from_people(date(2024, 10, 1), ["diana"])
    assert a1.get_color() == "🔵"

    # Dana only -> purple circle
    a2 = Assignment.from_people(date(2024, 10, 2), ["dana"])
    assert a2.get_color() == "🟣"

    # Zhenya only -> green circle
    a3 = Assignment.from_people(date(2024, 10, 3), ["zhenya"])
    assert a3.get_color() == "🟢"

    # Diana + Zhenya -> pink heart
    a4 = Assignment.from_people(date(2024, 10, 4), ["diana", "zhenya"])
    assert a4.get_color() == "🩷"

    # Dana + Zhenya -> yellow circle
    a5 = Assignment.from_people(date(2024, 10, 5), ["dana", "zhenya"])
    assert a5.get_color() == "🟡"

    # Dana + Diana -> red circle
    a6 = Assignment.from_people(date(2024, 10, 6), ["dana", "diana"])
    assert a6.get_color() == "🔴"


def test_bitmask_mapping():
    """Test that bitmask mapping is correct."""
    # Test individual bits
    a = Assignment.from_people(date(2024, 10, 1), ["diana"])
    assert a.mask == 1
    assert a.diana is True
    assert a.dana is False
    assert a.zhenya is False

    a = Assignment.from_people(date(2024, 10, 2), ["dana"])
    assert a.mask == 2
    assert a.diana is False
    assert a.dana is True
    assert a.zhenya is False

    a = Assignment.from_people(date(2024, 10, 3), ["zhenya"])
    assert a.mask == 4
    assert a.diana is False
    assert a.dana is False
    assert a.zhenya is True

    # Test combinations
    a = Assignment.from_people(date(2024, 10, 4), ["diana", "dana", "zhenya"])
    assert a.mask == 7
    assert a.diana is True
    assert a.dana is True
    assert a.zhenya is True
