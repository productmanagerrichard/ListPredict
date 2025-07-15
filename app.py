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
    df = pd.read_csv(file_path, low_memory=False)
    
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
    df['NeedsRemodel'] = (current_year - df['YR_RMDL']) > 20

    return df

# --- Scoring and Filtering Function ---
def get_prospect_list(df, zips, categories, show_liens):
    """
    Applies all filters and calculates tiers on the resulting list.
    """
    raw_score = (
        df['HasLien'] * 3 +
        df['IsLongTermOwner'] * 2 +
        df['IsEntityOwned'] * 1 +
        df['HighAssessmentChange'] * 1 +
        df['IsOldBuilding'] * 1 +
        df['NeedsRemodel'] * 1
    )
    df['LeadScore'] = 1 + 9 * (raw_score - raw_score.min()) / (raw_score.max() - raw_score.min() + 0.0001)

    filtered_list = df[(df['ZipCode'].isin(zips)) & (df['PropertyCategory'].isin(categories))].copy()
    if show_liens:
        filtered_list = filtered_list[filtered_list['HasLien'] == True]
    
    if not filtered_list.empty:
        high_thresh = filtered_list['LeadScore'].quantile(0.95)
        med_thresh = filtered_list['LeadScore'].quantile(0.80)
        def assign_tier(score):
            if score >= high_thresh: return 'High'
            elif score >= med_thresh: return 'Medium'
            else: return 'Low'
        filtered_list['ProspectTier'] = filtered_list['LeadScore'].apply(assign_tier)

    return filtered_list.sort_values(by='LeadScore', ascending=False)

# --- Dashboard Function ---
def create_dashboard(filtered_df):
    """
    Displays the metrics dashboard based on the full filtered list.
    """
    st.divider()
    if not filtered_df.empty:
        col1, col2, col3 = st.columns(3)
        col1.metric("Prospects Found", f"{len(filtered_df):,}")
        col2.metric("Median Assessed Value", f"${filtered_df['NEWTOTAL'].median():,.0f}")
        col3.metric("Avg. Years Owned", f"{filtered_df['YearsSinceLastSale'].mean():.1f}")
    else:
        st.info("No properties found matching your current filter criteria.")
    st.divider()

# --- Main App Execution ---
st.title("📈 Real Estate Listing Predictor")
st.write("Use the filters on the left to generate a high-confidence list of properties likely to be listed for sale in the next 6 months.")

# UPDATED: Use the new, compressed data file
properties_df = load_and_prepare_data('dc_properties_cleaned.csv.zip')

# --- Sidebar UI Elements ---
st.sidebar.header('🔎 Lead Filters')
all_zips = sorted(properties_df['ZipCode'].unique())
selected_zips = st.sidebar.multiselect('Zip Code', options=all_zips, default=all_zips)
category_order = ['Residential', 'Commercial', 'Other']
property_categories = st.sidebar.multiselect('Property Category', options=category_order, default=category_order)
st.sidebar.divider()
filter_liens = st.sidebar.toggle('Only Show Properties with Liens')

# --- Get the filtered list and create the dashboard ---
final_list = get_prospect_list(properties_df, selected_zips, property_categories, filter_liens)
create_dashboard(final_list)

# --- Create a new list containing only High-Tier prospects for display ---
high_tier_list = final_list[final_list['ProspectTier'] == 'High']

# --- Dynamic Results Slider ---
st.sidebar.divider()
if not high_tier_list.empty:
    num_results = st.sidebar.slider(
        'Number of High-Tier Results to Display', 
        min_value=1, max_value=len(high_tier_list), 
        value=min(100, len(high_tier_list))
    )
else:
    num_results = 0

# --- Display Results Table ---
st.header("High-Tier Prospect List")
if not high_tier_list.empty:
    display_list = high_tier_list.head(num_results)
    def format_years_owned(y):
        if pd.isna(y): return "No Record"
        return f"{y:.1f}"
    display_list['YearsOwnedDisplay'] = display_list['YearsSinceLastSale'].apply(format_years_owned)
    st.dataframe(
        display_list[['PREMISEADD', 'OWNERNAME', 'PropertyCategory', 'ZipCode', 'YearsOwnedDisplay', 'LeadScore', 'ProspectTier']],
        column_config={
            "PREMISEADD": "Property Address", "OWNERNAME": "Owner Name", "PropertyCategory": "Category",
            "ZipCode": "Zip Code", "YearsOwnedDisplay": "Years Since Last Transfer",
            "LeadScore": st.column_config.NumberColumn("Lead Score", format="%d"),
            "ProspectTier": "Tier"
        },
        hide_index=True, use_container_width=True
    )
else:
    st.warning("No high-tier prospects found for the selected filters.")