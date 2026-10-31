*** Settings ***
# Run with:  AGENT_MODEL=gpt-4o OPENAI_API_KEY=... robot -d results tests/demo.robot
Library    Browser
Library    RobotAgent

*** Test Cases ***
Login With The Agent
    New Browser    chromium    headless=True
    New Page       https://www.saucedemo.com/
    ${summary}=    AGENT ACT    log in as standard_user with password secret_sauce
    Log            ${summary}
    AGENT ASSERT   the page shows the product list, titled Products

Agent Detects A Bad Login
    New Page       https://www.saucedemo.com/
    AGENT ACT      try to log in as locked_out_user with password secret_sauce
    AGENT ASSERT   the page shows a login failure error message
