from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session

from app.core.security import require_operational_api_key
from app.core.settings import settings
from app.db.session import get_db
from app.models.evaluation_result import EvaluationResult
from app.models.generated_output import GeneratedOutput
from app.schemas.generate import GenerateRequest, GenerateResponse, GeneratedOutputOut, UpdateStatusRequest
from app.services.generator import generate_output

router = APIRouter(tags=["generate"], dependencies=[Depends(require_operational_api_key)])


@router.post("/generate", response_model=GenerateResponse)
def generate(payload: GenerateRequest, db: Session = Depends(get_db)) -> GenerateResponse:
    try:
        output = generate_output(db, payload.post_id, payload.output_type, evaluator_model=settings.anthropic_model)
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc

    eval_result = (
        db.query(EvaluationResult)
        .filter(EvaluationResult.output_id == output.id)
        .order_by(EvaluationResult.evaluated_at.desc())
        .first()
    )

    return GenerateResponse(
        output_id=output.id,
        type=payload.output_type,
        title=output.title,
        content=output.content,
        generated_at=output.generated_at,
        evaluation_score=eval_result.score if eval_result else None,
    )


@router.get("/outputs", response_model=list[GeneratedOutputOut])
def list_outputs(
    skip: int = Query(default=0, ge=0),
    limit: int | None = Query(default=None, ge=1, le=500),
    db: Session = Depends(get_db),
) -> list[GeneratedOutputOut]:
    query = db.query(GeneratedOutput).order_by(GeneratedOutput.generated_at.desc()).offset(skip)
    if limit is not None:
        query = query.limit(limit)

    rows = query.all()
    return [GeneratedOutputOut.model_validate(row) for row in rows]


@router.patch("/outputs/{output_id}/status", response_model=GeneratedOutputOut)
def update_output_status(output_id: str, payload: UpdateStatusRequest, db: Session = Depends(get_db)) -> GeneratedOutputOut:
    output = db.query(GeneratedOutput).filter(GeneratedOutput.id == output_id).first()
    if not output:
        raise HTTPException(status_code=404, detail="Output not found")

    output.status = payload.status
    db.commit()
    db.refresh(output)
    return GeneratedOutputOut.model_validate(output)


@router.delete("/outputs/{output_id}")
def delete_output(output_id: str, db: Session = Depends(get_db)) -> dict[str, object]:
    output = db.query(GeneratedOutput).filter(GeneratedOutput.id == output_id).first()
    if not output:
        raise HTTPException(status_code=404, detail="Output not found")

    deleted_evaluations = (
        db.query(EvaluationResult)
        .filter(EvaluationResult.output_id == output_id)
        .delete(synchronize_session=False)
    )
    db.delete(output)
    db.commit()

    return {
        "deleted": True,
        "output_id": output_id,
        "deleted_evaluations": deleted_evaluations,
    }
