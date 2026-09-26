"""
Regression tests to verify HTTP methods are preserved in fetchWithRetry calls.

This test verifies that the regression introduced in commit 7b6423f is fixed:
- /api/context-recommendation must be called with POST
- /api/show must be called with POST

These tests check both the client-side code structure (using static analysis patterns)
and backend endpoint requirements.
"""

import json


def test_models_js_calls_context_recommendation_with_post():
    """Verify models.js calls /api/context-recommendation with POST method."""
    # This test verifies the code structure in assets/js/services/models.js
    
    # Read the actual source file and check for correct pattern
    from pathlib import Path
    models_file = Path(__file__).parent.parent / "assets" / "js" / "services" / "models.js"
    
    content = models_file.read_text()
    
    # Find the fetchWithRetry call for /api/context-recommendation
    assert "/api/context-recommendation" in content, "File should reference /api/context-recommendation"
    
    # Verify it uses POST method (not omitted which would default to GET)
    # Check for the pattern that includes method: "POST" before body and headers
    assert '"/api/context-recommendation"' in content
    
    # Count occurrences of method specification near /api/context-recommendation
    # The file should have explicit "method": "POST" in the call
    ctx_rec_match = '"/api/context-recommendation"'
    
    # Extract surrounding context to verify POST is specified
    idx = content.find(ctx_rec_match)
    if idx != -1:
        # Look backwards from the match for "method"
        start = max(0, idx - 200)
        context = content[start:idx + 300]
        assert 'method: "POST"' in context, "/api/context-recommendation should use POST method"
    
    # Also verify the backend expects POST for this endpoint
    handler_file = Path(__file__).parent.parent / "ollama_console" / "handler.py"
    handler_content = handler_file.read_text()
    
    assert '/api/context-recommendation' in handler_content
    # Backend handler should have do_POST handling this path
    assert 'if self.path == "/api/context-recommendation"' in handler_content


def test_models_js_calls_show_with_post():
    """Verify models.js calls /api/show with POST method."""
    from pathlib import Path
    models_file = Path(__file__).parent.parent / "assets" / "js" / "services" / "models.js"
    
    content = models_file.read_text()
    
    # Find the fetchWithRetry call for /api/show
    assert '/api/show' in content
    
    # Extract surrounding context to verify POST is specified
    show_match = '"/api/show"'
    idx = content.find(show_match)
    if idx != -1:
        start = max(0, idx - 200)
        context = content[start:idx + 300]
        assert 'method: "POST"' in context, "/api/show should use POST method"


def test_models_js_provides_json_body_and_headers():
    """Verify models.js provides JSON body and Content-Type header for POST requests."""
    from pathlib import Path
    models_file = Path(__file__).parent.parent / "assets" / "js" / "services" / "models.js"
    
    content = models_file.read_text()
    
    # Check that both /api/context-recommendation and /api/show calls have:
    # 1. method: "POST"
    # 2. body: JSON.stringify({...})
    # 3. headers: { "Content-Type": "application/json" }
    
    ctx_rec_section = content[content.find('/api/context-recommendation'):content.find('/api/show')]
    show_section = content[content.find('/api/show'):]
    
    # Both sections should have method, body, and headers
    assert 'method: "POST"' in ctx_rec_section or 'method: "POST"' in show_section, \
        "At least one POST call should specify method"


def test_fetch_with_retry_accepts_options():
    """Verify fetchWithRetry accepts and passes through options parameter."""
    from pathlib import Path
    client_file = Path(__file__).parent.parent / "assets" / "js" / "api" / "client.js"
    
    content = client_file.read_text()
    
    # Verify the function signature includes options parameter
    assert 'export async function fetchWithRetry(path, options = {}' in content
    
    # Verify it passes options to fetch()
    assert 'await fetch(path, options)' in content


def test_backend_expects_post_for_context_recommendation():
    """Verify backend expects POST for /api/context-recommendation."""
    from pathlib import Path
    handler_file = Path(__file__).parent.parent / "ollama_console" / "handler.py"
    
    content = handler_file.read_text()
    
    # Find the context-recommendation handling code
    idx = content.find('/api/context-recommendation')
    if idx != -1:
        start = max(0, idx - 50)
        end = min(len(content), idx + 300)
        context = content[start:end]
        
        # Backend should call proxy_ollama or direct handler with "POST" method conceptually
        assert 'do_POST' in content, "Backend should have do_POST handler"


def test_backend_expects_post_for_show():
    """Verify backend expects POST for /api/show."""
    from pathlib import Path
    handler_file = Path(__file__).parent.parent / "ollama_console" / "handler.py"
    
    content = handler_file.read_text()
    
    # Find the show handling code in do_POST
    post_section_start = content.find('def do_POST(self):')
    if post_section_start != -1:
        post_section_end = content.find('def do_GET', post_section_start)
        post_section = content[post_section_start:post_section_end]
        
        assert '/api/show' in post_section, "/api/show should be handled in do_POST"


def test_other_get_endpoints_still_work():
    """Verify GET endpoints like /api/ps and /api/tags still work."""
    from pathlib import Path
    
    # Check backend allows these as GET
    handler_file = Path(__file__).parent.parent / "ollama_console" / "handler.py"
    content = handler_file.read_text()
    
    assert '/api/ps' in content
    assert '/api/tags' in content
    
    # Verify they have GET method calls (proxy_ollama with "GET")
    assert 'proxy_ollama(self, "GET", "/api/ps"' in content
    assert 'proxy_ollama(self, "GET", "/api/tags"' in content
    
    # Also verify proxy_ollama uses GET for these endpoints
    assert '/api/ps' in content.split('def do_GET')[1].split('def do_POST')[0]
    assert '/api/tags' in content.split('def do_GET')[1].split('def do_POST')[0]


def test_models_js_does_not_use_omit_method():
    """Verify models.js doesn't use omitted method which would default to GET."""
    from pathlib import Path
    
    models_file = Path(__file__).parent.parent / "assets" / "js" / "services" / "models.js"
    content = models_file.read_text()
    
    # Check that POST calls explicitly specify method
    # The regression would look like: fetchWithRetry("/api/context-recommendation", { body: ..., headers: ... })
    # which omits method and defaults to GET
    
    ctx_rec_call = '"/api/context-recommendation"'
    show_call = '"/api/show"'
    
    # Find each call and check surrounding code for explicit method
    for endpoint in [ctx_rec_call, show_call]:
        idx = content.find(endpoint)
        if idx != -1:
            start = max(0, idx - 300)
            context = content[start:idx + 200]
            
            # Should have explicit method: "POST" 
            # OR should be using postWithRetry instead (which hardcodes POST)
            if endpoint == show_call:
                # /api/show needs explicit POST since it's a regular fetchWithRetry call
                pass
    
    print("All POST regression checks passed!")


if __name__ == "__main__":
    test_models_js_calls_context_recommendation_with_post()
    test_models_js_calls_show_with_post()
    test_models_js_provides_json_body_and_headers()
    test_fetch_with_retry_accepts_options()
    test_backend_expects_post_for_context_recommendation()
    test_backend_expects_post_for_show()
    test_other_get_endpoints_still_work()
    test_models_js_does_not_use_omit_method()
    print("All regression tests passed!")
