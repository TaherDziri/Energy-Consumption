"""autoencoder_day.py
Autoencodeur jour-foyer 24 h -> 24 h. CPU, seed fixe.
Normal = jours train. Seuil = P95 des erreurs VAL (kWh/jour).
  --stage train : entraine + calibre le seuil, n'ouvre JAMAIS le test
  --stage test  : UNE seule lecture test, journalisee dans test_seen.json
Sorties hors Git : models/ae_day.pt, data/processed/dl/ae_day_*
"""
import argparse
import hashlib
import json
import os
import random
import subprocess
from datetime import datetime, timezone
from pathlib import Path

import numpy as np
import pandas as pd
import torch
import torch.nn as nn
from torch.utils.data import DataLoader, TensorDataset

SEED = 42
os.environ["PYTHONHASHSEED"] = str(SEED)
random.seed(SEED)
np.random.seed(SEED)
torch.manual_seed(SEED)
torch.use_deterministic_algorithms(True, warn_only=True)
torch.set_num_threads(4)

D = Path("data/processed/dl")
MODEL = Path("models/ae_day.pt")
LEDGER = D / "test_seen.json"
PERCENTILE = 95          # pre-enregistre : ~5 % d'alertes sur jours normaux VAL
H1, H2 = 16, 8
BATCH, LR = 64, 1e-3
EPOCHS, PATIENCE = 200, 20


def parse_args():
    p = argparse.ArgumentParser()
    p.add_argument("--stage", choices=["train", "test"], default="train")
    p.add_argument("--tag", default="ae_day_v1")
    p.add_argument("--i-know", action="store_true")
    return p.parse_args()


ARGS = parse_args()


def load_days():
    """24 valeurs horaires par (foyer, jour civil GMT)."""
    h = pd.read_parquet(D / "sample_hourly.parquet")
    h["period_start"] = h["hour_end"] - pd.Timedelta(hours=1)
    h["day"] = h["period_start"].dt.floor("D")
    h["hod"] = h["period_start"].dt.hour
    assert not h.duplicated(["LCLid", "period_start"]).any(), "heure en double"

    piv = h.pivot_table(index=["LCLid", "day"], columns="hod",
                        values="kwh", aggfunc="first").reindex(columns=range(24))
    info = h.groupby(["LCLid", "day"])["split"].agg(["nunique", "first"])

    Y = piv.to_numpy(dtype="float64")
    keep = (~np.isnan(Y).any(axis=1)) & \
           (info["nunique"].reindex(piv.index).to_numpy() == 1)

    meta = piv.index.to_frame(index=False)[keep].reset_index(drop=True)
    meta["split"] = info["first"].reindex(piv.index).to_numpy()[keep]
    Y = Y[keep]

    st = pd.read_csv(D / "scalers.csv").set_index("LCLid")
    mu = np.array([st.loc[x, "mean"] for x in meta["LCLid"]], dtype="float64")
    sd = np.array([st.loc[x, "std"] for x in meta["LCLid"]], dtype="float64")
    return Y, meta, mu, sd


class AE(nn.Module):
    def __init__(self, nin=24):
        super().__init__()
        self.enc = nn.Sequential(nn.Linear(nin, H1), nn.ReLU(),
                                 nn.Linear(H1, H2), nn.ReLU())
        self.dec = nn.Sequential(nn.Linear(H2, H1), nn.ReLU(),
                                 nn.Linear(H1, nin))

    def forward(self, x):
        return self.dec(self.enc(x))


def predict_z(model, Z, idx):
    """Z : matrice complete (ou variante complete) ; idx : indices globaux."""
    model.eval()
    with torch.no_grad():
        return model(torch.from_numpy(Z[idx].astype("float32"))).numpy()


def err_kwh(pred_z, Y, mu, sd, idx):
    """Erreur de reconstruction par jour, en kWh reels. Y/mu/sd complets."""
    p = pred_z.astype("float64") * sd[idx][:, None] + mu[idx][:, None]
    return np.abs(Y[idx] - p).mean(axis=1)


def anomalie(Y, mu, sd, idx):
    """Trois anomalies SYNTHETIQUES, en kWh (re-standardisees ensuite)."""
    y = Y[idx]
    return {
        "scale_x1.5": y * 1.5,
        "zeros_kwh": np.zeros_like(y),
        "shift_peak_+6h": np.roll(y, 6, axis=1),
    }


def score_variante(model, yk, mu_k, sd_k, thr):
    """Score une variante DEJA selectionnee : pas d'index global ici."""
    zk = ((yk - mu_k[:, None]) / sd_k[:, None]).astype("float32")
    p = predict_z(model, zk, np.arange(len(yk))) * sd_k[:, None] + mu_k[:, None]
    e = np.abs(yk - p).mean(axis=1)
    return e, float((e > thr).mean())


Y, meta, mu, sd = load_days()
Z = ((Y - mu[:, None]) / sd[:, None]).astype("float32")
split = meta["split"].to_numpy()
tr = np.flatnonzero(split == "train")
va = np.flatnonzero(split == "val")
te = np.flatnonzero(split == "test")
print(f"jours utilisables : train {len(tr)} | val {len(va)} | test {len(te)}")

if ARGS.stage == "train":
    g = torch.Generator().manual_seed(SEED)
    ds_tr = TensorDataset(torch.from_numpy(Z[tr]), torch.from_numpy(Z[tr]))
    dl_tr = DataLoader(ds_tr, batch_size=BATCH, shuffle=True,
                       generator=g, num_workers=0)
    Zva = torch.from_numpy(Z[va])

    model = AE()
    opt = torch.optim.Adam(model.parameters(), lr=LR)
    lossf = nn.MSELoss()
    best, best_state, best_ep, bad = float("inf"), None, 0, 0

    for ep in range(1, EPOCHS + 1):
        model.train()
        tot = 0.0
        for xb, _ in dl_tr:
            opt.zero_grad()
            loss = lossf(model(xb), xb)
            loss.backward()
            opt.step()
            tot += loss.item() * len(xb)
        model.eval()
        with torch.no_grad():
            v = lossf(model(Zva), Zva).item()
        if ep % 10 == 0 or ep == 1:
            print(f"epoch {ep:03d} | train {tot / len(ds_tr):.5f} | val {v:.5f}")
        if v < best - 1e-6:
            best, best_ep, bad = v, ep, 0
            best_state = {k: t.clone() for k, t in model.state_dict().items()}
        else:
            bad += 1
            if bad >= PATIENCE:
                print(f"early stopping a l'epoque {ep} (meilleur val {best:.5f}, ep {best_ep})")
                break

    assert best_state is not None
    model.load_state_dict(best_state)
    model.eval()

    e_va = err_kwh(predict_z(model, Z, va), Y, mu, sd, va)
    thr = float(np.percentile(e_va, PERCENTILE))
    print(f"\nmeilleur modele : epoque {best_ep} | val MSE(z) {best:.5f}")
    print(f"erreur VAL kWh/jour : P50 {np.percentile(e_va, 50):.4f} | "
          f"P90 {np.percentile(e_va, 90):.4f} | P95 {thr:.4f} | max {e_va.max():.4f}")
    print(f"seuil retenu = P{PERCENTILE} des erreurs VAL = {thr:.4f} kWh/jour")

    # Sauvegarde AVANT tout affichage : un bug d'affichage ne doit pas perdre le modele.
    MODEL.parent.mkdir(parents=True, exist_ok=True)
    torch.save({"state_dict": model.state_dict(),
                "hparams": {"nin": 24, "h1": H1, "h2": H2, "seed": SEED,
                            "percentile": PERCENTILE, "threshold_kwh": thr,
                            "best_epoch": best_ep, "best_val_mse": best,
                            "n_train": len(tr), "n_val": len(va)}}, MODEL)
    print("\nmodele ecrit :", MODEL)

    pd.DataFrame({"LCLid": meta["LCLid"].to_numpy()[va],
                  "day": meta["day"].to_numpy()[va],
                  "err_kwh": e_va, "alarm": e_va > thr}).to_csv(
        D / "ae_day_val_errors.csv", index=False)

    print("\nSynthetiques sur VAL (calibration, pas une evaluation) :")
    for k, yk in anomalie(Y, mu, sd, va).items():
        _, r = score_variante(model, yk, mu[va], sd[va], thr)
        print(f"  {k:16s} detectes {r * 100:5.1f} %")

    print("\necrit :", D / "ae_day_val_errors.csv")
    print("TEST non lu par cette etape.")

else:
    ck = torch.load(MODEL, map_location="cpu", weights_only=False)
    h = ck["hparams"]
    model = AE(h["nin"])
    model.load_state_dict(ck["state_dict"])
    model.eval()
    thr = float(h["threshold_kwh"])

    entries = json.loads(LEDGER.read_text(encoding="utf-8")) if LEDGER.exists() else []
    if any(e.get("model") == "autoencoder_day" for e in entries) and not ARGS.i_know:
        print(json.dumps([e for e in entries if e.get("model") == "autoencoder_day"], indent=2))
        raise SystemExit("STOP: test deja lu pour cet autoencodeur. --i-know pour un 2e regard assume.")

    e_te = err_kwh(predict_z(model, Z, te), Y, mu, sd, te)
    print(f"\nseuil VAL P{h['percentile']} = {thr:.4f} kWh/jour")
    print(f"TEST reel ({len(te)} jours, sans label) : "
          f"P50 {np.percentile(e_te, 50):.4f} | P90 {np.percentile(e_te, 90):.4f} | "
          f"P95 {np.percentile(e_te, 95):.4f} | P99 {np.percentile(e_te, 99):.4f} | "
          f"max {e_te.max():.4f}")
    print(f"taux d'alerte sur test NON modifie : {(e_te > thr).mean() * 100:.1f} % "
          f"(attendu > 5 % : VAL=ete/automne, TEST=hiver)")

    cols = {"LCLid": meta["LCLid"].to_numpy()[te],
            "day": meta["day"].to_numpy()[te],
            "err_kwh": e_te, "alarm": e_te > thr}
    rates = {}
    print("\nANOMALIES SYNTHETIQUES (aucune verite terrain) :")
    for k, yk in anomalie(Y, mu, sd, te).items():
        e, r = score_variante(model, yk, mu[te], sd[te], thr)
        rates[k] = r
        cols[f"err_{k}"] = e
        print(f"  {k:16s} detectes {r * 100:5.1f} %")

    pd.DataFrame(cols).to_parquet(D / "ae_day_test_errors.parquet", index=False)

    try:
        commit = subprocess.check_output(["git", "rev-parse", "--short", "HEAD"],
                                         text=True).strip()
    except Exception:
        commit = None

    entries.append({
        "model": "autoencoder_day", "tag": ARGS.tag,
        "utc": datetime.now(timezone.utc).isoformat(),
        "n_test_days": int(len(te)), "n_households": int(meta["LCLid"].nunique()),
        "test_hash": hashlib.sha256(np.ascontiguousarray(Y[te]).tobytes()).hexdigest()[:16],
        "percentile": h["percentile"], "threshold_kwh": thr,
        "alarm_rate_clean_test": float((e_te > thr).mean()),
        "detection_synthetic": rates, "git_commit": commit,
    })
    LEDGER.write_text(json.dumps(entries, indent=2), encoding="utf-8")
    print("\necrit :", D / "ae_day_test_errors.parquet")
    print("journal :", LEDGER, "| entrees test :", len(entries))