# Edit mutation stack

Three layers mutate the world. Prefer typed `Session` methods in product code.

```mermaid
flowchart LR
  subgraph studio [Studio]
    UI["GM UI / forms"]
    Cmd["command_dispatch string CLI"]
  end
  subgraph engine [Engine]
    SessionAPI["Session.create_edit_delete"]
    WorldAPI["edit.world_edit_api"]
    AreaEdit["edit.area_edit"]
    Appliers["edit.field_appliers"]
  end
  UI --> SessionAPI
  Cmd --> AreaEdit
  SessionAPI --> WorldAPI
  SessionAPI --> AreaEdit
  WorldAPI --> Appliers
  AreaEdit --> Appliers
```

| Path | When to use |
|------|-------------|
| `Session.create_*` / `edit_*` / `delete_*` | Apps and Studio typed HTTP APIs |
| `edit.world_edit_api` | Shared typed helpers behind Session |
| `edit.area_edit` + `area_edit_parse` | String field tokens; Studio `POST /api/command` |
| `edit.field_appliers` | Internal shared field application (not public API) |

Studio owns stepper-style command strings in `backend/command_dispatch.py`. Engine does not ship a CLI.
