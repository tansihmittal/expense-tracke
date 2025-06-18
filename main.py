import streamlit as st
import imaplib
import email
import re
import requests
import json
import os
import base64
from datetime import datetime, timedelta
from typing import List, Dict, Optional
from google.auth.transport.requests import Request
from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import InstalledAppFlow
from googleapiclient.discovery import build
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
from collections import Counter
import os
from dotenv import load_dotenv
import dateutil.parser
import urllib.parse


# Load environment variables from .secret file
load_dotenv('.secret')

# Set page config
st.set_page_config(
    page_title="SBI Transaction Analyzer",
    page_icon="🏦",
    layout="wide",
    initial_sidebar_state="expanded"
)

# Initialize session state for authentication
if 'authenticated' not in st.session_state:
    st.session_state.authenticated = False
if 'user_email' not in st.session_state:
    st.session_state.user_email = None

class ConfigManager:
    """Manages configuration and credentials with proper error handling"""
    
    def __init__(self):
        self.config = self._load_config()
        self.validation_errors = []
    
    def _load_config(self) -> Dict[str, str]:
        """Load configuration from environment variables"""
        config = {
            'GMAIL_CLIENT_ID': os.getenv('GMAIL_CLIENT_ID'),
            'GMAIL_CLIENT_SECRET': os.getenv('GMAIL_CLIENT_SECRET'),
            'REPLICATE_API_TOKEN': os.getenv('REPLICATE_API_TOKEN'),
            'REDIRECT_URI': os.getenv('REDIRECT_URI', 'https://sbi-track.streamlit.app/')
        }
        return config
    
    def validate_config(self) -> bool:
        """Validate that all required configuration is present"""
        self.validation_errors = []
        
        required_fields = {
            'GMAIL_CLIENT_ID': 'Gmail OAuth Client ID',
            'GMAIL_CLIENT_SECRET': 'Gmail OAuth Client Secret',
            'REPLICATE_API_TOKEN': 'Replicate API Token'
        }
        
        for key, display_name in required_fields.items():
            if not self.config.get(key):
                self.validation_errors.append(f"Missing {display_name}")
        
        return len(self.validation_errors) == 0
    
    def get_config_value(self, key: str) -> Optional[str]:
        """Get configuration value by key"""
        return self.config.get(key)
    
    def get_validation_errors(self) -> List[str]:
        """Get list of validation errors"""
        return self.validation_errors
    
    def display_config_status(self):
        """Display configuration status in Streamlit sidebar only if there are issues"""
        
        # Only show configuration status if there are validation errors
        if not self.validate_config():
            st.sidebar.subheader("Configuration Status")
            
            config_items = [
                ("Gmail Client ID", self.config.get('GMAIL_CLIENT_ID')),
                ("Gmail Client Secret", self.config.get('GMAIL_CLIENT_SECRET')),
                ("Replicate API Token", self.config.get('REPLICATE_API_TOKEN'))
            ]
            
            for name, value in config_items:
                if value:
                    st.sidebar.success(f"✅ {name}")
                else:
                    st.sidebar.error(f"❌ {name}")
            
            st.sidebar.error("⚠️ Configuration incomplete")
            with st.sidebar.expander("Setup Instructions"):
                st.write("""
                Create a `.secret` file in your project root with:
                ```
                GMAIL_CLIENT_ID=your_client_id_here
                GMAIL_CLIENT_SECRET=your_client_secret_here
                REPLICATE_API_TOKEN=your_replicate_token_here
                REDIRECT_URI=https://your-app.streamlit.app/
                ```
                
                **For Google OAuth Setup:**
                1. Go to [Google Cloud Console](https://console.cloud.google.com/)
                2. Create a new project or select existing
                3. Enable Gmail API
                4. Create OAuth2 credentials
                5. Add your Streamlit app URL to authorized redirect URIs
                """)

class AITransactionCategorizer:
    """AI-powered class to categorize transactions using Replicate API"""
    
    def __init__(self, replicate_token: str):
        self.replicate_token = replicate_token
        self.categories = {
            # Banking & Finance
            'ATM Withdrawal': '#FF6B6B',
            'Bank Transfer': '#4ECDC4',
            'Online Purchase': '#45B7D1',
            'Food & Dining': '#96CEB4',
            'Transportation': '#FFEAA7',
            'Shopping': '#DDA0DD',
            'Entertainment': '#98D8C8',
            'Bills & Utilities': '#F7DC6F',
            'Healthcare': '#BB8FCE',
            'Education': '#85C1E9',
            'Travel': '#F8C471',
            'Subscription': '#82E0AA',
            'Investment': '#F1948A',
            'Insurance': '#AED6F1',
            'Charity': '#A9DFBF',
            'Other': '#D5D8DC'
        }       
    
    def categorize_transaction_with_ai(self, subject: str, body: str, amount: str) -> str:
        """
        Use AI to categorize transactions intelligently
        
        Args:
            subject: Email subject
            body: Email body
            amount: Transaction amount
            
        Returns:
            Category name
        """
        try:
            url = "https://api.replicate.com/v1/models/openai/gpt-4o-mini/predictions"
            
            headers = {
                "Authorization": f"Bearer {self.replicate_token}",
                "Content-Type": "application/json"
            }
            
            # Create a comprehensive prompt for AI categorization
            transaction_text = f"Subject: {subject}\nBody: {body}\nAmount: {amount}"
            
            categories_list = ", ".join([cat for cat in self.categories.keys() if cat != 'Other'])
            
            prompt = f"""
                You are a financial transaction categorization expert. Analyze the transaction below and assign it to exactly ONE category from this list:

                {categories_list}

                ## Transaction Analysis Guidelines:

                **Financial Services:**
                - ATM Withdrawal: Cash withdrawals, ATM fees
                - Bank Transfer: UPI, NEFT, RTGS, IMPS, fund transfers
                - Investment: Mutual funds, stocks, bonds, SIP
                - Insurance: Policy payments, premiums

                **Shopping & Commerce:**
                - Online Purchase: E-commerce, online shopping
                - Shopping: Retail stores, markets, general shopping
                
                **Daily Expenses:**
                - Food & Dining: Restaurants, food delivery, groceries
                - Transportation: Fuel, public transport, ride-sharing
                - Bills & Utilities: Electricity, water, phone, internet
                
                **Lifestyle:**
                - Entertainment: Movies, games, streaming services
                - Travel: Hotels, flights, vacation expenses
                - Healthcare: Medical bills, pharmacy, hospitals
                - Education: Fees, courses, books
                
                **Services:**
                - Subscription: Monthly/yearly service subscriptions
                - Charity: Donations, NGO contributions

                **Fallback:**
                - Other: Only if transaction doesn't clearly fit any specific category above

                ## Key Decision Rules:
                1. **Merchant/Vendor Name**: Primary indicator - match known brands to their logical category
                2. **Transaction Purpose**: If description includes purpose keywords, prioritize those
                3. **Amount Context**: Large amounts might indicate investments/transfers, small regular amounts suggest subscriptions
                4. **Specificity**: Choose the MOST SPECIFIC category that fits (e.g., "Food & Dining" over "Entertainment")

                Transaction: {transaction_text}

                Return only the category name. No explanation.
                """

            
            data = {
                "input": {
                    "prompt": prompt,
                    "system_prompt": "You are an expert financial transaction categorizer. Analyze bank transaction details and categorize them accurately based on merchant names, transaction descriptions, and context. Always return exactly one category name from the provided list."
                }
            }
            
            response = requests.post(url, headers=headers, json=data)
            
            if response.status_code == 201:
                prediction = response.json()
                prediction_id = prediction['id']
                category = self.poll_prediction(prediction_id)
                
                # Validate that the returned category is in our list
                if category and category.strip() in self.categories:
                    return category.strip()
                else:
                    # Fallback to basic pattern matching if AI returns invalid category
                    return self.fallback_categorization(subject, body, amount)
            else:
                return self.fallback_categorization(subject, body, amount)
                
        except Exception as e:
            st.warning(f"AI categorization failed, using fallback: {e}")
            return self.fallback_categorization(subject, body, amount)
    
    def poll_prediction(self, prediction_id: str, max_attempts: int = 30) -> Optional[str]:
        """Poll Replicate API for prediction completion"""
        import time
        
        url = f"https://api.replicate.com/v1/predictions/{prediction_id}"
        headers = {
            "Authorization": f"Bearer {self.replicate_token}"
        }
        
        for attempt in range(max_attempts):
            try:
                response = requests.get(url, headers=headers)
                
                if response.status_code == 200:
                    result = response.json()
                    
                    if result['status'] == 'succeeded':
                        output = result.get('output', [])
                        if output:
                            return ''.join(output).strip()
                        return None
                    elif result['status'] == 'failed':
                        return None
                    else:
                        time.sleep(2)
                        continue
                else:
                    return None
                    
            except Exception as e:
                return None
        
        return None
    
    def fallback_categorization(self, subject: str, body: str, amount: str) -> str:
        """Fallback categorization using simple keyword matching"""
        text = f"{subject} {body}".lower()
        
        # Simple keyword-based fallback
        fallback_rules = {
            # Banking & Finance
            'ATM Withdrawal': ['atm', 'withdrawal', 'cash', 'withdraw'],
            'Bank Transfer': ['transfer', 'upi', 'neft', 'rtgs', 'imps', 'bank transfer', 'fund transfer'],
            'Investment': ['mutual fund', 'sip', 'investment', 'equity', 'stock'],
            'Insurance': ['insurance', 'policy', 'premium', 'lic'],
            
            # Shopping & Commerce
            'Online Purchase': ['amazon', 'flipkart', 'myntra', 'ajio', 'online', 'e-commerce'],
            'Shopping': ['mall', 'store', 'retail', 'shopping', 'market'],
            
            # Daily Expenses
            'Food & Dining': ['restaurant', 'food', 'dining', 'zomato', 'swiggy', 'dominos', 'kfc', 'mcdonald'],
            'Transportation': ['fuel', 'petrol', 'diesel', 'uber', 'ola', 'metro', 'bus', 'taxi'],
            'Bills & Utilities': ['electricity', 'water', 'gas', 'mobile', 'internet', 'broadband', 'bill'],
            
            # Lifestyle
            'Entertainment': ['movie', 'cinema', 'netflix', 'spotify', 'game', 'entertainment'],
            'Travel': ['hotel', 'flight', 'travel', 'booking', 'makemytrip', 'goibibo'],
            'Healthcare': ['hospital', 'doctor', 'medical', 'pharmacy', 'medicine', 'health'],
            'Education': ['school', 'college', 'university', 'course', 'education', 'fees'],
            
            # Services
            'Subscription': ['subscription', 'monthly', 'annual', 'renewal'],
            'Charity': ['donation', 'charity', 'ngo', 'trust', 'foundation']
        }
        
        for category, keywords in fallback_rules.items():
            if any(keyword in text for keyword in keywords):
                return category
        
        return 'Other'
    
    def get_category_color(self, category: str) -> str:
        """Get color for a category"""
        return self.categories.get(category, '#D3D3D3')
    
    def get_all_categories(self) -> List[str]:
        """Get list of all available categories"""
        return list(self.categories.keys())

class SBIEmailExtractor:
    def __init__(self, config_manager: ConfigManager):
        """
        Initialize the email extractor with configuration manager
        
        Args:
            config_manager: ConfigManager instance with loaded credentials
        """
        self.config_manager = config_manager
        self.target_sender = "donotreply.sbiatm@alerts.sbi.co.in"
        self.scopes = ['https://www.googleapis.com/auth/gmail.readonly']
        self.service = None
        
        # Initialize categorizer if token is available
        replicate_token = config_manager.get_config_value('REPLICATE_API_TOKEN')
        if replicate_token:
            self.categorizer = AITransactionCategorizer(replicate_token)
        else:
            self.categorizer = None
    
    def get_authorization_url(self):
        """Generate OAuth authorization URL for Streamlit Cloud"""
        try:
            client_id = self.config_manager.get_config_value('GMAIL_CLIENT_ID')
            client_secret = self.config_manager.get_config_value('GMAIL_CLIENT_SECRET')
            redirect_uri = self.config_manager.get_config_value('REDIRECT_URI')
            
            if not client_id or not client_secret:
                return None
            
            # Create OAuth2 config
            client_config = {
                "web": {
                    "client_id": client_id,
                    "client_secret": client_secret,
                    "auth_uri": "https://accounts.google.com/o/oauth2/auth",
                    "token_uri": "https://oauth2.googleapis.com/token",
                    "auth_provider_x509_cert_url": "https://www.googleapis.com/oauth2/v1/certs",
                    "redirect_uris": [redirect_uri]
                }
            }
            
            flow = InstalledAppFlow.from_client_config(client_config, self.scopes)
            flow.redirect_uri = redirect_uri
            
            authorization_url, state = flow.authorization_url(
                access_type='offline',
                include_granted_scopes='true'
            )
            
            # Store flow in session state for later use
            st.session_state.oauth_flow = flow
            st.session_state.oauth_state = state
            
            return authorization_url
            
        except Exception as e:
            st.error(f"Error generating authorization URL: {e}")
            return None
    
    def handle_oauth_callback(self, authorization_code: str):
        """Handle OAuth callback and exchange code for tokens"""
        try:
            if 'oauth_flow' not in st.session_state:
                return False, None
            
            flow = st.session_state.oauth_flow
            
            # Exchange authorization code for credentials
            flow.fetch_token(code=authorization_code)
            creds = flow.credentials
            
            # Save credentials for future use
            with open('token.json', 'w') as token:
                token.write(creds.to_json())
            
            # Build the Gmail service
            self.service = build('gmail', 'v1', credentials=creds)
            
            # Get user email
            user_info = self.service.users().getProfile(userId='me').execute()
            user_email = user_info.get('emailAddress', 'Unknown')
            
            # Clear OAuth flow from session state
            del st.session_state.oauth_flow
            del st.session_state.oauth_state
            
            return True, user_email
            
        except Exception as e:
            st.error(f"OAuth callback failed: {e}")
            return False, None
    
    def authenticate_gmail(self):
        """Authenticate with Gmail using OAuth2 - Streamlit Cloud compatible"""
        try:
            client_id = self.config_manager.get_config_value('GMAIL_CLIENT_ID')
            client_secret = self.config_manager.get_config_value('GMAIL_CLIENT_SECRET')
            
            if not client_id or not client_secret:
                st.error("Gmail credentials not configured")
                return False, None
            
            creds = None
            
            # Check if token.json exists (saved credentials)
            if os.path.exists('token.json'):
                creds = Credentials.from_authorized_user_file('token.json', self.scopes)
            
            # If there are no (valid) credentials available, need to authenticate
            if not creds or not creds.valid:
                if creds and creds.expired and creds.refresh_token:
                    try:
                        creds.refresh(Request())
                        # Save refreshed credentials
                        with open('token.json', 'w') as token:
                            token.write(creds.to_json())
                    except Exception as e:
                        st.error(f"Token refresh failed: {e}")
                        creds = None
                
                if not creds:
                    # Need to get new credentials
                    return False, None
            
            # Build the Gmail service
            self.service = build('gmail', 'v1', credentials=creds)
            
            # Get user email from token
            user_info = self.service.users().getProfile(userId='me').execute()
            user_email = user_info.get('emailAddress', 'Unknown')
            
            return True, user_email
            
        except Exception as e:
            st.error(f"Authentication failed: {e}")
            return False, None
    
    def search_sbi_emails(self, max_results: int = 50) -> List[Dict]:
        """Search for emails from SBI ATM alerts using Gmail API"""
        try:
            query = f'from:{self.target_sender}'
            results = self.service.users().messages().list(
                userId='me', 
                q=query, 
                maxResults=max_results
            ).execute()
            
            messages = results.get('messages', [])
            return messages
            
        except Exception as e:
            st.error(f"Error searching emails: {e}")
            return []
    
    def get_email_content(self, message_id: str) -> Dict:
        """Get email content by message ID using Gmail API"""
        try:
            message = self.service.users().messages().get(
                userId='me', 
                id=message_id
            ).execute()
            
            headers = message['payload'].get('headers', [])
            subject = next((h['value'] for h in headers if h['name'] == 'Subject'), '')
            sender = next((h['value'] for h in headers if h['name'] == 'From'), '')
            date = next((h['value'] for h in headers if h['name'] == 'Date'), '')
            
            body = self.extract_message_body(message['payload'])
            
            return {
                'message_id': message_id,
                'subject': subject,
                'sender': sender,
                'date': date,
                'body': body,
                'full_text': f"Subject: {subject}\n\nBody: {body}"
            }
            
        except Exception as e:
            st.error(f"Error fetching email {message_id}: {e}")
            return None
    
    def extract_message_body(self, payload) -> str:
        """Extract body text from Gmail message payload"""
        body = ""
        html_body = ""
        
        def extract_from_part(part):
            nonlocal body, html_body
            if part['mimeType'] == 'text/plain':
                if 'data' in part['body']:
                    body = base64.urlsafe_b64decode(part['body']['data']).decode('utf-8')
            elif part['mimeType'] == 'text/html':
                if 'data' in part['body']:
                    html_body = base64.urlsafe_b64decode(part['body']['data']).decode('utf-8')
            elif 'parts' in part:
                for subpart in part['parts']:
                    extract_from_part(subpart)
        
        if 'parts' in payload:
            for part in payload['parts']:
                extract_from_part(part)
        else:
            extract_from_part(payload)
        
        if html_body and not body:
            from html import unescape
            body = re.sub(r'<[^>]+>', ' ', html_body)
            body = unescape(body)
            body = re.sub(r'\s+', ' ', body).strip()
        
        return body or html_body
    
    def extract_amount_with_ai(self, email_text: str) -> Optional[str]:
        """Use Replicate AI to extract amount from email text"""
        if not self.categorizer:
            return None
            
        try:
            replicate_token = self.config_manager.get_config_value('REPLICATE_API_TOKEN')
            url = "https://api.replicate.com/v1/models/openai/gpt-4o-mini/predictions"
            
            headers = {
                "Authorization": f"Bearer {replicate_token}",
                "Content-Type": "application/json"
            }
            
            prompt = f"""
            Extract the transaction amount from this SBI bank transaction alert email. 
            
            Look for patterns like:
            - "Amount (INR)149.00"
            - "Amount: 149.00"
            - "Rs. 149.00"
            - "₹ 149.00"
            - "Debited for Rs 149.00"
            - "Transaction Amount: INR 149.00"
            
            Return ONLY the numeric amount with decimal (e.g., "149.00").
            If multiple amounts are present, return the main transaction amount (not fees or balances).
            If no amount is found, return "NO_AMOUNT_FOUND".
            
            Email content:
            {email_text}
            """
            
            data = {
                "input": {
                    "prompt": prompt,
                    "system_prompt": "You are an expert at extracting financial amounts from SBI bank transaction alert emails. Look carefully for transaction amounts in various formats. Return only the numeric value with decimal places, ignoring any fees or balance amounts."
                }
            }
            
            response = requests.post(url, headers=headers, json=data)
            
            if response.status_code == 201:
                prediction = response.json()
                prediction_id = prediction['id']
                return self.poll_prediction(prediction_id)
            else:
                return None
                
        except Exception as e:
            st.error(f"Error with AI extraction: {e}")
            return None
    
    def poll_prediction(self, prediction_id: str, max_attempts: int = 30) -> Optional[str]:
        """Poll Replicate API for prediction completion"""
        import time
        
        replicate_token = self.config_manager.get_config_value('REPLICATE_API_TOKEN')
        url = f"https://api.replicate.com/v1/predictions/{prediction_id}"
        headers = {
            "Authorization": f"Bearer {replicate_token}"
        }
        
        for attempt in range(max_attempts):
            try:
                response = requests.get(url, headers=headers)
                
                if response.status_code == 200:
                    result = response.json()
                    
                    if result['status'] == 'succeeded':
                        output = result.get('output', [])
                        if output:
                            return ''.join(output).strip()
                        return None
                    elif result['status'] == 'failed':
                        return None
                    else:
                        time.sleep(2)
                        continue
                else:
                    return None
                    
            except Exception as e:
                return None
        
        return None
    
    def extract_amount_regex(self, email_text: str) -> List[str]:
        """Fallback method to extract amounts using regex"""
        patterns = [
            r'Amount\s*\(INR\)\s*(\d+(?:,\d+)*(?:\.\d{2})?)',
            r'Amount\s*:\s*(\d+(?:,\d+)*(?:\.\d{2})?)',
            r'Rs\.?\s*(\d+(?:,\d+)*(?:\.\d{2})?)',
            r'INR\s*(\d+(?:,\d+)*(?:\.\d{2})?)',
            r'₹\s*(\d+(?:,\d+)*(?:\.\d{2})?)',
            r'Debited for Rs\.?\s*(\d+(?:,\d+)*(?:\.\d{2})?)',
            r'Transaction Amount:\s*INR\s*(\d+(?:,\d+)*(?:\.\d{2})?)',
            r'(\d{1,6}\.\d{2})',
        ]
        
        amounts = []
        clean_text = re.sub(r'\s+', ' ', email_text)
        
        for pattern in patterns:
            matches = re.findall(pattern, clean_text, re.IGNORECASE)
            amounts.extend(matches)
        
        # Remove duplicates and filter reasonable amounts
        seen = set()
        filtered_amounts = []
        for amount in amounts:
            if amount not in seen:
                seen.add(amount)
                try:
                    amt_float = float(amount.replace(',', ''))
                    if 1 <= amt_float <= 1000000:
                        filtered_amounts.append(amount)
                except ValueError:
                    continue
        
        return filtered_amounts
    
    def process_emails(self, max_emails: int = 50, progress_callback=None) -> List[Dict]:
        """Main method to process all SBI emails and extract amounts with AI categorization"""
        results = []
        
        try:
            messages = self.search_sbi_emails(max_emails)
            
            for i, message in enumerate(messages):
                if progress_callback:
                    progress_callback(i + 1, len(messages))
                
                message_id = message['id']
                email_data = self.get_email_content(message_id)
                if not email_data:
                    continue
                
                # Extract amount using AI
                ai_amount = self.extract_amount_with_ai(email_data['full_text'])
                
                # Fallback to regex
                regex_amounts = self.extract_amount_regex(email_data['full_text'])
                
                # Use AI amount if available, otherwise use first regex amount
                final_amount = ai_amount if ai_amount and ai_amount != 'NO_AMOUNT_FOUND' else (regex_amounts[0] if regex_amounts else None)
                
                # Categorize transaction using AI
                if self.categorizer:
                    category = self.categorizer.categorize_transaction_with_ai(
                        email_data['subject'], 
                        email_data['body'], 
                        final_amount or ''
                    )
                else:
                    category = 'Other'
                
                result = {
                    'message_id': message_id,
                    'date': email_data['date'],
                    'subject': email_data['subject'],
                    'sender': email_data['sender'],
                    'amount': final_amount,
                    'category': category,
                    'ai_extracted_amount': ai_amount,
                    'regex_extracted_amounts': regex_amounts,
                    'email_body_preview': email_data['body'][:200] + "..." if len(email_data['body']) > 200 else email_data['body'],
                    'full_email_text': email_data['full_text']
                }
                
                results.append(result)
        
        except Exception as e:
            st.error(f"Error processing emails: {e}")
        
        return results

def apply_date_filter(df: pd.DataFrame) -> pd.DataFrame:
    """Apply date filter from session state if enabled"""
    if st.session_state.get('date_filter_enabled', False):
        start_date = st.session_state.get('date_filter_start')
        end_date = st.session_state.get('date_filter_end')
        
        if start_date and end_date:
            # Ensure we have parsed dates
            if 'date_parsed' in df.columns:
                mask = (df['date_parsed'].dt.date >= start_date) & (df['date_parsed'].dt.date <= end_date)
                return df[mask]
    
    return df

def create_visualizations(df, categorizer):
    """Create various visualizations for the transaction data"""
    
    # Apply global date filter
    df_filtered = apply_date_filter(df)
    
    if len(df_filtered) == 0:
        st.warning("No transactions found in the selected date range.")
        return None, None, None, None
    
    # Category Distribution Pie Chart by Amount
    category_amounts = df_filtered.groupby('category')['amount_numeric'].sum().reset_index()
    fig_pie = px.pie(
        category_amounts,
        names='category', 
        values='amount_numeric',
        title='Transaction Distribution by Category (by Amount)',
        color='category',
        color_discrete_map={cat: categorizer.get_category_color(cat) for cat in category_amounts['category']}
    )
    fig_pie.update_traces(textposition='inside', textinfo='percent+label')
    
    # Amount by Category Bar Chart
    fig_bar = px.bar(
        category_amounts, 
        x='category', 
        y='amount_numeric',
        title='Total Amount by Category',
        color='category',
        color_discrete_map={cat: categorizer.get_category_color(cat) for cat in category_amounts['category']}
    )
    fig_bar.update_layout(xaxis_tickangle=-45)
    
    # Timeline of transactions
    df_sorted = df_filtered.sort_values('date_parsed')
    fig_timeline = px.line(
        df_sorted, 
        x='date_parsed', 
        y='amount_numeric',
        color='category',
        title='Transaction Timeline',
        markers=True,
        color_discrete_map={cat: categorizer.get_category_color(cat) for cat in df_sorted['category'].unique()}
    )
    
    # Monthly spending trends
    df_sorted['month'] = df_sorted['date_parsed'].dt.to_period('M')
    monthly_spending = df_sorted.groupby(['month', 'category'])['amount_numeric'].sum().reset_index()
    monthly_spending['month'] = monthly_spending['month'].astype(str)
    # Monthly spending stacked bar chart
    fig_monthly = px.bar(
        monthly_spending,
        x='month',
        y='amount_numeric',
        color='category',
        title='Monthly Spending by Category',
        color_discrete_map={cat: categorizer.get_category_color(cat) for cat in monthly_spending['category'].unique()}
    )
    fig_monthly.update_layout(xaxis_tickangle=-45)
    
    return fig_pie, fig_bar, fig_timeline, fig_monthly

def display_transaction_table(df):
    """Display transaction data in a formatted table"""
    
    # Apply global date filter
    df_filtered = apply_date_filter(df)
    
    if len(df_filtered) == 0:
        st.warning("No transactions found in the selected date range.")
        return
    
    # Create display dataframe
    display_df = df_filtered[[
        'date_parsed', 'subject', 'category', 'amount', 'email_body_preview'
    ]].copy()
    
    display_df = display_df.rename(columns={
        'date_parsed': 'Date',
        'subject': 'Description',
        'category': 'Category',
        'amount': 'Amount (₹)',
        'email_body_preview': 'Details'
    })
    
    # Sort by date descending
    display_df = display_df.sort_values('Date', ascending=False)
    
    st.dataframe(
        display_df,
        use_container_width=True,
        hide_index=True
    )

def create_summary_metrics(df):
    """Create summary metrics cards"""
    
    # Apply global date filter
    df_filtered = apply_date_filter(df)
    
    if len(df_filtered) == 0:
        return
    
    # Calculate metrics
    total_transactions = len(df_filtered)
    total_amount = df_filtered['amount_numeric'].sum()
    avg_transaction = df_filtered['amount_numeric'].mean()
    date_range = f"{df_filtered['date_parsed'].min().strftime('%Y-%m-%d')} to {df_filtered['date_parsed'].max().strftime('%Y-%m-%d')}"
    
    # Display metrics in columns
    col1, col2, col3, col4 = st.columns(4)
    
    with col1:
        st.metric("Total Transactions", total_transactions)
    
    with col2:
        st.metric("Total Amount", f"₹{total_amount:,.2f}")
    
    with col3:
        st.metric("Average Transaction", f"₹{avg_transaction:,.2f}")
    
    with col4:
        st.metric("Date Range", date_range)

def display_category_insights(df, categorizer):
    """Display category-wise insights"""
    
    # Apply global date filter
    df_filtered = apply_date_filter(df)
    
    if len(df_filtered) == 0:
        return
    
    st.subheader("📊 Category Insights")
    
    # Category summary
    category_summary = df_filtered.groupby('category').agg({
        'amount_numeric': ['sum', 'mean', 'count']
    }).round(2)
    
    category_summary.columns = ['Total Amount', 'Average Amount', 'Transaction Count']
    category_summary = category_summary.sort_values('Total Amount', ascending=False)
    
    # Add percentage of total
    category_summary['% of Total'] = (category_summary['Total Amount'] / category_summary['Total Amount'].sum() * 100).round(1)
    
    st.dataframe(
        category_summary,
        use_container_width=True
    )
    
    # Top spending categories
    st.subheader("🏆 Top Spending Categories")
    top_categories = category_summary.head(5)
    
    for idx, (category, row) in enumerate(top_categories.iterrows(), 1):
        color = categorizer.get_category_color(category)
        st.markdown(f"""
        <div style="background-color: {color}20; padding: 10px; margin: 5px 0; border-radius: 5px; border-left: 4px solid {color};">
            <strong>#{idx} {category}</strong><br>
            Amount: ₹{row['Total Amount']:,.2f} ({row['% of Total']}%)<br>
            Transactions: {int(row['Transaction Count'])} | Average: ₹{row['Average Amount']:,.2f}
        </div>
        """, unsafe_allow_html=True)

def export_data(df):
    """Export transaction data to CSV"""
    
    # Apply global date filter
    df_filtered = apply_date_filter(df)
    
    if len(df_filtered) == 0:
        st.warning("No data to export in the selected date range.")
        return
    
    # Prepare export dataframe
    export_df = df_filtered[[
        'date_parsed', 'subject', 'category', 'amount', 
        'ai_extracted_amount', 'regex_extracted_amounts'
    ]].copy()
    
    export_df = export_df.rename(columns={
        'date_parsed': 'Date',
        'subject': 'Transaction Description',
        'category': 'Category',
        'amount': 'Amount',
        'ai_extracted_amount': 'AI Extracted Amount',
        'regex_extracted_amounts': 'Regex Extracted Amounts'
    })
    
    # Convert to CSV
    csv = export_df.to_csv(index=False)
    
    st.download_button(
        label="📥 Download Transaction Data (CSV)",
        data=csv,
        file_name=f"sbi_transactions_{datetime.now().strftime('%Y%m%d_%H%M%S')}.csv",
        mime="text/csv"
    )

def main():
    """Main Streamlit application"""
    
    # Initialize configuration
    config_manager = ConfigManager()
    
    st.title("🏦 SBI Transaction Analyzer")
    st.markdown("Analyze your SBI ATM transaction alerts with AI-powered categorization")
    
    # Display configuration status in sidebar only if there are issues
    config_manager.display_config_status()
    
    # Check if configuration is valid
    if not config_manager.validate_config():
        st.error("⚠️ Configuration incomplete. Please check the sidebar for setup instructions.")
        st.stop()
    
    # Initialize email extractor
    extractor = SBIEmailExtractor(config_manager)
    
    # Authentication section
    st.sidebar.header("🔐 Authentication")
    
    # Check for OAuth callback
    query_params = st.query_params
    if 'code' in query_params and not st.session_state.authenticated:
        with st.spinner("Processing authentication..."):
            success, user_email = extractor.handle_oauth_callback(query_params['code'])
            if success:
                st.session_state.authenticated = True
                st.session_state.user_email = user_email
                st.success(f"✅ Successfully authenticated as {user_email}")
                # Clear the URL parameters
                st.query_params.clear()
                st.rerun()
            else:
                st.error("❌ Authentication failed")
    
    # Check existing authentication
    if not st.session_state.authenticated:
        success, user_email = extractor.authenticate_gmail()
        if success:
            st.session_state.authenticated = True
            st.session_state.user_email = user_email
    
    # Display authentication status
    if st.session_state.authenticated:
        st.sidebar.success(f"✅ Authenticated as {st.session_state.user_email}")
        
        if st.sidebar.button("🔓 Logout"):
            st.session_state.authenticated = False
            st.session_state.user_email = None
            if os.path.exists('token.json'):
                os.remove('token.json')
            st.rerun()
    else:
        st.sidebar.info("🔒 Not authenticated")
        
        # Generate authorization URL
        auth_url = extractor.get_authorization_url()
        if auth_url:
            st.sidebar.markdown(f"""
            **To get started:**
            1. Click the link below to authorize Gmail access
            2. Grant permissions in Google
            3. You'll be redirected back automatically
            
            [🔐 **Authorize Gmail Access**]({auth_url})
            """)
        else:
            st.sidebar.error("Unable to generate authorization URL. Check configuration.")
    
    # Main application (only show if authenticated)
    if st.session_state.authenticated:
        
        # Sidebar controls
        st.sidebar.header("⚙️ Analysis Settings")
        
        max_emails = st.sidebar.slider(
            "Max emails to analyze", 
            min_value=10, 
            max_value=200, 
            value=50, 
            step=10
        )
        
        # Date filter controls
        st.sidebar.subheader("📅 Date Filter")
        date_filter_enabled = st.sidebar.checkbox("Enable date filter", key="date_filter_enabled")
        
        if date_filter_enabled:
            # Default to last 30 days
            default_start = datetime.now() - timedelta(days=30)
            default_end = datetime.now()
            
            start_date = st.sidebar.date_input(
                "Start Date",
                value=default_start.date(),
                key="date_filter_start"
            )
            end_date = st.sidebar.date_input(
                "End Date", 
                value=default_end.date(),
                key="date_filter_end"
            )
            
            if start_date > end_date:
                st.sidebar.error("Start date must be before end date")
        
        # Process emails button
        if st.sidebar.button("🔍 Analyze Transactions", type="primary"):
            
            progress_bar = st.progress(0)
            status_text = st.empty()
            
            def update_progress(current, total):
                progress = current / total
                progress_bar.progress(progress)
                status_text.text(f"Processing email {current}/{total}...")
            
            with st.spinner("Fetching and analyzing emails..."):
                transactions = extractor.process_emails(
                    max_emails=max_emails,
                    progress_callback=update_progress
                )
            
            progress_bar.empty()
            status_text.empty()
            
            if transactions:
                # Convert to DataFrame
                df = pd.DataFrame(transactions)
                
                # Process data
                df = df[df['amount'].notna()]  # Remove rows without amounts
                df['amount_numeric'] = df['amount'].apply(lambda x: float(str(x).replace(',', '')) if x else 0)
                
                # Parse dates
                df['date_parsed'] = df['date'].apply(lambda x: dateutil.parser.parse(x) if x else datetime.now())
                
                # Store in session state
                st.session_state.transactions_df = df
                st.session_state.categorizer = extractor.categorizer
                
                st.success(f"✅ Successfully analyzed {len(df)} transactions!")
            else:
                st.warning("No transactions found or analysis failed.")
    
    # Display results if available
    if st.session_state.get('transactions_df') is not None:
        df = st.session_state.transactions_df
        categorizer = st.session_state.categorizer
        
        # Create tabs for different views
        tab1, tab2, tab3, tab4 = st.tabs(["📊 Dashboard", "📋 Transactions", "💡 Insights", "📥 Export"])
        
        with tab1:
            st.header("📊 Transaction Dashboard")
            
            # Summary metrics
            create_summary_metrics(df)
            
            # Visualizations
            with st.spinner("Creating visualizations..."):
                fig_pie, fig_bar, fig_timeline, fig_monthly = create_visualizations(df, categorizer)
                
                if fig_pie:
                    col1, col2 = st.columns(2)
                    
                    with col1:
                        st.plotly_chart(fig_pie, use_container_width=True)
                    
                    with col2:
                        st.plotly_chart(fig_bar, use_container_width=True)
                    
                    st.plotly_chart(fig_timeline, use_container_width=True)
                    st.plotly_chart(fig_monthly, use_container_width=True)
        
        with tab2:
            st.header("📋 Transaction Details")
            display_transaction_table(df)
        
        with tab3:
            st.header("💡 Transaction Insights")
            display_category_insights(df, categorizer)
        
        with tab4:
            st.header("📥 Export Data")
            st.write("Download your transaction data for further analysis.")
            export_data(df)
    
    # Footer
    st.markdown("---")
    st.markdown(
        "Built with ❤️ using Streamlit | "
        "Powered by Google Gmail API & Replicate AI"
    )

if __name__ == "__main__":
    main()
