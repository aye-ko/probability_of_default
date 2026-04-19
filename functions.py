import pandas as pd 
import numpy as np 
import shap
import joblib
from sqlalchemy import create_engine, text
from dotenv import load_dotenv
from urllib.parse import quote_plus
import streamlit as st
import os


load_dotenv()
model = joblib.load('model.pkl')  # predicts probability of default
scaler = joblib.load('scaler.pkl') # scales numeric inputs into z-scores
binner = joblib.load('binner.pkl') # bins total_il_high_credit_limit
imputer = joblib.load('imputer.pkl') # imputes missing values
columns = joblib.load('columns.pkl') # esnures correct columnn order
numeric_cols = joblib.load('numeric_cols.pkl') # tells scaler which columns to scale
X_sample = joblib.load('X_sample.pkl') # sample of X to use as baseline for SHAP


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

def get_and_predict_loan_application(engine, application_id):
    success, result = get_loan_application(engine, application_id)
    if not success:
        return False, result
    
    application = result
    prob_default, expected_loss, recommendation, input_df = predict_new_loan(
        loan_amnt=application['loan_amnt'],
        dti=application['dti'],
        fico_range_low=application['fico_range_low'],
        annual_inc=application['annual_inc'],
        revol_util=application['revol_util'],
        pub_rec_bankruptcies=application['pub_rec_bankruptcies'],
        tax_liens=application['tax_liens'],
        total_il_high_credit_limit=application['total_il_high_credit_limit'],
        term=application['term'],
        emp_length=application['emp_length'],
        home_ownership=application['home_ownership'],
        purpose=application['purpose'],
        verification_status=application['verification_status']
    )
    
    return True, {
        "probability_of_default": prob_default,
        "expected_loss": expected_loss,
        "recommendation": recommendation
    }
# CRUD FUNCTIONS

# Function to Connect to the database
def create_db_connection():
    try:
        supabase_pwd = quote_plus(st.secrets["supabase_pwd"])
        supabase_user = st.secrets["supabase_user"]
        supabase_host = st.secrets["supabase_host"]
        supabase_port = st.secrets["supabase_port"]
        supabase_name = st.secrets["supabase_dbname"]
        
    except KeyError:
        load_dotenv()
        supabase_pwd = quote_plus(os.getenv("supabase_pwd"))
        supabase_user = os.getenv("supabase_user")
        supabase_host = os.getenv("supabase_host")
        supabase_port = os.getenv("supabase_port")
        supabase_name = os.getenv("supabase_dbname")
        
    engine = create_engine(f'postgresql://{supabase_user}:{supabase_pwd}@{supabase_host}:{supabase_port}/{supabase_name}')
    return engine

def create_customer(engine, customer_fname, customer_lname, customer_email, customer_phone, customer_password):
    try:
        with engine.connect() as connection:
            result = connection.execute(text("""
                INSERT INTO customer (customer_fname, customer_lname, customer_email, customer_phone, customer_password)
                VALUES (:customer_fname, :customer_lname, :customer_email, :customer_phone, :customer_password)
                RETURNING customer_id;
            """), {
                'customer_fname': customer_fname,
                'customer_lname': customer_lname,
                'customer_email': customer_email,
                'customer_phone': customer_phone,
                'customer_password': customer_password
            })
            connection.commit()
            return True, "Customer created successfully"
    except Exception as e:
        return False, f"Error creating customer: {str(e)}"
    
def login_customer(engine, customer_email, customer_password):
    try:
        with engine.connect() as connection:
            result = connection.execute(
                text("SELECT * FROM customer where customer_email = :customer_email AND customer_password = :customer_password"),
                {"customer_email": customer_email, "customer_password": customer_password}
            )
            customer = result.fetchone() 
            
            if customer:
                return True, dict(customer.mapping)
            else: 
                return False, "Invalid email or password"
    except Exception as e:
        return False, f"Error logging in: {str(e)}"
    
def get_customer(engine, customer_email=None, customer_id=None, customer_phone=None):
    try:
        if customer_email is None and customer_id is None and customer_phone is None:
            return False, "At least one identifier (email, id, or phone) must be provided"
            
        with engine.connect() as connection:
            result = connection.execute(
                text("SELECT * FROM customer where customer_email = :customer_email OR customer_id = :customer_id OR customer_phone = :customer_phone"),
                {"customer_email": customer_email,
                "customer_id": customer_id,
                "customer_phone": customer_phone}
            )
            customer = result.fetchone() 
            
            if customer:
                return True, dict(customer.mapping)
            else: 
                return False, "Customer not found"
    except Exception as e:
        return False, f"Error retrieving customer: {str(e)}"
    
def update_customer(engine, customer_id, customer_email=None, customer_phone=None, customer_password=None):
    try:
        with engine.connect() as connection:
            update_fields = []
            values = {"customer_id": customer_id}
            
            if customer_email is not None:
                update_fields.append("customer_email = :customer_email")
                values["customer_email"] = customer_email
                
            if customer_phone is not None:
                update_fields.append("customer_phone = :customer_phone")
                values["customer_phone"] = customer_phone
                
            if customer_password is not None:
                update_fields.append("customer_password = :customer_password")
                values["customer_password"] = customer_password
                
            if not update_fields:
                return False, "No fields to update"
            
            connection.execute(
                text(f"UPDATE customer SET {', '.join(update_fields)} WHERE customer_id = :customer_id"),
                values
            )
            connection.commit()
            return True, "Customer updated successfully"
    except Exception as e:
        return False, f"Error updating customer: {str(e)}"
    
def delete_customer(engine, customer_id=None, customer_email=None, customer_phone=None):
    try:
        if customer_email is None and customer_id is None and customer_phone is None:
            return False, "At least one identifier (email, id, or phone) must be provided"
        
        with engine.connect() as connection:
            connection.execute(
                text("DELETE FROM customer WHERE customer_id = :customer_id OR customer_phone = :customer_phone OR customer_email = :customer_email"),
                {"customer_id": customer_id,
                "customer_email": customer_email,
                "customer_phone": customer_phone}
            )
            connection.commit()
            return True, "Customer deleted successfully"
    except Exception as e:
        return False, f"Error deleting customer: {str(e)}"
    
    
    # Create Employee, Get Employee, Update Employee, Delete Employee functions would be similar to the above functions but for the employee table instead of the customer table.
    
def create_employee(engine, employee_fname, employee_lname, employee_email, employee_phone, employee_password, isManager=False):
    try:
        with engine.connect() as connection:
            result = connection.execute(text("""
                INSERT INTO employee (employee_fname, employee_lname, employee_email, employee_phone, employee_password, isManager)
                VALUES (:employee_fname, :employee_lname, :employee_email, :employee_phone, :employee_password, :isManager)
                RETURNING employee_id;
            """), {
                'employee_fname': employee_fname,
                'employee_lname': employee_lname,
                'employee_email': employee_email,
                'employee_phone': employee_phone,
                'employee_password': employee_password,
                'isManager': isManager
            })
            connection.commit()
            return True, "Employee created successfully"
    except Exception as e:
        return False, f"Error creating employee: {str(e)}"
        
def update_employee(engine, employee_id, employee_email=None, employee_phone=None, employee_password=None, isManager=None):
    try:
        with engine.connect() as connection:
            update_fields = []
            values = {"employee_id": employee_id}
            
            if employee_email is not None:
                update_fields.append("employee_email = :employee_email")
                values["employee_email"] = employee_email
                
            if employee_phone is not None:
                update_fields.append("employee_phone = :employee_phone")
                values["employee_phone"] = employee_phone
                
            if employee_password is not None:
                update_fields.append("employee_password = :employee_password")
                values["employee_password"] = employee_password
            
            if isManager is False or isManager is True:
                update_fields.append("isManager = :isManager")
                values["isManager"] = True if isManager else False
                
            if not update_fields:
                return False, "No fields to update"
            
            connection.execute(
                text(f"UPDATE employee SET {', '.join(update_fields)} WHERE employee_id = :employee_id"),
                values
            )
            connection.commit()
            return True, "Employee updated successfully"
    except Exception as e:
        return False, f"Error updating employee: {str(e)}"
    
def get_employee(engine, employee_email=None, employee_id=None, employee_phone=None):
    try:
        with engine.connect() as connection:
            result = connection.execute(
                text("SELECT * FROM employee where employee_email = :employee_email OR employee_id = :employee_id OR employee_phone = :employee_phone"),
                {"employee_email": employee_email,
                "employee_id": employee_id,
                "employee_phone": employee_phone}
            )
            employee = result.fetchone() 
            
            if employee:
                return True, dict(employee.mapping)
            else: 
                return False, "Employee not found"
    except Exception as e:
        return False, f"Error retrieving employee: {str(e)}"

def delete_employee(engine, employee_id):
    try:
        with engine.connect() as connection:
            connection.execute(text("DELETE FROM employee WHERE employee_id = :employee_id"), 
                            {"employee_id": employee_id})
            connection.commit()
            return True, "Employee deleted successfully"
    except Exception as e:
        return False, f"Error deleting employee: {str(e)}"
    
def create_loan_application(engine, customer_id, loan_amnt, dti, fico_range_low, annual_inc, revol_util,
                            pub_rec_bankruptcies, tax_liens, total_il_high_credit_limit,
                            term, emp_length, home_ownership, purpose, verification_status):
    try:
        with engine.connect() as connection:
            result = connection.execute(text("""
                INSERT INTO loan_application (customer_id, loan_amnt, dti, fico_range_low, annual_inc, revol_util,
                                            pub_rec_bankruptcies, tax_liens, total_il_high_credit_limit,
                                            term, emp_length, home_ownership, purpose, verification_status)
                VALUES (:customer_id, :loan_amnt, :dti, :fico_range_low, :annual_inc, :revol_util,
                        :pub_rec_bankruptcies, :tax_liens, :total_il_high_credit_limit,
                        :term, :emp_length, :home_ownership, :purpose, :verification_status)
                RETURNING application_id;
            """), {
                'customer_id': customer_id,
                'loan_amnt': loan_amnt,
                'dti': dti,
                'fico_range_low': fico_range_low,
                'annual_inc': annual_inc,
                'revol_util': revol_util,
                'pub_rec_bankruptcies': pub_rec_bankruptcies,
                'tax_liens': tax_liens,
                'total_il_high_credit_limit': total_il_high_credit_limit,
                'term': term,
                'emp_length': emp_length,
                'home_ownership': home_ownership,
                'purpose': purpose,                    'verification_status': verification_status
            })
                
            connection.commit()
            return True, "Loan application created successfully"
    except Exception as e:
        return False, f"Error creating loan application: {str(e)}" 
        
def get_loan_application(engine, application_id):
    try:
        with engine.connect() as connection:
            result = connection.execute(
                text("SELECT * FROM loan_application where application_id = :application_id"),
                {"application_id": application_id}
            )
            application = result.fetchone() 
            
            if application:
                return True, dict(application.mapping)
            else: 
                return False, "Loan application not found"
    except Exception as e:
        return False, f"Error retrieving loan application: {str(e)}"

def delete_loan_application(engine, application_id):
    try:
        with engine.connect() as connection:
            connection.execute(text("DELETE FROM loan_application WHERE application_id = :application_id"), 
                            {"application_id": application_id})
            connection.commit()
            return True, "Loan application deleted successfully"
    except Exception as e:
        return False, f"Error deleting loan application: {str(e)}"
    
def update_loan_application(engine, application_id, loan_amnt=None, dti=None, fico_range_low=None, annual_inc=None, revol_util=None,
                            pub_rec_bankruptcies=None, tax_liens=None, total_il_high_credit_limit=None,
                            term=None, emp_length=None, home_ownership=None, purpose=None, verification_status=None):
    try:
        with engine.connect() as connection:
            update_fields = []
            values = {"application_id": application_id}
            
            if loan_amnt is not None:
                update_fields.append("loan_amnt = :loan_amnt")
                values["loan_amnt"] = loan_amnt
                
            if dti is not None:
                update_fields.append("dti = :dti")
                values["dti"] = dti
                
            if fico_range_low is not None:
                update_fields.append("fico_range_low = :fico_range_low")
                values["fico_range_low"] = fico_range_low
                
            if annual_inc is not None:
                update_fields.append("annual_inc = :annual_inc")
                values["annual_inc"] = annual_inc
                
            if revol_util is not None:
                update_fields.append("revol_util = :revol_util")
                values["revol_util"] = revol_util
                
            if pub_rec_bankruptcies is not None:
                update_fields.append("pub_rec_bankruptcies = :pub_rec_bankruptcies")
                values["pub_rec_bankruptcies"] = pub_rec_bankruptcies
                
            if tax_liens is not None:
                update_fields.append("tax_liens = :tax_liens")
                values["tax_liens"] = tax_liens
                
            if total_il_high_credit_limit is not None:
                update_fields.append("total_il_high_credit_limit = :total_il_high_credit_limit")
                values["total_il_high_credit_limit"] = total_il_high_credit_limit
                
            if term is not None:
                update_fields.append("term = :term")
                values["term"] = term
                
            if emp_length is not None:
                update_fields.append("emp_length = :emp_length")
                values["emp_length"] = emp_length
                
            if home_ownership is not None:
                update_fields.append("home_ownership = :home_ownership")
                values["home_ownership"] = home_ownership
                
            if purpose is not None:
                update_fields.append("purpose = :purpose")
                values["purpose"] = purpose
                
            if verification_status is not None:
                update_fields.append("verification_status = :verification_status")
                values["verification_status"] = verification_status 
                
            if not update_fields:
                return False, "No fields to update"
            
            connection.execute(
                text(f"UPDATE loan_application SET {', '.join(update_fields)} WHERE application_id = :application_id"),
                values
            )   
            connection.commit()
            return True, "Loan application updated successfully"
    except Exception as e:
        return False, f"Error updating loan application: {str(e)}"
    
def approve_loan_application(engine, employee_id, application_id):
    
    try:
        
        with engine.connect() as connection:
            
            connection.execute(text("UPDATE application SET status = 'approved' WHERE application_id = :application_id"),
                            {'application_id': application_id})
            connection.execute(text("""
                INSERT INTO decision (application_id, employee_id, is_approved)
                VALUES (:application_id, :employee_id, :is_approved);
            """),
                {"application_id": application_id, "employee_id": employee_id, "is_approved": True})
            connection.commit()
            return True, "Loan application approved successfully"
        
    except Exception as e:
        return False, f"Error approving loan application: {str(e)}"
    
def deny_loan_application(engine, employee_id, application_id, model, input_df):
    
    try:
        reasoning = denied(model, input_df)
        with engine.connect() as connection:
            
            connection.execute(text("UPDATE application SET status = 'denied' WHERE application_id = :application_id"),
                            {'application_id': application_id})
            connection.execute(text("""
                INSERT INTO decision (application_id, employee_id, is_approved,reason)
                VALUES (:application_id, :employee_id, :is_approved, :reason);
            """),
                {"application_id": application_id, "employee_id": employee_id, "is_approved": False, "reason": reasoning})
            connection.commit()
            return True, "Loan application denied successfully"
        
    except Exception as e:
        return False, f"Error denying loan application: {str(e)}"  

    
