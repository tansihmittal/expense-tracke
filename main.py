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
from google_auth_oauthlib.flow import Flow
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
            'REPLICATE_API_TOKEN': os.getenv('REPLICATE_API_TOKEN')
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
                **For Streamlit Cloud:**
                1. Go to your app settings
                2. Click on "Secrets"
                3. Add the following secrets:
                ```
                GMAIL_CLIENT_ID = "your_client_id_here"
                GMAIL_CLIENT_SECRET = "your_client_secret_here"
                REPLICATE_API_TOKEN = "your_replicate_token_here"
                ```
                
                **For local development:**
                Create a `.secret` file in your project root with:
                ```
                GMAIL_CLIENT_ID=your_client_id_here
                GMAIL_CLIENT_SECRET=your_client_secret_here
                REPLICATE_API_TOKEN=your_replicate_token_here
                ```
                """)

class AITransactionCategorizer:
    """AI-powered class to categorize transactions using Replicate API"""
    
    def __init__(self, replicate_token: str):
        self.replicate_token = replicate_token
        self.categories = {
            # Banking & Finance
            'ATM Withdrawal': '#FF6B6B',
            'Transfer': '#A8E6CF',
            'Other': '#D3D3D3'
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
                - Transfer: UPI transfers, NEFT, RTGS, IMPS, bank transfers

                **Fallback:**
                - Other: Only if transaction doesn't clearly fit any specific category above

                ## Key Decision Rules:
                1. **Merchant/Vendor Name**: Primary indicator - match known brands to their logical category
                2. **Transaction Purpose**: If description includes purpose keywords, prioritize those
                3. **Amount Context**: Large amounts might indicate investments/transfers, small regular amounts suggest subscriptions
                4. **Specificity**: Choose the MOST SPECIFIC category that fits

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
            'Transfer': ['transfer', 'upi', 'neft', 'rtgs', 'imps', 'bank transfer', 'fund transfer'],
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
    
    def get_auth_url(self):
        """Generate OAuth authorization URL for manual flow"""
        try:
            client_id = self.config_manager.get_config_value('GMAIL_CLIENT_ID')
            client_secret = self.config_manager.get_config_value('GMAIL_CLIENT_SECRET')
            
            if not client_id or not client_secret:
                return None
            
            # Create OAuth2 config for web flow
            client_config = {
                "web": {
                    "client_id": client_id,
                    "client_secret": client_secret,
                    "auth_uri": "https://accounts.google.com/o/oauth2/auth",
                    "token_uri": "https://oauth2.googleapis.com/token",
                    "auth_provider_x509_cert_url": "https://www.googleapis.com/oauth2/v1/certs",
                    "redirect_uris": ["urn:ietf:wg:oauth:2.0:oob"]
                }
            }
            
            flow = Flow.from_client_config(
                client_config, 
                scopes=self.scopes,
                redirect_uri="urn:ietf:wg:oauth:2.0:oob"
            )
            
            auth_url, _ = flow.authorization_url(prompt='consent')
            
            # Store flow in session state for later use
            st.session_state.oauth_flow = flow
            
            return auth_url
            
        except Exception as e:
            st.error(f"Error generating auth URL: {e}")
            return None

    def authenticate_with_code(self, auth_code: str):
        """Authenticate using the authorization code from manual flow"""
        try:
            if 'oauth_flow' not in st.session_state:
                st.error("OAuth flow not initialized. Please start the authentication process again.")
                return False, None
            
            flow = st.session_state.oauth_flow
            
            # Exchange code for credentials
            flow.fetch_token(code=auth_code)
            creds = flow.credentials
            
            # Try to save the credentials, but don't fail if we can't
            try:
                with open('token.json', 'w') as token:
                    token.write(creds.to_json())
            except Exception as e:
                st.warning(f"Could not save token to file: {e}. You may need to re-authenticate after app restart.")
            
            # Store credentials in session state as backup
            st.session_state.oauth_credentials = creds.to_json()
            
            # Build the Gmail service
            self.service = build('gmail', 'v1', credentials=creds)
            
            # Get user email from token
            user_info = self.service.users().getProfile(userId='me').execute()
            user_email = user_info.get('emailAddress', 'Unknown')
            
            return True, user_email
            
        except Exception as e:
            st.error(f"Authentication failed: {e}")
            return False, None

    def authenticate_gmail(self):
        """Authenticate with Gmail using existing token or OAuth2"""
        try:
            client_id = self.config_manager.get_config_value('GMAIL_CLIENT_ID')
            client_secret = self.config_manager.get_config_value('GMAIL_CLIENT_SECRET')
            
            if not client_id or not client_secret:
                st.error("Gmail credentials not configured")
                return False, None
            
            creds = None
            
            # Check session state first (for Streamlit Cloud)
            if 'oauth_credentials' in st.session_state:
                try:
                    creds = Credentials.from_authorized_user_info(
                        json.loads(st.session_state.oauth_credentials), 
                        self.scopes
                    )
                except Exception as e:
                    st.warning(f"Could not load credentials from session: {e}")
            
            # Check if token.json exists (saved credentials)
            if not creds and os.path.exists('token.json'):
                try:
                    creds = Credentials.from_authorized_user_file('token.json', self.scopes)
                except Exception as e:
                    st.warning(f"Could not load credentials from file: {e}")
            
            # If there are no (valid) credentials available, return False to trigger manual flow
            if not creds or not creds.valid:
                if creds and creds.expired and creds.refresh_token:
                    try:
                        creds.refresh(Request())
                        # Update session state with refreshed token
                        st.session_state.oauth_credentials = creds.to_json()
                    except Exception as e:
                        st.error(f"Token refresh failed: {e}")
                        return False, None
                else:
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
    
    fig_monthly = px.bar(
        monthly_spending,
        x='month',
        y='amount_numeric',
        color='category',
        title='Monthly Spending by Category',
        color_discrete_map={cat: categorizer.get_category_color(cat) for cat in monthly_spending['category'].unique()}
    )
    
    return fig_pie, fig_bar, fig_timeline, fig_monthly

def main():
    """Main Streamlit app"""
    
    st.title("🏦 SBI Transaction Analyzer")
    st.markdown("Extract and analyze your SBI bank transaction alerts with AI-powered categorization")
    
    # Initialize configuration manager
    config_manager = ConfigManager()
    
    # Sidebar for authentication and configuration
    st.sidebar.header("Authentication")

    if not st.session_state.authenticated:
        st.sidebar.info("Please login with your Gmail account to analyze SBI transactions")
        
        # Check if we can authenticate with existing token
        if st.sidebar.button("🔐 Try Auto-Login", type="secondary"):
            with st.spinner("Checking existing credentials..."):
                if not config_manager.validate_config():
                    st.sidebar.error("Configuration incomplete. Please check credentials.")
                    config_manager.display_config_status()
                else:
                    extractor = SBIEmailExtractor(config_manager)
                    success, user_email = extractor.authenticate_gmail()
                    if success:
                        st.session_state.authenticated = True
                        st.session_state.user_email = user_email
                        st.rerun()
                    else:
                        st.sidebar.info("No existing credentials found. Please use manual login.")
        
        st.sidebar.markdown("---")
        st.sidebar.subheader("Manual Login")
        
        # Manual OAuth flow for Streamlit Cloud
        if st.sidebar.button("🔗 Get Authorization URL", type="primary"):
            if not config_manager.validate_config():
                st.sidebar.error("Configuration incomplete. Please check credentials.")
                config_manager.display_config_status()
            else:
                extractor = SBIEmailExtractor(config_manager)
                auth_url = extractor.get_auth_url()
                if auth_url:
                    st.sidebar.success("✅ Authorization URL generated!")
                    st.sidebar.markdown(f"**Click here to authorize:** [Authorize App]({auth_url})")
                    st.sidebar.markdown("After authorization, copy the code and paste it below:")
                    
                    auth_code = st.sidebar.text_input("Authorization Code", type="password")
                    
                    if st.sidebar.button("🚀 Complete Login"):
                        if auth_code:
                            with st.spinner("Completing authentication..."):
                                success, user_email = extractor.authenticate_with_code(auth_code)
                                if success:
                                    st.session_state.authenticated = True
                                    st.session_state.user_email = user_email
                                    st.rerun()
                                else:
                                    st.sidebar.error("Authentication failed. Please try again.")
                        else:
                            st.sidebar.error("Please enter the authorization code.")
                else:
                    st.sidebar.error("Failed to generate authorization URL")
    else:
        st.sidebar.success(f"✅ Logged in as: {st.session_state.user_email}")
        
        if st.sidebar.button("🚪 Logout"):
            # Clear authentication state
            st.session_state.authenticated = False
            st.session_state.user_email = None
            
            # Remove saved token
            # Remove saved token
            if os.path.exists('token.json'):
                os.remove('token.json')
            
            st.rerun()
    
    # Only show main app if authenticated
    if st.session_state.authenticated:
        # Check configuration even when authenticated
        if not config_manager.validate_config():
            st.error("Configuration incomplete. Please check your credentials in the sidebar.")
            config_manager.display_config_status()
            return
        
        # Initialize extractor
        extractor = SBIEmailExtractor(config_manager)
        
        # Main app controls
        st.sidebar.markdown("---")
        st.sidebar.header("Analysis Controls")
        
        # Number of emails to analyze
        max_emails = st.sidebar.slider("Number of emails to analyze", min_value=10, max_value=200, value=50, step=10)
        
        # Date filter controls
        st.sidebar.subheader("Date Filter")
        date_filter_enabled = st.sidebar.checkbox("Enable date filter", key="date_filter_enabled")
        
        if date_filter_enabled:
            col1, col2 = st.sidebar.columns(2)
            with col1:
                start_date = st.date_input("From", value=datetime.now() - timedelta(days=30), key="date_filter_start")
            with col2:
                end_date = st.date_input("To", value=datetime.now(), key="date_filter_end")
        
        # Analyze button
        if st.sidebar.button("🔍 Analyze Transactions", type="primary"):
            st.session_state.analyze_clicked = True
        
        # Clear data button
        if st.sidebar.button("🗑️ Clear Data"):
            if 'transaction_data' in st.session_state:
                del st.session_state.transaction_data
            st.session_state.analyze_clicked = False
            st.rerun()
        
        # Show analysis results
        if st.session_state.get('analyze_clicked', False):
            if 'transaction_data' not in st.session_state:
                st.info("🔍 Analyzing your SBI transaction emails...")
                
                # Progress bar
                progress_bar = st.progress(0)
                status_text = st.empty()
                
                def update_progress(current, total):
                    progress = current / total
                    progress_bar.progress(progress)
                    status_text.text(f"Processing email {current} of {total}...")
                
                # Re-authenticate if needed
                success, _ = extractor.authenticate_gmail()
                if not success:
                    st.error("Authentication failed. Please login again.")
                    st.session_state.authenticated = False
                    st.rerun()
                    return
                
                # Process emails
                with st.spinner("Extracting and categorizing transactions..."):
                    results = extractor.process_emails(max_emails, update_progress)
                
                # Clear progress indicators
                progress_bar.empty()
                status_text.empty()
                
                if results:
                    st.session_state.transaction_data = results
                    st.success(f"✅ Successfully analyzed {len(results)} transactions!")
                else:
                    st.warning("No transactions found or analysis failed.")
                    return
            
            # Display results if we have data
            if 'transaction_data' in st.session_state:
                display_results(st.session_state.transaction_data, extractor.categorizer)
    
    else:
        # Show welcome message when not authenticated
        st.info("👋 Welcome! Please authenticate with your Gmail account to start analyzing your SBI transactions.")
        
        # Show features overview
        st.markdown("## 🌟 Features")
        col1, col2, col3 = st.columns(3)
        
        with col1:
            st.markdown("""
            **📧 Email Analysis**
            - Extracts SBI transaction alerts
            - AI-powered amount extraction
            - Smart transaction parsing
            """)
        
        with col2:
            st.markdown("""
            **🏷️ AI Categorization**
            - Automatic transaction categorization
            - Banking & Finance categories
            - Intelligent pattern recognition
            """)
        
        with col3:
            st.markdown("""
            **📊 Visualizations**
            - Category distribution charts
            - Timeline analysis
            - Monthly spending trends
            """)

def display_results(transaction_data, categorizer):
    """Display analysis results with visualizations and data tables"""
    
    # Convert to DataFrame
    df = pd.DataFrame(transaction_data)
    
    # Clean and process data
    df['amount_numeric'] = pd.to_numeric(
        df['amount'].str.replace(',', '').str.replace('Rs.', '').str.replace('₹', '').str.strip(),
        errors='coerce'
    )
    
    # Parse dates
    df['date_parsed'] = pd.to_datetime(df['date'], errors='coerce')
    
    # Remove rows with invalid amounts or dates
    df = df.dropna(subset=['amount_numeric', 'date_parsed'])
    
    if len(df) == 0:
        st.error("No valid transactions found after data cleaning.")
        return
    
    # Apply date filter if enabled
    df_display = apply_date_filter(df)
    
    if len(df_display) == 0:
        st.warning("No transactions found in the selected date range.")
        return
    
    # Summary metrics
    st.header("📊 Transaction Summary")
    
    col1, col2, col3, col4 = st.columns(4)
    
    with col1:
        st.metric(
            "Total Transactions", 
            len(df_display),
            delta=f"{len(df_display) - len(df)}" if st.session_state.get('date_filter_enabled') else None
        )
    
    with col2:
        total_amount = df_display['amount_numeric'].sum()
        st.metric(
            "Total Amount", 
            f"₹{total_amount:,.2f}",
            delta=f"₹{total_amount - df['amount_numeric'].sum():,.2f}" if st.session_state.get('date_filter_enabled') else None
        )
    
    with col3:
        avg_amount = df_display['amount_numeric'].mean()
        st.metric("Average Amount", f"₹{avg_amount:,.2f}")
    
    with col4:
        date_range = (df_display['date_parsed'].max() - df_display['date_parsed'].min()).days
        st.metric("Date Range", f"{date_range} days")
    
    # Category breakdown
    st.subheader("🏷️ Category Breakdown")
    category_summary = df_display.groupby('category').agg({
        'amount_numeric': ['count', 'sum', 'mean']
    }).round(2)
    category_summary.columns = ['Count', 'Total Amount', 'Average Amount']
    category_summary = category_summary.sort_values('Total Amount', ascending=False)
    
    # Add color indicators
    category_summary_display = category_summary.copy()
    if categorizer:
        category_summary_display.index = [
            f"🔴 {cat}" if categorizer.get_category_color(cat) == '#FF6B6B' else
            f"🟢 {cat}" if categorizer.get_category_color(cat) == '#A8E6CF' else
            f"⚪ {cat}"
            for cat in category_summary_display.index
        ]
    
    st.dataframe(category_summary_display, use_container_width=True)
    
    # Visualizations
    st.header("📈 Visualizations")
    
    if categorizer:
        fig_pie, fig_bar, fig_timeline, fig_monthly = create_visualizations(df, categorizer)
        
        if fig_pie:
            # Create tabs for different visualizations
            tab1, tab2, tab3, tab4 = st.tabs(["Category Distribution", "Amount by Category", "Timeline", "Monthly Trends"])
            
            with tab1:
                st.plotly_chart(fig_pie, use_container_width=True)
            
            with tab2:
                st.plotly_chart(fig_bar, use_container_width=True)
            
            with tab3:
                st.plotly_chart(fig_timeline, use_container_width=True)
            
            with tab4:
                st.plotly_chart(fig_monthly, use_container_width=True)
    
    # Detailed transaction table
    st.header("📋 Transaction Details")
    
    # Search and filter options
    col1, col2 = st.columns([2, 1])
    with col1:
        search_term = st.text_input("🔍 Search transactions", placeholder="Search by subject, amount, or category...")
    with col2:
        category_filter = st.selectbox("Filter by category", ["All"] + sorted(df_display['category'].unique()))
    
    # Apply filters
    df_filtered = df_display.copy()
    
    if search_term:
        search_mask = (
            df_filtered['subject'].str.contains(search_term, case=False, na=False) |
            df_filtered['amount'].str.contains(search_term, case=False, na=False) |
            df_filtered['category'].str.contains(search_term, case=False, na=False)
        )
        df_filtered = df_filtered[search_mask]
    
    if category_filter != "All":
        df_filtered = df_filtered[df_filtered['category'] == category_filter]
    
    # Display table
    display_columns = ['date_parsed', 'amount', 'category', 'subject', 'email_body_preview']
    df_display_table = df_filtered[display_columns].copy()
    df_display_table['date_parsed'] = df_display_table['date_parsed'].dt.strftime('%Y-%m-%d %H:%M')
    df_display_table = df_display_table.rename(columns={
        'date_parsed': 'Date',
        'amount': 'Amount',
        'category': 'Category',
        'subject': 'Subject',
        'email_body_preview': 'Email Preview'
    })
    
    st.dataframe(df_display_table, use_container_width=True)
    
    # Download options
    st.header("💾 Export Data")
    
    col1, col2 = st.columns(2)
    
    with col1:
        if st.button("📥 Download CSV"):
            csv = df_display.to_csv(index=False)
            st.download_button(
                label="Click to Download CSV",
                data=csv,
                file_name=f"sbi_transactions_{datetime.now().strftime('%Y%m%d_%H%M%S')}.csv",
                mime="text/csv"
            )
    
    with col2:
        if st.button("📊 Download Excel"):
            # Create Excel file in memory
            from io import BytesIO
            output = BytesIO()
            with pd.ExcelWriter(output, engine='openpyxl') as writer:
                df_display.to_excel(writer, sheet_name='Transactions', index=False)
                category_summary.to_excel(writer, sheet_name='Category Summary')
            
            st.download_button(
                label="Click to Download Excel",
                data=output.getvalue(),
                file_name=f"sbi_transactions_{datetime.now().strftime('%Y%m%d_%H%M%S')}.xlsx",
                mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
            )

if __name__ == "__main__":
    main()
