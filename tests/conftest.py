"""Shared pytest setup: render Matplotlib figures off-screen on every OS (Windows defaults to Tk)."""
import matplotlib

matplotlib.use("Agg")
