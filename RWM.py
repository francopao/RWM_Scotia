# -*- coding: utf-8 -*-
"""
Created on Sat Mar 29 10:09:12 2025

@author: usuario
"""

import streamlit as st
import pandas as pd
import matplotlib.pyplot as plt

def cargar_excel_a_diccionario(ruta_archivo):
    hojas_dict = pd.read_excel(ruta_archivo, sheet_name=None, header=None, dtype=str)
    diccionario_df = {}

    for hoja, df in hojas_dict.items():
        df.dropna(how='all', inplace=True)
        df.reset_index(drop=True, inplace=True)

        if not df.empty:
            df.columns = df.iloc[0].astype(str)
            df = df.iloc[1:].reset_index(drop=True)

        # Función para manejar conversiones a numérico
        def safe_to_numeric(x):
            try:
                return pd.to_numeric(x)
            except ValueError:
                return x  # Si no es convertible a numérico, devuelve el valor original

        df = df.apply(safe_to_numeric)
        diccionario_df[hoja] = df

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

        if "Duración Macaulay" in df.columns and "VAN (S/)" in df.columns:
            duracion_ponderada = (df["VAN (S/)"] / df["VAN (S/)"].sum() * df["Duración Macaulay"]).sum()
        else:
            duracion_ponderada = 0

        resumen_data.append([key, posicion_rf, posicion_rv, duracion_ponderada])

    if not resumen_data:
        st.warning("No se encontraron datos adecuados para generar el resumen.")
        return None

    return pd.DataFrame(resumen_data, columns=["Fondo", "Posición RF", "Posición RV", "Duración Ponderada"])

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
    import matplotlib.patheffects as path_effects
    import seaborn as sns

    # Establecer el estilo de Seaborn
    sns.set_style("whitegrid")
    
    # Crear la figura
    fig, ax = plt.subplots(figsize=(14, 7))

    # Paleta de colores impactantes
    colores = ["#FF6F61", "#6B5B95", "#88B04B"]

    # Graficar líneas con efecto de sombra
    for i, (col, label, marker) in enumerate(zip(["Posición RF", "Posición RV", "Duración Ponderada"], 
                                                 ["Posición RF", "Posición RV", "Duración Ponderada"], 
                                                 ['o', 's', 'D'])):
        ax.plot(resumen_df["Fondo"], resumen_df[col], marker=marker, markersize=10, linestyle='-', linewidth=3, 
                color=colores[i], alpha=0.9, label=label, path_effects=[path_effects.withStroke(linewidth=5, foreground='black')])

    # Fondos de umbrales con degradado
    ax.fill_between(resumen_df["Fondo"], umbral_rf[0], umbral_rf[1], color=colores[0], alpha=0.15, label="Umbral RF")
    ax.fill_between(resumen_df["Fondo"], umbral_rv[0], umbral_rv[1], color=colores[1], alpha=0.15, label="Umbral RV")
    ax.fill_between(resumen_df["Fondo"], limite_duracion[0], limite_duracion[1], color=colores[2], alpha=0.15, label="Límite Duración")

    # Personalización del gráfico
    ax.set_ylabel("Posición", fontsize=14, fontweight="bold", color="#333333")
    ax.set_xlabel("Fondo", fontsize=14, fontweight="bold", color="#333333")
    ax.set_title("Resumen de Posiciones y Umbrales", fontsize=16, fontweight="bold", color="#222222")

    # Mejorar etiquetas del eje X
    plt.xticks(rotation=30, fontsize=12, color="#333333")
    plt.yticks(fontsize=12, color="#333333")

    # Agregar anotaciones automáticas en los puntos más relevantes
    for i, fondo in enumerate(resumen_df["Fondo"]):
        ax.text(fondo, resumen_df["Posición RF"].iloc[i] + 0.02, f"{resumen_df['Posición RF'].iloc[i]:.2f}", 
                ha='center', fontsize=10, fontweight='bold', color=colores[0])
        ax.text(fondo, resumen_df["Posición RV"].iloc[i] + 0.02, f"{resumen_df['Posición RV'].iloc[i]:.2f}", 
                ha='center', fontsize=10, fontweight='bold', color=colores[1])
        ax.text(fondo, resumen_df["Duración Ponderada"].iloc[i] + 0.02, f"{resumen_df['Duración Ponderada'].iloc[i]:.2f}", 
                ha='center', fontsize=10, fontweight='bold', color=colores[2])

    # Mejorar la leyenda con efecto de sombra
    legend = ax.legend(loc='best', fontsize='medium', frameon=True, fancybox=True, shadow=True, borderpad=1)
    for text in legend.get_texts():
        text.set_color("#222222")

    # Ajustar márgenes
    plt.tight_layout()

    # Mostrar el gráfico
    st.pyplot(fig)

def main():
    st.image("https://i.pinimg.com/474x/5d/47/07/5d4707dfb4cfe73ff831c55cd64c9e49.jpg", width=250)
    st.title("Posición del Portfolio")
    archivo = st.file_uploader("Cargar archivo Excel", type=["xls", "xlsx"])

    if archivo:
        diccionario_df = cargar_excel_a_diccionario(archivo)
        hojas = list(diccionario_df.keys())

        if not hojas:
            st.error("No se encontraron hojas en el archivo cargado.")
            return

        hoja_excluir = st.selectbox("Seleccionar hoja de posición total de la cartera y activo por fondo", hojas)

        if st.button("Generar Resumen"):
            resumen_df = generar_resumen(diccionario_df, hoja_excluir)
            if resumen_df is not None:
                st.session_state["resumen_df"] = resumen_df
                st.dataframe(resumen_df)

        if "resumen_df" in st.session_state:
            with st.form(key="umbrales_form"):
                umbral_rf = st.text_input("Umbral RF", "80% - 100%")
                umbral_rv = st.text_input("Umbral RV", "0% - 20%")
                limite_duracion = st.text_input("Límite Duración", "0 - 3")
                submit_button = st.form_submit_button(label="Evaluar Umbrales")

            if submit_button:
                evaluacion_df = evaluar_umbral(st.session_state["resumen_df"], umbral_rf, umbral_rv, limite_duracion)
                if evaluacion_df is not None:
                    st.dataframe(evaluacion_df)
                    graficar_resumen_premium(st.session_state["resumen_df"])

    st.markdown("---")
    st.markdown("Riesgos Wealth Management - Franco Olivares")

if __name__ == "__main__":
    main()






"""
import streamlit as st 
import pandas as pd
import matplotlib.pyplot as plt

def cargar_excel_a_diccionario(ruta_archivo):
    hojas_dict = pd.read_excel(ruta_archivo, sheet_name=None, header=None, dtype=str)
    diccionario_df = {}
    
    for hoja, df in hojas_dict.items():
        df.dropna(how='all', inplace=True)
        df.reset_index(drop=True, inplace=True)
        
        if not df.empty:
            df.columns = df.iloc[0].astype(str)
            df = df.iloc[1:].reset_index(drop=True)
        
        def convertir_numerico(valor):
            if pd.isna(valor):
                return valor
            if isinstance(valor, str) and valor.replace('.', '', 1).isdigit():
                try:
                    return float(valor) if '.' in valor else int(valor)
                except ValueError:
                    return valor
            return valor
        
        df = df.map(convertir_numerico)
        diccionario_df[hoja] = df
    
    return diccionario_df

def parse_range(rango):
    min_val, max_val = rango.replace("%", "").split(" - ")
    return float(min_val) / 100 if "%" in rango else float(min_val), float(max_val) / 100 if "%" in rango else float(max_val)

def generar_resumen(diccionario_df, hoja_excluir):
    if hoja_excluir not in diccionario_df:
        raise ValueError(f"La hoja a excluir '{hoja_excluir}' no se encuentra en el diccionario.")
    
    df_excluir = diccionario_df[hoja_excluir]
    
    resumen_data = []
    
    for key, df in diccionario_df.items():
        if key == hoja_excluir:
            continue
        
        if "VAN (S/)" not in df.columns or "Instrumento" not in df.columns:
            continue
        
        pos_rf = df[df["Instrumento"].isin(["X0001", "X0002", "X0007"])]
        suma_rf = pos_rf["VAN (S/)"] if not pos_rf.empty else pd.Series(dtype=float)
        
        pos_rv = df[df["Instrumento"].isin(["X0006", "X0008"])]
        suma_rv = pos_rv["VAN (S/)"] if not pos_rv.empty else pd.Series(dtype=float)
        
        activo_fondo = df_excluir[df_excluir["Fondo"].astype(str).str.contains(key, na=False)]["Activo (S/.)"]
        activo_fondo = activo_fondo.iloc[0] if not activo_fondo.empty else 1  
        
        posicion_rf = suma_rf.sum() / activo_fondo
        posicion_rv = suma_rv.sum() / activo_fondo
        
        suma_van = df["VAN (S/)"] if "VAN (S/)" in df.columns else pd.Series(dtype=float)
        if "Duración Macaulay" in df.columns and not suma_van.empty:
            duracion_ponderada = (suma_van / suma_van.sum() * df["Duración Macaulay"]).sum()
        else:
            duracion_ponderada = 0
        
        resumen_data.append([key, posicion_rf, posicion_rv, duracion_ponderada])
    
    resumen_df = pd.DataFrame(resumen_data, columns=["Fondo", "Posición RF", "Posición RV", "Duración Ponderada"])
    return resumen_df

def evaluar_umbral(resumen_df, umbral_rf="80% - 100%", umbral_rv="0% - 20%", limite_duracion="0 - 3"):
    min_rf, max_rf = parse_range(umbral_rf)
    min_rv, max_rv = parse_range(umbral_rv)
    min_duracion, max_duracion = parse_range(limite_duracion)
    
    def verificar(valor, minimo, maximo):
        return "Cumple" if minimo <= valor <= maximo else "Alerta"
    
    evaluacion_df = resumen_df.copy()
    evaluacion_df["Evaluación RF"] = resumen_df["Posición RF"].apply(lambda x: verificar(x, min_rf, max_rf))
    evaluacion_df["Evaluación RV"] = resumen_df["Posición RV"].apply(lambda x: verificar(x, min_rv, max_rv))
    evaluacion_df["Evaluación Duración"] = resumen_df["Duración Ponderada"].apply(lambda x: verificar(x, min_duracion, max_duracion))
    
    return evaluacion_df[["Fondo", "Evaluación RF", "Evaluación RV", "Evaluación Duración"]]

def main():
    st.image("https://i.pinimg.com/474x/5d/47/07/5d4707dfb4cfe73ff831c55cd64c9e49.jpg", width=250)
    st.title("Posición del Portfolio")
    archivo = st.file_uploader("Cargar archivo Excel", type=["xls", "xlsx"])
    
    if archivo:
        diccionario_df = cargar_excel_a_diccionario(archivo)
        hojas = list(diccionario_df.keys())
        hoja_excluir = st.selectbox("Seleccionar hoja de posición total de la cartera y activo por fondo", hojas)
        
        if st.button("Generar Resumen"):
            resumen_df = generar_resumen(diccionario_df, hoja_excluir)
            st.session_state["resumen_df"] = resumen_df
            st.dataframe(resumen_df)
        
        if "resumen_df" in st.session_state:
            umbral_rf = st.text_input("Umbral RF", "80% - 100%")
            umbral_rv = st.text_input("Umbral RV", "0% - 20%")
            limite_duracion = st.text_input("Límite Duración", "0 - 3")
            
            if st.button("Evaluar Umbrales"):
                evaluacion_df = evaluar_umbral(st.session_state["resumen_df"], umbral_rf, umbral_rv, limite_duracion)
                st.dataframe(evaluacion_df)
                
                fig, ax = plt.subplots(figsize=(10, 6))
                ax.plot(st.session_state["resumen_df"]["Fondo"], st.session_state["resumen_df"]["Posición RF"], marker='o', label="Posición RF")
                ax.plot(st.session_state["resumen_df"]["Fondo"], st.session_state["resumen_df"]["Posición RV"], marker='s', label="Posición RV")
                ax.plot(st.session_state["resumen_df"]["Fondo"], st.session_state["resumen_df"]["Duración Ponderada"], marker='^', label="Duración Ponderada")
                ax.set_ylabel("Posición")
                ax.set_xlabel("Fondo")
                ax.set_title("Resumen de Posiciones y Umbrales")
                plt.xticks(rotation=45)
                plt.grid()
                ax.legend()
                st.pyplot(fig)
    
    st.markdown("---")
    st.markdown("Riesgos Wealth Management - Franco Olivares")

if __name__ == "__main__":
    main()
"""

















"""
import streamlit as st
import pandas as pd
import matplotlib.pyplot as plt

def cargar_excel_a_diccionario(ruta_archivo):
    hojas_dict = pd.read_excel(ruta_archivo, sheet_name=None, header=None, dtype=str)
    diccionario_df = {}
    
    for hoja, df in hojas_dict.items():
        df.dropna(how='all', inplace=True)
        df.reset_index(drop=True, inplace=True)
        
        if not df.empty:
            df.columns = df.iloc[0].astype(str)
            df = df.iloc[1:].reset_index(drop=True)
        
        def convertir_numerico(valor):
            if pd.isna(valor):
                return valor
            if isinstance(valor, str) and valor.replace('.', '', 1).isdigit():
                try:
                    return float(valor) if '.' in valor else int(valor)
                except ValueError:
                    return valor
            return valor
        
        df = df.map(convertir_numerico)
        diccionario_df[hoja] = df
    
    return diccionario_df

def generar_resumen(diccionario_df, hoja_excluir):
    if hoja_excluir not in diccionario_df:
        raise ValueError(f"La hoja a excluir '{hoja_excluir}' no se encuentra en el diccionario.")
    
    df_excluir = diccionario_df[hoja_excluir]
    
    resumen_data = []
    
    for key, df in diccionario_df.items():
        if key == hoja_excluir:
            continue
        
        if "VAN (S/)" not in df.columns or "Instrumento" not in df.columns:
            continue
        
        pos_rf = df[df["Instrumento"].isin(["X0001", "X0002", "X0007"])]
        suma_rf = pos_rf["VAN (S/)"] if not pos_rf.empty else pd.Series(dtype=float)
        
        pos_rv = df[df["Instrumento"].isin(["X0006", "X0008"])]
        suma_rv = pos_rv["VAN (S/)"] if not pos_rv.empty else pd.Series(dtype=float)
        
        activo_fondo = df_excluir[df_excluir["Fondo"].astype(str).str.contains(key, na=False)]["Activo (S/.)"]
        activo_fondo = activo_fondo.iloc[0] if not activo_fondo.empty else 1  
        
        posicion_rf = suma_rf.sum() / activo_fondo
        posicion_rv = suma_rv.sum() / activo_fondo
        
        suma_van = df["VAN (S/)"] if "VAN (S/)" in df.columns else pd.Series(dtype=float)
        if "Duración Macaulay" in df.columns and not suma_van.empty:
            duracion_ponderada = (suma_van / suma_van.sum() * df["Duración Macaulay"]).sum()
        else:
            duracion_ponderada = 0
        
        resumen_data.append([key, posicion_rf, posicion_rv, duracion_ponderada])
    
    resumen_df = pd.DataFrame(resumen_data, columns=["Fondo", "Posición RF", "Posición RV", "Duración Ponderada"])
    return resumen_df

def evaluar_umbral(resumen_df, umbral_rf="80% - 100%", umbral_rv="0% - 20%", limite_duracion="0 - 3"):
    def parse_range(rango):
        min_val, max_val = rango.replace("%", "").split(" - ")
        return float(min_val) / 100 if "%" in rango else float(min_val), float(max_val) / 100 if "%" in rango else float(max_val)
    
    min_rf, max_rf = parse_range(umbral_rf)
    min_rv, max_rv = parse_range(umbral_rv)
    min_duracion, max_duracion = parse_range(limite_duracion)
    
    def verificar(valor, minimo, maximo):
        return "Cumple" if minimo <= valor <= maximo else "Alerta"
    
    evaluacion_df = resumen_df.copy()
    evaluacion_df["Evaluación RF"] = resumen_df["Posición RF"].apply(lambda x: verificar(x, min_rf, max_rf))
    evaluacion_df["Evaluación RV"] = resumen_df["Posición RV"].apply(lambda x: verificar(x, min_rv, max_rv))
    evaluacion_df["Evaluación Duración"] = resumen_df["Duración Ponderada"].apply(lambda x: verificar(x, min_duracion, max_duracion))
    
    return evaluacion_df[["Fondo", "Evaluación RF", "Evaluación RV", "Evaluación Duración"]]

def main():
    st.title("Análisis Financiero con Streamlit")
    archivo = st.file_uploader("Cargar archivo Excel", type=["xls", "xlsx"])
    
    if archivo:
        diccionario_df = cargar_excel_a_diccionario(archivo)
        hojas = list(diccionario_df.keys())
        hoja_excluir = st.selectbox("Seleccionar hoja a excluir", hojas)
        
        if st.button("Generar Resumen"):
            resumen_df = generar_resumen(diccionario_df, hoja_excluir)
            st.session_state["resumen_df"] = resumen_df
            st.dataframe(resumen_df)
        
        if "resumen_df" in st.session_state:
            umbral_rf = st.text_input("Umbral RF", "80% - 100%")
            umbral_rv = st.text_input("Umbral RV", "0% - 20%")
            limite_duracion = st.text_input("Límite Duración", "0 - 3")
            
            if st.button("Evaluar Umbrales"):
                evaluacion_df = evaluar_umbral(st.session_state["resumen_df"], umbral_rf, umbral_rv, limite_duracion)
                st.dataframe(evaluacion_df)
                
                fig, ax = plt.subplots(figsize=(10, 6))
                ax.plot(st.session_state["resumen_df"]["Fondo"], st.session_state["resumen_df"]["Posición RF"], marker='o', label="Posición RF")
                ax.plot(st.session_state["resumen_df"]["Fondo"], st.session_state["resumen_df"]["Posición RV"], marker='s', label="Posición RV")
                ax.plot(st.session_state["resumen_df"]["Fondo"], st.session_state["resumen_df"]["Duración Ponderada"], marker='^', label="Duración Ponderada")
                ax.set_ylabel("Valores")
                ax.set_xlabel("Fondo")
                ax.set_title("Resumen de Posiciones y Umbrales")
                plt.xticks(rotation=45)
                plt.grid()
                ax.legend()
                st.pyplot(fig)

if __name__ == "__main__":
    main()
"""



