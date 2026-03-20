# EVE Frontier Utopia Interactable Inventory

## Scope

- Output root: `/Users/ocrand/Documents/New project/eve_skills/output/eve_frontier_utopia`
- Analysis root: `/Users/ocrand/Documents/New project/eve_skills/output/eve_frontier_utopia/analysis`
- Pyc modules analyzed: `7`
- Pb2 modules exported: `19` / `19`

## Static World Evidence

- Celestials: `261219` across `24026` solar systems.
- NPC stations: `98` across `98` solar systems.
- Dominant raw celestial groups:
  - `groupID 8`: `147060` objects. Likely moons.
  - `groupID 7`: `83257` objects. Likely planets.
  - `groupID 6`: `24026` objects. Likely sun objects (one per solar system in this dump).
  - `groupID 10`: `6876` objects. Likely stargates / travel nodes.

## Planet Resource Data

- Found: `True`
- Pickle type: `dict`
- Keys: `['depletionStdDevMax', 'depletionTemplates', 'depletionStdDevStepSize', 'depletionStdDevMin']`

## Interaction Families

### assembly_and_building

- Summary: Player-built structures, smart assemblies, hangars, cargo windows, and construction-site flows.
- Module count: `115`
- Key modules:
  - `frontier/smart_assemblies/client/window/cargo.pyc`
  - `frontier/base_building/client/construction_site/ui/window.pyc`
  - `frontier/smart_assemblies/client/window/controller.pyc`
  - `frontier/base_building/client/construction_site/ui/item_slot_controller.pyc`
  - `frontier/smart_assemblies/client/gate/operation.pyc`
  - `frontier/smart_assemblies/client/storage/controller.pyc`
  - `frontier/smart_assemblies/client/window/container.pyc`
  - `frontier/smart_assemblies/client/window/industry_container.pyc`
  - `frontier/smart_assemblies/client/storage/container.pyc`
  - `frontier/base_building/client/build/service.pyc`
- Symbol highlights:
  - `frontier/smart_assemblies/client/window/cargo.pyc` -> `CargoContainer`, `CargoContainer.__init__`, `CargoContainer.Close`, `CargoContainer._construct_main_content`, `CargoContainer._stack_all`, `CargoContainer._select_inventory`, `CargoContainer._load_inventory`, `CargoContainer._relevant_filter`
  - `frontier/base_building/client/construction_site/ui/window.pyc` -> `open_assembly_construction`, `AssemblyConstructionWindow`, `AssemblyConstructionWindow.__init__`, `AssemblyConstructionWindow.ApplyAttributes`, `AssemblyConstructionWindow._get_nearby_inventories`, `AssemblyConstructionWindow.Close`, `AssemblyConstructionWindow._delayed_close`, `AssemblyConstructionWindow.GetMenuMoreOptions`
- Confirmed pb2 interfaces: none in the current exported set.

### gates_and_travel

- Summary: Stargates, gate linking/unlinking, jump-drive flows, and travel-related client services.
- Module count: `18`
- Key modules:
  - `frontier/jump_drive/client/service.pyc`
  - `frontier/jump_drive/client/jump_drive.pyc`
  - `frontier/crdata/common/objects/cr_stargate.pyc`
  - `frontier/jump_drive/common/const.pyc`
  - `frontier/jump_drive/client/map_filter.pyc`
  - `eveProto/generated/eve/assembly/gate/gate_pb2.pyc`
  - `frontier/jump_drive/common/jump_drive_fuel_cost.pyc`
  - `eveProto/generated/eve/assembly/gate/api/events_pb2.pyc`
  - `eveProto/generated/eve/assembly/gate/api/requests_pb2.pyc`
  - `frontier/warping/common/warp_functions.pyc`
- Symbol highlights:
  - `frontier/jump_drive/client/service.pyc` -> `JumpService`, `JumpService.Run`, `JumpService.Run.<lambda>`
  - `frontier/jump_drive/client/jump_drive.pyc` -> `try_jump_jumpdrive`, `_get_jump_drive_manager`
  - `frontier/crdata/common/objects/cr_stargate.pyc` -> `CRWarpgate`, `CRWarpgate.__init__`, `CRWarpgate.gateActivationRange`, `CRWarpgate.dunKeyTypeID`, `CRWarpgate.dunKeyQuantity`, `CRWarpgate.dunOpenUntil`, `CRWarpgate.dunSpawnID`, `CRWarpgate.dunToGateID`
- Confirmed pb2 interfaces:
  - `eve/assembly/gate/api/events.proto` (eve.assembly.gate.api) -> `Created`, `Linked`, `Unlinked`, `Jumped` [`analysis/pb2/eveProto/generated/eve/assembly/gate/api/events_pb2.json`]
  - `eve/assembly/gate/api/requests.proto` (eve.assembly.gate.api) -> `CreateRequest`, `CreateResponse`, `GetRequest`, `GetResponse`, `PrepareOnlineTransactionRequest`, `PrepareOnlineTransactionResponse`, `PrepareOfflineTransactionRequest`, `PrepareOfflineTransactionResponse`, `PrepareLinkGateTransactionRequest`, `PrepareLinkGateTransactionResponse`, `PrepareUnlinkGateTransactionRequest`, `PrepareUnlinkGateTransactionResponse`, `PrepareJumpTransactionRequest`, `PrepareJumpTransactionResponse`, `DeleteRequest`, `DeleteResponse` [`analysis/pb2/eveProto/generated/eve/assembly/gate/api/requests_pb2.json`]
  - `eve/assembly/gate/gate.proto` (eve.assembly.gate) -> `Identifier`, `Attributes` [`analysis/pb2/eveProto/generated/eve/assembly/gate/gate_pb2.json`]

### legacy_structure_ui

- Summary: Legacy structure browser, deployment, access groups, and structure-side UI entry points carried into Frontier.
- Module count: `75`
- Key modules:
  - `eve/client/script/ui/structure/deployment/stargateSystemEntry.pyc`
  - `eve/client/script/ui/structure/deployment/stargateDeploymentCont.pyc`
  - `eve/client/script/ui/structure/structureSettings/serviceListCont.pyc`
  - `eve/client/script/ui/structure/structureSettings/controllers/settingController.pyc`
  - `eve/client/script/ui/structure/structureBrowser/controllers/filterContController.pyc`
  - `eve/client/script/ui/structure/structureBrowser/controllers/reinforceTimersBundle.pyc`
  - `eve/client/script/ui/structure/structureSettings/controllers/allProfilesController.pyc`
  - `eve/client/script/ui/structure/structureSettings/controllers/slimProfileController.pyc`
  - `eve/client/script/ui/structure/structureBrowser/controllers/structureEntryController.pyc`
  - `eve/client/script/ui/structure/structureBrowser/controllers/structureBrowserController.pyc`
- Symbol highlights: no targeted Python 3.12 metadata export for this family yet.
- Confirmed pb2 interfaces: none in the current exported set.

### operations_and_objectives

- Summary: Keeper/objective flows plus explicit character operation lifecycle events and requests.
- Module count: `25`
- Key modules:
  - `frontier/keeper/client/service.pyc`
  - `frontier/keeper/client/controller.pyc`
  - `frontier/keeper/client/menu/controllers.pyc`
  - `eveProto/generated/eve/operation/category_pb2.pyc`
  - `eveProto/generated/eve/operation/operation_pb2.pyc`
  - `eveProto/generated/eve/character/operation/operation_pb2.pyc`
  - `frontier/keeper/client/menu/container.pyc`
  - `frontier/keeper/client/keeper_container.pyc`
  - `frontier/keeper/client/link.pyc`
  - `frontier/keeper/color.pyc`
- Symbol highlights: no targeted Python 3.12 metadata export for this family yet.
- Confirmed pb2 interfaces:
  - `eve/character/operation/operation.proto` (eve.character.operation) -> `Started`, `Completed`, `Stopped`, `StartRequest`, `StartResponse` [`analysis/pb2/eveProto/generated/eve/character/operation/operation_pb2.json`]

### planetary_and_resources

- Summary: Planets, pins, colonies, collectors, links, routes, factories, storage, and planet-resource data.
- Module count: `22`
- Key modules:
  - `eveProto/generated/eve/planetinteraction/colony/colony_pb2.pyc`
  - `eveProto/generated/eve/planetinteraction/factory/factory_pb2.pyc`
  - `eveProto/generated/eve/planetinteraction/storage/storage_pb2.pyc`
  - `eveProto/generated/eve/planetinteraction/collector/collector_pb2.pyc`
  - `eveProto/generated/eve/planet/pin_pb2.pyc`
  - `eveProto/generated/eve/planet/pin_type_pb2.pyc`
  - `eveProto/generated/eve/planetinteraction/pin/pin_pb2.pyc`
  - `eveProto/generated/eve/planetinteraction/link/link_pb2.pyc`
  - `eveProto/generated/eve/planetinteraction/route/route_pb2.pyc`
  - `eveProto/generated/eve/planet/planet_pb2.pyc`
- Symbol highlights: no targeted Python 3.12 metadata export for this family yet.
- Confirmed pb2 interfaces:
  - `eve/planet/pin.proto` (eve.planet.pin) -> `Identifier`, `Attributes` [`analysis/pb2/eveProto/generated/eve/planet/pin_pb2.json`]
  - `eve/planet/planet.proto` (eve.planet) -> `Identifier`, `Attributes`, `Planet`, `GetRequest`, `GetResponse`, `GetPlanetsInSolarSystemRequest`, `GetPlanetsInSolarSystemResponse` [`analysis/pb2/eveProto/generated/eve/planet/planet_pb2.json`]
  - `eve/planetinteraction/collector/collector.proto` (eve.planetinteraction.collector) -> `Identifier`, `Attributes`, `Started`, `Stopped`, `Offlined`, `GetRequest`, `GetResponse` [`analysis/pb2/eveProto/generated/eve/planetinteraction/collector/collector_pb2.json`]
  - `eve/planetinteraction/colony/colony.proto` (eve.planetinteraction.colony) -> `Pin`, `Route`, `Link`, `Identifier`, `Attributes` [`analysis/pb2/eveProto/generated/eve/planetinteraction/colony/colony_pb2.json`]
  - `eve/planetinteraction/factory/factory.proto` (eve.planetinteraction.factory) -> `Identifier`, `Attributes`, `Started`, `Offlined`, `GetRequest`, `GetResponse` [`analysis/pb2/eveProto/generated/eve/planetinteraction/factory/factory_pb2.json`]
  - `eve/planetinteraction/link/link.proto` (eve.planetinteraction.link) -> `Identifier`, `Attributes`, `Link` [`analysis/pb2/eveProto/generated/eve/planetinteraction/link/link_pb2.json`]
  - `eve/planetinteraction/pin/pin.proto` (eve.planetinteraction.pin) -> `Identifier`, `Type`, `ExtractorDetails`, `Attributes`, `Pin` [`analysis/pb2/eveProto/generated/eve/planetinteraction/pin/pin_pb2.json`]
  - `eve/planetinteraction/route/route.proto` (eve.planetinteraction.route) -> `Identifier`, `Attributes`, `Route` [`analysis/pb2/eveProto/generated/eve/planetinteraction/route/route_pb2.json`]
  - `eve/planetinteraction/schematic/schematic.proto` (eve.planetinteraction.schematic) -> `Identifier`, `Attributes`, `GetRequest`, `GetResponse` [`analysis/pb2/eveProto/generated/eve/planetinteraction/schematic/schematic_pb2.json`]
  - `eve/planetinteraction/storage/storage.proto` (eve.planetinteraction.storage) -> `Identifier`, `Attributes`, `Started`, `CapacityReached`, `GetRequest`, `GetResponse` [`analysis/pb2/eveProto/generated/eve/planetinteraction/storage/storage_pb2.json`]

### scanning_and_sites

- Summary: Signature scanning, hacking containers, and deadspace site interactions such as data and relic sites.
- Module count: `37`
- Key modules:
  - `frontier/signatures_and_scanning/client/scanning_service.pyc`
  - `frontier/signatures_and_scanning/client/lasso.pyc`
  - `frontier/signatures_and_scanning/client/insider.pyc`
  - `frontier/signatures_and_scanning/common/scanning.pyc`
  - `frontier/signatures_and_scanning/common/signature.pyc`
  - `frontier/signatures_and_scanning/client/repository.pyc`
  - `eveProto/generated/eve/character/hacking/container_pb2.pyc`
  - `eveProto/generated/eve/dungeon/dungeon_pb2.pyc`
  - `eveProto/generated/eve/dungeon/instance_pb2.pyc`
  - `eveProto/generated/eve/deadspace/archetype_pb2.pyc`
- Symbol highlights:
  - `frontier/signatures_and_scanning/client/scanning_service.pyc` -> `ScanningService`, `ScanningService.__init__`, `ScanningService.Run`, `ScanningService.remote_service`, `ScanningService.get_signature_repository`, `ScanningService.OnScanResults`, `ScanningService.OnPassiveScanResults`, `ScanningService.OnPassiveScannerFailure`
- Confirmed pb2 interfaces:
  - `eve/character/hacking/container.proto` (eve.character.hacking.container) -> `Succeeded` [`analysis/pb2/eveProto/generated/eve/character/hacking/container_pb2.json`]
  - `eve/deadspace/datasite/data_site.proto` (eve.deadspace.datasite) -> `Identifier`, `Attributes` [`analysis/pb2/eveProto/generated/eve/deadspace/datasite/data_site_pb2.json`]
  - `eve/deadspace/datasite/event.proto` (eve.deadspace.datasite.event) -> `CharacterCompleted` [`analysis/pb2/eveProto/generated/eve/deadspace/datasite/event_pb2.json`]
  - `eve/deadspace/relicsite/event.proto` (eve.deadspace.relicsite.event) -> `CharacterCompleted` [`analysis/pb2/eveProto/generated/eve/deadspace/relicsite/event_pb2.json`]
  - `eve/deadspace/relicsite/relic_site.proto` (eve.deadspace.relicsite) -> `Identifier`, `Attributes` [`analysis/pb2/eveProto/generated/eve/deadspace/relicsite/relic_site_pb2.json`]

### station_flow

- Summary: Station HUD, docking/undocking, and station-side inventory or session transitions inferred from client modules.
- Module count: `61`
- Key modules:
  - `frontier/station_hud/undock/controller.pyc`
  - `frontier/station_hud/service.pyc`
  - `frontier/station_hud/ship_selection/controller.pyc`
  - `frontier/station_hud/undock/widget.pyc`
  - `frontier/station_hud/undock/integration.pyc`
  - `frontier/station/common/undock.pyc`
  - `eve/client/script/ui/station/undockQuestions.pyc`
  - `frontier/station_hud/base.pyc`
  - `frontier/station_hud/fuel.pyc`
  - `frontier/station_hud/color.pyc`
- Symbol highlights:
  - `frontier/station_hud/undock/controller.pyc` -> `UndockProgress`, `UndockController`, `UndockController.__init__`, `UndockController.progress`, `UndockController.undock`, `UndockController.abort`
- Confirmed pb2 interfaces: none in the current exported set.

## Notes

- Static world counts come from mapObjects.db and confirm where coordinates/IDs exist in the client cache.
- Module families come from local client code and indicate interaction surfaces even when no pb2 schema is exported yet.
- pb2 interfaces are confirmed from Python 3.12 imports against the extracted code, with a minimal uthread2 stub during analysis.
- Raw celestial group IDs still need full Frontier static-data name resolution before treating them as final labels.
