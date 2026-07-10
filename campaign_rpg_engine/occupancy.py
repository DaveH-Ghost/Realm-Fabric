"""
occupancy.py

V0.6.0a — grid occupancy and movement blocking.
V0.6.0d — multi-tile object footprints.
"""

from __future__ import annotations

from campaign_rpg_engine.agent import Agent
from campaign_rpg_engine.area import Area
from campaign_rpg_engine.object import Object, object_footprint_tiles, object_occupies_tile

NEIGHBOR_DELTAS: tuple[tuple[int, int], ...] = (
    (-1, -1),
    (0, -1),
    (1, -1),
    (-1, 0),
    (1, 0),
    (-1, 1),
    (0, 1),
    (1, 1),
)


def _entity_blocks_for_mover(
    entity: Agent | Object,
    mover_id: str,
) -> bool:
    if not entity.blocks_movement:
        return False
    if mover_id in entity.movement_exceptions:
        return False
    return True


def entity_blocks_for_mover(
    entity: Agent | Object,
    mover_id: str,
) -> bool:
    return _entity_blocks_for_mover(entity, mover_id)


def agents_at(area: Area, position: tuple[int, int]) -> list[Agent]:
    return [agent for agent in area.agents if agent.position == position]


def objects_at(area: Area, position: tuple[int, int]) -> list[Object]:
    x, y = position
    return [obj for obj in area.get_objects() if object_occupies_tile(obj, x, y)]


def footprint_tiles_for_entity(
    area: Area,
    entity_id: str,
) -> frozenset[tuple[int, int]]:
    """Return footprint tiles for an entity id (full object footprint or agent tile)."""
    obj = area.get_object_by_id(entity_id)
    if obj is not None:
        return frozenset(object_footprint_tiles(obj))
    agent = area.get_agent_by_id(entity_id)
    if agent is not None:
        return frozenset({agent.position})
    return frozenset()


def is_tile_enterable(
    area: Area,
    position: tuple[int, int],
    mover_id: str,
) -> bool:
    """Return True if *mover_id* may stand on *position*."""
    if not area.is_valid_position(position):
        return False
    for obj in objects_at(area, position):
        if _entity_blocks_for_mover(obj, mover_id):
            return False
    for agent in agents_at(area, position):
        if agent.id == mover_id:
            continue
        if _entity_blocks_for_mover(agent, mover_id):
            return False
    return True


def resolve_standable_goal(
    area: Area,
    goal: tuple[int, int],
    mover_id: str,
) -> tuple[int, int] | None:
    """
    Return a standable tile for movement.

    If *goal* is enterable, return it. Otherwise BFS outward for the nearest
    enterable tile by step count.
    """
    if not area.is_valid_position(goal):
        return None
    if is_tile_enterable(area, goal, mover_id):
        return goal

    from collections import deque

    queue: deque[tuple[int, int]] = deque([goal])
    seen = {goal}

    while queue:
        current = queue.popleft()
        for dx, dy in NEIGHBOR_DELTAS:
            neighbor = (current[0] + dx, current[1] + dy)
            if neighbor in seen or not area.is_valid_position(neighbor):
                continue
            seen.add(neighbor)
            if is_tile_enterable(area, neighbor, mover_id):
                return neighbor
            queue.append(neighbor)

    return None


def _blocker_name_at(
    area: Area,
    position: tuple[int, int],
    mover_id: str,
) -> str | None:
    for obj in objects_at(area, position):
        if _entity_blocks_for_mover(obj, mover_id):
            return obj.name
    for agent in agents_at(area, position):
        if agent.id == mover_id:
            continue
        if _entity_blocks_for_mover(agent, mover_id):
            return agent.name
    return None


def _goal_ignored(
    goal_pos: tuple[int, int],
    ignore_tiles: frozenset[tuple[int, int]] | None,
) -> bool:
    return ignore_tiles is not None and goal_pos in ignore_tiles


def _frontier_blocker(
    area: Area,
    from_pos: tuple[int, int],
    goal_pos: tuple[int, int],
    mover_id: str,
    ignore_tiles: frozenset[tuple[int, int]] | None,
) -> str | None:
    """Return a blocker on the BFS frontier when *from_pos* cannot reach *goal_pos*."""
    from collections import deque

    queue: deque[tuple[int, int]] = deque([from_pos])
    reachable = {from_pos}
    best_name: str | None = None
    best_dist = 10**9

    while queue:
        current = queue.popleft()
        for dx, dy in NEIGHBOR_DELTAS:
            neighbor = (current[0] + dx, current[1] + dy)
            if not area.is_valid_position(neighbor) or neighbor in reachable:
                continue
            if not is_tile_enterable(area, neighbor, mover_id):
                if ignore_tiles is not None and neighbor in ignore_tiles:
                    continue
                dist = max(
                    abs(neighbor[0] - goal_pos[0]),
                    abs(neighbor[1] - goal_pos[1]),
                )
                name = _blocker_name_at(area, neighbor, mover_id)
                if name is not None and dist < best_dist:
                    best_dist = dist
                    best_name = name
                continue
            reachable.add(neighbor)
            queue.append(neighbor)

    return best_name


def find_blocker_between(
    area: Area,
    from_pos: tuple[int, int],
    goal_pos: tuple[int, int],
    mover_id: str,
    *,
    ignore_tiles: frozenset[tuple[int, int]] | None = None,
) -> str | None:
    """
    Return the display name of a blocking entity between *from_pos* and *goal_pos*.

    Prefers the goal tile when it cannot be entered, then the next step toward
    the goal, then the blocked neighbor closest to the goal.

    *ignore_tiles* skips blockers on those tiles (e.g. the entity being moved toward).
    """
    from campaign_rpg_engine.pathing import path_step_towards

    if (
        not _goal_ignored(goal_pos, ignore_tiles)
        and not is_tile_enterable(area, goal_pos, mover_id)
    ):
        name = _blocker_name_at(area, goal_pos, mover_id)
        if name is not None:
            return name

    next_pos = path_step_towards(from_pos, goal_pos)
    if next_pos != from_pos:
        name = _blocker_name_at(area, next_pos, mover_id)
        if name is not None:
            return name

    standable = resolve_standable_goal(area, goal_pos, mover_id)
    if standable is not None:
        from campaign_rpg_engine.pathfinding import find_path

        if not find_path(from_pos, standable, area, mover_id):
            name = _frontier_blocker(
                area,
                from_pos,
                goal_pos,
                mover_id,
                ignore_tiles,
            )
            if name is not None:
                return name

    best_pos: tuple[int, int] | None = None
    best_dist = 10**9
    for dx, dy in NEIGHBOR_DELTAS:
        neighbor = (from_pos[0] + dx, from_pos[1] + dy)
        if not area.is_valid_position(neighbor):
            continue
        if is_tile_enterable(area, neighbor, mover_id):
            continue
        dist = max(abs(neighbor[0] - goal_pos[0]), abs(neighbor[1] - goal_pos[1]))
        if dist < best_dist:
            best_dist = dist
            best_pos = neighbor
    if best_pos is not None:
        return _blocker_name_at(area, best_pos, mover_id)
    return None
