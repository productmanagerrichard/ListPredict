import pandas as pd
import numpy as np
from datetime import datetime, date
import json
import warnings
warnings.filterwarnings('ignore')

def get_seasonal_multiplier():
    """Calculate seasonal listing multiplier based on current month"""
    current_month = datetime.now().month
    
    # DC market seasonality based on research
    seasonal_factors = {
        1: 0.75,   # January - Low activity
        2: 0.80,   # February - Building up
        3: 1.15,   # March - Spring surge begins
        4: 1.25,   # April - Peak spring
        5: 1.30,   # May - Peak spring
        6: 1.20,   # June - High summer
        7: 1.10,   # July - Summer activity
        8: 1.05,   # August - Late summer
        9: 1.15,   # September - Fall bounce
        10: 1.00,  # October - Moderate
        11: 0.85,  # November - Declining
        12: 0.70   # December - Holiday lull
    }
    
    return seasonal_factors.get(current_month, 1.0)

def get_ward_risk_multiplier(ward):
    """Ward-specific risk multipliers based on market dynamics"""
    # Based on DC market patterns and gentrification trends
    ward_multipliers = {
        '1': 1.10,   # Ward 1 - Strong market, corporate ownership
        '2': 0.95,   # Ward 2 - Stable, high-value area
        '3': 0.90,   # Ward 3 - Very stable, affluent
        '4': 1.15,   # Ward 4 - Transitioning, higher risk
        '5': 1.20,   # Ward 5 - Higher distress potential
        '6': 1.05,   # Ward 6 - Mixed, some gentrification
        '7': 1.25,   # Ward 7 - Higher financial distress
        '8': 1.30,   # Ward 8 - Highest risk factors
        '': 1.00     # Unknown ward
    }
    
    ward_str = str(ward).strip()
    return ward_multipliers.get(ward_str, 1.00)

def get_property_type_multiplier(prop_type):
    """Property type specific risk factors"""
    prop_type_upper = str(prop_type).upper()
    
    # Multi-family and commercial have different pressures
    if any(term in prop_type_upper for term in ['MULTI', 'APARTMENT', 'CONDO']):
        return 1.15  # Higher turnover, investment properties
    elif any(term in prop_type_upper for term in ['COMMERCIAL', 'OFFICE', 'RETAIL']):
        return 1.25  # Commercial distress post-COVID
    elif any(term in prop_type_upper for term in ['SINGLE', 'RESIDENTIAL']):
        return 1.00  # Baseline for single family
    else:
        return 1.05  # Unknown types get slight premium

def calculate_assessment_shock_factor(assessment, years_since_sale):
    """Advanced assessment shock calculation"""
    base_factor = 0
    
    # High assessment relative to potential purchase price
    if assessment > 1500000:
        base_factor = 0.25
    elif assessment > 1000000:
        base_factor = 0.20
    elif assessment > 750000:
        base_factor = 0.15
    elif assessment > 500000:
        base_factor = 0.10
    elif assessment > 250000:
        base_factor = 0.05
    
    # Amplify if property was purchased long ago (likely lower basis)
    if years_since_sale > 20:
        base_factor *= 1.4
    elif years_since_sale > 15:
        base_factor *= 1.2
    elif years_since_sale > 10:
        base_factor *= 1.1
    
    return min(base_factor, 0.30)  # Cap at 30%

def calculate_financial_pressure_score(assessment, debt_amount, debt_ratio):
    """Comprehensive financial pressure scoring"""
    pressure_points = 0
    
    # Debt ratio pressure (0-4 points)
    if debt_ratio > 0.50:
        pressure_points += 4
    elif debt_ratio > 0.30:
        pressure_points += 3
    elif debt_ratio > 0.15:
        pressure_points += 2
    elif debt_ratio > 0.05:
        pressure_points += 1
    
    # Absolute debt pressure (0-3 points)
    if debt_amount > 50000:
        pressure_points += 3
    elif debt_amount > 25000:
        pressure_points += 2
    elif debt_amount > 10000:
        pressure_points += 1
    
    # High-value property with debt (additional risk)
    if assessment > 800000 and debt_amount > 15000:
        pressure_points += 1
    
    return min(pressure_points, 7)  # Cap at 7 points

def calculate_ownership_complexity_factor(owner_name):
    """Enhanced ownership complexity analysis"""
    owner_upper = str(owner_name).upper()
    complexity_score = 0
    factors = []
    
    # Estate/inheritance situations (highest risk)
    estate_indicators = ['ESTATE', 'DECEASED', 'HEIRS', 'HEIR', 'DECD', 'ET AL']
    if any(indicator in owner_upper for indicator in estate_indicators):
        complexity_score += 0.25
        factors.append('estate')
    
    # Trust arrangements (high complexity)
    trust_indicators = ['TRUST', 'TRUSTEE', 'REVOCABLE', 'IRREVOCABLE', 'TR ', ' TR', 'TTEE']
    if any(indicator in owner_upper for indicator in trust_indicators):
        complexity_score += 0.20
        factors.append('trust')
    
    # Corporate/LLC ownership (moderate risk)
    corporate_indicators = ['LLC', 'INC', 'CORP', 'COMPANY', 'CO ', 'LTD', 'LIMITED', 'PROPERTIES', 'HOLDINGS', 'INVESTMENTS', 'VENTURES', 'GROUP', 'PARTNERS']
    if any(indicator in owner_upper for indicator in corporate_indicators):
        complexity_score += 0.15
        factors.append('corporate')
    
    # Multiple owners (additional complexity)
    multi_owner_indicators = ['&', ' AND ', ' + ', 'ET UX', 'ET VIR', 'ETAL', 'ET AL']
    if any(indicator in owner_upper for indicator in multi_owner_indicators):
        complexity_score += 0.10
        factors.append('multiple_owners')
    
    # Partnership indicators
    partnership_indicators = ['PARTNERSHIP', 'PARTNERS', 'LP ', ' LP', 'LLP']
    if any(indicator in owner_upper for indicator in partnership_indicators):
        complexity_score += 0.18
        factors.append('partnership')
    
    return min(complexity_score, 0.35), factors  # Cap at 35%

def calculate_assessment_shock_factor_advanced(old_total, new_total, assessment, years_since_sale):
    """Advanced assessment shock using historical assessment data"""
    shock_factor = 0
    
    # Use actual assessment changes if available
    if old_total and new_total and old_total > 0:
        assessment_increase_ratio = (new_total - old_total) / old_total
        if assessment_increase_ratio > 0.30:  # 30%+ increase
            shock_factor += 0.25
        elif assessment_increase_ratio > 0.20:  # 20%+ increase
            shock_factor += 0.20
        elif assessment_increase_ratio > 0.10:  # 10%+ increase
            shock_factor += 0.15
        elif assessment_increase_ratio > 0.05:  # 5%+ increase
            shock_factor += 0.10
    else:
        # Fallback to original method
        if assessment > 1500000:
            shock_factor = 0.25
        elif assessment > 1000000:
            shock_factor = 0.20
        elif assessment > 750000:
            shock_factor = 0.15
        elif assessment > 500000:
            shock_factor = 0.10
        elif assessment > 250000:
            shock_factor = 0.05
    
    # Amplify if property was purchased long ago
    if years_since_sale > 20:
        shock_factor *= 1.4
    elif years_since_sale > 15:
        shock_factor *= 1.2
    elif years_since_sale > 10:
        shock_factor *= 1.1
    
    return min(shock_factor, 0.35)  # Increased cap

def calculate_tax_sale_risk_factor(row):
    """Calculate risk based on tax sale flags in historical data"""
    risk_factor = 0
    tax_sale_fields = ['CY1TXSALE', 'CY2TXSALE', 'PY1TXSALE', 'PY2TXSALE', 'PY3TXSALE']
    
    tax_sale_count = 0
    for field in tax_sale_fields:
        if field in row.index:
            value = str(row[field]).upper()
            if value in ['Y', 'YES', '1', 'TRUE']:
                tax_sale_count += 1
    
    # Properties that have been in tax sale are high risk
    if tax_sale_count >= 3:
        risk_factor = 0.30  # Very high risk
    elif tax_sale_count >= 2:
        risk_factor = 0.25
    elif tax_sale_count >= 1:
        risk_factor = 0.20
    
    return min(risk_factor, 0.30)

def calculate_payment_pattern_risk(last_payment_date, total_balance):
    """Calculate risk based on payment patterns"""
    risk_factor = 0
    
    if last_payment_date and str(last_payment_date) != 'nan':
        try:
            # Parse last payment date
            for fmt in ['%m/%d/%Y', '%Y-%m-%d', '%m-%d-%Y', '%Y/%m/%d']:
                try:
                    last_payment = datetime.strptime(str(last_payment_date), fmt)
                    days_since_payment = (datetime.now() - last_payment).days
                    
                    # Risk increases with time since last payment
                    if days_since_payment > 730:  # 2+ years
                        risk_factor += 0.25
                    elif days_since_payment > 365:  # 1+ year
                        risk_factor += 0.20
                    elif days_since_payment > 180:  # 6+ months
                        risk_factor += 0.15
                    elif days_since_payment > 90:   # 3+ months
                        risk_factor += 0.10
                    break
                except:
                    continue
        except:
            pass
    else:
        # No payment history is concerning if there's a balance
        if total_balance > 5000:
            risk_factor += 0.15
        elif total_balance > 1000:
            risk_factor += 0.10
    
    return min(risk_factor, 0.25)

def calculate_homestead_protection_factor(homestead_code):
    """Calculate protection factor based on homestead status"""
    protection_factor = 0
    
    homestead_str = str(homestead_code).strip()
    if homestead_str in ['1', 'HS']:
        protection_factor = -0.10  # Homestead reduces listing probability
    elif homestead_str in ['2', 'SENIOR']:
        protection_factor = -0.15  # Senior homestead provides more protection
    
    return protection_factor

def calculate_vacant_property_risk(vacant_land_use):
    """Calculate risk for vacant properties"""
    vacant_str = str(vacant_land_use).upper()
    if vacant_str == 'Y':
        return 0.20  # Vacant properties are higher risk for listing
    return 0

def calculate_mixed_use_complexity(mixed_use_flag, tax_class):
    """Calculate complexity risk for mixed-use properties"""
    complexity_factor = 0
    
    mixed_str = str(mixed_use_flag).upper()
    if mixed_str == 'Y':
        complexity_factor += 0.10  # Mixed use adds complexity
        
        # Higher tax classes (commercial) add more risk
        try:
            tax_class_num = float(tax_class) if tax_class else 1
            if tax_class_num >= 3:  # Vacant or blighted
                complexity_factor += 0.20
            elif tax_class_num >= 2:  # Commercial
                complexity_factor += 0.15
        except:
            pass
    
    return min(complexity_factor, 0.25)

def calculate_market_pressure_factor(assessment, years_since_sale, sale_price):
    """Enhanced market pressure with sale price data"""
    pressure = 0
    
    # Use actual sale price if available for better calculation
    if sale_price and sale_price > 0 and assessment > 0:
        appreciation_ratio = assessment / sale_price
        
        # High appreciation creates selling pressure
        if appreciation_ratio > 4.0:  # 300%+ appreciation
            pressure += 0.25
        elif appreciation_ratio > 3.0:  # 200%+ appreciation  
            pressure += 0.20
        elif appreciation_ratio > 2.0:  # 100%+ appreciation
            pressure += 0.15
        elif appreciation_ratio > 1.5:  # 50%+ appreciation
            pressure += 0.10
    else:
        # Fallback to original time-based method
        if years_since_sale > 25:
            if assessment > 1000000:
                pressure += 0.20
            elif assessment > 500000:
                pressure += 0.15
            elif assessment > 250000:
                pressure += 0.10
    
    return min(pressure, 0.30)  # Increased cap

def main():
    print("Loading DC property data for enhanced prediction model...")
    
    # Load the data
    df = pd.read_csv('dc_property_data.csv')
    print(f"Loaded {len(df)} records from CSV")
    
    # Get current seasonal multiplier
    seasonal_multiplier = get_seasonal_multiplier()
    current_month_name = datetime.now().strftime("%B")
    print(f"Current month: {current_month_name} (Seasonal multiplier: {seasonal_multiplier:.2f})")
    
    # Process each record
    records = []
    
    for index, row in df.iterrows():
        # Helper functions (same as before)
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
        ward = get_value('PRMS_WARD')
        prop_type = get_value('PROPTYPE', 'Unknown')
        
        # Skip if essential fields are empty
        if not ssl and not premise_add and not owner_name and assessment == 0:
            continue
        
        # Calculate years since sale and extract sale price
        years_since_sale = 25.0
        sale_price = get_numeric_value('SALEPRICE', 0)
        
        if 'SALEDATE' in df.columns:
            sale_date_str = get_value('SALEDATE')
            if sale_date_str:
                try:
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
            debt_ratio = min(total_balance / assessment, 1.0)
        
        # ENHANCED SCORING SYSTEM WITH NEW DATA POINTS
        
        # Get additional data fields
        old_total = get_numeric_value('OLDTOTAL', 0)
        new_total = get_numeric_value('NEWTOTAL', 0)
        homestead_code = get_value('HSTDCODE')
        vacant_land_use = get_value('VACLNDUSE')
        mixed_use_flag = get_value('MIXEDUSE')
        tax_class = get_value('CLASSTYPE')
        last_payment_date = get_value('LASTPAYDT')
        
        # 1. Financial Pressure Score (0-0.35) - increased weight
        financial_pressure_points = calculate_financial_pressure_score(assessment, total_balance, debt_ratio)
        financial_pressure_factor = min(financial_pressure_points / 7 * 0.35, 0.35)
        
        # 2. Ownership Complexity Factor (0-0.30) 
        ownership_complexity_factor, ownership_factors = calculate_ownership_complexity_factor(owner_name)
        
        # 3. Enhanced Assessment Shock Factor (0-0.30)
        assessment_shock_factor = calculate_assessment_shock_factor_advanced(
            old_total, new_total, assessment, years_since_sale
        )
        
        # 4. Enhanced Market Pressure Factor (0-0.30)
        market_pressure_factor = calculate_market_pressure_factor(assessment, years_since_sale, sale_price)
        
        # 5. NEW: Tax Sale History Risk (0-0.30)
        tax_sale_risk_factor = calculate_tax_sale_risk_factor(row)
        
        # 6. NEW: Payment Pattern Risk (0-0.25) 
        payment_pattern_risk = calculate_payment_pattern_risk(last_payment_date, total_balance)
        
        # 7. NEW: Homestead Protection (-0.15 to 0)
        homestead_protection = calculate_homestead_protection_factor(homestead_code)
        
        # 8. NEW: Vacant Property Risk (0-0.20)
        vacant_property_risk = calculate_vacant_property_risk(vacant_land_use)
        
        # 9. NEW: Mixed Use Complexity (0-0.25)
        mixed_use_complexity = calculate_mixed_use_complexity(mixed_use_flag, tax_class)
        
        # 5. Geographic Risk Multiplier
        ward_multiplier = get_ward_risk_multiplier(ward)
        
        # 6. Property Type Multiplier
        prop_type_multiplier = get_property_type_multiplier(prop_type)
        
        # COMPOSITE SCORING WITH ALL FACTORS
        base_probability = 0.18  # Reduced base to accommodate new factors
        
        # Add all positive risk factors
        probability_before_multipliers = (
            base_probability + 
            financial_pressure_factor +
            ownership_complexity_factor +
            assessment_shock_factor +
            market_pressure_factor +
            tax_sale_risk_factor +
            payment_pattern_risk +
            vacant_property_risk +
            mixed_use_complexity +
            homestead_protection  # This can be negative
        )
        
        # Apply multipliers
        probability_with_location = probability_before_multipliers * ward_multiplier
        probability_with_property_type = probability_with_location * prop_type_multiplier
        final_probability = probability_with_property_type * seasonal_multiplier
        
        # Bounds checking
        final_probability = max(min(final_probability, 0.95), 0.10)
        
        # Risk categorization (adjusted thresholds)
        if final_probability >= 0.75:
            risk_category = "Extremely High"
        elif final_probability >= 0.55:
            risk_category = "Very High"
        elif final_probability >= 0.35:
            risk_category = "High"
        elif final_probability >= 0.20:
            risk_category = "Moderate"
        else:
            risk_category = "Low"
        
        # Enhanced scoring metrics
        financial_distress_score = min(financial_pressure_points, 10)
        
        ownership_complexity_score = min(len(ownership_factors) * 2, 10)
        
        assessment_shock_score = min(int(assessment_shock_factor * 10), 10)
        
        # Determine ownership flags
        corporate_owner = 'corporate' in ownership_factors
        trust_ownership = 'trust' in ownership_factors
        estate_ownership = 'estate' in ownership_factors
        
        # Create enhanced record
        record = {
            "SSL": ssl,
            "PREMISEADD": premise_add,
            "OWNERNAME": owner_name,
            "ADDRESS1": get_value('ADDRESS1'),
            "ADDRESS2": get_value('ADDRESS2'),
            "CITYSTZIP": get_value('CITYSTZIP'),
            "listing_probability": round(final_probability, 3),
            "risk_category": risk_category,
            "ASSESSMENT": int(assessment),
            "TOTBALAMT": round(total_balance, 2),
            "PRMS_WARD": ward,
            "PROPTYPE": prop_type,
            "years_since_last_sale": round(years_since_sale, 1),
            "debt_to_assessment_ratio": round(debt_ratio, 4),
            "financial_distress_score": financial_distress_score,
            "ownership_complexity_score": ownership_complexity_score,
            "assessment_shock_score": assessment_shock_score,
            "corporate_owner": corporate_owner,
            "trust_ownership": trust_ownership,
            "estate_ownership": estate_ownership,
            # Enhanced fields
            "ward_risk_multiplier": round(ward_multiplier, 3),
            "property_type_multiplier": round(prop_type_multiplier, 3),
            "seasonal_multiplier": round(seasonal_multiplier, 3),
            "financial_pressure_factor": round(financial_pressure_factor, 3),
            "ownership_complexity_factor": round(ownership_complexity_factor, 3),
            "assessment_shock_factor": round(assessment_shock_factor, 3),
            "market_pressure_factor": round(market_pressure_factor, 3),
            "tax_sale_risk_factor": round(tax_sale_risk_factor, 3),
            "payment_pattern_risk": round(payment_pattern_risk, 3),
            "homestead_protection": round(homestead_protection, 3),
            "vacant_property_risk": round(vacant_property_risk, 3),
            "mixed_use_complexity": round(mixed_use_complexity, 3),
            "ownership_factors": ownership_factors,
            "prediction_confidence": "High" if final_probability > 0.6 or final_probability < 0.25 else "Medium",
            "sale_price": int(sale_price) if sale_price > 0 else None,
            "assessment_vs_sale_ratio": round(assessment / sale_price, 2) if sale_price > 0 else None,
            "homestead_status": homestead_code if homestead_code else None,
            "is_vacant": vacant_land_use == 'Y',
            "is_mixed_use": mixed_use_flag == 'Y',
            "tax_class": tax_class,
            "last_payment_date": last_payment_date if last_payment_date else None
        }
        
        records.append(record)
    
    # Sort by listing probability (highest first)
    records.sort(key=lambda x: x['listing_probability'], reverse=True)
    
    # Save to JSON
    with open('dc_property_predictions.json', 'w') as f:
        json.dump(records, f, indent=2)
    
    print(f"\nENHANCED MODEL SUCCESS!")
    print(f"Processed {len(records)} property records")
    print(f"Saved to dc_property_predictions.json")
    
    # Enhanced summary
    if records:
        print(f"\nModel Performance Summary:")
        print(f"Seasonal Factor: {current_month_name} ({seasonal_multiplier:.2f}x)")
        
        # Risk distribution
        risk_counts = {}
        confidence_counts = {}
        ward_averages = {}
        
        for record in records:
            risk = record['risk_category']
            risk_counts[risk] = risk_counts.get(risk, 0) + 1
            
            confidence = record['prediction_confidence']
            confidence_counts[confidence] = confidence_counts.get(confidence, 0) + 1
            
            ward = record['PRMS_WARD']
            if ward not in ward_averages:
                ward_averages[ward] = []
            ward_averages[ward].append(record['listing_probability'])
        
        print(f"\nRisk Distribution:")
        for risk, count in sorted(risk_counts.items()):
            percentage = count / len(records) * 100
            print(f"  {risk}: {count} ({percentage:.1f}%)")
        
        print(f"\nPrediction Confidence:")
        for confidence, count in confidence_counts.items():
            percentage = count / len(records) * 100
            print(f"  {confidence}: {count} ({percentage:.1f}%)")
        
        print(f"\nTop 5 Highest Risk Properties:")
        for i, record in enumerate(records[:5]):
            print(f"  {i+1}. {record['PREMISEADD']} - {record['listing_probability']:.1%} ({record['risk_category']})")
        
        print(f"\nWard Risk Averages:")
        for ward in sorted(ward_averages.keys()):
            if ward and ward_averages[ward]:
                avg_prob = sum(ward_averages[ward]) / len(ward_averages[ward])
                print(f"  Ward {ward}: {avg_prob:.1%} (n={len(ward_averages[ward])})")

if __name__ == "__main__":
    main()
