import pandas as pd 
import numpy as np 
import shap
import joblib
import streamlit as st

# We import the database fetcher so our bridge function at the bottom works!

# ── Loaders ─────────────────────────────────────────────────────────────
@st.cache_resource
def load_ml_assets():
    model = joblib.load('model.pkl')       
    scaler = joblib.load('scaler.pkl')     
    binner = joblib.load('binner.pkl')     
    imputer = joblib.load('imputer.pkl')   
    columns = joblib.load('columns.pkl')   
    numeric_cols = joblib.load('numeric_cols.pkl') 
    return model, scaler, binner, imputer, columns, numeric_cols

model, scaler, binner, imputer, columns, numeric_cols, = load_ml_assets()

# ── Helpers ─────────────────────────────────────────────────────────────
def get_recommendation(prob_default):
    if prob_default <= 0.35:
        return 'Low Risk Customer, Recommend Approval'
    elif prob_default > 0.35 and prob_default <= 0.55:
        return 'Moderate Risk Customer, Recommend Further Review'
    else:
        return 'High Risk Customer, Recommend Decline'

def calculate_expected_loss(loan_amnt, prob_default, lgd=0.50):
    return loan_amnt * prob_default * lgd

# ── Core Prediction ─────────────────────────────────────────────────────
def predict_new_loan(
    loan_amnt, dti, fico_range_low, annual_inc, revol_util,
    pub_rec_bankruptcies, tax_liens, total_il_high_credit_limit,
    term, emp_length, home_ownership, purpose, verification_status,
    lgd=0.50
):
    input_df = pd.DataFrame(0, index=[0], columns=columns)
    
    input_df['loan_amnt'] = loan_amnt
    input_df['dti'] = dti
    input_df['fico_range_low'] = fico_range_low
    input_df['annual_inc'] = annual_inc
    input_df['revol_util'] = revol_util
    input_df['pub_rec_bankruptcies'] = pub_rec_bankruptcies
    input_df['tax_liens'] = tax_liens
    
    if term == "60 months": input_df['term_ 60 months'] = 1
    
    emp_col = f'emp_length_{emp_length}'
    if emp_col in input_df.columns: input_df[emp_col] = 1
    
    home_col = f'home_ownership_{home_ownership}'
    if home_col in input_df.columns: input_df[home_col] = 1
    
    purpose_col = f'purpose_{purpose}'
    if purpose_col in input_df.columns: input_df[purpose_col] = 1
    
    ver_col = f'verification_status_{verification_status}'
    if ver_col in input_df.columns: input_df[ver_col] = 1
    
    til_bin = binner.transform(pd.Series([total_il_high_credit_limit]), metric='bins')[0]
    if til_bin == "[423.00, inf)": input_df['til_binned_[423.00, inf)'] = 1
    elif til_bin == "Missing": input_df['til_binned_Missing'] = 1
    
    input_df[numeric_cols] = scaler.transform(input_df[numeric_cols])
    
    prob_default = model.predict_proba(input_df)[:, 1][0]
    expected_loss = calculate_expected_loss(loan_amnt, prob_default, lgd)
    recommendation = get_recommendation(prob_default)
    
    return prob_default, expected_loss, recommendation, input_df

# ── SHAP Explainability ─────────────────────────────────────────────────
def shap_report(model, input_df): 
    explainer = shap.LinearExplainer(model) 
    return explainer(input_df) 

def shap_explanation(shap_values, input_df):
    shap_values = shap_values.values 
    shap_values = pd.Series(shap_values[0], input_df.columns)
    for_default = shap_values.sort_values(ascending=False)[:2].index.tolist()
    against_default = shap_values.sort_values(ascending=True)[:2].index.tolist()
    return for_default, against_default

def denied(model, input_df):
    shap_values = shap_report(model, input_df)
    for_default, against_default = shap_explanation(shap_values, input_df)
    reasoning = ('While the following features are contributing against default: \n' + ', '.join(against_default) + '\n' +
                'The loan is denied due to the following features contributing to default: \n' + ', '.join(for_default))
    return reasoning

# ── The Bridge ──────────────────────────────────────────────────────────
def get_and_predict_loan_application(engine, application_id):
    from db_utils import get_loan_application  
    
    success, result = get_loan_application(engine, application_id)
    if not success:
        return False, result
    
    application = result
    
    # We use .get() here to prevent KeyErrors if the DB column names 
    # differ slightly or if a column is missing (like total_il_high_credit_limit)
    prob_default, expected_loss, recommendation, input_df = predict_new_loan(
        loan_amnt=application.get('loan_amount', 0),  # <-- Fixed key name here!
        dti=application.get('dti', 0),
        fico_range_low=application.get('fico_range_low', 0),
        annual_inc=application.get('annual_inc', 0),
        revol_util=application.get('revol_util', 0),
        pub_rec_bankruptcies=application.get('pub_rec_bankruptcies', 0),
        tax_liens=application.get('tax_liens', 0),
        total_il_high_credit_limit=application.get('total_il_high_credit_limit', 0), # Protects against missing DB column
        term=application.get('term', '36 months'),
        emp_length=application.get('emp_length', '< 1 year'),
        home_ownership=application.get('home_ownership', 'RENT'),
        purpose=application.get('purpose', 'other'),
        verification_status=application.get('verification_status', 'Not Verified')
    )
    
    return True, {
        "probability_of_default": prob_default, 
        "expected_loss": expected_loss, 
        "recommendation": recommendation
    }