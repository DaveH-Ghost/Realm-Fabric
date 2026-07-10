"""Session-level area CRUD (typed API)."""

from campaign_rpg_engine.session import Session


def test_create_area_command():
    session = Session.from_default()
    result = session.create_area(
        "attic",
        description="A dusty attic.",
        width=6,
        height=4,
    )
    assert result.ok
    assert "attic" in session.areas
    assert session.active_area_id == "attic"
    attic = session.areas["attic"]
    assert attic.bounds.width == 6
    assert attic.bounds.height == 4
    assert "dusty attic" in attic.area_description.lower()


def test_create_area_duplicate_rejected():
    session = Session.from_default()
    first = session.create_area("hall", description="A hall.")
    assert first.ok
    second = session.create_area("hall", description="Again.")
    assert not second.ok


def test_create_area_invalid_id():
    session = Session.from_default()
    result = session.create_area("Bad Id", description="Nope.")
    assert not result.ok


def test_edit_area_description():
    session = Session.from_default()
    session.create_area("cellar", description="Old text.")
    result = session.edit_area("cellar", description="Damp cellar.")
    assert result.ok
    assert session.areas["cellar"].area_description == "Damp cellar."


def test_edit_area_resize():
    session = Session.from_default()
    session.create_area("yard", width=3, height=3)
    result = session.edit_area("yard", width=5, height=5)
    assert result.ok
    assert session.areas["yard"].bounds.width == 5


def test_edit_area_resize_blocked_by_agent():
    session = Session.from_default()
    session.create_agent(
        name="Sentinel",
        position=(4, 4),
        personality="Stoic.",
    )
    result = session.edit_area("room", width=3, height=3)
    assert not result.ok
    assert "outside" in result.message.lower()


def test_delete_empty_area():
    session = Session.from_default()
    session.create_area("closet", description="Empty.")
    assert "closet" in session.areas
    result = session.delete_area("closet")
    assert result.ok
    assert "closet" not in session.areas


def test_delete_area_with_agents_rejected():
    session = Session.from_default()
    session.create_area("wing", description="Empty wing.")
    session.set_active_area("room")
    result = session.delete_area("room")
    assert not result.ok
    assert "agent" in result.message.lower()


def test_delete_last_area_rejected():
    session = Session.from_default()
    session.create_area("spare", description="Spare.")
    session.delete_area("spare")
    result = session.delete_area("room")
    assert not result.ok
    assert "last area" in result.message.lower()


def test_delete_active_area_switches_scope():
    session = Session.from_default()
    session.create_area("loft", description="Empty loft.")
    session.set_active_area("loft")
    result = session.delete_area("loft")
    assert result.ok
    assert session.active_area_id == "room"
