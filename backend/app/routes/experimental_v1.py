from fastapi import APIRouter, HTTPException

from ..schemas_experimental_v1 import (
    ExperimentalV1Request,
    ExperimentalV1Response,
)
from ..services.experimental_v1_service import predict_experimental_v1


router = APIRouter(
    prefix="/api/experimental/v1",
    tags=["Experimental V1"],
)


@router.post("/predict", response_model=ExperimentalV1Response)
def experimental_v1_predict(
    payload: ExperimentalV1Request,
):
    try:
        return predict_experimental_v1(payload.model_dump())

    except FileNotFoundError:
        raise HTTPException(
            status_code=503,
            detail="Experimental V1 model is unavailable.",
        )

    except ValueError:
        raise HTTPException(
            status_code=422,
            detail="Invalid experimental prediction input.",
        )