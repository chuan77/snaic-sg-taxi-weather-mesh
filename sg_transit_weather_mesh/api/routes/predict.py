import numpy as np
from fastapi import APIRouter, HTTPException
from ..schemas import DemandPredictRequest, DemandPredictResponse, ZonePrediction
from ..model_store import model_store

router = APIRouter(tags=["predict"])

LAG = 6


@router.post("/demand", response_model=DemandPredictResponse)
def predict_demand(request: DemandPredictRequest) -> DemandPredictResponse:
    """On-demand GBR inference. Accepts lag_counts for 1-6 zones, returns predicted count."""
    if not model_store.ready:
        raise HTTPException(
            status_code=503,
            detail=(
                "Demand model not available. Run the Dagster pipeline at least once "
                "to register a model in the MLflow registry."
            ),
        )

    model = model_store.demand_models["latest"]
    version = model_store.demand_models.get("_version", "unknown")

    predictions = []
    for zone in request.zones:
        X = np.array([zone.lag_counts], dtype=float)
        pred = max(0, int(round(float(model.predict(X)[0]))))
        predictions.append(ZonePrediction(
            zone_id=zone.zone_id,
            predicted_count=pred,
            model_version=str(version),
        ))

    return DemandPredictResponse(predictions=predictions)
