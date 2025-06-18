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
from googleapiclient.discovery import build
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
from collections import Counter
import os
from dotenv import load_dotenv
import dateutil.parser


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
        """Load configuration from environment variables and Streamlit secrets"""
        config = {}
        
        # Try to load from Streamlit secrets first (for cloud deployment)
        try:
            config = {
                'GMAIL_CLIENT_ID': st.secrets.get('GMAIL_CLIENT_ID', os.getenv('GMAIL_CLIENT_ID')),
                'GMAIL_CLIENT_SECRET': st.secrets.get('GMAIL_CLIENT_SECRET', os.getenv('GMAIL_CLIENT_SECRET')),
                'REPLICATE_API_TOKEN': st.secrets.get('REPLICATE_API_TOKEN', os.getenv('REPLICATE_API_TOKEN'))
            }
        except:
            # Fallback to environment variables
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
                **For Local Development:**
                Create a `.secret` file in your project root with:
                ```
                GMAIL_CLIENT_ID=your_client_id_here
                GMAIL_CLIENT_SECRET=your_client_secret_here
                REPLICATE_API_TOKEN=your_replicate_token_here
                ```
                
                **For Streamlit Cloud:**
                Add these to your app's secrets:
                - GMAIL_CLIENT_ID
                - GMAIL_CLIENT_SECRET  
                - REPLICATE_API_TOKEN
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
                - Transfer: Money transfers, fund transfers
                **Fallback:**
                - Other: Only if transaction doesn't clearly fit any specific category above

                ## Key Decision Rules:
                1. **Merchant/Vendor Name**: Primary indicator - match known brands to their logical category
                2. **Transaction Purpose**: If description includes purpose keywords, prioritize those
                3. **Amount Context**: Large amounts might indicate investments/transfers, small regular amounts suggest subscriptions
                4. **Specificity**: Choose the MOST SPECIFIC category that fits (e.g., "Transfer" over "Other")

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
            'ATM Withdrawal': ['atm', 'withdrawal', 'cash', 'withdraw'],
            'Transfer': ['transfer', 'fund transfer', 'imps', 'neft', 'rtgs']
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
    
    def get_oauth_url(self):
        """Generate OAuth URL for manual authentication"""
        try:
            client_id = self.config_manager.get_config_value('GMAIL_CLIENT_ID')
            if not client_id:
                return None
            
            # OAuth 2.0 parameters
            auth_url = "https://accounts.google.com/o/oauth2/auth"
            redirect_uri = "urn:ietf:wg:oauth:2.0:oob"  # For manual copy-paste flow
            scope = "https://www.googleapis.com/auth/gmail.readonly"
            
            oauth_url = (
                f"{auth_url}?"
                f"client_id={client_id}&"
                f"redirect_uri={redirect_uri}&"
                f"scope={scope}&"
                f"response_type=code&"
                f"access_type=offline&"
                f"prompt=consent"
            )
            
            return oauth_url
        except Exception as e:
            st.error(f"Error generating OAuth URL: {e}")
            return None
    
    def exchange_code_for_token(self, auth_code: str):
        """Exchange authorization code for access token"""
        try:
            client_id = self.config_manager.get_config_value('GMAIL_CLIENT_ID')
            client_secret = self.config_manager.get_config_value('GMAIL_CLIENT_SECRET')
            
            if not client_id or not client_secret:
                return False, None, "Missing OAuth credentials"
            
            token_url = "https://oauth2.googleapis.com/token"
            
            data = {
                'client_id': client_id,
                'client_secret': client_secret,
                'code': auth_code,
                'grant_type': 'authorization_code',
                'redirect_uri': 'urn:ietf:wg:oauth:2.0:oob'
            }
            
            response = requests.post(token_url, data=data)
            
            if response.status_code == 200:
                token_data = response.json()
                
                # Create credentials object
                creds = Credentials(
                    token=token_data.get('access_token'),
                    refresh_token=token_data.get('refresh_token'),
                    token_uri='https://oauth2.googleapis.com/token',
                    client_id=client_id,
                    client_secret=client_secret,
                    scopes=self.scopes
                )
                
                # Build Gmail service
                self.service = build('gmail', 'v1', credentials=creds)
                
                # Get user email
                user_info = self.service.users().getProfile(userId='me').execute()
                user_email = user_info.get('emailAddress', 'Unknown')
                
                # Store credentials in session state (not persistent across sessions)
                st.session_state.gmail_credentials = creds
                
                return True, user_email, "Authentication successful"
            else:
                error_data = response.json()
                return False, None, f"Token exchange failed: {error_data.get('error_description', 'Unknown error')}"
                
        except Exception as e:
            return False, None, f"Authentication error: {str(e)}"
    
    def restore_service_from_session(self):
        """Restore Gmail service from session state credentials"""
        try:
            if 'gmail_credentials' in st.session_state:
                creds = st.session_state.gmail_credentials
                
                # Refresh token if expired
                if creds.expired and creds.refresh_token:
                    creds.refresh(Request())
                
                self.service = build('gmail', 'v1', credentials=creds)
                return True
            return False
        except Exception as e:
            st.error(f"Error restoring Gmail service: {e}")
            return False
    
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
        st.sidebar.info("Please authenticate with your Gmail account to analyze SBI transactions")
        
        # Check if configuration is valid
        if not config_manager.validate_config():
            st.sidebar.error("Configuration incomplete. Please check credentials.")
            config_manager.display_config_status()
            return
        
        # Initialize extractor for OAuth URL generation
        extractor = SBIEmailExtractor(config_manager)
        oauth_url = extractor.get_oauth_url()
        
        if oauth_url:
            st.sidebar.markdown("### Step 1: Get Authorization Code")
            st.sidebar.markdown(f"[Click here to authorize Gmail access]({oauth_url})")
            st.sidebar.markdown("Copy the authorization code from the browser")
            
            st.sidebar.markdown("### Step 2: Enter Authorization Code")
            auth_code = st.sidebar.text_input(
                "Authorization Code",
                type="password",
                help="Paste the code you got from Gmail authorization"
            )
            
            if st.sidebar.button("🔐 Authenticate", type="primary"):
                if auth_code.strip():
                    with st.spinner("Authenticating..."):
                        success, user_email, message = extractor.exchange_code_for_token(auth_code.strip())
                        if success:
                            st.session_state.authenticated = True
                            st.session_state.user_email = user_email
                            st.success(f"✅ {message}")
                            st.rerun()
                        else:
                            st.sidebar.error(f"❌ {message}")
                else:
                    st.sidebar.error("Please enter the authorization code")
        else:
            st.sidebar.error("Unable to generate OAuth URL. Check configuration.")
    else:
        st.sidebar.success(f"✅ Logged in as: {st.session_state.user_email}")
        
        if st.sidebar.button("🚪 Logout"):
            # Clear authentication state
            st.session_state.authenticated = False
            st.session_state.user_email = None
            
            # Clear other session data
            keys_to_clear = ['transaction_data', 'categorizer', 'results_processed', 
                           'date_filter_enabled', 'date_filter_start', 'date_filter_end',
                           'gmail_credentials']
            for key in keys_to_clear:
                if key in st.session_state:
                    del st.session_state[key]
            
            st.rerun()

    # Only show configuration and other options if authenticated
    if st.session_state.authenticated:
        st.sidebar.header("Configuration")
        config_manager.display_config_status()
        
        # Settings
        st.sidebar.subheader("Analysis Settings")
        max_emails = st.sidebar.slider("Max Emails to Process", 5, 100, 20)

        # Date Range Filter
        st.sidebar.subheader("Date Range Filter")
        
        # Initialize date filter state if not exists
        if 'date_filter_enabled' not in st.session_state:
            st.session_state.date_filter_enabled = False
        
        date_filter_enabled = st.sidebar.checkbox(
            "Enable Date Range Filter", 
            value=st.session_state.date_filter_enabled,
            key="date_filter_checkbox"
        )
        st.session_state.date_filter_enabled = date_filter_enabled
        
        if date_filter_enabled:
            col1, col2 = st.sidebar.columns(2)
            with col1:
                start_date = st.date_input(
                    "From",
                    value=st.session_state.get('date_filter_start', datetime.now().date() - timedelta(days=30)),
                    key="start_date_input"
                )
                st.session_state.date_filter_start = start_date
            
            with col2:
                end_date = st.date_input(
                    "To",
                    value=st.session_state.get('date_filter_end', datetime.now().date()),
                    key="end_date_input"
                )
                st.session_state.date_filter_end = end_date

    # Main application logic - only show if authenticated
    if not st.session_state.authenticated:
        st.info("👈 Please authenticate using the sidebar to get started")
        return

    # Initialize extractor and categorizer
    if 'extractor' not in st.session_state:
        st.session_state.extractor = SBIEmailExtractor(config_manager)
        if not st.session_state.extractor.restore_service_from_session():
            st.error("Failed to restore Gmail connection. Please re-authenticate.")
            return

    # Action buttons
    col1, col2, col3 = st.columns([2, 2, 1])
    
    with col1:
        if st.button("📧 Analyze Transactions", type="primary"):
            with st.spinner("Fetching and analyzing emails..."):
                progress_bar = st.progress(0)
                status_text = st.empty()
                
                def progress_callback(current, total):
                    progress = current / total
                    progress_bar.progress(progress)
                    status_text.text(f"Processing email {current} of {total}")
                
                results = st.session_state.extractor.process_emails(
                    max_emails=max_emails,
                    progress_callback=progress_callback
                )
                
                progress_bar.empty()
                status_text.empty()
                
                if results:
                    st.session_state.transaction_data = results
                    st.session_state.results_processed = True
                    st.success(f"✅ Successfully processed {len(results)} emails!")
                else:
                    st.warning("No transaction emails found or processed.")
    
    with col2:
        if st.button("🔄 Refresh Data"):
            # Clear cached data
            keys_to_clear = ['transaction_data', 'results_processed']
            for key in keys_to_clear:
                if key in st.session_state:
                    del st.session_state[key]
            st.rerun()
    
    with col3:
        if st.session_state.get('transaction_data'):
            # Export functionality
            df_export = pd.DataFrame(st.session_state.transaction_data)
            csv_data = df_export.to_csv(index=False)
            st.download_button(
                "📄 Export CSV",
                data=csv_data,
                file_name=f"sbi_transactions_{datetime.now().strftime('%Y%m%d_%H%M%S')}.csv",
                mime="text/csv"
            )

    # Display results if available
    if st.session_state.get('results_processed') and st.session_state.get('transaction_data'):
        results = st.session_state.transaction_data
        
        # Convert to DataFrame for analysis
        df = pd.DataFrame(results)
        
        # Data cleaning and preparation
        if not df.empty:
            # Parse dates
            df['date_parsed'] = pd.to_datetime(df['date'], errors='coerce')
            
            # Clean and convert amounts
            df['amount_numeric'] = df['amount'].apply(lambda x: 
                float(str(x).replace(',', '')) if x and str(x) != 'None' else 0.0
            )
            
            # Filter out zero amounts
            df = df[df['amount_numeric'] > 0]
            
            if df.empty:
                st.warning("No valid transactions with amounts found.")
                return
            
            # Get categorizer for visualizations
            categorizer = st.session_state.extractor.categorizer
            
            # Apply date filter if enabled
            df_display = apply_date_filter(df)
            
            # Summary metrics
            st.header("📊 Transaction Summary")
            
            if len(df_display) == 0:
                st.warning("No transactions in selected date range.")
            else:
                col1, col2, col3, col4 = st.columns(4)
                
                with col1:
                    st.metric("Total Transactions", len(df_display))
                
                with col2:
                    total_amount = df_display['amount_numeric'].sum()
                    st.metric("Total Amount", f"₹{total_amount:,.2f}")
                
                with col3:
                    avg_amount = df_display['amount_numeric'].mean()
                    st.metric("Average Amount", f"₹{avg_amount:,.2f}")
                
                with col4:
                    unique_categories = df_display['category'].nunique()
                    st.metric("Categories", unique_categories)
                
                # Visualizations
                if categorizer:
                    st.header("📈 Analytics")
                    
                    fig_pie, fig_bar, fig_timeline, fig_monthly = create_visualizations(df, categorizer)
                    
                    if fig_pie:
                        # Two columns for charts
                        col1, col2 = st.columns(2)
                        
                        with col1:
                            st.plotly_chart(fig_pie, use_container_width=True)
                        
                        with col2:
                            st.plotly_chart(fig_bar, use_container_width=True)
                        
                        # Full width charts
                        st.plotly_chart(fig_timeline, use_container_width=True)
                        st.plotly_chart(fig_monthly, use_container_width=True)
                
                # Category breakdown
                st.header("🏷️ Category Breakdown")
                category_summary = df_display.groupby('category').agg({
                    'amount_numeric': ['count', 'sum', 'mean'],
                    'date_parsed': ['min', 'max']
                }).round(2)
                
                category_summary.columns = ['Count', 'Total Amount', 'Average Amount', 'First Transaction', 'Last Transaction']
                category_summary = category_summary.sort_values('Total Amount', ascending=False)
                
                st.dataframe(category_summary, use_container_width=True)
                
                # Detailed transaction table
                st.header("📋 Transaction Details")
                
                # Filters for the table
                col1, col2, col3 = st.columns(3)
                
                with col1:
                    selected_categories = st.multiselect(
                        "Filter by Category",
                        options=df_display['category'].unique(),
                        default=df_display['category'].unique()
                    )
                
                with col2:
                    min_amount = st.number_input(
                        "Minimum Amount",
                        min_value=0.0,
                        value=0.0,
                        step=10.0
                    )
                
                with col3:
                    max_amount = st.number_input(
                        "Maximum Amount",
                        min_value=0.0,
                        value=float(df_display['amount_numeric'].max()),
                        step=100.0
                    )
                
                # Apply filters
                filtered_df = df_display[
                    (df_display['category'].isin(selected_categories)) &
                    (df_display['amount_numeric'] >= min_amount) &
                    (df_display['amount_numeric'] <= max_amount)
                ]
                
                # Display table
                display_columns = ['date_parsed', 'category', 'amount_numeric', 'subject', 'email_body_preview']
                display_df = filtered_df[display_columns].copy()
                display_df.columns = ['Date', 'Category', 'Amount (₹)', 'Subject', 'Preview']
                display_df = display_df.sort_values('Date', ascending=False)
                
                st.dataframe(
                    display_df,
                    use_container_width=True,
                    hide_index=True,
                    column_config={
                        "Date": st.column_config.DatetimeColumn(
                            "Date",
                            format="DD/MM/YYYY HH:mm"
                        ),
                        "Amount (₹)": st.column_config.NumberColumn(
                            "Amount (₹)",
                            format="₹%.2f"
                        ),
                        "Preview": st.column_config.TextColumn(
                            "Preview",
                            width="large"
                        )
                    }
                )
                
                # Email details expander
                if st.checkbox("Show detailed email content"):
                    st.subheader("📧 Email Details")
                    
                    email_index = st.selectbox(
                        "Select email to view",
                        options=range(len(filtered_df)),
                        format_func=lambda x: f"{filtered_df.iloc[x]['subject'][:50]}... (₹{filtered_df.iloc[x]['amount_numeric']})"
                    )
                    
                    if email_index is not None:
                        selected_email = filtered_df.iloc[email_index]
                        
                        col1, col2 = st.columns([1, 2])
                        
                        with col1:
                            st.write("**Date:**", selected_email['date_parsed'].strftime("%d/%m/%Y %H:%M"))
                            st.write("**Category:**", selected_email['category'])
                            st.write("**Amount:**", f"₹{selected_email['amount_numeric']}")
                            st.write("**Subject:**", selected_email['subject'])
                        
                        with col2:
                            st.write("**Email Content:**")
                            st.text_area(
                                "Full Email Text",
                                value=selected_email.get('full_email_text', 'Not available'),
                                height=300,
                                key="email_content_display"
                            )

    # Footer
    st.markdown("---")
    st.markdown(
        """
        <div style='text-align: center; color: #666;'>
            <p>🏦 SBI Transaction Analyzer | Built with ❤️ using Streamlit</p>
            <p><small>This app analyzes your SBI transaction alert emails. Your data is processed locally and not stored.</small></p>
        </div>
        """,
        unsafe_allow_html=True
    )

if __name__ == "__main__":
    main()
