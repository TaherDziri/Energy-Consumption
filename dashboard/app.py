"""dashboard/app.py
Dashboard P08 en lecture seule.
Sources : exports Parquet depuis Iceberg (data/dashboard/) + echantillon DL local.
Lancement : .venv\\Scripts\\streamlit run dashboard\\app.py
"""
from html import escape
from pathlib import Path

import pandas as pd
import plotly.express as px
import streamlit as st

D_DASH = Path("data/dashboard")
D_DL = Path("data/processed/dl")

PAGES = [
    "Vue d'ensemble",
    "Profil horaire",
    "Journees et pics",
    "Couts (GBP)",
    "Run reel v1.1",
    "Run reel 50 foyers",
    "Validation ",
    "Qualite",
    "Std vs ToU",
    "Modeles",
]
CAPTIONS = [
    "lecture et contexte",
    "5 foyers, heure locale",
    "totaux journaliers",
    "validation tarifaire",
    "echantillon 5 foyers",
    "40 Std + 10 ToU",
    "jeu fabrique",
    "MR1 v1, 4 colonnes",
    "groupes et test ToU",
    "GRU et autoencodeur",
]

DL_NOTICE = (
    "Le Deep Learning (GRU + autoencodeur) est un livrable exigé oralement par "
    "l'enseignante. Le sujet écrit (ideep08.pdf §12) le classe hors périmètre ; "
    "cette exigence orale n'est pas confirmée par écrit à ce jour."
)

st.set_page_config(
    page_title=" Consommation énergétique",
    layout="wide",
    initial_sidebar_state="expanded",
)

theme_choice = st.sidebar.radio(
    "Thème",
    ["Sombre", "Clair"],
    index=0,
    horizontal=True,
    label_visibility="collapsed",
    key="p08_theme",
)
DARK = theme_choice == "Sombre"

if DARK:
    C = {
        "BG": "#06171d",
        "BG2": "#0b2a33",
        "SURFACE": "rgba(255,255,255,0.045)",
        "SURFACE2": "rgba(255,255,255,0.085)",
        "BORDER": "rgba(158,224,214,0.18)",
        "TEXT": "#e8f6f4",
        "MUTED": "#9fb9bc",
        "ACCENT": "#3ddc97",
        "ACCENT2": "#43b8ff",
        "GLOW": "rgba(61,220,151,0.20)",
        "GLOW2": "rgba(67,184,255,0.13)",
        "SIDEBAR": "#071d25",
        "SIDEBAR2": "#0a2c34",
        "SHADOW": "0 18px 45px rgba(0,0,0,0.38)",
        "GRID": "rgba(255,255,255,0.09)",
        "BADGE_REAL": "#3ddc97",
        "BADGE_FIXTURE": "#ffb454",
        "BADGE_LEGACY": "#9fb9bc",
        "BADGE_MODEL": "#a78bfa",
        "BADGE_NEUTRAL": "#43b8ff",
    }
else:
    C = {
        "BG": "#f3f8f9",
        "BG2": "#e6f2f2",
        "SURFACE": "rgba(255,255,255,0.92)",
        "SURFACE2": "#ffffff",
        "BORDER": "#d7e6e7",
        "TEXT": "#12333a",
        "MUTED": "#5c7478",
        "ACCENT": "#0f766e",
        "ACCENT2": "#2563eb",
        "GLOW": "rgba(15,118,110,0.12)",
        "GLOW2": "rgba(37,99,235,0.08)",
        "SIDEBAR": "#eef7f6",
        "SIDEBAR2": "#ffffff",
        "SHADOW": "0 14px 34px rgba(15,51,58,0.12)",
        "GRID": "#e7eff1",
        "BADGE_REAL": "#0f766e",
        "BADGE_FIXTURE": "#b45309",
        "BADGE_LEGACY": "#475569",
        "BADGE_MODEL": "#7c3aed",
        "BADGE_NEUTRAL": "#1d4ed8",
    }

CSS = """
<style>
  :root {
    --p08-bg: __BG__; --p08-bg2: __BG2__;
    --p08-surface: __SURFACE__; --p08-surface2: __SURFACE2__;
    --p08-border: __BORDER__; --p08-text: __TEXT__; --p08-muted: __MUTED__;
    --p08-accent: __ACCENT__; --p08-accent2: __ACCENT2__;
    --p08-glow: __GLOW__; --p08-glow2: __GLOW2__;
    --p08-sidebar: __SIDEBAR__; --p08-sidebar2: __SIDEBAR2__;
    --p08-shadow: __SHADOW__; --p08-grid: __GRID__;
    --p08-badge-real: __BADGE_REAL__; --p08-badge-fixture: __BADGE_FIXTURE__;
    --p08-badge-legacy: __BADGE_LEGACY__; --p08-badge-model: __BADGE_MODEL__;
    --p08-badge-neutral: __BADGE_NEUTRAL__;
  }
  body, [data-testid="stAppViewContainer"] {
    background:
      radial-gradient(950px 420px at 88% -12%, var(--p08-glow), transparent 62%),
      radial-gradient(780px 360px at -12% 8%, var(--p08-glow2), transparent 60%),
      linear-gradient(165deg, var(--p08-bg2) 0%, var(--p08-bg) 58%);
    color: var(--p08-text);
  }
  [data-testid="stHeader"] { background: transparent; }
  .block-container { padding-top: 1.5rem; padding-bottom: 3rem; max-width: 1500px; }
  [data-testid="stAppViewContainer"], [data-testid="stSidebar"] {
    color: var(--p08-text);
  }
  [data-testid="stSidebar"] {
    background: linear-gradient(180deg, var(--p08-sidebar) 0%, var(--p08-sidebar2) 100%);
    border-right: 1px solid var(--p08-border);
    box-shadow: inset -1px 0 0 rgba(255,255,255,0.02);
  }
  [data-testid="stSidebar"] [role="radio"] {
    border-radius: 10px; padding: 5px 8px;
  }
  [data-testid="stSidebar"] [role="radio"][aria-checked="true"] {
    background: var(--p08-glow);
    box-shadow: inset 3px 0 0 var(--p08-accent);
  }
  [data-testid="stSidebar"] [data-baseweb="radio"] label {
    font-weight: 600; color: var(--p08-text);
  }
  .p08-brand {
    display: flex; align-items: center; gap: 11px;
    padding: 10px 12px; margin: 4px 0 10px 0;
    border: 1px solid var(--p08-border); border-radius: 14px;
    background: var(--p08-surface); backdrop-filter: blur(8px);
  }
  .p08-brand-mark {
    width: 36px; height: 36px; border-radius: 11px; flex: none;
    display: grid; place-items: center; font-size: 1rem;
    background: linear-gradient(135deg, var(--p08-accent), var(--p08-accent2));
    color: #04181d; box-shadow: 0 0 18px var(--p08-glow);
  }
  .p08-brand-name { font-weight: 800; letter-spacing: 0.08em; line-height: 1.1; }
  .p08-brand-sub { font-size: 0.72rem; color: var(--p08-muted); }
  .p08-side-status {
    display: flex; align-items: center; gap: 8px;
    font-size: 0.72rem; color: var(--p08-muted);
    padding: 2px 4px 10px 4px;
  }
  .p08-dot {
    width: 7px; height: 7px; border-radius: 50%;
    background: var(--p08-accent); box-shadow: 0 0 10px var(--p08-accent);
  }
  .p08-header {
    position: relative; overflow: hidden;
    border: 1px solid var(--p08-border); border-radius: 20px;
    padding: 20px 24px; margin-bottom: 20px;
    background:
      linear-gradient(120deg, var(--p08-glow) 0%, var(--p08-glow2) 100%),
      linear-gradient(160deg, var(--p08-surface2), var(--p08-surface));
    box-shadow: var(--p08-shadow); backdrop-filter: blur(12px);
  }
  .p08-header::before {
    content: ""; position: absolute; right: -70px; top: -150px;
    width: 280px; height: 280px; border-radius: 50%;
    background: radial-gradient(circle, var(--p08-glow), transparent 68%);
    animation: p08-float 9s ease-in-out infinite alternate;
  }
  .p08-header::after {
    content: ""; position: absolute; left: 0; bottom: 0; height: 3px; width: 100%;
    background: linear-gradient(90deg, var(--p08-accent), var(--p08-accent2), transparent);
  }
  .p08-header > * { position: relative; z-index: 1; }
  @keyframes p08-float {
    from { transform: translate3d(0, 0, 0) scale(1); }
    to { transform: translate3d(-18px, 22px, 0) scale(1.12); }
  }
  .p08-kicker {
    color: var(--p08-accent); font-size: 0.74rem; text-transform: uppercase;
    letter-spacing: 0.14em; font-weight: 800; margin-bottom: 6px;
  }
  .p08-kicker::before {
    content: ""; display: inline-block; width: 7px; height: 7px;
    margin-right: 9px; border-radius: 50%; background: var(--p08-accent);
    box-shadow: 0 0 12px var(--p08-accent);
  }
  .p08-title {
    color: var(--p08-text); font-size: 1.85rem; font-weight: 800;
    letter-spacing: -0.02em; line-height: 1.15;
  }
  .p08-badges { margin-top: 12px; display: flex; gap: 8px; flex-wrap: wrap; }
  .p08-badge {
    display: inline-block; border-radius: 999px; padding: 4px 11px;
    font-size: 0.72rem; font-weight: 800; letter-spacing: 0.02em;
    border: 1px solid var(--p08-border); background: var(--p08-surface2);
  }
  .p08-badge--real { color: var(--p08-badge-real); border-color: var(--p08-badge-real); }
  .p08-badge--fixture { color: var(--p08-badge-fixture); border-color: var(--p08-badge-fixture); }
  .p08-badge--legacy { color: var(--p08-badge-legacy); border-color: var(--p08-badge-legacy); }
  .p08-badge--model { color: var(--p08-badge-model); border-color: var(--p08-badge-model); }
  .p08-badge--neutral { color: var(--p08-badge-neutral); border-color: var(--p08-badge-neutral); }
  .p08-lead {
    color: var(--p08-muted); font-size: 0.98rem; margin: 0 0 16px 0;
    line-height: 1.55; padding-left: 14px;
    border-left: 3px solid var(--p08-accent);
  }
  .p08-section {
    font-size: 1.06rem; font-weight: 800; color: var(--p08-text);
    margin: 12px 0 8px 0; padding-left: 12px;
    border-left: 3px solid var(--p08-accent2);
  }
  [data-testid="stMetric"] {
    background: linear-gradient(145deg, var(--p08-surface2), var(--p08-surface));
    border: 1px solid var(--p08-border); border-top: 2px solid var(--p08-accent);
    border-radius: 16px; padding: 14px 16px; box-shadow: var(--p08-shadow);
    transition: transform 0.18s ease, box-shadow 0.18s ease;
  }
  [data-testid="stMetric"]:hover {
    transform: translateY(-3px);
    box-shadow: 0 20px 42px var(--p08-glow);
  }
  [data-testid="stMetricLabel"] p {
    color: var(--p08-muted) !important; font-size: 0.72rem;
    text-transform: uppercase; letter-spacing: 0.06em; font-weight: 800;
  }
  [data-testid="stMetricValue"] div {
    color: var(--p08-text) !important; font-weight: 800;
  }
  [data-testid="stDataFrame"] {
    border: 1px solid var(--p08-border); border-radius: 14px; overflow: hidden;
  }
  [data-testid="stExpander"] {
    border: 1px solid var(--p08-border) !important;
    border-radius: 13px; background: var(--p08-surface) !important;
  }
  [data-baseweb="tab-list"] { gap: 8px; border-bottom: 1px solid var(--p08-border); }
  [data-baseweb="tab"] {
    border-radius: 10px 10px 0 0; padding: 8px 12px;
    color: var(--p08-muted); font-weight: 700;
  }
  [data-baseweb="tab"][aria-selected="true"] {
    color: var(--p08-accent); background: var(--p08-glow);
  }
  [data-testid="stNotification"] {
    background: var(--p08-surface) !important;
    border: 1px solid var(--p08-border) !important;
    color: var(--p08-text) !important;
  }
  .stCaption p, [data-testid="stCaptionContainer"] p,
  [data-testid="stExpander"] summary p { color: var(--p08-muted) !important; }
  .stMarkdown, .stMarkdown p { color: var(--p08-text); }
  .p08-footer {
    margin-top: 28px; padding: 14px 0 4px; text-align: center;
    color: var(--p08-muted); font-size: 0.74rem; letter-spacing: 0.03em;
    background: linear-gradient(90deg, transparent, var(--p08-surface), transparent);
    border-top: 1px solid var(--p08-border);
  }
</style>
"""
for _token, _value in C.items():
    CSS = CSS.replace(f"__{_token}__", _value)
st.markdown(CSS, unsafe_allow_html=True)

PALETTE = (
    ["#3ddc97", "#ffb454", "#43b8ff", "#a78bfa", "#fb7185"]
    if DARK
    else ["#0f766e", "#d97706", "#2563eb", "#7c3aed", "#be123c"]
)
QUALITY_COLORS = {
    "ok": PALETTE[0],
    "partial_data": PALETTE[1],
    "partial_tariff": "#fbbf24" if DARK else "#f59e0b",
    "no_tariff": "#82969b" if DARK else "#64748b",
    "no_data": PALETTE[4],
}
GROUP_COLORS = {"Std": PALETTE[0], "ToU": PALETTE[1]}

PLOT_TEMPLATE = "plotly_dark" if DARK else "plotly_white"
PLOT_FONT = "#e8f6f4" if DARK else "#1c2733"
PLOT_TITLE = "#8ef0c6" if DARK else "#12333a"
PLOT_GRID = "rgba(255,255,255,0.10)" if DARK else "#eef2f5"
PLOT_HOVER_BG = "#0d3038" if DARK else "#ffffff"


@st.cache_data(show_spinner=False)
def load_dir(path: str):
    p = Path(path)
    if not p.exists() or not list(p.glob("*.parquet")):
        return None
    import pyarrow.dataset as pads

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
dl_preds = load_dir(str(D_DASH / "dl_predictions"))
hourly = load_file(str(D_DL / "sample_hourly.parquet"))

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

# ------------------------------------------------------------------ helpers


def badge(text: str, kind: str = "neutral") -> str:
    return f'<span class="p08-badge p08-badge--{escape(kind)}">{escape(text)}</span>'


def header(kicker: str, title: str, badges=()) -> None:
    marks = "".join(badge(t, k) for t, k in badges)
    st.markdown(
        '<div class="p08-header">'
        f'<div class="p08-kicker">{escape(kicker)}</div>'
        f'<div class="p08-title">{escape(title)}</div>'
        f'<div class="p08-badges">{marks}</div>'
        "</div>",
        unsafe_allow_html=True,
    )


def lead(text: str) -> None:
    st.markdown(f'<p class="p08-lead">{escape(text)}</p>', unsafe_allow_html=True)


def section(text: str) -> None:
    st.markdown(f'<div class="p08-section">{escape(text)}</div>', unsafe_allow_html=True)


def source_note(text: str) -> None:
    with st.expander("Source et hypothèses", expanded=False):
        st.write(text)


def kpis(items) -> None:
    slots = st.columns(len(items))
    for col, item in zip(slots, items):
        label, value = item[0], item[1]
        delta = item[2] if len(item) > 2 else None
        with col:
            st.metric(label, value, delta=delta)


def styled(fig, height=360, hover="closest", legend_title=None):
    fig.update_layout(
        template=PLOT_TEMPLATE,
        height=height,
        margin=dict(l=56, r=24, t=64 if fig.layout.title.text else 28, b=52),
        paper_bgcolor="rgba(0,0,0,0)",
        plot_bgcolor="rgba(0,0,0,0)",
        font=dict(family="Segoe UI, Arial, sans-serif", size=12, color=PLOT_FONT),
        title=dict(font=dict(size=15, color=PLOT_TITLE), x=0.01, xanchor="left"),
        legend=dict(
            orientation="h",
            y=1.14 if fig.layout.title.text else 1.02,
            x=0,
            title=dict(text=legend_title, font=dict(size=11)) if legend_title else None,
        ),
        hovermode=hover,
        hoverlabel=dict(
            bgcolor=PLOT_HOVER_BG,
            font_color=PLOT_FONT,
            bordercolor=PLOT_GRID,
        ),
    )
    fig.update_xaxes(showgrid=False, linecolor=PLOT_GRID, zeroline=False)
    fig.update_yaxes(showgrid=True, gridcolor=PLOT_GRID, zeroline=False)
    return fig


def show(fig, height=360, hover="closest", legend_title=None) -> None:
    st.plotly_chart(
        styled(fig, height=height, hover=hover, legend_title=legend_title),
        width="stretch",
        config={"displaylogo": False, "responsive": True},
    )


def n0(value) -> str:
    return f"{int(value):,}".replace(",", " ")


def n3(value) -> str:
    return f"{value:,.3f}".replace(",", " ")


def gb(value) -> str:
    return f"{value:,.2f}".replace(",", " ")


def cost_text(value) -> str:
    return "non calculable" if pd.isna(value) else f"{gb(value)} GBP"


def cover_text(value) -> str:
    return "–" if pd.isna(value) else f"{value:.0%}"


def monthly_table(df):
    x = df.copy()
    x["period"] = pd.to_datetime(x["period"])
    x["Mois"] = x["period"].dt.strftime("%Y-%m")
    x = x.rename(columns={
        "lclid": "Foyer", "tariff_group": "Tarif", "monthly_kwh": "Energie (kWh)",
        "estimated_cost_gbp": "Cout", "price_coverage": "Couverture",
        "peak_kwh_hh": "Pic (kWh/30 min)", "valid_days": "Jours valides",
        "quality_flag": "Qualite", "run_id": "Run",
    })
    x["Cout"] = x["Cout"].map(cost_text)
    x["Couverture"] = x["Couverture"].map(cover_text)
    x["Energie (kWh)"] = x["Energie (kWh)"].map(n3)
    return x[[
        "Foyer", "Mois", "Tarif", "Energie (kWh)", "Cout", "Couverture",
        "Pic (kWh/30 min)", "Jours valides", "Qualite", "Run",
    ]].sort_values(["Foyer", "Mois"])


def series_frame(daily_df, with_group=False):
    rows = []
    cols = ["tariff_group", "slot", "kwh"] if with_group else ["lclid", "slot", "kwh"]
    for values in zip(*[daily_df[c] for c in cols[:1] + ["series"]]):
        ident, ser = values
        if not isinstance(ser, str) or not ser:
            continue
        for pair in ser.split(";"):
            slot, _, val = pair.partition(":")
            try:
                rows.append((ident, int(slot), float(val)))
            except ValueError:
                continue
    return pd.DataFrame(rows, columns=["groupe", "slot", "kwh"] if with_group
                        else ["foyer", "slot", "kwh"])


def missing_export(sql: str) -> None:
    st.info(f"Export Parquet absent. Lancez d'abord `{sql}`.")


st.sidebar.markdown(
    '<div class="p08-brand">'
    '<div class="p08-brand-mark">⚡</div>'
    '<div><div class="p08-brand-name">P08</div>'
    '<div class="p08-brand-sub">Énergie · lecture seule</div></div>'
    "</div>",
    unsafe_allow_html=True,
)
st.sidebar.markdown(
    '<div class="p08-side-status"><span class="p08-dot"></span>'
    "10 vues · jeux réels et fabriqués</div>",
    unsafe_allow_html=True,
)
page = st.sidebar.radio(
    "Navigation", PAGES, captions=CAPTIONS, label_visibility="collapsed"
)
st.sidebar.markdown("---")
with st.sidebar.expander("Étiquettes et sources", expanded=False):
    st.caption("Jeux réels : échantillon 5 foyers, run 50 foyers.")
    st.caption("Jeux fabriqués : sample-fixture-v11.")
    st.caption("Volumes synthétiques : synthetic_155k, synthetic_620k.")
    st.caption("Sources : exports Parquet de data/dashboard/ et données DL locales.")

# ------------------------------------------------------------- 1. ensemble
if page == "Vue d'ensemble":
    header(
        "Lecture transversale",
        "Vue d'ensemble",
        [("Lecture seule", "neutral"), ("10 pages", "neutral")],
    )
    lead(
        "Deux jeux réels sont disponibles. Le run 50 foyers est affiché par défaut. "
        "Le run 5 foyers sert de référence historique."
    )
    jeu = st.radio(
        "Jeu de données",
        ["Run reel 50 foyers (Std + ToU)", "Run reel 5 foyers (reference)"],
        horizontal=True,
    )
    if jeu.startswith("Run reel 50"):
        src = daily_50mix
        source_txt = (
            "Source : lh.p08.daily_v11, MR1 v1.1, 50 foyers réels "
            "(40 Std + 10 ToU), dataset_version=mr1-v11-50mix."
        )
        export_txt = "sql/p08_dashboard_export_50mix.sql"
    else:
        src = daily
        source_txt = (
            "Source : lh.p08.daily, MR1 4 colonnes, échantillon de référence "
            "5 foyers (total exact 28 416,517 kWh)."
        )
        export_txt = "sql/p08_dashboard_export.sql"
    if src is None:
        missing_export(export_txt)
        st.stop()

    kpis([
        ("Foyers", n0(src["lclid"].nunique())),
        ("Jours-foyers", n0(len(src))),
        ("Période", f"{src['day'].min():%Y-%m-%d} → {src['day'].max():%Y-%m-%d}"),
        ("Énergie totale", f"{n3(src['total_kwh'].sum())} kWh"),
    ])
    st.caption(source_txt)

    col_left, col_right = st.columns([1, 1.6])
    with col_left:
        q = (src["quality_flag"].value_counts()
             .rename_axis("quality_flag").reset_index(name="jours"))
        q["part"] = q["jours"] / q["jours"].sum()
        fig = px.bar(
            q.sort_values("jours"), x="jours", y="quality_flag", orientation="h",
            text=q["jours"].map(n0), color="quality_flag",
            color_discrete_map=QUALITY_COLORS,
            title="Jours-foyers par indicateur qualité",
            labels={"quality_flag": "", "jours": "jours-foyers"},
            custom_data=["part"],
        )
        fig.update_traces(textposition="outside", hovertemplate=(
            "%{y}<br>%{x} jours-foyers<br>%{customdata[0]:.1%}</extra>"
        ))
        show(fig, height=330, legend_title="Qualité")
    with col_right:
        daily_tot = src.groupby("day", as_index=False)["total_kwh"].sum()
        fig = px.line(
            daily_tot, x="day", y="total_kwh",
            title="Énergie journalière agrégée",
            labels={"day": "date", "total_kwh": "kWh / jour"},
        )
        fig.update_traces(line=dict(color=PALETTE[0], width=2))
        fig.update_xaxes(rangeslider_visible=True)
        show(fig, height=330, hover="x unified")
    source_note(source_txt + f" Export utilisé : `{export_txt}`. "
                "Les agrégats sont calculés à partir du Parquet affiché.")

# --------------------------------------------------------- 2. profil horaire
elif page == "Profil horaire":
    header(
        "Échantillon horaire",
        "Profil horaire moyen",
        [("5 foyers", "neutral"), ("split train", "neutral")],
    )
    lead(
        "Ce n'est pas un profil demi-horaire. Il provient de l'échantillon horaire "
        "utilisé pour le Deep Learning. Le profil à 48 créneaux exige MR1 v1.1."
    )
    if hourly is None:
        missing_export("data/processed/dl/sample_hourly.parquet")
        st.stop()
    h = hourly[hourly["split"] == "train"].copy()
    h["heure"] = h["hour_end"].dt.hour
    prof = h.groupby(["LCLid", "heure"], as_index=False)["kwh"].mean()
    pooled = h.groupby("heure", as_index=False)["kwh"].mean()
    show_pooled = st.checkbox("Afficher la moyenne des 5 foyers", value=True)
    fig = px.line(
        prof, x="heure", y="kwh", color="LCLid",
        color_discrete_sequence=PALETTE,
        labels={"heure": "heure de fin de période (GMT)",
                "kwh": "kWh par heure", "LCLid": "foyer"},
        title="Consommation moyenne par heure — échantillon horaire (train)",
    )
    if show_pooled:
        fig.add_scatter(
            x=pooled["heure"], y=pooled["kwh"], name="moyenne 5 foyers",
            line=dict(width=4, dash="dash", color="#12333a"),
        )
    fig.update_xaxes(dtick=2)
    show(fig, height=460, hover="x unified", legend_title="Foyer")
    st.caption(f"{n0(len(h))} heures, 5 foyers. Unité : kWh par heure.")
    source_note(
        "Source : data/processed/dl/sample_hourly.parquet, split train. "
        "Les heures sont celles de l'échantillon DL, en GMT. "
        "Aucune valeur manquante n'est inventée."
    )

# ------------------------------------------------------- 3. journées et pics
elif page == "Journees et pics":
    header(
        "Totaux journaliers",
        "Journées et pics",
        [("MR1 v1", "legacy"), ("4 colonnes", "legacy")],
    )
    lead(
        "Distribution des totaux journaliers. Le pic demi-horaire n'existe pas dans "
        "cette version du contrat."
    )
    if daily is None:
        missing_export("sql/p08_dashboard_export.sql")
        st.stop()
    foyers = ["Tous les foyers"] + sorted(daily["lclid"].dropna().unique().tolist())
    choix = st.selectbox("Foyer", foyers, index=0)
    d = daily if choix == "Tous les foyers" else daily[daily["lclid"] == choix]
    fig = px.histogram(
        d, x="total_kwh", color="lclid", nbins=60,
        color_discrete_sequence=PALETTE,
        labels={"total_kwh": "kWh par jour", "lclid": "foyer"},
        title="Distribution des consommations journalières",
    )
    show(fig, height=380, legend_title="Foyer")
    section("Les dix journées les plus consommatrices")
    top = d.nlargest(10, "total_kwh")[
        ["day", "lclid", "total_kwh", "n_slots", "quality_flag"]
    ].copy()
    top["day"] = top["day"].dt.strftime("%Y-%m-%d")
    top["total_kwh"] = top["total_kwh"].map(n3)
    st.dataframe(top.rename(columns={
        "day": "Date", "lclid": "Foyer", "total_kwh": "Énergie (kWh)",
        "n_slots": "Créneaux", "quality_flag": "Qualité",
    }), width="stretch", hide_index=True)
    st.caption(
        "`peak_kwh_hh` et `peak_slot` valent NULL par construction en MR1 v1 "
        "(4 colonnes) : aucun pic horaire fiable avant MR1 v1.1. "
        "Le tableau ci-dessus n'est qu'un classement des totaux journaliers."
    )
    source_note("Source : lh.p08.daily, export sql/p08_dashboard_export.sql.")

# -------------------------------------------------------------- 4. coûts
elif page == "Couts (GBP)":
    header(
        "Validation tarifaire",
        "Coûts estimés",
        [("lh.test.monthly", "neutral")],
    )
    lead(
        "Un run MR2 réel sur 5 foyers est chargé dans lh.p08.monthly : voir la page "
        "Run reel v1.1. Le tableau ci-dessous montre les lignes de validation."
    )
    if monthly_test is not None and len(monthly_test):
        t = monthly_test.copy()
        t["period"] = pd.to_datetime(t["period"])
        t["Mois"] = t["period"].dt.strftime("%Y-%m")
        t["Coût"] = t["estimated_cost_gbp"].map(cost_text)
        t["Couverture"] = t["price_coverage"].map(cover_text)
        view = t[[
            "dataset_version", "Mois", "lclid", "monthly_kwh", "Coût",
            "Couverture", "quality_flag",
        ]].rename(columns={
            "dataset_version": "Jeu", "lclid": "Foyer",
            "monthly_kwh": "Énergie (kWh)", "quality_flag": "Qualité",
        })
        view["Énergie (kWh)"] = view["Énergie (kWh)"].map(n3)
        st.dataframe(view, width="stretch", hide_index=True)
        st.caption(
            "Lignes de **validation** (lh.test.monthly), 3 au total. "
            "2012-03 : coût **non calculable** (hors calendrier tarifaire 2013) "
            "-> NULL, jamais 0."
        )
    else:
        st.info("lh.test.monthly est vide ou non exporté.")
    source_note(
        "Source : lh.test.monthly. Un coût inconnu est un champ vide, jamais 0.0 "
        "et jamais NaN. La couverture mesure la disponibilité du prix, "
        "non la complétude des mesures."
    )

# --------------------------------------------------- 5. run réel v1.1
elif page == "Run reel v1.1":
    header(
        "Run réel — échantillon de référence",
        "Run reel v1.1 (5 foyers)",
        [("Jeu réel", "real"), ("MR1 v1.1", "neutral")],
    )
    lead(
        "Run réel sur 5 foyers, mais pas le run complet 8,5 Go. "
        "Jours et créneaux locaux Europe/London, DST 46/48/50."
    )
    if monthly_v11 is None or not len(monthly_v11):
        missing_export("sql/p08_dashboard_export_v11.sql")
        st.stop()
    m = monthly_v11.copy()
    kpis([
        ("Foyers", n0(m["lclid"].nunique())),
        ("Lignes foyer × mois", n0(len(m))),
        ("Énergie totale", f"{n3(m['monthly_kwh'].sum())} kWh"),
        ("Coût 2013", f"{gb(m['estimated_cost_gbp'].sum())} GBP"),
    ])
    st.caption(
        "Coût NULL = mois hors calendrier tarifaire 2013 (jamais 0) : "
        f"{n0(m['estimated_cost_gbp'].isna().sum())} lignes. "
        "Convention début/fin de période : hypothèse **non vérifiée**."
    )
    tabs = st.tabs(["Mensuel", "Qualité journalière", "Profil 48 créneaux"])
    with tabs[0]:
        t = m.assign(mois=m["period"].dt.strftime("%Y-%m"))
        fig = px.bar(
            t.groupby(["mois", "quality_flag"], as_index=False)
            .agg(kwh=("monthly_kwh", "sum")),
            x="mois", y="kwh", color="quality_flag",
            color_discrete_map=QUALITY_COLORS,
            title="kWh par mois et indicateur qualité",
            labels={"mois": "mois", "kwh": "kWh", "quality_flag": "qualité"},
        )
        show(fig, height=370, legend_title="Qualité")
        section("Détail mensuel")
        st.dataframe(monthly_table(m), width="stretch", hide_index=True)
    with tabs[1]:
        if daily_v11 is not None and len(daily_v11):
            d = daily_v11.copy()
            kpis([
                ("Jours-foyers", n0(len(d))),
                ("Jours DST (46/50)", n0((d["expected_slots"] != 48).sum())),
                ("Jours incomplets", n0((d["n_missing_slots"] > 0).sum())),
                ("Pics NULL", n0(d["peak_kwh_hh"].isna().sum())),
            ])
            st.caption(
                "Les jours de 50 demi-heures répètent les slots 2 et 3 "
                "(deux lectures physiques additionnées). Un créneau absent est "
                "absent de la série, jamais écrit `slot:0`."
            )
        else:
            st.info("Export journalier v1.1 absent.")
    with tabs[2]:
        if daily_v11 is not None and len(daily_v11):
            slots_df = series_frame(daily_v11)
            if len(slots_df):
                prof = slots_df.groupby("slot", as_index=False)["kwh"].mean()
                fig = px.line(
                    prof, x="slot", y="kwh",
                    title="Consommation moyenne par créneau local (0–47)",
                    labels={"slot": "slot local (2 × heure + 30 min)",
                            "kwh": "kWh moyen par créneau"},
                )
                fig.update_traces(line=dict(color=PALETTE[0], width=2))
                fig.update_xaxes(dtick=4)
                show(fig, height=390, hover="x unified")
                st.caption(
                    "Slot = heure locale × 2 + minute/30. La moyenne inclut les "
                    "jours DST : les slots 2/3 du jour de 50 demi-heures comptent deux fois."
                )
    source_note(
        "Sources : /p08/gold/mr1_daily_v11 (Job 1 v1.1 de Taher) puis MR2 v1.1. "
        "Export : sql/p08_dashboard_export_v11.sql. "
        "Le run complet 8,5 Go est une mesure du binôme enregistrée dans le dépôt, "
        "non reproduite localement."
    )

# --------------------------------------------- 6. run réel 50 foyers
elif page == "Run reel 50 foyers":
    header(
        "Run réel — échantillon élargi",
        "Run reel 50 foyers (40 Std + 10 ToU)",
        [("Jeu réel", "real"), ("40 Std + 10 ToU", "neutral")],
    )
    lead(
        "Run réel issu du jeu complet Low Carbon London. Le run complet 8,5 Go "
        "reste une mesure du binôme, non reproduite localement."
    )
    if monthly_50mix is None or not len(monthly_50mix):
        missing_export("sql/p08_dashboard_export_50mix.sql")
        st.stop()
    m = monthly_50mix.copy()
    kpis([
        ("Foyers", n0(m["lclid"].nunique())),
        ("Lignes foyer × mois", n0(len(m))),
        ("Énergie totale", f"{n3(m['monthly_kwh'].sum())} kWh"),
        ("Coût 2013", f"{gb(m['estimated_cost_gbp'].sum())} GBP"),
    ])
    st.caption(
        f"Répartition : {m[m['tariff_group'] == 'Std']['lclid'].nunique()} foyers Std, "
        f"{m[m['tariff_group'] == 'ToU']['lclid'].nunique()} foyers ToU. "
        "Coût NULL = mois hors calendrier tarifaire 2013 (jamais 0) : "
        f"{n0(m['estimated_cost_gbp'].isna().sum())} lignes ; aucun coût ne vaut 0. "
        "Convention début/fin de période : hypothèse non vérifiée."
    )
    tabs = st.tabs(["Synthèse", "Mensuel", "Qualité journalière", "Profil par tarif"])
    with tabs[0]:
        g = m.groupby("tariff_group", as_index=False).agg(
            lignes=("lclid", "size"), foyers=("lclid", "nunique"),
            kwh=("monthly_kwh", "sum"), cout=("estimated_cost_gbp", "sum"))
        view = g.rename(columns={
            "tariff_group": "Groupe", "lignes": "Lignes", "foyers": "Foyers",
            "kwh": "Énergie (kWh)", "cout": "Coût (GBP)",
        })
        view["Énergie (kWh)"] = view["Énergie (kWh)"].map(n3)
        view["Coût (GBP)"] = view["Coût (GBP)"].map(gb)
        st.dataframe(view, width="stretch", hide_index=True)
        fig = px.bar(
            g, x="tariff_group", y="kwh", text=g["kwh"].map(n0),
            color="tariff_group", color_discrete_map=GROUP_COLORS,
            title="Énergie par groupe tarifaire",
            labels={"tariff_group": "groupe", "kwh": "kWh"},
        )
        fig.update_traces(textposition="outside")
        show(fig, height=340, legend_title="Groupe")
    with tabs[1]:
        t = m.assign(mois=m["period"].dt.strftime("%Y-%m"))
        fig = px.bar(
            t.groupby(["mois", "tariff_group"], as_index=False)
            .agg(kwh=("monthly_kwh", "sum")),
            x="mois", y="kwh", color="tariff_group",
            color_discrete_map=GROUP_COLORS,
            title="kWh par mois et groupe tarifaire",
            labels={"mois": "mois", "kwh": "kWh", "tariff_group": "groupe"},
        )
        show(fig, height=380, legend_title="Groupe")
        section("Détail mensuel")
        st.dataframe(monthly_table(m), width="stretch", hide_index=True)
    with tabs[2]:
        if daily_50mix is not None and len(daily_50mix):
            d = daily_50mix.copy()
            kpis([
                ("Jours-foyers", n0(len(d))),
                ("Jours DST (46/50)", n0((d["expected_slots"] != 48).sum())),
                ("Jours incomplets", n0((d["n_missing_slots"] > 0).sum())),
                ("Pics NULL", n0(d["peak_kwh_hh"].isna().sum())),
            ])
            st.caption(
                "Les jours de 50 demi-heures répètent les slots 2 et 3. "
                "Un créneau absent est absent de la série, jamais écrit `slot:0`."
            )
        else:
            st.info("Export journalier 50 foyers absent.")
    with tabs[3]:
        if daily_50mix is not None and len(daily_50mix):
            slots_df = series_frame(daily_50mix, with_group=True)
            if len(slots_df):
                prof = slots_df.groupby(["groupe", "slot"], as_index=False)["kwh"].mean()
                fig = px.line(
                    prof, x="slot", y="kwh", color="groupe",
                    color_discrete_map=GROUP_COLORS,
                    title="Consommation moyenne par créneau et groupe tarifaire",
                    labels={"slot": "slot local", "kwh": "kWh moyen par créneau",
                            "groupe": "groupe"},
                )
                fig.update_xaxes(dtick=4)
                show(fig, height=400, hover="x unified", legend_title="Groupe")
                st.caption(
                    "Slot = heure locale × 2 + minute/30. Les slots 2/3 du jour "
                    "de 50 demi-heures comptent deux fois."
                )
    source_note(
        "Sources : /p08/raw/meters/sample_50_mix.csv → /p08/gold/mr1_daily_50mix "
        "→ /p08/gold/mr2_monthly_50mix, run_id=mr2-v11-50mix. "
        "Le script check_v11_vs_mr2.py suppose un échantillon 100 % Std : "
        "il n'a pas été appliqué à ce sous-ensemble mixte."
    )

# ------------------------------------------------ 7. validation (fixture)
elif page == "Validation (fixture)":
    header(
        "Jeu fabriqué — contrôle",
        "Validation sur fixture",
        [("sample-fixture-v11", "fixture"), ("non production", "fixture")],
    )
    lead(
        "sample-fixture-v11 est un jeu de test fabriqué depuis les 5 foyers "
        "de l'échantillon : ce n'est pas une sortie de MR1."
    )
    if monthly_fixture is None or not len(monthly_fixture):
        missing_export("sql/p08_dashboard_export_fixture.sql")
        st.stop()
    f = monthly_fixture.copy()
    kpis([
        ("Lignes foyer × mois", n0(len(f))),
        ("Énergie", f"{n0(f['monthly_kwh'].sum())} kWh"),
        ("Coût 2013", f"{gb(f['estimated_cost_gbp'].sum())} GBP"),
        ("Coûts NULL", n0(f["estimated_cost_gbp"].isna().sum())),
    ])
    t = f.assign(mois=f["period"].astype(str).str.slice(0, 7))
    fig = px.bar(
        t.groupby(["mois", "quality_flag"], as_index=False)
        .agg(kwh=("monthly_kwh", "sum")),
        x="mois", y="kwh", color="quality_flag",
        color_discrete_map=QUALITY_COLORS,
        title="kWh par mois et indicateur qualité",
        labels={"mois": "mois", "kwh": "kWh", "quality_flag": "qualité"},
    )
    show(fig, height=360, legend_title="Qualité")
    section("Détail mensuel")
    st.dataframe(monthly_table(f), width="stretch", hide_index=True)
    st.caption(
        "Coût NULL = mois hors calendrier tarifaire 2013 (jamais 0). "
        "Controle attendu : 108 lignes, 55 ok / 5 partial_data / 48 no_tariff, "
        "2 321,437773 GBP. Comparaison pandas independante : ecart <= 1e-6 par ligne."
    )
    source_note(
        "Source : lh.test.monthly, run_id=fixture-sample-v11. "
        "La fixture est isolée de la production. Une hypothèse non vérifiée "
        "porte sur la convention d'horodatage, avec environ 3 100 lectures concernées."
    )

# ---------------------------------------------------------------- 8. qualité
elif page == "Qualite":
    header(
        "Contrôle de la chaîne",
        "Qualité des données",
        [("MR1 v1", "legacy"), ("n_missing dérivé", "legacy")],
    )
    lead(
        "Cette vue vient de lh.p08.daily, contrat MR1 v1 à 4 colonnes. "
        "Le nombre de créneaux manquants y est dérivé, pas mesuré."
    )
    if daily is None:
        missing_export("sql/p08_dashboard_export.sql")
        st.stop()
    kpis([
        ("Jours-foyers", n0(len(daily))),
        ("Créneaux moyens", f"{daily['n_slots'].mean():.1f} / 48"),
        ("Jours incomplets", n0((daily["n_slots"] < 48).sum())),
        ("Qualité OK", n0((daily["quality_flag"] == "ok").sum())),
    ])
    fig = px.histogram(
        daily, x="n_slots", nbins=48,
        color_discrete_sequence=[PALETTE[0]],
        labels={"n_slots": "créneaux réellement sommés (sur 48)"},
        title="Nombre de créneaux par jour",
    )
    show(fig, height=330)
    q = daily.groupby("quality_flag").size().reset_index(name="jours")
    fig = px.bar(
        q, x="quality_flag", y="jours", text=q["jours"].map(n0),
        color="quality_flag", color_discrete_map=QUALITY_COLORS,
        labels={"quality_flag": "qualité", "jours": "jours-foyers"},
        title="Indicateurs qualité",
    )
    fig.update_traces(textposition="outside")
    show(fig, height=330, legend_title="Qualité")
    st.caption(
        "Cette vue vient de `lh.p08.daily` (MR1 v1, 4 colonnes) : `n_missing_slots` y est "
        "**dérivé** (48 - n_slots), pas mesuré. Le vrai `n_missing_slots` du contrat v1.1 "
        "(jour local, DST 46/48/50) est sur la page **Run reel v1.1**."
    )
    source_note("Source : lh.p08.daily, export sql/p08_dashboard_export.sql.")

# ------------------------------------------------------------ 9. Std vs ToU
elif page == "Std vs ToU":
    header(
        "Comparaison tarifaire",
        "Std vs ToU",
        [("40 Std + 10 ToU", "real"), ("test ToU synthétique", "fixture")],
    )
    lead(
        "MR1 v1.1 fournit bien tariff_group. L'échantillon 5 foyers était "
        "exclusivement Std ; le run 50 foyers ajoute 40 Std + 10 ToU réels."
    )
    if monthly_50mix is not None and len(monthly_50mix):
        m = monthly_50mix.copy()
        g = m.groupby("tariff_group", as_index=False).agg(
            foyers=("lclid", "nunique"), lignes=("lclid", "size"),
            kwh=("monthly_kwh", "sum"), cout=("estimated_cost_gbp", "sum"))
        view = g.rename(columns={
            "tariff_group": "Groupe", "foyers": "Foyers", "lignes": "Lignes",
            "kwh": "Énergie (kWh)", "cout": "Coût (GBP)",
        })
        view["Énergie (kWh)"] = view["Énergie (kWh)"].map(n3)
        view["Coût (GBP)"] = view["Coût (GBP)"].map(gb)
        section("Run réel 50 foyers — répartition")
        st.dataframe(view, width="stretch", hide_index=True)
        left, right = st.columns(2)
        with left:
            fig = px.bar(
                g, x="tariff_group", y="kwh", text=g["kwh"].map(n0),
                color="tariff_group", color_discrete_map=GROUP_COLORS,
                title="Énergie (kWh)", labels={"tariff_group": "groupe", "kwh": "kWh"},
            )
            fig.update_traces(textposition="outside")
            show(fig, height=320, legend_title="Groupe")
        with right:
            fig = px.bar(
                g, x="tariff_group", y="cout", text=g["cout"].map(gb),
                color="tariff_group", color_discrete_map=GROUP_COLORS,
                title="Coût 2013 (GBP)",
                labels={"tariff_group": "groupe", "cout": "GBP"},
            )
            fig.update_traces(textposition="outside")
            show(fig, height=320, legend_title="Groupe")
    else:
        st.info("Export du run 50 foyers absent.")
    section("Preuve ToU synthétique")
    if monthly_test is not None and "tou-test-mr2" in set(monthly_test["dataset_version"]):
        st.caption("Seule preuve disponible : la ligne du test ToU du 19/01/2013.")
        t = monthly_test[monthly_test["dataset_version"] == "tou-test-mr2"].copy()
        t["period"] = pd.to_datetime(t["period"])
        t["Mois"] = t["period"].dt.strftime("%Y-%m")
        t["Coût"] = t["estimated_cost_gbp"].map(cost_text)
        st.dataframe(t[["Mois", "lclid", "monthly_kwh", "Coût", "price_coverage"]]
                     .rename(columns={
                         "lclid": "Foyer", "monthly_kwh": "Énergie (kWh)",
                         "price_coverage": "Couverture",
                     }), width="stretch", hide_index=True)
    else:
        st.info("Ligne de test ToU absente de l'export.")
    st.caption(
        "Ne pas appliquer check_v11_vs_mr2.py au run 50 foyers : le script suppose "
        "un échantillon entièrement Std. Aucun script compare_std_tou n'est présent "
        "dans le dépôt."
    )
    source_note(
        "Sources : sql/p08_50mix.sql (groupes tarifaires) et lh.test.monthly "
        "(ligne de validation ToU)."
    )

# --------------------------------------------------------------- 10. modèles
elif page == "Modeles (documentation)":
    header(
        "Branche parallèle",
        "Résultats des modèles",
        [("Lecture seule", "neutral"), ("GRU + autoencodeur", "model")],
    )
    st.info(DL_NOTICE)
    tabs = st.tabs(["GRU 24 h", "Prédictions Iceberg", "Autoencodeur jour"])
    b = load_file(str(D_DL / "baseline_24h_metrics.csv"))
    g = load_file(str(D_DL / "gru_test_runA_l1_metrics.csv"))
    a = load_file(str(D_DL / "ae_day_val_errors.csv"))

    with tabs[0]:
        if b is not None:
            section("Baselines 24 h (test, kWh réels)")
            st.dataframe(b, width="stretch", hide_index=True)
        if g is not None:
            fig = px.line(
                g, x="horizon_h", y=["MAE_GRU", "MAE_saisonnier"],
                color_discrete_sequence=[PALETTE[0], PALETTE[1]],
                labels={"horizon_h": "horizon (h)", "value": "MAE (kWh)",
                        "variable": "modèle"},
                title="GRU runA_l1 vs saisonnier — MAE par horizon (test)",
            )
            show(fig, height=420, hover="x unified", legend_title="Modèle")
            st.caption("Test lu **une seule fois** (journal test_seen.json). "
                       "MAE poolé 0,1980 vs 0,2014 (gain faible).")
        if b is None and g is None:
            st.info("Aucun fichier de métriques GRU local.")

    with tabs[1]:
        if dl_preds is not None:
            d = dl_preds.copy()
            d["target_hour"] = pd.to_datetime(d["target_hour"])
            meilleur = int((d["abs_err_gru"] < d["abs_err_seasonal"]).sum())
            kpis([
                ("Lignes", n0(len(d))),
                ("Foyers", n0(d["lclid"].nunique())),
                ("MAE GRU", f"{d['abs_err_gru'].mean():.4f} kWh"),
                ("MAE saisonnier", f"{d['abs_err_seasonal'].mean():.4f} kWh"),
            ])
            st.caption(
                f"Source : lh.p08.dl_predictions (modèle {d['model_tag'].iloc[0]}, "
                f"split {d['split_name'].iloc[0]}), hash test {d['test_hash'].iloc[0]}, "
                f"commit {d['git_commit'].iloc[0]}"
                f" - {d['target_hour'].min():%Y-%m-%d %H:%M} à "
                f"{d['target_hour'].max():%Y-%m-%d %H:%M}. GRU meilleur sur "
                f"{n0(meilleur)} / {n0(len(d))} horizons. Branche parallèle à Job 2 "
                "(source = série MR1, jamais le mensuel)."
            )
            st.dataframe(
                d.sort_values(["lclid", "target_hour", "horizon_h"]).head(200),
                width="stretch", hide_index=True,
            )
            st.caption(f"Extrait des 200 premières lignes sur {n0(len(d))} lignes "
                       "de la table Iceberg.")
        else:
            st.info(
                "Export DL manquant : lancez scripts/export_dl_predictions.py, "
                "puis sql/p08_dl_predictions.sql et sql/p08_dashboard_export_dl.sql."
            )

    with tabs[2]:
        if a is not None:
            e = a["err_kwh"]
            kpis([
                ("P50", f"{e.quantile(.50):.4f} kWh/h"),
                ("P90", f"{e.quantile(.90):.4f} kWh/h"),
                ("Seuil = P95", f"{e.quantile(.95):.4f} kWh/h"),
            ])
            st.caption("Résultat **négatif** documenté : 12,4 % de détection à 1 % de fausses "
                       "alertes < 40 % pré-enregistré → test jamais lu.")
        else:
            st.info("Aucun fichier de métriques autoencodeur local.")

    source_note(
        "Sources : data/processed/dl/ (métriques locales) et lh.p08.dl_predictions. "
        "Le test n'est lu qu'une fois pour le GRU sélectionné. "
        "Aucun run GPU des modèles retenus n'est documenté."
    )

st.markdown(
    '<div class="p08-footer">P08 · 10 pages · 50 foyers par défaut · '
    'tableau de bord en lecture seule</div>',
    unsafe_allow_html=True,
)
