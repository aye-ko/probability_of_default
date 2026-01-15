# Credit Risk Loan Predictor

## Overview

Used for underwriters to quickly assess whether to approve a loan, dismiss a loan or review further based on the probability of default and the expected loss based on the probability of default and recovery. 


## Business Problem

Underwriters evaluating loan applications can quickly determine, based on certain features, the probability of loan default. 


This takes input from the underwriter, estimates the probability that the applicant will default on their loan (expected loss given default rate of 50%), and recommends the applicant's risk category. 

## Live Demo
[https://probabilitydefaultcalculator.streamlit.app/]

## Business Problem

Saves underwriters' time when reviewing multiple loan applications on who to quickly approve, who to deny immediately, and who needs further review based on bank guidelines for conservative or aggressive approaches to lending. 


## Data
- Source: Lending Club via Kaggle
- Size: 1.3M+ loans
- Features used: FICO, DTI, loan amount, purpose, etc.

## Methodology
1. Data cleaning (SQL)
2. Feature engineering 
3. Model selection : Logistic Regression 
4. Evaluation (Recall-focused for catching defaults)

## Key Findings

- 60-month loans are significantly riskier than 36-month
- Small business loans have highest default rate
=======
- 60-month loans are significantly riskier than 36-month loans
- Small business loans have the highest default rate
>>>>>>> e86d8ee00edd2303caafdd92219d8eb4d26b62dc
- Verified income correlates with MORE defaults (selection bias)
- Model achieves 62% recall on defaults

## Model Performance
- Recall (Defaults):  62%
- Accuracy:  64%
- Precision: 30% 

## Tech Stack
- Python, SQL, PostgreSQL
- scikit-learn, XGBoost, OptBinning
- Streamlit (deployment)

## How to Run Locally
1. Clone repo
2. `pip install -r requirements.txt`
3. `streamlit run app.py`

## Future Improvements
- Docker deployment
- Monte Carlo simulation for portfolio risk
- Additional features (payment history, etc.)

## Contact
Onyedikachukwu Okonkwo
https://www.linkedin.com/in/onyedikachukwu-okonkwo/

okonkwo.employee@gmail.com
=======

okonkwo.employee@gmail.com


