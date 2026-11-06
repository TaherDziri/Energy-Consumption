# PHASE 1 SUMMARY – Environment & Dataset
## P08 – Intelligent Energy Consumption Analysis
**Developer:** Rahma (Person 2) | **Branch:** `solo-Rahma`
**Date:** 2026-11-04

---

## 1. Phase Objective
Verify the complete development environment, set up the GitHub repository,
download and inspect the London Smart Meter dataset and the Tariffs file,
and create a manageable development sample for local testing.

---

## 2. Tasks Completed
- [x] Java 21.0.9 verified
- [x] Maven 3.9.12 verified
- [x] Python 3.14 (system) identified as incompatible with PyTorch
- [x] Miniconda installed → p08-env created with Python 3.11.18
- [x] PyTorch 2.6.0+cu124 installed → GPU (RTX 2050) confirmed working
- [x] numpy, pandas, scikit-learn, matplotlib, seaborn, streamlit installed
- [x] openpyxl installed (for Excel tariff file)
- [x] GitHub repository cloned: https://github.com/TaherDziri/Energy-Consumption
- [x] Branch `solo-Rahma` created locally and pushed to GitHub
- [x] .gitignore committed (data files excluded)
- [x] README.md committed
- [x] Project folder structure created
- [x] CC_LCL-FullData.csv (8.54 GB) moved to data/
- [x] Tariffs.xlsx moved to data/
- [x] Dataset columns and types inspected
- [x] Tariffs file inspected and understood
- [x] Development sample (5 Std households, 152,811 rows) created
- [ ] ToU households sample – in progress

---

## 3. Technologies Used
| Tool | Version | Purpose |
|---|---|---|
| Java | 21.0.9 LTS | MapReduce development |
| Maven | 3.9.12 | Java build tool |
| Miniconda | 26.9.4 | Python environment manager |
| Python | 3.11.18 (p08-env) | Deep Learning + data scripts |
| PyTorch | 2.6.0+cu124 | GRU + Autoencoder models |
| CUDA | 12.4 | GPU acceleration (RTX 2050) |
| pandas | latest | Dataset inspection |
| openpyxl | latest | Tariffs Excel reading |
| Git | system | Version control |

---

## 4. Dataset Profile

### Main Dataset: CC_LCL-FullData.csv
| Property | Value |
|---|---|
| Size | 8.54 GB |
| Estimated rows | ~167 million |
| Households | ~5,567 |
| Period | 2012-01-30 → 2014-02-28 |
| Frequency | Every 30 minutes |

### Columns (original → normalized)
| Original column | Normalized name | Type | Notes |
|---|---|---|---|
| `LCLid` | `household_id` | String | e.g. MAC000002 |
| `stdorToU` | `tariff_group` | String | Std or ToU |
| `DateTime` | `event_time` | String | Format: 2012-10-12 00:30:00.0000000 |
| `KWH/hh (per half hour) ` | `energy_kwh` | float64 | ⚠️ Trailing space in original name |

### Sample Profile (5 Std households)
| Metric | Value |
|---|---|
| Rows | 152,811 |
| KWH min | 0.0000 |
| KWH max | 3.921 kWh |
| KWH mean | 0.1862 kWh |
| NaN values | 5 |
| Zeros | 26,229 (17%) |
| Negatives | 0 |

### Tariffs File: Tariffs.xlsx
| Property | Value |
|---|---|
| Columns | TariffDateTime, Tariff |
| Rows | 17,520 (365 days × 48 slots) |
| Coverage | 2013-01-01 → 2013-12-31 ONLY |
| Levels | Normal (86%), Low (9.5%), High (4.5%) |

### Tariff Price Reference
| Group | Level | Price |
|---|---|---|
| Std | Flat rate | 14.228 p/kWh |
| ToU | High | 67.20 p/kWh |
| ToU | Normal | 11.76 p/kWh |
| ToU | Low | 3.99 p/kWh |

> ⚠️ Dynamic tariffs apply ONLY to 2013 documented periods.
> Cost formula: cost (£) = energy_kwh × tariff_price_pence / 100

---

## 5. Data Quality Flags Identified
| Issue | Count | Decision |
|---|---|---|
| Trailing space in KWH column name | Present | Strip with `.str.strip()` |
| DateTime has 7 decimal zeros | All rows | Parse with pandas `str.split()` or `pd.to_datetime()` |
| Zero KWH readings | 26,229 (17%) | Keep as valid — flag with `quality_flag=zero_reading` |
| NaN KWH values | 5 | Quarantine — flag with `quality_flag=missing` |
| Negative KWH values | 0 | No action needed |
| All Std in beginning | First 10+ households | ToU households appear later in file |

---

## 6. Files Created or Modified
| File | Location | Purpose |
|---|---|---|
| `.gitignore` | `Energy-Consumption/` | Excludes data, JARs, Python cache |
| `README.md` | `Energy-Consumption/` | Project overview |
| `data/CC_LCL-FullData.csv` | `data/` | Full dataset (not in git) |
| `data/Tariffs.xlsx` | `data/` | Tariff calendar 2013 (not in git) |
| `data/sample/sample_5households.csv` | `data/sample/` | Dev sample – Std only |
| `data/sample/sample_8households.csv` | `data/sample/` | Dev sample – Std + ToU (in progress) |

---

## 7. Commands Executed
```bash
# Environment verification
java -version
mvn -version
python --version
conda --version

# Conda setup
conda tos accept (x3)
conda create -n p08-env python=3.11 -y
conda activate p08-env

# Package installation
pip install torch torchvision torchaudio --index-url https://download.pytorch.org/whl/cu124
pip install numpy pandas scikit-learn matplotlib seaborn streamlit openpyxl

# GPU verification
python -c "import torch; print(torch.cuda.is_available())"

# Git setup
git clone https://github.com/TaherDziri/Energy-Consumption.git
git checkout -b solo-Rahma
git add .
git commit -m "Initial project structure - solo-Rahma branch"
git push -u origin solo-Rahma
```

---

## 8. Problems Encountered and Solutions
| Problem | Cause | Solution |
|---|---|---|
| `New-Item` not found | Running cmd.exe not PowerShell | Used `notepad` command instead |
| Git clone permission denied | Running from C:\WINDOWS\System32 | Ran from PROJET folder |
| `conda` not recognized | PATH missing miniconda paths | Added 3 paths to Windows environment variables |
| conda create TOS error | Terms not accepted | Ran `conda tos accept` for 3 channels |
| conda activate no effect in PowerShell | PowerShell not initialized for conda | Switched to cmd.exe |
| `openpyxl` not found | Not installed by default | `pip install openpyxl` |
| All sample households are Std | ToU households appear later in file | Running extended scan for ToU households |

---

## 9. Current Project Status
| Component | Status |
|---|---|
| Java + Maven | ✅ Ready |
| Python 3.11 environment | ✅ Ready |
| PyTorch 2.6 + GPU | ✅ Ready |
| GitHub repository | ✅ Ready |
| Dataset (full) | ✅ Available locally |
| Tariffs file | ✅ Understood |
| Development sample (Std) | ✅ Created |
| Development sample (ToU) | 🔄 In progress |
| Hadoop | ❌ Not installed |
| Spark | ❌ Not installed |

---

## 10. Next Phase – Phase 2: Hadoop Installation & MapReduce

### Objectives
- Install Apache Hadoop 3.4.1 on Windows
- Configure HDFS (namenode, datanode, zones)
- Create HDFS zone structure: raw, silver, quarantine, gold
- Upload development sample to HDFS
- Implement MapReduce Job 2 (monthly aggregation + cost estimation)
- Compile and execute MR2 Java application
- Validate results against manual calculations

### Key Decision Needed
Hadoop on Windows can be installed three ways:
1. **WSL2** (Windows Subsystem for Linux) — Recommended
2. **Docker** — Cleanest but needs Docker Desktop
3. **Native Windows** — Requires winutils.exe, more complex

---

## Progress Checklist
### PHASE 1
- [x] OS, Java, Python, Maven confirmed
- [x] GitHub cloned, `solo-Rahma` branch created
- [x] .gitignore committed
- [x] Dataset downloaded locally
- [x] Dataset structure inspected
- [x] Tariffs file inspected
- [x] Development sample created (Std)
- [ ] Development sample with ToU households
- [ ] Dataset profile document in docs/

### PHASE 2 (not started)
- [ ] Hadoop installed
- [ ] HDFS configured
- [ ] HDFS zones created
- [ ] Sample data uploaded to HDFS
- [ ] MR2 Java project created
- [ ] MR2 compiled and executed
- [ ] Results validated
