# export_cookies.py
import browser_cookie3
import sys

def export_cookies():
    try:
        # Try to get cookies from Chrome
        cookies = browser_cookie3.chrome(domain_name='youtube.com')
    except:
        try:
            # Try Firefox if Chrome fails
            cookies = browser_cookie3.firefox(domain_name='youtube.com')
        except:
            print("Could not extract cookies from browser")
            return
    
    # Write cookies to file in Netscape format
    with open('cookies.txt', 'w') as f:
        for cookie in cookies:
            if cookie.domain.endswith('youtube.com'):
                f.write('\t'.join([
                    cookie.domain,
                    'TRUE' if cookie.domain.startswith('.') else 'FALSE',
                    cookie.path,
                    'TRUE' if cookie.secure else 'FALSE',
                    str(int(cookie.expires)) if cookie.expires else '0',
                    cookie.name,
                    cookie.value
                ]) + '\n')
    
    print("Cookies exported to cookies.txt")

if __name__ == '__main__':
    export_cookies()
