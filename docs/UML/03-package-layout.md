# Package layout (1.6.0)

After regrouping edit and template modules. Public imports stay on `campaign_rpg_engine` (`__all__`) and top-level **compat shims** (e.g. `campaign_rpg_engine.area_edit`).

```mermaid
flowchart TB
  subgraph root [campaign_rpg_engine]
    Session["session.py facade"]
    Sim["simulation.py"]
    Prompt["prompt_blocks.py"]
    Persist["session_persistence.py"]
  end
  subgraph editPkg [edit]
    AreaEdit["area_edit"]
    WorldEdit["world_edit_api"]
    Appliers["field_appliers"]
    Deco["decoration_edit"]
    SessionArea["session_area_edit"]
    Parse["area_edit_parse"]
  end
  subgraph templatesPkg [templates]
    EntityT["entity_templates"]
    AreaT["area_templates"]
    InteractT["interact_templates"]
  end
  subgraph other [Existing packages]
    LLM["llm/"]
    Mem["memory_modules/"]
    Act["actions/"]
    Handlers["interaction_handlers/"]
  end
  Session --> editPkg
  Session --> templatesPkg
  Session --> Sim
  WorldEdit --> Appliers
  AreaEdit --> Appliers
  EntityT --> WorldEdit
```

**Left large on purpose:** `session.py` (~1.2k) remains the public facade; splitting method surface is out of scope for 1.6.0.

**Shims:** top-level `area_edit.py`, `world_edit_api.py`, `entity_templates.py`, etc. alias to the real modules via `sys.modules` so Studio/plugins keep old import paths.
