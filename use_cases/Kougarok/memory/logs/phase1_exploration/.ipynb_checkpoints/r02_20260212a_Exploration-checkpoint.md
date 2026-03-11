# Exploration

**Site:** Kougarok
**Phase:** 1 - Exploration
**Round:** 2 | **Iteration:** 1
**Date:** 2026-02-12 12:53:22

---

## Ensemble Status

| Metric | Value |
|--------|-------|
| Total Cases | 4890 |
| Completed | 4890 |
| Failed | 0 |
| Incomplete | 0 |
| Completion Rate | 100.0% |

---

## AI Reasoning and Analysis

## Morris Sensitivity Analysis Summary

### Abg Biomass

**PFT7** - Top 5 most sensitive parameters:

  1. `phen_gddthresh_c`: μ*=0.690, σ=1.070
  2. `turnover_leaf_7`: μ*=0.266, σ=0.664
  3. `nfix1_9`: μ*=0.249, σ=1.200
  4. `pid_kp_7`: μ*=0.222, σ=1.094
  5. `vmax_ptase_7`: μ*=0.212, σ=0.652

**PFT9** - Top 5 most sensitive parameters:

  1. `phen_gddthresh_c`: μ*=0.120, σ=0.179
  2. `alloc_storage_cushion_7`: μ*=0.104, σ=0.231
  3. `l2fr_ini_9`: μ*=0.102, σ=0.235
  4. `alloc_storage_cushion_9`: μ*=0.098, σ=0.269
  5. `l2fr_ini_7`: μ*=0.082, σ=0.232

**PFT10** - Top 5 most sensitive parameters:

  1. `phen_gddthresh_c`: μ*=0.065, σ=0.098
  2. `allom_dbh_maxheight_7`: μ*=0.045, σ=0.201
  3. `leaf_vcmax25top_7`: μ*=0.046, σ=0.140
  4. `alloc_store_priority_frac_9`: μ*=0.036, σ=0.192
  5. `allom_d2bl2_10`: μ*=0.058, σ=0.213

### Leaf Biomass

**PFT7** - Top 5 most sensitive parameters:

  1. `phen_gddthresh_c`: μ*=0.092, σ=0.153
  2. `turnover_leaf_7`: μ*=0.031, σ=0.075
  3. `vmax_ptase_7`: μ*=0.035, σ=0.107
  4. `recruit_seed_alloc_7`: μ*=0.023, σ=0.080
  5. `recruit_seed_supplement_9`: μ*=0.026, σ=0.074

**PFT9** - Top 5 most sensitive parameters:

  1. `phen_gddthresh_c`: μ*=0.010, σ=0.016
  2. `l2fr_ini_9`: μ*=0.011, σ=0.026
  3. `phos_store_ratio_9`: μ*=0.009, σ=0.017
  4. `pid_ki_9`: μ*=0.008, σ=0.014
  5. `alloc_storage_cushion_7`: μ*=0.007, σ=0.017

**PFT10** - Top 5 most sensitive parameters:

  1. `phen_gddthresh_c`: μ*=0.009, σ=0.012
  2. `nitr_store_ratio_10`: μ*=0.007, σ=0.017
  3. `km_nh4_9`: μ*=0.007, σ=0.026
  4. `l2fr_ini_10`: μ*=0.005, σ=0.024
  5. `allom_d2bl2_9`: μ*=0.004, σ=0.009

### Fineroot Biomass

**PFT7** - Top 5 most sensitive parameters:

  1. `phen_gddthresh_c`: μ*=0.190, σ=0.321
  2. `nitr_store_ratio_7`: μ*=0.131, σ=0.280
  3. `phos_retrans_10`: μ*=0.105, σ=0.498
  4. `alloc_storage_cushion_9`: μ*=0.099, σ=0.402
  5. `stoich_phos_leaf_7`: μ*=0.096, σ=0.191

**PFT9** - Top 5 most sensitive parameters:

  1. `phen_gddthresh_c`: μ*=0.090, σ=0.129
  2. `alloc_storage_cushion_7`: μ*=0.045, σ=0.117
  3. `microb_bio_10`: μ*=0.047, σ=0.116
  4. `pid_ki_9`: μ*=0.045, σ=0.082
  5. `l2fr_ini_9`: μ*=0.046, σ=0.104

**PFT10** - Top 5 most sensitive parameters:

  1. `phen_gddthresh_c`: μ*=0.048, σ=0.078
  2. `leaf_vcmax25top_7`: μ*=0.035, σ=0.103
  3. `fnrt_prof_a_7`: μ*=0.029, σ=0.096
  4. `alpha_ptase_10`: μ*=0.023, σ=0.055
  5. `fnrt_prof_b_7`: μ*=0.025, σ=0.074

### Output Files

- **abg_biomass**: 30 trajectories
  - Plot: `/global/homes/j/jingtao/A2MC/use_cases/Kougarok/memory/phase_results/phase1_exploration/morris_abg_biomass_sensitivity_20260212_125317.png`
  - CSV: `/global/homes/j/jingtao/A2MC/use_cases/Kougarok/memory/phase_results/phase1_exploration/morris_abg_biomass_rankings_20260212_125317.csv`
- **leaf_biomass**: 30 trajectories
  - Plot: `/global/homes/j/jingtao/A2MC/use_cases/Kougarok/memory/phase_results/phase1_exploration/morris_leaf_biomass_sensitivity_20260212_125318.png`
  - CSV: `/global/homes/j/jingtao/A2MC/use_cases/Kougarok/memory/phase_results/phase1_exploration/morris_leaf_biomass_rankings_20260212_125318.csv`
- **fineroot_biomass**: 30 trajectories
  - Plot: `/global/homes/j/jingtao/A2MC/use_cases/Kougarok/memory/phase_results/phase1_exploration/morris_fineroot_biomass_sensitivity_20260212_125320.png`
  - CSV: `/global/homes/j/jingtao/A2MC/use_cases/Kougarok/memory/phase_results/phase1_exploration/morris_fineroot_biomass_rankings_20260212_125320.csv`

---

## Issues Encountered

*No issues recorded*

---

## Metadata

```json
{
  "iteration": 1,
  "scheme": "morris",
  "analysis_complete": true,
  "sensitivity_rankings": {
    "abg_biomass": {
      "PFT7": [
        {
          "rank": 1,
          "parameter": "phen_gddthresh_c",
          "mu": 0.679221172466784,
          "mu_star": 0.6898168880223637,
          "sigma": 1.0699362710373392,
          "type": "Phenology"
        },
        {
          "rank": 2,
          "parameter": "turnover_leaf_7",
          "mu": 0.22378726042376848,
          "mu_star": 0.2655668538664775,
          "sigma": 0.6638956429379596,
          "type": "Turnover"
        },
        {
          "rank": 3,
          "parameter": "nfix1_9",
          "mu": -0.21425171683566308,
          "mu_star": 0.24861679598369826,
          "sigma": 1.2003553486522716,
          "type": "N"
        },
        {
          "rank": 4,
          "parameter": "pid_kp_7",
          "mu": -0.21283605372248107,
          "mu_star": 0.22227370187630704,
          "sigma": 1.0939303067375135,
          "type": "Allocation"
        },
        {
          "rank": 5,
          "parameter": "vmax_ptase_7",
          "mu": -0.18313999095883104,
          "mu_star": 0.2116833558672764,
          "sigma": 0.6519635260789992,
          "type": "P"
        },
        {
          "rank": 6,
          "parameter": "allom_d2bl1_7",
          "mu": -0.18296745892325844,
          "mu_star": 0.21364860520287918,
          "sigma": 0.9198552606689989,
          "type": "Allometry"
        },
        {
          "rank": 7,
          "parameter": "recruit_height_min_7",
          "mu": -0.17274228764244942,
          "mu_star": 0.25679781402946805,
          "sigma": 1.1120917600602307,
          "type": "Allometry"
        },
        {
          "rank": 8,
          "parameter": "allom_d2bl1_10",
          "mu": -0.1716821232798321,
          "mu_star": 0.18509691685934554,
          "sigma": 0.7956930193844779,
          "type": "Allometry"
        },
        {
          "rank": 9,
          "parameter": "alloc_storage_cushion_7",
          "mu": -0.17107804417220995,
          "mu_star": 0.4009681729713824,
          "sigma": 1.397645965197358,
          "type": "Allocation"
        },
        {
          "rank": 10,
          "parameter": "vmax_no3_10",
          "mu": -0.16334238960385808,
          "mu_star": 0.21959148687028948,
          "sigma": 0.9686858253820534,
          "type": "N"
        }
      ],
      "PFT9": [
        {
          "rank": 1,
          "parameter": "phen_gddthresh_c",
          "mu": -0.11532818892770003,
          "mu_star": 0.11977683266803335,
          "sigma": 0.1792718537577833,
          "type": "Phenology"
        },
        {
          "rank": 2,
          "parameter": "alloc_storage_cushion_7",
          "mu": -0.10147206463902077,
          "mu_star": 0.10447473152445577,
          "sigma": 0.23110981079657109,
          "type": "Allocation"
        },
        {
          "rank": 3,
          "parameter": "l2fr_ini_9",
          "mu": -0.09177493034491833,
          "mu_star": 0.10155018012252168,
          "sigma": 0.23455149321293298,
          "type": "Allocation"
        },
        {
          "rank": 4,
          "parameter": "alloc_storage_cushion_9",
          "mu": 0.07564198994200919,
          "mu_star": 0.09804673846050418,
          "sigma": 0.2690702323394613,
          "type": "Allocation"
        },
        {
          "rank": 5,
          "parameter": "l2fr_ini_7",
          "mu": -0.07373314045466559,
          "mu_star": 0.08247529000058992,
          "sigma": 0.23199781526107094,
          "type": "Allocation"
        },
        {
          "rank": 6,
          "parameter": "phos_store_ratio_9",
          "mu": 0.06939862576716475,
          "mu_star": 0.07621820533804692,
          "sigma": 0.133453558058385,
          "type": "P"
        },
        {
          "rank": 7,
          "parameter": "pid_ki_9",
          "mu": -0.06145568583161746,
          "mu_star": 0.06695749528356747,
          "sigma": 0.1454564119018595,
          "type": "Allocation"
        },
        {
          "rank": 8,
          "parameter": "microb_bio_10",
          "mu": 0.0580178104277875,
          "mu_star": 0.061355933952556334,
          "sigma": 0.1642286177674723,
          "type": "Microbial"
        },
        {
          "rank": 9,
          "parameter": "mort_scalar_hydrfailure_7",
          "mu": -0.05732641635576907,
          "mu_star": 0.05916743607213727,
          "sigma": 0.19950557881848904,
          "type": "Mortality"
        },
        {
          "rank": 10,
          "parameter": "fnrt_prof_b_9",
          "mu": -0.05692033912489168,
          "mu_star": 0.06174542866034668,
          "sigma": 0.15319098083945876,
          "type": "Turnover"
        }
      ],
      "PFT10": [
        {
          "rank": 1,
          "parameter": "phen_gddthresh_c",
          "mu": -0.06246019684974112,
          "mu_star": 0.06530119683184112,
          "sigma": 0.09786591559175811,
          "type": "Phenology"
        },
        {
          "rank": 2,
          "parameter": "allom_dbh_maxheight_7",
          "mu": -0.042354087024735206,
          "mu_star": 0.04471954518725137,
          "sigma": 0.20082704351088965,
          "type": "Allometry"
        },
        {
          "rank": 3,
          "parameter": "leaf_vcmax25top_7",
          "mu": 0.04034378836174226,
          "mu_star": 0.04621124459510708,
          "sigma": 0.13974928679649806,
          "type": "Allometry"
        },
        {
          "rank": 4,
          "parameter": "alloc_store_priority_frac_9",
          "mu": 0.035457029509206664,
          "mu_star": 0.035874069874276666,
          "sigma": 0.19173470435624648,
          "type": "Allocation"
        },
        {
          "rank": 5,
          "parameter": "allom_d2bl2_10",
          "mu": 0.03175389942083035,
          "mu_star": 0.05759769370897086,
          "sigma": 0.21251885889645983,
          "type": "Allometry"
        },
        {
          "rank": 6,
          "parameter": "nitr_retrans_7",
          "mu": 0.03041744130720401,
          "mu_star": 0.03484212395527733,
          "sigma": 0.1455641364884769,
          "type": "N"
        },
        {
          "rank": 7,
          "parameter": "km_nh4_7",
          "mu": 0.0289593449076198,
          "mu_star": 0.030988818664060034,
          "sigma": 0.11980784716325954,
          "type": "N"
        },
        {
          "rank": 8,
          "parameter": "fnrt_prof_a_7",
          "mu": 0.022153663824617927,
          "mu_star": 0.024788963584654225,
          "sigma": 0.0763895744643078,
          "type": "Turnover"
        },
        {
          "rank": 9,
          "parameter": "stoich_phos_leaf_10",
          "mu": -0.021429394014231166,
          "mu_star": 0.031332585426389496,
          "sigma": 0.08064363549374318,
          "type": "P"
        },
        {
          "rank": 10,
          "parameter": "maintresp_nonleaf_baserate",
          "mu": 0.020876422930286003,
          "mu_star": 0.022952044967567333,
          "sigma": 0.10075947856370922,
          "type": "Other"
        }
      ]
    },
    "leaf_biomass": {
      "PFT7": [
        {
          "rank": 1,
          "parameter": "phen_gddthresh_c",
          "mu": 0.09000767701875925,
          "mu_star": 0.09164154971540187,
          "sigma": 0.15284475981692663,
          "type": "Phenology"
        },
        {
          "rank": 2,
          "parameter": "turnover_leaf_7",
          "mu": 0.029396405641046102,
          "mu_star": 0.030774755737304673,
          "sigma": 0.07504708998856466,
          "type": "Turnover"
        },
        {
          "rank": 3,
          "parameter": "vmax_ptase_7",
          "mu": -0.02644687355989076,
          "mu_star": 0.03465997972508022,
          "sigma": 0.10713735979916955,
          "type": "P"
        },
        {
          "rank": 4,
          "parameter": "recruit_seed_alloc_7",
          "mu": 0.019454203567307937,
          "mu_star": 0.023283449047912155,
          "sigma": 0.08016753978406083,
          "type": "Allocation"
        },
        {
          "rank": 5,
          "parameter": "recruit_seed_supplement_9",
          "mu": 0.018463747586189867,
          "mu_star": 0.02626968373672228,
          "sigma": 0.07414756328836562,
          "type": "Other"
        },
        {
          "rank": 6,
          "parameter": "maintresp_nonleaf_baserate",
          "mu": 0.018264620963699723,
          "mu_star": 0.020277516133828645,
          "sigma": 0.08912267512002392,
          "type": "Other"
        },
        {
          "rank": 7,
          "parameter": "allom_d2h1_7",
          "mu": -0.017482391719155613,
          "mu_star": 0.023894834190397802,
          "sigma": 0.0739297534809173,
          "type": "Allometry"
        },
        {
          "rank": 8,
          "parameter": "vmax_p_7",
          "mu": -0.01742276244973357,
          "mu_star": 0.05027026882830901,
          "sigma": 0.12978843457763942,
          "type": "P"
        },
        {
          "rank": 9,
          "parameter": "recruit_seed_supplement_7",
          "mu": 0.017013785827569107,
          "mu_star": 0.021655774058560402,
          "sigma": 0.08194651147620387,
          "type": "Other"
        },
        {
          "rank": 10,
          "parameter": "stoich_phos_fineroot_10",
          "mu": -0.01573458108858285,
          "mu_star": 0.024597034418073975,
          "sigma": 0.0906694820971503,
          "type": "P"
        }
      ],
      "PFT9": [
        {
          "rank": 1,
          "parameter": "phen_gddthresh_c",
          "mu": -0.009866883795429791,
          "mu_star": 0.010369546730446457,
          "sigma": 0.016142495935830687,
          "type": "Phenology"
        },
        {
          "rank": 2,
          "parameter": "l2fr_ini_9",
          "mu": -0.008808459673503,
          "mu_star": 0.010600076095532,
          "sigma": 0.025695829776876206,
          "type": "Allocation"
        },
        {
          "rank": 3,
          "parameter": "phos_store_ratio_9",
          "mu": 0.007858453654912174,
          "mu_star": 0.008529209138737176,
          "sigma": 0.01726036619144817,
          "type": "P"
        },
        {
          "rank": 4,
          "parameter": "pid_ki_9",
          "mu": -0.007019741649794279,
          "mu_star": 0.008122472867657613,
          "sigma": 0.014375619078809127,
          "type": "Allocation"
        },
        {
          "rank": 5,
          "parameter": "alloc_storage_cushion_7",
          "mu": -0.006772406772566424,
          "mu_star": 0.006921790806343256,
          "sigma": 0.017386384387563448,
          "type": "Allocation"
        },
        {
          "rank": 6,
          "parameter": "alloc_storage_cushion_10",
          "mu": -0.004286697852148751,
          "mu_star": 0.004679377013015752,
          "sigma": 0.01420914100020433,
          "type": "Allocation"
        },
        {
          "rank": 7,
          "parameter": "microb_bio_10",
          "mu": 0.003974585730996824,
          "mu_star": 0.004467854492747509,
          "sigma": 0.014288793853524941,
          "type": "Microbial"
        },
        {
          "rank": 8,
          "parameter": "recruit_seed_supplement_10",
          "mu": -0.0038827019849680877,
          "mu_star": 0.004840748862193173,
          "sigma": 0.017600006972553126,
          "type": "Other"
        },
        {
          "rank": 9,
          "parameter": "nitr_store_ratio_9",
          "mu": 0.0038377503760724015,
          "mu_star": 0.004945288011958434,
          "sigma": 0.013062228454396635,
          "type": "N"
        },
        {
          "rank": 10,
          "parameter": "fnrt_prof_b_9",
          "mu": -0.0038117453312674168,
          "mu_star": 0.00448414493122575,
          "sigma": 0.00921742927931022,
          "type": "Turnover"
        }
      ],
      "PFT10": [
        {
          "rank": 1,
          "parameter": "phen_gddthresh_c",
          "mu": -0.009005498575205247,
          "mu_star": 0.00914653995182358,
          "sigma": 0.011803401382666601,
          "type": "Phenology"
        },
        {
          "rank": 2,
          "parameter": "nitr_store_ratio_10",
          "mu": 0.005087229683047342,
          "mu_star": 0.0065701208114140085,
          "sigma": 0.01688113188347128,
          "type": "N"
        },
        {
          "rank": 3,
          "parameter": "km_nh4_9",
          "mu": 0.0047201921393426275,
          "mu_star": 0.006768245514007645,
          "sigma": 0.026028408043264235,
          "type": "N"
        },
        {
          "rank": 4,
          "parameter": "l2fr_ini_10",
          "mu": -0.004129054807824099,
          "mu_star": 0.005399063395607934,
          "sigma": 0.024417936344600363,
          "type": "Allocation"
        },
        {
          "rank": 5,
          "parameter": "allom_d2bl2_9",
          "mu": -0.0032069314964037897,
          "mu_star": 0.0035160662504274466,
          "sigma": 0.009261902075531406,
          "type": "Allometry"
        },
        {
          "rank": 6,
          "parameter": "pid_ki_10",
          "mu": -0.003005735365391672,
          "mu_star": 0.0032502557908878583,
          "sigma": 0.00799542446375155,
          "type": "Allocation"
        },
        {
          "rank": 7,
          "parameter": "fnrt_prof_a_9",
          "mu": 0.0029340971975556174,
          "mu_star": 0.003934800261662284,
          "sigma": 0.012403321783341576,
          "type": "Turnover"
        },
        {
          "rank": 8,
          "parameter": "allom_agb2_10",
          "mu": 0.002706713228624984,
          "mu_star": 0.0036153205637798175,
          "sigma": 0.012281816231834898,
          "type": "Allometry"
        },
        {
          "rank": 9,
          "parameter": "fnrt_prof_b_9",
          "mu": 0.0027065913520385983,
          "mu_star": 0.003497349093239181,
          "sigma": 0.01170139695704559,
          "type": "Turnover"
        },
        {
          "rank": 10,
          "parameter": "leaf_slatop_10",
          "mu": -0.0024725219018853863,
          "mu_star": 0.0032785450799633397,
          "sigma": 0.006170854127905013,
          "type": "Allometry"
        }
      ]
    },
    "fineroot_biomass": {
      "PFT7": [
        {
          "rank": 1,
          "parameter": "phen_gddthresh_c",
          "mu": 0.1792742919664007,
          "mu_star": 0.18995343257689581,
          "sigma": 0.32103202432845895,
          "type": "Phenology"
        },
        {
          "rank": 2,
          "parameter": "nitr_store_ratio_7",
          "mu": 0.10357682337345311,
          "mu_star": 0.13100373167165638,
          "sigma": 0.27966708371470184,
          "type": "N"
        },
        {
          "rank": 3,
          "parameter": "phos_retrans_10",
          "mu": 0.09676674678995875,
          "mu_star": 0.1047410379967657,
          "sigma": 0.49815549430363143,
          "type": "P"
        },
        {
          "rank": 4,
          "parameter": "alloc_storage_cushion_9",
          "mu": -0.0784021689584525,
          "mu_star": 0.09946026844576913,
          "sigma": 0.4022872096547139,
          "type": "Allocation"
        },
        {
          "rank": 5,
          "parameter": "stoich_phos_leaf_7",
          "mu": 0.07517398879995181,
          "mu_star": 0.09606321283820501,
          "sigma": 0.19141549387540338,
          "type": "P"
        },
        {
          "rank": 6,
          "parameter": "vmax_nh4_7",
          "mu": -0.07450842933009724,
          "mu_star": 0.12278401271742806,
          "sigma": 0.30415297409282654,
          "type": "N"
        },
        {
          "rank": 7,
          "parameter": "allom_agb2_7",
          "mu": 0.07142813460339266,
          "mu_star": 0.1414862418918245,
          "sigma": 0.5025601700570039,
          "type": "Allometry"
        },
        {
          "rank": 8,
          "parameter": "vmax_p_10",
          "mu": -0.07112310533180911,
          "mu_star": 0.07643463866172598,
          "sigma": 0.25702154434355723,
          "type": "P"
        },
        {
          "rank": 9,
          "parameter": "recruit_seed_germination_rate_9",
          "mu": 0.07062516241017164,
          "mu_star": 0.0774265282849917,
          "sigma": 0.19566392115806688,
          "type": "Other"
        },
        {
          "rank": 10,
          "parameter": "recruit_seed_supplement_7",
          "mu": 0.059913497883881936,
          "mu_star": 0.0634562160466158,
          "sigma": 0.1738342747813969,
          "type": "Other"
        }
      ],
      "PFT9": [
        {
          "rank": 1,
          "parameter": "phen_gddthresh_c",
          "mu": -0.08545321091880999,
          "mu_star": 0.08980435959084333,
          "sigma": 0.1290105964147096,
          "type": "Phenology"
        },
        {
          "rank": 2,
          "parameter": "alloc_storage_cushion_7",
          "mu": -0.04366757639116629,
          "mu_star": 0.04534369387485963,
          "sigma": 0.11736194601103138,
          "type": "Allocation"
        },
        {
          "rank": 3,
          "parameter": "microb_bio_10",
          "mu": 0.042152547695475176,
          "mu_star": 0.046535773832704144,
          "sigma": 0.11551637502270963,
          "type": "Microbial"
        },
        {
          "rank": 4,
          "parameter": "pid_ki_9",
          "mu": -0.04109742992958284,
          "mu_star": 0.044851728445105175,
          "sigma": 0.08219972463372967,
          "type": "Allocation"
        },
        {
          "rank": 5,
          "parameter": "l2fr_ini_9",
          "mu": -0.04105834960361167,
          "mu_star": 0.045760504696024995,
          "sigma": 0.1041138767554098,
          "type": "Allocation"
        },
        {
          "rank": 6,
          "parameter": "fnrt_prof_b_9",
          "mu": -0.03793139210718503,
          "mu_star": 0.0409671844705333,
          "sigma": 0.09535932820793544,
          "type": "Turnover"
        },
        {
          "rank": 7,
          "parameter": "mort_scalar_hydrfailure_7",
          "mu": -0.0364663332968375,
          "mu_star": 0.03708180430429417,
          "sigma": 0.125324718653762,
          "type": "Mortality"
        },
        {
          "rank": 8,
          "parameter": "turnover_fnrt_7",
          "mu": 0.03502640937984417,
          "mu_star": 0.03948087944128417,
          "sigma": 0.11867595711571788,
          "type": "Turnover"
        },
        {
          "rank": 9,
          "parameter": "km_nh4_7",
          "mu": 0.032897513732848334,
          "mu_star": 0.04092091872996167,
          "sigma": 0.10367422092258018,
          "type": "N"
        },
        {
          "rank": 10,
          "parameter": "phos_store_ratio_9",
          "mu": 0.02848754325270379,
          "mu_star": 0.0423863187112012,
          "sigma": 0.0830224875520012,
          "type": "P"
        }
      ],
      "PFT10": [
        {
          "rank": 1,
          "parameter": "phen_gddthresh_c",
          "mu": -0.045668142101876155,
          "mu_star": 0.04816962998097382,
          "sigma": 0.07753503088156073,
          "type": "Phenology"
        },
        {
          "rank": 2,
          "parameter": "leaf_vcmax25top_7",
          "mu": 0.02861803358195448,
          "mu_star": 0.034508381816497534,
          "sigma": 0.10297558431755022,
          "type": "Allometry"
        },
        {
          "rank": 3,
          "parameter": "fnrt_prof_a_7",
          "mu": 0.026112930348169174,
          "mu_star": 0.02863155572800359,
          "sigma": 0.09579917197980874,
          "type": "Turnover"
        },
        {
          "rank": 4,
          "parameter": "alpha_ptase_10",
          "mu": -0.019395935972620675,
          "mu_star": 0.022512488141625993,
          "sigma": 0.05517111137575257,
          "type": "P"
        },
        {
          "rank": 5,
          "parameter": "fnrt_prof_b_7",
          "mu": -0.01726644379429287,
          "mu_star": 0.02527777962309396,
          "sigma": 0.07369796943145669,
          "type": "Turnover"
        },
        {
          "rank": 6,
          "parameter": "fnrt_prof_a_9",
          "mu": 0.01688252331357566,
          "mu_star": 0.01862495289238601,
          "sigma": 0.053674545681734284,
          "type": "Turnover"
        },
        {
          "rank": 7,
          "parameter": "phos_store_ratio_10",
          "mu": 0.0159696485825054,
          "mu_star": 0.020226953179998765,
          "sigma": 0.07525411052506421,
          "type": "P"
        },
        {
          "rank": 8,
          "parameter": "frag_seed_decay_rate_7",
          "mu": -0.01565399858363069,
          "mu_star": 0.024722789003053438,
          "sigma": 0.06347884854316922,
          "type": "Turnover"
        },
        {
          "rank": 9,
          "parameter": "recruit_seed_supplement_10",
          "mu": -0.014973235808695137,
          "mu_star": 0.049914756757381024,
          "sigma": 0.12821800648149215,
          "type": "Other"
        },
        {
          "rank": 10,
          "parameter": "allom_dbh_maxheight_7",
          "mu": -0.014748436722858584,
          "mu_star": 0.015334696373174656,
          "sigma": 0.0633871394565146,
          "type": "Allometry"
        }
      ]
    }
  },
  "analysis_results": [
    {
      "output_var": "abg_biomass",
      "n_trajectories": 30,
      "plot_file": "/global/homes/j/jingtao/A2MC/use_cases/Kougarok/memory/phase_results/phase1_exploration/morris_abg_biomass_sensitivity_20260212_125317.png",
      "csv_file": "/global/homes/j/jingtao/A2MC/use_cases/Kougarok/memory/phase_results/phase1_exploration/morris_abg_biomass_rankings_20260212_125317.csv"
    },
    {
      "output_var": "leaf_biomass",
      "n_trajectories": 30,
      "plot_file": "/global/homes/j/jingtao/A2MC/use_cases/Kougarok/memory/phase_results/phase1_exploration/morris_leaf_biomass_sensitivity_20260212_125318.png",
      "csv_file": "/global/homes/j/jingtao/A2MC/use_cases/Kougarok/memory/phase_results/phase1_exploration/morris_leaf_biomass_rankings_20260212_125318.csv"
    },
    {
      "output_var": "fineroot_biomass",
      "n_trajectories": 30,
      "plot_file": "/global/homes/j/jingtao/A2MC/use_cases/Kougarok/memory/phase_results/phase1_exploration/morris_fineroot_biomass_sensitivity_20260212_125320.png",
      "csv_file": "/global/homes/j/jingtao/A2MC/use_cases/Kougarok/memory/phase_results/phase1_exploration/morris_fineroot_biomass_rankings_20260212_125320.csv"
    }
  ]
}
```

---

## Iteration Context

```json
{
  "calibration_round": 2,
  "iteration": 1,
  "phase": 1,
  "phase_name": "exploration",
  "timestamp": "2026-02-12T12:53:22.128828",
  "site": "Kougarok",
  "scheme": "morris",
  "analysis_complete": true,
  "sensitivity_rankings": {
    "abg_biomass": {
      "PFT7": [
        {
          "rank": 1,
          "parameter": "phen_gddthresh_c",
          "mu": 0.679221172466784,
          "mu_star": 0.6898168880223637,
          "sigma": 1.0699362710373392,
          "type": "Phenology"
        },
        {
          "rank": 2,
          "parameter": "turnover_leaf_7",
          "mu": 0.22378726042376848,
          "mu_star": 0.2655668538664775,
          "sigma": 0.6638956429379596,
          "type": "Turnover"
        },
        {
          "rank": 3,
          "parameter": "nfix1_9",
          "mu": -0.21425171683566308,
          "mu_star": 0.24861679598369826,
          "sigma": 1.2003553486522716,
          "type": "N"
        },
        {
          "rank": 4,
          "parameter": "pid_kp_7",
          "mu": -0.21283605372248107,
          "mu_star": 0.22227370187630704,
          "sigma": 1.0939303067375135,
          "type": "Allocation"
        },
        {
          "rank": 5,
          "parameter": "vmax_ptase_7",
          "mu": -0.18313999095883104,
          "mu_star": 0.2116833558672764,
          "sigma": 0.6519635260789992,
          "type": "P"
        },
        {
          "rank": 6,
          "parameter": "allom_d2bl1_7",
          "mu": -0.18296745892325844,
          "mu_star": 0.21364860520287918,
          "sigma": 0.9198552606689989,
          "type": "Allometry"
        },
        {
          "rank": 7,
          "parameter": "recruit_height_min_7",
          "mu": -0.17274228764244942,
          "mu_star": 0.25679781402946805,
          "sigma": 1.1120917600602307,
          "type": "Allometry"
        },
        {
          "rank": 8,
          "parameter": "allom_d2bl1_10",
          "mu": -0.1716821232798321,
          "mu_star": 0.18509691685934554,
          "sigma": 0.7956930193844779,
          "type": "Allometry"
        },
        {
          "rank": 9,
          "parameter": "alloc_storage_cushion_7",
          "mu": -0.17107804417220995,
          "mu_star": 0.4009681729713824,
          "sigma": 1.397645965197358,
          "type": "Allocation"
        },
        {
          "rank": 10,
          "parameter": "vmax_no3_10",
          "mu": -0.16334238960385808,
          "mu_star": 0.21959148687028948,
          "sigma": 0.9686858253820534,
          "type": "N"
        }
      ],
      "PFT9": [
        {
          "rank": 1,
          "parameter": "phen_gddthresh_c",
          "mu": -0.11532818892770003,
          "mu_star": 0.11977683266803335,
          "sigma": 0.1792718537577833,
          "type": "Phenology"
        },
        {
          "rank": 2,
          "parameter": "alloc_storage_cushion_7",
          "mu": -0.10147206463902077,
          "mu_star": 0.10447473152445577,
          "sigma": 0.23110981079657109,
          "type": "Allocation"
        },
        {
          "rank": 3,
          "parameter": "l2fr_ini_9",
          "mu": -0.09177493034491833,
          "mu_star": 0.10155018012252168,
          "sigma": 0.23455149321293298,
          "type": "Allocation"
        },
        {
          "rank": 4,
          "parameter": "alloc_storage_cushion_9",
          "mu": 0.07564198994200919,
          "mu_star": 0.09804673846050418,
          "sigma": 0.2690702323394613,
          "type": "Allocation"
        },
        {
          "rank": 5,
          "parameter": "l2fr_ini_7",
          "mu": -0.07373314045466559,
          "mu_star": 0.08247529000058992,
          "sigma": 0.23199781526107094,
          "type": "Allocation"
        },
        {
          "rank": 6,
          "parameter": "phos_store_ratio_9",
          "mu": 0.06939862576716475,
          "mu_star": 0.07621820533804692,
          "sigma": 0.133453558058385,
          "type": "P"
        },
        {
          "rank": 7,
          "parameter": "pid_ki_9",
          "mu": -0.06145568583161746,
          "mu_star": 0.06695749528356747,
          "sigma": 0.1454564119018595,
          "type": "Allocation"
        },
        {
          "rank": 8,
          "parameter": "microb_bio_10",
          "mu": 0.0580178104277875,
          "mu_star": 0.061355933952556334,
          "sigma": 0.1642286177674723,
          "type": "Microbial"
        },
        {
          "rank": 9,
          "parameter": "mort_scalar_hydrfailure_7",
          "mu": -0.05732641635576907,
          "mu_star": 0.05916743607213727,
          "sigma": 0.19950557881848904,
          "type": "Mortality"
        },
        {
          "rank": 10,
          "parameter": "fnrt_prof_b_9",
          "mu": -0.05692033912489168,
          "mu_star": 0.06174542866034668,
          "sigma": 0.15319098083945876,
          "type": "Turnover"
        }
      ],
      "PFT10": [
        {
          "rank": 1,
          "parameter": "phen_gddthresh_c",
          "mu": -0.06246019684974112,
          "mu_star": 0.06530119683184112,
          "sigma": 0.09786591559175811,
          "type": "Phenology"
        },
        {
          "rank": 2,
          "parameter": "allom_dbh_maxheight_7",
          "mu": -0.042354087024735206,
          "mu_star": 0.04471954518725137,
          "sigma": 0.20082704351088965,
          "type": "Allometry"
        },
        {
          "rank": 3,
          "parameter": "leaf_vcmax25top_7",
          "mu": 0.04034378836174226,
          "mu_star": 0.04621124459510708,
          "sigma": 0.13974928679649806,
          "type": "Allometry"
        },
        {
          "rank": 4,
          "parameter": "alloc_store_priority_frac_9",
          "mu": 0.035457029509206664,
          "mu_star": 0.035874069874276666,
          "sigma": 0.19173470435624648,
          "type": "Allocation"
        },
        {
          "rank": 5,
          "parameter": "allom_d2bl2_10",
          "mu": 0.03175389942083035,
          "mu_star": 0.05759769370897086,
          "sigma": 0.21251885889645983,
          "type": "Allometry"
        },
        {
          "rank": 6,
          "parameter": "nitr_retrans_7",
          "mu": 0.03041744130720401,
          "mu_star": 0.03484212395527733,
          "sigma": 0.1455641364884769,
          "type": "N"
        },
        {
          "rank": 7,
          "parameter": "km_nh4_7",
          "mu": 0.0289593449076198,
          "mu_star": 0.030988818664060034,
          "sigma": 0.11980784716325954,
          "type": "N"
        },
        {
          "rank": 8,
          "parameter": "fnrt_prof_a_7",
          "mu": 0.022153663824617927,
          "mu_star": 0.024788963584654225,
          "sigma": 0.0763895744643078,
          "type": "Turnover"
        },
        {
          "rank": 9,
          "parameter": "stoich_phos_leaf_10",
          "mu": -0.021429394014231166,
          "mu_star": 0.031332585426389496,
          "sigma": 0.08064363549374318,
          "type": "P"
        },
        {
          "rank": 10,
          "parameter": "maintresp_nonleaf_baserate",
          "mu": 0.020876422930286003,
          "mu_star": 0.022952044967567333,
          "sigma": 0.10075947856370922,
          "type": "Other"
        }
      ]
    },
    "leaf_biomass": {
      "PFT7": [
        {
          "rank": 1,
          "parameter": "phen_gddthresh_c",
          "mu": 0.09000767701875925,
          "mu_star": 0.09164154971540187,
          "sigma": 0.15284475981692663,
          "type": "Phenology"
        },
        {
          "rank": 2,
          "parameter": "turnover_leaf_7",
          "mu": 0.029396405641046102,
          "mu_star": 0.030774755737304673,
          "sigma": 0.07504708998856466,
          "type": "Turnover"
        },
        {
          "rank": 3,
          "parameter": "vmax_ptase_7",
          "mu": -0.02644687355989076,
          "mu_star": 0.03465997972508022,
          "sigma": 0.10713735979916955,
          "type": "P"
        },
        {
          "rank": 4,
          "parameter": "recruit_seed_alloc_7",
          "mu": 0.019454203567307937,
          "mu_star": 0.023283449047912155,
          "sigma": 0.08016753978406083,
          "type": "Allocation"
        },
        {
          "rank": 5,
          "parameter": "recruit_seed_supplement_9",
          "mu": 0.018463747586189867,
          "mu_star": 0.02626968373672228,
          "sigma": 0.07414756328836562,
          "type": "Other"
        },
        {
          "rank": 6,
          "parameter": "maintresp_nonleaf_baserate",
          "mu": 0.018264620963699723,
          "mu_star": 0.020277516133828645,
          "sigma": 0.08912267512002392,
          "type": "Other"
        },
        {
          "rank": 7,
          "parameter": "allom_d2h1_7",
          "mu": -0.017482391719155613,
          "mu_star": 0.023894834190397802,
          "sigma": 0.0739297534809173,
          "type": "Allometry"
        },
        {
          "rank": 8,
          "parameter": "vmax_p_7",
          "mu": -0.01742276244973357,
          "mu_star": 0.05027026882830901,
          "sigma": 0.12978843457763942,
          "type": "P"
        },
        {
          "rank": 9,
          "parameter": "recruit_seed_supplement_7",
          "mu": 0.017013785827569107,
          "mu_star": 0.021655774058560402,
          "sigma": 0.08194651147620387,
          "type": "Other"
        },
        {
          "rank": 10,
          "parameter": "stoich_phos_fineroot_10",
          "mu": -0.01573458108858285,
          "mu_star": 0.024597034418073975,
          "sigma": 0.0906694820971503,
          "type": "P"
        }
      ],
      "PFT9": [
        {
          "rank": 1,
          "parameter": "phen_gddthresh_c",
          "mu": -0.009866883795429791,
          "mu_star": 0.010369546730446457,
          "sigma": 0.016142495935830687,
          "type": "Phenology"
        },
        {
          "rank": 2,
          "parameter": "l2fr_ini_9",
          "mu": -0.008808459673503,
          "mu_star": 0.010600076095532,
          "sigma": 0.025695829776876206,
          "type": "Allocation"
        },
        {
          "rank": 3,
          "parameter": "phos_store_ratio_9",
          "mu": 0.007858453654912174,
          "mu_star": 0.008529209138737176,
          "sigma": 0.01726036619144817,
          "type": "P"
        },
        {
          "rank": 4,
          "parameter": "pid_ki_9",
          "mu": -0.007019741649794279,
          "mu_star": 0.008122472867657613,
          "sigma": 0.014375619078809127,
          "type": "Allocation"
        },
        {
          "rank": 5,
          "parameter": "alloc_storage_cushion_7",
          "mu": -0.006772406772566424,
          "mu_star": 0.006921790806343256,
          "sigma": 0.017386384387563448,
          "type": "Allocation"
        },
        {
          "rank": 6,
          "parameter": "alloc_storage_cushion_10",
          "mu": -0.004286697852148751,
          "mu_star": 0.004679377013015752,
          "sigma": 0.01420914100020433,
          "type": "Allocation"
        },
        {
          "rank": 7,
          "parameter": "microb_bio_10",
          "mu": 0.003974585730996824,
          "mu_star": 0.004467854492747509,
          "sigma": 0.014288793853524941,
          "type": "Microbial"
        },
        {
          "rank": 8,
          "parameter": "recruit_seed_supplement_10",
          "mu": -0.0038827019849680877,
          "mu_star": 0.004840748862193173,
          "sigma": 0.017600006972553126,
          "type": "Other"
        },
        {
          "rank": 9,
          "parameter": "nitr_store_ratio_9",
          "mu": 0.0038377503760724015,
          "mu_star": 0.004945288011958434,
          "sigma": 0.013062228454396635,
          "type": "N"
        },
        {
          "rank": 10,
          "parameter": "fnrt_prof_b_9",
          "mu": -0.0038117453312674168,
          "mu_star": 0.00448414493122575,
          "sigma": 0.00921742927931022,
          "type": "Turnover"
        }
      ],
      "PFT10": [
        {
          "rank": 1,
          "parameter": "phen_gddthresh_c",
          "mu": -0.009005498575205247,
          "mu_star": 0.00914653995182358,
          "sigma": 0.011803401382666601,
          "type": "Phenology"
        },
        {
          "rank": 2,
          "parameter": "nitr_store_ratio_10",
          "mu": 0.005087229683047342,
          "mu_star": 0.0065701208114140085,
          "sigma": 0.01688113188347128,
          "type": "N"
        },
        {
          "rank": 3,
          "parameter": "km_nh4_9",
          "mu": 0.0047201921393426275,
          "mu_star": 0.006768245514007645,
          "sigma": 0.026028408043264235,
          "type": "N"
        },
        {
          "rank": 4,
          "parameter": "l2fr_ini_10",
          "mu": -0.004129054807824099,
          "mu_star": 0.005399063395607934,
          "sigma": 0.024417936344600363,
          "type": "Allocation"
        },
        {
          "rank": 5,
          "parameter": "allom_d2bl2_9",
          "mu": -0.0032069314964037897,
          "mu_star": 0.0035160662504274466,
          "sigma": 0.009261902075531406,
          "type": "Allometry"
        },
        {
          "rank": 6,
          "parameter": "pid_ki_10",
          "mu": -0.003005735365391672,
          "mu_star": 0.0032502557908878583,
          "sigma": 0.00799542446375155,
          "type": "Allocation"
        },
        {
          "rank": 7,
          "parameter": "fnrt_prof_a_9",
          "mu": 0.0029340971975556174,
          "mu_star": 0.003934800261662284,
          "sigma": 0.012403321783341576,
          "type": "Turnover"
        },
        {
          "rank": 8,
          "parameter": "allom_agb2_10",
          "mu": 0.002706713228624984,
          "mu_star": 0.0036153205637798175,
          "sigma": 0.012281816231834898,
          "type": "Allometry"
        },
        {
          "rank": 9,
          "parameter": "fnrt_prof_b_9",
          "mu": 0.0027065913520385983,
          "mu_star": 0.003497349093239181,
          "sigma": 0.01170139695704559,
          "type": "Turnover"
        },
        {
          "rank": 10,
          "parameter": "leaf_slatop_10",
          "mu": -0.0024725219018853863,
          "mu_star": 0.0032785450799633397,
          "sigma": 0.006170854127905013,
          "type": "Allometry"
        }
      ]
    },
    "fineroot_biomass": {
      "PFT7": [
        {
          "rank": 1,
          "parameter": "phen_gddthresh_c",
          "mu": 0.1792742919664007,
          "mu_star": 0.18995343257689581,
          "sigma": 0.32103202432845895,
          "type": "Phenology"
        },
        {
          "rank": 2,
          "parameter": "nitr_store_ratio_7",
          "mu": 0.10357682337345311,
          "mu_star": 0.13100373167165638,
          "sigma": 0.27966708371470184,
          "type": "N"
        },
        {
          "rank": 3,
          "parameter": "phos_retrans_10",
          "mu": 0.09676674678995875,
          "mu_star": 0.1047410379967657,
          "sigma": 0.49815549430363143,
          "type": "P"
        },
        {
          "rank": 4,
          "parameter": "alloc_storage_cushion_9",
          "mu": -0.0784021689584525,
          "mu_star": 0.09946026844576913,
          "sigma": 0.4022872096547139,
          "type": "Allocation"
        },
        {
          "rank": 5,
          "parameter": "stoich_phos_leaf_7",
          "mu": 0.07517398879995181,
          "mu_star": 0.09606321283820501,
          "sigma": 0.19141549387540338,
          "type": "P"
        },
        {
          "rank": 6,
          "parameter": "vmax_nh4_7",
          "mu": -0.07450842933009724,
          "mu_star": 0.12278401271742806,
          "sigma": 0.30415297409282654,
          "type": "N"
        },
        {
          "rank": 7,
          "parameter": "allom_agb2_7",
          "mu": 0.07142813460339266,
          "mu_star": 0.1414862418918245,
          "sigma": 0.5025601700570039,
          "type": "Allometry"
        },
        {
          "rank": 8,
          "parameter": "vmax_p_10",
          "mu": -0.07112310533180911,
          "mu_star": 0.07643463866172598,
          "sigma": 0.25702154434355723,
          "type": "P"
        },
        {
          "rank": 9,
          "parameter": "recruit_seed_germination_rate_9",
          "mu": 0.07062516241017164,
          "mu_star": 0.0774265282849917,
          "sigma": 0.19566392115806688,
          "type": "Other"
        },
        {
          "rank": 10,
          "parameter": "recruit_seed_supplement_7",
          "mu": 0.059913497883881936,
          "mu_star": 0.0634562160466158,
          "sigma": 0.1738342747813969,
          "type": "Other"
        }
      ],
      "PFT9": [
        {
          "rank": 1,
          "parameter": "phen_gddthresh_c",
          "mu": -0.08545321091880999,
          "mu_star": 0.08980435959084333,
          "sigma": 0.1290105964147096,
          "type": "Phenology"
        },
        {
          "rank": 2,
          "parameter": "alloc_storage_cushion_7",
          "mu": -0.04366757639116629,
          "mu_star": 0.04534369387485963,
          "sigma": 0.11736194601103138,
          "type": "Allocation"
        },
        {
          "rank": 3,
          "parameter": "microb_bio_10",
          "mu": 0.042152547695475176,
          "mu_star": 0.046535773832704144,
          "sigma": 0.11551637502270963,
          "type": "Microbial"
        },
        {
          "rank": 4,
          "parameter": "pid_ki_9",
          "mu": -0.04109742992958284,
          "mu_star": 0.044851728445105175,
          "sigma": 0.08219972463372967,
          "type": "Allocation"
        },
        {
          "rank": 5,
          "parameter": "l2fr_ini_9",
          "mu": -0.04105834960361167,
          "mu_star": 0.045760504696024995,
          "sigma": 0.1041138767554098,
          "type": "Allocation"
        },
        {
          "rank": 6,
          "parameter": "fnrt_prof_b_9",
          "mu": -0.03793139210718503,
          "mu_star": 0.0409671844705333,
          "sigma": 0.09535932820793544,
          "type": "Turnover"
        },
        {
          "rank": 7,
          "parameter": "mort_scalar_hydrfailure_7",
          "mu": -0.0364663332968375,
          "mu_star": 0.03708180430429417,
          "sigma": 0.125324718653762,
          "type": "Mortality"
        },
        {
          "rank": 8,
          "parameter": "turnover_fnrt_7",
          "mu": 0.03502640937984417,
          "mu_star": 0.03948087944128417,
          "sigma": 0.11867595711571788,
          "type": "Turnover"
        },
        {
          "rank": 9,
          "parameter": "km_nh4_7",
          "mu": 0.032897513732848334,
          "mu_star": 0.04092091872996167,
          "sigma": 0.10367422092258018,
          "type": "N"
        },
        {
          "rank": 10,
          "parameter": "phos_store_ratio_9",
          "mu": 0.02848754325270379,
          "mu_star": 0.0423863187112012,
          "sigma": 0.0830224875520012,
          "type": "P"
        }
      ],
      "PFT10": [
        {
          "rank": 1,
          "parameter": "phen_gddthresh_c",
          "mu": -0.045668142101876155,
          "mu_star": 0.04816962998097382,
          "sigma": 0.07753503088156073,
          "type": "Phenology"
        },
        {
          "rank": 2,
          "parameter": "leaf_vcmax25top_7",
          "mu": 0.02861803358195448,
          "mu_star": 0.034508381816497534,
          "sigma": 0.10297558431755022,
          "type": "Allometry"
        },
        {
          "rank": 3,
          "parameter": "fnrt_prof_a_7",
          "mu": 0.026112930348169174,
          "mu_star": 0.02863155572800359,
          "sigma": 0.09579917197980874,
          "type": "Turnover"
        },
        {
          "rank": 4,
          "parameter": "alpha_ptase_10",
          "mu": -0.019395935972620675,
          "mu_star": 0.022512488141625993,
          "sigma": 0.05517111137575257,
          "type": "P"
        },
        {
          "rank": 5,
          "parameter": "fnrt_prof_b_7",
          "mu": -0.01726644379429287,
          "mu_star": 0.02527777962309396,
          "sigma": 0.07369796943145669,
          "type": "Turnover"
        },
        {
          "rank": 6,
          "parameter": "fnrt_prof_a_9",
          "mu": 0.01688252331357566,
          "mu_star": 0.01862495289238601,
          "sigma": 0.053674545681734284,
          "type": "Turnover"
        },
        {
          "rank": 7,
          "parameter": "phos_store_ratio_10",
          "mu": 0.0159696485825054,
          "mu_star": 0.020226953179998765,
          "sigma": 0.07525411052506421,
          "type": "P"
        },
        {
          "rank": 8,
          "parameter": "frag_seed_decay_rate_7",
          "mu": -0.01565399858363069,
          "mu_star": 0.024722789003053438,
          "sigma": 0.06347884854316922,
          "type": "Turnover"
        },
        {
          "rank": 9,
          "parameter": "recruit_seed_supplement_10",
          "mu": -0.014973235808695137,
          "mu_star": 0.049914756757381024,
          "sigma": 0.12821800648149215,
          "type": "Other"
        },
        {
          "rank": 10,
          "parameter": "allom_dbh_maxheight_7",
          "mu": -0.014748436722858584,
          "mu_star": 0.015334696373174656,
          "sigma": 0.0633871394565146,
          "type": "Allometry"
        }
      ]
    }
  },
  "analysis_results": [
    {
      "output_var": "abg_biomass",
      "n_trajectories": 30,
      "plot_file": "/global/homes/j/jingtao/A2MC/use_cases/Kougarok/memory/phase_results/phase1_exploration/morris_abg_biomass_sensitivity_20260212_125317.png",
      "csv_file": "/global/homes/j/jingtao/A2MC/use_cases/Kougarok/memory/phase_results/phase1_exploration/morris_abg_biomass_rankings_20260212_125317.csv"
    },
    {
      "output_var": "leaf_biomass",
      "n_trajectories": 30,
      "plot_file": "/global/homes/j/jingtao/A2MC/use_cases/Kougarok/memory/phase_results/phase1_exploration/morris_leaf_biomass_sensitivity_20260212_125318.png",
      "csv_file": "/global/homes/j/jingtao/A2MC/use_cases/Kougarok/memory/phase_results/phase1_exploration/morris_leaf_biomass_rankings_20260212_125318.csv"
    },
    {
      "output_var": "fineroot_biomass",
      "n_trajectories": 30,
      "plot_file": "/global/homes/j/jingtao/A2MC/use_cases/Kougarok/memory/phase_results/phase1_exploration/morris_fineroot_biomass_sensitivity_20260212_125320.png",
      "csv_file": "/global/homes/j/jingtao/A2MC/use_cases/Kougarok/memory/phase_results/phase1_exploration/morris_fineroot_biomass_rankings_20260212_125320.csv"
    }
  ]
}
```
