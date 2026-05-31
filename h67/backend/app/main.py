from fastapi import FastAPI, WebSocket, WebSocketDisconnect, HTTPException, BackgroundTasks
from fastapi.middleware.cors import CORSMiddleware
from contextlib import asynccontextmanager
from typing import List, Dict, Any
import asyncio

from .models import (
    SimulationParameters,
    SimulationStatus,
    SimulationControl,
    PIDParameters,
    PerturbationConfig,
    OptimizationConfig,
    OptimizationStatus,
    SimulationTimeSeries,
    SimulationConfig,
    NeuralSurrogateConfig,
    NeuralSurrogateStatus,
    MultichannelConfig,
    FaultDetectionStatus,
    ChannelResult
)
from .simulation_manager import SimulationManager
from .optimization import OptimizationEngine

simulation_manager = SimulationManager()
optimization_engine = OptimizationEngine(simulation_manager.droplet_model)


@asynccontextmanager
async def lifespan(app: FastAPI):
    yield
    simulation_manager.reset()
    optimization_engine.stop()


app = FastAPI(
    title="Two-Phase Flow Droplet Generation Simulator",
    version="2.0.0",
    lifespan=lifespan
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=False,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.get("/api/health")
async def health_check():
    return {"status": "ok"}


@app.get("/api/simulation/status")
async def get_simulation_status():
    return simulation_manager.get_status()


@app.post("/api/simulation/control")
async def control_simulation(control: SimulationControl):
    if control.action == "start":
        if simulation_manager.paused:
            simulation_manager.resume()
        else:
            simulation_manager.start()
    elif control.action == "pause":
        simulation_manager.pause()
    elif control.action == "reset":
        simulation_manager.reset()
    else:
        raise HTTPException(status_code=400, detail="Invalid action")
    return {"status": "success", "action": control.action}


@app.post("/api/simulation/parameters")
async def update_parameters(params: SimulationParameters):
    simulation_manager.update_parameters(params)
    return {"status": "success"}


@app.post("/api/simulation/config")
async def update_simulation_config(config: SimulationConfig):
    simulation_manager.update_simulation_config(config)
    return {"status": "success"}


@app.get("/api/simulation/time-series", response_model=SimulationTimeSeries)
async def get_time_series():
    return simulation_manager.get_time_series()


@app.post("/api/pid/parameters")
async def update_pid_parameters(params: PIDParameters):
    simulation_manager.update_pid_parameters(params)
    return {"status": "success"}


@app.post("/api/perturbation/config")
async def update_perturbation_config(config: PerturbationConfig):
    simulation_manager.update_perturbation_config(config)
    return {"status": "success"}


@app.get("/api/optimization/status", response_model=OptimizationStatus)
async def get_optimization_status():
    return optimization_engine.get_status()


@app.post("/api/optimization/start")
async def start_optimization(config: OptimizationConfig, background_tasks: BackgroundTasks):
    if optimization_engine.is_running():
        raise HTTPException(status_code=400, detail="Optimization already running")

    base_params = simulation_manager.parameters
    background_tasks.add_task(optimization_engine.run_optimization, config, base_params)
    return {"status": "optimization started"}


@app.post("/api/optimization/stop")
async def stop_optimization():
    optimization_engine.stop()
    return {"status": "optimization stopped"}


@app.post("/api/neural-surrogate/train")
async def train_neural_surrogate(config: NeuralSurrogateConfig, background_tasks: BackgroundTasks):
    result = simulation_manager.train_neural_surrogate(config)
    if "error" in result:
        raise HTTPException(status_code=400, detail=result["error"])
    return result


@app.get("/api/neural-surrogate/status", response_model=NeuralSurrogateStatus)
async def get_neural_surrogate_status():
    return simulation_manager.get_neural_surrogate_status()


@app.post("/api/multichannel/config")
async def update_multichannel_config(config: MultichannelConfig):
    sim_config = simulation_manager.simulation_config
    sim_config.multichannel = config
    simulation_manager.update_simulation_config(sim_config)
    return {"status": "success"}


@app.post("/api/multichannel/channel/{channel_id}/blocked")
async def set_channel_blocked(channel_id: int, blocked: bool = True, severity: float = 0.5):
    if not (0 <= channel_id < 16):
        raise HTTPException(status_code=400, detail="Invalid channel ID")
    simulation_manager.set_channel_blocked(channel_id, blocked, severity)
    return {"status": "success", "channel_id": channel_id, "blocked": blocked, "severity": severity}


@app.post("/api/multichannel/channel/{channel_id}/enabled")
async def set_channel_enabled(channel_id: int, enabled: bool = True):
    if not (0 <= channel_id < 16):
        raise HTTPException(status_code=400, detail="Invalid channel ID")
    simulation_manager.set_channel_enabled(channel_id, enabled)
    return {"status": "success", "channel_id": channel_id, "enabled": enabled}


@app.get("/api/fault-detection/status")
async def get_fault_detection_status():
    status = simulation_manager.get_status()
    if 'faultDetection' in status:
        return status['faultDetection']
    return {"enabled": False, "overallStatus": "normal", "channelStatuses": [], "anomalies": [], "recommendations": []}


@app.get("/api/multichannel/results")
async def get_multichannel_results():
    mc_status = simulation_manager.get_multichannel_status()
    if mc_status is None:
        return {"results": [], "summary": {}}
    return {
        "results": [r.model_dump() for r in mc_status.lastResults],
        "summary": mc_status.summaryStats
    }


@app.post("/api/simulation/single-step")
async def single_step_simulation(params: SimulationParameters):
    D, f, Q_ratio, Ca_c = simulation_manager.droplet_model.simulate_step(
        params=params,
        add_noise=False
    )
    return {
        "dropletSize": D,
        "generationFrequency": f,
        "flowRateRatio": Q_ratio,
        "capillaryNumber": Ca_c
    }


@app.post("/api/neural-surrogate/predict")
async def neural_surrogate_predict(params: SimulationParameters):
    status = simulation_manager.get_neural_surrogate_status()
    if not status.trained:
        raise HTTPException(status_code=400, detail="Neural surrogate not trained")

    try:
        D, f = simulation_manager._neural_surrogate.predict(params)
        return {
            "dropletSize": D,
            "generationFrequency": f,
            "model": "neural_surrogate"
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.websocket("/ws/simulation")
async def websocket_simulation(websocket: WebSocket):
    await websocket.accept()
    simulation_manager.add_websocket_client(websocket)

    try:
        initial_status = simulation_manager.get_status()
        await websocket.send_json({
            "type": "simulation_data",
            "data": initial_status
        })

        while True:
            data = await websocket.receive_text()
            if data == "ping":
                await websocket.send_json({"type": "pong"})

            if optimization_engine.is_running():
                opt_status = optimization_engine.get_status()
                await websocket.send_json({
                    "type": "optimization_update",
                    "data": opt_status.model_dump()
                })

            await asyncio.sleep(0.5)

    except WebSocketDisconnect:
        simulation_manager.remove_websocket_client(websocket)
    except Exception as e:
        print(f"WebSocket error: {e}")
        simulation_manager.remove_websocket_client(websocket)
