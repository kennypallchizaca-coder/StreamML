"""Sondas HTTP autenticadas utilizadas por el conector local vinculado."""

from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, Query, Request, Response, status

from apps.api.dependencies import current_connector


router = APIRouter(prefix="/api/v1/network/probe", tags=["network-probe"])
MIN_PROBE_BYTES = 64 * 1024
MAX_PROBE_BYTES = 512 * 1024


@router.get("/latency")
def latency_probe(_connector: dict = Depends(current_connector)) -> Response:
    return Response(status_code=status.HTTP_204_NO_CONTENT, headers={"Cache-Control": "no-store"})


@router.get("/download")
def download_probe(
    size: int = Query(default=256 * 1024, ge=MIN_PROBE_BYTES, le=MAX_PROBE_BYTES),
    _connector: dict = Depends(current_connector),
) -> Response:
    # A deterministic payload avoids CPU-heavy generation on every request.
    # nginx does not enable response compression for this route.
    return Response(
        content=b"S" * size,
        media_type="application/octet-stream",
        headers={"Cache-Control": "no-store", "X-StreamML-Probe-Bytes": str(size)},
    )


@router.post("/upload")
async def upload_probe(request: Request, _connector: dict = Depends(current_connector)) -> dict:
    content_length = request.headers.get("content-length")
    if not content_length or not content_length.isdigit():
        raise HTTPException(status_code=411, detail="Content-Length es requerido.")
    declared = int(content_length)
    if not MIN_PROBE_BYTES <= declared <= MAX_PROBE_BYTES:
        raise HTTPException(status_code=413, detail="El tamaño del payload de prueba es inválido.")
    payload = await request.body()
    if len(payload) != declared:
        raise HTTPException(status_code=400, detail="El payload de prueba está incompleto.")
    return {"received_bytes": len(payload)}
