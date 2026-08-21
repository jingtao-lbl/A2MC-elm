"""Parse-layer tests for the ECO_ / SNOW_ / SOIL_ calibration-target specs.

Pure (no NetCDF file): they lock in the target-key grammar + registry resolution that the
extractors depend on. End-to-end extraction against real ELM-FATES output is verified
manually (dev_log 20260711k) since it needs an on-disk history file.
"""
from tools.extract_ecosystem_series import parse_ecosystem_specs
from tools.extract_land_series import parse_land_specs


# ---- ECO_ (ecosystem site scalars: FATES families + ELM-flux fallback) ----

def test_eco_fates_family_resolves():
    specs = parse_ecosystem_specs(["ECO_gpp", "ECO_lai"])
    assert specs["ECO_gpp"][0] == "FATES_GPP"
    assert specs["ECO_lai"][0] == "FATES_LAI"


def test_eco_fates_prefix_stripped():
    specs = parse_ecosystem_specs(["ECO_gpp", "ECO_fates_gpp"])
    assert specs["ECO_fates_gpp"][0] == specs["ECO_gpp"][0] == "FATES_GPP"


def test_eco_elm_flux_fallback():
    specs = parse_ecosystem_specs(["ECO_eflx_lh_tot", "ECO_fsh", "ECO_nee", "ECO_tsa"])
    assert specs["ECO_eflx_lh_tot"][0] == "EFLX_LH_TOT"
    assert specs["ECO_fsh"][0] == "FSH"
    assert specs["ECO_nee"][0] == "NEE"
    assert specs["ECO_tsa"][0] == "TSA"


def test_eco_elm_aliases():
    specs = parse_ecosystem_specs(["ECO_le", "ECO_latent_heat", "ECO_eflx_lh_tot"])
    lh = {v[0] for v in specs.values()}
    assert lh == {"EFLX_LH_TOT"}  # all three aliases collapse to the same nc var


def test_eco_unknown_is_skipped():
    specs = parse_ecosystem_specs(["ECO_bogusvar", "PFT10_leaf", "SOIL_tsoi_10cm"])
    assert specs == {}  # non-ECO keys + unknown ECO var all ignored here


# ---- SNOW_ / SOIL_ (land column: site scalars + depth/layer profiles) ----

def test_land_site_scalar():
    specs = parse_land_specs(["SNOW_snowdp", "SNOW_swe", "SNOW_fsno"])
    assert specs["SNOW_snowdp"][:2] == ("SNOWDP", "site")
    assert specs["SNOW_swe"][:2] == ("H2OSNO", "site")


def test_land_profile_depth_and_index():
    specs = parse_land_specs(["SOIL_tsoi_10cm", "SOIL_tsoi_L3",
                              "SOIL_tsoi_surface", "SOIL_tsoi_bottom"])
    assert specs["SOIL_tsoi_10cm"][:3] == ("TSOI", "profile", ("depth", 10.0))
    assert specs["SOIL_tsoi_L3"][:3] == ("TSOI", "profile", ("index", 3))
    assert specs["SOIL_tsoi_surface"][2] == ("surface",)
    assert specs["SOIL_tsoi_bottom"][2] == ("bottom",)


def test_land_shape_selector_consistency():
    # a site var with a depth suffix, and a profile var with NO suffix, are both rejected
    specs = parse_land_specs(["SNOW_snowdp_10cm", "SOIL_tsoi"])
    assert "SNOW_snowdp_10cm" not in specs
    assert "SOIL_tsoi" not in specs


def test_land_snow_layer_rejects_depth():
    # levsno layers are dynamic — a fixed depth is not meaningful, must be skipped
    specs = parse_land_specs(["SNOW_sno_t_10cm", "SNOW_sno_t_surface"])
    assert "SNOW_sno_t_10cm" not in specs
    assert specs["SNOW_sno_t_surface"][:3] == ("SNO_T", "profile", ("surface",))
