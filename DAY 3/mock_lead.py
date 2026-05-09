mock_database = []

def create_lead(data):

    mock_database.append(data)

    return {
        "lead_created": True,
        "stored_data": data,
        "total_leads": len(mock_database)
    }