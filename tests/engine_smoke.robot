*** Settings ***
# Engine smoke test: no LLM involved, verifies observe.js + Browser glue.
# Node ids are deterministic for the fixed fixture: n1=username, n2=password,
# n3=login button (document order, fresh page).
Library    Browser
Library    RobotAgent
Library    engine_smoke.py

*** Test Cases ***
Engine Observes And Drives The Login Page
    New Browser    chromium    headless=True
    New Page       file://${CURDIR}/fixtures/login.html
    ${obs}=        Observe Page
    Log            ${obs}
    Should Contain    ${obs}    textbox "Username"
    Should Contain    ${obs}    textbox "Password"
    Should Contain    ${obs}    button "Login"
    ${size}=       Screenshot Size
    Should Be True    ${size} > 1000

    Type Into Node    n1    standard_user
    Type Into Node    n2    secret_sauce
    ${obs_filled}=    Observe Page
    Should Contain    ${obs_filled}    value="standard_user"
    Click Node        n3
    ${obs2}=          Observe Page
    Log               ${obs2}
    Should Contain    ${obs2}    Products
    Should Contain    ${obs2}    Sauce Labs Backpack
