# -*- coding: utf-8 -*-
"""
Franco Olivares
"""

import streamlit as st
import pandas as pd
import matplotlib.pyplot as plt
import seaborn as sns
import matplotlib.patheffects as path_effects

def cargar_excel_a_diccionario(ruta_archivo):
    hojas_dict = pd.read_excel(ruta_archivo, sheet_name=None, header=None, dtype=str)
    diccionario_df = {}

    for hoja, df in hojas_dict.items():
        df.dropna(how='all', inplace=True)
        df.reset_index(drop=True, inplace=True)
        if not df.empty:
            df.columns = df.iloc[0].astype(str)
            df = df.iloc[1:].reset_index(drop=True)
        diccionario_df[hoja] = df.apply(pd.to_numeric, errors='ignore')
    return diccionario_df

def parse_range(rango):
    try:
        min_val, max_val = rango.replace("%", "").split(" - ")
        return float(min_val) / 100 if "%" in rango else float(min_val), float(max_val) / 100 if "%" in rango else float(max_val)
    except ValueError:
        st.error(f"Formato incorrecto en el rango: {rango}. Debe ser 'X - Y' con valores numéricos.")
        return None, None

def generar_resumen(diccionario_df, hoja_excluir):
    if hoja_excluir not in diccionario_df:
        st.error(f"La hoja a excluir '{hoja_excluir}' no se encuentra en el diccionario.")
        return None
    df_excluir = diccionario_df[hoja_excluir]
    resumen_data = []
    for key, df in diccionario_df.items():
        if key == hoja_excluir or not {"VAN (S/)", "Instrumento"}.issubset(df.columns):
            continue
        pos_rf = df[df["Instrumento"].isin(["X0001", "X0002", "X0003", "X0005", "X0007"])]["VAN (S/)"]
        pos_rv = df[df["Instrumento"].isin(["X0006", "X0008"])]["VAN (S/)"]
        activo_fondo = df_excluir[df_excluir["Fondo"].astype(str).str.contains(key, na=False)]["Activo (S/.)"]
        activo_fondo = activo_fondo.iloc[0] if not activo_fondo.empty else 1
        posicion_rf = pos_rf.sum() / activo_fondo if not pos_rf.empty else 0
        posicion_rv = pos_rv.sum() / activo_fondo if not pos_rv.empty else 0
        duracion_ponderada = (df["VAN (S/)"] / df["VAN (S/)"].sum() * df["Duración Macaulay"]).sum() if "Duración Macaulay" in df.columns else 0
        resumen_data.append([key, posicion_rf, posicion_rv, duracion_ponderada])
    return pd.DataFrame(resumen_data, columns=["Fondo", "Posición RF", "Posición RV", "Duración Ponderada"]) if resumen_data else None

def evaluar_umbral(resumen_df, umbral_rf, umbral_rv, limite_duracion):
    min_rf, max_rf = parse_range(umbral_rf)
    min_rv, max_rv = parse_range(umbral_rv)
    min_duracion, max_duracion = parse_range(limite_duracion)
    if None in [min_rf, max_rf, min_rv, max_rv, min_duracion, max_duracion]:
        return None
    def verificar(valor, minimo, maximo):
        return "Cumple" if minimo <= valor <= maximo else "Alerta"
    resumen_df["Evaluación RF"] = resumen_df["Posición RF"].apply(lambda x: verificar(x, min_rf, max_rf))
    resumen_df["Evaluación RV"] = resumen_df["Posición RV"].apply(lambda x: verificar(x, min_rv, max_rv))
    resumen_df["Evaluación Duración"] = resumen_df["Duración Ponderada"].apply(lambda x: verificar(x, min_duracion, max_duracion))
    return resumen_df[["Fondo", "Evaluación RF", "Evaluación RV", "Evaluación Duración"]]

def graficar_resumen_premium(resumen_df, umbral_rf=(0.8, 1.0), umbral_rv=(0.0, 0.2), limite_duracion=(0, 3)):
    fig, ax = plt.subplots(figsize=(14, 7))
    colores = ["#FF6F61", "#6B5B95", "#88B04B"]
    for i, (col, label, marker) in enumerate(zip(["Posición RF", "Posición RV", "Duración Ponderada"], ["Posición RF", "Posición RV", "Duración Ponderada"], ['o', 's', 'D'])):
        ax.plot(resumen_df["Fondo"], resumen_df[col], marker=marker, markersize=10, linestyle='-', linewidth=3, color=colores[i], alpha=0.9, label=label, path_effects=[path_effects.withStroke(linewidth=5, foreground='black')])
    ax.fill_between(resumen_df["Fondo"], umbral_rf[0], umbral_rf[1], color=colores[0], alpha=0.15, label="Umbral RF")
    ax.fill_between(resumen_df["Fondo"], umbral_rv[0], umbral_rv[1], color=colores[1], alpha=0.15, label="Umbral RV")
    ax.fill_between(resumen_df["Fondo"], limite_duracion[0], limite_duracion[1], color=colores[2], alpha=0.15, label="Límite Duración")
    ax.set_ylabel("Posición", fontsize=14, fontweight="bold")
    ax.set_xlabel("Fondo", fontsize=14, fontweight="bold")
    ax.set_title("Resumen de Posiciones y Umbrales", fontsize=16, fontweight="bold")
    plt.xticks(rotation=30, fontsize=12)
    plt.yticks(fontsize=12)
    plt.legend()
    plt.tight_layout()
    st.pyplot(fig)

def main():
    st.title("Posición del Portfolio")
    archivo = st.file_uploader("Cargar archivo Excel", type=["xls", "xlsx"])
    if archivo:
        diccionario_df = cargar_excel_a_diccionario(archivo)
        hoja_excluir = st.selectbox("Seleccionar hoja de posición total de la cartera y activo por fondo", list(diccionario_df.keys()))
        if st.button("Generar Resumen"):
            resumen_df = generar_resumen(diccionario_df, hoja_excluir)
            if resumen_df is not None:
                st.session_state["resumen_df"] = resumen_df
                st.dataframe(resumen_df)
        if "resumen_df" in st.session_state:
            if st.button("Evaluar Umbrales"):
                evaluacion_df = evaluar_umbral(st.session_state["resumen_df"], "80% - 100%", "0% - 20%", "0 - 3")
                if evaluacion_df is not None:
                    st.dataframe(evaluacion_df)
                    graficar_resumen_premium(st.session_state["resumen_df"])

if __name__ == "__main__":
    main()



