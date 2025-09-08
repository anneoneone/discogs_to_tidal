"""
String manipulation utilities.
"""
import re
import unicodedata


def normalize_string(text: str) -> str:
    """
    Normalize a string for comparison purposes.
    
    Args:
        text: Input string to normalize
        
    Returns:
        Normalized string
    """
    if not text:
        return ""
    
    # Convert to lowercase
    text = text.lower()
    
    # Remove unicode accents and normalize
    text = unicodedata.normalize('NFD', text)
    text = ''.join(c for c in text if unicodedata.category(c) != 'Mn')
    
    # Remove common punctuation and special characters
    text = re.sub(r'[^\w\s]', ' ', text)
    
    # Replace multiple whitespace with single space
    text = re.sub(r'\s+', ' ', text)
    
    # Strip leading/trailing whitespace
    text = text.strip()
    
    return text
