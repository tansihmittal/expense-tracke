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
                'REPLICATE_API_TOKEN': st.secrets.get('REPLICATE_API_TOKEN', os.getenv('REPLICATE_API_TOKEN'))
            }
        except Exception:
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
        if not self.validate_config():
            st.sidebar.subheader("⚠️ Configuration Issues")
            
            for error in self.validation_errors:
                st.sidebar.error(error)
            
            with st.sidebar.expander("Setup Instructions"):
                st.write("""
                **For Streamlit Cloud:**
                Add these secrets in your Streamlit Cloud app settings:
                - `GMAIL_CLIENT_ID`
                - `GMAIL_CLIENT_SECRET` 
                - `REPLICATE_API_TOKEN`
                
                **For local development:**
                Create a `.streamlit/secrets.toml` file:
                ```toml
                GMAIL_CLIENT_ID = "your_client_id_here"
                GMAIL_CLIENT_SECRET = "your_client_secret_here"
                REPLICATE_API_TOKEN = "your_replicate_token_here"
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
            url = "https://api.replicate.com/v1/models/openai/gpt-4o-mini/predictions"
            
            headers = {
                "Authorization": f"Bearer {self.replicate_token}",
                "Content-Type": "application/json"
            }
            
            transaction_text = f"Subject: {subject}\nBody: {body}\nAmount: {amount}"
            categories_list = ", ".join([cat for cat in self.categories.keys() if cat != 'Other'])
            
            prompt = f"""
            You are a financial transaction categorization expert. Analyze the transaction below and assign it to exactly ONE category from this list:

            {categories_list}

            ## Transaction Analysis Guidelines:
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

            Return only the category name. No explanation.
            """
            
            data = {
                "input": {
                    "prompt": prompt,
                    "system_prompt": "You are an expert financial transaction categorizer. Return exactly one category name from the provided list."
                }
            }
            
            response = requests.post(url, headers=headers, json=data)
            
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
            st.warning(f"AI categorization failed, using fallback: {e}")
            return self.fallback_categorization(subject, body, amount)
    
    def poll_prediction(self, prediction_id: str, max_attempts: int = 30) -> Optional[str]:
        """Poll Replicate API for prediction completion"""
        import time
        
        url = f"https://api.replicate.com/v1/predictions/{prediction_id}"
        headers = {"Authorization": f"Bearer {self.replicate_token}"}
        
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
            
            if not client_id or not client_secret:
                st.error("Gmail credentials not configured")
                return None
            
            # For Streamlit Cloud, we need to use the app URL as redirect URI
            redirect_uri = st.secrets.get("REDIRECT_URI", "https://sbi-track.streamlit.app/")
            
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
            
            auth_url, _ = flow.authorization_url(prompt='consent')
            return auth_url, flow
            
        except Exception as e:
            st.error(f"Error creating OAuth URL: {e}")
            return None, None
    
    def authenticate_with_code(self, auth_code: str, flow: Flow):
        """Authenticate using authorization code"""
        try:
            flow.fetch_token(code=auth_code)
            credentials = flow.credentials
            
            # Store credentials in session state (not in files for cloud deployment)
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
                    "system_prompt": "You are an expert at extracting financial amounts from SBI bank transaction alert emails. Return only the numeric value with decimal places."
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
            return None
    
    def poll_prediction(self, prediction_id: str, max_attempts: int = 30) -> Optional[str]:
        """Poll Replicate API for prediction completion"""
        import time
        
        replicate_token = self.config_manager.get_config_value('REPLICATE_API_TOKEN')
        url = f"https://api.replicate.com/v1/predictions/{prediction_id}"
        headers = {"Authorization": f"Bearer {replicate_token}"}
        
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
        query_params = st.experimental_get_query_params()
        auth_code = query_params.get('code', [None])[0]
        
        if auth_code:
            # Handle OAuth callback
            if 'oauth_flow' in st.session_state:
                success, user_email = extractor.authenticate_with_code(auth_code, st.session_state.oauth_flow)
                if success:
                    st.success(f"✅ Authenticated as: {user_email}")
                    st.experimental_rerun()
                else:
                    st.error("❌ Authentication failed")
            else:
                st.error("OAuth flow not found. Please try again.")
        else:
            # Try to authenticate from session first
            success, user_email = extractor.authenticate_from_session()
            
            if success:
                st.session_state.authenticated = True
                st.session_state.user_email = user_email
                st.success(f"✅ Authenticated as: {user_email}")
                st.experimental_rerun()
            else:
                # Show authentication button
                if st.button("🔗 Connect to Gmail", type="primary"):
                    auth_url, flow = extractor.get_oauth_url()
                    if auth_url and flow:
                        st.session_state.oauth_flow = flow
                        st.markdown(f"[Click here to authenticate with Gmail]({auth_url})")
                        st.info("After authentication, you'll be redirected back to this app.")
                    else:
                        st.error("Failed to create authentication URL")
    
    else:
        # User is authenticated
        st.sidebar.success(f"✅ Authenticated as: {st.session_state.user_email}")
        
        if st.sidebar.button("🚪 Logout"):
            st.session_state.authenticated = False
            st.session_state.user_email = None
            st.session_state.credentials = None
            if 'oauth_flow' in st.session_state:
                del st.session_state.oauth_flow
            st.experimental_rerun()
        
        # Main application interface
        st.sidebar.header("📊 Analysis Options")
        
        # Email limit selection
        max_emails = st.sidebar.slider(
            "Number of emails to analyze",
            min_value=10,
            max_value=200,
            value=50,
            step=10,
            help="Higher numbers will take longer to process"
        )
        
        # Date filter options
        st.sidebar.subheader("📅 Date Filter")
        enable_date_filter = st.sidebar.checkbox("Enable date filter")
        
        if enable_date_filter:
            col1, col2 = st.sidebar.columns(2)
            with col1:
                start_date = st.date_input(
                    "From",
                    value=datetime.now() - timedelta(days=30),
                    key="date_filter_start"
                )
            with col2:
                end_date = st.date_input(
                    "To",
                    value=datetime.now(),
                    key="date_filter_end"
                )
            
            st.session_state.date_filter_enabled = True
            st.session_state.date_filter_start = start_date
            st.session_state.date_filter_end = end_date
        else:
            st.session_state.date_filter_enabled = False
        
        # Process emails button
        if st.button("🔍 Analyze SBI Transactions", type="primary"):
            with st.spinner("Processing emails... This may take a few minutes."):
                # Progress bar
                progress_bar = st.progress(0)
                status_text = st.empty()
                
                def update_progress(current, total):
                    progress = current / total
                    progress_bar.progress(progress)
                    status_text.text(f"Processing email {current} of {total}")
                
                # Process emails
                results = extractor.process_emails(
                    max_emails=max_emails,
                    progress_callback=update_progress
                )
                
                # Clear progress indicators
                progress_bar.empty()
                status_text.empty()
                
                if results:
                    st.success(f"✅ Processed {len(results)} emails successfully!")
                    
                    # Convert to DataFrame
                    df = pd.DataFrame(results)
                    
                    # Parse dates for filtering
                    df['date_parsed'] = pd.to_datetime(df['date'], errors='coerce')
                    
                    # Apply date filter if enabled
                    df = apply_date_filter(df)
                    
                    if df.empty:
                        st.warning("No transactions found in the selected date range.")
                        st.stop()
                    
                    # Store results in session state
                    st.session_state.transaction_data = df
                    
                    # Display summary statistics
                    col1, col2, col3, col4 = st.columns(4)
                    
                    with col1:
                        st.metric("Total Transactions", len(df))
                    
                    with col2:
                        valid_amounts = df[df['amount'].notna()]
                        if not valid_amounts.empty:
                            total_amount = pd.to_numeric(
                                valid_amounts['amount'].str.replace(',', ''), 
                                errors='coerce'
                            ).sum()
                            st.metric("Total Amount", f"₹{total_amount:,.2f}")
                        else:
                            st.metric("Total Amount", "N/A")
                    
                    with col3:
                        unique_categories = df['category'].nunique()
                        st.metric("Categories", unique_categories)
                    
                    with col4:
                        if not df.empty and 'date_parsed' in df.columns:
                            date_range = (df['date_parsed'].max() - df['date_parsed'].min()).days + 1
                            st.metric("Date Range", f"{date_range} days")
                        else:
                            st.metric("Date Range", "N/A")
                    
                    # Tabs for different views
                    tab1, tab2, tab3, tab4 = st.tabs(["📊 Visualizations", "📋 Transaction Details", "🔍 Search & Filter", "📈 Advanced Analytics"])
                    
                    with tab1:
                        create_visualizations(df, extractor.categorizer)
                    
                    with tab2:
                        st.subheader("📋 Transaction Details")
                        
                        # Display options
                        col1, col2 = st.columns(2)
                        with col1:
                            show_email_preview = st.checkbox("Show email preview", value=False)
                        with col2:
                            show_debug_info = st.checkbox("Show extraction details", value=False)
                        
                        # Prepare display dataframe
                        display_df = df.copy()
                        
                        # Format columns for display
                        display_columns = ['date', 'subject', 'amount', 'category']
                        if show_email_preview:
                            display_columns.append('email_body_preview')
                        if show_debug_info:
                            display_columns.extend(['ai_extracted_amount', 'regex_extracted_amounts'])
                        
                        # Rename columns for better display
                        column_mapping = {
                            'date': 'Date',
                            'subject': 'Subject',
                            'amount': 'Amount (₹)',
                            'category': 'Category',
                            'email_body_preview': 'Email Preview',
                            'ai_extracted_amount': 'AI Amount',
                            'regex_extracted_amounts': 'Regex Amounts'
                        }
                        
                        display_df = display_df[display_columns].rename(columns=column_mapping)
                        
                        # Style the dataframe
                        if extractor.categorizer:
                            def style_category(val):
                                color = extractor.categorizer.get_category_color(val)
                                return f'background-color: {color}; color: white; font-weight: bold;'
                            
                            if 'Category' in display_df.columns:
                                styled_df = display_df.style.applymap(
                                    style_category, 
                                    subset=['Category']
                                )
                                st.dataframe(styled_df, use_container_width=True)
                            else:
                                st.dataframe(display_df, use_container_width=True)
                        else:
                            st.dataframe(display_df, use_container_width=True)
                        
                        # Download button
                        csv = df.to_csv(index=False)
                        st.download_button(
                            label="📥 Download CSV",
                            data=csv,
                            file_name=f"sbi_transactions_{datetime.now().strftime('%Y%m%d_%H%M%S')}.csv",
                            mime="text/csv"
                        )
                    
                    with tab3:
                        st.subheader("🔍 Search & Filter Transactions")
                        
                        col1, col2 = st.columns(2)
                        
                        with col1:
                            # Search functionality
                            search_term = st.text_input("🔍 Search in subject/email content", "")
                            
                            # Category filter
                            if extractor.categorizer:
                                available_categories = df['category'].unique().tolist()
                                selected_categories = st.multiselect(
                                    "Filter by categories",
                                    options=available_categories,
                                    default=available_categories
                                )
                            else:
                                selected_categories = df['category'].unique().tolist()
                        
                        with col2:
                            # Amount range filter
                            valid_amounts = pd.to_numeric(
                                df[df['amount'].notna()]['amount'].str.replace(',', ''), 
                                errors='coerce'
                            ).dropna()
                            
                            if not valid_amounts.empty:
                                min_amount = float(valid_amounts.min())
                                max_amount = float(valid_amounts.max())
                                
                                amount_range = st.slider(
                                    "Amount range (₹)",
                                    min_value=min_amount,
                                    max_value=max_amount,
                                    value=(min_amount, max_amount),
                                    step=1.0
                                )
                            else:
                                amount_range = (0, 0)
                        
                        # Apply filters
                        filtered_df = df.copy()
                        
                        # Apply search filter
                        if search_term:
                            search_mask = (
                                filtered_df['subject'].str.contains(search_term, case=False, na=False) |
                                filtered_df['email_body_preview'].str.contains(search_term, case=False, na=False)
                            )
                            filtered_df = filtered_df[search_mask]
                        
                        # Apply category filter
                        if selected_categories:
                            filtered_df = filtered_df[filtered_df['category'].isin(selected_categories)]
                        
                        # Apply amount filter
                        if not valid_amounts.empty and amount_range != (0, 0):
                            filtered_df['amount_numeric'] = pd.to_numeric(
                                filtered_df['amount'].str.replace(',', ''), 
                                errors='coerce'
                            )
                            amount_mask = (
                                (filtered_df['amount_numeric'] >= amount_range[0]) & 
                                (filtered_df['amount_numeric'] <= amount_range[1])
                            )
                            filtered_df = filtered_df[amount_mask]
                        
                        st.write(f"**Found {len(filtered_df)} transactions matching your criteria**")
                        
                        if not filtered_df.empty:
                            # Display filtered results
                            display_columns = ['date', 'subject', 'amount', 'category', 'email_body_preview']
                            display_df = filtered_df[display_columns].rename(columns={
                                'date': 'Date',
                                'subject': 'Subject', 
                                'amount': 'Amount (₹)',
                                'category': 'Category',
                                'email_body_preview': 'Email Preview'
                            })
                            
                            st.dataframe(display_df, use_container_width=True)
                    
                    with tab4:
                        st.subheader("📈 Advanced Analytics")
                        
                        # Convert amounts to numeric for analysis
                        df_analysis = df.copy()
                        df_analysis['amount_numeric'] = pd.to_numeric(
                            df_analysis['amount'].str.replace(',', ''), 
                            errors='coerce'
                        )
                        df_analysis = df_analysis.dropna(subset=['amount_numeric'])
                        
                        if not df_analysis.empty:
                            col1, col2 = st.columns(2)
                            
                            with col1:
                                st.subheader("💰 Spending Statistics")
                                stats_df = pd.DataFrame({
                                    'Metric': ['Mean', 'Median', 'Std Dev', 'Min', 'Max'],
                                    'Amount (₹)': [
                                        f"{df_analysis['amount_numeric'].mean():.2f}",
                                        f"{df_analysis['amount_numeric'].median():.2f}",
                                        f"{df_analysis['amount_numeric'].std():.2f}",
                                        f"{df_analysis['amount_numeric'].min():.2f}",
                                        f"{df_analysis['amount_numeric'].max():.2f}"
                                    ]
                                })
                                st.dataframe(stats_df, use_container_width=True)
                                
                                # Top spending days
                                if 'date_parsed' in df_analysis.columns:
                                    st.subheader("📅 Top Spending Days")
                                    daily_spending = df_analysis.groupby(
                                        df_analysis['date_parsed'].dt.date
                                    )['amount_numeric'].sum().sort_values(ascending=False).head(10)
                                    
                                    top_days_df = pd.DataFrame({
                                        'Date': daily_spending.index,
                                        'Total Amount (₹)': [f"{amt:.2f}" for amt in daily_spending.values]
                                    })
                                    st.dataframe(top_days_df, use_container_width=True)
                            
                            with col2:
                                # Category insights
                                st.subheader("🏷️ Category Insights")
                                category_stats = df_analysis.groupby('category')['amount_numeric'].agg([
                                    'count', 'sum', 'mean', 'std'
                                ]).round(2)
                                category_stats.columns = ['Count', 'Total', 'Average', 'Std Dev']
                                category_stats = category_stats.sort_values('Total', ascending=False)
                                st.dataframe(category_stats, use_container_width=True)
                                
                                # Frequency analysis
                                st.subheader("📊 Transaction Frequency")
                                if 'date_parsed' in df_analysis.columns:
                                    df_analysis['day_of_week'] = df_analysis['date_parsed'].dt.day_name()
                                    day_counts = df_analysis['day_of_week'].value_counts()
                                    
                                    freq_df = pd.DataFrame({
                                        'Day': day_counts.index,
                                        'Transactions': day_counts.values
                                    })
                                    st.dataframe(freq_df, use_container_width=True)
                        else:
                            st.warning("No valid transaction data available for advanced analytics.")
                
                else:
                    st.error("❌ No SBI transaction emails found. Please check:")
                    st.markdown("""
                    - Make sure you have SBI transaction alert emails in your Gmail
                    - Check if the emails are from: `donotreply.sbiatm@alerts.sbi.co.in`
                    - Try increasing the number of emails to analyze
                    """)
        
        # Show cached data if available
        if 'transaction_data' in st.session_state and not st.session_state.transaction_data.empty:
            st.info("💡 Previous analysis results are still available. Click 'Analyze SBI Transactions' to refresh.")

if __name__ == "__main__":
    main()
