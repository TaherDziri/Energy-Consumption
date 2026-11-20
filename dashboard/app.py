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

st.set_page_config(page_title="P08 - Consommation energétique", layout="wide")


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
daily_v11 = load_dir(str(D_DASH / "daily_v11"))
monthly_v11 = load_dir(str(D_DASH / "monthly_v11"))
monthly_50mix = load_dir(str(D_DASH / "monthly_50mix"))
daily_50mix = load_dir(str(D_DASH / "daily_50mix"))
hourly = load_file(str(D_DL / "sample_hourly.parquet"))

st.sidebar.title("P08 - Consommation energétique")
page = st.sidebar.radio("Page", [
    "Vue d'ensemble",
    "Profil horaire",
    "Journees et pics",
    "Couts (GBP)",
    "Run reel v1.1",
    "Run reel 50 foyers",
    "Validation (fixture)",
    "Qualite",
    "Std vs ToU",
    "Modeles (documentation)",
])

if daily is not None:
    daily["day"] = pd.to_datetime(daily["day"])
if daily_v11 is not None:
    daily_v11["day"] = pd.to_datetime(daily_v11["day"])
if monthly_v11 is not None:
    monthly_v11["period"] = pd.to_datetime(monthly_v11["period"])
if daily_50mix is not None:
    daily_50mix["day"] = pd.to_datetime(daily_50mix["day"])
if monthly_50mix is not None:
    monthly_50mix["period"] = pd.to_datetime(monthly_50mix["period"])

# ---------------------------------------------------------------- 1. ensemble
if page == "Vue d'ensemble":
    st.title("Vue d'ensemble")
    jeu = st.radio("Jeu de donnees", [
        "Run reel 50 foyers (Std + ToU)",
        "Run reel 5 foyers (reference)",
    ], horizontal=True)
    if jeu.startswith("Run reel 50"):
        src = daily_50mix
        source_txt = (
            "Source : lh.p08.daily_v11, MR1 v1.1, 50 foyers reels "
            "(40 Std + 10 ToU), dataset_version=mr1-v11-50mix."
        )
        export_txt = "sql/p08_dashboard_export_50mix.sql"
    else:
        src = daily
        source_txt = (
            "Source : lh.p08.daily, MR1 **4 colonnes**, echantillon de reference "
            "5 foyers (total exact 28 416,517 kWh)."
        )
        export_txt = "sql/p08_dashboard_export.sql"
    if src is None:
        st.caption(f"Export manquant : lance {export_txt}")
        st.stop()
    c1, c2, c3, c4 = st.columns(4)
    c1.metric("Foyers", src["lclid"].nunique())
    c2.metric("Jours-foyers", len(src))
    c3.metric("Periode", f"{src['day'].min():%Y-%m-%d} -> {src['day'].max():%Y-%m-%d}")
    c4.metric("Energie totale", f"{src['total_kwh'].sum():,.3f} kWh")
    st.caption(source_txt)
    q = src["quality_flag"].value_counts().rename_axis("quality_flag").reset_index(name="jours")
    st.plotly_chart(px.bar(q, x="quality_flag", y="jours", text="jours",
                           title="Jours par indicateur qualite",
                           labels={"jours": "nombre de jours-foyers"}),
                    width="stretch")

# ------------------------------------------------------------- 2. profil horaire
elif page == "Profil horaire":
    st.title("Profil horaire moyen")
    st.caption(
        "Ce n'est pas un profil demi-heure. Il vient de l'echantillon horaire "
        "(5 foyers, split train). Le profil 48 creneaux/jour exige MR1 v1.1 (10 colonnes)."
    )
    if hourly is None:
        st.caption("Echantillon absent : data/processed/dl/sample_hourly.parquet")
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
        st.caption("Export manquant.")
        st.stop()
    st.plotly_chart(px.histogram(daily, x="total_kwh", color="lclid", nbins=60,
                                 labels={"total_kwh": "kWh par jour", "lclid": "foyer"},
                                 title="Distribution des consommations journalieres"),
                    width="stretch")
    top = daily.nlargest(10, "total_kwh")[["day", "lclid", "total_kwh", "n_slots", "quality_flag"]]
    st.dataframe(top, width="stretch")
    st.caption(
        "`peak_kwh_hh` et `peak_slot` valent NULL par construction en MR1 v1 "
        "(4 colonnes) : aucun pic horaire fiable avant MR1 v1.1. "
        "La table ci-dessus n'est qu'un classement des totaux journaliers."
    )

# ------------------------------------------------------------------ 4. couts
elif page == "Couts (GBP)":
    st.title("Couts")
    st.caption(
        "Un run MR2 reel (echantillon 5 foyers, v1.1) est maintenant charge dans "
        "`lh.p08.monthly` : voir la page **Run reel v1.1**. Le tableau ci-dessous "
        "montre les lignes de validation (cout NULL = hors calendrier 2013)."
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
        st.caption("lh.test.monthly vide ou non exporte.")

# --------------------------------------------------- 5bis. run reel v1.1
elif page == "Run reel v1.1":
    st.title("Run reel v1.1 (echantillon 5 foyers)")
    st.caption(
        "Run reel, mais sur l'echantillon de 5 foyers : ce n'est pas le run "
        "complet 8,5 Go. Source : `/p08/gold/mr1_daily_v11` (job 1 v1.1 de Taher) puis "
        "MR2 v1.1. Jours et creneaux locaux Europe/London, DST 46/48/50."
    )
    if monthly_v11 is None or not len(monthly_v11):
        st.caption("Export manquant : lance sql/p08_dashboard_export_v11.sql")
        st.stop()
    m = monthly_v11.copy()
    c1, c2, c3, c4 = st.columns(4)
    c1.metric("Foyers", m["lclid"].nunique())
    c2.metric("Lignes foyer x mois", len(m))
    c3.metric("Energie totale", f"{m['monthly_kwh'].sum():,.3f} kWh")
    c4.metric("Cout 2013", f"{m['estimated_cost_gbp'].sum():,.2f} GBP")
    st.caption(
        "Cout **NULL** = mois hors calendrier tarifaire 2013 (jamais 0) : "
        f"{int(m['estimated_cost_gbp'].isna().sum())} lignes. "
        "Convention debut/fin de periode : hypothese **non verifiee**."
    )

    t = m.assign(mois=m["period"].dt.strftime("%Y-%m"))
    st.plotly_chart(
        px.bar(t.groupby(["mois", "quality_flag"], as_index=False)
                .agg(kwh=("monthly_kwh", "sum")),
               x="mois", y="kwh", color="quality_flag",
               title="Run reel v1.1 : kWh par mois et indicateur qualite",
               labels={"mois": "mois", "kwh": "kWh", "quality_flag": "qualite"}),
        width="stretch")

    st.subheader("Detail mensuel")
    st.dataframe(
        m.sort_values(["lclid", "period"])[
            ["lclid", "period", "tariff_group", "monthly_kwh", "estimated_cost_gbp",
             "price_coverage", "peak_kwh_hh", "valid_days", "quality_flag", "run_id"]],
        width="stretch")

    if daily_v11 is not None and len(daily_v11):
        d = daily_v11.copy()
        st.subheader("Qualite journaliere et DST")
        c1, c2, c3, c4 = st.columns(4)
        c1.metric("Jours-foyers", len(d))
        c2.metric("Jours DST (46/50)", int((d["expected_slots"] != 48).sum()))
        c3.metric("Jours incomplets", int((d["n_missing_slots"] > 0).sum()))
        c4.metric("Pics NULL", int(d["peak_kwh_hh"].isna().sum()))
        st.caption(
            "Les jours de 50 demi-heures repettent les slots 2 et 3 (deux lectures "
            "physiques additionnees). Un creneau absent est **absent** de la serie, "
            "jamais ecrit `slot:0`."
        )

        st.subheader("Profil demi-heure moyen (serie MR1 v1.1)")
        # La serie est "slot:kwh;slot:kwh;...". On l'eclate sans la faire confondre
        # avec un creneau manquant : seules les paires presentes sont additionnees.
        rows = []
        for lclid, ser in zip(d["lclid"], d["series"]):
            if not isinstance(ser, str) or not ser:
                continue
            for pair in ser.split(";"):
                slot, _, val = pair.partition(":")
                try:
                    rows.append((lclid, int(slot), float(val)))
                except ValueError:
                    continue
        if rows:
            slots_df = pd.DataFrame(rows, columns=["lclid", "slot", "kwh"])
            prof = slots_df.groupby("slot", as_index=False)["kwh"].mean()
            st.plotly_chart(
                px.line(prof, x="slot", y="kwh",
                        title="Consommation moyenne par creneau local (0..47)",
                        labels={"slot": "slot local (2 x heure + 30 min)",
                                "kwh": "kWh moyen par creneau"}),
                width="stretch")
            st.caption(
                "Slot = heure locale x 2 + minute/30. La moyenne inclut les jours DST : "
                "les slots 2/3 du jour de 50 demi-heures comptent deux fois."
            )

# ---------------------------------------- 5ter. run reel 50 foyers Std+ToU
elif page == "Run reel 50 foyers":
    st.title("Run reel 50 foyers (40 Std + 10 ToU)")
    st.caption(
        "Run reel issu du jeu complet Low Carbon London : 50 foyers reels "
        "(40 Std + 10 ToU). Source : `/p08/raw/meters/sample_50_mix.csv` -> "
        "`/p08/gold/mr1_daily_50mix` -> `/p08/gold/mr2_monthly_50mix`, "
        "`run_id=mr2-v11-50mix`. Jours et creneaux locaux Europe/London, DST 46/48/50. "
        "Le run complet 8,5 Go reste une mesure du binome, non reproduite localement."
    )
    if monthly_50mix is None or not len(monthly_50mix):
        st.caption("Export manquant : lance sql/p08_dashboard_export_50mix.sql")
        st.stop()
    m = monthly_50mix.copy()
    c1, c2, c3, c4 = st.columns(4)
    c1.metric("Foyers", m["lclid"].nunique())
    c2.metric("Lignes foyer x mois", len(m))
    c3.metric("Energie totale", f"{m['monthly_kwh'].sum():,.3f} kWh")
    c4.metric("Cout 2013", f"{m['estimated_cost_gbp'].sum():,.2f} GBP")

    st.caption(
        f"Repartition : {m[m['tariff_group'] == 'Std']['lclid'].nunique()} foyers Std, "
        f"{m[m['tariff_group'] == 'ToU']['lclid'].nunique()} foyers ToU. "
        f"Cout NULL = mois hors calendrier tarifaire 2013 (jamais 0) : "
        f"{int(m['estimated_cost_gbp'].isna().sum())} lignes ; aucun cout ne vaut 0. "
        "Convention debut/fin de periode : hypothese non verifiee."
    )

    st.subheader("Repartition Std / ToU")
    g = m.groupby("tariff_group", as_index=False).agg(
        lignes=("lclid", "size"), foyers=("lclid", "nunique"),
        kwh=("monthly_kwh", "sum"), cout=("estimated_cost_gbp", "sum"))
    st.dataframe(g, width="stretch")
    st.plotly_chart(
        px.bar(g, x="tariff_group", y="kwh", text="kwh", color="tariff_group",
               title="Energie par groupe tarifaire",
               labels={"tariff_group": "groupe", "kwh": "kWh"}),
        width="stretch")

    t = m.assign(mois=m["period"].dt.strftime("%Y-%m"))
    st.plotly_chart(
        px.bar(t.groupby(["mois", "tariff_group"], as_index=False)
                .agg(kwh=("monthly_kwh", "sum")),
               x="mois", y="kwh", color="tariff_group",
               title="Run reel 50 foyers : kWh par mois et groupe tarifaire",
               labels={"mois": "mois", "kwh": "kWh", "tariff_group": "groupe"}),
        width="stretch")

    st.subheader("Detail mensuel")
    st.dataframe(
        m.sort_values(["lclid", "period"])[
            ["lclid", "period", "tariff_group", "monthly_kwh", "estimated_cost_gbp",
             "price_coverage", "peak_kwh_hh", "valid_days", "quality_flag", "run_id"]],
        width="stretch")

    if daily_50mix is not None and len(daily_50mix):
        d = daily_50mix.copy()
        st.subheader("Qualite journaliere et DST")
        c1, c2, c3, c4 = st.columns(4)
        c1.metric("Jours-foyers", len(d))
        c2.metric("Jours DST (46/50)", int((d["expected_slots"] != 48).sum()))
        c3.metric("Jours incomplets", int((d["n_missing_slots"] > 0).sum()))
        c4.metric("Pics NULL", int(d["peak_kwh_hh"].isna().sum()))
        st.caption(
            "Les jours de 50 demi-heures repettent les slots 2 et 3 (deux lectures "
            "physiques additionnees). Un creneau absent est absent de la serie, "
            "jamais ecrit `slot:0`."
        )

        st.subheader("Profil demi-heure moyen par groupe tarifaire")
        rows = []
        for lclid, grp, ser in zip(d["lclid"], d["tariff_group"], d["series"]):
            if not isinstance(ser, str) or not ser:
                continue
            for pair in ser.split(";"):
                slot, _, val = pair.partition(":")
                try:
                    rows.append((grp, int(slot), float(val)))
                except ValueError:
                    continue
        if rows:
            slots_df = pd.DataFrame(rows, columns=["tariff_group", "slot", "kwh"])
            prof = slots_df.groupby(["tariff_group", "slot"], as_index=False)["kwh"].mean()
            st.plotly_chart(
                px.line(prof, x="slot", y="kwh", color="tariff_group",
                        title="Consommation moyenne par creneau local et groupe tarifaire",
                        labels={"slot": "slot local", "kwh": "kWh moyen par creneau",
                                "tariff_group": "groupe"}),
                width="stretch")
            st.caption(
                "Slot = heure locale x 2 + minute/30. Les slots 2/3 du jour de 50 "
                "demi-heures comptent deux fois."
            )

# ------------------------------------------------- 6bis. validation (fixture)
elif page == "Validation (fixture)":
    st.title("Validation sur fixture")
    st.caption(
        "Ce n'est pas de la production. `sample-fixture-v11` est un jeu de test "
        "fabrique depuis les 5 foyers de l'echantillon : ce n'est pas une sortie de MR1."
    )
    if monthly_fixture is None or not len(monthly_fixture):
        st.caption("Export manquant : lance sql/p08_dashboard_export_fixture.sql")
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
        st.caption("Export manquant.")
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
        "Cette vue vient de `lh.p08.daily` (MR1 v1, 4 colonnes) : `n_missing_slots` y est "
        "**derive** (48 - n_slots), pas mesure. Le vrai `n_missing_slots` du contrat v1.1 "
        "(jour local, DST 46/48/50) est sur la page **Run reel v1.1**."
    )

# -------------------------------------------------------------- 6. Std vs ToU
elif page == "Std vs ToU":
    st.title("Std vs ToU")
    st.caption(
        "MR1 v1.1 fournit bien `tariff_group`. L'echantillon de 5 foyers etait "
        "exclusivement Std ; la page **Run reel 50 foyers** ajoute 40 Std + 10 ToU reel. "
        "La ligne de test ToU ci-dessous reste une preuve synthetique."
    )
    if monthly_test is not None and "tou-test-mr2" in set(monthly_test["dataset_version"]):
        st.caption("Seule preuve disponible : la ligne du test ToU du 19/01/2013.")
        st.dataframe(monthly_test[monthly_test["dataset_version"] == "tou-test-mr2"],
                     width="stretch")

# ------------------------------------------------------------------ 7. modeles
elif page == "Modeles (documentation)":
    st.title("Resultats des modeles (lecture seule)")
    st.caption("Le Deep Learning (GRU + autoencodeur) est un livrable exigé oralement par l'enseignante. Le sujet écrit (ideep08.pdf §12) le classe hors périmètre ; cette exigence orale n'est pas confirmée par écrit à ce jour.")
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
                   "MAE poulee 0,1980 vs 0,2014 (gain faible).")
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
        st.caption("Aucun fichier de metriques local (ils sont hors Git).")
