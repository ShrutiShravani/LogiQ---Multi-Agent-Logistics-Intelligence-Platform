def test_all():
    """
    Returns True only if ALL external services are available.
    """
    status_report = {}
    
    # 1. Check Postgres
    status_report['postgres'] = check_postgres() 
    
    # 2. Check Redis
    status_report['redis'] = check_redis()
    
    # 3. Check Disk/Folders (Senior level addition)
    status_report['storage'] = os.access('data/processed', os.W_OK)

    # Print the pretty table for the logs
    print_report(status_report)

    # Return True only if every single value is True
    return all(status_report.values())