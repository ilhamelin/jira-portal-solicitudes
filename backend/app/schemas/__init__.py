"""Contratos de entrada y salida de la API."""

from .adjunto import AdjuntoResponse
from .comentario import ComentarioCreate, ComentarioResponse
from .webhook import JiraWebhookPayload

__all__ = ["AdjuntoResponse", "JiraWebhookPayload", "ComentarioCreate", "ComentarioResponse"]
