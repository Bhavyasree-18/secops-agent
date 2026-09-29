from app.services.incident_agent import get_incident_agent


def test_incident_agent():
    agent = get_incident_agent()

    result = agent.analyze(
        """
        Multiple failed login attempts were detected against
        an employee account from several external IP addresses.
        One login attempt succeeded.
        The account does not currently have MFA enabled.
        """
    )

    assert result.response
    assert isinstance(result.response, str)

    print("\n========== INCIDENT RESPONSE ==========\n")
    print(result.response)

    print("\n========== MEMORIES USED ==========\n")

    for memory in result.memories_used:
        print(memory)