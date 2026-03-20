        # EVE Frontier Utopia Extraction

        ## Source

        - SharedCache: `/Users/ocrand/Library/Application Support/EVE Frontier/SharedCache`
        - Build root: `/Users/ocrand/Library/Application Support/EVE Frontier/SharedCache/utopia/EVE.app/Contents/Resources/build`
        - Output root: `/Users/ocrand/Documents/New project/eve_skills/output/eve_frontier_utopia`
        - Code extract mode: `full`
        - Selected code entries: 10419
        - Extracted code entries: 10414

        ## Module Categories

        - `building`: 115
- `legacy_ui`: 1259
- `navigation`: 38
- `other`: 7787
- `proto_interfaces`: 881
- `space_hud`: 243
- `station`: 61
- `world_objects`: 35

        ## Static Data

        - Celestials: 261219 across 24026 solar systems
        - NPC stations: 98 across 98 solar systems

        ## Planet Resources

        - Found: True
        - Pickle type: dict
        - Keys: ['depletionStdDevMax', 'depletionTemplates', 'depletionStdDevStepSize', 'depletionStdDevMin']

        ## Interactable Module Groups

        ## station_flow

Count: 61

- `frontier/station/__init__.pyc`
- `frontier/station/common/__init__.pyc`
- `frontier/station/common/inventory/__init__.pyc`
- `frontier/station/common/inventory/platform.pyc`
- `frontier/station/common/undock.pyc`
- `frontier/station_hud/__init__.pyc`
- `frontier/station_hud/base.pyc`
- `frontier/station_hud/color.pyc`
- `frontier/station_hud/fuel.pyc`
- `frontier/station_hud/health.pyc`
- ... and 51 more
## assembly_and_building

Count: 115

- `frontier/base_building/__init__.pyc`
- `frontier/base_building/client/__init__.pyc`
- `frontier/base_building/client/build/__init__.pyc`
- `frontier/base_building/client/build/browse_mode/__init__.pyc`
- `frontier/base_building/client/build/browse_mode/build_card.pyc`
- `frontier/base_building/client/build/browse_mode/selection_container.pyc`
- `frontier/base_building/client/build/browse_mode/view_mode.pyc`
- `frontier/base_building/client/build/camera.pyc`
- `frontier/base_building/client/build/command.pyc`
- `frontier/base_building/client/build/constants.pyc`
- ... and 105 more
## gates_and_travel

Count: 18

- `frontier/crdata/common/objects/cr_stargate.pyc`
- `frontier/jump_drive/__init__.pyc`
- `frontier/jump_drive/client/__init__.pyc`
- `frontier/jump_drive/client/jump_drive.pyc`
- `frontier/jump_drive/client/map_filter.pyc`
- `frontier/jump_drive/client/service.pyc`
- `frontier/jump_drive/common/__init__.pyc`
- `frontier/jump_drive/common/const.pyc`
- `frontier/jump_drive/common/jump_drive_fuel_cost.pyc`
- `frontier/warping/__init__.pyc`
- ... and 8 more
## scanning_and_sites

Count: 37

- `frontier/signatures_and_scanning/__init__.pyc`
- `frontier/signatures_and_scanning/client/__init__.pyc`
- `frontier/signatures_and_scanning/client/insider.pyc`
- `frontier/signatures_and_scanning/client/lasso.pyc`
- `frontier/signatures_and_scanning/client/repository.pyc`
- `frontier/signatures_and_scanning/client/scanning_service.pyc`
- `frontier/signatures_and_scanning/common/__init__.pyc`
- `frontier/signatures_and_scanning/common/scanning.pyc`
- `frontier/signatures_and_scanning/common/signature.pyc`
- `eveProto/generated/eve/character/hacking/__init__.pyc`
- ... and 27 more
## operations_and_objectives

Count: 25

- `frontier/keeper/__init__.pyc`
- `frontier/keeper/client/__init__.pyc`
- `frontier/keeper/client/controller.pyc`
- `frontier/keeper/client/demo.pyc`
- `frontier/keeper/client/face.pyc`
- `frontier/keeper/client/guidance.pyc`
- `frontier/keeper/client/insider.pyc`
- `frontier/keeper/client/keeper_container.pyc`
- `frontier/keeper/client/layer.pyc`
- `frontier/keeper/client/link.pyc`
- ... and 15 more
## planetary_and_resources

Count: 22

- `eveProto/generated/eve/planet/__init__.pyc`
- `eveProto/generated/eve/planet/pin_pb2.pyc`
- `eveProto/generated/eve/planet/pin_type_pb2.pyc`
- `eveProto/generated/eve/planet/planet_pb2.pyc`
- `eveProto/generated/eve/planet/planet_type_pb2.pyc`
- `eveProto/generated/eve/planetinteraction/__init__.pyc`
- `eveProto/generated/eve/planetinteraction/collector/__init__.pyc`
- `eveProto/generated/eve/planetinteraction/collector/collector_pb2.pyc`
- `eveProto/generated/eve/planetinteraction/colony/__init__.pyc`
- `eveProto/generated/eve/planetinteraction/colony/colony_pb2.pyc`
- ... and 12 more
## legacy_structure_ui

Count: 75

- `eve/client/script/ui/structure/__init__.pyc`
- `eve/client/script/ui/structure/accessGroups/__init__.pyc`
- `eve/client/script/ui/structure/accessGroups/accesGroupsWnd.pyc`
- `eve/client/script/ui/structure/accessGroups/accessGroupEntry.pyc`
- `eve/client/script/ui/structure/accessGroups/accessGroupListCont.pyc`
- `eve/client/script/ui/structure/accessGroups/accessGroupMemberCont.pyc`
- `eve/client/script/ui/structure/accessGroups/accessGroupsController.pyc`
- `eve/client/script/ui/structure/accessGroups/accessMemberEntry.pyc`
- `eve/client/script/ui/structure/accessGroups/addCont.pyc`
- `eve/client/script/ui/structure/accessGroups/auditLogCont.pyc`
- ... and 65 more

        ## Notes

        - `mapObjects.db` gives static IDs and positions, not resolved names for every group/type.
        - `code.ccp` is the most useful code source and contains 3.12 `.pyc` modules.
        - `eveProto/generated/eve/...` can be reflected into JSON schemas with `python3.12` and `protobuf==3.20.x`.
        - Full source decompilation is optional; `marshal + dis` is enough for a first-pass interface inventory.
