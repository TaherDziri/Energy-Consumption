"""check_h1.py - saisonnier h=1 sur les fenetres communes one-step / 24 h.

Sert a distinguer un vrai bug d'un simple changement de test set :
le saisonnier h=1 (y(t-24) -> y(t)) est identique dans les deux jeux.
delta ~ 0  -> pipeline correct, l'ecart a 0.2021 vient du jeu de fenetres.
delta != 0 -> bug (echelle, jointure ou split).
"""
import numpy as np
import pandas as pd

D = "data/processed/dl"
a = np.load(D + "/windows_48to24.npz")
b = np.load(D + "/windows_48to1.npz")
s = pd.read_csv(D + "/scalers.csv").set_index("LCLid")


def frame(h, tgt, y, p, sp):
    h = np.asarray(h, dtype=str)
    mu = np.array([s.loc[x, "mean"] for x in h], dtype="float64")
    sd = np.array([s.loc[x, "std"] for x in h], dtype="float64")
    return pd.DataFrame({
        "LCLid": h,
        "target_hour": pd.to_datetime(tgt),
        "y": np.asarray(y, "float64") * sd + mu,
        "p": np.asarray(p, "float64") * sd + mu,
        "split": np.asarray(sp, dtype=str),
    })


f24 = frame(a["LCLid"], a["target_hour"], a["Y"][:, 0], a["X"][:, 24], a["split"])
f1 = frame(b["LCLid"], b["target_hour"], b["y"], b["X"][:, 24], b["split"])
m = f1.merge(
    f24[["LCLid", "target_hour", "y", "p"]],
    on=["LCLid", "target_hour"],
    suffixes=("_1", "_24"),
)
m = m[m["split"] == "test"]

print("fenetres communes :", len(m))
print("MAE one-step  h=1 :", round(float(np.mean(np.abs(m.y_1 - m.p_1))), 4))
print("MAE 24h       h=1 :", round(float(np.mean(np.abs(m.y_24 - m.p_24))), 4))
print(
    "delta             :",
    round(float(np.mean(np.abs(m.y_24 - m.p_24)) - np.mean(np.abs(m.y_1 - m.p_1))), 6),
)
t24 = f24[f24.split == "test"]
print("MAE 24h h=1 (toutes fenetres test) :", round(float(np.mean(np.abs(t24.y - t24.p))), 4))
