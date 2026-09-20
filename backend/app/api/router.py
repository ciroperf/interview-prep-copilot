"""Assembla tutte le rotte sotto il prefisso /api."""

from __future__ import annotations

from fastapi import APIRouter

from .routes import cv, health, jobs, knowledge, plans, problems, quizzes

api_router = APIRouter(prefix="/api")
api_router.include_router(health.router)
api_router.include_router(knowledge.router)
api_router.include_router(jobs.router)
api_router.include_router(plans.router)
api_router.include_router(quizzes.router)
api_router.include_router(problems.router)
api_router.include_router(cv.router)
