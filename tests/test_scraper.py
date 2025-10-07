import sys, os
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from backend.app.data_preparation.scrapping import WHOScraper

def test_extract_article(monkeypatch):
    # simulation de réponse HTML (mock)
    html = """
    <html><body>
        <h1>Test Disease</h1>
        <article class="sf-detail-body-wrapper">
            <p>This is a test paragraph.</p>
            <li>Symptom A</li>
        </article>
    </body></html>
    """

    class MockResponse:
        def __init__(self, text): self.text = text
        def raise_for_status(self): pass

    def mock_get(*args, **kwargs): return MockResponse(html)
    monkeypatch.setattr("requests.get", mock_get)

    scraper = WHOScraper()
    title, content = scraper.extract_article("https://mock-url")
    assert "Test Disease" in title
    assert "Symptom A" in content
