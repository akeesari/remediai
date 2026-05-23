def exceptions_kql(lookback_minutes: int = 10, limit: int = 500) -> str:
    """KQL query that fetches .NET exceptions from Application Insights."""
    return f"""
exceptions
| where timestamp > ago({lookback_minutes}m)
| project
    timestamp,
    operation_Id,
    type,
    outerMessage,
    innermostMessage,
    innermostType,
    assembly,
    method,
    outerAssembly,
    outerMethod,
    details,
    client_Type,
    operation_Name,
    cloud_RoleName,
    application_Version,
    itemId
| order by timestamp desc
| limit {limit}
"""
