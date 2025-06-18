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
        """Load configuration from environment variables"""
        config = {
            'REPLICATE_API_TOKEN': os.getenv('REPLICATE_API_TOKEN')
        }
        return config
    
    def validate_config(self) -> bool:
        """Validate that all required configuration is present"""
        self.validation_errors = []
        
        required_fields = {
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
            'Online Purchase': '#4ECDC4',
            'Food & Dining': '#45B7D1',
            'Transportation': '#96CEB4',
            'Bills & Utilities': '#FCEA2B',
            'Entertainment': '#FF9A8B',
            'Healthcare': '#A8E6CF',
            'Shopping': '#FFD93D',
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
                - Transfer: Money transfers, UPI payments
                - Online Purchase: E-commerce, online shopping
                - Food & Dining: Restaurants, food delivery, groceries
                - Transportation: Fuel, cab services, public transport
                - Bills & Utilities: Phone, internet, electricity, water bills
                - Entertainment: Movies, games, subscriptions
                - Healthcare: Medical expenses, pharmacy
                - Shopping: Retail purchases, clothing, electronics
                
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
            'Transfer': ['transfer', 'upi', 'imps', 'neft', 'rtgs'],
            'Online Purchase': ['amazon', 'flipkart', 'paytm', 'online', 'purchase'],
            'Food & Dining': ['restaurant', 'food', 'zomato', 'swiggy', 'dining', 'cafe'],
            'Transportation': ['fuel', 'petrol', 'diesel', 'uber', 'ola', 'transport'],
            'Bills & Utilities': ['bill', 'electricity', 'water', 'phone', 'internet', 'utility'],
            'Entertainment': ['movie', 'cinema', 'netflix', 'game', 'entertainment'],
            'Healthcare': ['medical', 'pharmacy', 'hospital', 'doctor', 'health'],
            'Shopping': ['shopping', 'store', 'mall', 'retail', 'clothing']
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
        self.mail = None
        
        # Initialize categorizer if token is available
        replicate_token = config_manager.get_config_value('REPLICATE_API_TOKEN')
        if replicate_token:
            self.categorizer = AITransactionCategorizer(replicate_token)
        else:
            self.categorizer = None
        
    def authenticate_gmail(self, email_address: str, password: str):
        """Authenticate with Gmail using IMAP with email and password"""
        try:
            # Connect to Gmail IMAP server
            self.mail = imaplib.IMAP4_SSL('imap.gmail.com')
            
            # Login with email and password
            self.mail.login(email_address, password)
            
            return True, email_address
            
        except imaplib.IMAP4.error as e:
            error_msg = str(e)
            if 'invalid credentials' in error_msg.lower():
                st.error("❌ Invalid email or password. Please check your credentials.")
            elif 'application-specific password required' in error_msg.lower():
                st.error("❌ App-specific password required. Please enable 2-factor authentication and use an app-specific password.")
            else:
                st.error(f"❌ Login failed: {error_msg}")
            return False, None
        except Exception as e:
            st.error(f"❌ Connection failed: {e}")
            return False, None
    
    def search_sbi_emails(self, max_results: int = 50) -> List[str]:
        """Search for emails from SBI ATM alerts using IMAP"""
        try:
            # Select INBOX
            self.mail.select('INBOX')
            
            # Search for emails from SBI
            search_criteria = f'FROM "{self.target_sender}"'
            result, message_ids = self.mail.search(None, search_criteria)
            
            if result == 'OK':
                # Get message IDs (most recent first)
                message_id_list = message_ids[0].split()
                message_id_list.reverse()  # Most recent first
                
                # Limit results
                return message_id_list[:max_results]
            else:
                return []
            
        except Exception as e:
            st.error(f"Error searching emails: {e}")
            return []
    
    def get_email_content(self, message_id: str) -> Dict:
        """Get email content by message ID using IMAP"""
        try:
            # Fetch the email
            result, msg_data = self.mail.fetch(message_id, '(RFC822)')
            
            if result == 'OK':
                # Parse the email
                raw_email = msg_data[0][1]
                email_message = email.message_from_bytes(raw_email)
                
                # Extract headers
                subject = email_message.get('Subject', '')
                sender = email_message.get('From', '')
                date_header = email_message.get('Date', '')
                
                # Extract body
                body = self.extract_email_body(email_message)
                
                return {
                    'message_id': message_id.decode(),
                    'subject': subject,
                    'sender': sender,
                    'date': date_header,
                    'body': body,
                    'full_text': f"Subject: {subject}\n\nBody: {body}"
                }
            else:
                return None
            
        except Exception as e:
            st.error(f"Error fetching email {message_id}: {e}")
            return None
    
    def extract_email_body(self, email_message) -> str:
        """Extract body text from email message"""
        body = ""
        
        if email_message.is_multipart():
            # Handle multipart messages
            for part in email_message.walk():
                content_type = part.get_content_type()
                content_disposition = str(part.get("Content-Disposition"))
                
                if content_type == "text/plain" and "attachment" not in content_disposition:
                    try:
                        body = part.get_payload(decode=True).decode('utf-8')
                        break
                    except:
                        try:
                            body = part.get_payload(decode=True).decode('latin-1')
                            break
                        except:
                            continue
                elif content_type == "text/html" and "attachment" not in content_disposition and not body:
                    try:
                        html_body = part.get_payload(decode=True).decode('utf-8')
                        # Simple HTML to text conversion
                        body = re.sub(r'<[^>]+>', ' ', html_body)
                        body = re.sub(r'\s+', ' ', body).strip()
                        break
                    except:
                        continue
        else:
            # Handle simple messages
            try:
                body = email_message.get_payload(decode=True).decode('utf-8')
            except:
                try:
                    body = email_message.get_payload(decode=True).decode('latin-1')
                except:
                    body = str(email_message.get_payload())
        
        return body
    
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
            message_ids = self.search_sbi_emails(max_emails)
            
            for i, message_id in enumerate(message_ids):
                if progress_callback:
                    progress_callback(i + 1, len(message_ids))
                
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
                    'message_id': email_data['message_id'],
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
        finally:
            # Close IMAP connection
            if self.mail:
                try:
                    self.mail.close()
                    self.mail.logout()
                except:
                    pass
        
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
        st.sidebar.info("Please login with your Gmail credentials to analyze SBI transactions")
        
        # Email and password input
        with st.sidebar.form("login_form"):
            email_address = st.text_input(
                "Gmail Address", 
                placeholder="your-email@gmail.com",
                help="Enter your full Gmail address"
            )
            password = st.text_input(
                "Password", 
                type="password",
                placeholder="Your Gmail password or App Password",
                help="Use App Password if 2FA is enabled"
            )
            
            login_button = st.form_submit_button("🔐 Login", type="primary")
            
            if login_button:
                if not email_address or not password:
                    st.error("Please enter both email and password")
                elif not config_manager.validate_config():
                    st.error("Configuration incomplete. Please check Replicate API token.")
                    config_manager.display_config_status()
                else:
                    with st.spinner("Authenticating..."):
                        extractor = SBIEmailExtractor(config_manager)
                        success, user_email = extractor.authenticate_gmail(email_address, password)
                        if success:
                            st.session_state.authenticated = True
                            st.session_state.user_email = user_email
                            st.session_state.extractor = extractor
                            st.rerun()
        
        # Help section
        with st.sidebar.expander("ℹ️ Gmail Authentication Help"):
            st.write("""
            **For Gmail accounts with 2-Factor Authentication:**
            1. Go to Google Account settings
            2. Security → 2-Step Verification
            3. App passwords → Generate new password
            4. Use the generated password here
            
            **For accounts without 2FA:**
            - Use your regular Gmail password
            - You may need to enable "Less secure app access"
            """)
    else:
        st.sidebar.success(f"✅ Logged in as: {st.session_state.user_email}")
        
        if st.sidebar.button("🚪 Logout"):
            # Clear authentication state
            st.session_state.authenticated = False
            st.session_state.user_email = None
            
            # Clear other session data
            keys_to_clear = ['transaction_data', 'categorizer', 'results_processed', 
                           'date_filter_enabled', 'date_filter_start', 'date_filter_end', 'extractor']
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
            "Enable Date Filtering", 
            value=st.session_state.get('date_filter_enabled', False),
            key='date_filter_checkbox'
        )
        
        # Update session state
        st.session_state.date_filter_enabled = date_filter_enabled

        if date_filter_enabled:
            # Set default date range (last 30 days)
            default_end = datetime.now().date()
            default_start = default_end - timedelta(days=30)
            
            # Get existing values from session state or use defaults
            existing_start = st.session_state.get('date_filter_start', default_start)
            existing_end = st.session_state.get('date_filter_end', default_end)
            
            start_date = st.sidebar.date_input(
                "Start Date", 
                value=existing_start,
                key='date_start_input'
            )
            end_date = st.sidebar.date_input(
                "End Date", 
                value=existing_end,
                min_value=start_date,
                key='date_end_input'
            )
            
            # Store in session state
            st.session_state.date_filter_start = start_date
            st.session_state.date_filter_end = end_date
            
            # Show current filter status
            st.sidebar.info(f"Filtering: {start_date} to {end_date}")
        else:
            # Clear date filter from session state when disabled
            if 'date_filter_start' in st.session_state:
                del st.session_state['date_filter_start']
            if 'date_filter_end' in st.session_state:
                del st.session_state['date_filter_end']
        
        # Main content area
        if not config_manager.validate_config():
            st.error("⚠️ Configuration incomplete!")
            st.error("Please set up your Replicate API token in the `.secret` file.")
            return
        
        # Process transactions button
        if st.button("🔍 Analyze SBI Transactions", type="primary"):
            with st.spinner(f"Processing up to {max_emails} emails..."):
                
                # Create progress bar
                progress_bar = st.progress(0)
                status_text = st.empty()
                
                def update_progress(current, total):
                    progress = current / total
                    progress_bar.progress(progress)
                    status_text.text(f"Processing email {current}/{total}")
                
                # Get extractor from session state or create new one
                if 'extractor' in st.session_state:
                    extractor = st.session_state.extractor
                else:
                    extractor = SBIEmailExtractor(config_manager)
                    # Re-authenticate
                    success, _ = extractor.authenticate_gmail(st.session_state.user_email, "")
                    if not success:
                        st.error("Re-authentication failed. Please logout and login again.")
                        return
                
                # Process emails
                results = extractor.process_emails(max_emails, update_progress)
                
                # Clear progress indicators
                progress_bar.empty()
                status_text.empty()
                
                if results:
                    st.session_state.transaction_data = results
                    st.session_state.results_processed = True
                    st.session_state.categorizer = extractor.categorizer
                    st.success(f"✅ Successfully processed {len(results)} transaction emails!")
                else:
                    st.warning("No SBI transaction emails found or processed.")
        
        # Display results if available
        if st.session_state.get('results_processed', False) and 'transaction_data' in st.session_state:
            results = st.session_state.transaction_data
            categorizer = st.session_state.categorizer
            
            # Convert to DataFrame for analysis
            df = pd.DataFrame(results)
            
            # Parse dates and amounts
            df['date_parsed'] = pd.to_datetime(df['date'], errors='coerce')
            df['amount_numeric'] = pd.to_numeric(df['amount'].str.replace(',', ''), errors='coerce')
            
            # Filter out rows without valid amounts or dates
            df = df.dropna(subset=['amount_numeric', 'date_parsed'])
            
            if len(df) == 0:
                st.warning("No valid transactions with amounts found.")
                return
            
            # Apply date filter
            df_display = apply_date_filter(df)
            
            # Show summary statistics
            st.header("📊 Transaction Summary")
            
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
                date_range = df_display['date_parsed'].max() - df_display['date_parsed'].min()
                st.metric("Date Range", f"{date_range.days} days")
            
            # Create visualizations
            st.header("📈 Transaction Analysis")
            
            if len(df_display) > 0:
                fig_pie, fig_bar, fig_timeline, fig_monthly = create_visualizations(df, categorizer)
                
                if fig_pie:
                    # Display charts in tabs
                    tab1, tab2, tab3, tab4 = st.tabs(["Category Distribution", "Amount by Category", "Timeline", "Monthly Trends"])
                    
                    with tab1:
                        st.plotly_chart(fig_pie, use_container_width=True)
                    
                    with tab2:
                        st.plotly_chart(fig_bar, use_container_width=True)
                    
                    with tab3:
                        st.plotly_chart(fig_timeline, use_container_width=True)
                    
                    with tab4:
                        st.plotly_chart(fig_monthly, use_container_width=True)
            
            # Category breakdown
            st.header("🏷️ Category Breakdown")
            
            category_summary = df_display.groupby('category').agg({
                'amount_numeric': ['count', 'sum', 'mean']
            }).round(2)
            
            category_summary.columns = ['Count', 'Total Amount', 'Average Amount']
            category_summary = category_summary.sort_values('Total Amount', ascending=False)
            
            # Add color coding
            def color_categories(row):
                color = categorizer.get_category_color(row.name)
                return [f'background-color: {color}; color: white' for _ in row]
            
            styled_summary = category_summary.style.apply(color_categories, axis=1)
            st.dataframe(styled_summary, use_container_width=True)
            
            # Detailed transaction table
            st.header("📋 Transaction Details")
            
            # Add filters
            col1, col2 = st.columns(2)
            
            with col1:
                selected_categories = st.multiselect(
                    "Filter by Category",
                    options=df_display['category'].unique(),
                    default=df_display['category'].unique()
                )
            
            with col2:
                amount_filter = st.selectbox(
                    "Amount Filter",
                    ["All", "< ₹100", "₹100-₹1000", "₹1000-₹10000", "> ₹10000"]
                )
            
            # Apply filters
            filtered_df = df_display[df_display['category'].isin(selected_categories)]
            
            if amount_filter != "All":
                if amount_filter == "< ₹100":
                    filtered_df = filtered_df[filtered_df['amount_numeric'] < 100]
                elif amount_filter == "₹100-₹1000":
                    filtered_df = filtered_df[(filtered_df['amount_numeric'] >= 100) & 
                                            (filtered_df['amount_numeric'] < 1000)]
                elif amount_filter == "₹1000-₹10000":
                    filtered_df = filtered_df[(filtered_df['amount_numeric'] >= 1000) & 
                                            (filtered_df['amount_numeric'] < 10000)]
                elif amount_filter == "> ₹10000":
                    filtered_df = filtered_df[filtered_df['amount_numeric'] >= 10000]
            
            # Display filtered results
            display_columns = ['date_parsed', 'subject', 'amount', 'category', 'email_body_preview']
            display_df = filtered_df[display_columns].copy()
            display_df['date_parsed'] = display_df['date_parsed'].dt.strftime('%Y-%m-%d %H:%M')
            display_df.columns = ['Date', 'Subject', 'Amount', 'Category', 'Preview']
            
            st.dataframe(display_df, use_container_width=True)
            
            # Export functionality
            st.header("💾 Export Data")
            
            col1, col2 = st.columns(2)
            
            with col1:
                # Export to CSV
                csv_data = filtered_df.to_csv(index=False)
                st.download_button(
                    label="📥 Download as CSV",
                    data=csv_data,
                    file_name=f"sbi_transactions_{datetime.now().strftime('%Y%m%d_%H%M%S')}.csv",
                    mime="text/csv"
                )
            
            with col2:
                # Export summary
                summary_data = category_summary.to_csv()
                st.download_button(
                    label="📊 Download Summary",
                    data=summary_data,
                    file_name=f"sbi_summary_{datetime.now().strftime('%Y%m%d_%H%M%S')}.csv",
                    mime="text/csv"
                )
        
        # Instructions section
        if not st.session_state.get('results_processed', False):
            st.header("🚀 How to Use")
            
            st.markdown("""
            ### Steps to Analyze Your SBI Transactions:
            
            1. **Authentication**: Login with your Gmail credentials in the sidebar
            2. **Configuration**: Ensure your Replicate API token is set in `.secret` file
            3. **Settings**: Adjust the number of emails to process (5-100)
            4. **Date Filter**: Optionally enable date filtering to analyze specific periods
            5. **Analysis**: Click "Analyze SBI Transactions" to start processing
            
            ### Features:
            - 🤖 **AI-Powered Categorization**: Automatically categorizes transactions using advanced AI
            - 📊 **Visual Analytics**: Interactive charts and graphs
            - 🔍 **Smart Filtering**: Filter by category, amount, and date range
            - 📈 **Trend Analysis**: Monthly spending patterns and timeline views
            - 💾 **Export Options**: Download data as CSV for further analysis
            
            ### Requirements:
            - Gmail account with SBI transaction alert emails
            - Replicate API token for AI features
            - App Password if 2FA is enabled on Gmail
            """)
            
            st.info("💡 Make sure you have SBI transaction alert emails in your Gmail inbox from 'donotreply.sbiatm@alerts.sbi.co.in'")

if __name__ == "__main__":
    main()
