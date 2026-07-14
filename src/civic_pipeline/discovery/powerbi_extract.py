import json

def parse_powerbi_data(data):
    # This structure is common in PowerBI nested JSON
    # ValueDicts contains the actual string values mapped to indices
    # PH -> DM0 contains the matrix of indices
    dsr = data['results'][0]['result']['data']['dsr']['DS'][0]
    
    value_dicts = dsr['ValueDicts']
    dm0 = dsr['PH'][0]['DM0']
    
    # Example: Access first item in DM0
    # DM0 is list of dicts. 'C' is list of indices or values.
    # If it's a list of indices, look up in ValueDicts
    
    records = []
    
    # We need to map 'D0', 'D1', etc. from ValueDicts
    # The keys in ValueDicts represent columns, e.g., 'D0': [...]
    
    for row in dm0:
        if 'C' not in row:
            continue
        
        row_data = {}
        for i, val in enumerate(row['C']):
            if isinstance(val, int):
                # Look up from ValueDicts
                col_key = f'D{i}'
                if col_key in value_dicts:
                    row_data[col_key] = value_dicts[col_key][val]
                else:
                    row_data[col_key] = val
            else:
                # Direct value
                row_data[f'D{i}'] = val
        records.append(row_data)
        
    return records

if __name__ == "__main__":
    with open('/ramdisk/test_response.json', 'r') as f:
        data = json.load(f)
        records = parse_powerbi_data(data)
        print(f"Extracted {len(records)} records")
        print(records[:5])
