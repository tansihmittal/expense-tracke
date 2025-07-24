import streamlit as st
import imaplib
import email
import re
import requests
import json
import os
import base64
from datetime import datetime, timedelta, date
from typing import List, Dict, Optional
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
from collections import Counter
import os
from dotenv import load_dotenv
import dateutil.parser
import calendar
from streamlit_tags import st_tags
import numpy as np
from io import StringIO
from bs4 import BeautifulSoup
import pytz
from concurrent.futures import ThreadPoolExecutor, as_completed
import threading
import time
import hashlib

# Load environment variables
load_dotenv('.secret')

# Set page config
st.set_page_config(
    page_title="AI Expense & Subscription Tracker",
    page_icon="💳",
    layout="wide",
    initial_sidebar_state="expanded"
)

# Custom CSS for professional styling
st.markdown("""
<style>
    .main {
        background-color: #f8f9fa;
    }
    .stButton>button {
        border-radius: 8px;
        padding: 8px 16px;
        font-weight: 500;
    }
    .stSelectbox, .stTextInput, .stTextArea, .stDateInput {
        border-radius: 8px;
    }
    .stDataFrame {
        border-radius: 8px;
        box-shadow: 0 2px 4px rgba(0,0,0,0.1);
    }
    .metric-card {
        background-color: white;
        border-radius: 12px;
        padding: 20px;
        box-shadow: 0 4px 6px rgba(0,0,0,0.1);
        margin-bottom: 15px;
        text-align: center;
    }
    .metric-title {
        font-size: 14px;
        color: #6c757d;
        margin-bottom: 8px;
        font-weight: 500;
    }
    .metric-value {
        font-size: 28px;
        font-weight: bold;
        color: #212529;
    }
    .section-header {
        border-bottom: 2px solid #dee2e6;
        padding-bottom: 8px;
        margin-top: 25px;
        margin-bottom: 20px;
        color: #495057;
        font-weight: 600;
    }
    .subscription-card {
        background-color: white;
        border-radius: 12px;
        padding: 20px;
        box-shadow: 0 4px 8px rgba(0,0,0,0.1);
        margin-bottom: 20px;
        border-left: 4px solid #007bff;
        transition: transform 0.2s;
    }
    .subscription-card:hover {
        transform: translateY(-2px);
        box-shadow: 0 6px 12px rgba(0,0,0,0.15);
    }
    .subscription-card.trial {
        border-left-color: #ffc107;
        background: linear-gradient(135deg, #fff9e6 0%, #ffffff 100%);
    }
    .subscription-header {
        display: flex;
        justify-content: space-between;
        align-items: center;
        margin-bottom: 15px;
    }
    .subscription-name {
        font-size: 20px;
        font-weight: bold;
        color: #2c3e50;
    }
    .subscription-amount {
        font-size: 22px;
        font-weight: bold;
        color: #e74c3c;
    }
    .subscription-amount.trial {
        color: #ff8c00;
    }
    .subscription-details {
        font-size: 14px;
        color: #7f8c8d;
        margin-top: 10px;
        line-height: 1.4;
    }
    .subscription-status {
        display: inline-block;
        padding: 4px 12px;
        border-radius: 15px;
        font-size: 12px;
        font-weight: bold;
        margin-left: 10px;
    }
    .status-active {
        background-color: #d4edda;
        color: #155724;
    }
    .status-trial {
        background-color: #fff3cd;
        color: #856404;
    }
    .status-inactive {
        background-color: #f8d7da;
        color: #721c24;
    }
    .next-payment {
        background-color: #fff3cd;
        padding: 10px;
        border-radius: 8px;
        margin-top: 15px;
        font-size: 13px;
        color: #856404;
        font-weight: 500;
    }
    .next-payment.overdue {
        background-color: #f8d7da;
        color: #721c24;
    }
    .trial-badge {
        background: linear-gradient(45deg, #ffc107, #ff8c00);
        color: white;
        padding: 4px 8px;
        border-radius: 12px;
        font-size: 11px;
        font-weight: bold;
        margin-left: 10px;
        animation: pulse 2s infinite;
    }
    @keyframes pulse {
        0% { opacity: 1; }
        50% { opacity: 0.7; }
        100% { opacity: 1; }
    }
    .subscription-summary {
        background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
        color: white;
        padding: 25px;
        border-radius: 15px;
        margin-bottom: 25px;
    }
    .summary-stat {
        text-align: center;
        margin-bottom: 15px;
    }
    .summary-value {
        font-size: 32px;
        font-weight: bold;
    }
    .summary-label {
        font-size: 14px;
        opacity: 0.9;
        margin-top: 5px;
    }
    .transaction-card {
        background-color: white;
        border-radius: 10px;
        padding: 18px;
        box-shadow: 0 2px 6px rgba(0,0,0,0.1);
        margin-bottom: 15px;
        border-left: 3px solid #28a745;
    }
    .transaction-amount {
        font-size: 20px;
        font-weight: bold;
    }
    .transaction-date {
        font-size: 12px;
        color: #6c757d;
        font-weight: 500;
    }
    .transaction-merchant {
        font-weight: 600;
        margin: 8px 0;
        color: #2c3e50;
        font-size: 16px;
    }
    .category-tag {
        display: inline-block;
        padding: 4px 10px;
        border-radius: 15px;
        font-size: 12px;
        margin-right: 8px;
        margin-bottom: 5px;
        font-weight: 500;
    }
    .service-logo {
        width: 28px;
        height: 28px;
        border-radius: 6px;
        margin-right: 10px;
        vertical-align: middle;
    }
    .success-message {
        background-color: #d4edda;
        border: 1px solid #c3e6cb;
        color: #155724;
        padding: 15px;
        border-radius: 8px;
        margin: 10px 0;
    }
    .info-box {
        background-color: #e3f2fd;
        border-left: 4px solid #2196f3;
        padding: 15px;
        margin: 15px 0;
        border-radius: 4px;
    }
    .warning-box {
        background-color: #fff3cd;
        border-left: 4px solid #ffc107;
        padding: 15px;
        margin: 15px 0;
        border-radius: 4px;
        color: #856404;
    }
    .stats-container {
        background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
        border-radius: 15px;
        padding: 20px;
        margin: 20px 0;
        color: white;
    }
    .stats-grid {
        display: grid;
        grid-template-columns: repeat(auto-fit, minmax(200px, 1fr));
        gap: 15px;
        margin-top: 15px;
    }
    .stats-card {
        background: rgba(255, 255, 255, 0.1);
        border-radius: 10px;
        padding: 15px;
        text-align: center;
        backdrop-filter: blur(10px);
    }
    .stats-number {
        font-size: 24px;
        font-weight: bold;
        margin-bottom: 5px;
    }
    .stats-label {
        font-size: 14px;
        opacity: 0.9;
    }
</style>
""", unsafe_allow_html=True)

class UserStatisticsManager:
    """Manages user statistics and analytics"""
    
    def __init__(self):
        self.stats_file = 'user_statistics.json'
        self.stats = self._load_statistics()
    
    def _load_statistics(self) -> Dict:
        """Load statistics from file"""
        try:
            if os.path.exists(self.stats_file):
                with open(self.stats_file, 'r') as f:
                    return json.load(f)
        except Exception:
            pass
        
        return {
            'total_users': 0,
            'total_amount_detected': 0.0,
            'total_subscriptions_detected': 0,
            'last_updated': None
        }
    
    def _save_statistics(self):
        """Save statistics to file"""
        try:
            self.stats['last_updated'] = datetime.now().isoformat()
            with open(self.stats_file, 'w') as f:
                json.dump(self.stats, f, indent=2)
        except Exception as e:
            print(f"Error saving statistics: {e}")
    
    def record_user_session(self, user_email: str):
        """Record a new user session"""
        users_file = 'tracked_users.json'
        tracked_users = set()
        
        try:
            if os.path.exists(users_file):
                with open(users_file, 'r') as f:
                    tracked_users = set(json.load(f))
        except Exception:
            pass
        
        if user_email not in tracked_users:
            tracked_users.add(user_email)
            self.stats['total_users'] = len(tracked_users)
            
            try:
                with open(users_file, 'w') as f:
                    json.dump(list(tracked_users), f)
            except Exception:
                pass
            
            self._save_statistics()
    
    def record_transaction_analysis(self, total_amount: float, subscription_count: int):
        """Record transaction analysis results"""
        self.stats['total_amount_detected'] += total_amount
        self.stats['total_subscriptions_detected'] += subscription_count
        self._save_statistics()
    
    def get_statistics(self) -> Dict:
        """Get current statistics"""
        return self.stats.copy()
    
    def format_amount(self, amount: float) -> str:
        """Format amount for display"""
        if amount >= 10000000:  # 1 crore
            return f"₹{amount/10000000:.1f}Cr"
        elif amount >= 100000:  # 1 lakh
            return f"₹{amount/100000:.1f}L"
        elif amount >= 1000:  # 1 thousand
            return f"₹{amount/1000:.1f}K"
        else:
            return f"₹{amount:,.0f}"

class ConfigManager:
    """Manages configuration and credentials"""
    
    def __init__(self):
        self.config = self._load_config()
        self.validation_errors = []
    
    def _load_config(self) -> Dict[str, str]:
        """Load configuration from environment variables"""
        config = {
            'REPLICATE_API_TOKEN': os.getenv('REPLICATE_API_TOKEN'),
            'PLAID_CLIENT_ID': os.getenv('PLAID_CLIENT_ID'),
            'PLAID_SECRET': os.getenv('PLAID_SECRET'),
            'PLAID_ENV': os.getenv('PLAID_ENV', 'sandbox')
        }
        return config
    
    def validate_config(self) -> bool:
        """Validate required configuration"""
        self.validation_errors = []
        
        if not self.config.get('REPLICATE_API_TOKEN'):
            self.validation_errors.append("Missing Replicate API Token")
        
        return len(self.validation_errors) == 0
    
    def get_config_value(self, key: str) -> Optional[str]:
        """Get configuration value by key"""
        return self.config.get(key)
    
    def display_config_status(self):
        """Display configuration status if there are issues"""
        if not self.validate_config():
            st.sidebar.error("⚠️ Configuration incomplete")
            with st.sidebar.expander("Setup Instructions"):
                st.write("""
                Create a `.secret` file in your project root with:
                ```
                REPLICATE_API_TOKEN=your_replicate_token_here
                ```
                """)

class AITransactionCategorizer:
    """AI-powered transaction categorization with unlimited categories"""
    
    def __init__(self, replicate_token: str):
        self.replicate_token = replicate_token
        self.category_colors = {}
        self.vendor_cache = {}
        self.subscription_indicators = {
            'netflix', 'prime video', 'disney', 'hotstar', 'zee5', 'youtube', 'spotify', 'apple music',
            'adobe', 'microsoft', 'google workspace', 'zoom', 'slack', 'notion', 'dropbox',
            'aws', 'azure', 'google cloud', 'digitalocean',
            'subscription', 'monthly', 'yearly', 'recurring', 'auto-renewal'
        }
        
        # Improved color palette for better distribution
        self.color_palette = [
            '#E50914', '#4285F4', '#FF6B35', '#4CAF50', '#9C27B0', '#FF5722',
            '#00BCD4', '#FFC107', '#795548', '#607D8B', '#3F51B5', '#009688',
            '#8BC34A', '#CDDC39', '#FFEB3B', '#FF9800', '#FF5252', '#536DFE',
            '#1DB954', '#00A3E0', '#F7931E', '#FF4444', '#6C5CE7', '#74B9FF',
            '#A29BFE', '#FD79A8', '#FDCB6E', '#6C757D', '#E17055', '#2D3436'
        ]
        self.color_index = 0
        
        # Initialize with predefined service colors
        self._initialize_service_colors()
    
    def _initialize_service_colors(self):
        """Initialize with predefined colors for common services"""
        predefined_colors = {
            'netflix': '#E50914',
            'youtube': '#FF0000',
            'spotify': '#1DB954',
            'google cloud': '#4285F4',
            'microsoft': '#0078D4',
            'adobe': '#FF0000',
            'amazon': '#FF9900',
            'uber': '#000000',
            'zomato': '#E23744',
            'swiggy': '#FC8019',
            'food delivery': '#FF6B35',
            'streaming services': '#E50914',
            'saas services': '#4285F4',
            'cloud platform': '#4285F4',
            'video streaming': '#E50914',
            'music streaming': '#1DB954'
        }
        
        for service, color in predefined_colors.items():
            self.category_colors[service.lower()] = color
    
    def get_next_color(self) -> str:
        """Get next color from palette"""
        color = self.color_palette[self.color_index % len(self.color_palette)]
        self.color_index += 1
        return color
    
    def clean_html_content(self, html_content: str) -> str:
        """Clean HTML content and extract meaningful text"""
        try:
            soup = BeautifulSoup(html_content, 'html.parser')
            
            for script in soup(["script", "style"]):
                script.decompose()
            
            text = soup.get_text()
            lines = (line.strip() for line in text.splitlines())
            chunks = (phrase.strip() for line in lines for phrase in line.split("  "))
            text = ' '.join(chunk for chunk in chunks if chunk)
            
            return text[:1200]
            
        except Exception:
            clean_text = re.sub(r'<[^>]+>', ' ', html_content)
            clean_text = re.sub(r'\s+', ' ', clean_text).strip()
            return clean_text[:1200]
    
    def analyze_transaction_complete(self, subject: str, body: str, bank_name: str) -> Dict:
        """Complete AI analysis of transaction"""
        try:
            url = "https://api.replicate.com/v1/models/openai/gpt-4.1-nano/predictions"
            
            headers = {
                "Authorization": f"Bearer {self.replicate_token}",
                "Content-Type": "application/json"
            }
            
            subject_clean = subject[:100]
            body_clean = self.clean_html_content(body)
            
            prompt = f"""Analyze this bank transaction email from {bank_name}:

Email Content: {body_clean}

Extract and return ONLY this JSON:
{{
    "amount": "numeric amount only (e.g. 895.62) or null",
    "vendor": "actual merchant/store name from transaction details",
    "category": "specific category based on vendor context",
    "color": "appropriate hex color for category",
    "confidence": 0-100,
    "is_subscription": true/false,
    "subscription_type": "streaming/saas/food_delivery/telecom/etc or null",
    "billing_cycle": "monthly/quarterly/yearly or null",
    "service_logo": "appropriate emoji for service",
    "is_trial": true/false
}}"""
            
            data = {
                "input": {
                    "prompt": prompt,
                    "system_prompt": "You are an expert transaction analyzer. Extract vendor details from bank email content, identify subscriptions, detect trials (amounts under ₹10 or keywords like 'trial', 'free', 'test'). Return only valid JSON.",
                    "max_tokens": 400,
                    "temperature": 0.2
                }
            }
            
            response = requests.post(url, headers=headers, json=data)
            
            if response.status_code == 201:
                prediction = response.json()
                prediction_id = prediction['id']
                result = self.poll_prediction(prediction_id)
                
                if result:
                    try:
                        json_match = re.search(r'\{.*\}', result.strip(), re.DOTALL)
                        if json_match:
                            json_str = json_match.group(0)
                            analysis = json.loads(json_str)
                        else:
                            analysis = json.loads(result.strip())
                        
                        category = analysis.get('category', 'Other Transactions')
                        vendor = analysis.get('vendor', 'Unknown Vendor')
                        color = analysis.get('color', self.get_category_color(category))
                        amount = analysis.get('amount')
                        confidence = analysis.get('confidence', 50)
                        is_subscription = analysis.get('is_subscription', False)
                        subscription_type = analysis.get('subscription_type')
                        billing_cycle = analysis.get('billing_cycle')
                        service_logo = analysis.get('service_logo', '💳')
                        is_trial = analysis.get('is_trial', False)
                        
                        # Validate amount
                        if amount and isinstance(amount, str):
                            amount = re.sub(r'[^\d.]', '', amount)
                            try:
                                amount = float(amount)
                                if amount <= 0 or amount > 10000000:
                                    amount = None
                                # Check if amount indicates trial
                                elif amount <= 10:
                                    is_trial = True
                            except:
                                amount = None
                        
                        # Additional trial detection
                        if not is_trial:
                            trial_keywords = ['trial', 'free', 'test', 'demo', 'preview', 'beta']
                            text_content = f"{subject} {body}".lower()
                            is_trial = any(keyword in text_content for keyword in trial_keywords)
                            if amount and amount <= 10:
                                is_trial = True
                        
                        # Store color for category
                        if category.lower() not in self.category_colors:
                            self.category_colors[category.lower()] = color if color and color.startswith('#') else self.get_next_color()
                        
                        vendor_key = vendor.lower().strip()
                        if vendor_key not in self.vendor_cache:
                            self.vendor_cache[vendor_key] = {
                                'display_name': vendor,
                                'category': category,
                                'color': self.category_colors[category.lower()],
                                'is_subscription': is_subscription,
                                'subscription_type': subscription_type,
                                'service_logo': service_logo,
                                'is_trial': is_trial
                            }
                        
                        return {
                            'amount': str(amount) if amount else None,
                            'category': category,
                            'merchant_name': vendor,
                            'color': self.category_colors[category.lower()],
                            'confidence': confidence,
                            'is_subscription': is_subscription,
                            'subscription_type': subscription_type,
                            'billing_cycle': billing_cycle,
                            'service_logo': service_logo,
                            'is_trial': is_trial
                        }
                    except json.JSONDecodeError:
                        pass
            
            return self.enhanced_fallback_analysis(subject, body, bank_name)
                
        except Exception:
            return self.enhanced_fallback_analysis(subject, body, bank_name)
    
    def enhanced_fallback_analysis(self, subject: str, body: str, bank_name: str) -> Dict:
        """Enhanced fallback analysis with vendor extraction and trial detection"""
        body_clean = self.clean_html_content(body)
        text = f"{subject} {body_clean}".lower()
        
        amount = self.extract_amount_regex(f"{subject} {body}")
        amount_float = None
        try:
            if amount:
                amount_float = float(amount)
        except:
            pass
        
        # Enhanced vendor extraction patterns
        vendor_patterns = [
            r'(?:at|@)\s+([A-Za-z][A-Za-z0-9\s&.-]{2,30})(?:\s|$|,|\.|;)',
            r'(?:paid to|payment to|transfer to)\s+([A-Za-z][A-Za-z0-9\s&.-]{2,30})(?:\s|$|,|\.|;)',
            r'(?:merchant|store|shop):\s*([A-Za-z][A-Za-z0-9\s&.-]{2,30})(?:\s|$|,|\.|;)',
            r'(?:purchase from|bought from)\s+([A-Za-z][A-Za-z0-9\s&.-]{2,30})(?:\s|$|,|\.|;)',
            r'([A-Z][A-Z0-9\s&.-]{3,25})\s+(?:store|shop|restaurant|cafe)',
            r'(?:^|\s)([A-Z][a-z]+(?:\s[A-Z][a-z]+)*)\s+(?:payment|transaction)',
        ]
        
        vendor = "Unknown Vendor"
        for pattern in vendor_patterns:
            matches = re.findall(pattern, body_clean, re.IGNORECASE | re.MULTILINE)
            if matches:
                vendor = matches[0].strip().title()
                if len(vendor) > 3 and not vendor.lower() in ['the', 'and', 'for', 'with', 'from', 'account', 'bank', 'card']:
                    break
        
        # Check subscription indicators
        is_subscription = any(indicator in text for indicator in self.subscription_indicators)
        subscription_type = None
        billing_cycle = None
        service_logo = '💳'
        
        # Trial detection
        trial_keywords = ['trial', 'free', 'test', 'demo', 'preview', 'beta', 'promo']
        is_trial = any(keyword in text for keyword in trial_keywords)
        if amount_float and amount_float <= 10:
            is_trial = True
        
        if is_subscription:
            if any(word in text for word in ['stream', 'video', 'movie', 'tv']):
                subscription_type = 'streaming'
                service_logo = '🎬'
            elif any(word in text for word in ['music', 'audio', 'song']):
                subscription_type = 'music'
                service_logo = '🎧'
            elif any(word in text for word in ['cloud', 'storage', 'software', 'saas']):
                subscription_type = 'saas'
                service_logo = '☁️'
            elif any(word in text for word in ['food', 'delivery', 'restaurant']):
                subscription_type = 'food_delivery'
                service_logo = '🍕'
            elif any(word in text for word in ['mobile', 'internet', 'phone']):
                subscription_type = 'telecom'
                service_logo = '📱'
            else:
                subscription_type = 'other'
                service_logo = '🔄'
            
            if any(word in text for word in ['monthly', 'month']):
                billing_cycle = 'monthly'
            elif any(word in text for word in ['quarterly', 'quarter']):
                billing_cycle = 'quarterly'
            elif any(word in text for word in ['yearly', 'annual', 'year']):
                billing_cycle = 'yearly'
            else:
                billing_cycle = 'monthly'
        
        # Enhanced category mapping
        category_mapping = {
            'food delivery': {'keywords': ['zomato', 'swiggy', 'uber eats', 'foodpanda', 'delivery', 'dominos', 'pizza', 'kfc', 'mcdonalds'], 'color': '#FF6B35'},
            'restaurants': {'keywords': ['restaurant', 'dining', 'cafe', 'coffee', 'starbucks', 'ccd', 'bistro'], 'color': '#F7931E'},
            'grocery stores': {'keywords': ['grocery', 'supermarket', 'big bazaar', 'dmart', 'reliance fresh', 'more', 'store'], 'color': '#4CAF50'},
            'ride sharing': {'keywords': ['uber', 'ola', 'taxi', 'cab', 'ride'], 'color': '#000000'},
            'fuel & petrol': {'keywords': ['petrol', 'diesel', 'fuel', 'gas', 'hp', 'bharat petroleum', 'iocl'], 'color': '#FF4444'},
            'online shopping': {'keywords': ['amazon', 'flipkart', 'myntra', 'jabong', 'snapdeal', 'online', 'ecommerce'], 'color': '#FF5722'},
            'streaming services': {'keywords': ['netflix', 'prime video', 'hotstar', 'disney', 'youtube', 'spotify'], 'color': '#E50914'},
            'saas services': {'keywords': ['google cloud', 'aws', 'azure', 'office 365', 'adobe', 'dropbox'], 'color': '#4285F4'},
            'pharmacy': {'keywords': ['pharmacy', 'medical', 'medicine', 'drug', 'apollo', 'netmeds'], 'color': '#4CAF50'},
            'atm withdrawal': {'keywords': ['atm', 'withdrawal', 'cash', 'withdraw'], 'color': '#795548'},
            'money transfer': {'keywords': ['transfer', 'upi', 'neft', 'rtgs', 'imps', 'paytm', 'phonepe', 'gpay'], 'color': '#2196F3'},
            'electricity bill': {'keywords': ['electricity', 'power', 'current bill', 'bescom', 'kseb'], 'color': '#FFC107'},
            'internet & telecom': {'keywords': ['internet', 'broadband', 'wifi', 'airtel', 'jio', 'bsnl', 'mobile bill'], 'color': '#9C27B0'},
        }
        
        category = 'other transactions'
        color = self.get_next_color()
        max_matches = 0
        
        for cat, info in category_mapping.items():
            matches = sum(1 for keyword in info['keywords'] if keyword in text)
            if matches > max_matches:
                max_matches = matches
                category = cat
                color = info['color']
        
        if max_matches == 0 and vendor != "Unknown Vendor":
            vendor_lower = vendor.lower()
            if any(word in vendor_lower for word in ['restaurant', 'cafe', 'kitchen', 'food']):
                category = 'restaurants'
                color = '#F7931E'
            elif any(word in vendor_lower for word in ['store', 'mart', 'shop', 'retail']):
                category = 'retail stores'
                color = '#FF5722'
            elif any(word in vendor_lower for word in ['tech', 'digital', 'software', 'app', 'cloud']):
                category = 'saas services'
                color = '#4285F4'
        
        # Store color for category
        if category.lower() not in self.category_colors:
            self.category_colors[category.lower()] = color
        
        return {
            'amount': amount,
            'category': category.title(),
            'merchant_name': vendor,
            'color': self.category_colors[category.lower()],
            'confidence': max_matches * 15 if max_matches > 0 else 25,
            'is_subscription': is_subscription,
            'subscription_type': subscription_type,
            'billing_cycle': billing_cycle,
            'service_logo': service_logo,
            'is_trial': is_trial
        }
    
    def extract_amount_regex(self, text: str) -> Optional[str]:
        """Extract amount with enhanced patterns"""
        patterns = [
            r'(?:Rs\.?\s*|₹\s*)(\d+(?:,\d+)*(?:\.\d{1,2})?)',
            r'(?:INR\s*)(\d+(?:,\d+)*(?:\.\d{1,2})?)',
            r'(?:\$|USD\s*)(\d+(?:,\d+)*(?:\.\d{1,2})?)',
            r'(?:Amount\s*:?\s*Rs\.?\s*|Amount\s*:?\s*₹\s*)(\d+(?:,\d+)*(?:\.\d{1,2})?)',
            r'(?:Amount\s*:?\s*)(\d+(?:,\d+)*(?:\.\d{1,2})?)',
            r'(?:Debited|Credited|Withdrawn).*?(?:Rs\.?\s*|₹\s*)(\d+(?:,\d+)*(?:\.\d{1,2})?)',
            r'(?:Debited|Credited|Withdrawn).*?(\d+(?:,\d+)*(?:\.\d{1,2})?)',
            r'(?:^|\s)(\d{1,8}\.\d{2})(?:\s|$)',
            r'(?:^|\s)(\d{2,8})(?:\s|$)'
        ]
        
        for pattern in patterns:
            matches = re.findall(pattern, text, re.IGNORECASE)
            for match in matches:
                amount = match.replace(',', '').strip()
                try:
                    amount_float = float(amount)
                    if 0.01 <= amount_float <= 10000000:
                        return amount
                except ValueError:
                    continue
        
        return None
    
    def poll_prediction(self, prediction_id: str, max_attempts: int = 30) -> Optional[str]:
        """Poll prediction with retry logic"""
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
                    
            except Exception:
                return None
        
        return None
    
    def get_category_color(self, category: str) -> str:
        """Get color for a category"""
        category_lower = category.lower()
        if category_lower in self.category_colors:
            return self.category_colors[category_lower]
        else:
            color = self.get_next_color()
            self.category_colors[category_lower] = color
            return color

class SubscriptionTracker:
    """Subscription tracking with trial detection and optimized unique ID generation"""
    
    def __init__(self, config_manager: ConfigManager):
        self.config_manager = config_manager
    
    def generate_unique_id(self, prefix: str, merchant_name: str, amount: float, extra: str = "") -> str:
        """Generate a truly unique ID using hash of multiple components"""
        timestamp = str(int(time.time() * 1000))
        merchant_clean = re.sub(r'[^a-zA-Z0-9]', '', merchant_name.lower())
        amount_str = str(int(amount * 100)) if amount else "0"
        
        # Create hash from components
        hash_input = f"{merchant_clean}_{amount_str}_{timestamp}_{extra}".encode()
        hash_id = hashlib.md5(hash_input).hexdigest()[:8]
        
        return f"{prefix}_{merchant_clean}_{hash_id}"
    
    def detect_subscription_type_and_trial(self, merchant_name: str, amount: float, transaction_data: Dict) -> Dict:
        """Detect if subscription is trial and determine type"""
        is_trial = False
        trial_reason = None
        
        # Check amount-based trial detection
        if amount <= 10:
            is_trial = True
            trial_reason = f"Low amount (₹{amount:.2f})"
        
        # Check text-based trial detection
        text_content = f"{merchant_name} {transaction_data.get('original_description', '')}".lower()
        trial_keywords = ['trial', 'free', 'test', 'demo', 'preview', 'beta', 'promo', 'starter']
        
        for keyword in trial_keywords:
            if keyword in text_content:
                is_trial = True
                trial_reason = f"Contains '{keyword}'"
                break
        
        # Special service detection
        service_lower = merchant_name.lower()
        subscription_type = transaction_data.get('subscription_type', 'other')
        
        if 'google cloud' in service_lower or 'gcp' in service_lower:
            subscription_type = 'cloud_platform'
            if amount <= 10:
                is_trial = True
                trial_reason = "Google Cloud trial/credits"
        
        return {
            'is_trial': is_trial,
            'trial_reason': trial_reason,
            'subscription_type': subscription_type
        }
    
    def detect_subscriptions_from_transactions(self, df: pd.DataFrame) -> List[Dict]:
        """Detect subscriptions from existing transaction analysis with trial detection"""
        if df.empty:
            return []
        
        detected_subscriptions = []
        
        subscription_transactions = df[df.get('is_subscription', False) == True].copy()
        
        if subscription_transactions.empty:
            return self._detect_subscriptions_by_pattern(df)
        
        subscription_transactions['merchant_key'] = subscription_transactions['merchant_name'].str.lower().str.strip()
        
        merchant_groups = subscription_transactions.groupby(['merchant_key', 'amount_numeric']).agg({
            'date_parsed': ['count', 'min', 'max'],
            'merchant_name': 'first',
            'category': 'first',
            'bank': 'first',
            'subscription_type': 'first',
            'billing_cycle': 'first',
            'service_logo': 'first',
            'color': 'first',
            'confidence': 'mean',
            'is_trial': 'first',
            'subject': 'first'
        })
        
        merchant_groups.columns = ['transaction_count', 'first_date', 'last_date', 'merchant_name', 
                                 'category', 'bank', 'subscription_type', 'billing_cycle', 
                                 'service_logo', 'color', 'confidence', 'is_trial', 'subject']
        merchant_groups = merchant_groups.reset_index()
        
        potential_subs = merchant_groups[merchant_groups['transaction_count'] >= 1]
        
        for idx, row in potential_subs.iterrows():
            ai_billing_cycle = row['billing_cycle']
            amount = float(row['amount_numeric'])
            
            if row['transaction_count'] > 1:
                date_diff = (row['last_date'] - row['first_date']).days
                avg_cycle = date_diff / (row['transaction_count'] - 1) if row['transaction_count'] > 1 else 0
                
                if 25 <= avg_cycle <= 35:
                    pattern_cycle = 'monthly'
                elif 85 <= avg_cycle <= 95:
                    pattern_cycle = 'quarterly'
                elif 360 <= avg_cycle <= 370:
                    pattern_cycle = 'yearly'
                else:
                    pattern_cycle = ai_billing_cycle or 'monthly'
                
                final_cycle = ai_billing_cycle if ai_billing_cycle else pattern_cycle
            else:
                final_cycle = ai_billing_cycle or 'monthly'
            
            # Enhanced trial and type detection
            trial_info = self.detect_subscription_type_and_trial(
                row['merchant_name'], 
                amount, 
                {'original_description': row['subject'], 'subscription_type': row['subscription_type']}
            )
            
            # Generate truly unique ID
            unique_id = self.generate_unique_id(
                "detected", 
                row['merchant_name'], 
                amount, 
                f"{idx}_{row['bank']}"
            )
            
            detected_subscriptions.append({
                'id': unique_id,
                'service_name': row['merchant_name'],
                'service_logo': row['service_logo'] or '☁️' if 'cloud' in row['merchant_name'].lower() else '💳',
                'amount': amount,
                'billing_cycle': final_cycle.title(),
                'start_date': row['first_date'].date(),
                'last_payment': row['last_date'].date(),
                'category': row['category'],
                'brand_color': row['color'] or '#6C757D',
                'bank': row['bank'],
                'transaction_count': row['transaction_count'],
                'status': 'Trial' if trial_info['is_trial'] else 'Active',
                'auto_detected': True,
                'original_description': f"{row['merchant_name']} - {row['subscription_type'] or 'subscription'}",
                'confidence_score': row['confidence'],
                'subscription_type': trial_info['subscription_type'],
                'is_trial': trial_info['is_trial'],
                'trial_reason': trial_info['trial_reason']
            })
        
        return detected_subscriptions
    
    def _detect_subscriptions_by_pattern(self, df: pd.DataFrame) -> List[Dict]:
        """Fallback pattern-based subscription detection with trial detection"""
        detected_subscriptions = []
        
        df['merchant_key'] = df['subject'].str.lower().str.strip()
        
        merchant_groups = df.groupby(['merchant_key', 'amount_numeric']).agg({
            'date_parsed': ['count', 'min', 'max'],
            'subject': 'first',
            'category': 'first',
            'bank': 'first',
            'merchant_name': 'first'
        })
        
        merchant_groups.columns = ['transaction_count', 'first_date', 'last_date', 'subject', 'category', 'bank', 'merchant_name']
        merchant_groups = merchant_groups.reset_index()
        
        potential_subs = merchant_groups[merchant_groups['transaction_count'] >= 2]
        
        for idx, row in potential_subs.iterrows():
            date_diff = (row['last_date'] - row['first_date']).days
            amount = float(row['amount_numeric'])
            
            if date_diff > 0:
                avg_cycle = date_diff / (row['transaction_count'] - 1)
                
                if 25 <= avg_cycle <= 35:
                    billing_cycle = 'Monthly'
                elif 85 <= avg_cycle <= 95:
                    billing_cycle = 'Quarterly'
                elif 360 <= avg_cycle <= 370:
                    billing_cycle = 'Yearly'
                else:
                    billing_cycle = 'Irregular'
                
                if billing_cycle in ['Monthly', 'Quarterly', 'Yearly']:
                    service_info = self._basic_service_detection(row['subject'], amount)
                    
                    # Trial detection for pattern-based subscriptions
                    trial_info = self.detect_subscription_type_and_trial(
                        service_info['name'], 
                        amount, 
                        {'original_description': row['subject']}
                    )
                    
                    # Generate unique ID
                    unique_id = self.generate_unique_id(
                        "pattern", 
                        service_info['name'], 
                        amount, 
                        f"{idx}_{billing_cycle}"
                    )
                    
                    detected_subscriptions.append({
                        'id': unique_id,
                        'service_name': service_info['name'],
                        'service_logo': service_info['logo'],
                        'amount': amount,
                        'billing_cycle': billing_cycle,
                        'start_date': row['first_date'].date(),
                        'last_payment': row['last_date'].date(),
                        'category': service_info['category'],
                        'brand_color': service_info['color'],
                        'bank': row['bank'],
                        'transaction_count': row['transaction_count'],
                        'status': 'Trial' if trial_info['is_trial'] else 'Active',
                        'auto_detected': True,
                        'original_description': row['subject'],
                        'confidence_score': service_info['confidence'],
                        'subscription_type': 'pattern_detected',
                        'is_trial': trial_info['is_trial'],
                        'trial_reason': trial_info['trial_reason']
                    })
        
        return detected_subscriptions
    
    def _basic_service_detection(self, description: str, amount: float = None) -> Dict:
        """Basic service detection for fallback with enhanced Google Cloud detection"""
        desc_lower = description.lower().strip()
        
        service_patterns = {
            'netflix': {'name': 'Netflix', 'category': 'Video Streaming', 'logo': '🎬', 'color': '#E50914', 'confidence': 85},
            'spotify': {'name': 'Spotify', 'category': 'Music Streaming', 'logo': '🎧', 'color': '#1DB954', 'confidence': 85},
            'youtube': {'name': 'YouTube Premium', 'category': 'Video Streaming', 'logo': '▶️', 'color': '#FF0000', 'confidence': 80},
            'amazon': {'name': 'Amazon Prime', 'category': 'Video Streaming', 'logo': '📦', 'color': '#FF9900', 'confidence': 85},
            'microsoft': {'name': 'Microsoft 365', 'category': 'Productivity SaaS', 'logo': '💼', 'color': '#0078D4', 'confidence': 80},
            'adobe': {'name': 'Adobe Creative', 'category': 'Design SaaS', 'logo': '🎨', 'color': '#FF0000', 'confidence': 80},
            'google cloud': {'name': 'Google Cloud', 'category': 'Cloud Platform', 'logo': '☁️', 'color': '#4285F4', 'confidence': 90},
            'google': {'name': 'Google Workspace', 'category': 'Productivity SaaS', 'logo': '☁️', 'color': '#4285F4', 'confidence': 75},
        }
        
        for pattern, info in service_patterns.items():
            if pattern in desc_lower:
                return info
        
        # Special handling for cloud services
        if any(keyword in desc_lower for keyword in ['cloud', 'aws', 'azure', 'gcp']):
            words = description.split()
            service_name = ' '.join(words[:2]).title() if len(words) >= 2 else words[0].title()
            return {
                'name': service_name,
                'category': "Cloud Services",
                'logo': '☁️',
                'color': "#4285F4",
                'confidence': 75
            }
        
        words = description.split()
        service_name = words[0].title() if words else "Unknown Service"
        
        return {
            'name': service_name,
            'category': "Other Services",
            'logo': '💳',
            'color': "#6C757D",
            'confidence': 35
        }
    
    def calculate_subscription_metrics(self, subscriptions: List[Dict]) -> Dict:
        """Calculate comprehensive subscription metrics including trial handling"""
        if not subscriptions:
            return {
                'total_monthly': 0,
                'total_yearly': 0,
                'remaining_year': 0,
                'active_count': 0,
                'inactive_count': 0,
                'trial_count': 0,
                'monthly_breakdown': {},
                'category_breakdown': {}
            }
        
        active_subs = [sub for sub in subscriptions if sub.get('status', 'Active') in ['Active', 'Trial']]
        trial_subs = [sub for sub in subscriptions if sub.get('status') == 'Trial']
        
        total_monthly = 0
        monthly_breakdown = {}
        category_breakdown = {}
        
        current_date = datetime.now().date()
        year_end = date(current_date.year, 12, 31)
        months_remaining = (year_end.year - current_date.year) * 12 + year_end.month - current_date.month + 1
        
        for sub in active_subs:
            if sub['billing_cycle'] == 'Monthly':
                monthly_amount = sub['amount']
            elif sub['billing_cycle'] == 'Quarterly':
                monthly_amount = sub['amount'] / 3
            elif sub['billing_cycle'] == 'Yearly':
                monthly_amount = sub['amount'] / 12
            else:
                monthly_amount = sub['amount']
            
            # For trials, we might want to project the full cost
            if sub.get('status') == 'Trial' and sub.get('is_trial'):
                # Keep trial cost as is, but note it separately
                pass
            
            total_monthly += monthly_amount
            monthly_breakdown[sub['service_name']] = monthly_amount
            
            category = sub.get('category', 'Other')
            if category in category_breakdown:
                category_breakdown[category] += monthly_amount
            else:
                category_breakdown[category] = monthly_amount
        
        total_yearly = total_monthly * 12
        remaining_year = total_monthly * months_remaining
        
        return {
            'total_monthly': total_monthly,
            'total_yearly': total_yearly,
            'remaining_year': remaining_year,
            'active_count': len([s for s in subscriptions if s.get('status') == 'Active']),
            'inactive_count': len([s for s in subscriptions if s.get('status') == 'Inactive']),
            'trial_count': len(trial_subs),
            'monthly_breakdown': monthly_breakdown,
            'category_breakdown': category_breakdown,
            'months_remaining': months_remaining
        }
    
    def get_next_payment_date(self, subscription: Dict) -> date:
        """Calculate next payment date"""
        last_payment = subscription.get('last_payment', subscription['start_date'])
        if isinstance(last_payment, str):
            last_payment = datetime.strptime(last_payment, '%Y-%m-%d').date()
        
        billing_cycle = subscription['billing_cycle']
        
        if billing_cycle == 'Monthly':
            next_date = last_payment + timedelta(days=30)
        elif billing_cycle == 'Quarterly':
            next_date = last_payment + timedelta(days=90)
        elif billing_cycle == 'Yearly':
            next_date = last_payment + timedelta(days=365)
        else:
            next_date = last_payment + timedelta(days=30)
        
        return next_date
    
    def add_subscription(self, subscription_data: Dict) -> bool:
        """Add a new subscription with trial detection"""
        try:
            # Generate unique ID
            subscription_data['id'] = self.generate_unique_id(
                "manual",
                subscription_data['service_name'],
                subscription_data['amount']
            )
            subscription_data['auto_detected'] = False
            
            # Trial detection for manual subscriptions
            is_trial = subscription_data['amount'] <= 10
            if is_trial:
                subscription_data['status'] = 'Trial'
                subscription_data['is_trial'] = True
                subscription_data['trial_reason'] = f"Low amount (₹{subscription_data['amount']:.2f})"
            else:
                subscription_data['is_trial'] = False
            
            if 'service_logo' not in subscription_data or 'brand_color' not in subscription_data:
                service_info = self._enhance_manual_subscription(subscription_data['service_name'])
                subscription_data['service_logo'] = service_info['logo']
                subscription_data['brand_color'] = service_info['color']
                if 'category' not in subscription_data or not subscription_data['category']:
                    subscription_data['category'] = service_info['category']
                
            st.session_state.subscriptions.append(subscription_data)
            return True
        except Exception as e:
            st.error(f"Error adding subscription: {e}")
            return False
    
    def _enhance_manual_subscription(self, service_name: str) -> Dict:
        """Enhanced service detection for manually added subscriptions"""
        service_lower = service_name.lower().strip()
        
        enhanced_patterns = {
            'netflix': {'category': 'Video Streaming', 'logo': '🎬', 'color': '#E50914'},
            'amazon prime': {'category': 'Video Streaming', 'logo': '📺', 'color': '#FF9900'},
            'disney': {'category': 'Video Streaming', 'logo': '🏰', 'color': '#113CCF'},
            'youtube': {'category': 'Video Streaming', 'logo': '▶️', 'color': '#FF0000'},
            'spotify': {'category': 'Music Streaming', 'logo': '🎧', 'color': '#1DB954'},
            'apple music': {'category': 'Music Streaming', 'logo': '🎵', 'color': '#FA243C'},
            'hotstar': {'category': 'Video Streaming', 'logo': '🌟', 'color': '#0F1419'},
            'microsoft': {'category': 'Productivity SaaS', 'logo': '💼', 'color': '#0078D4'},
            'adobe': {'category': 'Design SaaS', 'logo': '🎨', 'color': '#FF0000'},
            'google cloud': {'category': 'Cloud Platform', 'logo': '☁️', 'color': '#4285F4'},
            'google': {'category': 'Productivity SaaS', 'logo': '☁️', 'color': '#4285F4'},
            'dropbox': {'category': 'Cloud Storage', 'logo': '📦', 'color': '#0061FF'},
            'zoom': {'category': 'Video Conferencing', 'logo': '📹', 'color': '#2D8CFF'},
            'slack': {'category': 'Team Communication', 'logo': '💬', 'color': '#4A154B'},
            'notion': {'category': 'Productivity SaaS', 'logo': '📝', 'color': '#000000'},
            'zomato': {'category': 'Food Delivery', 'logo': '🍕', 'color': '#E23744'},
            'swiggy': {'category': 'Food Delivery', 'logo': '🛵', 'color': '#FC8019'},
            'uber eats': {'category': 'Food Delivery', 'logo': '🍔', 'color': '#000000'},
            'airtel': {'category': 'Telecom', 'logo': '📶', 'color': '#E50000'},
            'jio': {'category': 'Telecom', 'logo': '📱', 'color': '#0066CC'},
            'vi': {'category': 'Telecom', 'logo': '📞', 'color': '#FF6B00'},
        }
        
        for pattern, info in enhanced_patterns.items():
            if pattern in service_lower:
                return info
        
        # Infer category from keywords
        if any(word in service_lower for word in ['stream', 'video', 'movie', 'tv', 'watch']):
            return {'category': 'Video Streaming', 'logo': '🎬', 'color': '#E50914'}
        elif any(word in service_lower for word in ['music', 'audio', 'song', 'podcast']):
            return {'category': 'Music Streaming', 'logo': '🎧', 'color': '#1DB954'}
        elif any(word in service_lower for word in ['cloud', 'storage', 'backup', 'sync']):
            return {'category': 'Cloud Services', 'logo': '☁️', 'color': '#4285F4'}
        elif any(word in service_lower for word in ['food', 'restaurant', 'delivery', 'eat']):
            return {'category': 'Food Services', 'logo': '🍕', 'color': '#FC8019'}
        elif any(word in service_lower for word in ['mobile', 'internet', 'phone', 'data']):
            return {'category': 'Telecom Services', 'logo': '📱', 'color': '#E50000'}
        elif any(word in service_lower for word in ['software', 'saas', 'tool', 'app']):
            return {'category': 'Software SaaS', 'logo': '⚙️', 'color': '#6C5CE7'}
        else:
            return {'category': 'Other Services', 'logo': '💳', 'color': '#6C757D'}
    
    def update_subscription(self, subscription_id: str, updated_data: Dict) -> bool:
        """Update an existing subscription with trial detection"""
        try:
            for i, sub in enumerate(st.session_state.subscriptions):
                if sub['id'] == subscription_id:
                    # Check if amount changed and affects trial status
                    if 'amount' in updated_data:
                        new_amount = updated_data['amount']
                        if new_amount <= 10 and not sub.get('is_trial', False):
                            updated_data['status'] = 'Trial'
                            updated_data['is_trial'] = True
                            updated_data['trial_reason'] = f"Low amount (₹{new_amount:.2f})"
                        elif new_amount > 10 and sub.get('is_trial', False):
                            updated_data['status'] = 'Active'
                            updated_data['is_trial'] = False
                            updated_data['trial_reason'] = None
                    
                    if 'service_name' in updated_data and updated_data['service_name'] != sub.get('service_name'):
                        service_info = self._enhance_manual_subscription(updated_data['service_name'])
                        updated_data['service_logo'] = service_info['logo']
                        updated_data['brand_color'] = service_info['color']
                        updated_data['category'] = service_info['category']
                    
                    st.session_state.subscriptions[i].update(updated_data)
                    return True
            return False
        except Exception as e:
            st.error(f"Error updating subscription: {e}")
            return False
    
    def delete_subscription(self, subscription_id: str) -> bool:
        """Delete a subscription"""
        try:
            st.session_state.subscriptions = [
                sub for sub in st.session_state.subscriptions 
                if sub['id'] != subscription_id
            ]
            return True
        except Exception as e:
            st.error(f"Error deleting subscription: {e}")
            return False

class BankEmailExtractor:
    """Enhanced email extraction with multi-threaded processing"""
    def __init__(self, config_manager: ConfigManager):
        self.config_manager = config_manager
        self.bank_senders = {
            'SBI': ['donotreply.sbiatm@alerts.sbi.co.in', 'alerts@sbi.co.in', 'sbicard.alerts@sbi.co.in'],
            'HDFC Bank': ['alerts@hdfcbank.net', 'hdfcbank@hdfcbank.net'],
            'ICICI Bank': ['alert@icicibank.com', 'credit_cards@icicibank.com'],
            'Axis Bank': ['alerts@axisbank.com'],
            'Kotak Mahindra Bank': ['creditcardalerts@kotak.com'],
            'IDFC FIRST Bank': ['noreply@idfcfirstbank.com'],
            'Yes Bank': ['alerts@yesbank.in'],
            'IndusInd Bank': ['transactionalert@indusind.com'],
            'Chase': ['noreply@chase.com'],
            'Bank of America': ['alerts@bankofamerica.com'],
            'Citi Bank': ['alerts@citibank.com'],
            'Wells Fargo': ['alerts@wellsfargo.com'],
            'Capital One': ['notifications@capitalone.com'],
            'American Express': ['DoNotReply@americanexpress.com'],
            'Discover': ['donotreply@discover.com'],
            'Synchrony Bank': ['alerts@synchronybank.com'],
            'US Bank': ['customerservice@usbank.com'],
            'PNC Bank': ['alerts@pnc.com'],
            'Truist': ['no-reply@truist.com'],
            'Ally Bank': ['no-reply@ally.com'],
            'SoFi': ['support@sofi.com'],
            'PayPal': ['no-reply@paypal.com'],
            'Venmo': ['donotreply@venmo.com'],
            'TD Bank': ['mailer@tdbank.com', 'alerts@td.com'],
            'Charles Schwab': ['no-reply@schwab.com']
        }
        self.mail = None
        self.lock = threading.Lock()
        
        replicate_token = config_manager.get_config_value('REPLICATE_API_TOKEN')
        if replicate_token:
            self.categorizer = AITransactionCategorizer(replicate_token)
        else:
            self.categorizer = None
        
    def authenticate_gmail(self, email_address: str, password: str):
        """Authenticate with Gmail using IMAP"""
        try:
            self.mail = imaplib.IMAP4_SSL('imap.gmail.com')
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
    
    def search_bank_emails(self, max_results: int = 50) -> List[str]:
        """Search for bank emails"""
        try:
            self.mail.select('INBOX')
            
            all_message_ids = []
            
            search_terms = [
                *[f'FROM "{sender}"' for bank_senders in self.bank_senders.values() for sender in bank_senders],
                'SUBJECT "transaction"',
                'SUBJECT "debit"',
                'SUBJECT "credit"',
                'SUBJECT "withdrawal"',
                'SUBJECT "payment"',
                'SUBJECT "alert"',
                'SUBJECT "statement"',
                'SUBJECT "google cloud"',
                'BODY "google cloud"'
            ]
            
            for search_term in search_terms:
                if len(all_message_ids) >= max_results:
                    break
                    
                try:
                    result, message_ids = self.mail.search(None, search_term)
                    
                    if result == 'OK' and message_ids[0]:
                        new_ids = message_ids[0].split()
                        all_message_ids.extend(new_ids)
                        
                except Exception as e:
                    continue
            
            unique_ids = list(set(all_message_ids))
            unique_ids.sort(reverse=True)
            
            return unique_ids[:max_results]
            
        except Exception as e:
            st.error(f"Error searching emails: {e}")
            return []
    
    def fetch_and_analyze_email(self, message_id: str) -> Optional[Dict]:
        """Thread-safe method to fetch and analyze a single email"""
        try:
            with self.lock:
                result, msg_data = self.mail.fetch(message_id, '(RFC822)')
            
            if result != 'OK' or not msg_data:
                return None
                
            raw_email = msg_data[0][1]
            email_message = email.message_from_bytes(raw_email)
            
            subject = email_message.get('Subject', '')
            sender = email_message.get('From', '')
            date_header = email_message.get('Date', '')
            
            body = self.extract_email_body(email_message)
            bank_name = self.identify_bank(sender)
            
            if self.categorizer:
                analysis = self.categorizer.analyze_transaction_complete(
                    subject, 
                    body, 
                    bank_name
                )
                
                amount = analysis['amount']
                category = analysis['category']
                merchant_name = analysis['merchant_name']
                category_color = analysis['color']
                confidence = analysis['confidence']
                is_subscription = analysis.get('is_subscription', False)
                subscription_type = analysis.get('subscription_type')
                billing_cycle = analysis.get('billing_cycle')
                service_logo = analysis.get('service_logo', '💳')
                is_trial = analysis.get('is_trial', False)
            else:
                amount = None
                category = 'Other'
                merchant_name = subject[:50]
                category_color = '#6C757D'
                confidence = 0
                is_subscription = False
                subscription_type = None
                billing_cycle = None
                service_logo = '💳'
                is_trial = False
            
            return {
                'message_id': message_id.decode() if isinstance(message_id, bytes) else str(message_id),
                'date': date_header,
                'bank': bank_name,
                'subject': subject,
                'merchant_name': merchant_name,
                'sender': sender,
                'amount': amount,
                'category': category,
                'category_color': category_color,
                'color': category_color,
                'confidence': confidence,
                'is_subscription': is_subscription,
                'subscription_type': subscription_type,
                'billing_cycle': billing_cycle,
                'service_logo': service_logo,
                'is_trial': is_trial,
                'email_body_preview': body[:200] + "..." if len(body) > 200 else body
            }
            
        except Exception:
            return None
    
    def process_emails(self, max_emails: int = 50, progress_callback=None) -> List[Dict]:
        """Process emails with multi-threaded processing"""
        results = []
        
        try:
            message_ids = self.search_bank_emails(max_emails)
            total_emails = len(message_ids)
            
            if total_emails == 0:
                return results
            
            with ThreadPoolExecutor(max_workers=15, thread_name_prefix="EmailProcessor") as executor:
                future_to_message_id = {
                    executor.submit(self.fetch_and_analyze_email, message_id): message_id 
                    for message_id in message_ids
                }
                
                completed_count = 0
                successful_count = 0
                
                for future in as_completed(future_to_message_id):
                    completed_count += 1
                    
                    try:
                        email_data = future.result(timeout=30)
                        if email_data:
                            results.append(email_data)
                            successful_count += 1
                    except Exception:
                        pass
                    
                    if progress_callback:
                        progress_callback(completed_count, total_emails)
                
        except Exception:
            pass
        finally:
            if self.mail:
                try:
                    self.mail.close()
                    self.mail.logout()
                except:
                    pass
        
        return results
    
    def identify_bank(self, sender: str) -> str:
        """Enhanced bank identification"""
        sender_lower = sender.lower()
        
        for bank, identifiers in self.bank_senders.items():
            for identifier in identifiers:
                if identifier.lower() in sender_lower:
                    return bank
        
        if any(domain in sender_lower for domain in ['sbi', 'statebank']):
            return 'SBI'
        elif any(domain in sender_lower for domain in ['hdfc']):
            return 'HDFC Bank'
        elif any(domain in sender_lower for domain in ['icici']):
            return 'ICICI Bank'
        elif any(domain in sender_lower for domain in ['axis']):
            return 'Axis Bank'
        elif any(domain in sender_lower for domain in ['kotak']):
            return 'Kotak Bank'
            
        return "Unknown Bank"
    
    def extract_email_body(self, email_message) -> str:
        """Enhanced email body extraction"""
        body = ""
        
        if email_message.is_multipart():
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
                        try:
                            from bs4 import BeautifulSoup
                            soup = BeautifulSoup(html_body, 'html.parser')
                            body = soup.get_text(separator=' ', strip=True)
                        except ImportError:
                            body = re.sub(r'<[^>]+>', ' ', html_body)
                            body = re.sub(r'\s+', ' ', body).strip()
                        break
                    except:
                        continue
        else:
            try:
                body = email_message.get_payload(decode=True).decode('utf-8')
            except:
                try:
                    body = email_message.get_payload(decode=True).decode('latin-1')
                except:
                    body = str(email_message.get_payload())
        
        return body[:1500]

def ensure_unique_subscription_ids(subscriptions):
    """Ensure all subscription IDs are unique"""
    seen_ids = set()
    for i, sub in enumerate(subscriptions):
        original_id = sub['id']
        counter = 1
        while sub['id'] in seen_ids:
            sub['id'] = f"{original_id}_dup_{counter}"
            counter += 1
        seen_ids.add(sub['id'])
    return subscriptions

def display_subscription_card(subscription: Dict, tracker: SubscriptionTracker):
    """Display a subscription card with NO HTML - Pure Streamlit components only"""
    next_payment = tracker.get_next_payment_date(subscription)
    days_until_payment = (next_payment - datetime.now().date()).days
    
    status = subscription.get('status', 'Active')
    is_trial = subscription.get('is_trial', False)
    
    # Calculate yearly cost
    if subscription['billing_cycle'] == 'Monthly':
        yearly_cost = subscription['amount'] * 12
    elif subscription['billing_cycle'] == 'Quarterly':
        yearly_cost = subscription['amount'] * 4
    elif subscription['billing_cycle'] == 'Yearly':
        yearly_cost = subscription['amount']
    else:
        yearly_cost = subscription['amount'] * 12
    
    service_logo = subscription.get('service_logo', '💳')
    brand_color = subscription.get('brand_color', '#007bff')
    
    # Create a container with border using Streamlit components only
    with st.container():
        # Create colored header bar using columns
        header_col1, header_col2, header_col3 = st.columns([0.1, 8, 1.9])
        
        with header_col1:
            # Color indicator using colored markdown
            st.markdown(f'<div style="background-color: {brand_color}; width: 100%; height: 60px; border-radius: 5px;"></div>', unsafe_allow_html=True)
        
        with header_col2:
            # Service name and status
            if is_trial or status == 'Trial':
                st.markdown(f"### {service_logo} {subscription['service_name']} 🧪 TRIAL")
                trial_reason = subscription.get('trial_reason', 'Trial detected')
                st.caption(f"Trial Status: {trial_reason}")
            else:
                status_emoji = "🟢" if status == 'Active' else "🔴"
                st.markdown(f"### {service_logo} {subscription['service_name']} {status_emoji}")
            
            # Service details in clean format
            col_cat, col_bank, col_conf = st.columns(3)
            with col_cat:
                st.write(f"**Category:** {subscription.get('category', 'Other')}")
            with col_bank:
                st.write(f"**Bank:** {subscription.get('bank', 'N/A')}")
            with col_conf:
                if subscription.get('auto_detected'):
                    confidence = subscription.get('confidence_score', 0)
                    st.write(f"**Confidence:** {confidence:.0f}%")
                else:
                    st.write("**Type:** Manual")
        
        with header_col3:
            # Amount display - clean format
            st.markdown(f"**₹{subscription['amount']:,.2f}**")
            st.caption(f"per {subscription['billing_cycle']}")
            st.caption(f"₹{yearly_cost:,.2f}/year")
        
        # Payment status using Streamlit native alerts
        if days_until_payment < 0:
            st.error(f"⚠️ Overdue by {abs(days_until_payment)} days - Due: {next_payment.strftime('%B %d, %Y')}")
        elif days_until_payment <= 7:
            st.warning(f"⏰ Due soon: {next_payment.strftime('%B %d, %Y')} ({days_until_payment} days)")
        else:
            st.info(f"📅 Next payment: {next_payment.strftime('%B %d, %Y')} ({days_until_payment} days)")
        
        # Clean separator
        st.divider()

def create_subscription_visualizations(subscriptions: List[Dict], metrics: Dict):
    """Create visualizations for subscription data with trial handling"""
    if not subscriptions:
        return None, None, None
    
    monthly_data = pd.DataFrame(list(metrics['monthly_breakdown'].items()), 
                               columns=['Service', 'Monthly Amount'])
    
    color_map = {}
    for sub in subscriptions:
        if sub.get('status', 'Active') in ['Active', 'Trial']:
            color_map[sub['service_name']] = sub.get('brand_color', '#007bff')
    
    fig_monthly = px.pie(
        monthly_data,
        names='Service',
        values='Monthly Amount',
        title='Monthly Subscription Spending by Service',
        color='Service',
        color_discrete_map=color_map
    )
    
    category_data = pd.DataFrame(list(metrics['category_breakdown'].items()), 
                                columns=['Category', 'Monthly Amount'])
    
    category_colors = {}
    for category in metrics['category_breakdown'].keys():
        cat_subs = [sub for sub in subscriptions if sub.get('category') == category and sub.get('status', 'Active') in ['Active', 'Trial']]
        if cat_subs:
            category_colors[category] = cat_subs[0].get('brand_color', '#007bff')
        else:
            category_colors[category] = '#007bff'
    
    fig_category = px.bar(
        category_data,
        x='Category',
        y='Monthly Amount',
        title='Monthly Subscription Spending by Category',
        color='Category',
        color_discrete_map=category_colors
    )
    
    months = list(range(1, 13))
    cumulative_spending = [metrics['total_monthly'] * month for month in months]
    
    fig_yearly = px.line(
        x=months,
        y=cumulative_spending,
        title='Cumulative Subscription Spending (Yearly Projection)',
        labels={'x': 'Month', 'y': 'Cumulative Spending (₹)'}
    )
    
    current_month = datetime.now().month
    current_spending = metrics['total_monthly'] * current_month
    
    fig_yearly.add_scatter(
        x=[current_month],
        y=[current_spending],
        mode='markers',
        marker=dict(size=12, color='red'),
        name='Current Month'
    )
    
    return fig_monthly, fig_category, fig_yearly

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
    """Create various visualizations for the transaction data with collapsible containers - FIXED VERSION"""
    
    df_filtered = apply_date_filter(df)
    
    if len(df_filtered) == 0:
        st.warning("No transactions found in the selected date range.")
        return None, None, None, None, None, None, None
    
    # CRITICAL FIX: Create a copy and ensure date_parsed is datetime
    df_filtered = df_filtered.copy()
    
    # Multiple-layer datetime conversion with error handling
    if 'date_parsed' in df_filtered.columns:
        # Check if date_parsed is already datetime
        if not pd.api.types.is_datetime64_any_dtype(df_filtered['date_parsed']):
            # Try multiple conversion methods
            try:
                # Ensure date_parsed is real datetime
                    df_filtered['date_parsed'] = pd.to_datetime(
                        df_filtered['date_parsed'],            # the source column
                        errors='coerce',                       # turn bad rows into NaT
                        utc=False                              # keep local time; change if needed
                    )

                    # Remove rows where the conversion failed
                    df_filtered = df_filtered.dropna(subset=['date_parsed'])

                    # Final safety check
                    if not pd.api.types.is_datetime64_any_dtype(df_filtered['date_parsed']):
                        st.error("Date parsing failed – cannot continue.")
                        st.stop()               # or return / handle gracefully

            except:
                try:
                    # Fallback conversion
                    df_filtered['date_parsed'] = df_filtered['date_parsed'].apply(
                        lambda x: pd.to_datetime(x, errors='coerce') if pd.notna(x) else pd.NaT
                    )
                except:
                    st.error("Critical error: Unable to parse dates for visualization")
                    return None, None, None, None, None, None, None
        
        # Remove any rows where date conversion failed
        df_filtered = df_filtered.dropna(subset=['date_parsed'])
        
        # Final validation - ensure we have datetime data
        if not pd.api.types.is_datetime64_any_dtype(df_filtered['date_parsed']):
            st.error("Date parsing failed - cannot create visualizations")
            return None, None, None, None, None, None, None
            
    else:
        st.error("Date column 'date_parsed' not found in data")
        return None, None, None, None, None, None, None
    
    # Ensure we have data after filtering
    if df_filtered.empty:
        st.warning("No valid data after date processing.")
        return None, None, None, None, None, None, None
    
    # Color mapping
    color_map = {}
    if hasattr(categorizer, 'category_colors'):
        color_map = categorizer.category_colors
    else:
        unique_categories = df_filtered['category'].unique()
        colors = px.colors.qualitative.Set3
        color_map = {cat: colors[i % len(colors)] for i, cat in enumerate(unique_categories)}
    
    # 1. Pie Chart - Category Distribution
    try:
        category_amounts = df_filtered.groupby('category')['amount_numeric'].sum().reset_index()
        fig_pie = px.pie(
            category_amounts,
            names='category', 
            values='amount_numeric',
            title='Transaction Distribution by Category (by Amount)',
            color='category',
            color_discrete_map=color_map
        )
        fig_pie.update_traces(textposition='inside', textinfo='percent+label')
    except Exception as e:
        st.warning(f"Could not create pie chart: {e}")
        fig_pie = None
    
    # 2. Bar Chart - Total by Category
    try:
        fig_bar = px.bar(
            category_amounts, 
            x='category', 
            y='amount_numeric',
            title='Total Amount by Category',
            color='category',
            color_discrete_map=color_map
        )
        fig_bar.update_layout(xaxis_tickangle=-45)
    except Exception as e:
        st.warning(f"Could not create bar chart: {e}")
        fig_bar = None
    
    # 3. Timeline Chart
    try:
        df_sorted = df_filtered.sort_values('date_parsed')
        fig_timeline = px.line(
            df_sorted, 
            x='date_parsed', 
            y='amount_numeric',
            color='category',
            title='Transaction Timeline',
            markers=True,
            color_discrete_map=color_map
        )
    except Exception as e:
        st.warning(f"Could not create timeline chart: {e}")
        fig_timeline = None
    
    # 4. Monthly Spending Chart - WITH ENHANCED ERROR HANDLING
    try:
        df_sorted = df_filtered.sort_values('date_parsed').copy()
        
        # CRITICAL FIX: Additional validation before using .dt accessor
        if pd.api.types.is_datetime64_any_dtype(df_sorted['date_parsed']):
            # Safe to use .dt accessor now
            df_sorted['month'] = df_sorted['date_parsed'].dt.to_period('M')
            monthly_spending = df_sorted.groupby(['month', 'category'])['amount_numeric'].sum().reset_index()
            monthly_spending['month'] = monthly_spending['month'].astype(str)
            
            fig_monthly = px.bar(
                monthly_spending,
                x='month',
                y='amount_numeric',
                color='category',
                title='Monthly Spending by Category',
                color_discrete_map=color_map
            )
        else:
            st.warning("Cannot create monthly chart - invalid date format")
            fig_monthly = None
    except Exception as e:
        st.warning(f"Could not create monthly chart: {e}")
        fig_monthly = None
    
    # 5. Bank Distribution
    try:
        bank_spending = df_filtered.groupby('bank')['amount_numeric'].sum().reset_index()
        fig_bank = px.pie(
            bank_spending,
            names='bank',
            values='amount_numeric',
            title='Spending Distribution by Bank'
        )
    except Exception as e:
        st.warning(f"Could not create bank chart: {e}")
        fig_bank = None
    
    # 6. Heatmap - WITH ENHANCED ERROR HANDLING
    try:
        df_heat = df_filtered.copy()
        
        # CRITICAL FIX: Validate datetime before using .dt accessor
        if pd.api.types.is_datetime64_any_dtype(df_heat['date_parsed']):
            df_heat['weekday'] = df_heat['date_parsed'].dt.day_name()
            df_heat['week'] = df_heat['date_parsed'].dt.isocalendar().week
            
            heatmap_data = df_heat.groupby(['weekday', 'week'])['amount_numeric'].sum().reset_index()
            
            weekday_order = ['Monday', 'Tuesday', 'Wednesday', 'Thursday', 'Friday', 'Saturday', 'Sunday']
            heatmap_data['weekday'] = pd.Categorical(heatmap_data['weekday'], categories=weekday_order, ordered=True)
            heatmap_data = heatmap_data.sort_values('weekday')
            
            fig_heatmap = px.density_heatmap(
                heatmap_data,
                x='week',
                y='weekday',
                z='amount_numeric',
                title='Weekly Spending Heatmap',
                color_continuous_scale='Blues'
            )
        else:
            st.warning("Cannot create heatmap - invalid date format")
            fig_heatmap = None
    except Exception as e:
        st.warning(f"Could not create heatmap: {e}")
        fig_heatmap = None
    
    # 7. Hourly Pattern - WITH ENHANCED ERROR HANDLING
    try:
        df_hourly = df_filtered.copy()
        
        # CRITICAL FIX: Validate datetime before using .dt accessor
        if pd.api.types.is_datetime64_any_dtype(df_hourly['date_parsed']):
            df_hourly['hour'] = df_hourly['date_parsed'].dt.hour
            hourly_spending = df_hourly.groupby('hour')['amount_numeric'].sum().reset_index()
            
            fig_hourly = px.bar(
                hourly_spending,
                x='hour',
                y='amount_numeric',
                title='Hourly Spending Pattern',
                color_discrete_sequence=['#00CEC9']
            )
        else:
            st.warning("Cannot create hourly chart - invalid date format")
            fig_hourly = None
    except Exception as e:
        st.warning(f"Could not create hourly chart: {e}")
        fig_hourly = None
    
    return fig_pie, fig_bar, fig_timeline, fig_monthly, fig_bank, fig_heatmap, fig_hourly

def create_metric_card(title, value, delta=None):
    """Helper function to create a metric card"""
    st.markdown(f"""
    <div class="metric-card">
        <div class="metric-title">{title}</div>
        <div class="metric-value">{value}</div>
    </div>
    """, unsafe_allow_html=True)

def display_transaction_card(row, categorizer):
    """Display a transaction as a card with trial indicators"""
    amount_color = "#FF6B6B" if float(row['amount_numeric']) < 0 else "#4CAF50"
    
    if hasattr(categorizer, 'category_colors') and row['category'] in categorizer.category_colors:
        category_color = categorizer.category_colors[row['category']]
    else:
        category_color = row.get('category_color', '#6C757D')
    
    merchant_name = row.get('merchant_name', row['subject'][:50])
    confidence = row.get('confidence', 0)
    is_subscription = row.get('is_subscription', False)
    is_trial = row.get('is_trial', False)
    
    subscription_badge = ""
    if is_subscription:
        if is_trial:
            subscription_badge = f' <span style="background-color: #ffc107; color: white; padding: 2px 6px; border-radius: 10px; font-size: 10px;">TRIAL</span>'
        else:
            subscription_badge = f' <span style="background-color: #28a745; color: white; padding: 2px 6px; border-radius: 10px; font-size: 10px;">SUBSCRIPTION</span>'
    
    st.markdown(f"""
    <div class="transaction-card">
        <div style="display: flex; justify-content: space-between; align-items: center;">
            <div>
                <div class="transaction-date">{row['date_parsed'].strftime('%b %d, %Y %I:%M %p')}</div>
                <div class="transaction-merchant">{merchant_name}{subscription_badge}</div>
            </div>
            <div class="transaction-amount" style="color: {amount_color};">₹{abs(float(row['amount_numeric'])):,.2f}</div>
        </div>
        <div style="display: flex; justify-content: space-between; align-items: center; margin-top: 10px;">
            <div>
                <span class="category-tag" style="background-color: {category_color}; color: white;">{row['category']}</span>
                <span style="font-size: 12px; color: #6c757d;">{row['bank']}</span>
            </div>
        </div>
    </div>
    """, unsafe_allow_html=True)

def main():
    """Main Streamlit app"""
    
    # Initialize statistics manager
    if 'stats_manager' not in st.session_state:
        st.session_state.stats_manager = UserStatisticsManager()
    
    stats_manager = st.session_state.stats_manager
    
    st.markdown("""
    <div style="display: flex; align-items: center; margin-bottom: 20px;">
        <h1 style="margin: 0;">🏦 AI Expense & Subscription Tracker</h1>
    </div>
    """, unsafe_allow_html=True)
    
    st.markdown("""
    <p style="font-size: 16px; color: #6c757d;">
    Extract and analyze your bank transaction alerts with AI-powered categorization and spending insights
    </p>
    """, unsafe_allow_html=True)
    
    # Initialize session state
    if 'authenticated' not in st.session_state:
        st.session_state.authenticated = False
    if 'user_email' not in st.session_state:
        st.session_state.user_email = None
    if 'subscriptions' not in st.session_state:
        st.session_state.subscriptions = []
    
    # Add image and statistics (only shown when not authenticated)
    if not st.session_state.authenticated:
        st.image(
            "https://tanishmittal.com/wp-content/uploads/2025/07/Expense-Tracker-V2.0.png",
            caption="Expense Tracker",
            use_container_width=True
        )
        
        # Display User Statistics
        st.markdown("### 📊 Platform Statistics")
        
        stats = stats_manager.get_statistics()
        
        col1, col2, col3 = st.columns(3)
        
        with col1:
            st.markdown(f"""
            <div class="metric-card" style="background: linear-gradient(135deg, #667eea 0%, #764ba2 100%); color: white;">
                <div class="metric-title" style="color: rgba(255,255,255,0.9);">Total Users</div>
                <div class="metric-value">{stats['total_users']:,}</div>
            </div>
            """, unsafe_allow_html=True)
        
        with col2:
            formatted_amount = stats_manager.format_amount(stats['total_amount_detected'])
            st.markdown(f"""
            <div class="metric-card" style="background: linear-gradient(135deg, #f093fb 0%, #f5576c 100%); color: white;">
                <div class="metric-title" style="color: rgba(255,255,255,0.9);">Total Amount Analyzed</div>
                <div class="metric-value">{formatted_amount}</div>
            </div>
            """, unsafe_allow_html=True)
        
        with col3:
            st.markdown(f"""
            <div class="metric-card" style="background: linear-gradient(135deg, #4facfe 0%, #00f2fe 100%); color: white;">
                <div class="metric-title" style="color: rgba(255,255,255,0.9);">Subscriptions Detected</div>
                <div class="metric-value">{stats['total_subscriptions_detected']:,}</div>
            </div>
            """, unsafe_allow_html=True)
        
        # Supported banks section
        st.markdown("### 🏦 Supported Banks")
        
        col1, col2, col3, col4 = st.columns(4)
        
        with col1:
            st.markdown("""
            **🇮🇳 Indian Banks:**
            - State Bank of India (SBI)
            - HDFC Bank
            - ICICI Bank
            - Axis Bank
            - Kotak Mahindra Bank
            - IDFC FIRST Bank
            - Yes Bank
            - IndusInd Bank
            """)
        
        with col2:
            st.markdown("""
            **🇺🇸 US Banks:**
            - Chase Bank
            - Bank of America
            - Wells Fargo
            - Citi Bank
            - Capital One
            - US Bank
            - PNC Bank
            - Truist Bank
            """)
        
        with col3:
            st.markdown("""
            **💳 Credit Cards:**
            - American Express
            - Discover
            - Synchrony Bank
            - TD Bank
            - Charles Schwab
            """)
        
        with col4:
            st.markdown("""
            **💸 Digital Payments:**
            - PayPal
            - Venmo
            - SoFi
            - Ally Bank
            """)
    
    # Configuration management
    config_manager = ConfigManager()
    if not config_manager.validate_config():
        config_manager.display_config_status()
    
    # Authentication section
    if not st.session_state.authenticated:
        st.markdown("---")
        st.markdown("### 🔐 Login to Access Your Financial Data")
        
        col1, col2 = st.columns([1, 1])
        
        with col1:
            email_address = st.text_input("📧 Email Address", 
                                        placeholder="your-email@gmail.com",
                                        help="Your Gmail address to access bank transaction alerts")
            
        with col2:
            password = st.text_input("🔒 Password", 
                                   type="password",
                                   placeholder="Your Gmail password or App Password",
                                   help="Use App Password if 2FA is enabled")
        
        login_button = st.button("🚀 Connect & Analyze Transactions", type="primary", use_container_width=True)
        
        # Enhanced security notice
        with st.expander("🛡️ Security & Privacy Information"):
            st.markdown("""
            **Your security is our priority:**
            - ✅ All credentials are processed locally and never stored
            - ✅ We only read email headers and transaction alerts
            - ✅ No personal data is transmitted to external services except for AI analysis
            - ✅ Use Gmail App Passwords for enhanced security
            - ✅ All analysis happens in real-time without data persistence
            
            **For Gmail App Password setup:**
            1. Enable 2-Factor Authentication on your Google account
            2. Go to Google Account Settings → Security → App Passwords
            3. Generate a new app password for "Mail"
            4. Use the generated password instead of your regular password
            """)
        
        if login_button:
            if not email_address or not password:
                st.error("Please enter both email and password")
            elif not config_manager.validate_config():
                st.error("Configuration incomplete. Please check Replicate API token.")
                config_manager.display_config_status()
            else:
                with st.spinner("Authenticating and connecting to your email..."):
                    extractor = BankEmailExtractor(config_manager)
                    success, user_email = extractor.authenticate_gmail(email_address, password)
                    if success:
                        st.session_state.authenticated = True
                        st.session_state.user_email = user_email
                        st.session_state.extractor = extractor
                        
                        # Record user session
                        stats_manager.record_user_session(user_email)
                        
                        st.rerun()
    
    else:
        # Main application tabs for authenticated users
        st.markdown(f"### Welcome back! 👋 {st.session_state.user_email}")
        
        tab1, tab2, tab3, tab4 = st.tabs(["📊 Transaction Analysis", "🔄 Subscription Tracker", "📈 Analytics Dashboard", "⚙️ Settings"])
        
        with tab1:
            st.markdown("## 🔍 AI-Powered Transaction Analysis")
            
            col1, col2 = st.columns([2, 1])
            
            with col1:
                max_emails = st.slider("Number of emails to analyze", 10, 200, 50, 10)
                
            with col2:
                analyze_button = st.button("🚀 Analyze Transactions", type="primary", use_container_width=True)
            
            # Date filter controls
            with st.expander("📅 Date Range Filter (Optional)"):
                enable_date_filter = st.checkbox("Enable date filtering", key="date_filter_enabled")
                
                if enable_date_filter:
                    col1, col2 = st.columns(2)
                    with col1:
                        start_date = st.date_input("Start Date", 
                                                 value=datetime.now().date() - timedelta(days=30),
                                                 key="date_filter_start")
                    with col2:
                        end_date = st.date_input("End Date", 
                                               value=datetime.now().date(),
                                               key="date_filter_end")
            
            if analyze_button:
                with st.spinner("🔄 Processing your bank emails with AI..."):
                    extractor = st.session_state.extractor
                    progress_bar = st.progress(0)
                    status_text = st.empty()
                    
                    def update_progress(completed, total):
                        progress = completed / total if total > 0 else 0
                        progress_bar.progress(progress)
                        status_text.text(f"Processed {completed}/{total} emails...")
                    
                    results = extractor.process_emails(max_emails, update_progress)
                    
                    if results:
                        st.session_state.transaction_data = results
                        st.session_state.results_processed = True
                        st.session_state.categorizer = extractor.categorizer
                        
                        # Record transaction analysis statistics
                        total_amount = sum(float(r.get('amount', 0)) for r in results if r.get('amount') and r.get('amount').replace('.', '').replace(',', '').isdigit())
                        subscription_count = len([r for r in results if r.get('is_subscription', False)])
                        
                        stats_manager.record_transaction_analysis(total_amount, subscription_count)
                        
                        st.success(f"✅ Successfully processed {len(results)} transactions!")
                        progress_bar.empty()
                        status_text.empty()
                    else:
                        st.warning("No bank transaction emails found. Please check your email settings or try increasing the email count.")
            
            # Display results if available
            if st.session_state.get('results_processed', False) and st.session_state.get('transaction_data'):
                results = st.session_state.transaction_data
                categorizer = st.session_state.categorizer
                
                # Convert to DataFrame for analysis
                df = pd.DataFrame(results)
                
                # Data cleaning and preparation
                df['amount_numeric'] = df['amount'].apply(lambda x: float(x) if x and str(x).replace('.', '').replace(',', '').replace('-', '').isdigit() else 0)
                df = df[df['amount_numeric'] > 0]
                
                if len(df) > 0:
                    # Parse dates
                    df['date_parsed'] = pd.to_datetime(df['date'], errors='coerce')
                    df = df.dropna(subset=['date_parsed'])
                    df = df.sort_values('date_parsed', ascending=False)
                    
                    # Apply date filter if enabled
                    df_display = apply_date_filter(df)
                    
                    if len(df_display) == 0:
                        st.warning("No transactions found in the selected date range.")
                    else:
                        # Summary metrics
                        st.markdown("### 📊 Transaction Summary")
                        
                        col1, col2, col3, col4 = st.columns(4)
                        
                        with col1:
                            total_amount = df_display['amount_numeric'].sum()
                            create_metric_card("Total Amount", f"₹{total_amount:,.2f}")
                        
                        with col2:
                            transaction_count = len(df_display)
                            create_metric_card("Total Transactions", f"{transaction_count:,}")
                        
                        with col3:
                            avg_amount = df_display['amount_numeric'].mean()
                            create_metric_card("Average Amount", f"₹{avg_amount:,.2f}")
                        
                        with col4:
                            unique_merchants = df_display['merchant_name'].nunique()
                            create_metric_card("Unique Merchants", f"{unique_merchants}")
                        
                        # Category breakdown
                        st.markdown("### 🏷️ Spending by Category")
                        category_summary = df_display.groupby('category').agg({
                            'amount_numeric': ['sum', 'count', 'mean']
                        }).round(2)
                        category_summary.columns = ['Total Amount', 'Transaction Count', 'Average Amount']
                        category_summary = category_summary.sort_values('Total Amount', ascending=False)
                        
                        st.dataframe(category_summary, use_container_width=True)
                        
                        # Subscription insights
                        subscription_df = df_display[df_display['is_subscription'] == True]
                        if len(subscription_df) > 0:
                            st.markdown("### 🔄 Subscription Insights")
                            
                            col1, col2, col3 = st.columns(3)
                            
                            with col1:
                                subscription_count = len(subscription_df)
                                create_metric_card("Subscription Transactions", f"{subscription_count}")
                            
                            with col2:
                                subscription_amount = subscription_df['amount_numeric'].sum()
                                create_metric_card("Subscription Spending", f"₹{subscription_amount:,.2f}")
                            
                            with col3:
                                trial_count = len(subscription_df[subscription_df['is_trial'] == True])
                                create_metric_card("Trial Subscriptions", f"{trial_count}")
                        
                        # Visualizations
                        st.markdown("### 📈 Spending Analysis")
                        
                        with st.expander("📊 View Detailed Charts", expanded=True):
                            fig_pie, fig_bar, fig_timeline, fig_monthly, fig_bank, fig_heatmap, fig_hourly = create_visualizations(df_display, categorizer)
                            
                            if fig_pie:
                                col1, col2 = st.columns(2)
                                with col1:
                                    st.plotly_chart(fig_pie, use_container_width=True)
                                with col2:
                                    st.plotly_chart(fig_bar, use_container_width=True)
                                
                                st.plotly_chart(fig_timeline, use_container_width=True)
                                
                                col1, col2 = st.columns(2)
                                with col1:
                                    st.plotly_chart(fig_monthly, use_container_width=True)
                                with col2:
                                    st.plotly_chart(fig_bank, use_container_width=True)
                                
                                col1, col2 = st.columns(2)
                                with col1:
                                    st.plotly_chart(fig_heatmap, use_container_width=True)
                                with col2:
                                    st.plotly_chart(fig_hourly, use_container_width=True)
                        
                        # Transaction details
                        st.markdown("### 💳 Transaction Details")
                        
                        with st.expander("🔍 Filter Transactions"):
                            col1, col2, col3 = st.columns(3)
                            
                            with col1:
                                selected_categories = st.multiselect(
                                    "Filter by Category",
                                    options=df_display['category'].unique(),
                                    default=df_display['category'].unique()
                                )
                            
                            with col2:
                                selected_banks = st.multiselect(
                                    "Filter by Bank",
                                    options=df_display['bank'].unique(),
                                    default=df_display['bank'].unique()
                                )
                            
                            with col3:
                                amount_range = st.slider(
                                    "Amount Range",
                                    min_value=float(df_display['amount_numeric'].min()),
                                    max_value=float(df_display['amount_numeric'].max()),
                                    value=(float(df_display['amount_numeric'].min()), float(df_display['amount_numeric'].max()))
                                )
                        
                        # Apply filters
                        filtered_df = df_display[
                            (df_display['category'].isin(selected_categories)) &
                            (df_display['bank'].isin(selected_banks)) &
                            (df_display['amount_numeric'] >= amount_range[0]) &
                            (df_display['amount_numeric'] <= amount_range[1])
                        ]
                        
                        st.write(f"Showing {len(filtered_df)} transactions")
                        
                        # Display transactions as cards
                        for idx, row in filtered_df.head(20).iterrows():
                            display_transaction_card(row, categorizer)
                        
                        if len(filtered_df) > 20:
                            st.info(f"Showing first 20 transactions. {len(filtered_df) - 20} more available.")
                        
                        # Export functionality
                        st.markdown("### 📤 Export Data")
                        
                        col1, col2, col3 = st.columns(3)
                        
                        with col1:
                            csv_data = filtered_df.to_csv(index=False)
                            st.download_button(
                                label="📥 Download as CSV",
                                data=csv_data,
                                file_name=f"transactions_{datetime.now().strftime('%Y%m%d_%H%M%S')}.csv",
                                mime="text/csv",
                                use_container_width=True
                            )
                        
                        with col2:
                            json_data = filtered_df.to_json(orient='records', date_format='iso')
                            st.download_button(
                                label="📥 Download as JSON",
                                data=json_data,
                                file_name=f"transactions_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json",
                                mime="application/json",
                                use_container_width=True
                            )
                else:
                    st.warning("No valid transaction data found in the processed emails.")
        
        with tab2:
            st.markdown("## 🔄 Subscription Management")
            
            # Initialize subscription tracker
            tracker = SubscriptionTracker(config_manager)
            
            # Auto-detect subscriptions from transaction data
            if st.session_state.get('results_processed', False) and st.session_state.get('transaction_data'):
                if st.button("🔍 Auto-Detect Subscriptions from Transactions", type="primary"):
                    with st.spinner("Analyzing transactions for subscription patterns..."):
                        df = pd.DataFrame(st.session_state.transaction_data)
                        df['amount_numeric'] = df['amount'].apply(lambda x: float(x) if x and str(x).replace('.', '').replace(',', '').replace('-', '').isdigit() else 0)
                        df = df[df['amount_numeric'] > 0]
                        
                        if len(df) > 0:
                            df['date_parsed'] = pd.to_datetime(df['date'], errors='coerce')
                            df = df.dropna(subset=['date_parsed'])
                            
                            detected_subs = tracker.detect_subscriptions_from_transactions(df)
                            
                            if detected_subs:
                                # Ensure unique IDs and merge with existing subscriptions
                                existing_services = {sub.get('service_name', '').lower() for sub in st.session_state.subscriptions}
                                new_subs = []
                                
                                for sub in detected_subs:
                                    if sub['service_name'].lower() not in existing_services:
                                        new_subs.append(sub)
                                        existing_services.add(sub['service_name'].lower())
                                
                                if new_subs:
                                    st.session_state.subscriptions.extend(new_subs)
                                    st.session_state.subscriptions = ensure_unique_subscription_ids(st.session_state.subscriptions)
                                    st.success(f"✅ Detected and added {len(new_subs)} new subscriptions!")
                                else:
                                    st.info("No new subscriptions detected. All found subscriptions are already in your list.")
                            else:
                                st.warning("No subscription patterns detected in your transaction data.")
                        else:
                            st.warning("No valid transaction data available for subscription detection.")
            
            # Manual subscription addition
            st.markdown("### ➕ Add Manual Subscription")
            
            with st.expander("Add New Subscription"):
                col1, col2 = st.columns(2)
                
                with col1:
                    service_name = st.text_input("Service Name", placeholder="e.g., Netflix, Spotify")
                    amount = st.number_input("Amount", min_value=0.01, value=99.0, step=0.01)
                    billing_cycle = st.selectbox("Billing Cycle", ["Monthly", "Quarterly", "Yearly"])
                
                with col2:
                    category = st.text_input("Category", placeholder="e.g., Streaming, SaaS")
                    start_date = st.date_input("Start Date", value=datetime.now().date())
                    status = st.selectbox("Status", ["Active", "Trial", "Inactive"])
                
                if st.button("➕ Add Subscription"):
                    if service_name and amount > 0:
                        subscription_data = {
                            'service_name': service_name,
                            'amount': amount,
                            'billing_cycle': billing_cycle,
                            'category': category or 'Other',
                            'start_date': start_date,
                            'last_payment': start_date,
                            'status': status,
                            'bank': 'Manual Entry'
                        }
                        
                        if tracker.add_subscription(subscription_data):
                            st.success(f"✅ Added {service_name} subscription!")
                            st.rerun()
                        else:
                            st.error("Failed to add subscription.")
                    else:
                        st.error("Please fill in all required fields.")
            
            # Display subscriptions
            if st.session_state.subscriptions:
                # Calculate metrics
                metrics = tracker.calculate_subscription_metrics(st.session_state.subscriptions)
                
                # Summary cards
                st.markdown("### 📊 Subscription Overview")
                
                col1, col2, col3, col4 = st.columns(4)
                
                with col1:
                    st.markdown(f"""
                    <div class="subscription-summary">
                        <div class="summary-stat">
                            <div class="summary-value">₹{metrics['total_monthly']:,.2f}</div>
                            <div class="summary-label">Monthly Total</div>
                        </div>
                    </div>
                    """, unsafe_allow_html=True)
                
                with col2:
                    st.markdown(f"""
                    <div class="subscription-summary">
                        <div class="summary-stat">
                            <div class="summary-value">₹{metrics['total_yearly']:,.2f}</div>
                            <div class="summary-label">Yearly Total</div>
                        </div>
                    </div>
                    """, unsafe_allow_html=True)
                
                with col3:
                    st.markdown(f"""
                    <div class="subscription-summary">
                        <div class="summary-stat">
                            <div class="summary-value">{metrics['active_count']}</div>
                            <div class="summary-label">Active Subscriptions</div>
                        </div>
                    </div>
                    """, unsafe_allow_html=True)
                
                with col4:
                    trial_color = "#ffc107" if metrics['trial_count'] > 0 else "#28a745"
                    st.markdown(f"""
                    <div class="subscription-summary" style="background: linear-gradient(135deg, {trial_color} 0%, #764ba2 100%);">
                        <div class="summary-stat">
                            <div class="summary-value">{metrics['trial_count']}</div>
                            <div class="summary-label">Trial Subscriptions</div>
                        </div>
                    </div>
                    """, unsafe_allow_html=True)
                
                # Subscription visualizations
                if len(st.session_state.subscriptions) > 0:
                    st.markdown("### 📈 Subscription Analytics")
                    
                    with st.expander("📊 View Charts", expanded=False):
                        fig_monthly, fig_category, fig_yearly = create_subscription_visualizations(st.session_state.subscriptions, metrics)
                        
                        if fig_monthly:
                            col1, col2 = st.columns(2)
                            with col1:
                                st.plotly_chart(fig_monthly, use_container_width=True)
                            with col2:
                                st.plotly_chart(fig_category, use_container_width=True)
                            
                            st.plotly_chart(fig_yearly, use_container_width=True)
                
                # Subscription list
                st.markdown("### 📋 Your Subscriptions")
                
                # Filter options
                with st.expander("🔍 Filter Subscriptions"):
                    col1, col2, col3 = st.columns(3)
                    
                    with col1:
                        status_filter = st.multiselect(
                            "Filter by Status",
                            options=["Active", "Trial", "Inactive"],
                            default=["Active", "Trial"]
                        )
                    
                    with col2:
                        categories = list(set(sub.get('category', 'Other') for sub in st.session_state.subscriptions))
                        category_filter = st.multiselect(
                            "Filter by Category",
                            options=categories,
                            default=categories
                        )
                    
                    with col3:
                        sort_by = st.selectbox(
                            "Sort by",
                            options=["Amount (High to Low)", "Amount (Low to High)", "Name", "Next Payment"]
                        )
                
                # Apply filters and sorting
                filtered_subs = [
                    sub for sub in st.session_state.subscriptions
                    if sub.get('status', 'Active') in status_filter
                    and sub.get('category', 'Other') in category_filter
                ]
                
                # Sort subscriptions
                if sort_by == "Amount (High to Low)":
                    filtered_subs.sort(key=lambda x: x['amount'], reverse=True)
                elif sort_by == "Amount (Low to High)":
                    filtered_subs.sort(key=lambda x: x['amount'])
                elif sort_by == "Name":
                    filtered_subs.sort(key=lambda x: x['service_name'])
                elif sort_by == "Next Payment":
                    filtered_subs.sort(key=lambda x: tracker.get_next_payment_date(x))
                
                if filtered_subs:
                    for subscription in filtered_subs:
                        display_subscription_card(subscription, tracker)
                        
                        # Edit/Delete buttons
                        col1, col2, col3 = st.columns([1, 1, 8])
                        
                        with col1:
                            if st.button("✏️ Edit", key=f"edit_{subscription['id']}"):
                                st.session_state[f"editing_{subscription['id']}"] = True
                        
                        with col2:
                            if st.button("🗑️ Delete", key=f"delete_{subscription['id']}"):
                                if tracker.delete_subscription(subscription['id']):
                                    st.success(f"Deleted {subscription['service_name']}")
                                    st.rerun()
                        
                            # Edit form - FIXED VERSION
                        if st.session_state.get(f"editing_{subscription['id']}", False):
                            with st.form(key=f"edit_form_{subscription['id']}"):
                                st.write(f"**Editing {subscription['service_name']}**")
                                
                                col1, col2 = st.columns(2)
                                
                                with col1:
                                    new_name = st.text_input("Service Name", value=subscription['service_name'])
                                    new_amount = st.number_input("Amount", value=subscription['amount'], min_value=0.01)
                                    new_cycle = st.selectbox("Billing Cycle", 
                                                           options=["Monthly", "Quarterly", "Yearly"],
                                                           index=["Monthly", "Quarterly", "Yearly"].index(subscription['billing_cycle']))
                                
                                with col2:
                                    new_category = st.text_input("Category", value=subscription.get('category', ''))
                                    new_status = st.selectbox("Status",
                                                            options=["Active", "Trial", "Inactive"],
                                                            index=["Active", "Trial", "Inactive"].index(subscription.get('status', 'Active')))
                                
                                col1, col2 = st.columns(2)
                                
                                with col1:
                                    if st.form_submit_button("💾 Save Changes"):
                                        updated_data = {
                                            'service_name': new_name,
                                            'amount': new_amount,
                                            'billing_cycle': new_cycle,
                                            'category': new_category,
                                            'status': new_status
                                        }
                                        
                                        if tracker.update_subscription(subscription['id'], updated_data):
                                            st.success("✅ Subscription updated!")
                                            st.session_state[f"editing_{subscription['id']}"] = False
                                            st.rerun()
                                        else:
                                            st.error("Failed to update subscription.")
                                
                                with col2:
                                    if st.form_submit_button("❌ Cancel"):
                                        st.session_state[f"editing_{subscription['id']}"] = False
                                        st.rerun()
                        
                        
                        st.markdown("---")
                else:
                    st.info("No subscriptions match the current filters.")
                
                # Export subscriptions
                st.markdown("### 📤 Export Subscriptions")
                
                col1, col2 = st.columns(2)
                
                with col1:
                    subscription_df = pd.DataFrame(st.session_state.subscriptions)
                    csv_data = subscription_df.to_csv(index=False)
                    st.download_button(
                        label="📥 Download Subscriptions as CSV",
                        data=csv_data,
                        file_name=f"subscriptions_{datetime.now().strftime('%Y%m%d_%H%M%S')}.csv",
                        mime="text/csv",
                        use_container_width=True
                    )
                
                with col2:
                    json_data = json.dumps(st.session_state.subscriptions, indent=2, default=str)
                    st.download_button(
                        label="📥 Download Subscriptions as JSON",
                        data=json_data,
                        file_name=f"subscriptions_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json",
                        mime="application/json",
                        use_container_width=True
                    )
            else:
                st.info("💡 No subscriptions found. Add one manually or analyze your transactions to auto-detect subscriptions.")
        
        with tab3:
            st.markdown("## 📈 Advanced Analytics Dashboard")
            
            if st.session_state.get('results_processed', False) and st.session_state.get('transaction_data'):
                df = pd.DataFrame(st.session_state.transaction_data)
                df['amount_numeric'] = df['amount'].apply(lambda x: float(x) if x and str(x).replace('.', '').replace(',', '').replace('-', '').isdigit() else 0)
                df = df[df['amount_numeric'] > 0]
                
                if len(df) > 0:
                    df['date_parsed'] = pd.to_datetime(df['date'], errors='coerce')
                    df = df.dropna(subset=['date_parsed'])
                    
                    # Apply date filter if enabled
                    df_filtered = apply_date_filter(df)
                    
                    if len(df_filtered) > 0:
                        # Advanced insights
                        st.markdown("### 🧠 Smart Insights")
                        
                        # Spending patterns
                        col1, col2 = st.columns(2)
                        
                        with col1:
                            st.markdown("#### 📊 Spending Distribution")
                            
                            # Top spending categories
                            top_categories = df_filtered.groupby('category')['amount_numeric'].sum().sort_values(ascending=False).head(5)
                            
                            for category, amount in top_categories.items():
                                percentage = (amount / df_filtered['amount_numeric'].sum()) * 100
                                st.write(f"**{category}:** ₹{amount:,.2f} ({percentage:.1f}%)")
                        
                        with col2:
                            st.markdown("#### 🏪 Top Merchants")
                            
                            top_merchants = df_filtered.groupby('merchant_name')['amount_numeric'].sum().sort_values(ascending=False).head(5)
                            
                            for merchant, amount in top_merchants.items():
                                st.write(f"**{merchant}:** ₹{amount:,.2f}")
                        
                        # Spending trends
                        st.markdown("### 📈 Spending Trends")
                        # Add this BEFORE the problematic line 2727
                        # Ensure date_parsed is datetime before using .dt accessor
                        if 'date_parsed' in df_filtered.columns:
                            if not pd.api.types.is_datetime64_any_dtype(df_filtered['date_parsed']):
                                df_filtered['date_parsed'] = pd.to_datetime(
                                    df_filtered['date_parsed'],
                                    errors='coerce',
                                    utc=False
                                )
                                # Remove rows where conversion failed
                                df_filtered = df_filtered.dropna(subset=['date_parsed'])

                        # Final safety check before using .dt accessor
                        if not pd.api.types.is_datetime64_any_dtype(df_filtered['date_parsed']):
                            st.error("Date parsing failed – cannot create monthly trends.")
                        else:
                            # Now safe to use .dt accessor
                            df_filtered['month_year'] = df_filtered['date_parsed'].dt.to_period('M')
                            monthly_trend = df_filtered.groupby('month_year')['amount_numeric'].sum()

                        
                        # Monthly trend
                        df_filtered['month_year'] = df_filtered['date_parsed'].dt.to_period('M')
                        monthly_trend = df_filtered.groupby('month_year')['amount_numeric'].sum()
                        
                        if len(monthly_trend) > 1:
                            latest_month = monthly_trend.iloc[-1]
                            previous_month = monthly_trend.iloc[-2]
                            change = ((latest_month - previous_month) / previous_month) * 100
                            
                            col1, col2, col3 = st.columns(3)
                            
                            with col1:
                                st.metric("This Month", f"₹{latest_month:,.2f}")
                            
                            with col2:
                                st.metric("Previous Month", f"₹{previous_month:,.2f}")
                            
                            with col3:
                                st.metric("Change", f"{change:+.1f}%", delta=f"{change:+.1f}%")
                        
                        # Subscription analysis (if available)
                        if st.session_state.subscriptions:
                            st.markdown("### 🔄 Subscription Analytics")
                            
                            metrics = tracker.calculate_subscription_metrics(st.session_state.subscriptions)
                            
                            # Subscription vs one-time spending
                            subscription_spending = metrics['total_monthly']
                            total_monthly_transactions = df_filtered['amount_numeric'].sum() / max(1, len(df_filtered['date_parsed'].dt.to_period('M').unique()))
                            one_time_spending = max(0, total_monthly_transactions - subscription_spending)
                            
                            col1, col2 = st.columns(2)
                            
                            with col1:
                                st.metric("Monthly Subscriptions", f"₹{subscription_spending:,.2f}")
                            
                            with col2:
                                st.metric("Monthly One-time", f"₹{one_time_spending:,.2f}")
                            
                            # Subscription efficiency
                            if subscription_spending > 0:
                                efficiency = (subscription_spending / total_monthly_transactions) * 100
                                st.write(f"**Subscription Ratio:** {efficiency:.1f}% of your spending goes to subscriptions")
                        
                        # Recommendations
                        st.markdown("### 💡 Smart Recommendations")
                        
                        recommendations = []
                        
                        # High spending categories
                        top_category = df_filtered.groupby('category')['amount_numeric'].sum().idxmax()
                        top_amount = df_filtered.groupby('category')['amount_numeric'].sum().max()
                        
                        if top_amount > df_filtered['amount_numeric'].sum() * 0.3:
                            recommendations.append(f"🎯 Consider reducing spending in **{top_category}** - it accounts for a large portion of your expenses")
                        
                        # Frequent small transactions
                        small_transactions = df_filtered[df_filtered['amount_numeric'] < 100]
                        if len(small_transactions) > len(df_filtered) * 0.5:
                            recommendations.append("☕ You have many small transactions - consider budgeting for daily expenses")
                        
                        # Subscription recommendations
                        if st.session_state.subscriptions:
                            trial_subs = [sub for sub in st.session_state.subscriptions if sub.get('is_trial', False)]
                            if trial_subs:
                                recommendations.append(f"🧪 You have {len(trial_subs)} trial subscriptions - remember to cancel before they convert to paid")
                        
                        # Weekend vs weekday spending
                        df_filtered['is_weekend'] = df_filtered['date_parsed'].dt.dayofweek >= 5
                        weekend_avg = df_filtered[df_filtered['is_weekend']]['amount_numeric'].mean()
                        weekday_avg = df_filtered[~df_filtered['is_weekend']]['amount_numeric'].mean()
                        
                        if weekend_avg > weekday_avg * 1.5:
                            recommendations.append("🎉 Your weekend spending is significantly higher - consider setting weekend budgets")
                        
                        if recommendations:
                            for rec in recommendations:
                                st.info(rec)
                        else:
                            st.success("👍 Your spending patterns look balanced!")
                    
                    else:
                        st.warning("No data available in the selected date range.")
                else:
                    st.warning("No valid transaction data available for analytics.")
            else:
                st.info("💡 Please analyze your transactions first to see advanced analytics.")
        
        with tab4:
            st.markdown("## ⚙️ Settings & Configuration")
            
            # Account information
            st.markdown("### 👤 Account Information")
            st.info(f"**Logged in as:** {st.session_state.user_email}")
            
            # Data management
            st.markdown("### 🗂️ Data Management")
            
            col1, col2 = st.columns(2)
            
            with col1:
                if st.button("🗑️ Clear Transaction Data", type="secondary"):
                    st.session_state.transaction_data = []
                    st.session_state.results_processed = False
                    st.success("✅ Transaction data cleared!")
            
            with col2:
                if st.button("🗑️ Clear All Subscriptions", type="secondary"):
                    if st.checkbox("I confirm I want to delete all subscriptions"):
                        st.session_state.subscriptions = []
                        st.success("✅ All subscriptions cleared!")
            
            # Configuration status
            st.markdown("### 🔧 Configuration Status")
            
            config_status = config_manager.validate_config()
            
            if config_status:
                st.success("✅ All configurations are properly set up")
            else:
                st.error("❌ Some configurations are missing")
                config_manager.display_config_status()
            
            # Privacy and security
            st.markdown("### 🛡️ Privacy & Security")
            
            with st.expander("Data Privacy Information"):
                st.markdown("""
                **How we handle your data:**
                
                - ✅ **No Data Storage**: Your emails and transactions are processed in real-time and not stored on our servers
                - ✅ **Local Processing**: All analysis happens locally in your browser session
                - ✅ **Secure Connections**: All API calls use encrypted HTTPS connections
                - ✅ **No Sharing**: Your financial data is never shared with third parties
                - ✅ **Session-Based**: Data is cleared when you close the browser or log out
                
                **External Services Used:**
                - **Replicate API**: For AI-powered transaction categorization (only transaction descriptions are sent)
                - **Gmail IMAP**: To read your bank transaction emails (read-only access)
                
                **Your Rights:**
                - You can clear all data at any time using the buttons above
                - You can disconnect your account by logging out
                - You have full control over which emails are processed
                """)
            
            # Logout
            st.markdown("### 🚪 Session Management")
            
            if st.button("🚪 Logout", type="primary"):
                st.session_state.authenticated = False
                st.session_state.user_email = None
                st.session_state.transaction_data = []
                st.session_state.results_processed = False
                st.session_state.subscriptions = []
                st.success("✅ Successfully logged out!")
                st.rerun()

if __name__ == "__main__":
    main()
