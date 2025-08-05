import pandas as pd
import numpy as np
from datetime import datetime
import json
import warnings
warnings.filterwarnings('ignore')

def main():
    print("Loading DC property data...")
    
    # Load the data - read everything as-is
    df = pd.read_csv('dc_property_data.csv')
    print(f"Loaded {len(df)} records from CSV")
    
    # Show first few records to debug
    print("\nFirst 3 records from CSV:")
    print("=" * 80)
    for i in range(min(3, len(df))):
        print(f"Record {i+1}:")
        for col in ['SSL', 'PREMISEADD', 'OWNERNAME', 'ASSESSMENT', 'TOTBALAMT']:
            if col in df.columns:
                value = df.iloc[i][col]
                print(f"  {col}: '{value}' (type: {type(value)})")
        print()
    
    # Process each record individually
    records = []
    
    for index, row in df.iterrows():
        # Helper function to safely get values
        def get_value(column_name, default=''):
            if column_name in df.columns:
                val = row[column_name]
                if pd.isna(val) or val == 'nan' or str(val).strip() == '':
                    return default
                return str(val).strip()
            return default
        
        def get_numeric_value(column_name, default=0):
            if column_name in df.columns:
                val = row[column_name]
                try:
                    if pd.isna(val):
                        return default
                    return float(val)
                except:
                    return default
            return default
        
        # Extract basic property info
        ssl = get_value('SSL')
        premise_add = get_value('PREMISEADD')
        owner_name = get_value('OWNERNAME')
        assessment = get_numeric_value('ASSESSMENT', 0)
        total_balance = get_numeric_value('TOTBALAMT', 0)
        
        # Skip only if ALL essential fields are empty
        if not ssl and not premise_add and not owner_name and assessment == 0:
            continue
        
        # Calculate years since sale
        years_since_sale = 25.0  # Default
        if 'SALEDATE' in df.columns:
            sale_date_str = get_value('SALEDATE')
            if sale_date_str:
                try:
                    # Try different date formats
                    for fmt in ['%m/%d/%Y', '%Y-%m-%d', '%m-%d-%Y', '%Y/%m/%d']:
                        try:
                            sale_date = datetime.strptime(sale_date_str, fmt)
                            years_since_sale = max(0, (datetime.now() - sale_date).days / 365.25)
                            break
                        except:
                            continue
                except:
                    years_since_sale = 25.0
        
        # Calculate debt to assessment ratio
        debt_ratio = 0
        if assessment > 0:
            debt_ratio = min(total_balance / assessment, 1.0)  # Cap at 100%
        
        # Determine ownership type
        owner_upper = owner_name.upper()
        corporate_owner = any(word in owner_upper for word in ['LLC', 'INC', 'CORP', 'COMPANY', 'PROPERTIES', 'HOLDINGS'])
        trust_ownership = any(word in owner_upper for word in ['TRUST', 'TRUSTEE', 'REVOCABLE', 'IRREVOCABLE'])
        estate_ownership = any(word in owner_upper for word in ['ESTATE', 'DECEASED', 'HEIRS'])
        
        # Calculate listing probability based on risk factors
        probability_factors = []
        
        # Debt ratio factor (0-0.4 points)
        if debt_ratio > 0.1:
            probability_factors.append(min(debt_ratio * 4, 0.4))
        
        # Years since sale factor (0-0.3 points)
        if years_since_sale > 10:
            probability_factors.append(min((years_since_sale - 10) / 20 * 0.3, 0.3))
        
        # High debt amount factor (0-0.2 points)
        if total_balance > 15000:
            probability_factors.append(0.2)
        elif total_balance > 5000:
            probability_factors.append(0.1)
        
        # Ownership complexity factor (0-0.2 points)
        if estate_ownership:
            probability_factors.append(0.2)
        elif trust_ownership:
            probability_factors.append(0.15)
        elif corporate_owner:
            probability_factors.append(0.1)
        
        # Base probability + factors
        base_prob = 0.2  # 20% base probability
        listing_probability = min(base_prob + sum(probability_factors), 0.95)
        listing_probability = max(listing_probability, 0.15)  # Minimum 15%
        
        # Determine risk category
        if listing_probability >= 0.8:
            risk_category = "Extremely High"
        elif listing_probability >= 0.6:
            risk_category = "Very High"
        elif listing_probability >= 0.4:
            risk_category = "High"
        elif listing_probability >= 0.2:
            risk_category = "Moderate"
        else:
            risk_category = "Low"
        
        # Calculate scores
        financial_distress_score = min(int(debt_ratio * 10 + (1 if total_balance > 10000 else 0)), 10)
        ownership_complexity_score = (
            (2 if corporate_owner else 0) +
            (3 if trust_ownership else 0) +
            (4 if estate_ownership else 0)
        )
        ownership_complexity_score = min(ownership_complexity_score, 5)
        
        assessment_shock_score = 1
        if assessment > 1000000:
            assessment_shock_score = 3
        elif assessment > 500000:
            assessment_shock_score = 2
        
        # Create the record
        record = {
            "SSL": ssl,
            "PREMISEADD": premise_add,
            "OWNERNAME": owner_name,
            "ADDRESS1": get_value('ADDRESS1'),
            "ADDRESS2": get_value('ADDRESS2'),
            "CITYSTZIP": get_value('CITYSTZIP'),
            "listing_probability": round(listing_probability, 3),
            "risk_category": risk_category,
            "ASSESSMENT": int(assessment),
            "TOTBALAMT": round(total_balance, 2),
            "PRMS_WARD": get_value('PRMS_WARD'),
            "PROPTYPE": get_value('PROPTYPE', 'Unknown'),
            "years_since_last_sale": round(years_since_sale, 1),
            "debt_to_assessment_ratio": round(debt_ratio, 4),
            "financial_distress_score": financial_distress_score,
            "ownership_complexity_score": ownership_complexity_score,
            "assessment_shock_score": assessment_shock_score,
            "corporate_owner": corporate_owner,
            "trust_ownership": trust_ownership,
            "estate_ownership": estate_ownership
        }
        
        records.append(record)
    
    # Sort by listing probability (highest first)
    records.sort(key=lambda x: x['listing_probability'], reverse=True)
    
    # Save to JSON
    with open('dc_property_predictions.json', 'w') as f:
        json.dump(records, f, indent=2)
    
    print(f"\nSUCCESS!")
    print(f"Processed {len(records)} property records")
    print(f"Saved to dc_property_predictions.json")
    
    # Show summary
    if records:
        print(f"\nSample of first record:")
        sample = records[0]
        for key, value in sample.items():
            print(f"  {key}: {value}")
        
        print(f"\nRisk Distribution:")
        risk_counts = {}
        for record in records:
            risk = record['risk_category']
            risk_counts[risk] = risk_counts.get(risk, 0) + 1
        
        for risk, count in risk_counts.items():
            print(f"  {risk}: {count}")

if __name__ == "__main__":
    main()
