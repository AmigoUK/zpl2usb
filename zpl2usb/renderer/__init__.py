"""Lokalny renderer ZPL -> obraz rastrowy."""

from .interpreter import RenderResult, render

__all__ = ["render", "RenderResult"]
