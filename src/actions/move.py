"""

move.py



Coordinate and entity-id move for V0.2 / V0.4.0a–b.



V0.4.0a: ``move_target`` may be ``x,y`` or ``agent_*`` / ``obj_*``.

V0.4.0b: when ``agent.move_speed`` is set, walk up to N steps (5e pathing).

"""



from src.action_outcome import ActionOutcome

from src.agent import Agent

from src.coordinates import format_coordinate

from src.move_target import (

    MoveTargetError,

    entity_goal_blocks_movement,

    format_already_at_message,

    format_move_arrival_message,

    format_move_arrival_passive,

    format_move_towards_message,

    format_move_towards_passive,

    format_unreachable_message,

    resolve_move_target,

)

from src.occupancy import find_blocker_between, is_tile_enterable, resolve_standable_goal

from src.pathfinding import find_path, walk_with_pathfinding

from src.area import Area





def move(agent: Agent, area: Area, target: str) -> ActionOutcome:

    """Move the agent toward a coordinate or entity-id target tile."""

    try:

        resolved = resolve_move_target(area, target)

    except MoveTargetError as exc:

        return ActionOutcome(

            result=f"This action wasn't recognized, {exc}",

        )



    goal = resolved.position

    goal_label = format_coordinate(*goal)

    goal_blocks = entity_goal_blocks_movement(area, resolved, agent.id)

    ignore_blockers_at = goal if resolved.entity_id else None



    if not area.is_valid_position(goal):

        return ActionOutcome(

            result=(

                "This action wasn't recognized, ERR:INVALID_COORDINATES, "

                f"{goal_label} is outside the room."

            ),

        )



    standable_goal = resolve_standable_goal(area, goal, agent.id)

    if standable_goal is None:

        blocker = find_blocker_between(

            area,

            agent.position,

            goal,

            agent.id,

            ignore_blockers_at=ignore_blockers_at,

        )

        return ActionOutcome(

            result=format_unreachable_message(resolved, goal_label, blocker),

        )



    if agent.position == standable_goal:

        return ActionOutcome(

            result=format_already_at_message(

                resolved,

                agent.position,

                standable_goal,

                goal_blocks_movement=goal_blocks,

            ),

        )



    if agent.move_speed is None:

        if not is_tile_enterable(area, standable_goal, agent.id):

            blocker = find_blocker_between(

                area,

                agent.position,

                goal,

                agent.id,

                ignore_blockers_at=ignore_blockers_at,

            )

            return ActionOutcome(

                result=format_unreachable_message(resolved, goal_label, blocker),

            )

        agent.position = standable_goal

        return ActionOutcome(

            result=format_move_arrival_message(

                resolved,

                agent.position,

                goal_blocks_movement=goal_blocks,

            ),

            passive_result=format_move_arrival_passive(

                agent.name,

                resolved,

                agent.position,

                goal_blocks_movement=goal_blocks,

            ),

        )



    if not find_path(agent.position, standable_goal, area, agent.id):

        blocker = find_blocker_between(

            area,

            agent.position,

            goal,

            agent.id,

            ignore_blockers_at=ignore_blockers_at,

        )

        return ActionOutcome(

            result=format_unreachable_message(resolved, goal_label, blocker),

        )



    final_pos, reached, _path = walk_with_pathfinding(

        agent.position, standable_goal, agent.move_speed, area, agent.id

    )

    if not area.is_valid_position(final_pos):

        return ActionOutcome(

            result=(

                "This action wasn't recognized, ERR:INVALID_COORDINATES, "

                f"{format_coordinate(*final_pos)} is outside the room."

            ),

        )



    agent.position = final_pos



    if reached:

        return ActionOutcome(

            result=format_move_arrival_message(

                resolved,

                agent.position,

                goal_blocks_movement=goal_blocks,

            ),

            passive_result=format_move_arrival_passive(

                agent.name,

                resolved,

                agent.position,

                goal_blocks_movement=goal_blocks,

            ),

        )



    no_path_remaining = not find_path(final_pos, standable_goal, area, agent.id)

    blocker = (

        find_blocker_between(

            area,

            final_pos,

            goal,

            agent.id,

            ignore_blockers_at=ignore_blockers_at,

        )

        if no_path_remaining and resolved.entity_id

        else None

    )

    return ActionOutcome(

        result=format_move_towards_message(

            resolved,

            final_pos,

            blocker_name=blocker,

        ),

        passive_result=format_move_towards_passive(

            agent.name,

            resolved,

            final_pos,

        ),

    )

