"""Streamlit interface for the official StreamML models."""

from __future__ import annotations

import json
from pathlib import Path

import joblib
import pandas as pd
import streamlit as st

from src.predictive_features import frame_in_contract_order

ROOT = Path(__file__).resolve().parent
RELEASE = ROOT / "models" / "release"


def read_json(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


@st.cache_resource
def load_models():
    return (
        joblib.load(RELEASE / "reactive" / "model.joblib"),
        joblib.load(RELEASE / "predictive" / "model.joblib"),
    )


def probability_frame(model, frame: pd.DataFrame, labels: list[str] | None = None) -> pd.DataFrame:
    values = model.predict_proba(frame)[0]
    names = labels or [str(value) for value in model.classes_]
    return pd.DataFrame({"Clase": names, "Probabilidad": values})


def reactive_page(model, contract: dict) -> None:
    st.header("Modelo reactivo")
    values = {
        "upload_mbps": st.number_input("Subida (Mbps)", min_value=0.0, value=8.0),
        "download_mbps": st.number_input("Descarga (Mbps)", min_value=0.0, value=20.0),
        "latency_ms": st.number_input("Latencia (ms)", min_value=0.0, value=40.0),
    }
    if st.button("Predecir perfil", type="primary"):
        frame = pd.DataFrame([values]).loc[:, contract["features"]]
        prediction = str(model.predict(frame)[0])
        st.metric("Perfil recomendado", prediction)
        st.bar_chart(probability_frame(model, frame).set_index("Clase"))


def predictive_page(model, contract: dict, threshold: float) -> None:
    st.header("Modelo predictivo")
    values = {}
    columns = st.columns(2)
    defaults = {"measurements_count": 120.0, "lookback_duration_seconds": 120.0,
                "current_profile": 2.0, "required_capacity_mbps": 3.375}
    for index, feature in enumerate(contract["features"]):
        values[feature] = columns[index % 2].number_input(feature, value=float(defaults.get(feature, 0.0)))
    if st.button("Estimar riesgo", type="primary"):
        frame = frame_in_contract_order(pd.DataFrame([values]), contract)
        classes = list(model.classes_)
        probability = float(model.predict_proba(frame)[0, classes.index(1)])
        prediction = "downgrade_needed" if probability >= threshold else "maintain"
        st.metric("Decisión", prediction)
        st.metric("Probabilidad de reducción", f"{probability:.2%}")
        st.caption(f"Umbral oficial: {threshold:.2f}")
        st.bar_chart(pd.DataFrame({"Clase": ["maintain", "downgrade_needed"],
                                  "Probabilidad": [1.0 - probability, probability]}).set_index("Clase"))


def csv_page(reactive_model, predictive_model, reactive_contract: dict, predictive_contract: dict, threshold: float) -> None:
    st.header("Predicción mediante CSV")
    role = st.segmented_control("Modelo", ["Reactivo", "Predictivo"], default="Reactivo")
    uploaded = st.file_uploader("Archivo CSV", type="csv")
    if uploaded is None:
        return
    frame = pd.read_csv(uploaded)
    contract = reactive_contract if role == "Reactivo" else predictive_contract
    missing = [feature for feature in contract["features"] if feature not in frame.columns]
    if missing:
        st.error("Faltan columnas requeridas: " + ", ".join(missing))
        return
    x = frame.loc[:, contract["features"]]
    if role == "Reactivo":
        output = frame.copy()
        output["prediction"] = reactive_model.predict(x)
        probabilities = reactive_model.predict_proba(x)
        for index, label in enumerate(reactive_model.classes_):
            output[f"probability_{label}"] = probabilities[:, index]
    else:
        x = frame_in_contract_order(frame, predictive_contract)
        probabilities = predictive_model.predict_proba(x)
        positive = probabilities[:, list(predictive_model.classes_).index(1)]
        output = frame.copy()
        output["probability_downgrade_needed"] = positive
        output["prediction"] = pd.Series(positive).ge(threshold).map({True: "downgrade_needed", False: "maintain"})
    st.dataframe(output, use_container_width=True)
    st.download_button("Descargar resultados", output.to_csv(index=False), "streamml_predictions.csv", "text/csv")


def metrics_page() -> None:
    st.header("Resultados y métricas")
    for role, title in (("reactive", "Modelo reactivo"), ("predictive", "Modelo predictivo")):
        metrics = read_json(RELEASE / role / "metrics.json")
        test = metrics["test"]
        st.subheader(title)
        columns = st.columns(3)
        columns[0].metric("Accuracy", f"{test['accuracy']:.2%}")
        columns[1].metric("Balanced accuracy", f"{test['balanced_accuracy']:.2%}")
        columns[2].metric("Macro F1", f"{test['macro_f1']:.2%}")
        st.dataframe(pd.DataFrame(test["confusion_matrix"]), use_container_width=True)


def main() -> None:
    st.set_page_config(page_title="StreamML", page_icon="📊", layout="wide")
    reactive_model, predictive_model = load_models()
    reactive_contract = read_json(ROOT / "config" / "reactive_feature_contract.json")
    predictive_contract = read_json(ROOT / "config" / "predictive_feature_contract.json")
    threshold = read_json(RELEASE / "predictive" / "threshold.json")["threshold"]
    page = st.sidebar.radio("Navegación", ["Inicio", "Modelo reactivo", "Modelo predictivo",
                                            "Predicción mediante CSV", "Resultados y métricas"])
    if page == "Inicio":
        st.title("StreamML")
        st.write("Clasificación reactiva de calidad y estimación predictiva de reducción de perfil.")
        st.info("Los resultados se calculan localmente con los dos modelos oficiales.")
    elif page == "Modelo reactivo":
        reactive_page(reactive_model, reactive_contract)
    elif page == "Modelo predictivo":
        predictive_page(predictive_model, predictive_contract, threshold)
    elif page == "Predicción mediante CSV":
        csv_page(reactive_model, predictive_model, reactive_contract, predictive_contract, threshold)
    else:
        metrics_page()


if __name__ == "__main__":
    main()
