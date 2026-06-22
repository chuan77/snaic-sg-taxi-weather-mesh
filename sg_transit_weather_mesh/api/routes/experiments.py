from fastapi import APIRouter, HTTPException, Query
from ..schemas import ExperimentRunItem
from ...utils import get_mlflow_config

router = APIRouter(tags=["experiments"])

_VALID_EXPERIMENTS = {"demand_forecast", "taxi_clusters"}


@router.get("/{name}/runs", response_model=list[ExperimentRunItem])
def get_experiment_runs(
    name: str,
    limit: int = Query(default=20, ge=1, le=100),
) -> list[ExperimentRunItem]:
    """Return recent MLflow runs. name must be 'demand_forecast' or 'taxi_clusters'."""
    if name not in _VALID_EXPERIMENTS:
        raise HTTPException(status_code=404, detail=f"Unknown experiment '{name}'")

    mlflow_cfg = get_mlflow_config()
    if mlflow_cfg is None:
        raise HTTPException(status_code=503, detail="MLflow disabled in config")

    try:
        import mlflow

        mlflow.set_tracking_uri(mlflow_cfg["tracking_uri"])
        exp_name = mlflow_cfg["experiments"][name]
        runs = mlflow.search_runs(
            experiment_names=[exp_name],
            max_results=limit,
            order_by=["start_time DESC"],
            output_format="list",
        )
        return [
            ExperimentRunItem(
                run_id=r.info.run_id,
                start_time=str(r.info.start_time),
                status=r.info.status,
                metrics={k: v for k, v in r.data.metrics.items()},
                params={k: v for k, v in r.data.params.items()},
                tags={
                    k: v
                    for k, v in r.data.tags.items()
                    if not k.startswith("mlflow.")
                },
            )
            for r in runs
        ]
    except Exception as exc:
        raise HTTPException(status_code=503, detail=f"MLflow unreachable: {exc}")
