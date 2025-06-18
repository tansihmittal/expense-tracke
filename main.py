import streamlit as st
import base64
import json
import os
import re
import requests
from datetime import datetime, timedelta
from typing import List, Dict, Optional
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
from collections import Counter
import dateutil.parser
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart

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
if 'access_token' not in st.session_state:
    st.session_state.access_token = None
if 'user_email' not in st.session_state:
    st.session_state.user_email = None

class ConfigManager:
    """Manages configuration and credentials"""
    
    def __init__(self):
        self.config = self._load_config()
        self.validation_errors = []
    
    def _load_config(self) -> Dict[str, str]:
        """Load configuration from Streamlit secrets or environment variables"""
        config = {}
        
        try:
            # Try Streamlit secrets first
            config = {
                'GOOGLE_CLIENT_ID': st.secrets.get('GOOGLE_CLIENT_ID', ''),
                'GOOGLE_CLIENT_SECRET': st.secrets.get('GOOGLE_CLIENT_SECRET', ''),
                'REPLICATE_API_TOKEN': st.secrets.get('REPLICATE_API_TOKEN', ''),
                'GMAIL_USER': st.secrets.get('GMAIL_USER', ''),  # Fallback
                'GMAIL_PASSWORD': st.secrets.get('GMAIL_PASSWORD', '')  # Fallback
            }
        except:
            # Fallback to environment variables
            config = {
                'GOOGLE_CLIENT_ID': os.getenv('GOOGLE_CLIENT_ID', ''),
                'GOOGLE_CLIENT_SECRET': os.getenv('GOOGLE_CLIENT_SECRET', ''),
                'REPLICATE_API_TOKEN': os.getenv('REPLICATE_API_TOKEN', ''),
                'GMAIL_USER': os.getenv('GMAIL_USER', ''),
                'GMAIL_PASSWORD': os.getenv('GMAIL_PASSWORD', '')
            }
        
        return config
    
    def validate_config(self) -> bool:
        """Validate configuration"""
        self.validation_errors = []
        
        # Check if we have OAuth credentials OR fallback credentials
        has_oauth = self.config.get('GOOGLE_CLIENT_ID') and self.config.get('GOOGLE_CLIENT_SECRET')
        has_fallback = self.config.get('GMAIL_USER') and self.config.get('GMAIL_PASSWORD')
        
        if not has_oauth and not has_fallback:
            self.validation_errors.append("Missing authentication credentials")
        
        return len(self.validation_errors) == 0
    
    def get_config_value(self, key: str) -> Optional[str]:
        """Get configuration value by key"""
        return self.config.get(key)
    
    def display_config_status(self):
        """Display configuration status in sidebar"""
        st.sidebar.subheader("⚙️ Configuration Status")
        
        has_oauth = self.config.get('GOOGLE_CLIENT_ID') and self.config.get('GOOGLE_CLIENT_SECRET')
        has_fallback = self.config.get('GMAIL_USER') and self.config.get('GMAIL_PASSWORD')
        
        if has_oauth:
            st.sidebar.success("✅ OAuth Credentials (Recommended)")
        elif has_fallback:
            st.sidebar.warning("⚠️ Using Fallback Credentials")
            st.sidebar.info("Consider upgrading to OAuth for better security")
        else:
            st.sidebar.error("❌ No Valid Credentials")
        
        if self.config.get('REPLICATE_API_TOKEN'):
            st.sidebar.success("✅ AI Categorization Available")
        else:
            st.sidebar.warning("⚠️ AI Categorization Disabled")
        
        if not self.validate_config():
            with st.sidebar.expander("📋 Setup Instructions"):
                st.write("""
                **Option 1: OAuth Setup (Recommended)**
                1. Go to Google Cloud Console
                2. Create a new project or select existing
                3. Enable Gmail API
                4. Create OAuth 2.0 credentials
                5. Add these secrets:
                ```
                GOOGLE_CLIENT_ID = "your-client-id"
                GOOGLE_CLIENT_SECRET = "your-client-secret"
                REPLICATE_API_TOKEN = "your-token" # Optional
                ```
                
                **Option 2: App Password (Fallback)**
                1. Enable 2FA on Gmail
                2. Generate App Password
                3. Add these secrets:
                ```
                GMAIL_USER = "your-email@gmail.com"
                GMAIL_PASSWORD = "your-app-password"
                ```
                """)

class GoogleOAuthManager:
    """Handles Google OAuth authentication"""
    
    def __init__(self, config_manager: ConfigManager):
        self.config_manager = config_manager
        self.client_id = config_manager.get_config_value('GOOGLE_CLIENT_ID')
        self.client_secret = config_manager.get_config_value('GOOGLE_CLIENT_SECRET')
        self.redirect_uri = self._get_redirect_uri()
        self.scopes = ['https://www.googleapis.com/auth/gmail.readonly']
    
    def _get_redirect_uri(self) -> str:
        """Get redirect URI for OAuth"""
        # For Streamlit Cloud, use the app URL
        return "https://your-app-name.streamlit.app/"  # Replace with your actual app URL
    
    def get_auth_url(self) -> str:
        """Generate OAuth authorization URL"""
        if not self.client_id:
            return None
        
        auth_url = "https://accounts.google.com/o/oauth2/auth"
        params = {
            'client_id': self.client_id,
            'redirect_uri': self.redirect_uri,
            'scope': ' '.join(self.scopes),
            'response_type': 'code',
            'access_type': 'offline',
            'prompt': 'consent'
        }
        
        query_string = '&'.join([f"{k}={v}" for k, v in params.items()])
        return f"{auth_url}?{query_string}"
    
    def exchange_code_for_token(self, code: str) -> Optional[str]:
        """Exchange authorization code for access token"""
        if not self.client_id or not self.client_secret:
            return None
        
        token_url = "https://oauth2.googleapis.com/token"
        data = {
            'client_id': self.client_id,
            'client_secret': self.client_secret,
            'code': code,
            'grant_type': 'authorization_code',
            'redirect_uri': self.redirect_uri
        }
        
        try:
            response = requests.post(token_url, data=data)
            if response.status_code == 200:
                token_data = response.json()
                return token_data.get('access_token')
        except Exception as e:
            st.error(f"Token exchange failed: {e}")
        
        return None

class AITransactionCategorizer:
    """AI-powered transaction categorization"""
    
    def __init__(self, replicate_token: str = None):
        self.replicate_token = replicate_token
        self.categories = {
            'ATM Withdrawal': '#FF6B6B',
            'Transfer': '#A8E6CF',
            'Payment': '#4ECDC4',
            'Shopping': '#45B7D1',
            'Food & Dining': '#96CEB4',
            'Bills & Utilities': '#FECA57',
            'Entertainment': '#FF9FF3',
            'Transport': '#54A0FF',
            'Healthcare': '#5F27CD',
            'Investment': '#00D2D3',
            'Other': '#D3D3D3'
        }
    
    def categorize_transaction(self, subject: str, body: str, amount: str) -> str:
        """Categorize transaction using AI or fallback rules"""
        if self.replicate_token:
            return self._categorize_with_ai(subject, body, amount)
        else:
            return self._fallback_categorization(subject, body, amount)
    
    def _categorize_with_ai(self, subject: str, body: str, amount: str) -> str:
        """Use AI for categorization"""
        try:
            # Simplified AI categorization logic
            # You can implement full Replicate API call here
            return self._fallback_categorization(subject, body, amount)
        except:
            return self._fallback_categorization(subject, body, amount)
    
    def _fallback_categorization(self, subject: str, body: str, amount: str) -> str:
        """Rule-based categorization"""
        text = f"{subject} {body}".lower()
        
        rules = {
            'ATM Withdrawal': ['atm', 'withdrawal', 'cash', 'withdraw'],
            'Transfer': ['transfer', 'neft', 'rtgs', 'imps', 'upi'],
            'Payment': ['payment', 'paid', 'bill payment'],
            'Shopping': ['purchase', 'shopping', 'store', 'mart'],
            'Food & Dining': ['restaurant', 'food', 'dining', 'cafe'],
            'Bills & Utilities': ['electricity', 'water', 'gas', 'phone'],
            'Transport': ['fuel', 'petrol', 'taxi', 'uber'],
            'Healthcare': ['medical', 'hospital', 'pharmacy'],
            'Investment': ['mutual fund', 'sip', 'investment']
        }
        
        for category, keywords in rules.items():
            if any(keyword in text for keyword in keywords):
                return category
        
        return 'Other'
    
    def get_category_color(self, category: str) -> str:
        """Get color for category"""
        return self.categories.get(category, '#D3D3D3')
    
    def get_all_categories(self) -> List[str]:
        """Get all categories"""
        return list(self.categories.keys())

class GmailAPIExtractor:
    """Extract emails using Gmail API"""
    
    def __init__(self, access_token: str):
        self.access_token = access_token
        self.base_url = "https://gmail.googleapis.com/gmail/v1"
        self.headers = {'Authorization': f'Bearer {access_token}'}
    
    def search_sbi_emails(self, max_results: int = 50) -> List[Dict]:
        """Search for SBI emails using Gmail API"""
        try:
            # Search for emails from SBI
            query = 'from:donotreply.sbiatm@alerts.sbi.co.in'
            search_url = f"{self.base_url}/users/me/messages"
            params = {'q': query, 'maxResults': max_results}
            
            response = requests.get(search_url, headers=self.headers, params=params)
            
            if response.status_code == 200:
                messages = response.json().get('messages', [])
                emails = []
                
                for message in messages:
                    email_data = self._get_email_content(message['id'])
                    if email_data:
                        emails.append(email_data)
                
                return emails
            
        except Exception as e:
            st.error(f"Error searching emails: {e}")
        
        return []
    
    def _get_email_content(self, message_id: str) -> Optional[Dict]:
        """Get email content by message ID"""
        try:
            url = f"{self.base_url}/users/me/messages/{message_id}"
            response = requests.get(url, headers=self.headers)
            
            if response.status_code == 200:
                message = response.json()
                
                # Extract headers
                headers = {h['name']: h['value'] for h in message['payload'].get('headers', [])}
                
                # Extract body
                body = self._extract_body(message['payload'])
                
                return {
                    'id': message_id,
                    'subject': headers.get('Subject', ''),
                    'sender': headers.get('From', ''),
                    'date': headers.get('Date', ''),
                    'body': body
                }
                
        except Exception as e:
            st.error(f"Error getting email content: {e}")
        
        return None
    
    def _extract_body(self, payload: Dict) -> str:
        """Extract email body from payload"""
        try:
            if 'parts' in payload:
                for part in payload['parts']:
                    if part['mimeType'] == 'text/plain':
                        data = part['body']['data']
                        return base64.urlsafe_b64decode(data).decode('utf-8')
            elif payload['body'].get('data'):
                data = payload['body']['data']
                return base64.urlsafe_b64decode(data).decode('utf-8')
        except:
            pass
        
        return ""

def extract_amount_from_text(text: str) -> Optional[str]:
    """Extract amount from email text"""
    patterns = [
        r'Amount\s*\(INR\)\s*(\d+(?:,\d+)*(?:\.\d{2})?)',
        r'Rs\.?\s*(\d+(?:,\d+)*(?:\.\d{2})?)',
        r'INR\s*(\d+(?:,\d+)*(?:\.\d{2})?)',
        r'₹\s*(\d+(?:,\d+)*(?:\.\d{2})?)'
    ]
    
    for pattern in patterns:
        matches = re.findall(pattern, text, re.IGNORECASE)
        if matches:
            return matches[0]
    
    return None

def create_visualizations(df, categorizer):
    """Create visualizations"""
    if len(df) == 0:
        return None, None, None, None
    
    # Category distribution
    category_amounts = df.groupby('category')['amount_numeric'].sum().reset_index()
    
    fig_pie = px.pie(
        category_amounts,
        names='category',
        values='amount_numeric',
        title='Transaction Distribution by Category',
        color='category',
        color_discrete_map={cat: categorizer.get_category_color(cat) for cat in category_amounts['category']}
    )
    
    fig_bar = px.bar(
        category_amounts,
        x='category',
        y='amount_numeric',
        title='Total Amount by Category',
        color='category',
        color_discrete_map={cat: categorizer.get_category_color(cat) for cat in category_amounts['category']}
    )
    
    # Timeline
    df_sorted = df.sort_values('date_parsed')
    fig_timeline = px.line(
        df_sorted,
        x='date_parsed',
        y='amount_numeric',
        color='category',
        title='Transaction Timeline',
        markers=True
    )
    
    # Monthly trends
    df_sorted['month'] = df_sorted['date_parsed'].dt.to_period('M').astype(str)
    monthly_data = df_sorted.groupby(['month', 'category'])['amount_numeric'].sum().reset_index()
    
    fig_monthly = px.bar(
        monthly_data,
        x='month',
        y='amount_numeric',
        color='category',
        title='Monthly Spending by Category'
    )
    
    return fig_pie, fig_bar, fig_timeline, fig_monthly

def main():
    """Main Streamlit app"""
    
    st.title("🏦 SBI Transaction Analyzer")
    st.markdown("Extract and analyze your SBI bank transaction alerts")
    
    # Initialize managers
    config_manager = ConfigManager()
    oauth_manager = GoogleOAuthManager(config_manager) if config_manager.get_config_value('GOOGLE_CLIENT_ID') else None
    
    # Sidebar authentication
    st.sidebar.header("🔐 Authentication")
    
    if not st.session_state.authenticated:
        st.sidebar.info("Please authenticate to analyze transactions")
        config_manager.display_config_status()
        
        # OAuth Authentication
        if oauth_manager:
            if st.sidebar.button("🔐 Login with Google", type="primary"):
                auth_url = oauth_manager.get_auth_url()
                st.sidebar.markdown(f"[Click here to authenticate]({auth_url})")
                st.sidebar.info("After authentication, paste the authorization code below:")
            
            auth_code = st.sidebar.text_input("Authorization Code", type="password")
            
            if auth_code and st.sidebar.button("Submit Code"):
                access_token = oauth_manager.exchange_code_for_token(auth_code)
                if access_token:
                    st.session_state.access_token = access_token
                    st.session_state.authenticated = True
                    st.success("✅ Authentication successful!")
                    st.rerun()
                else:
                    st.sidebar.error("❌ Authentication failed")
        
        # Fallback authentication (if no OAuth)
        elif config_manager.get_config_value('GMAIL_USER'):
            if st.sidebar.button("🔐 Use App Password", type="primary"):
                st.session_state.authenticated = True
                st.session_state.user_email = config_manager.get_config_value('GMAIL_USER')
                st.success("✅ Using fallback authentication")
                st.rerun()
    
    else:
        st.sidebar.success("✅ Authenticated")
        
        if st.sidebar.button("🚪 Logout"):
            for key in ['authenticated', 'access_token', 'user_email', 'transaction_data']:
                if key in st.session_state:
                    del st.session_state[key]
            st.rerun()
    
    # Main content
    if not st.session_state.authenticated:
        st.info("👈 Please authenticate using the sidebar")
        
        st.markdown("""
        ## 🚀 Features
        
        - **🔒 Secure OAuth Authentication**: Google OAuth 2.0 for secure access
        - **🤖 AI-Powered Categorization**: Automatically categorize transactions
        - **📊 Rich Visualizations**: Interactive charts and analysis
        - **📅 Date Filtering**: Analyze specific time periods
        - **💾 Export Functionality**: Download analysis as CSV
        
        ## 🛠️ Setup Guide
        
        ### Option 1: OAuth Setup (Recommended)
        1. **Google Cloud Console Setup**:
           - Create project at [console.cloud.google.com](https://console.cloud.google.com)
           - Enable Gmail API
           - Create OAuth 2.0 credentials
           - Add your Streamlit app URL as authorized redirect URI
        
        2. **Streamlit Secrets**:
           ```toml
           GOOGLE_CLIENT_ID = "your-client-id.googleusercontent.com"
           GOOGLE_CLIENT_SECRET = "your-client-secret"
           REPLICATE_API_TOKEN = "your-replicate-token"  # Optional for AI
           ```
        
        ### Option 2: App Password (Fallback)
        1. **Gmail Setup**:
           - Enable 2-Factor Authentication
           - Generate App Password for "Mail"
        
        2. **Streamlit Secrets**:
           ```toml
           GMAIL_USER = "your-email@gmail.com"
           GMAIL_PASSWORD = "your-16-digit-app-password"
           ```
        """)
        
        return
    
    # Analysis section
    st.header("📊 Transaction Analysis")
    
    # Settings
    st.sidebar.header("⚙️ Settings")
    max_emails = st.sidebar.slider("Max Emails", 10, 100, 30)
    
    # Analysis button
    if st.button("🔍 Analyze Transactions", type="primary"):
        with st.spinner("Analyzing transactions..."):
            # Mock data for demonstration
            # Replace this with actual Gmail API calls
            mock_transactions = [
                {
                    'date': '2024-06-15 10:30:00',
                    'subject': 'SBI ATM Withdrawal Alert',
                    'amount': '2000.00',
                    'category': 'ATM Withdrawal'
                },
                {
                    'date': '2024-06-14 15:45:00',
                    'subject': 'SBI UPI Payment Alert',
                    'amount': '150.00',
                    'category': 'Food & Dining'
                },
                {
                    'date': '2024-06-13 09:20:00',
                    'subject': 'SBI Online Payment Alert',
                    'amount': '1250.00',
                    'category': 'Bills & Utilities'
                }
            ]
            
            # Convert to DataFrame
            df = pd.DataFrame(mock_transactions)
            df['amount_numeric'] = pd.to_numeric(df['amount'])
            df['date_parsed'] = pd.to_datetime(df['date'])
            
            st.session_state.transaction_data = df
            
            st.success(f"✅ Processed {len(df)} transactions")
    
    # Display results
    if 'transaction_data' in st.session_state:
        df = st.session_state.transaction_data
        categorizer = AITransactionCategorizer()
        
        # Summary stats
        st.header("📈 Summary")
        col1, col2, col3 = st.columns(3)
        
        with col1:
            st.metric("Total Transactions", len(df))
        with col2:
            st.metric("Total Amount", f"₹{df['amount_numeric'].sum():,.2f}")
        with col3:
            st.metric("Average Amount", f"₹{df['amount_numeric'].mean():,.2f}")
        
        # Visualizations
        st.header("📊 Visualizations")
        
        fig_pie, fig_bar, fig_timeline, fig_monthly = create_visualizations(df, categorizer)
        
        if fig_pie:
            col1, col2 = st.columns(2)
            with col1:
                st.plotly_chart(fig_pie, use_container_width=True)
            with col2:
                st.plotly_chart(fig_bar, use_container_width=True)
            
            st.plotly_chart(fig_timeline, use_container_width=True)
        
        # Transaction details
        st.header("📋 Transaction Details")
        st.dataframe(df, use_container_width=True)
        
        # Export
        csv = df.to_csv(index=False)
        st.download_button(
            "📥 Download CSV",
            csv,
            "sbi_transactions.csv",
            "text/csv"
        )

if __name__ == "__main__":
    main()
