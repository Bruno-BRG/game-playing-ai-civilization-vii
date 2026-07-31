/*
 * AIRI Civilization VII bridge.
 *
 * The add-on never accepts arbitrary game API calls. It publishes a current list of action IDs,
 * then revalidates the selected action through Civ VII's own operation API before execution.
 */
(() => {
  "use strict";

  const config = globalThis.AiriCiv7BridgeConfig;
  if (!config?.endpoint || !config?.token) {
    console.error("[AIRI Civ VII] Missing bridge configuration; reinstall the add-on.");
    return;
  }

  let requestInFlight = false;
  let observationSequence = 0;
  let currentObservationId = null;
  let currentActions = new Map();

  function isSinglePlayerGame() {
    const gameConfiguration = Configuration.getGame();
    return !UI.isMultiplayer() && !gameConfiguration.isNetworkMultiplayer && !gameConfiguration.isHotseat;
  }

  function localize(value) {
    if (typeof value !== "string") return null;
    try {
      return Locale.compose(value);
    } catch {
      return value;
    }
  }

  function componentId(value) {
    if (!value) return null;
    if (typeof value === "string" || typeof value === "number") return String(value);
    const owner = value.owner ?? "unknown";
    const type = value.type ?? "unknown";
    const id = value.id ?? value.index ?? "unknown";
    return `${owner}:${type}:${id}`;
  }

  function locationOf(value) {
    const location = value?.location;
    if (!location || typeof location.x !== "number" || typeof location.y !== "number") return null;
    return { x: location.x, y: location.y };
  }

  function collectYields(yieldApi) {
    const result = {};
    const yieldTypes = {
      gold: YieldTypes.YIELD_GOLD,
      science: YieldTypes.YIELD_SCIENCE,
      culture: YieldTypes.YIELD_CULTURE,
      happiness: YieldTypes.YIELD_HAPPINESS,
      diplomacy: YieldTypes.YIELD_DIPLOMACY,
      food: YieldTypes.YIELD_FOOD,
      production: YieldTypes.YIELD_PRODUCTION,
    };
    for (const [name, yieldType] of Object.entries(yieldTypes)) {
      try {
        const value = yieldApi?.getNetYield(yieldType);
        if (typeof value === "number" && Number.isFinite(value)) result[name] = value;
      } catch {
        // A player-level yield API does not necessarily expose city-only yield types.
      }
    }
    return result;
  }

  function collectCities(player) {
    return (player.Cities?.getCities() ?? []).map((city) => ({
      id: componentId(city.id),
      name: localize(city.name) ?? String(city.name ?? "Unknown city"),
      location: locationOf(city),
      population: city.population ?? null,
      is_town: city.isTown ?? null,
      food_stored: city.Growth?.currentFood ?? null,
      yields: collectYields(city.Yields),
    }));
  }

  function collectUnits(player) {
    return (player.Units?.getUnits() ?? []).map((unit) => {
      const definition = GameInfo.Units?.lookup(unit.type);
      return {
        id: componentId(unit.id),
        type: definition?.UnitType ?? unit.type ?? null,
        name: localize(definition?.Name) ?? definition?.UnitType ?? String(unit.type ?? "Unknown unit"),
        location: locationOf(unit),
        can_move: unit.canMove ?? null,
        has_moved: unit.hasMoved ?? null,
        moves_remaining: unit.Movement?.movementMovesRemaining ?? null,
        max_moves: unit.Movement?.maxMoves ?? null,
      };
    });
  }

  function collectResearch(player, actions) {
    const techs = player.Techs;
    if (!techs) return null;
    const available = [];
    for (const nodeType of techs.getAllAvailableNodeTypes?.() ?? []) {
      const definition = GameInfo.ProgressionTreeNodes.lookup(nodeType);
      const args = { ProgressionTreeNodeType: nodeType };
      const canStart = Game.PlayerOperations.canStart(
        GameContext.localPlayerID,
        PlayerOperationTypes.SET_TECH_TREE_NODE,
        args,
        false,
      );
      const node = {
        node_type: nodeType,
        name: localize(definition?.Name) ?? String(definition?.ProgressionTreeNodeType ?? nodeType),
        cost: techs.getNodeCost?.(nodeType) ?? null,
        turns: techs.getTurnsForNode?.(nodeType) ?? null,
        legal: canStart?.Success === true,
      };
      available.push(node);
      if (node.legal) {
        const actionId = `set_tech:${nodeType}`;
        actions.set(actionId, {
          id: actionId,
          kind: "set_tech",
          description: `Research ${node.name}`,
          nodeType,
        });
      }
    }
    return {
      tree_type: techs.getTreeType?.() ?? null,
      target_node: techs.getTargetNode?.() ?? null,
      available,
    };
  }

  function collectVisibleTiles(cities, units) {
    const plotIndices = new Set();
    for (const entity of [...cities, ...units]) {
      if (!entity.location) continue;
      for (const index of GameplayMap.getPlotIndicesInRadius(entity.location.x, entity.location.y, 2)) {
        plotIndices.add(index);
      }
    }
    const tiles = [];
    for (const index of plotIndices) {
      const location = GameplayMap.getLocationFromIndex(index);
      if (!location) continue;
      const revealed = GameplayMap.getRevealedState(
        GameContext.localPlayerID,
        location.x,
        location.y,
      );
      // Only the currently visible state is exported. Revealed-but-fogged plots can otherwise
      // leak live ownership or resource changes that the player has not observed yet.
      if (revealed !== RevealedStates.VISIBLE) continue;
      tiles.push({
        index,
        x: location.x,
        y: location.y,
        revealed_state: revealed,
        terrain_type: GameplayMap.getTerrainType(location.x, location.y),
        biome_type: GameplayMap.getBiomeType(location.x, location.y),
        feature_type: GameplayMap.getFeatureType(location.x, location.y),
        resource_type: GameplayMap.getResourceType(location.x, location.y),
        owner: GameplayMap.getOwner(location.x, location.y),
        yields: GameplayMap.getYields(index, GameContext.localPlayerID),
      });
    }
    return tiles;
  }

  function buildObservation() {
    if (!UI.isInGame() || !isSinglePlayerGame()) return null;
    const player = Players.get(GameContext.localPlayerID);
    if (!player) return null;

    const actions = new Map();
    actions.set("wait", { id: "wait", kind: "wait", description: "Wait for the game state to change" });
    const research = collectResearch(player, actions);
    if (player.isTurnActive) {
      actions.set("next_action", {
        id: "next_action",
        kind: "next_action",
        description: "Use Civilization VII's native next-action/end-turn resolver",
      });
    }
    const cities = collectCities(player);
    const units = collectUnits(player);
    const observationId = `${Game.turn ?? "unknown"}:${++observationSequence}`;
    currentObservationId = observationId;
    currentActions = actions;
    return {
      protocol_version: 1,
      observation_id: observationId,
      captured_at: new Date().toISOString(),
      game: {
        turn: Game.turn ?? null,
        age: Game.age ?? null,
        local_player_id: GameContext.localPlayerID,
        is_multiplayer: false,
      },
      player: {
        id: player.id,
        name: localize(player.name) ?? String(player.name ?? "Local player"),
        civilization_type: player.civilizationType ?? null,
        is_turn_active: player.isTurnActive === true,
        yields: collectYields(player.Stats),
      },
      cities,
      units,
      research,
      visible_tiles: collectVisibleTiles(cities, units),
      legal_actions: [...actions.values()].map(({ nodeType: _nodeType, ...action }) => action),
    };
  }

  function executeDecision(decision) {
    if (!decision?.execute || decision.observation_id !== currentObservationId) return;
    const action = currentActions.get(decision.action_id);
    if (!action || action.id === "wait") return;
    if (!isSinglePlayerGame() || !UI.isInGame()) return;
    const player = Players.get(GameContext.localPlayerID);
    if (!player?.isTurnActive) return;

    if (action.kind === "next_action") {
      window.dispatchEvent(new CustomEvent("hotkey-next-action"));
      return;
    }
    if (action.kind === "set_tech") {
      const args = { ProgressionTreeNodeType: action.nodeType };
      const canStart = Game.PlayerOperations.canStart(
        GameContext.localPlayerID,
        PlayerOperationTypes.SET_TECH_TREE_NODE,
        args,
        false,
      );
      if (canStart?.Success) {
        Game.PlayerOperations.sendRequest(
          GameContext.localPlayerID,
          PlayerOperationTypes.SET_TECH_TREE_NODE,
          args,
        );
      }
    }
  }

  async function poll() {
    if (requestInFlight) return;
    let observation;
    try {
      observation = buildObservation();
    } catch (error) {
      console.error("[AIRI Civ VII] Could not build observation", error);
      return;
    }
    if (!observation) return;

    requestInFlight = true;
    try {
      const response = await fetch(config.endpoint, {
        method: "POST",
        headers: {
          "Content-Type": "application/json",
          "X-AIRI-Bridge-Token": config.token,
        },
        body: JSON.stringify(observation),
      });
      if (!response.ok) {
        console.warn(`[AIRI Civ VII] Companion returned HTTP ${response.status}`);
        return;
      }
      const decision = await response.json();
      console.info(`[AIRI Civ VII] ${decision.action_id}: ${decision.reason}`);
      executeDecision(decision);
    } catch (error) {
      console.warn("[AIRI Civ VII] Companion is unavailable", error);
    } finally {
      requestInFlight = false;
    }
  }

  console.info("[AIRI Civ VII] Structured single-player bridge loaded.");
  setInterval(poll, Math.max(1000, config.pollIntervalMs ?? 5000));
  setTimeout(poll, 1500);
})();
