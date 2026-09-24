"""
ETL: convierte la base de datos termodinamica de Carl Yaws (Excel) en:
  - base_termodinamica.json  (snapshot legible/portable de toda la data)
  - base_termodinamica.db    (SQLite: una tabla por propiedad, para consultas)

Uso:
    python etl_yaws.py

Este script se ejecuta una sola vez (o cada vez que cambie el Excel fuente).
No forma parte de la capa de persistencia en tiempo de ejecucion: esa capa
es repositorio.py, que solo LEE la base de datos generada aqui.
"""

import datetime
import json
import math
import sqlite3
from datetime import date
from pathlib import Path

import openpyxl

ARCHIVO_EXCEL = "Yaws_Handbook_of_Thermodynamic_and_Physi.xlsx"
ARCHIVO_JSON_SALIDA = "base_termodinamica.json"
ARCHIVO_DB_SALIDA = "base_termodinamica.db"

# Columnas de texto (todo lo demas se guarda como REAL en SQLite)
CAMPOS_TEXTO = {
    "Name", "Formula", "Phase", "state",
    "code_solubilidad", "code_logKow",
    "code_limite_explosivo", "code_flash_point", "code_autoignicion",
}

# ---------------------------------------------------------------------------
# Configuracion de cada hoja del Excel.
#
#   sheet        -> nombre exacto de la hoja en el Excel
#   slug         -> clave corta usada en el JSON para esta propiedad
#   data_start   -> primera fila (1-indexada) que contiene datos de compuestos
#   columns      -> lista de (indice_columna_0based, nombre_clave)
#   name_idx     -> indice de columna (0-based) con el nombre del compuesto
#   formula_idx  -> indice de columna (0-based) con la formula quimica
#   ecuacion     -> expresion matematica del modelo, tal como aparece en Yaws
#   unidades     -> unidades de las variables involucradas
# ---------------------------------------------------------------------------
SHEET_CONFIG = [
    dict(
        sheet="Cp Liquid (Organic)", slug="cp_liquido_organico", data_start=4,
        name_idx=1, formula_idx=2,
        columns=[(0, "No"), (1, "Name"), (2, "Formula"), (3, "A"), (4, "B"),
                 (5, "C"), (6, "D"), (7, "Tmin"), (8, "Tmax"), (9, "T"),
                 (10, "Cp_at_T")],
        ecuacion="Cp_liq = A + B*T + C*T^2 + D*T^3", unidades="Cp [J/(mol*K)], T [K]",
    ),
    dict(
        sheet="Cp Liquid (Inorganic)", slug="cp_liquido_inorganico", data_start=3,
        name_idx=2, formula_idx=1,
        columns=[(0, "No"), (1, "Formula"), (2, "Name"), (3, "A"), (4, "B"),
                 (5, "C"), (6, "D"), (7, "Tmin"), (8, "Tmax"), (9, "Cp_25C")],
        ecuacion="Cp_liq = A + B*T + C*T^2 + D*T^3", unidades="Cp [J/(mol*K)], T [K]",
    ),
    dict(
        sheet="Cp Gas (Organic)", slug="cp_gas_organico", data_start=4,
        name_idx=1, formula_idx=2,
        columns=[(0, "No"), (1, "Name"), (2, "Formula"), (3, "MW"), (4, "A"),
                 (5, "B"), (6, "C"), (7, "D"), (8, "E"), (9, "Tmin"),
                 (10, "Tmax"), (11, "Cp_25C")],
        ecuacion="Cp_gas = A + B*T + C*T^2 + D*T^3 + E*T^4", unidades="Cp [J/(mol*K)], T [K]",
    ),
    dict(
        sheet="CP Gas (Inorganic)", slug="cp_gas_inorganico", data_start=4,
        name_idx=2, formula_idx=1,
        columns=[(0, "No"), (1, "Formula"), (2, "Name"), (3, "A"), (4, "B"),
                 (5, "C"), (6, "D"), (7, "E"), (8, "Tmin"), (9, "Tmax")],
        ecuacion="Cp_gas = A + B*T + C*T^2 + D*T^3 + E*T^4", unidades="Cp [J/(mol*K)], T [K]",
    ),
    dict(
        sheet="Cp solid (Organic)", slug="cp_solido_organico", data_start=3,
        name_idx=1, formula_idx=2,
        columns=[(0, "No"), (1, "Name"), (2, "Formula"), (3, "A"), (4, "B"),
                 (5, "C"), (6, "Tmin"), (7, "Tmax"), (8, "T"), (9, "Cp_at_T")],
        ecuacion="Cp_solido = A + B*T + C*T^2", unidades="Cp [J/(mol*K)], T [K]",
    ),
    dict(
        sheet="Cp Solid (Inorganic)", slug="cp_solido_inorganico", data_start=4,
        name_idx=2, formula_idx=1,
        columns=[(0, "No"), (1, "Formula"), (2, "Name"), (3, "A"), (4, "B"),
                 (5, "C"), (6, "Tmin"), (7, "Tmax"), (8, "Cp_25C"),
                 (9, "Cp_Tmin"), (10, "Cp_Tmax")],
        ecuacion="Cp_solido = A + B*T + C*T^2", unidades="Cp [J/(mol*K)], T [K]",
    ),
    dict(
        sheet="Antoine (Organic) (°C)", slug="antoine_organico_C", data_start=4,
        name_idx=1, formula_idx=2,
        columns=[(0, "No"), (1, "Name"), (2, "Formula"), (3, "A"), (4, "B"),
                 (5, "C"), (6, "Tmin"), (7, "Tmax")],
        ecuacion="log10(P) = A - B/(T+C)", unidades="P [mmHg], T [°C]",
    ),
    dict(
        sheet="Antoine (Organic) (K)", slug="antoine_organico_K", data_start=4,
        name_idx=1, formula_idx=2,
        columns=[(0, "No"), (1, "Name"), (2, "Formula"), (3, "MW"), (4, "A"),
                 (5, "B"), (6, "C"), (7, "D"), (8, "E"), (9, "Tmin"), (10, "Tmax")],
        ecuacion="log10(P) = A + B/T + C*log10(T) + D*T + E*T^2", unidades="P [mmHg], T [K]",
    ),
    dict(
        sheet="Antoine (Inorganic) (K)", slug="antoine_inorganico_K", data_start=4,
        name_idx=2, formula_idx=1,
        columns=[(0, "No"), (1, "Formula"), (2, "Name"), (3, "A"), (4, "B"),
                 (5, "C"), (6, "D"), (7, "E"), (8, "Tmin"), (9, "Tmax")],
        ecuacion="log10(P) = A + B/T + C*log10(T) + D*T + E*T^2", unidades="P [mmHg], T [K]",
    ),
    dict(
        sheet="Tc, Pc, Vc, Zc,ρ, ω (Organic)", slug="propiedades_criticas_organico", data_start=3,
        name_idx=1, formula_idx=2,
        columns=[(0, "No"), (1, "Name"), (2, "Formula"), (3, "MW"), (4, "Tc"),
                 (5, "Pc"), (6, "Vc"), (7, "rho"), (8, "Zc"), (9, "omega")],
        ecuacion=None, unidades="Tc [K], Pc [bar], Vc [cm3/mol], rho [g/cm3]",
    ),
    dict(
        sheet="Tc, Pc, Vc, Zc,ρ, ω (Inorganic)", slug="propiedades_criticas_inorganico", data_start=5,
        name_idx=2, formula_idx=1,
        columns=[(0, "No"), (1, "Formula"), (2, "Name"), (3, "MW"), (4, "TF"),
                 (5, "TB"), (6, "Tc"), (7, "Pc"), (8, "Vc"), (9, "rhoc"),
                 (10, "Zc"), (11, "omega")],
        ecuacion=None,
        unidades="MW [g/mol], TF/TB/Tc [K], Pc [bar], Vc [cm3/mol], rhoc [g/cm3]",
    ),
    dict(
        sheet="∆Hc (Organic)", slug="calor_combustion_organico", data_start=5,
        name_idx=1, formula_idx=2,
        columns=[(1, "Name"), (2, "Formula"), (3, "Phase"), (4, "Hc_kJ_mol"),
                 (5, "Hc_kJ_kg"), (6, "Hc_Btu_lb")],
        ecuacion=None, unidades="Entalpia de combustion a 77F, en kJ/mol, kJ/kg y Btu/lb",
    ),
    dict(
        sheet="∆Hf (Organic)", slug="calor_formacion_organico", data_start=3,
        name_idx=1, formula_idx=2,
        columns=[(0, "No"), (1, "Name"), (2, "Formula"), (3, "MW"), (4, "A"),
                 (5, "B"), (6, "C"), (7, "Tmin"), (8, "Tmax"),
                 (9, "Hf_298K"), (10, "Hf_500K")],
        ecuacion="Hf = A + B*T + C*T^2", unidades="Hf [kJ/mol], T [K]",
    ),
    dict(
        sheet="H Fusion", slug="calor_fusion_organico", data_start=4,
        name_idx=1, formula_idx=2,
        columns=[(0, "No"), (1, "Name"), (2, "Formula"), (3, "MW"),
                 (4, "Tfreeze"), (5, "Hfusion_kJ_mol"), (6, "Hfusion_kJ_kg"),
                 (7, "Hfusion_Btu_lb")],
        ecuacion=None, unidades="Tfreeze [K]",
    ),
    dict(
        sheet="Liq Viscos (Organic) cP", slug="viscosidad_liquido_organico", data_start=3,
        name_idx=1, formula_idx=2,
        columns=[(0, "No"), (1, "Name"), (2, "Formula"), (3, "MW"), (4, "A"),
                 (5, "B"), (6, "C"), (7, "D"), (8, "Tmin"), (9, "Tmax"),
                 (10, "T"), (11, "mu_liq_at_T")],
        ecuacion="log10(mu_liq) = A + B/T + C*T + D*T^2", unidades="mu_liq [cP], T [K]",
    ),
    dict(
        sheet="Gas Viscos (Organic) (µP)", slug="viscosidad_gas_organico", data_start=3,
        name_idx=1, formula_idx=2,
        columns=[(0, "No"), (1, "Name"), (2, "Formula"), (3, "MW"), (4, "A"),
                 (5, "B"), (6, "C"), (7, "Tmin"), (8, "Tmax"),
                 (9, "mu_gas_25C"), (10, "mu_gas_Tmin"), (11, "mu_gas_Tmax")],
        ecuacion="mu_gas = A + B*T + C*T^2", unidades="mu_gas [uP], T [K]",
    ),
    dict(
        sheet="Sf gas (Organic)", slug="entropia_formacion_gas_organico", data_start=6,
        name_idx=1, formula_idx=2,
        columns=[(0, "No"), (1, "Name"), (2, "Formula"), (3, "MW"), (4, "A"),
                 (5, "B"), (6, "C"), (7, "Tmin"), (8, "Tmax"),
                 (9, "Sf_298K"), (10, "Sf_500K")],
        ecuacion="Sf_gas = A + B/T + C*T", unidades="Sf [J/(mol*K)], T [K]",
    ),
    dict(
        sheet="HVav (Organic)", slug="calor_vaporizacion_organico", data_start=3,
        name_idx=1, formula_idx=2,
        columns=[(0, "No"), (1, "Name"), (2, "Formula"), (3, "MW"), (4, "A"),
                 (5, "Tc"), (6, "n"), (7, "Tmin"), (8, "Tmax"), (9, "Tb"),
                 (10, "HV_at_Tb")],
        ecuacion="Hvap = A*(1-T/Tc)^n", unidades="Hvap [kJ/mol], T/Tc [K]",
    ),
    dict(
        sheet="HVav (Inorganic)", slug="calor_vaporizacion_inorganico", data_start=4,
        name_idx=2, formula_idx=1,
        columns=[(0, "No"), (1, "Formula"), (2, "Name"), (3, "A"), (4, "Tc"),
                 (5, "n"), (6, "Tmin"), (7, "Tmax"), (8, "TB"), (9, "Hvap_at_TB")],
        ecuacion="Hvap = A*(1-T/Tc)^n", unidades="Hvap [kJ/mol], T/Tc [K]",
    ),
    dict(
        sheet="H-Fusion (Inorganic)", slug="calor_fusion_inorganico", data_start=3,
        name_idx=2, formula_idx=1,
        columns=[(0, "No"), (1, "Formula"), (2, "Name"), (3, "MW"), (4, "TF"),
                 (5, "HFusion_kJ_mol"), (6, "HFusion_kJ_kg"), (7, "HFusion_Btu_lb")],
        ecuacion=None, unidades="TF [K]",
    ),
    dict(
        sheet="Entropy gas (Organic)", slug="entropia_gas_organico", data_start=6,
        name_idx=1, formula_idx=2,
        columns=[(0, "No"), (1, "Name"), (2, "Formula"), (3, "MW"), (4, "A"),
                 (5, "B"), (6, "C"), (7, "Tmin"), (8, "Tmax"),
                 (9, "S_298K"), (10, "S_500K")],
        ecuacion="S_gas = A + B*T + C*T^2", unidades="S [J/(mol*K)], T [K]",
    ),
    dict(
        sheet="∆Gf Gibbs Energy (Organic)", slug="energia_gibbs_formacion_organico", data_start=5,
        name_idx=1, formula_idx=2,
        columns=[(0, "No"), (1, "Name"), (2, "Formula"), (3, "MW"), (4, "A"),
                 (5, "B"), (6, "C"), (7, "Tmin"), (8, "Tmax"),
                 (9, "Gf_298K"), (10, "Gf_500K")],
        ecuacion="Gf = A + B*T + C*T^2", unidades="Gf [kJ/mol], T [K]",
    ),
    dict(
        sheet="∆Af Helmholtz Ebergy (Organic)", slug="energia_helmholtz_formacion_organico", data_start=5,
        name_idx=1, formula_idx=2,
        columns=[(0, "No"), (1, "Name"), (2, "Formula"), (3, "MW"), (4, "A"),
                 (5, "B"), (6, "C"), (7, "Tmin"), (8, "Tmax"),
                 (9, "Af_298K"), (10, "Af_500K")],
        ecuacion="Af = A + B*T + C*T^2", unidades="Af [kJ/mol], T [K]",
    ),
    dict(
        sheet="∆Uf Internal Energy (Organic)", slug="energia_interna_formacion_organico", data_start=5,
        name_idx=1, formula_idx=2,
        columns=[(0, "No"), (1, "Name"), (2, "Formula"), (3, "MW"), (4, "A"),
                 (5, "B"), (6, "C"), (7, "Tmin"), (8, "Tmax"),
                 (9, "Uf_298K"), (10, "Uf_500K")],
        ecuacion="Uf = A + B*T + C*T^2", unidades="Uf [kJ/mol], T [K]",
    ),
    dict(
        sheet="Surface Tension (Organic)", slug="tension_superficial_organico", data_start=5,
        name_idx=1, formula_idx=2,
        columns=[(0, "No"), (1, "Name"), (2, "Formula"), (3, "A"), (4, "Tc"),
                 (5, "n"), (6, "Tmin"), (7, "Tmax"), (8, "T"), (9, "sigma")],
        ecuacion="sigma = A*(1-T/Tc)^n", unidades="sigma [dyne/cm], T/Tc [K]",
    ),
    dict(
        sheet="Surface Tension (Inorganic)", slug="tension_superficial_inorganico", data_start=4,
        name_idx=2, formula_idx=1,
        columns=[(0, "No"), (1, "Formula"), (2, "Name"), (3, "A"), (4, "Tc"),
                 (5, "n"), (6, "Tmin"), (7, "Tmax"), (8, "T"), (9, "sigma_at_T")],
        ecuacion="sigma = A*(1-T/Tc)^n", unidades="sigma [dyne/cm], T/Tc [K]",
    ),
    dict(
        sheet="Rho liq (Organic)", slug="densidad_liquido_organico", data_start=4,
        name_idx=1, formula_idx=2,
        columns=[(0, "No"), (1, "Name"), (2, "Formula"), (3, "MW"), (4, "A"),
                 (5, "B"), (6, "n"), (7, "Tc"), (8, "Tmin"), (9, "Tmax"),
                 (10, "rho_25C")],
        ecuacion="rho_liq = A*B^(-(1-T/Tc)^n)", unidades="rho [g/cm3], T/Tc [K]",
    ),
    dict(
        sheet="Rho liq (Inorganic)", slug="densidad_liquido_inorganico", data_start=4,
        name_idx=2, formula_idx=1,
        columns=[(0, "No"), (1, "Formula"), (2, "Name"), (3, "A"), (4, "B"),
                 (5, "n"), (6, "Tc"), (7, "Tmin"), (8, "Tmax"), (9, "rho_25C")],
        ecuacion="rho_liq = A*B^(-(1-T/Tc)^n)", unidades="rho [g/mL], T/Tc [K]",
    ),
    dict(
        sheet="K gas-Thermal Cond (Organic)", slug="conductividad_termica_gas_organico", data_start=4,
        name_idx=1, formula_idx=2,
        columns=[(0, "No"), (1, "Name"), (2, "Formula"), (3, "MW"), (4, "A"),
                 (5, "B"), (6, "C"), (7, "Tmin"), (8, "Tmax"), (9, "K_25C"),
                 (10, "K_Tmax"), (11, "K_Tmin")],
        ecuacion="K_gas = A + B*T + C*T^2", unidades="K [W/(m*K)], T [K]",
    ),
    dict(
        sheet="K liq-Thermal Cond (Organic)", slug="conductividad_termica_liquido_organico", data_start=4,
        name_idx=1, formula_idx=2,
        columns=[(0, "No"), (1, "Name"), (2, "Formula"), (3, "MW"), (4, "A"),
                 (5, "B"), (6, "C"), (7, "Tmin"), (8, "Tmax"), (9, "K_25C"),
                 (10, "K_Tmin"), (11, "K_Tmax")],
        ecuacion="K_liq = A + B*T + C*T^2", unidades="K [W/(m*K)], T [K]",
    ),
    dict(
        sheet="Liq Thermal Exp (Organic)", slug="expansion_termica_liquido_organico", data_start=4,
        name_idx=1, formula_idx=2,
        columns=[(0, "No"), (1, "Name"), (2, "Formula"), (3, "MW"), (4, "a"),
                 (5, "Tc"), (6, "m"), (7, "Tmin"), (8, "Tmax"),
                 (9, "rho_25C"), (10, "B_25C")],
        ecuacion="B_liq = a*(1-T/Tc)^m", unidades="B [1/C], T/Tc [K]",
    ),
    dict(
        sheet="Liq Adsorption (Organic)", slug="adsorcion_liquido_organico", data_start=6,
        name_idx=1, formula_idx=2,
        columns=[(0, "No"), (1, "Name"), (2, "Formula"), (3, "K"),
                 (4, "one_over_n"), (5, "Xmin"), (6, "Xmax"),
                 (7, "Q_10ppmw"), (8, "Q_Xmin"), (9, "Q_Xmax")],
        ecuacion="log(Q) = log(K) + (1/n)*log(X)", unidades="Q [g/100g carbon], X [ppmw]",
    ),
    dict(
        sheet="Gas Adsorption (Organic)", slug="adsorcion_gas_organico", data_start=6,
        name_idx=1, formula_idx=2,
        columns=[(0, "No"), (1, "Name"), (2, "Formula"), (3, "K"),
                 (4, "one_over_n"), (5, "Ymin"), (6, "Ymax"),
                 (7, "Q_Y10ppmv"), (8, "Q_Ymin"), (9, "Q_Ymax")],
        ecuacion="log(Q) = log(K) + (1/n)*log(Y)", unidades="Q [g/100g carbon], Y [ppmv]",
    ),
    dict(
        sheet="Liq Vol, dipole, Van der walls", slug="volumen_dipolo_vanderwaals_organico", data_start=5,
        name_idx=1, formula_idx=2,
        columns=[(0, "No"), (1, "Name"), (2, "Formula"), (3, "T_C"),
                 (4, "solubility_param"), (5, "liq_vol"), (6, "state"),
                 (7, "dipole_moment"), (8, "vdw_area"), (9, "vdw_vol"),
                 (10, "r_gyration")],
        ecuacion=None,
        unidades="solu.param [(J/cm3)^0.5], liq_vol [cm3/mol], dipole [D], "
                 "vdw_area [cm2/mol], vdw_vol [cm3/mol], r_gyration [Angstrom]",
    ),
    dict(
        sheet="__Diffu Coeff in Air (Organic)", slug="difusividad_aire_organico", data_start=6,
        name_idx=1, formula_idx=2,
        columns=[(0, "No"), (1, "Name"), (2, "Formula"), (3, "A"), (4, "B"),
                 (5, "C"), (6, "Tmin"), (7, "Tmax"), (8, "D_25C"), (9, "D_100C")],
        ecuacion="D = A + B*T + C*T^2", unidades="D [cm2/s], T [K]",
    ),
    dict(
        sheet="Diffu Coeff in water (Organic)", slug="difusividad_agua_organico", data_start=4,
        name_idx=1, formula_idx=2,
        columns=[(0, "No"), (1, "Name"), (2, "Formula"), (3, "A"), (4, "B"),
                 (5, "Tmin"), (6, "Tmax"), (7, "D0_25C"), (8, "D0_100C")],
        ecuacion="log10(D0) = A + B/T", unidades="D0 [cm2/s], T [K]",
    ),
    dict(
        sheet="Solubility in H2O (Organic)", slug="solubilidad_agua_organico", data_start=4,
        name_idx=1, formula_idx=2,
        columns=[(0, "No"), (1, "Name"), (2, "Formula"), (3, "A"), (4, "B"),
                 (5, "C"), (6, "S_25C"), (7, "S_100C")],
        ecuacion="log10(S) = A + B/T + C/T^2", unidades="S [ppmw], T [K]",
    ),
    dict(
        sheet="Solubility in Octanol-water", slug="solubilidad_octanol_agua", data_start=5,
        name_idx=1, formula_idx=2,
        columns=[(0, "No"), (1, "Name"), (2, "Formula"), (3, "code_solubilidad"),
                 (4, "temp_C"), (5, "S_at_T_mass_ppmw"), (6, "S_at_T_mole_ppmm"),
                 (7, "code_logKow"), (8, "log_Kow")],
        ecuacion=None, unidades="S [ppmw / ppm molar], temp [C]",
    ),
    dict(
        sheet="Solubility in salt water", slug="solubilidad_agua_salada", data_start=5,
        name_idx=1, formula_idx=2,
        columns=[(0, "No"), (1, "Name"), (2, "Formula"), (3, "A"), (4, "B"),
                 (5, "C"), (6, "S_saltwater_25C"), (7, "S_saltwater_100C")],
        ecuacion="log10(S) = A + B*T + C*T^2", unidades="S [ppm], T [K]",
    ),
    dict(
        sheet="Refractive Index", slug="indice_refraccion", data_start=5,
        name_idx=1, formula_idx=2,
        columns=[(0, "No"), (1, "Name"), (2, "Formula"), (3, "MW"),
                 (4, "Tfz"), (5, "Tb"), (6, "rho"), (7, "RI_temp_C"),
                 (8, "RI_at_T_nD")],
        ecuacion=None, unidades="Tfz/Tb [K], rho [g/cm3]",
    ),
    dict(
        sheet="D°", slug="difusividad_agua_dilucion_infinita", data_start=6,
        name_idx=1, formula_idx=2,
        columns=[(0, "No"), (1, "Name"), (2, "Formula"), (3, "A"), (4, "B"),
                 (5, "Tmin"), (6, "Tmax"), (7, "D0_25C"), (8, "D0_100C")],
        ecuacion="log10(D0) = A + B/T", unidades="D0 [cm2/s], T [K]",
    ),
    dict(
        sheet="D", slug="difusividad_aire_generico", data_start=4,
        name_idx=1, formula_idx=2,
        columns=[(0, "No"), (1, "Name"), (2, "Formula"), (3, "A"), (4, "B"),
                 (5, "C"), (6, "Tmin"), (7, "Tmax"), (8, "D_25C"), (9, "D_100C")],
        ecuacion="D = A + B*T + C*T^2", unidades="D [cm2/s], T [K]",
    ),
    dict(
        sheet="Hazard", slug="peligrosidad", data_start=5,
        name_idx=1, formula_idx=2,
        columns=[(0, "No"), (1, "Name"), (2, "Formula"),
                 (3, "limite_explosivo_inferior_vol_pct"),
                 (4, "limite_explosivo_superior_vol_pct"),
                 (5, "code_limite_explosivo"), (6, "flash_point_F"),
                 (7, "code_flash_point"), (8, "autoignicion_temp_F"),
                 (9, "code_autoignicion")],
        ecuacion=None, unidades="limites explosivos [%vol], flash/autoignicion [F]",
    ),
    dict(
        sheet="Henry's Law Constant", slug="constante_henry", data_start=4,
        name_idx=1, formula_idx=2,
        columns=[(0, "No"), (1, "Name"), (2, "Formula"), (3, "MW"),
                 (4, "Tfz"), (5, "Tb"), (6, "T_C"),
                 (7, "henry_atm_por_frac_molar"), (8, "henry_atm_m3_mol")],
        ecuacion=None, unidades="Tfz/Tb [K], T [C]",
    ),
    dict(
        sheet="Threshold, Exposure", slug="limites_exposicion", data_start=5,
        name_idx=1, formula_idx=2,
        columns=[(0, "No"), (1, "Name"), (2, "Formula"),
                 (3, "limite_umbral_ppmv"), (4, "limite_umbral_mgm3"),
                 (5, "limite_exposicion_permisible_ppmv"),
                 (6, "limite_exposicion_permisible_mgm3"),
                 (7, "limite_exposicion_recomendado_ppmv"),
                 (8, "limite_exposicion_recomendado_mgm3"),
                 (9, "conc_max_lugar_trabajo_ppmv"),
                 (10, "conc_max_lugar_trabajo_mgm3")],
        ecuacion=None, unidades="ppmv y mg/m3",
    ),
]


def limpiar_valor(valor):
    """Normaliza celdas de Excel: quita espacios, placeholders '-' y NaN -> None."""
    if valor is None:
        return None
    if isinstance(valor, str):
        v = valor.strip()
        if v in ("", "-", "--", "n/a", "N/A", "NA"):
            return None
        return v
    if isinstance(valor, float) and math.isnan(valor):
        return None
    if isinstance(valor, (datetime.datetime, datetime.date, datetime.time)):
        # Excel a veces mal-interpreta un numero como fecha/hora; se recupera
        # el valor numerico original que Yaws realmente reporta.
        if isinstance(valor, datetime.time):
            return valor.hour + valor.minute / 60 + valor.second / 3600
        epoch = datetime.datetime(1899, 12, 30)
        dt = valor if isinstance(valor, datetime.datetime) else datetime.datetime.combine(valor, datetime.time())
        return (dt - epoch).total_seconds() / 86400.0
    return valor


def clave_compuesto(nombre, formula):
    if nombre:
        return nombre.strip().lower()
    if formula:
        return formula.strip().lower()
    return None


def procesar_hoja(wb, config, compuestos, metadatos_propiedades):
    ws = wb[config["sheet"]]
    slug = config["slug"]

    metadatos_propiedades[slug] = {
        "hoja_origen": config["sheet"],
        "ecuacion": config["ecuacion"],
        "unidades": config["unidades"],
    }

    filas_procesadas = 0
    for fila in ws.iter_rows(min_row=config["data_start"], values_only=True):
        registro = {}
        for idx, clave in config["columns"]:
            if idx < len(fila):
                registro[clave] = limpiar_valor(fila[idx])
            else:
                registro[clave] = None

        nombre = registro.get("Name")
        formula = registro.get("Formula")

        # fila vacia o de relleno -> se descarta
        if nombre is None and formula is None:
            continue

        clave = clave_compuesto(nombre, formula)
        if clave is None:
            continue

        registro.pop("No", None)

        if clave not in compuestos:
            compuestos[clave] = {
                "nombre": nombre if nombre else formula,
                "formula": formula,
                "propiedades": {},
            }
        else:
            if not compuestos[clave].get("formula") and formula:
                compuestos[clave]["formula"] = formula
            if not compuestos[clave].get("nombre") and nombre:
                compuestos[clave]["nombre"] = nombre

        compuestos[clave]["propiedades"].setdefault(slug, []).append(registro)
        filas_procesadas += 1

    return filas_procesadas


def escribir_sqlite(compuestos, metadatos_propiedades, ruta_db):
    ruta = Path(ruta_db)
    if ruta.exists():
        ruta.unlink()  # se regenera desde cero en cada corrida del ETL

    con = sqlite3.connect(ruta_db)
    cur = con.cursor()
    cur.execute("PRAGMA foreign_keys = ON")

    cur.execute(
        "CREATE TABLE compuestos ("
        "id INTEGER PRIMARY KEY, clave TEXT UNIQUE NOT NULL, "
        "nombre TEXT NOT NULL, formula TEXT)"
    )
    cur.execute(
        "CREATE TABLE metadatos_propiedades ("
        "slug TEXT PRIMARY KEY, hoja_origen TEXT, ecuacion TEXT, unidades TEXT)"
    )
    cur.execute(
        "CREATE TABLE parametros_binarios ("
        "compuesto_a TEXT NOT NULL, compuesto_b TEXT NOT NULL, "
        "parametro TEXT NOT NULL, valor REAL)"
    )

    cur.executemany(
        "INSERT INTO metadatos_propiedades VALUES (?,?,?,?)",
        [(slug, m["hoja_origen"], m["ecuacion"], m["unidades"])
         for slug, m in metadatos_propiedades.items()],
    )

    id_por_clave = {}
    for clave, c in compuestos.items():
        cur.execute(
            "INSERT INTO compuestos (clave, nombre, formula) VALUES (?,?,?)",
            (clave, c["nombre"], c["formula"]),
        )
        id_por_clave[clave] = cur.lastrowid

    # Una tabla por propiedad (slug), con las mismas columnas que su hoja
    # de origen en el Excel. Se recorren los propios registros ya limpios
    # (no el Excel) para no perder la limpieza aplicada arriba.
    for config in SHEET_CONFIG:
        slug = config["slug"]
        columnas = [nombre for _, nombre in config["columns"] if nombre != "No"]
        defs = ", ".join(
            f'"{c}" {"TEXT" if c in CAMPOS_TEXTO else "REAL"}' for c in columnas
        )
        cur.execute(
            f'CREATE TABLE "{slug}" (id INTEGER PRIMARY KEY, '
            f'compuesto_id INTEGER NOT NULL REFERENCES compuestos(id), {defs})'
        )
        cur.execute(f'CREATE INDEX "idx_{slug}_compuesto" ON "{slug}"(compuesto_id)')

        filas = [
            (id_por_clave[clave], *[registro.get(col) for col in columnas])
            for clave, c in compuestos.items()
            for registro in c["propiedades"].get(slug, [])
        ]
        placeholders = ", ".join(["?"] * (len(columnas) + 1))
        cur.executemany(
            f'INSERT INTO "{slug}" (compuesto_id, {", ".join(columnas)}) '
            f'VALUES ({placeholders})',
            filas,
        )

    con.commit()
    con.close()


def main():
    print(f"Cargando '{ARCHIVO_EXCEL}' ...")
    wb = openpyxl.load_workbook(ARCHIVO_EXCEL, read_only=True, data_only=True)

    compuestos = {}
    metadatos_propiedades = {}

    for config in SHEET_CONFIG:
        n = procesar_hoja(wb, config, compuestos, metadatos_propiedades)
        print(f"  {config['sheet']!r:45s} -> {n:5d} registros ({config['slug']})")

    base = {
        "metadata": {
            "fuente": ARCHIVO_EXCEL,
            "fecha_generacion": date.today().isoformat(),
            "total_compuestos": len(compuestos),
            "total_hojas_procesadas": len(SHEET_CONFIG),
            "notas": (
                "Generado automaticamente a partir del Yaws' Handbook of "
                "Thermodynamic and Physical Properties of Chemical Compounds. "
                "El libro de origen contiene UNICAMENTE propiedades de "
                "compuestos puros; no incluye parametros de interaccion "
                "binaria (NRTL, UNIQUAC, Wilson, etc.). Por eso "
                "'parametros_binarios' se deja vacio: si se dispone de otra "
                "fuente con esos parametros, deben cargarse en esa misma "
                "estructura (ver 'obtener_parametros_binarios' en repositorio.py)."
            ),
        },
        "metadatos_propiedades": metadatos_propiedades,
        "compuestos": compuestos,
        "parametros_binarios": {},
    }

    print(f"Escribiendo '{ARCHIVO_JSON_SALIDA}' ...")
    with open(ARCHIVO_JSON_SALIDA, "w", encoding="utf-8") as f:
        json.dump(base, f, ensure_ascii=False, indent=None, separators=(",", ":"))

    print(f"Escribiendo '{ARCHIVO_DB_SALIDA}' ...")
    escribir_sqlite(compuestos, metadatos_propiedades, ARCHIVO_DB_SALIDA)

    print(f"Listo. {len(compuestos)} compuestos exportados.")


if __name__ == "__main__":
    main()
