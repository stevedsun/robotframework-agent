*** Settings ***
# Run with:  AGENT_MODEL=gpt-4o OPENAI_API_KEY=... robot -d results tests/demo.robot
Library    Browser
Library    RobotAgent

*** Test Cases ***
Login With The Agent
    New Browser    chromium    headless=True
    New Page       https://www.saucedemo.com/
    ${summary}=    AGENT ACT    使用用户 standard_user 和密码 secret_sauce 登录
    Log            ${summary}
    AGENT ASSERT   页面显示了商品列表，标题为 Products

Agent Detects A Bad Login
    New Page       https://www.saucedemo.com/
    AGENT ACT      尝试用用户 locked_out_user 和密码 secret_sauce 登录
    AGENT ASSERT   页面显示了一条登录失败的错误提示
