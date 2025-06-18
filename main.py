import streamlit as st
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
import dateutil.parser

# Set page config
st.set_page_config(
    page_title="SBI Transaction Analyzer",
    page_icon="🏦",
    layout="wide",
    initial_sidebar_state="expanded"
)

# Initialize session state
if 'authenticated' not in st.session_state:
    st.session_state.authenticated = False
if 'user_email' not in st.session_state:
    st.session_state.user_email = None
if 'credentials' not in st.session_state:
    st.session_state.credentials = None

class ConfigManager:
    """Manages configuration and credentials with proper error handling"""
    
    def __init__(self):
        self.config = self._load_config()
        self.validation_errors = []
    
    def _load_config(self) -> Dict[str, str]:
        """Load configuration from Streamlit secrets or environment variables"""
        config = {}
        
        # Try Streamlit secrets first (for cloud deployment)
        try:
            config = {
                'GMAIL_CLIENT_ID': st.secrets.get('GMAIL_CLIENT_ID', os.getenv('GMAIL_CLIENT_ID')),
                'GMAIL_CLIENT_SECRET': st.secrets.get('GMAIL_CLIENT_SECRET', os.getenv('GMAIL_CLIENT_SECRET')),
                'REPLICATE_API_TOKEN': st.secrets.get('REPLICATE_API_TOKEN', os.getenv('REPLICATE_API_TOKEN')),
                'REDIRECT_URI': st.secrets.get('REDIRECT_URI', os.getenv('REDIRECT_URI'))
            }
        except Exception:
            # Fallback to environment variables
            config = {
                'GMAIL_CLIENT_ID': os.getenv('GMAIL_CLIENT_ID'),
                'GMAIL_CLIENT_SECRET': os.getenv('GMAIL_CLIENT_SECRET'),
                'REPLICATE_API_TOKEN': os.getenv('REPLICATE_API_TOKEN'),
                'REDIRECT_URI': os.getenv('REDIRECT_URI')
            }
        
        return config
    
    def validate_config(self) -> bool:
        """Validate that all required configuration is present"""
        self.validation_errors = []
        
        required_fields = {
            'GMAIL_CLIENT_ID': 'Gmail OAuth Client ID',
            'GMAIL_CLIENT_SECRET': 'Gmail OAuth Client Secret',
            'REPLICATE_API_TOKEN': 'Replicate API Token',
            'REDIRECT_URI': 'OAuth Redirect URI'
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
        if not self.validate_config():
            st.sidebar.subheader("⚠️ Configuration Issues")
            
            for error in self.validation_errors:
                st.sidebar.error(error)
            
            with st.sidebar.expander("Setup Instructions"):
                st.write("""
                **For Streamlit Cloud:**
                Add these secrets in your Streamlit Cloud app settings:
                - `GMAIL_CLIENT_ID` - Your Google OAuth Client ID
                - `GMAIL_CLIENT_SECRET` - Your Google OAuth Client Secret
                - `REPLICATE_API_TOKEN` - Your Replicate API token
                - `REDIRECT_URI` - Your app URL (e.g., https://your-app.streamlit.app/)
                
                **Google OAuth Setup:**
                1. Go to [Google Cloud Console](https://console.cloud.google.com/)
                2. Create a new project or select existing
                3. Enable Gmail API
                4. Create OAuth 2.0 credentials
                5. Add your Streamlit app URL to authorized redirect URIs
                
                **For local development:**
                Create a `.streamlit/secrets.toml` file:
                ```toml
                GMAIL_CLIENT_ID = "your_client_id_here"
                GMAIL_CLIENT_SECRET = "your_client_secret_here"
                REPLICATE_API_TOKEN = "your_replicate_token_here"
                REDIRECT_URI = "http://localhost:8501/"
                ```
                """)

class AITransactionCategorizer:
    """AI-powered class to categorize transactions using Replicate API"""
    
    def __init__(self, replicate_token: str):
        self.replicate_token = replicate_token
        self.categories = {
            'ATM Withdrawal': '#FF6B6B',
            'Transfer': '#A8E6CF',
            'Food & Dining': '#FFD93D',
            'Shopping': '#6BCF7F',
            'Bills & Utilities': '#4ECDC4',
            'Transportation': '#45B7D1',
            'Entertainment': '#96CEB4',
            'Healthcare': '#FFEAA7',
            'Education': '#DDA0DD',
            'Investment': '#98D8C8',
            'Other': '#D3D3D3'
        }
    
    def categorize_transaction_with_ai(self, subject: str, body: str, amount: str) -> str:
        """Use AI to categorize transactions intelligently"""
        try:
            url = "https://api.replicate.com/v1/models/meta/llama-2-70b-chat/predictions"
            
            headers = {
                "Authorization": f"Bearer {self.replicate_token}",
                "Content-Type": "application/json"
            }
            
            transaction_text = f"Subject: {subject}\nBody: {body}\nAmount: {amount}"
            categories_list = ", ".join([cat for cat in self.categories.keys() if cat != 'Other'])
            
            prompt = f"""You are a financial transaction categorization expert. Analyze the transaction below and assign it to exactly ONE category from this list:

{categories_list}

Transaction Analysis Guidelines:
- ATM Withdrawal: Cash withdrawals, ATM fees
- Transfer: UPI, NEFT, RTGS, IMPS, bank transfers
- Food & Dining: Restaurants, food delivery, groceries
- Shopping: Retail purchases, online shopping, clothing
- Bills & Utilities: Electricity, water, phone, internet bills
- Transportation: Fuel, taxi, public transport, parking
- Entertainment: Movies, games, subscriptions, events
- Healthcare: Medical bills, pharmacy, health insurance
- Education: School fees, courses, books, training
- Investment: Mutual funds, stocks, SIP, insurance premiums
- Other: Only if transaction doesn't clearly fit any specific category above

Transaction: {transaction_text}

Return only the category name. No explanation."""
            
            data = {
                "input": {
                    "prompt": prompt,
                    "max_new_tokens": 50,
                    "temperature": 0.1,
                    "system_prompt": "You are an expert financial transaction categorizer. Return exactly one category name from the provided list."
                }
            }
            
            response = requests.post(url, headers=headers, json=data, timeout=30)
            
            if response.status_code == 201:
                prediction = response.json()
                prediction_id = prediction['id']
                category = self.poll_prediction(prediction_id)
                
                if category and category.strip() in self.categories:
                    return category.strip()
                else:
                    return self.fallback_categorization(subject, body, amount)
            else:
                return self.fallback_categorization(subject, body, amount)
                
        except Exception as e:
            st.warning(f"AI categorization failed, using fallback: {str(e)}")
            return self.fallback_categorization(subject, body, amount)
    
    def poll_prediction(self, prediction_id: str, max_attempts: int = 15) -> Optional[str]:
        """Poll Replicate API for prediction completion"""
        import time
        
        url = f"https://api.replicate.com/v1/predictions/{prediction_id}"
        headers = {"Authorization": f"Bearer {self.replicate_token}"}
        
        for attempt in range(max_attempts):
            try:
                response = requests.get(url, headers=headers, timeout=10)
                
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
                        time.sleep(3)
                        continue
                else:
                    return None
                    
            except Exception:
                return None
        
        return None
    
    def fallback_categorization(self, subject: str, body: str, amount: str) -> str:
        """Fallback categorization using simple keyword matching"""
        text = f"{subject} {body}".lower()
        
        fallback_rules = {
            'ATM Withdrawal': ['atm', 'withdrawal', 'cash', 'withdraw'],
            'Transfer': ['transfer', 'upi', 'neft', 'rtgs', 'imps', 'fund transfer'],
            'Food & Dining': ['restaurant', 'food', 'dining', 'swiggy', 'zomato', 'grocery'],
            'Shopping': ['shopping', 'purchase', 'buy', 'amazon', 'flipkart', 'store'],
            'Bills & Utilities': ['bill', 'electricity', 'water', 'phone', 'internet', 'utility'],
            'Transportation': ['fuel', 'petrol', 'diesel', 'taxi', 'uber', 'ola', 'transport'],
            'Entertainment': ['movie', 'netflix', 'entertainment', 'game', 'subscription'],
            'Healthcare': ['medical', 'doctor', 'hospital', 'pharmacy', 'health'],
            'Education': ['education', 'school', 'course', 'training', 'book'],
            'Investment': ['investment', 'mutual fund', 'sip', 'insurance', 'premium']
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
        """Initialize the email extractor with configuration manager"""
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
        """Get OAuth authorization URL for cloud deployment"""
        try:
            client_id = self.config_manager.get_config_value('GMAIL_CLIENT_ID')
            client_secret = self.config_manager.get_config_value('GMAIL_CLIENT_SECRET')
            redirect_uri = self.config_manager.get_config_value('REDIRECT_URI')
            
            if not client_id or not client_secret or not redirect_uri:
                st.error("Gmail credentials not properly configured")
                return None, None
            
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
            
            flow = Flow.from_client_config(
                client_config,
                scopes=self.scopes,
                redirect_uri=redirect_uri
            )
            
            auth_url, _ = flow.authorization_url(
                prompt='consent',
                access_type='offline',
                include_granted_scopes='true'
            )
            return auth_url, flow
            
        except Exception as e:
            st.error(f"Error creating OAuth URL: {e}")
            return None, None
    
    def authenticate_with_code(self, auth_code: str, flow: Flow):
        """Authenticate using authorization code"""
        try:
            flow.fetch_token(code=auth_code)
            credentials = flow.credentials
            
            # Store credentials in session state
            st.session_state.credentials = {
                'token': credentials.token,
                'refresh_token': credentials.refresh_token,
                'token_uri': credentials.token_uri,
                'client_id': credentials.client_id,
                'client_secret': credentials.client_secret,
                'scopes': credentials.scopes
            }
            
            # Build the Gmail service
            self.service = build('gmail', 'v1', credentials=credentials)
            
            # Get user email
            user_info = self.service.users().getProfile(userId='me').execute()
            user_email = user_info.get('emailAddress', 'Unknown')
            
            st.session_state.authenticated = True
            st.session_state.user_email = user_email
            
            return True, user_email
            
        except Exception as e:
            st.error(f"Authentication failed: {e}")
            return False, None
    
    def authenticate_from_session(self):
        """Authenticate using stored session credentials"""
        try:
            if not st.session_state.get('credentials'):
                return False, None
            
            cred_data = st.session_state.credentials
            credentials = Credentials(
                token=cred_data['token'],
                refresh_token=cred_data['refresh_token'],
                token_uri=cred_data['token_uri'],
                client_id=cred_data['client_id'],
                client_secret=cred_data['client_secret'],
                scopes=cred_data['scopes']
            )
            
            # Refresh token if expired
            if credentials.expired and credentials.refresh_token:
                credentials.refresh(Request())
                # Update session state with new token
                st.session_state.credentials['token'] = credentials.token
            
            # Build the Gmail service
            self.service = build('gmail', 'v1', credentials=credentials)
            
            return True, st.session_state.user_email
            
        except Exception as e:
            st.error(f"Session authentication failed: {e}")
            # Clear invalid credentials
            st.session_state.credentials = None
            st.session_state.authenticated = False
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
            url = "https://api.replicate.com/v1/models/meta/llama-2-70b-chat/predictions"
            
            headers = {
                "Authorization": f"Bearer {replicate_token}",
                "Content-Type": "application/json"
            }
            
            prompt = f"""Extract the transaction amount from this SBI bank transaction alert email. 

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
{email_text}"""
            
            data = {
                "input": {
                    "prompt": prompt,
                    "max_new_tokens": 50,
                    "temperature": 0.1,
                    "system_prompt": "You are an expert at extracting financial amounts from SBI bank transaction alert emails. Return only the numeric value with decimal places."
                }
            }
            
            response = requests.post(url, headers=headers, json=data, timeout=30)
            
            if response.status_code == 201:
                prediction = response.json()
                prediction_id = prediction['id']
                return self.poll_prediction(prediction_id)
            else:
                return None
                
        except Exception as e:
            return None
    
    def poll_prediction(self, prediction_id: str, max_attempts: int = 15) -> Optional[str]:
        """Poll Replicate API for prediction completion"""
        import time
        
        replicate_token = self.config_manager.get_config_value('REPLICATE_API_TOKEN')
        url = f"https://api.replicate.com/v1/predictions/{prediction_id}"
        headers = {"Authorization": f"Bearer {replicate_token}"}
        
        for attempt in range(max_attempts):
            try:
                response = requests.get(url, headers=headers, timeout=10)
                
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
                        time.sleep(3)
                        continue
                else:
                    return None
                    
            except Exception:
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
            if 'date_parsed' in df.columns:
                mask = (df['date_parsed'].dt.date >= start_date) & (df['date_parsed'].dt.date <= end_date)
                return df[mask]
    
    return df

def create_visualizations(df, categorizer):
    """Create various visualizations for the transaction data"""
    if df.empty:
        st.warning("No data available for visualization")
        return
    
    # Convert amounts to numeric
    df_viz = df.copy()
    df_viz['amount_numeric'] = pd.to_numeric(df_viz['amount'].str.replace(',', ''), errors='coerce')
    df_viz = df_viz.dropna(subset=['amount_numeric'])
    
    if df_viz.empty:
        st.warning("No valid transaction amounts found for visualization")
        return
    
    col1, col2 = st.columns(2)
    
    with col1:
        # Category pie chart
        st.subheader("Transactions by Category")
        category_counts = df_viz['category'].value_counts()
        
        colors = [categorizer.get_category_color(cat) for cat in category_counts.index]
        
        fig_pie = px.pie(
            values=category_counts.values,
            names=category_counts.index,
            title="Distribution of Transaction Categories",
            color_discrete_sequence=colors
        )
        fig_pie.update_traces(textposition='inside', textinfo='percent+label')
        st.plotly_chart(fig_pie, use_container_width=True)
        
        # Category spending chart
        st.subheader("Spending by Category")
        category_amounts = df_viz.groupby('category')['amount_numeric'].sum().sort_values(ascending=True)
        
        colors_spending = [categorizer.get_category_color(cat) for cat in category_amounts.index]
        
        fig_bar = px.bar(
            x=category_amounts.values,
            y=category_amounts.index,
            orientation='h',
            title="Total Amount by Category",
            labels={'x': 'Amount (₹)', 'y': 'Category'},
            color_discrete_sequence=colors_spending
        )
        fig_bar.update_layout(showlegend=False)
        st.plotly_chart(fig_bar, use_container_width=True)
    
    with col2:
        # Parse dates for time series
        df_viz['date_parsed'] = pd.to_datetime(df_viz['date'], errors='coerce')
        df_viz = df_viz.dropna(subset=['date_parsed'])
        
        if not df_viz.empty:
            # Time series chart
            st.subheader("Spending Over Time")
            daily_spending = df_viz.groupby(df_viz['date_parsed'].dt.date)['amount_numeric'].sum().reset_index()
            daily_spending.columns = ['Date', 'Amount']
            
            fig_line = px.line(
                daily_spending,
                x='Date',
                y='Amount',
                title="Daily Spending Trend",
                labels={'Amount': 'Amount (₹)'}
            )
            fig_line.update_traces(line_color='#4ECDC4')
            st.plotly_chart(fig_line, use_container_width=True)
            
            # Monthly summary
            st.subheader("Monthly Summary")
            df_viz['month'] = df_viz['date_parsed'].dt.to_period('M')
            monthly_summary = df_viz.groupby('month').agg({
                'amount_numeric': ['sum', 'count', 'mean']
            }).round(2)
            
            monthly_summary.columns = ['Total Amount', 'Transaction Count', 'Average Amount']
            monthly_summary.index = monthly_summary.index.astype(str)
            
            st.dataframe(monthly_summary, use_container_width=True)

def main():
    """Main application function"""
    st.title("🏦 SBI Transaction Analyzer")
    st.markdown("Analyze your SBI ATM transaction emails with AI-powered categorization")
    
    # Initialize config manager
    config_manager = ConfigManager()
    
    # Show configuration status if there are issues
    config_manager.display_config_status()
    
    # Check if configuration is valid
    if not config_manager.validate_config():
        st.error("Please configure the required credentials to use this application.")
        st.stop()
    
    # Initialize email extractor
    extractor = SBIEmailExtractor(config_manager)
    
    # Handle authentication
    if not st.session_state.authenticated:
        st.subheader("🔐 Gmail Authentication Required")
        st.info("This app needs access to your Gmail to read SBI transaction emails.")
        
        # Check URL parameters for auth code (for OAuth callback)
        query_params = st.query_params
        auth_code = query_params.get('code')
        
        if auth_code:
            # Handle OAuth callback
            if 'oauth_flow' in st.session_state:
                success, user_email = extractor.authenticate_with_code(auth_code, st.session_state.oauth_flow)
                if success:
                    st.success(f"✅ Successfully authenticated as {user_email}")
                    st.rerun()
                else:
                    st.error("Authentication failed. Please try again.")
                    if 'oauth_flow' in st.session_state:
                        del st.session_state.oauth_flow
            else:
                st.error("OAuth flow not found. Please restart authentication.")
        
        # Try to authenticate from existing session
        if not st.session_state.authenticated:
            success, user_email = extractor.authenticate_from_session()
            if success:
                st.session_state.authenticated = True
                st.session_state.user_email = user_email
                st.rerun()
        
        # Show authentication button if not authenticated
        if not st.session_state.authenticated:
            if st.button("🔑 Authenticate with Gmail", type="primary"):
                auth_url, flow = extractor.get_oauth_url()
                if auth_url and flow:
                    st.session_state.oauth_flow = flow
                    st.markdown(f"**Please click the link below to authenticate:**")
                    st.markdown(f"[🔗 Authenticate with Gmail]({auth_url})")
                    st.info("After authentication, you'll be redirected back to this app.")
                else:
                    st.error("Failed to create authentication URL. Please check your configuration.")
            st.stop()
    
    # Main application interface (authenticated users)
    st.sidebar.header("📊 Controls")
    
    # User info
    if st.session_state.user_email:
        st.sidebar.success(f"✅ Logged in as: {st.session_state.user_email}")
    
    # Logout button
    if st.sidebar.button("🚪 Logout"):
        st.session_state.authenticated = False
        st.session_state.user_email = None
        st.session_state.credentials = None
        if 'oauth_flow' in st.session_state:
            del st.session_state.oauth_flow
        st.rerun()
    
    # Email processing controls
    st.sidebar.subheader("📧 Email Processing")
    max_emails = st.sidebar.slider("Maximum emails to process", 10, 200, 50, 10)
    
    # Date filter
    st.sidebar.subheader("📅 Date Filter")
    enable_date_filter = st.sidebar.checkbox("Enable date filter", key="date_filter_enabled")
    
    if enable_date_filter:
        col1, col2 = st.sidebar.columns(2)
        with col1:
            start_date = st.date_input(
                "Start date",
                value=datetime.now() - timedelta(days=30),
                key="date_filter_start"
            )
        with col2:
            end_date = st.date_input(
                "End date",
                value=datetime.now(),
                key="date_filter_end"
            )
    
    # Process emails button
    if st.sidebar.button("🔍 Analyze Transactions", type="primary"):
        with st.spinner("Processing emails..."):
            progress_bar = st.progress(0)
            status_text = st.empty()
            
            def update_progress(current, total):
                progress = current / total
                progress_bar.progress(progress)
                status_text.text(f"Processing email {current} of {total}...")
            
            # Process emails
            results = extractor.process_emails(max_emails, update_progress)
            
            if results:
                # Convert to DataFrame
                df = pd.DataFrame(results)
                
                # Parse dates
                df['date_parsed'] = pd.to_datetime(df['date'], errors='coerce')
                
                # Apply date filter if enabled
                df_filtered = apply_date_filter(df)
                
                # Store in session state
                st.session_state.transaction_data = df_filtered
                
                status_text.text("✅ Processing complete!")
                progress_bar.empty()
                
                st.success(f"Processed {len(df_filtered)} transactions!")
            else:
                st.error("No emails found or processing failed.")
    
    # Display results if available
    if 'transaction_data' in st.session_state and not st.session_state.transaction_data.empty:
        df = st.session_state.transaction_data
        
        # Summary metrics
        st.subheader("📊 Transaction Summary")
        
        # Calculate metrics
        total_transactions = len(df)
        transactions_with_amounts = df['amount'].notna().sum()
        
        # Convert amounts to numeric for calculations
        df_numeric = df.copy()
        df_numeric['amount_numeric'] = pd.to_numeric(
            df_numeric['amount'].str.replace(',', ''), 
            errors='coerce'
        )
        
        total_amount = df_numeric['amount_numeric'].sum()
        avg_amount = df_numeric['amount_numeric'].mean()
        
        # Display metrics
        col1, col2, col3, col4 = st.columns(4)
        
        with col1:
            st.metric("Total Transactions", total_transactions)
        
        with col2:
            st.metric("With Amounts", transactions_with_amounts)
        
        with col3:
            st.metric("Total Amount", f"₹{total_amount:,.2f}" if not pd.isna(total_amount) else "N/A")
        
        with col4:
            st.metric("Average Amount", f"₹{avg_amount:,.2f}" if not pd.isna(avg_amount) else "N/A")
        
        # Category breakdown
        if extractor.categorizer:
            st.subheader("📈 Category Breakdown")
            category_summary = df.groupby('category').agg({
                'amount_numeric': ['count', 'sum', 'mean']
            }).round(2)
            
            category_summary.columns = ['Count', 'Total Amount', 'Average Amount']
            category_summary = category_summary.sort_values('Total Amount', ascending=False)
            
            # Add color coding
            st.dataframe(
                category_summary,
                use_container_width=True,
                column_config={
                    "Total Amount": st.column_config.NumberColumn(
                        "Total Amount",
                        help="Total amount spent in this category",
                        format="₹%.2f"
                    ),
                    "Average Amount": st.column_config.NumberColumn(
                        "Average Amount",
                        help="Average amount per transaction",
                        format="₹%.2f"
                    )
                }
            )
        
        # Visualizations
        if extractor.categorizer:
            st.subheader("📊 Visualizations")
            create_visualizations(df, extractor.categorizer)
        
        # Detailed transaction table
        st.subheader("📋 Transaction Details")
        
        # Category filter
        if extractor.categorizer:
            categories = ['All'] + extractor.categorizer.get_all_categories()
            selected_category = st.selectbox("Filter by category:", categories)
            
            if selected_category != 'All':
                df_display = df[df['category'] == selected_category]
            else:
                df_display = df
        else:
            df_display = df
        
        # Display options
        col1, col2 = st.columns(2)
        with col1:
            show_email_preview = st.checkbox("Show email preview", value=False)
        with col2:
            show_all_columns = st.checkbox("Show all columns", value=False)
        
        # Prepare display DataFrame
        if show_all_columns:
            display_cols = df_display.columns.tolist()
        else:
            display_cols = ['date', 'subject', 'amount', 'category']
            if show_email_preview:
                display_cols.append('email_body_preview')
        
        # Format the display
        df_display_formatted = df_display[display_cols].copy()
        
        # Format date column
        if 'date_parsed' in df_display_formatted.columns:
            df_display_formatted['date'] = df_display_formatted['date_parsed'].dt.strftime('%Y-%m-%d %H:%M')
        
        st.dataframe(
            df_display_formatted,
            use_container_width=True,
            column_config={
                "amount": st.column_config.TextColumn(
                    "Amount (₹)",
                    help="Transaction amount"
                ),
                "category": st.column_config.TextColumn(
                    "Category",
                    help="AI-categorized transaction type"
                ),
                "date": st.column_config.TextColumn(
                    "Date",
                    help="Transaction date"
                )
            }
        )
        
        # Export options
        st.subheader("💾 Export Data")
        
        col1, col2 = st.columns(2)
        
        with col1:
            # CSV export
            csv_data = df_display.to_csv(index=False)
            st.download_button(
                label="📄 Download as CSV",
                data=csv_data,
                file_name=f"sbi_transactions_{datetime.now().strftime('%Y%m%d_%H%M%S')}.csv",
                mime="text/csv"
            )
        
        with col2:
            # JSON export
            json_data = df_display.to_json(orient='records', date_format='iso')
            st.download_button(
                label="📄 Download as JSON",
                data=json_data,
                file_name=f"sbi_transactions_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json",
                mime="application/json"
            )
    
    # Footer
    st.markdown("---")
    st.markdown(
        """
        <div style='text-align: center; color: #666; font-size: 0.8em;'>
        Made with ❤️ using Streamlit | Powered by AI | 
        <a href='https://github.com' target='_blank'>View Source</a>
        </div>
        """,
        unsafe_allow_html=True
    )

if __name__ == "__main__":
    main()
