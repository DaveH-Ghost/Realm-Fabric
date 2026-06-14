"""Session-level area CRUD commands (V0.4.0c2+)."""

from src.session import Session


def test_create_area_command():
    session = Session.from_default()
    result = session.run_command(
        'create-area id attic desc "A dusty attic." width 6 height 4'
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
    first = session.run_command('create-area id hall desc "A hall."')
    assert first.ok
    second = session.run_command('create-area id hall desc "Again."')
    assert not second.ok


def test_create_area_invalid_id():
    session = Session.from_default()
    result = session.run_command('create-area id "Bad Id" desc "Nope."')
    assert not result.ok


def test_edit_area_description():
    session = Session.from_default()
    session.run_command('create-area id cellar desc "Old text."')
    result = session.run_command('edit-area cellar desc "Damp cellar."')
    assert result.ok
    assert session.areas["cellar"].area_description == "Damp cellar."


def test_edit_area_resize():
    session = Session.from_default()
    session.run_command('create-area id yard width 3 height 3')
    result = session.run_command("edit-area yard width 5 height 5")
    assert result.ok
    assert session.areas["yard"].bounds.width == 5


def test_edit_area_resize_blocked_by_agent():
    session = Session.from_default()
    session.run_command(
        'create-agent name "Sentinel" personality "Stoic." at 4,4'
    )
    result = session.run_command("edit-area room width 3 height 3")
    assert not result.ok
    assert "outside" in result.message.lower()


def test_delete_empty_area():
    session = Session.from_default()
    session.run_command('create-area id closet desc "Empty."')
    assert "closet" in session.areas
    result = session.run_command("delete-area closet")
    assert result.ok
    assert "closet" not in session.areas


def test_delete_area_with_agents_rejected():
    session = Session.from_default()
    session.run_command('create-area id wing desc "Empty wing."')
    session.set_active_area("room")
    result = session.run_command("delete-area room")
    assert not result.ok
    assert "agent" in result.message.lower()


def test_delete_last_area_rejected():
    session = Session.from_default()
    session.run_command('create-area id spare desc "Spare."')
    session.run_command("delete-area spare")
    result = session.run_command("delete-area room")
    assert not result.ok
    assert "last area" in result.message.lower()


def test_delete_active_area_switches_scope():
    session = Session.from_default()
    session.run_command('create-area id loft desc "Empty loft."')
    session.set_active_area("loft")
    result = session.run_command("delete-area loft")
    assert result.ok
    assert session.active_area_id == "room"
