import re

def test(academic_year_name: str) -> str:
    match = re.search(r'\d{4}', str(academic_year_name))
    year_val = '00'
    if match:
        matched_str = str(match.group(0))
        year_val = matched_str[-2:]
        
        # Another test:
        alt_str = match.group(0)
        if isinstance(alt_str, str):
            year_val = alt_str[-2:]
    return year_val
