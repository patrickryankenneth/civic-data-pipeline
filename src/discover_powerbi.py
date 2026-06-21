import asyncio
import json
from playwright.async_api import async_playwright

async def run():
    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=True)
        page = await browser.new_page()

        captured_data = None

        def handle_request(request):
            nonlocal captured_data
            if request.method == "POST" and "querydata" in request.url:
                print(f"Captured relevant request: {request.url}")
                try:
                    payload = request.post_data
                    headers = request.headers
                    captured_data = {
                        "url": request.url,
                        "headers": headers,
                        "payload": json.loads(payload) if payload else None
                    }
                except Exception as e:
                    print(f"Error parsing request: {e}")

        page.on("request", handle_request)

        print("Navigating to URL...")
        await page.goto("https://app.powerbigov.us/view?r=eyJrIjoiNmZmMmMwNzMtNjRjNC00Zjg1LWFkNTctNGVmNTIxMTNjYTQ0IiwidCI6IjcyN2Q1NDFjLTBhZjEtNDVmNi1hYmYzLTM0YzJjZjQ0ODNmZSJ9")
        
        # Wait a bit for the app to load and trigger the query
        await page.wait_for_timeout(10000)

        if captured_data:
            with open("src/powerbi_schema.json", "w") as f:
                json.dump(captured_data, f, indent=4)
            print("Successfully saved data to src/powerbi_schema.json")
        else:
            print("Failed to capture any request matching 'querydata'")

        await browser.close()

if __name__ == "__main__":
    asyncio.run(run())
