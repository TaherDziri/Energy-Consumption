"""dashboard/app.py
Dashboard P08 en lecture seule.
Sources : exports Parquet depuis Iceberg (data/dashboard/) + echantillon DL local.
Lancement : .venv\\Scripts\\streamlit run dashboard\\app.py
"""
from pathlib import Path

import pandas as pd
import plotly.express as px
import pyarrow.dataset as pads
import streamlit as st

D_DASH = Path("data/dashboard")
D_DL = Path("data/processed/dl")

st.set_page_config(page_title="P08 - Energy Consumption", layout="wide")


@st.cache_data(show_spinner=False)
def load_dir(path: str):
    p = Path(path)
    if not p.exists() or not list(p.glob("*.parquet")):
        return None
    return pads.dataset(str(p), format="parquet").to_table().to_pandas()


@st.cache_data(show_spinner=False)
def load_file(path: str):
    p = Path(path)
    if not p.exists():
        return None
    return pd.read_parquet(p) if p.suffix == ".parquet" else pd.read_csv(p)


daily = load_dir(str(D_DASH / "daily"))
monthly = load_dir(str(D_DASH / "monthly"))
monthly_test = load_dir(str(D_DASH / "monthly_test"))
monthly_fixture = load_dir(str(D_DASH / "monthly_fixture"))
hourly = load_file(str(D_DL / "sample_hourly.parquet"))

st.sidebar.title("P08 - consommation")
page = st.sidebar.radio("Page", [
    "Vue d'ensemble",
    "Profil horaire",
    "Journees et pics",
    "Couts (GBP)",
    "Validation (fixture)",
    "Qualite",
    "Std vs ToU",
    "Modeles (documentation)",
    "Limites",
])

if daily is not None:
    daily["day"] = pd.to_datetime(daily["day"])

# ---------------------------------------------------------------- 1. ensemble
if page == "Vue d'ensemble":
    st.title("Vue d'ensemble")
    if daily is None:
        st.error("Export manquant : lance sql/p08_dashboard_export.sql")
        st.stop()
    c1, c2, c3, c4 = st.columns(4)
    c1.metric("Foyers", daily["lclid"].nunique())
    c2.metric("Jours-foyers", len(daily))
    c3.metric("Periode", f"{daily['day'].min():%Y-%m-%d} -> {daily['day'].max():%Y-%m-%d}")
    c4.metric("Energie totale", f"{daily['total_kwh'].sum():,.0f} kWh")
    st.caption(
        "Source : lh.p08.daily, MR1 **4 colonnes** sur l'echantillon 5 foyers. "
        "Total exact 28 416,517 kWh (arrondi a l'affichage)."
    )
    q = daily["quality_flag"].value_counts().rename_axis("quality_flag").reset_index(name="jours")
    st.plotly_chart(px.bar(q, x="quality_flag", y="jours", text="jours",
                           title="Jours par indicateur qualite",
                           labels={"jours": "nombre de jours-foyers"}),
                    width="stretch")

# ------------------------------------------------------------- 2. profil horaire
elif page == "Profil horaire":
    st.title("Profil horaire moyen")
    st.warning(
        "**Ce n'est pas un profil demi-heure.** Il vient de l'echantillon horaire "
        "(5 foyers, split train). Le profil 48 creneaux/jour exige MR1 v1.1 (10 colonnes)."
    )
    if hourly is None:
        st.error("Echantillon absent : data/processed/dl/sample_hourly.parquet")
        st.stop()
    h = hourly[hourly["split"] == "train"].copy()
    h["heure"] = h["hour_end"].dt.hour
    prof = h.groupby(["LCLid", "heure"], as_index=False)["kwh"].mean()
    pooled = h.groupby("heure", as_index=False)["kwh"].mean()
    fig = px.line(prof, x="heure", y="kwh", color="LCLid",
                  labels={"heure": "heure de fin de periode (GMT)",
                          "kwh": "kWh par heure", "LCLid": "foyer"},
                  title="Consommation moyenne par heure - echantillon horaire (train)")
    fig.add_scatter(x=pooled["heure"], y=pooled["kwh"], name="moyenne 5 foyers",
                    line=dict(width=4, dash="dash"))
    st.plotly_chart(fig, width="stretch")
    st.caption(f"{len(h):,} heures, 5 foyers. Unite : kWh par heure.")

# ---------------------------------------------------------- 3. journees et pics
elif page == "Journees et pics":
    st.title("Journees et pics")
    if daily is None:
        st.error("Export manquant.")
        st.stop()
    st.plotly_chart(px.histogram(daily, x="total_kwh", color="lclid", nbins=60,
                                 labels={"total_kwh": "kWh par jour", "lclid": "foyer"},
                                 title="Distribution des consommations journalieres"),
                    width="stretch")
    top = daily.nlargest(10, "total_kwh")[["day", "lclid", "total_kwh", "n_slots", "quality_flag"]]
    st.dataframe(top, width="stretch")
    st.info(
        "`peak_kwh_hh` et `peak_slot` valent **NULL** par construction en MR1 v1 "
        "(4 colonnes) : aucun pic horaire fiable avant MR1 v1.1. "
        "La table ci-dessus n'est qu'un classement des totaux journaliers."
    )

# ------------------------------------------------------------------ 4. couts
elif page == "Couts (GBP)":
    st.title("Couts")
    st.warning(
        "**Aucun run MR2 reel n'a encore ete charge.** `lh.p08.monthly` est vide par "
        "decision de conception, en attente de MR1 v1.1."
    )
    if monthly_test is not None and len(monthly_test):
        t = monthly_test.copy()
        t["cout"] = t["estimated_cost_gbp"].map(
            lambda v: "non calculable" if pd.isna(v) else f"{v:.2f} GBP")
        t["couverture_tarif"] = t["price_coverage"].map(
            lambda v: "-" if pd.isna(v) else f"{v:.0%}")
        st.dataframe(
            t[["dataset_version", "period", "lclid", "monthly_kwh", "cout",
               "couverture_tarif", "quality_flag"]],
            width="stretch")
        st.caption(
            "Lignes de **validation** (lh.test.monthly), 3 au total. "
            "2012-03 : cout **non calculable** (hors calendrier tarifaire 2013) -> NULL, jamais 0."
        )
    else:
        st.info("lh.test.monthly vide ou non exporte.")

# ------------------------------------------------- 6bis. validation (fixture)
elif page == "Validation (fixture)":
    st.title("Validation sur fixture")
    st.error(
        "**Ce n'est pas de la production.** `sample-fixture-v11` est un jeu de test "
        "fabrique depuis les 5 foyers de l'echantillon : ce n'est pas une sortie de MR1."
    )
    if monthly_fixture is None or not len(monthly_fixture):
        st.info("Export manquant : lance sql/p08_dashboard_export_fixture.sql")
        st.stop()
    f = monthly_fixture.copy()
    c1, c2, c3, c4 = st.columns(4)
    c1.metric("Lignes foyer x mois", len(f))
    c2.metric("Energie", f"{f['monthly_kwh'].sum():,.0f} kWh")
    c3.metric("Cout 2013", f"{f['estimated_cost_gbp'].sum():,.2f} GBP")
    c4.metric("Couts NULL", int(f["estimated_cost_gbp"].isna().sum()))
    t = f.assign(mois=f["period"].astype(str).str.slice(0, 7))
    st.plotly_chart(
        px.bar(t.groupby(["mois", "quality_flag"], as_index=False)
                .agg(kwh=("monthly_kwh", "sum")),
               x="mois", y="kwh", color="quality_flag",
               title="Fixture : kWh par mois et par indicateur qualite",
               labels={"mois": "mois", "kwh": "kWh", "quality_flag": "qualite"}),
        width="stretch")
    st.dataframe(
        f.sort_values(["lclid", "period"])[
            ["lclid", "period", "tariff_group", "monthly_kwh", "estimated_cost_gbp",
             "price_coverage", "peak_kwh_hh", "valid_days", "quality_flag", "run_id"]],
        width="stretch")
    st.caption(
        "Cout NULL = mois hors calendrier tarifaire 2013 (jamais 0). "
        "Controle attendu : 108 lignes, 55 ok / 5 partial_data / 48 no_tariff, "
        "2 321,437773 GBP. Comparaison pandas independante : ecart <= 1e-6 par ligne."
    )

# ---------------------------------------------------------------- 5. qualite
elif page == "Qualite":
    st.title("Qualite des donnees")
    if daily is None:
        st.error("Export manquant.")
        st.stop()
    st.plotly_chart(px.histogram(daily, x="n_slots", nbins=48,
                                 labels={"n_slots": "creneaux reellement sommes (sur 48)"},
                                 title="Nombre de creneaux par jour"),
                    width="stretch")
    st.plotly_chart(px.bar(daily.groupby("quality_flag").size().reset_index(name="jours"),
                           x="quality_flag", y="jours", text="jours",
                           labels={"jours": "jours-foyers"},
                           title="Indicateurs qualite"),
                    width="stretch")
    st.caption(
        "`n_missing_slots` est **derive** (48 - n_slots) en MR1 v1 : ce n'est pas une mesure "
        "des creneaux absents du fichier source. MR1 v1.1 le fournira."
    )

# -------------------------------------------------------------- 6. Std vs ToU
elif page == "Std vs ToU":
    st.title("Std vs ToU")
    st.error(
        "**Vue impossible aujourd'hui.** `tariff_group` est NULL dans lh.p08.daily "
        "(MR1 4 colonnes) et lh.p08.monthly n'a aucune ligne de production. "
        "La comparaison Standard / Time-of-Use exige MR1 v1.1."
    )
    if monthly_test is not None and "tou-test-mr2" in set(monthly_test["dataset_version"]):
        st.caption("Seule preuve disponible : la ligne du test ToU du 19/01/2013.")
        st.dataframe(monthly_test[monthly_test["dataset_version"] == "tou-test-mr2"],
                     width="stretch")

# ------------------------------------------------------------------ 7. modeles
elif page == "Modeles (documentation)":
    st.title("Resultats des modeles (lecture seule)")
    b = load_file(str(D_DL / "baseline_24h_metrics.csv"))
    if b is not None:
        st.subheader("Baselines 24 h (test, kWh reels)")
        st.dataframe(b, width="stretch")
    g = load_file(str(D_DL / "gru_test_runA_l1_metrics.csv"))
    if g is not None:
        fig = px.line(g, x="horizon_h", y=["MAE_GRU", "MAE_saisonnier"],
                      labels={"horizon_h": "horizon (h)", "value": "MAE (kWh)",
                              "variable": "modele"},
                      title="GRU runA_l1 vs saisonnier - MAE par horizon (test)")
        st.plotly_chart(fig, width="stretch")
        st.caption("Test lu **une seule fois** (journal test_seen.json). "
                   "MAE poulee 0,1980 vs 0,2014.")
    a = load_file(str(D_DL / "ae_day_val_errors.csv"))
    if a is not None:
        st.subheader("Autoencodeur jour - erreurs VAL")
        e = a["err_kwh"]
        c1, c2, c3 = st.columns(3)
        c1.metric("P50", f"{e.quantile(.50):.4f} kWh/h")
        c2.metric("P90", f"{e.quantile(.90):.4f} kWh/h")
        c3.metric("Seuil = P95", f"{e.quantile(.95):.4f} kWh/h")
        st.caption("Resultat **negatif** documente : 12,4 % de detection a 1 % de fausses "
                   "alertes < 40 % pre-enregistre -> test jamais lu.")
    if b is None and g is None and a is None:
        st.info("Aucun fichier de metriques local (ils sont hors Git).")

# ------------------------------------------------------------------ 8. limites
else:
    st.title("Limites declarees")
    st.markdown(
        "- **Profil demi-heure** : impossible avant MR1 v1.1 (pas de `slot`).\n"
        "- **Pics** (`peak_kwh_hh`, `peak_slot`) : NULL en MR1 v1.\n"
        "- **Std vs ToU** : impossible, `tariff_group` NULL.\n"
        "- **Couts** : 3 lignes de validation seulement ; 2012 = non calculable.\n"
        "- **Profils affiches** : echantillon horaire 5 foyers, explicitement etiquete.\n"
        "- **MR2 sur donnees reelles** : bloque par l'absence de MR1 v1.1 (10 colonnes)."
    )
