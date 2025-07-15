import streamlit as st
import pandas as pd
import numpy as np
from PIL import Image

# --- Page Configuration ---
st.set_page_config(page_title="DC Listing Predictor", page_icon="📈", layout="wide")

# --- Data Loading and Caching ---
@st.cache_data
def load_and_prepare_data(file_path):
    """
    This function loads the property data and engineers a reliable set of features.
    """
    # CORRECTED: Added the compression argument to handle the .zip file
    df = pd.read_csv(file_path, compression='zip', low_memory=False)
    
    # Remove government-owned properties
    government_owners = 'DISTRICT OF COLUMBIA|UNITED STATES'
    df = df[~df['OWNERNAME'].str.contains(government_owners, case=False, na=False)].copy()

    # --- Base Feature Engineering ---
    df['SALEDATE'] = pd.to_datetime(df['SALEDATE'], errors='coerce')
    df['DEEDDATE'] = pd.to_datetime(df['DEEDDATE'], errors='coerce')
    df['LastTransferDate'] = df['SALEDATE'].combine_first(df['DEEDDATE'])
    current_year = 2025
    df['YearsSinceLastSale'] = current_year - df['LastTransferDate'].dt.year
    
    df['ZipCode'] = df['PREMISEADD'].str.extract(r'(\d{5})(?:-\d{4})?').fillna('Unknown')
    
    def bucket_property_type(proptype):
        proptype_str = str(proptype).upper()
        if 'RESIDENTIAL' in proptype_str: return 'Residential'
        elif 'COMMERCIAL' in proptype_str: return 'Commercial'
        else: return 'Other'
    df['PropertyCategory'] = df['PROPTYPE'].apply(bucket_property_type).astype('category')

    def classify_owner(name):
        name_upper = str(name).upper()
        if 'LLC' in name_upper or 'L.L.C' in name_upper: return 'LLC'
        elif 'TRUST' in name_upper or 'TR' in name_upper: return 'Trust'
        elif 'INC' in name_upper or 'CORP' in name_upper: return 'Corporation'
        else: return 'Individual'
    df['OwnerEntityType'] = df['OWNERNAME'].apply(classify_owner).astype('category')
    
    # --- Scoring Features ---
    df['HasLien'] = np.where(df['TOTBALAMT'] > 0, True, False)
    df['AssessmentPctChange'] = ((df['NEWTOTAL'] - df['OLDTOTAL']) / df['OLDTOTAL']).replace([np.inf, -np.inf], 0).fillna(0)
    df['HighAssessmentChange'] = df['AssessmentPctChange'] > 0.25
    df['IsEntityOwned'] = df['OwnerEntityType'] != 'Individual'
    df['IsLongTermOwner'] = df['YearsSinceLastSale'] > 20
    df['IsOldBuilding'] = (current_year - df['AYB']) > 75

    return df

# --- Main App Logic ---
# Use the new, compressed data file
properties_df = load_and_prepare_data('dc_properties_cleaned.csv.zip')

# --- Scoring Logic ---
raw_score = (
    properties_df['HasLien'] * 3 +
    properties_df['IsLongTermOwner'] * 2 +
    properties_df['IsEntityOwned'] * 1 +
    properties_df['HighAssessmentChange'] * 1 +
    properties_df['IsOldBuilding'] * 1
)
min_raw_score, max_raw_score = raw_score.min(), raw_score.max()
properties_df['LeadScore'] = 1 + 9 * (raw_score - min_raw_score) / ((max_raw_score - min_raw_score) + 0.0001)

# --- Sidebar UI Elements ---
st.sidebar.header('🔎 Lead Filters')

all_zips = sorted(properties_df['ZipCode'].unique())
selected_zips = st.sidebar.multiselect('Zip Code', options=all_zips, default=all_zips)

category_order = ['Residential', 'Commercial', 'Other']
property_categories = st.sidebar.multiselect('Property Category', options=category_order, default=category_order)

filter_liens = st.sidebar.toggle('Only Show Properties with Liens')

# --- Filtering and Tier Assignment ---
final_list = properties_df[
    (properties_df['ZipCode'].isin(selected_zips)) &
    (properties_df['PropertyCategory'].isin(property_categories))
].copy()

if filter_liens:
    final_list = final_list[final_list['HasLien'] == True]

if not final_list.empty:
    high_thresh = final_list['LeadScore'].quantile(0.95)
    med_thresh = final_list['LeadScore'].quantile(0.80)
    def assign_tier(score):
        if score >= high_thresh: return 'High'
        elif score >= med_thresh: return 'Medium'
        else: return 'Low'
    final_list['ProspectTier'] = final_list['LeadScore'].apply(assign_tier)
    final_list.sort_values(by='LeadScore', ascending=False, inplace=True)

# --- Dynamic Results Slider ---
st.sidebar.divider()
if not final_list.empty:
    max_results = len(final_list)
    default_count = min(100, max_results)
    num_results = st.sidebar.slider('Number of Results to Display', min_value=1, max_value=max_results, value=default_count)
else:
    num_results = 0

# --- Page Layout & Display ---
st.title("📈 Real Estate Listing Predictor")
st.write("Use the filters on the left to generate a high-confidence list of properties likely to be listed for sale in the next 6 months.")

# --- Dashboard Metrics ---
st.divider()
if not final_list.empty:
    col1, col2, col3 = st.columns(3)
    col1.metric("Prospects Found", f"{len(final_list):,}")
    col2.metric("Median Assessed Value", f"${final_list['NEWTOTAL'].median():,.0f}")
    col3.metric("Avg. Years Owned", f"{final_list['YearsSinceLastSale'].mean():.1f}")
    
    tier_counts = final_list['ProspectTier'].value_counts()
    col4, col5, col6 = st.columns(3)
    col4.metric("High-Tier Prospects", f"{tier_counts.get('High', 0):,}")
    col5.metric("Medium-Tier Prospects", f"{tier_counts.get('Medium', 0):,}")
    col6.metric("Low-Tier Prospects", f"{tier_counts.get('Low', 0):,}")
else:
    st.info("No properties found matching your current filter criteria.")

st.divider()
st.header("Your Prospect List")

def format_years_owned(y):
    if pd.isna(y): return "No Record"
    return f"{y:.1f}"
final_list['YearsOwnedDisplay'] = final_list['YearsSinceLastSale'].apply(format_years_owned)

st.dataframe(
    final_list[['PREMISEADD', 'OWNERNAME', 'PropertyCategory', 'ZipCode', 'YearsOwnedDisplay', 'LeadScore', 'ProspectTier']].head(num_results),
    column_config={
        "PREMISEADD": "Property Address", "OWNERNAME": "Owner Name", "PropertyCategory": "Category",
        "ZipCode": "Zip Code", "YearsOwnedDisplay": "Years Since Last Transfer",
        "LeadScore": st.column_config.NumberColumn("Lead Score", format="%d"),
        "ProspectTier": "Tier"
    },
    hide_index=True, use_container_width=True
)

st.download_button(
   f"Download {len(final_list)} Prospects as CSV",
   final_list.to_csv(index=False).encode('utf-8'),
   "property_prospect_list.csv",
   "text/csv"
)