"""Analytics engine (BUS 751, Assignment 6): fixed-effects estimation of the A3 research question.

Reads the A4 database through the A5 loader and estimates

    log(Y_oit) = alpha_oi + delta_it + beta * (Exposure_o x Post_t) + e_oit

with occupation-clustered inference suited to ~19 clusters, simpler comparison specifications, an
event study, a robustness suite, and known-answer validation against the synthetic generator.

Typical use (see ``notebooks/03_model.ipynb``)::

    from oews_eda import data
    from oews_model import analysis, inference
    d = analysis.model_frame(data.load_panel())
    res = analysis.run_spec(d, analysis.specifications()[2])     # A3 main model
    res.table                                                    # coef, CR1 SE, t(G-1) p and CI
    inference.wild_cluster_bootstrap(res)                        # small-cluster p-value and CI

Modules
-------
estimate    fixed-effect absorption, OLS, CR1 cluster-robust inference, ModelError
inference   wild cluster restricted bootstrap (Webb weights), randomization inference
analysis    model frame, specification suite, event study, leave-one-out, finance contrast
validation  known-answer recovery and Monte Carlo calibration on the synthetic generator
plots       fig12-fig14
report      one-call runner (``uv run oews-model``) that writes every artifact and a run log
"""
__version__ = "0.6.0"
