"""
Simulation API Router
Controls chaos engineering and failure simulations across microservices.
"""

from fastapi import APIRouter, HTTPException, Query, Body
from typing import Dict, Any, Optional
from backend.models import SimulationScenarioToggle, SimulationStateResponse
from backend.sentinel.simulation_engine import simulation_engine

router = APIRouter(prefix="/api/simulation", tags=["Chaos & Failure Simulation Lab"])

@router.post("/start")
async def start_scenario(toggle: SimulationScenarioToggle):
    """Activate a controlled failure simulation scenario."""
    try:
        params = {}
        if toggle.intensity_or_delay_ms:
            params["delay_ms"] = toggle.intensity_or_delay_ms
        if toggle.target_service:
            params["target_service"] = toggle.target_service

        result = simulation_engine.start_scenario(toggle.scenario, params)
        return result
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@router.post("/stop")
async def stop_scenario(scenario: str = Query(...)):
    """Deactivate a running simulation scenario."""
    return simulation_engine.stop_scenario(scenario)

@router.post("/stop-all")
async def stop_all_scenarios():
    """Immediately stop and clear all active failure simulations."""
    simulation_engine.stop_all()
    return {"status": "SUCCESS", "message": "All failure simulations halted."}

@router.get("/status")
async def get_simulation_status():
    """Return all active failure scenarios with elapsed runtimes."""
    return simulation_engine.get_state()
