import pandas as pd
from config import load_ml_assets

model, scaler, binner, imputer, columns, numeric_cols = load_ml_assets()


def get_recommendation(prob_default):
    if prob_default <= 0.35:
        return "Low Risk — Recommend Approval"
    elif prob_default <= 0.55:
        return "Moderate Risk — Recommend Further Review"
    else:
        return "High Risk — Recommend Decline"


def calculate_expected_loss(loan_amnt, prob_default, lgd=0.50):
    return loan_amnt * prob_default * lgd


def predict_new_loan(
    loan_amnt, dti, fico_range_low, annual_inc, revol_util,
    pub_rec_bankruptcies, tax_liens, total_il_high_credit_limit,
    term, emp_length, home_ownership, purpose, verification_status,
):
    input_df = pd.DataFrame(0, index=[0], columns=columns)

    # Numeric features
    input_df['loan_amnt']           = loan_amnt
    input_df['dti']                 = dti
    input_df['fico_range_low']      = fico_range_low
    input_df['annual_inc']          = annual_inc
    input_df['revol_util']          = revol_util
    input_df['pub_rec_bankruptcies']= pub_rec_bankruptcies
    input_df['tax_liens']           = tax_liens

    # Term (reference category: 36 months)
    if term == "60 months":
        input_df['term_ 60 months'] = 1

    # Employment length (reference: 1 year)
    emp_col = f'emp_length_{emp_length}'
    if emp_col in input_df.columns:
        input_df[emp_col] = 1

    # Home ownership (reference: ANY)
    home_col = f'home_ownership_{home_ownership}'
    if home_col in input_df.columns:
        input_df[home_col] = 1

    # Purpose (reference: car)
    purpose_col = f'purpose_{purpose}'
    if purpose_col in input_df.columns:
        input_df[purpose_col] = 1

    # Verification status (reference: Not Verified)
    ver_col = f'verification_status_{verification_status}'
    if ver_col in input_df.columns:
        input_df[ver_col] = 1

    # Binned total installment credit limit
    til_bin = binner.transform(
        pd.Series([total_il_high_credit_limit]), metric='bins'
    )[0]
    if til_bin == "[214.00, inf)":
        input_df['til_binned_[214.00, inf)'] = 1
    elif til_bin == "Missing":
        input_df['til_binned_Missing'] = 1

    # Column name fixes (dummy encoding edge cases)
    input_df = input_df.rename(columns={
        'emp_length_less_than_1_year': 'emp_length_< 1 year',
        'til_binned_214_plus':         'til_binned_[214.00, inf)',
    })

    # Scale numeric features
    input_df[numeric_cols] = scaler.transform(input_df[numeric_cols])

    prob_default  = model.predict_proba(input_df)[:, 1][0]
    expected_loss = calculate_expected_loss(loan_amnt, prob_default)
    recommendation = get_recommendation(prob_default)

    return prob_default, expected_loss, recommendation, input_df