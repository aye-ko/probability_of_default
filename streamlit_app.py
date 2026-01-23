import streamlit as st
import pandas as pd
import joblib
from optbinning import OptimalBinning # for binning total_il_high_credit_limit
import re # for email validation
# Function to give recommendation based on probability of default
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

    if til_bin == "[214.00, inf)":
        input_df['til_binned_[214.00, inf)'] = 1
    elif til_bin == "Missing":
        input_df['til_binned_Missing'] = 1
    
    # Rename columns back to what the model expects
    input_df = input_df.rename(columns={
    'emp_length_less_than_1_year': 'emp_length_< 1 year',
    'til_binned_214_plus': 'til_binned_[214.00, inf)'
    })
    # Scale numeric features
    input_df[numeric_cols] = scaler.transform(input_df[numeric_cols])
    
    # Predict
    prob_default = model.predict_proba(input_df)[:, 1][0]
    expected_loss = calculate_expected_loss(loan_amnt, prob_default, lgd)
    recommendation = get_recommendation(prob_default)
    
    return prob_default, expected_loss, recommendation

# load the pickle files into the app.py

model = joblib.load('model.pkl')  # predicts probability of default
scaler = joblib.load('scaler.pkl') # scales numeric inputs into z-scores
binner = joblib.load('binner.pkl') # bins total_il_high_credit_limit
imputer = joblib.load('imputer.pkl') # imputes missing values
columns = joblib.load('columns.pkl') # esnures correct columnn order
numeric_cols = joblib.load('numeric_cols.pkl') # tells scaler which columns to scale

# App Title

st.title("Credit Risk Loan Prediction App")
st.write("This app predicts the probability of loan default based on user inputs.")
st.write("Please fill in the following details to get Probability of Default, Estimated Loss and Recommendation:" )

# User Inputs Field
# Customer information
customer_name = st.text_input("Customer Name", placeholder="John Doe", max_chars= 50)
customer_id = st.text_input("Customer ID", placeholder="123456", max_chars=50)
customer_phone = st.text_input("Customer Phone Number", placeholder="(123) 456-7890", max_chars=15)
customer_email = st.text_input("Customer Email", placeholder="xxx@xxx.xxx", max_chars=50)

# numeric inputs
loan_amnt = st.number_input("Loan Amount", min_value=500, max_value=50000, placeholder=10000, step=500)
monthly_debt = st.number_input("Monthly Debt", min_value=0, max_value=20000, placeholder=500, step=500,)
fico_range_low = st.number_input("FICO Score", min_value=300, max_value=850, placeholder=680, step=1)
annual_inc = st.number_input("Annual Income", min_value=1000, max_value=1000000, placeholder=60000, step=1000)
dti = monthly_debt / (annual_inc / 12) * 100 if annual_inc > 0 else 0
revol_util = st.number_input("Revolving Line Utilization Rate (%)", min_value=0.0, max_value=200.0, placeholder=30.0, step=0.1)
pub_rec_bankruptcies = st.number_input("Number of Public Record Bankruptcies", min_value=0, max_value=10, placeholder=0, step=1)
tax_liens = st.number_input("Number of Tax Liens", min_value=0, max_value=10, placeholder=0, step=1)
total_il_high_credit_limit = st.number_input("Total Installment Credit Limit", min_value=0, max_value=1000000, placeholder=20000, step=1000)

# drop downs for categorical inputs
term = st.selectbox("Loan Term", options=["36 months", "60 months"])
emp_length = st.selectbox("Employment Length", options=["< 1 year", "1 year", "2 years", "3 years", "4 years", "5 years", "6 years", "7 years", "8 years", "9 years", "10+ years","nan"])
home_ownership = st.selectbox("Home Ownership", options=["RENT", "OWN", "MORTGAGE", "OTHER"])
purpose = st.selectbox("Purpose of Loan", options=["debt_consolidation", "credit_card", "home_improvement", "major_purchase", "small_business", "car", "wedding", "medical", "moving", "vacation", "house", "educational", "renewable_energy", "other"])
verification_status = st.selectbox("Verification Status", options=["Verified", "Source Verified", "Not Verified"])

# button for prediction

if st.button("Predict"):
    
    email_pattern = r'^[\w\.-]+@[\w\.-]+\.\w+$'
    if not re.match(email_pattern, customer_email):
        st.error("Invalid email format. Please enter a valid email address.")
    elif len(customer_name) < 2:
        st.error("Enter valid customer name.")
    elif len(customer_id) < 2:
        st.error("Enter valid customer ID.")
    elif len(customer_phone) < 10:
        st.error("Enter valid customer phone number.")
    else:
        prob_default, expected_loss, recommendation = predict_new_loan(
            loan_amnt, dti, fico_range_low, annual_inc, revol_util,
            pub_rec_bankruptcies, tax_liens, total_il_high_credit_limit,
            term, emp_length, home_ownership, purpose, verification_status
        )
        
        st.subheader("Prediction Results:")
        st.write(f"Probability of Default: {prob_default:.2%}")
        st.write(f"Estimated Loss: ${expected_loss:.2f}")
        st.write(f"Recommendation: {recommendation}")


