import json
import requests
import os

def ingest_contracts():
    # Load schema
    with open('data/schemas/powerbi_schema.json', 'r') as f:
        schema = json.load(f)

    url = schema['url']
    headers = schema['headers']
    payload = schema['payload']

    # Execute request
    response = requests.post(url, json=payload, headers=headers)
    response.raise_for_status()
    data = response.json()

    # Flatten logic for PowerBI nested JSON
    # Typically found in results[0]['result']['data']['dsr']['DS'][0]['ValueDicts'] or 'PH'
    # Based on standard PowerBI Query DataShape structure:
    try:
        # Accessing the nested results
        dsr = data['results'][0]['result']['data']['dsr']
        
        # PowerBI usually returns a header section and a data section (PH and DS)
        # This is a simplified extraction
        records = []
        # DS -> Projections -> Rows
        # Note: Depending on actual payload, this path might need refinement
        # This is a generic approach to extract the 'rows'
        
        rows = dsr['DS'][0]['PH'][0]['DM0'] # Example path, needs verification
        
        # Save to RAM disk
        os.makedirs('/ramdisk', exist_ok=True)
        with open('/ramdisk/raw_contracts.json', 'w') as f:
            json.dump(rows, f)
            
        print(f"Successfully saved {len(rows)} records to /ramdisk/raw_contracts.json")
        
    except (KeyError, IndexError) as e:
        print(f"Error parsing PowerBI response: {e}")
        # Print a bit of response to debug if failed
        print(json.dumps(data, indent=2)[:500])

if __name__ == "__main__":
    ingest_contracts()
