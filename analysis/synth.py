"""Synthetic cells with known truth, used only to test the analysis code."""
import numpy as np
import pandas as pd


def make_cells(n_pairs=30, n_ops=12, n_layouts=4, p_move=0.3, effect=0.08,
               layout_sigma=0.002, coupling=1.0, blind_share=0.0, seed=1):
    """
    coupling: silicon delta per unit of instruction delta.
    blind_share: share of moves that change cycles without changing instructions.
    """
    rng = np.random.default_rng(seed)
    rows = []
    for p in range(n_pairs):
        for o in range(n_ops):
            base = rng.uniform(100, 2000)
            cpi = rng.uniform(1.1, 2.0)
            moves = rng.random() < p_move
            size = rng.choice([-1, 1]) * effect * rng.uniform(0.5, 2.0) if moves else 0.0
            blind = moves and rng.random() < blind_share
            instr_delta = 0.0 if blind else size
            silicon_delta = size if blind else size * coupling
            for side, emu, sil in (("parent", 0.0, 0.0), ("child", instr_delta, silicon_delta)):
                for layout in range(n_layouts):
                    rows.append((f"P{p:02d}", side, layout * 4, "renode", f"op{o}",
                                 round(base * (1 + emu))))
                    noise = rng.normal(0, layout_sigma)
                    rows.append((f"P{p:02d}", side, layout * 4, "silicon", f"op{o}",
                                 base * cpi * (1 + sil) * (1 + noise)))
    return pd.DataFrame(rows, columns=["pair", "side", "layout", "platform", "op", "value"])
