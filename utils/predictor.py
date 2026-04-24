import joblib
import pandas as pd

MODEL_PATH = "model/final_intensity_model.pkl"
ENCODER_PATH = "model/intensity_label_encoder.pkl"
FEATURES_PATH = "model/model_features.pkl"

model = joblib.load(MODEL_PATH)
label_encoder = joblib.load(ENCODER_PATH)
feature_cols = joblib.load(FEATURES_PATH)


def predict_intensity(input_data: dict) -> str:
    df = pd.DataFrame([input_data])
    df = df[feature_cols]
    pred = model.predict(df)[0]
    label = label_encoder.inverse_transform([pred])[0]
    return label