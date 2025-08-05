#!/usr/bin/env python3
"""
DC Property Listing Prediction Processor
Converts raw DC property tax data into JSON format for the ListPredict UI
"""

import pandas as pd
import numpy as np
import json
from datetime import datetime, timedelta
import re
import warnings
warnings.filterwarnings('ignore')

class DCPropertyPredictor:
    def __init__(self):
        self.current_date = datetime.now()
        
    def clean_currency_field(self, value):
        """Clean currency fields and convert to float"""
        if pd.isna(value) or value == '' or value == 0:
            return 0.0
        try:
            # Remove any non-numeric characters except decimal point and minus
            if isinstance(value, str):
                cleaned = re.sub(r'[^\d.-]', '', str(value))
                return float(cleaned) if cleaned else 0.0
            return float(value)
        except:
            return 0.0
    
    def calculate_years_since_sale(self, sale_date):
        """Calculate years since last sale"""
        if pd.isna(sale_date) or sale_date == '':
            return 25.0  # Default for properties with no sale data
        
        try:
            if isinstance(sale_date, str):
                # Parse date string (format: YYYY/MM/DD HH:MM:SS+00)
                date_part = sale_date.split(' ')[0]
                sale_datetime = datetime.strptime(date_part, '%Y/%m/%d')
            else:
                sale_datetime = pd.to_datetime(sale_date)
            
            years_diff = (self.current_date - sale_datetime).days / 365.25
            return max(0, years_diff)
        except:
            return 25.0
    
    def determine_ownership_type(self, owner_name):
        """Determine ownership complexity indicators"""
        if pd.isna(owner_name):
            return False, False, False
        
        owner_upper = str(owner_name).upper()
        
        # Corporate indicators
        corporate_indicators = ['LLC', 'INC', 'CORP', 'COMPANY', 'PROPERTIES', 'HOLDINGS', 'VENTURES', 'GROUP']
        corporate_owner = any(indicator in owner_upper for indicator in corporate_indicators)
        
        # Trust indicators
        trust_indicators = ['TRUST', 'TRUSTEE', 'REVOCABLE', 'IRREVOCABLE']
        trust_ownership = any(indicator in owner_upper for indicator in trust_indicators)
        
        # Estate indicators
        estate_indicators = ['ESTATE', 'DECEASED', 'HEIRS', 'SUCCESSION']
        estate_ownership = any(indicator in owner_upper for indicator in estate_indicators)
        
        return corporate_owner, trust_ownership, estate_ownership
    
    def calculate_financial_distress_score(self, row):
        """Calculate financial distress score (0-8 scale)"""
        score = 0
        
        assessment = self.clean_currency_field(row.get('ASSESSMENT', 0))
        total_balance = self.clean_currency_field(row.get('TOTBALAMT', 0))
        
        if assessment > 0:
            debt_ratio = total_balance / assessment
            
            # High debt-to-assessment ratio
            if debt_ratio > 0.15:
                score += 3
            elif debt_ratio > 0.10:
                score += 2
            elif debt_ratio > 0.05:
                score += 1
            
            # Multiple year balances
            prior_year_balances = 0
            for i in range(1, 11):  # PY1BAL through PY10BAL
                py_bal = self.clean_currency_field(row.get(f'PY{i}BAL', 0))
                if py_bal > 0:
                    prior_year_balances += 1
            
            if prior_year_balances >= 5:
                score += 2
            elif prior_year_balances >= 3:
                score += 1
            
            # High assessment (potential cash flow issues)
            if assessment > 2000000:
                score += 1
            
            # Recent penalties/interest
            current_penalty = self.clean_currency_field(row.get('CY1PEN', 0)) + self.clean_currency_field(row.get('CY2PEN', 0))
            current_interest = self.clean_currency_field(row.get('CY1INT', 0)) + self.clean_currency_field(row.get('CY2INT', 0))
            
            if current_penalty > 0 or current_interest > 0:
                score += 1
        
        return min(score, 8)
    
    def calculate_ownership_complexity_score(self, row):
        """Calculate ownership complexity score (0-5 scale)"""
        score = 0
        
        corporate, trust, estate = self.determine_ownership_type(row.get('OWNERNAME', ''))
        
        if estate:
            score += 3  # Estate ownership is most complex
        elif trust:
            score += 2  # Trust ownership is moderately complex
        elif corporate:
            score += 1  # Corporate ownership has some complexity
        
        # Different mailing address indicates absentee ownership
        premise_addr = str(row.get('PREMISEADD', '')).upper()
        mailing_addr = str(row.get('ADDRESS1', '')).upper()
        
        if premise_addr and mailing_addr and premise_addr not in mailing_addr:
            score += 1
        
        # Out of state/DC ownership
        city_state_zip = str(row.get('CITYSTZIP', '')).upper()
        if 'DC' not in city_state_zip and city_state_zip:
            score += 1
        
        return min(score, 5)
    
    def calculate_assessment_shock_score(self, row):
        """Calculate assessment shock score (0-4 scale)"""
        old_total = self.clean_currency_field(row.get('OLDTOTAL', 0))
        new_total = self.clean_currency_field(row.get('NEWTOTAL', 0))
        
        if old_total > 0 and new_total > old_total:
            increase_ratio = (new_total - old_total) / old_total
            
            if increase_ratio > 0.50:  # 50%+ increase
                return 4
            elif increase_ratio > 0.30:  # 30-50% increase
                return 3
            elif increase_ratio > 0.20:  # 20-30% increase
                return 2
            elif increase_ratio > 0.10:  # 10-20% increase
                return 1
        
        return 0
    
    def calculate_listing_probability(self, financial_score, ownership_score, assessment_score, years_since_sale, debt_ratio):
        """Calculate listing probability using weighted scoring"""
        
        # Base probability from financial distress (40% weight)
        financial_prob = min(financial_score / 8.0, 1.0) * 0.4
        
        # Ownership complexity probability (25% weight)
        ownership_prob = min(ownership_score / 5.0, 1.0) * 0.25
        
        # Assessment shock probability (15% weight)
        assessment_prob = min(assessment_score / 4.0, 1.0) * 0.15
        
        # Time since sale factor (20% weight)
        if years_since_sale > 20:
            time_prob = 0.20
        elif years_since_sale > 15:
            time_prob = 0.16
        elif years_since_sale > 10:
            time_prob = 0.12
        elif years_since_sale > 5:
            time_prob = 0.08
        elif years_since_sale < 2:  # Very recent sales less likely to list again
            time_prob = 0.02
        else:
            time_prob = 0.04
        
        base_probability = financial_prob + ownership_prob + assessment_prob + time_prob
        
        # Debt ratio boost
        if debt_ratio > 0.10:
            base_probability += 0.15
        elif debt_ratio > 0.05:
            base_probability += 0.10
        
        # Property type adjustments
        # (This could be enhanced with PROPTYPE field analysis)
        
        return min(max(base_probability, 0.05), 0.95)  # Keep between 5% and 95%
    
    def categorize_risk(self, probability):
        """Categorize risk level based on probability"""
        if probability >= 0.80:
            return "Extremely High"
        elif probability >= 0.60:
            return "Very High"
        elif probability >= 0.40:
            return "High"
        elif probability >= 0.20:
            return "Moderate"
        else:
            return "Low"
    
    def process_property_data(self, df):
        """Process the property dataframe and add prediction columns"""
        processed_data = []
        
        for _, row in df.iterrows():
            try:
                # Clean and calculate fields
                assessment = self.clean_currency_field(row.get('ASSESSMENT', 0))
                total_balance = self.clean_currency_field(row.get('TOTBALAMT', 0))
                debt_ratio = total_balance / assessment if assessment > 0 else 0
                years_since_sale = self.calculate_years_since_sale(row.get('SALEDATE'))
                
                # Calculate scores
                financial_score = self.calculate_financial_distress_score(row)
                ownership_score = self.calculate_ownership_complexity_score(row)
                assessment_score = self.calculate_assessment_shock_score(row)
                
                # Determine ownership types
                corporate, trust, estate = self.determine_ownership_type(row.get('OWNERNAME', ''))
                
                # Calculate listing probability
                listing_probability = self.calculate_listing_probability(
                    financial_score, ownership_score, assessment_score, 
                    years_since_sale, debt_ratio
                )
                
                # Format mailing address
                address_parts = [
                    str(row.get('ADDRESS1', '')).strip(),
                    str(row.get('ADDRESS2', '')).strip(),
                    str(row.get('CITYSTZIP', '')).strip()
                ]
                mailing_address_parts = [part for part in address_parts if part and part != 'nan']
                
                # Create property record matching UI format
                property_record = {
                    'SSL': str(row.get('SSL', '')),
                    'PREMISEADD': str(row.get('PREMISEADD', '')),
                    'OWNERNAME': str(row.get('OWNERNAME', '')),
                    'ADDRESS1': str(row.get('ADDRESS1', '')),
                    'ADDRESS2': str(row.get('ADDRESS2', '')),
                    'CITYSTZIP': str(row.get('CITYSTZIP', '')),
                    'listing_probability': round(listing_probability, 3),
                    'risk_category': self.categorize_risk(listing_probability),
                    'ASSESSMENT': int(assessment),
                    'TOTBALAMT': int(total_balance),
                    'PRMS_WARD': str(row.get('PRMS_WARD', '')),
                    'PROPTYPE': str(row.get('PROPTYPE', 'Unknown')),
                    'years_since_last_sale': round(years_since_sale, 1),
                    'debt_to_assessment_ratio': round(debt_ratio, 4),
                    'financial_distress_score': financial_score,
                    'ownership_complexity_score': ownership_score,
                    'assessment_shock_score': assessment_score,
                    'corporate_owner': corporate,
                    'trust_ownership': trust,
                    'estate_ownership': estate
                }
                
                processed_data.append(property_record)
                
            except Exception as e:
                print(f"Error processing row {row.get('SSL', 'unknown')}: {e}")
                continue
        
        return processed_data
    
    def save_to_json(self, processed_data, output_file='dc_property_predictions.json'):
        """Save processed data to JSON file"""
        # Sort by listing probability (highest first)
        sorted_data = sorted(processed_data, key=lambda x: x['listing_probability'], reverse=True)
        
        with open(output_file, 'w') as f:
            json.dump(sorted_data, f, indent=2)
        
        print(f"Saved {len(sorted_data)} property records to {output_file}")
        return output_file

def main():
    """Main processing function"""
    print("DC Property Listing Prediction Processor")
    print("=" * 50)
    
    # Initialize processor
    predictor = DCPropertyPredictor()
    
    # Load data
    try:
        # Try to read the CSV file
        df = pd.read_csv('dc_property_data.csv', sep='\t', low_memory=False)
        print(f"Loaded {len(df)} property records")
        
        # Process the data
        print("Processing property data...")
        processed_data = predictor.process_property_data(df)
        
        # Save to JSON
        output_file = predictor.save_to_json(processed_data)
        
        # Print summary statistics
        print("\nSummary Statistics:")
        print("-" * 30)
        
        high_risk = len([p for p in processed_data if p['listing_probability'] >= 0.6])
        avg_probability = sum(p['listing_probability'] for p in processed_data) / len(processed_data)
        avg_debt_ratio = sum(p['debt_to_assessment_ratio'] for p in processed_data) / len(processed_data)
        
        print(f"Total Properties: {len(processed_data):,}")
        print(f"High Opportunity (60%+): {high_risk:,}")
        print(f"Average Listing Probability: {avg_probability:.1%}")
        print(f"Average Debt Ratio: {avg_debt_ratio:.1%}")
        
        # Risk category breakdown
        risk_counts = {}
        for prop in processed_data:
            risk = prop['risk_category']
            risk_counts[risk] = risk_counts.get(risk, 0) + 1
        
        print("\nRisk Category Breakdown:")
        for risk, count in sorted(risk_counts.items()):
            print(f"  {risk}: {count:,}")
        
        print(f"\nOutput saved to: {output_file}")
        print("Ready to deploy to your GitHub/Vercel project!")
        
    except FileNotFoundError:
        print("Error: Could not find 'dc_property_data.csv'")
        print("Please make sure your CSV file is named 'dc_property_data.csv' and in the same directory.")
    except Exception as e:
        print(f"Error processing data: {e}")

if __name__ == "__main__":
    main()
