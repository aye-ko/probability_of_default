import pandas as pd 
import numpy as np 
import shap
import joblib

model = joblib.load('model.pkl')  # predicts probability of default
scaler = joblib.load('scaler.pkl') # scales numeric inputs into z-scores
binner = joblib.load('binner.pkl') # bins total_il_high_credit_limit
imputer = joblib.load('imputer.pkl') # imputes missing values
columns = joblib.load('columns.pkl') # esnures correct columnn order
numeric_cols = joblib.load('numeric_cols.pkl') # tells scaler which columns to scale
X_sample = joblib.load('X_sample.pkl') # sample of X to use as baseline for SHAP


# Function to give recommendation

def get_recommendation(prob_default):
    if prob_default <= 0.35:
        return ('Low Risk Customer, Recommend Approval')
    elif prob_default > 0.35 and prob_default <= 0.55:
        return ('Moderate Risk Customer, Recommend Further Review')
    else:
        return ('High Risk Customer, Recommend Decline')
    
    
# Function to calculate expected loss
    
def calculate_expected_loss(loan_amnt, prob_default, lgd):
    expected_loss = loan_amnt * prob_default * lgd  # Expected Loss = Loan Amount * Probability of Default * lgd
    return expected_loss

# FUnction to  predict loan default

def predict_new_loan(
    loan_amnt, dti, fico_range_low, annual_inc, revol_util,
    pub_rec_bankruptcies, tax_liens, total_il_high_credit_limit,
    term, emp_length, home_ownership, purpose, verification_status,
    lgd=0.50
):
    # Start with all columns set to 0
    input_df = pd.DataFrame(0, index=[0], columns=columns)
    
    # Fill numeric columns
    input_df['loan_amnt'] = loan_amnt
    input_df['dti'] = dti
    input_df['fico_range_low'] = fico_range_low
    input_df['annual_inc'] = annual_inc
    input_df['revol_util'] = revol_util
    input_df['pub_rec_bankruptcies'] = pub_rec_bankruptcies
    input_df['tax_liens'] = tax_liens
    
    # Handle term (reference: 36 months)
    if term == "60 months":
        input_df['term_ 60 months'] = 1
    
    # Handle emp_length (reference: 1 year)
    emp_col = f'emp_length_{emp_length}'
    if emp_col in input_df.columns:
        input_df[emp_col] = 1
    
    # Handle home_ownership (reference: ANY)
    home_col = f'home_ownership_{home_ownership}'
    if home_col in input_df.columns:
        input_df[home_col] = 1
    
    # Handle purpose (reference: car)
    purpose_col = f'purpose_{purpose}'
    if purpose_col in input_df.columns:
        input_df[purpose_col] = 1
    
    # Handle verification_status (reference: Not Verified)
    ver_col = f'verification_status_{verification_status}'
    if ver_col in input_df.columns:
        input_df[ver_col] = 1
    

    # Handle til_binned
    til_bin = binner.transform(pd.Series([total_il_high_credit_limit]), metric='bins')[0]

    if til_bin == "[423.00, inf)":
        input_df['til_binned_[423.00, inf)'] = 1
    elif til_bin == "Missing":
        input_df['til_binned_Missing'] = 1
    

    # Scale numeric features
    input_df[numeric_cols] = scaler.transform(input_df[numeric_cols])
    
    # Predict
    prob_default = model.predict_proba(input_df)[:, 1][0]
    expected_loss = calculate_expected_loss(loan_amnt, prob_default, lgd)
    recommendation = get_recommendation(prob_default)
    
    return prob_default, expected_loss, recommendation, input_df

# function to return shap report
# SHAP Report to explain the predictions of the loan default model


def shap_report(model, input_df): 
    explainer = shap.LinearExplainer(model, X_sample) # use the example sample as a baseline
    shap_values = explainer(input_df) # take the input and compare to the baseline sample
    return shap_values

# FUnction to get explanation
def shap_explanation(shap_values, input_df):
    shap_values = shap_values.values 
    shap_values = pd.Series(shap_values[0], input_df.columns)
    for_default = shap_values.sort_values(ascending=False)[:2]
    for_default = for_default.index.tolist()
    against_default = shap_values.sort_values(ascending=True)[:2]
    against_default = against_default.index.tolist()
    return for_default, against_default

# Function to tell you why a loan is denied

def denied(model, input_df):
    shap_values = shap_report(model, input_df)
    for_default, against_default = shap_explanation(shap_values, input_df)
    reasoning = ('While the following features are contributing against default: \n' + ', '.join(against_default) + '\n' +
                'The loan is denied due to the following features contributing to default: \n' + ', '.join(for_default))
    return reasoning