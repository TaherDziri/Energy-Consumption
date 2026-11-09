"""train_gru_24h.py
GRU 48 h -> 24 h (direct, multi-step). CPU, seed fixe.
Early stopping sur VAL uniquement. UNE seule evaluation finale sur TEST.
Sorties hors Git : models/gru_24h.pt, data/processed/dl/gru_test_preds.parquet,
                   data/processed/dl/gru_24h_metrics.csv
"""
import os
import random
from pathlib import Path

import numpy as np
import pandas as pd
import torch
import torch.nn as nn
from torch.utils.data import TensorDataset, DataLoader

SEED = 42
os.environ["PYTHONHASHSEED"] = str(SEED)
random.seed(SEED)
np.random.seed(SEED)
torch.manual_seed(SEED)
torch.use_deterministic_algorithms(True, warn_only=True)
torch.set_num_threads(4)

D = Path("data/processed/dl")
OUT_PRED = D / "gru_test_preds.parquet"
OUT_METRICS = D / "gru_24h_metrics.csv"
OUT_MODEL = Path("models/gru_24h.pt")

LOOKBACK, HORIZON = 48, 24
HIDDEN, LAYERS = 64, 1
BATCH, LR = 128, 1e-3
EPOCHS, PATIENCE = 40, 8

d = np.load(D / "windows_48to24.npz")
X = d["X"].astype("float32")            # (N, 48) z-score
Y = d["Y"].astype("float32")            # (N, 24) z-score
hid = d["LCLid"].astype(str)
split = d["split"].astype(str)
st = pd.read_csv(D / "scalers.csv").set_index("LCLid")
mu = np.array([st.loc[h, "mean"] for h in hid], dtype="float64")
sd = np.array([st.loc[h, "std"] for h in hid], dtype="float64")

X3 = torch.from_numpy(X[:, :, None])    # (N, 48, 1)
Yt = torch.from_numpy(Y)
tr = torch.from_numpy(split == "train")
va = torch.from_numpy(split == "val")

class GRU24(nn.Module):
    def __init__(self):
        super().__init__()
        self.gru = nn.GRU(1, HIDDEN, LAYERS, batch_first=True)
        self.head = nn.Linear(HIDDEN, HORIZON)

    def forward(self, x):
        out, _ = self.gru(x)
        return self.head(out[:, -1, :])

model = GRU24()
opt = torch.optim.Adam(model.parameters(), lr=LR)
lossf = nn.MSELoss()

g = torch.Generator().manual_seed(SEED)
dl_tr = DataLoader(TensorDataset(X3[tr], Yt[tr]), batch_size=BATCH,
                   shuffle=True, generator=g, num_workers=0)
dl_va = DataLoader(TensorDataset(X3[va], Yt[va]), batch_size=512,
                   shuffle=False, num_workers=0)
ds_tr, ds_va = TensorDataset(X3[tr], Yt[tr]), TensorDataset(X3[va], Yt[va])

best, best_state, bad, best_ep = float("inf"), None, 0, 0
for ep in range(1, EPOCHS + 1):
    model.train()
    tot = 0.0
    for xb, yb in dl_tr:
        opt.zero_grad()
        loss = lossf(model(xb), yb)
        loss.backward()
        opt.step()
        tot += loss.item() * len(xb)
    model.eval()
    with torch.no_grad():
        v = sum(lossf(model(xb), yb).item() * len(xb) for xb, yb in dl_va) / len(ds_va)
    print(f"epoch {ep:02d} | train {tot / len(ds_tr):.5f} | val {v:.5f}")
    if v < best - 1e-5:
        best, best_ep, bad = v, ep, 0
        best_state = {k: t.clone() for k, t in model.state_dict().items()}
    else:
        bad += 1
        if bad >= PATIENCE:
            print(f"early stopping a l'epoque {ep} (meilleure val {best:.5f}, ep {best_ep})")
            break

assert best_state is not None
model.load_state_dict(best_state)
model.eval()
print(f"\nmeilleur modele : epoque {best_ep} | val MSE {best:.5f}")

# Sauvegarde du modele tout de suite : un bug d'affichage ne doit pas le perdre.
OUT_MODEL.parent.mkdir(parents=True, exist_ok=True)
torch.save({"state_dict": model.state_dict(),
            "hparams": {"lookback": LOOKBACK, "horizon": HORIZON,
                        "hidden": HIDDEN, "layers": LAYERS,
                        "seed": SEED, "best_epoch": best_ep,
                        "best_val_mse": best}}, OUT_MODEL)
print("modele ecrit :", OUT_MODEL)

# ----- UNE seule lecture du test, apres restauration du meilleur modele -----
te = torch.from_numpy(split == "test")
idx_te = np.flatnonzero(split == "test")
with torch.no_grad():
    pred_te = model(X3[te]).numpy()     # z-score, (n_test, 24)

def metrics(pred_z, idx):
    y = Y[idx].astype("float64") * sd[idx][:, None] + mu[idx][:, None]
    p = np.asarray(pred_z, "float64") * sd[idx][:, None] + mu[idx][:, None]
    e = y - p
    return y, p, np.mean(np.abs(e), axis=0), np.sqrt(np.mean(e ** 2, axis=0))

y_g, p_g, mae_g, rmse_g = metrics(pred_te, idx_te)
sais_z = X[idx_te, 24:48]
y_s, p_s, mae_s, rmse_s = metrics(sais_z, idx_te)

tab = pd.DataFrame({
    "horizon_h": np.arange(1, HORIZON + 1),
    "MAE_GRU": mae_g, "MAE_saisonnier": mae_s,
    "RMSE_GRU": rmse_g, "RMSE_saisonnier": rmse_s,
})
print("\nTEST - comparaison par horizon (kWh reels) :")
print(tab.to_string(index=False, float_format=lambda v: f"{v:.4f}"))
print(f"\npoule GRU  : MAE {mae_g.mean():.4f} | RMSE {np.sqrt(np.mean(rmse_g ** 2)):.4f}")
print(f"poule sais : MAE {mae_s.mean():.4f} | RMSE {np.sqrt(np.mean(rmse_s ** 2)):.4f}")
print(f"GRU bat le saisonnier (MAE) : {bool(mae_g.mean() < mae_s.mean())}")

OUT_METRICS.parent.mkdir(parents=True, exist_ok=True)
tab.to_csv(OUT_METRICS, index=False)
pd.DataFrame({
    "LCLid": np.repeat(hid[idx_te], HORIZON),
    "target_hour": np.repeat(pd.to_datetime(d["target_hour"][idx_te]), HORIZON),
    "horizon_h": np.tile(np.arange(1, HORIZON + 1), len(idx_te)),
    "y_true_kwh": y_g.ravel(),
    "y_pred_kwh": p_g.ravel(),
    "y_seasonal_kwh": p_s.ravel(),
}).to_parquet(OUT_PRED, index=False)

print("\necrit :", OUT_PRED, "|", OUT_METRICS, "|", OUT_MODEL)